"""
Webhook handlers for TradeUp platform.
Processes Shopify webhooks for rewards, orders, customers, and app lifecycle.
"""
import hmac
import hashlib
import base64
from functools import wraps
from flask import request, jsonify, current_app
from ..models import Tenant


def verify_shopify_webhook_signature(data: bytes, hmac_header: str, secret: str) -> bool:
    """
    Verify Shopify webhook HMAC-SHA256 signature.

    Shopify signs webhooks using HMAC-SHA256 with the webhook secret.
    This function computes the expected signature and compares it using
    a timing-safe comparison to prevent timing attacks.

    Args:
        data: Raw request body bytes
        hmac_header: The X-Shopify-Hmac-SHA256 header value
        secret: The webhook secret (stored per tenant)

    Returns:
        True if signature is valid, False otherwise
    """
    if not secret:
        current_app.logger.warning('No webhook secret configured for verification')
        return False

    if not hmac_header:
        current_app.logger.warning('No HMAC header in webhook request')
        return False

    try:
        computed_hmac = base64.b64encode(
            hmac.new(secret.encode('utf-8'), data, hashlib.sha256).digest()
        ).decode('utf-8')

        # Use timing-safe comparison to prevent timing attacks
        return hmac.compare_digest(computed_hmac, hmac_header)
    except Exception as e:
        current_app.logger.error(f'Webhook signature verification error: {e}')
        return False


def get_tenant_from_webhook_headers() -> Tenant:
    """
    Get tenant from Shopify webhook headers.

    Returns:
        Tenant object or None if not found
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    if not shop_domain:
        return None
    return Tenant.query.filter_by(shopify_domain=shop_domain).first()


def require_webhook_verification(skip_in_dev: bool = False):
    """
    Decorator to require Shopify webhook signature verification.

    This decorator:
    1. Extracts the shop domain from headers
    2. Looks up the tenant and their webhook secret
    3. Verifies the HMAC signature
    4. Returns 401 if verification fails

    Args:
        skip_in_dev: If True, skip verification in development mode (not recommended)

    Usage:
        @app.route('/webhook/orders/create', methods=['POST'])
        @require_webhook_verification()
        def handle_order_created():
            tenant = g.webhook_tenant
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import g

            # Get shop domain from headers
            shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
            if not shop_domain:
                current_app.logger.warning('Webhook missing X-Shopify-Shop-Domain header')
                return jsonify({'error': 'Missing shop domain header'}), 400

            # Look up tenant
            tenant = Tenant.query.filter_by(shopify_domain=shop_domain).first()
            if not tenant:
                current_app.logger.warning(f'Webhook from unknown shop: {shop_domain}')
                return jsonify({'error': 'Unknown shop'}), 404

            # Store tenant in g for handler use
            g.webhook_tenant = tenant
            g.tenant_id = tenant.id

            # Skip verification in development if flag set (NOT recommended for production)
            is_dev = current_app.config.get('ENV') == 'development'
            if skip_in_dev and is_dev:
                current_app.logger.debug('Skipping webhook verification in development')
                return f(*args, **kwargs)

            # Verify signature
            hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
            webhook_secret = tenant.webhook_secret or current_app.config.get('SHOPIFY_API_SECRET')

            if not verify_shopify_webhook_signature(request.data, hmac_header, webhook_secret):
                current_app.logger.warning(
                    f'Invalid webhook signature from {shop_domain}'
                )
                return jsonify({'error': 'Invalid signature'}), 401

            return f(*args, **kwargs)

        return decorated_function
    return decorator


from .shopify import webhooks_bp
from .shopify_billing import shopify_billing_webhook_bp
from .customer_lifecycle import customer_lifecycle_bp
from .order_lifecycle import order_lifecycle_bp
from .app_lifecycle import app_lifecycle_bp

__all__ = [
    'webhooks_bp',
    'shopify_billing_webhook_bp',
    'customer_lifecycle_bp',
    'order_lifecycle_bp',
    'app_lifecycle_bp',
    'verify_shopify_webhook_signature',
    'require_webhook_verification',
    'get_tenant_from_webhook_headers',
]
