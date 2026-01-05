"""
Tenant Settings API endpoints.

Manages branding, features, and configuration for tenants.
"""
from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import Tenant

settings_bp = Blueprint('settings', __name__)


# Default settings structure
DEFAULT_SETTINGS = {
    'branding': {
        'app_name': 'Quick Flip',
        'tagline': 'Trade-in Loyalty Program',
        'logo_url': None,
        'logo_dark_url': None,
        'colors': {
            'primary': '#e85d27',
            'primary_hover': '#d14d1a',
            'secondary': '#1e293b',
            'accent': '#3b82f6'
        },
        'style': 'glass'  # glass, solid, minimal
    },
    'features': {
        'points_enabled': False,
        'referrals_enabled': False,
        'self_signup_enabled': True
    },
    'quick_flip': {
        'default_window_days': 7,
        'allow_tier_override': True
    },
    'contact': {
        'support_email': None,
        'support_phone': None
    }
}


def get_settings_with_defaults(settings: dict) -> dict:
    """Merge tenant settings with defaults."""
    result = {}
    for key, default_value in DEFAULT_SETTINGS.items():
        if isinstance(default_value, dict):
            result[key] = {**default_value, **(settings.get(key) or {})}
        else:
            result[key] = settings.get(key, default_value)
    return result


@settings_bp.route('', methods=['GET'])
def get_settings():
    """Get all tenant settings with defaults."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    tenant = Tenant.query.get_or_404(tenant_id)
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'settings': settings,
        'tenant': {
            'id': tenant.id,
            'shop_name': tenant.shop_name,
            'shop_slug': tenant.shop_slug
        }
    })


@settings_bp.route('', methods=['PATCH'])
def update_settings():
    """Update tenant settings (partial update)."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
    data = request.json

    tenant = Tenant.query.get_or_404(tenant_id)

    # Deep merge settings
    current_settings = tenant.settings or {}
    for key, value in data.items():
        if key in DEFAULT_SETTINGS:
            if isinstance(value, dict) and isinstance(current_settings.get(key), dict):
                current_settings[key] = {**current_settings.get(key, {}), **value}
            else:
                current_settings[key] = value

    tenant.settings = current_settings
    db.session.commit()

    return jsonify({
        'success': True,
        'settings': get_settings_with_defaults(tenant.settings)
    })


@settings_bp.route('/branding', methods=['GET'])
def get_branding():
    """Get branding settings only."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    tenant = Tenant.query.get_or_404(tenant_id)
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'branding': settings['branding'],
        'shop_name': tenant.shop_name
    })


@settings_bp.route('/branding', methods=['PATCH'])
def update_branding():
    """Update branding settings."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
    data = request.json

    tenant = Tenant.query.get_or_404(tenant_id)

    current_settings = tenant.settings or {}
    current_branding = current_settings.get('branding', {})

    # Update branding with new values
    for key, value in data.items():
        if key == 'colors' and isinstance(value, dict):
            current_branding['colors'] = {
                **current_branding.get('colors', {}),
                **value
            }
        else:
            current_branding[key] = value

    current_settings['branding'] = current_branding
    tenant.settings = current_settings
    db.session.commit()

    return jsonify({
        'success': True,
        'branding': get_settings_with_defaults(tenant.settings)['branding']
    })


@settings_bp.route('/features', methods=['GET'])
def get_features():
    """Get feature flags."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    tenant = Tenant.query.get_or_404(tenant_id)
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'features': settings['features']
    })


@settings_bp.route('/features', methods=['PATCH'])
def update_features():
    """Update feature flags."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
    data = request.json

    tenant = Tenant.query.get_or_404(tenant_id)

    current_settings = tenant.settings or {}
    current_features = current_settings.get('features', {})

    for key, value in data.items():
        current_features[key] = value

    current_settings['features'] = current_features
    tenant.settings = current_settings
    db.session.commit()

    return jsonify({
        'success': True,
        'features': get_settings_with_defaults(tenant.settings)['features']
    })
