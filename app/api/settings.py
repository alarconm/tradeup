"""
Tenant Settings API endpoints.

Manages branding, features, and configuration for tenants.
"""
from flask import Blueprint, request, jsonify, g
from ..extensions import db
from ..models import Tenant
from ..middleware.shopify_auth import require_shopify_auth

settings_bp = Blueprint('settings', __name__)


# Cashback method options
CASHBACK_METHODS = {
    'native_store_credit': 'Shopify Native Store Credit (recommended)',
    'discount_code': 'Unique Discount Codes',
    'gift_card': 'Shopify Gift Cards',
    'manual': 'Manual Fulfillment (track only)',
}


# Default settings structure
DEFAULT_SETTINGS = {
    'branding': {
        'app_name': 'TradeUp',
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
        'self_signup_enabled': True,
        'advanced_features_enabled': False  # Show simplified nav by default
    },
    'auto_enrollment': {
        'enabled': True,  # Auto-enroll customers on first purchase
        'default_tier_id': None,  # Tier to assign (None = lowest tier)
        'min_order_value': 0,  # Minimum order value to trigger enrollment
        'excluded_tags': [],  # Customer tags to exclude (e.g., ['wholesale', 'staff'])
    },
    'cashback': {
        'method': 'native_store_credit',  # How rewards are delivered
        # Options: native_store_credit, discount_code, gift_card, manual
        'purchase_cashback_enabled': True,  # Award cashback on purchases
        'trade_in_credit_enabled': True,   # Award credit on trade-ins
        'same_transaction_bonus': True,    # Apply tier benefits to same order as membership purchase
        'rounding_mode': 'down',           # down, up, nearest - for cashback cents
        'min_cashback_amount': 0.01,       # Minimum amount to issue (avoid tiny credits)
    },
    'subscriptions': {
        'monthly_enabled': True,  # Offer monthly subscriptions
        'yearly_enabled': True,   # Offer yearly subscriptions (uses yearly_price from tier)
        'trial_days': 0,          # Free trial days (0 = no trial)
        'grace_period_days': 3,   # Days to retry failed payment before downgrade
    },
    'notifications': {
        'enabled': True,
        'welcome_email': True,  # Send welcome email on enrollment
        'trade_in_updates': True,  # Trade-in status change emails
        'tier_change': True,  # Tier upgrade/downgrade emails
        'credit_issued': True,  # Store credit issued emails
        'from_name': None,  # Defaults to shop name
        'from_email': None,  # SendGrid verified sender
    },
    'contact': {
        'support_email': None,
        'support_phone': None
    },
    'trade_ins': {
        'enabled': True,
        'auto_approve_under': 50.00,  # Auto-approve trade-ins under this value
        'require_review_over': 500.00,  # Require manual review over this value
        'allow_guest_trade_ins': True,  # Allow non-member trade-ins
        'default_category': 'other',
        'require_photos': False,
    },
    'general': {
        'currency': 'USD',
        'timezone': 'America/Los_Angeles',
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
@require_shopify_auth
def get_settings():
    """Get all tenant settings with defaults."""
    tenant = g.tenant
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
@require_shopify_auth
def update_settings():
    """Update tenant settings (partial update)."""
    data = request.json
    tenant = g.tenant

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
@require_shopify_auth
def get_branding():
    """Get branding settings only."""
    tenant = g.tenant
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'branding': settings['branding'],
        'shop_name': tenant.shop_name
    })


@settings_bp.route('/branding', methods=['PATCH'])
@require_shopify_auth
def update_branding():
    """Update branding settings."""
    tenant = g.tenant  # Use tenant from auth decorator
    data = request.json

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
@require_shopify_auth
def get_features():
    """Get feature flags."""
    tenant = g.tenant
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'features': settings['features']
    })


@settings_bp.route('/features', methods=['PATCH'])
@require_shopify_auth
def update_features():
    """Update feature flags."""
    tenant = g.tenant  # Use tenant from auth decorator
    data = request.json

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


@settings_bp.route('/cashback', methods=['GET'])
@require_shopify_auth
def get_cashback_settings():
    """Get cashback/rewards settings."""
    tenant = g.tenant
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'cashback': settings['cashback'],
        'available_methods': CASHBACK_METHODS
    })


@settings_bp.route('/cashback', methods=['PATCH'])
@require_shopify_auth
def update_cashback_settings():
    """
    Update cashback/rewards settings.

    Request body:
        method: native_store_credit | discount_code | gift_card | manual
        purchase_cashback_enabled: bool
        trade_in_credit_enabled: bool
        same_transaction_bonus: bool
        rounding_mode: down | up | nearest
        min_cashback_amount: float
    """
    tenant = g.tenant  # Use tenant from auth decorator
    data = request.json

    # Validate method if provided
    if 'method' in data and data['method'] not in CASHBACK_METHODS:
        return jsonify({
            'error': f"Invalid method. Choose from: {list(CASHBACK_METHODS.keys())}"
        }), 400

    current_settings = tenant.settings or {}
    current_cashback = current_settings.get('cashback', {})

    for key, value in data.items():
        current_cashback[key] = value

    current_settings['cashback'] = current_cashback
    tenant.settings = current_settings
    db.session.commit()

    return jsonify({
        'success': True,
        'cashback': get_settings_with_defaults(tenant.settings)['cashback']
    })


