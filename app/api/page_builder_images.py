"""
Page Builder Images API - LP-009

Handles image upload for loyalty page sections.
Supports:
- Hero backgrounds
- Section icons/logos
- Custom images

Images are stored locally in static/uploads/page-builder/
and can be migrated to S3 or Shopify Files in the future.
"""

import os
import uuid
import base64
from datetime import datetime
from flask import Blueprint, request, jsonify, g, current_app, url_for
from werkzeug.utils import secure_filename

from app.middleware.shopify_auth import require_shopify_auth

page_builder_images_bp = Blueprint('page_builder_images', __name__)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

# Max file size (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024

# Max dimensions (optional, for validation)
MAX_WIDTH = 4096
MAX_HEIGHT = 4096


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_upload_folder() -> str:
    """Get the upload folder path for the current tenant."""
    # Get app root directory
    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Create tenant-specific folder
    tenant_id = str(g.tenant.id)
    upload_folder = os.path.join(app_root, 'static', 'uploads', 'page-builder', tenant_id)

    # Ensure folder exists
    os.makedirs(upload_folder, exist_ok=True)

    return upload_folder


def get_image_url(filename: str) -> str:
    """Get the public URL for an uploaded image."""
    tenant_id = str(g.tenant.id)
    # Use relative path that Flask can serve
    return f'/static/uploads/page-builder/{tenant_id}/{filename}'


@page_builder_images_bp.route('/upload', methods=['POST'])
@require_shopify_auth
def upload_image():
    """
    Upload an image for use in loyalty page sections.

    Accepts:
    - multipart/form-data with 'file' field
    - JSON with base64-encoded 'image' field

    Returns:
        {
            "success": true,
            "url": "/static/uploads/page-builder/{tenant_id}/{filename}",
            "filename": "abc123_image.png",
            "size": 12345,
            "content_type": "image/png"
        }
    """
    upload_folder = get_upload_folder()

    # Check content type
    content_type = request.content_type or ''

    if 'multipart/form-data' in content_type:
        # Handle file upload
        return _handle_file_upload(upload_folder)
    elif 'application/json' in content_type:
        # Handle base64 upload
        return _handle_base64_upload(upload_folder)
    else:
        return jsonify({
            'error': 'Unsupported content type. Use multipart/form-data or application/json'
        }), 400


def _handle_file_upload(upload_folder: str):
    """Handle multipart file upload."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({
            'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400

    # Check file size by reading content
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to start

    if file_size > MAX_FILE_SIZE:
        return jsonify({
            'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB'
        }), 400

    # Generate unique filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.utcnow().strftime('%Y%m%d')
    filename = secure_filename(f'{timestamp}_{unique_id}.{ext}')

    # Save file
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)

    # Get content type
    content_type_map = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'svg': 'image/svg+xml',
    }

    return jsonify({
        'success': True,
        'url': get_image_url(filename),
        'filename': filename,
        'size': file_size,
        'content_type': content_type_map.get(ext, 'application/octet-stream'),
    })


def _handle_base64_upload(upload_folder: str):
    """Handle base64-encoded image upload."""
    data = request.get_json()

    if not data or 'image' not in data:
        return jsonify({'error': 'No image data provided'}), 400

    image_data = data['image']

    # Parse data URL format: data:image/png;base64,xxxxx
    if image_data.startswith('data:'):
        try:
            header, encoded = image_data.split(',', 1)
            # Extract content type: data:image/png;base64 -> image/png
            content_type = header.split(':')[1].split(';')[0]
            ext = content_type.split('/')[1]

            # Handle svg+xml -> svg
            if '+' in ext:
                ext = ext.split('+')[0]

        except (ValueError, IndexError):
            return jsonify({'error': 'Invalid data URL format'}), 400
    else:
        # Assume base64 without header
        encoded = image_data
        ext = data.get('extension', 'png')
        content_type = f'image/{ext}'

    # Validate extension
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400

    # Decode base64
    try:
        image_bytes = base64.b64decode(encoded)
    except Exception:
        return jsonify({'error': 'Invalid base64 encoding'}), 400

    # Check size
    if len(image_bytes) > MAX_FILE_SIZE:
        return jsonify({
            'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB'
        }), 400

    # Generate unique filename
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.utcnow().strftime('%Y%m%d')
    filename = f'{timestamp}_{unique_id}.{ext}'

    # Save file
    filepath = os.path.join(upload_folder, filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)

    return jsonify({
        'success': True,
        'url': get_image_url(filename),
        'filename': filename,
        'size': len(image_bytes),
        'content_type': content_type,
    })


@page_builder_images_bp.route('/list', methods=['GET'])
@require_shopify_auth
def list_images():
    """
    List all uploaded images for the current tenant.

    Returns:
        {
            "success": true,
            "images": [
                {
                    "url": "/static/uploads/page-builder/{tenant_id}/image.png",
                    "filename": "image.png",
                    "size": 12345,
                    "uploaded_at": "2026-01-22T10:30:00Z"
                }
            ]
        }
    """
    upload_folder = get_upload_folder()

    images = []

    if os.path.exists(upload_folder):
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                images.append({
                    'url': get_image_url(filename),
                    'filename': filename,
                    'size': stat.st_size,
                    'uploaded_at': datetime.fromtimestamp(stat.st_mtime).isoformat() + 'Z',
                })

    # Sort by upload date (newest first)
    images.sort(key=lambda x: x['uploaded_at'], reverse=True)

    return jsonify({
        'success': True,
        'images': images,
    })


@page_builder_images_bp.route('/delete/<filename>', methods=['DELETE'])
@require_shopify_auth
def delete_image(filename: str):
    """
    Delete an uploaded image.

    Args:
        filename: The filename to delete

    Returns:
        {"success": true}
    """
    upload_folder = get_upload_folder()

    # Secure the filename to prevent path traversal
    safe_filename = secure_filename(filename)

    if not safe_filename:
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(upload_folder, safe_filename)

    if not os.path.exists(filepath):
        return jsonify({'error': 'Image not found'}), 404

    # Ensure file is within upload folder (extra security)
    if not os.path.abspath(filepath).startswith(os.path.abspath(upload_folder)):
        return jsonify({'error': 'Invalid path'}), 400

    try:
        os.remove(filepath)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Failed to delete image: {str(e)}'}), 500
