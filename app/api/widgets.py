"""
Widget Settings API Endpoints

Manage widget configurations for tenants.
CRUD operations for enabling, disabling, and configuring widgets.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from ..extensions import db
from ..models.widget import Widget, WidgetType, DEFAULT_WIDGET_CONFIGS

widgets_bp = Blueprint('widgets', __name__)


@widgets_bp.route('', methods=['GET'])
@require_shopify_auth
def list_widgets():
    """
    GET /api/widgets - List all widgets for tenant

    Returns all widget configurations for the current tenant,
    creating default widgets if none exist.
    """
    tenant_id = g.tenant.id

    # Get all widgets for tenant
    widgets = Widget.get_all_for_tenant(tenant_id)

    # If no widgets exist, create defaults
    if not widgets:
        widgets = Widget.create_defaults_for_tenant(tenant_id)

    # Ensure all widget types exist
    existing_types = {w.widget_type for w in widgets}
    for widget_type in WidgetType:
        if widget_type.value not in existing_types:
            widget = Widget.get_or_create(tenant_id, widget_type.value)
            widgets.append(widget)

    db.session.commit()

    return jsonify({
        'success': True,
        'widgets': [w.to_dict() for w in widgets],
        'available_types': [wt.value for wt in WidgetType],
    })


@widgets_bp.route('/<widget_type>', methods=['GET'])
@require_shopify_auth
def get_widget(widget_type):
    """
    GET /api/widgets/{type} - Get specific widget config

    Args:
        widget_type: The widget type (points_balance, tier_badge, rewards_launcher, referral_prompt)
    """
    tenant_id = g.tenant.id

    # Validate widget type
    valid_types = [wt.value for wt in WidgetType]
    if widget_type not in valid_types:
        return jsonify({
            'error': f'Invalid widget type. Must be one of: {", ".join(valid_types)}'
        }), 400

    # Get or create widget
    widget = Widget.get_or_create(tenant_id, widget_type)
    db.session.commit()

    # Include default config for reference
    try:
        wt = WidgetType(widget_type)
        default_config = DEFAULT_WIDGET_CONFIGS.get(wt, {})
    except ValueError:
        default_config = {}

    return jsonify({
        'success': True,
        'widget': widget.to_dict(),
        'default_config': default_config,
    })


@widgets_bp.route('/<widget_type>', methods=['PUT'])
@require_shopify_auth
def update_widget(widget_type):
    """
    PUT /api/widgets/{type} - Update widget config

    Args:
        widget_type: The widget type to update

    Request Body:
        {
            "config": {
                "position": {...},
                "styling": {...},
                "content": {...},
                "behavior": {...}
            },
            "is_enabled": true/false  (optional)
        }
    """
    tenant_id = g.tenant.id

    # Validate widget type
    valid_types = [wt.value for wt in WidgetType]
    if widget_type not in valid_types:
        return jsonify({
            'error': f'Invalid widget type. Must be one of: {", ".join(valid_types)}'
        }), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Get or create widget
    widget = Widget.get_or_create(tenant_id, widget_type)

    # Update config if provided
    if 'config' in data:
        config = data['config']
        if not isinstance(config, dict):
            return jsonify({'error': 'Config must be a dictionary'}), 400
        widget.update_config(config)

    # Update enabled status if provided
    if 'is_enabled' in data:
        widget.is_enabled = bool(data['is_enabled'])

    db.session.commit()

    return jsonify({
        'success': True,
        'widget': widget.to_dict(),
    })


@widgets_bp.route('/<widget_type>/enable', methods=['POST'])
@require_shopify_auth
def enable_widget(widget_type):
    """
    POST /api/widgets/{type}/enable - Enable widget

    Args:
        widget_type: The widget type to enable
    """
    tenant_id = g.tenant.id

    # Validate widget type
    valid_types = [wt.value for wt in WidgetType]
    if widget_type not in valid_types:
        return jsonify({
            'error': f'Invalid widget type. Must be one of: {", ".join(valid_types)}'
        }), 400

    # Get or create widget
    widget = Widget.get_or_create(tenant_id, widget_type)
    widget.is_enabled = True
    db.session.commit()

    return jsonify({
        'success': True,
        'widget': widget.to_dict(),
        'message': f'Widget {widget_type} has been enabled',
    })


@widgets_bp.route('/<widget_type>/disable', methods=['POST'])
@require_shopify_auth
def disable_widget(widget_type):
    """
    POST /api/widgets/{type}/disable - Disable widget

    Args:
        widget_type: The widget type to disable
    """
    tenant_id = g.tenant.id

    # Validate widget type
    valid_types = [wt.value for wt in WidgetType]
    if widget_type not in valid_types:
        return jsonify({
            'error': f'Invalid widget type. Must be one of: {", ".join(valid_types)}'
        }), 400

    # Get or create widget
    widget = Widget.get_or_create(tenant_id, widget_type)
    widget.is_enabled = False
    db.session.commit()

    return jsonify({
        'success': True,
        'widget': widget.to_dict(),
        'message': f'Widget {widget_type} has been disabled',
    })


@widgets_bp.route('/<widget_type>/reset', methods=['POST'])
@require_shopify_auth
def reset_widget(widget_type):
    """
    POST /api/widgets/{type}/reset - Reset widget to default config

    Args:
        widget_type: The widget type to reset
    """
    tenant_id = g.tenant.id

    # Validate widget type
    valid_types = [wt.value for wt in WidgetType]
    if widget_type not in valid_types:
        return jsonify({
            'error': f'Invalid widget type. Must be one of: {", ".join(valid_types)}'
        }), 400

    # Get or create widget
    widget = Widget.get_or_create(tenant_id, widget_type)

    # Reset to default config
    try:
        wt = WidgetType(widget_type)
        default_config = DEFAULT_WIDGET_CONFIGS.get(wt, {})
    except ValueError:
        default_config = {}

    widget.config = default_config
    db.session.commit()

    return jsonify({
        'success': True,
        'widget': widget.to_dict(),
        'message': f'Widget {widget_type} has been reset to defaults',
    })


@widgets_bp.route('/enabled', methods=['GET'])
@require_shopify_auth
def list_enabled_widgets():
    """
    GET /api/widgets/enabled - List only enabled widgets

    Returns only widgets that are currently enabled for display.
    """
    tenant_id = g.tenant.id
    widgets = Widget.get_enabled_for_tenant(tenant_id)

    return jsonify({
        'success': True,
        'widgets': [w.to_dict() for w in widgets],
        'count': len(widgets),
    })


@widgets_bp.route('/bulk', methods=['PUT'])
@require_shopify_auth
def bulk_update_widgets():
    """
    PUT /api/widgets/bulk - Bulk update multiple widgets

    Request Body:
        {
            "widgets": [
                {
                    "widget_type": "points_balance",
                    "is_enabled": true,
                    "config": {...}
                },
                ...
            ]
        }
    """
    tenant_id = g.tenant.id
    data = request.get_json()

    if not data or 'widgets' not in data:
        return jsonify({'error': 'No widgets data provided'}), 400

    widgets_data = data['widgets']
    if not isinstance(widgets_data, list):
        return jsonify({'error': 'Widgets must be a list'}), 400

    valid_types = [wt.value for wt in WidgetType]
    updated_widgets = []
    errors = []

    for widget_data in widgets_data:
        widget_type = widget_data.get('widget_type')

        if not widget_type:
            errors.append({'error': 'Missing widget_type', 'data': widget_data})
            continue

        if widget_type not in valid_types:
            errors.append({'error': f'Invalid widget_type: {widget_type}', 'data': widget_data})
            continue

        widget = Widget.get_or_create(tenant_id, widget_type)

        if 'config' in widget_data:
            config = widget_data['config']
            if isinstance(config, dict):
                widget.update_config(config)

        if 'is_enabled' in widget_data:
            widget.is_enabled = bool(widget_data['is_enabled'])

        updated_widgets.append(widget)

    db.session.commit()

    response = {
        'success': True,
        'widgets': [w.to_dict() for w in updated_widgets],
        'updated_count': len(updated_widgets),
    }

    if errors:
        response['errors'] = errors

    return jsonify(response)