@settings_bp.route('/subscriptions', methods=['GET'])
@require_shopify_auth
def get_subscription_settings():
    """Get subscription/membership settings."""
    tenant = g.tenant
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'subscriptions': settings['subscriptions']
    })


@settings_bp.route('/subscriptions', methods=['PATCH'])
@require_shopify_auth
def update_subscription_settings():
    """
    Update subscription/membership settings.

    Request body:
        monthly_enabled: bool
        yearly_enabled: bool
        trial_days: int
        grace_period_days: int
    """
    tenant = g.tenant  # Use tenant from auth decorator
    data = request.json

    current_settings = tenant.settings or {}
    current_subs = current_settings.get('subscriptions', {})

    for key, value in data.items():
        current_subs[key] = value

    current_settings['subscriptions'] = current_subs
    tenant.settings = current_settings
    db.session.commit()

    return jsonify({
        'success': True,
        'subscriptions': get_settings_with_defaults(tenant.settings)['subscriptions']
    })


@settings_bp.route('/auto-enrollment', methods=['GET'])
@require_shopify_auth
def get_auto_enrollment_settings():
    """Get auto-enrollment settings."""
    tenant = g.tenant
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'auto_enrollment': settings['auto_enrollment']
    })


@settings_bp.route('/auto-enrollment', methods=['PATCH'])
@require_shopify_auth
def update_auto_enrollment_settings():
    """
    Update auto-enrollment settings.

    Request body:
        enabled: bool - Auto-enroll on first purchase
        default_tier_id: int - Tier to assign
        min_order_value: float - Minimum order to trigger
        excluded_tags: list - Customer tags to exclude
    """
    tenant = g.tenant  # Use tenant from auth decorator
    data = request.json

    current_settings = tenant.settings or {}
    current_enrollment = current_settings.get('auto_enrollment', {})

    for key, value in data.items():
        current_enrollment[key] = value

    current_settings['auto_enrollment'] = current_enrollment
    tenant.settings = current_settings
    db.session.commit()

    return jsonify({
        'success': True,
        'auto_enrollment': get_settings_with_defaults(tenant.settings)['auto_enrollment']
    })


@settings_bp.route('/notifications', methods=['GET'])
@require_shopify_auth
def get_notification_settings():
    """Get notification settings."""
    tenant = g.tenant
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'notifications': settings['notifications']
    })


@settings_bp.route('/notifications', methods=['PATCH'])
@require_shopify_auth
def update_notification_settings():
    """
    Update notification settings.

    Request body:
        enabled: bool - Master toggle
        welcome_email: bool - Send on enrollment
        trade_in_updates: bool - Trade-in status emails
        tier_change: bool - Tier upgrade/downgrade emails
        credit_issued: bool - Store credit issued emails
        from_name: str - Sender name
        from_email: str - Sender email (must be verified)
    """
    tenant = g.tenant  # Use tenant from auth decorator
    data = request.json

    current_settings = tenant.settings or {}
    current_notifications = current_settings.get('notifications', {})

    for key, value in data.items():
        current_notifications[key] = value

    current_settings['notifications'] = current_notifications
    tenant.settings = current_settings
    db.session.commit()

    return jsonify({
        'success': True,
        'notifications': get_settings_with_defaults(tenant.settings)['notifications']
    })


@settings_bp.route('/trade-ins', methods=['GET'])
@require_shopify_auth
def get_trade_in_settings():
    """Get trade-in settings."""
    tenant = g.tenant
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'trade_ins': settings['trade_ins']
    })


@settings_bp.route('/trade-ins', methods=['PATCH'])
@require_shopify_auth
def update_trade_in_settings():
    """
    Update trade-in settings.

    Request body:
        enabled: bool - Enable trade-in feature
        auto_approve_under: float - Auto-approve threshold
        require_review_over: float - Manual review threshold
        allow_guest_trade_ins: bool - Allow non-member trade-ins
        default_category: str - Default category
        require_photos: bool - Require photo uploads
    """
    tenant = g.tenant  # Use tenant from auth decorator
    data = request.json

    current_settings = tenant.settings or {}
    current_trade_ins = current_settings.get('trade_ins', {})

    for key, value in data.items():
        current_trade_ins[key] = value

    current_settings['trade_ins'] = current_trade_ins
    tenant.settings = current_settings
    db.session.commit()

    return jsonify({
        'success': True,
        'trade_ins': get_settings_with_defaults(tenant.settings)['trade_ins']
    })


@settings_bp.route('/general', methods=['GET'])
@require_shopify_auth
def get_general_settings():
    """Get general settings."""
    tenant = g.tenant
    settings = get_settings_with_defaults(tenant.settings or {})

    return jsonify({
        'general': settings['general'],
        'branding': settings['branding']
    })


