"""
Widget Visual Builder API Endpoints

Manage customer-facing loyalty widget configuration.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from app.services.widget_builder_service import WidgetBuilderService

widget_builder_bp = Blueprint('widget_builder', __name__)


def get_service():
    """Get widget builder service for current tenant."""
    settings = g.tenant.settings or {}
    return WidgetBuilderService(g.tenant.id, settings)


@widget_builder_bp.route('/config', methods=['GET'])
@require_shopify_auth
def get_widget_config():
    """Get current widget configuration."""
    service = get_service()
    config = service.get_widget_config()

    return jsonify({
        'success': True,
        'config': config,
    })


@widget_builder_bp.route('/config', methods=['PUT'])
@require_shopify_auth
def update_widget_config():
    """Update widget configuration."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    service = get_service()
    try:
        config = service.update_widget_config(data)
        return jsonify({
            'success': True,
            'config': config,
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@widget_builder_bp.route('/themes', methods=['GET'])
@require_shopify_auth
def get_themes():
    """Get available widget themes."""
    service = get_service()
    themes = service.get_available_themes()

    return jsonify({
        'success': True,
        'themes': themes,
    })


@widget_builder_bp.route('/themes/<theme_id>/apply', methods=['POST'])
@require_shopify_auth
def apply_theme(theme_id):
    """Apply a widget theme."""
    service = get_service()
    try:
        config = service.apply_theme(theme_id)
        return jsonify({
            'success': True,
            'config': config,
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@widget_builder_bp.route('/embed-code', methods=['GET'])
@require_shopify_auth
def get_embed_code():
    """Get the widget embed code."""
    service = get_service()
    embed_code = service.get_widget_embed_code()

    return jsonify({
        'success': True,
        'embed_code': embed_code,
    })


@widget_builder_bp.route('/css', methods=['GET'])
@require_shopify_auth
def get_css_variables():
    """Get CSS variables for the widget."""
    service = get_service()
    css = service.generate_css_variables()

    return css, 200, {'Content-Type': 'text/css'}
