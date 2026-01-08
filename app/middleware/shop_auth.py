"""
Shop Authentication Middleware.

Simplified auth decorator for embedded Shopify app requests.
Extracts shop domain from query params, headers, or session token.
"""
import os
from functools import wraps
from flask import request, jsonify, g
from ..models import Tenant
from ..extensions import db

# Development mode - skip strict verification
DEV_MODE = os.getenv('FLASK_ENV') == 'development' or os.getenv('SHOPIFY_AUTH_DEV_MODE') == 'true'


def get_shop_from_request() -> str | None:
    """
    Get shop domain from request using multiple methods.

    Priority:
    1. shop query parameter
    2. X-Shop-Domain header
    3. Referer header (extract shop from embedded app URL)

    Returns:
        Shop domain or None
    """
    # Method 1: Query parameter (most common for embedded apps)
    shop = request.args.get('shop')
    if shop:
        return shop

    # Method 2: Custom header
    shop = request.headers.get('X-Shop-Domain')
    if shop:
        return shop

    # Method 3: Try to extract from referer
    referer = request.headers.get('Referer', '')
    if 'myshopify.com' in referer:
        # Extract shop from URL like https://shop.myshopify.com/admin/apps/...
        try:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            if parsed.netloc.endswith('myshopify.com'):
                return parsed.netloc
        except Exception:
            pass

    return None


def get_or_create_tenant(shop: str) -> Tenant | None:
    """
    Get existing tenant or create a new one in dev mode.

    Args:
        shop: Shop domain (e.g., 'mystore.myshopify.com')

    Returns:
        Tenant object or None
    """
    tenant = Tenant.query.filter_by(shopify_domain=shop).first()

    if not tenant and DEV_MODE:
        # Auto-create tenant in dev mode
        shop_slug = shop.replace('.myshopify.com', '').lower()
        tenant = Tenant(
            shop_name=shop_slug.replace('-', ' ').title(),
            shop_slug=shop_slug,
            shopify_domain=shop,
            is_active=True,
            subscription_plan='growth',  # Dev gets full features
            subscription_active=True,
        )
        db.session.add(tenant)
        db.session.commit()
        print(f'[Auth] Auto-created dev tenant for {shop}')

    return tenant


def require_shop_auth(f):
    """
    Decorator to require shop authentication for admin API endpoints.

    Sets g.shop and g.tenant_id if authenticated.

    In production: Requires shop domain and valid tenant
    In development: Auto-creates tenant if needed

    Usage:
        @require_shop_auth
        def my_endpoint():
            shop = g.shop
            tenant_id = g.tenant_id
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get shop from request
        shop = get_shop_from_request()

        # Check for dev mode with tenant ID header
        if not shop and DEV_MODE:
            tenant_id = request.headers.get('X-Tenant-ID')
            if tenant_id:
                try:
                    tenant = Tenant.query.get(int(tenant_id))
                    if tenant:
                        g.shop = tenant.shopify_domain
                        g.tenant_id = tenant.id
                        g.tenant = tenant
                        return f(*args, **kwargs)
                except (ValueError, TypeError):
                    pass

        if not shop:
            return jsonify({
                'error': 'Authentication required',
                'message': 'Missing shop domain',
                'code': 'AUTH_REQUIRED'
            }), 401

        # Get or create tenant
        tenant = get_or_create_tenant(shop)

        if not tenant:
            return jsonify({
                'error': 'Shop not found',
                'message': 'This shop has not installed the app',
                'code': 'SHOP_NOT_FOUND'
            }), 404

        # Check if tenant is active
        if not tenant.is_active:
            return jsonify({
                'error': 'Shop inactive',
                'message': 'This shop\'s access has been disabled',
                'code': 'SHOP_INACTIVE'
            }), 403

        # Set context
        g.shop = shop
        g.tenant_id = tenant.id
        g.tenant = tenant

        return f(*args, **kwargs)

    return decorated_function


def require_subscription(plan_levels: list[str] = None):
    """
    Decorator to require a specific subscription level.

    Must be used after @require_shop_auth.

    Args:
        plan_levels: List of required plan levels (e.g., ['growth', 'enterprise'])
                    If None, any active subscription is accepted

    Usage:
        @require_shop_auth
        @require_subscription(['growth', 'enterprise'])
        def my_premium_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            tenant = getattr(g, 'tenant', None)

            if not tenant:
                return jsonify({
                    'error': 'Not authenticated',
                    'code': 'AUTH_REQUIRED'
                }), 401

            # Skip subscription check in dev mode
            if DEV_MODE:
                return f(*args, **kwargs)

            # Free tier check
            if tenant.subscription_plan == 'free':
                if plan_levels and 'free' not in plan_levels:
                    return jsonify({
                        'error': 'Upgrade required',
                        'message': 'Please upgrade your plan to access this feature',
                        'code': 'UPGRADE_REQUIRED',
                        'required_plans': plan_levels
                    }), 402

            # Check if subscription is active
            if plan_levels and not tenant.subscription_active:
                return jsonify({
                    'error': 'Subscription required',
                    'message': 'Please activate your subscription to access this feature',
                    'code': 'SUBSCRIPTION_REQUIRED'
                }), 402

            # Check plan level
            if plan_levels and tenant.subscription_plan not in plan_levels:
                return jsonify({
                    'error': 'Plan upgrade required',
                    'message': f'This feature requires one of: {", ".join(plan_levels)}',
                    'code': 'PLAN_UPGRADE_REQUIRED',
                    'current_plan': tenant.subscription_plan,
                    'required_plans': plan_levels
                }), 402

            return f(*args, **kwargs)

        return decorated_function
    return decorator