@settings_bp.route('/general', methods=['PATCH'])
@require_shopify_auth
def update_general_settings():
    """
    Update general settings.

    Request body:
        currency: str - Currency code (USD, CAD, EUR, etc.)
        timezone: str - Timezone identifier
    """
    tenant = g.tenant  # Use tenant from auth decorator
    data = request.json

    current_settings = tenant.settings or {}
    current_general = current_settings.get('general', {})

    for key, value in data.items():
        current_general[key] = value

    current_settings['general'] = current_general
    tenant.settings = current_settings
    db.session.commit()

    return jsonify({
        'success': True,
        'general': get_settings_with_defaults(tenant.settings)['general']
    })


# ==============================================
# Shopify Customer Segments
# ==============================================

@settings_bp.route('/segments', methods=['GET'])
@require_shopify_auth
def get_shopify_segments():
    """
    Get all customer segments from Shopify, highlighting TradeUp ones.

    Returns:
        segments: List of all segments
        tradeup_segments: List of TradeUp-specific segments
    """
    tenant_id = g.tenant_id

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(tenant_id)
        segments = client.get_segments()

        # Separate TradeUp segments
        tradeup_segments = [s for s in segments if s.get('name', '').startswith('TradeUp')]
        other_segments = [s for s in segments if not s.get('name', '').startswith('TradeUp')]

        return jsonify({
            'success': True,
            'tradeup_segments': tradeup_segments,
            'other_segments': other_segments,
            'total_count': len(segments)
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/segments/sync', methods=['POST'])
@require_shopify_auth
def sync_tradeup_segments():
    """
    Create/update Shopify customer segments for all TradeUp tiers.

    Creates:
    1. "TradeUp Members" - All members with any tier tag
    2. One segment per tier (e.g., "TradeUp Gold Members")

    These segments can then be used with Shopify Email or other
    marketing tools that support customer segments.

    Returns:
        segments: List of created/updated segments
        errors: Any errors that occurred
    """
    tenant_id = g.tenant_id

    try:
        # Get all tiers for this tenant
        from ..models.member import MembershipTier
        tiers = MembershipTier.query.filter_by(tenant_id=tenant_id, is_active=True).all()

        if not tiers:
            return jsonify({
                'success': False,
                'error': 'No active tiers found. Create tiers first.'
            }), 400

        # Build tier data for segment creation
        # slug is generated from name (lowercase, hyphenated)
        tier_data = [{
            'name': t.name,
            'slug': t.name.lower().replace(' ', '-')
        } for t in tiers]

        # Create segments in Shopify
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(tenant_id)
        result = client.create_tradeup_segments(tier_data)

        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/segments/<segment_id>', methods=['DELETE'])
@require_shopify_auth
def delete_shopify_segment(segment_id: str):
    """
    Delete a customer segment from Shopify.

    Args:
        segment_id: Shopify segment GID

    Returns:
        success: bool
    """
    tenant_id = g.tenant_id

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(tenant_id)
        result = client.delete_segment(segment_id)

        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==============================================
# Shopify Membership Products
# ==============================================

@settings_bp.route('/products', methods=['GET'])
@require_shopify_auth
def get_membership_products():
    """
    Get all TradeUp membership products from Shopify.

    Returns:
        products: List of membership products with their variants
    """
    tenant_id = g.tenant_id

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(tenant_id)
        products = client.get_products_by_tag('tradeup-membership')

        return jsonify({
            'success': True,
            'products': products,
            'count': len(products)
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/products/sync', methods=['POST'])
@require_shopify_auth
def sync_membership_products():
    """
    Create/update Shopify products for all TradeUp tiers.

    Creates purchasable membership products that customers can buy
    to join a tier. Products have monthly/yearly variants with
    appropriate pricing from the tier configuration.

    Returns:
        products: List of created/updated products
        errors: Any errors that occurred
    """
    tenant = g.tenant
    tenant_id = g.tenant_id

    try:
        # Get all tiers for this tenant
        from ..models.member import MembershipTier
        tiers = MembershipTier.query.filter_by(tenant_id=tenant_id, is_active=True).all()

        if not tiers:
            return jsonify({
                'success': False,
                'error': 'No active tiers found. Create tiers first.'
            }), 400

        # Build tier data for product creation
        # Map MembershipTier attributes to what ShopifyClient expects
        tier_data = [{
            'name': t.name,
            'slug': t.name.lower().replace(' ', '-'),
            'price': float(t.monthly_price) if t.monthly_price else 0,
            'yearly_price': float(t.yearly_price) if t.yearly_price else None,
            'description': f'{t.name} Membership',
            'trade_in_bonus_percent': float(t.bonus_rate * 100) if t.bonus_rate else 0,
            'cashback_percent': float(t.purchase_cashback_pct) if t.purchase_cashback_pct else 0
        } for t in tiers]

        # Create products in Shopify
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(tenant_id)
        result = client.create_tradeup_membership_products(
            tier_data,
            shop_name=tenant.shop_name or 'TradeUp'
        )

        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
