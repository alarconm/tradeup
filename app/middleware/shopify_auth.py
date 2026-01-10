"""
Shopify Session Token Authentication Middleware.

Verifies Shopify session tokens (JWT) from embedded apps to authenticate
requests. Falls back to shop query param for development and backwards
compatibility.

Session tokens are issued by Shopify App Bridge and contain:
- iss: Shop domain (https://shop.myshopify.com/admin)
- dest: Shop domain
- aud: API key
- sub: Staff member GID
- exp: Expiration time
"""
import os
import jwt
from functools import wraps
from flask import request, jsonify, g
from ..models import Tenant


# Shopify App credentials
SHOPIFY_API_KEY = os.getenv('SHOPIFY_CLIENT_ID', os.getenv('SHOPIFY_API_KEY', ''))
SHOPIFY_API_SECRET = os.getenv('SHOPIFY_CLIENT_SECRET', os.getenv('SHOPIFY_API_SECRET', ''))

# Development mode - skip strict verification
DEV_MODE = os.getenv('FLASK_ENV') == 'development' or os.getenv('SHOPIFY_AUTH_DEV_MODE') == 'true'


def decode_session_token(token: str) -> dict | None:
    """
    Decode and verify a Shopify session token.

    Args:
        token: JWT session token from App Bridge

    Returns:
        Decoded token payload or None if invalid
    """
    if not token:
        return None

    try:
        # Shopify session tokens are signed with the app's API secret
        payload = jwt.decode(
            token,
            SHOPIFY_API_SECRET,
            algorithms=['HS256'],
            audience=SHOPIFY_API_KEY,
            options={
                'verify_aud': bool(SHOPIFY_API_KEY),
                'verify_exp': True,
            }
        )
        return payload
    except jwt.ExpiredSignatureError:
        print('[Auth] Session token expired')
        return None
    except jwt.InvalidAudienceError:
        print('[Auth] Invalid token audience')
        return None
    except jwt.InvalidTokenError as e:
        print(f'[Auth] Invalid token: {e}')
        return None


def get_shop_from_token(payload: dict) -> str | None:
    """
    Extract shop domain from session token payload.

    Args:
        payload: Decoded JWT payload

    Returns:
        Shop domain (e.g., 'shop.myshopify.com')
    """
    # dest contains the shop URL: https://shop.myshopify.com/admin
    dest = payload.get('dest', '')
    if dest:
        # Extract domain from URL
        dest = dest.replace('https://', '').replace('http://', '')
        dest = dest.split('/')[0]  # Remove /admin path
        return dest

    # Fallback to iss (issuer)
    iss = payload.get('iss', '')
    if iss:
        iss = iss.replace('https://', '').replace('http://', '')
        iss = iss.split('/')[0]
        return iss

    return None


def get_staff_id_from_token(payload: dict) -> str | None:
    """
    Extract staff member ID from session token.

    Args:
        payload: Decoded JWT payload

    Returns:
        Staff member GID (e.g., 'gid://shopify/StaffMember/123')
    """
    return payload.get('sub')


def get_shop_from_request() -> str | None:
    """
    Get shop domain from request using multiple methods.
    Priority:
    1. Session token in Authorization header
    2. shop query parameter
    3. X-Shop-Domain header (for backwards compatibility)

    Returns:
        Shop domain or None
    """
    # Method 1: Session token from Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1]
        payload = decode_session_token(token)
        if payload:
            shop = get_shop_from_token(payload)
            if shop:
                return shop

    # Method 2: Query parameter
    shop = request.args.get('shop')
    if shop:
        return shop

    # Method 3: Header (backwards compatibility)
    shop = request.headers.get('X-Shop-Domain')
    if shop:
        return shop

    return None


