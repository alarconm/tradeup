"""
Loyalty Page Builder API Endpoints

Manage loyalty landing page configuration.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from app.services.page_builder_service import PageBuilderService

page_builder_bp = Blueprint('page_builder', __name__)


def get_service():
    """Get page builder service for current tenant."""
    settings = g.tenant.settings or {}
    return PageBuilderService(g.tenant.id, settings)


@page_builder_bp.route('/config', methods=['GET'])
@require_shopify_auth
def get_page_config():
    """Get current page configuration."""
    service = get_service()
    config = service.get_page_config()

    return jsonify({
        'success': True,
        'config': config,
    })


@page_builder_bp.route('/config', methods=['PUT'])
@require_shopify_auth
def update_page_config():
    """Update page configuration."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    service = get_service()
    try:
        config = service.update_page_config(data)
        return jsonify({
            'success': True,
            'config': config,
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@page_builder_bp.route('/templates', methods=['GET'])
@require_shopify_auth
def get_templates():
    """Get available page templates."""
    service = get_service()
    templates = service.get_available_templates()

    return jsonify({
        'success': True,
        'templates': templates,
    })


@page_builder_bp.route('/templates/<template_id>/apply', methods=['POST'])
@require_shopify_auth
def apply_template(template_id):
    """Apply a page template."""
    service = get_service()
    try:
        config = service.apply_template(template_id)
        return jsonify({
            'success': True,
            'config': config,
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@page_builder_bp.route('/sections/<section_id>', methods=['PUT'])
@require_shopify_auth
def update_section(section_id):
    """Update a specific section's settings."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    service = get_service()
    config = service.update_section(section_id, data)

    return jsonify({
        'success': True,
        'config': config,
    })


@page_builder_bp.route('/sections/<section_id>/toggle', methods=['POST'])
@require_shopify_auth
def toggle_section(section_id):
    """Enable or disable a section."""
    data = request.get_json() or {}
    enabled = data.get('enabled', True)

    service = get_service()
    config = service.toggle_section(section_id, enabled)

    return jsonify({
        'success': True,
        'config': config,
    })


@page_builder_bp.route('/sections/reorder', methods=['POST'])
@require_shopify_auth
def reorder_sections():
    """Reorder page sections."""
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': 'Section order required'}), 400

    service = get_service()
    config = service.reorder_sections(data['order'])

    return jsonify({
        'success': True,
        'config': config,
    })


@page_builder_bp.route('/preview', methods=['GET'])
@require_shopify_auth
def preview_page():
    """Get HTML preview of the page."""
    service = get_service()
    html = service.render_page_html()

    return html, 200, {'Content-Type': 'text/html'}