def require_shopify_auth(f):
    """
    Decorator to require Shopify authentication.

    Sets g.tenant, g.tenant_id, g.shop, and g.staff_id if authenticated.

    In production: Requires valid session token
    In development: Falls back to shop query param

    Usage:
        @require_shopify_auth
        def my_endpoint():
            tenant = g.tenant
            shop = g.shop
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        shop = None
        staff_id = None
        authenticated_via = None

        # Try session token first
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
            payload = decode_session_token(token)
            if payload:
                shop = get_shop_from_token(payload)
                staff_id = get_staff_id_from_token(payload)
                authenticated_via = 'session_token'

        # Fallback: shop query param (for dev/backwards compat)
        if not shop:
            shop = request.args.get('shop')
            if shop:
                authenticated_via = 'query_param'

        # Fallback: X-Shop-Domain header
        if not shop:
            shop = request.headers.get('X-Shop-Domain')
            if shop:
                authenticated_via = 'header'

        # Still no shop? Check if we should allow in dev mode
        if not shop:
            if DEV_MODE:
                # In dev mode, allow requests with X-Tenant-ID header
                tenant_id = request.headers.get('X-Tenant-ID')
                if tenant_id:
                    try:
                        tenant = Tenant.query.get(int(tenant_id))
                        if tenant:
                            g.tenant = tenant
                            g.tenant_id = tenant.id
                            g.shop = tenant.shopify_domain
                            g.staff_id = None
                            g.auth_method = 'dev_tenant_id'
                            return f(*args, **kwargs)
                    except (ValueError, TypeError):
                        pass

            return jsonify({
                'error': 'Authentication required',
                'message': 'Missing shop domain or session token',
                'code': 'AUTH_REQUIRED'
            }), 401

        # Look up tenant by shop domain
        tenant = Tenant.query.filter_by(shopify_domain=shop).first()

        if not tenant:
            # In dev mode, auto-create tenant
            if DEV_MODE:
                from ..extensions import db
                shop_slug = shop.replace('.myshopify.com', '').lower()
                tenant = Tenant(
                    shop_name=shop_slug.title(),
                    shop_slug=shop_slug,
                    shopify_domain=shop,
                    is_active=True,
                )
                db.session.add(tenant)
                db.session.commit()
                print(f'[Auth] Auto-created dev tenant for {shop}')
            else:
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

        # Check if access token exists (app is properly installed)
        if not DEV_MODE and not tenant.shopify_access_token:
            return jsonify({
                'error': 'App not installed',
                'message': 'Please reinstall the app from the Shopify App Store',
                'code': 'APP_NOT_INSTALLED'
            }), 403

        # Set context
        g.tenant = tenant
        g.tenant_id = tenant.id
        g.shop = shop
        g.staff_id = staff_id
        g.auth_method = authenticated_via

        return f(*args, **kwargs)

    return decorated_function


def require_shopify_auth_debug(f):
    """
    Debug version of require_shopify_auth that catches and reports errors.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Same logic as require_shopify_auth
            shop = None
            staff_id = None
            authenticated_via = None

            # Try session token first
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1]
                payload = decode_session_token(token)
                if payload:
                    shop = get_shop_from_token(payload)
                    staff_id = get_staff_id_from_token(payload)
                    authenticated_via = 'session_token'

            # Fallback: shop query param
            if not shop:
                shop = request.args.get('shop')
                if shop:
                    authenticated_via = 'query_param'

            # Fallback: X-Shop-Domain header
            if not shop:
                shop = request.headers.get('X-Shop-Domain')
                if shop:
                    authenticated_via = 'header'

            if not shop:
                return jsonify({
                    'error': 'Authentication required',
                    'message': 'Missing shop domain or session token',
                    'code': 'AUTH_REQUIRED'
                }), 401

            # Look up tenant
            tenant = Tenant.query.filter_by(shopify_domain=shop).first()

            if not tenant:
                return jsonify({
                    'error': 'Shop not found',
                    'message': f'Shop {shop} not found in database',
                    'code': 'SHOP_NOT_FOUND'
                }), 404

            if not tenant.is_active:
                return jsonify({
                    'error': 'Shop inactive',
                    'code': 'SHOP_INACTIVE'
                }), 403

            # Set context
            g.tenant = tenant
            g.tenant_id = tenant.id
            g.shop = shop
            g.staff_id = staff_id
            g.auth_method = authenticated_via

            return f(*args, **kwargs)

        except Exception as e:
            import traceback
            print(f"[Auth Debug] Error in decorator: {e}")
            traceback.print_exc()
            return jsonify({
                'error': 'Auth error',
                'message': str(e),
                'type': type(e).__name__
            }), 500

    return decorated_function


def require_active_subscription(f):
    """
    Decorator to require an active Shopify billing subscription.

    Must be used after @require_shopify_auth.

    Usage:
        @require_shopify_auth
        @require_active_subscription
        def my_premium_endpoint():
            ...
    """
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

        # Free tier is always allowed
        if tenant.subscription_plan == 'free':
            return f(*args, **kwargs)

        # Check if subscription is active
        if not tenant.subscription_active:
            return jsonify({
                'error': 'Subscription required',
                'message': 'Please activate your subscription to access this feature',
                'code': 'SUBSCRIPTION_REQUIRED',
                'redirect': '/app/billing'
            }), 402

        return f(*args, **kwargs)

    return decorated_function
