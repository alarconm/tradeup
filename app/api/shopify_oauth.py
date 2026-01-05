"""
Shopify OAuth flow for app installation.
Handles the OAuth dance for installing the TradeUp app on Shopify stores.
"""
import os
import hmac
import hashlib
import secrets
import requests
from urllib.parse import urlencode
from flask import Blueprint, request, redirect, jsonify
from ..models import Tenant
from ..extensions import db

shopify_oauth_bp = Blueprint('shopify_oauth', __name__)

# Shopify App credentials
SHOPIFY_API_KEY = os.getenv('SHOPIFY_CLIENT_ID', os.getenv('SHOPIFY_API_KEY', ''))
SHOPIFY_API_SECRET = os.getenv('SHOPIFY_CLIENT_SECRET', os.getenv('SHOPIFY_API_SECRET', ''))
APP_URL = os.getenv('APP_URL', 'https://app.cardflowlabs.com')

# Required scopes for TradeUp
SCOPES = [
    'read_customers',
    'write_customers',
    'read_orders',
    'read_products',
    'write_products',
    'read_inventory',
    'read_fulfillments',
]


def verify_hmac(query_params: dict) -> bool:
    """
    Verify the HMAC signature from Shopify.

    Args:
        query_params: Query parameters from Shopify request

    Returns:
        True if HMAC is valid
    """
    if not SHOPIFY_API_SECRET:
        return False

    received_hmac = query_params.get('hmac', '')

    # Build the message to verify
    params = {k: v for k, v in query_params.items() if k != 'hmac'}
    sorted_params = sorted(params.items())
    message = '&'.join(f'{k}={v}' for k, v in sorted_params)

    # Calculate expected HMAC
    computed_hmac = hmac.new(
        SHOPIFY_API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_hmac, received_hmac)


def verify_webhook_hmac(data: bytes, hmac_header: str) -> bool:
    """Verify webhook HMAC signature."""
    if not SHOPIFY_API_SECRET:
        return os.getenv('FLASK_ENV') == 'development'

    digest = hmac.new(
        SHOPIFY_API_SECRET.encode('utf-8'),
        data,
        hashlib.sha256
    ).digest()

    import base64
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)


def generate_state(shop: str) -> str:
    """Generate a secure state parameter that encodes the shop."""
    if not SHOPIFY_API_SECRET:
        return secrets.token_urlsafe(32)

    # Create state as: nonce.hmac(nonce+shop)
    nonce = secrets.token_urlsafe(16)
    message = f"{nonce}:{shop}"
    signature = hmac.new(
        SHOPIFY_API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:16]

    return f"{nonce}.{signature}"


def verify_state(state: str, shop: str) -> bool:
    """Verify the state parameter matches the shop."""
    if not SHOPIFY_API_SECRET:
        return True  # Skip verification in dev

    try:
        nonce, signature = state.split('.', 1)
        message = f"{nonce}:{shop}"
        expected = hmac.new(
            SHOPIFY_API_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()[:16]
        return hmac.compare_digest(signature, expected)
    except (ValueError, AttributeError):
        return False


@shopify_oauth_bp.route('/install', methods=['GET'])
def install():
    """
    Start the OAuth flow when merchant clicks "Install" in Shopify App Store.

    Shopify redirects here with: shop, timestamp, hmac
    """
    shop = request.args.get('shop')

    if not shop:
        return jsonify({'error': 'Missing shop parameter'}), 400

    # Verify HMAC if present
    if request.args.get('hmac') and not verify_hmac(dict(request.args)):
        return jsonify({'error': 'Invalid HMAC signature'}), 401

    # Check if already installed
    tenant = Tenant.query.filter_by(shopify_domain=shop).first()
    if tenant and tenant.shopify_access_token:
        # Already installed, redirect to app
        return redirect(f"https://{shop}/admin/apps/{SHOPIFY_API_KEY}")

    # Generate state that encodes shop for verification (no session needed)
    state = generate_state(shop)

    # Build OAuth URL
    oauth_params = {
        'client_id': SHOPIFY_API_KEY,
        'scope': ','.join(SCOPES),
        'redirect_uri': f"{APP_URL}/api/shopify/callback",
        'state': state,
    }

    auth_url = f"https://{shop}/admin/oauth/authorize?{urlencode(oauth_params)}"
    return redirect(auth_url)


@shopify_oauth_bp.route('/callback', methods=['GET'])
def callback():
    """
    Handle OAuth callback from Shopify after merchant approves.

    Shopify redirects here with: code, hmac, shop, state, timestamp
    """
    shop = request.args.get('shop')
    code = request.args.get('code')
    state = request.args.get('state')

    if not all([shop, code, state]):
        return jsonify({'error': 'Missing required parameters'}), 400

    # Verify HMAC
    if not verify_hmac(dict(request.args)):
        return jsonify({'error': 'Invalid HMAC signature'}), 401

    # Verify state parameter (no session needed)
    if not verify_state(state, shop):
        return jsonify({'error': 'Invalid state parameter'}), 401

    # Exchange code for access token
    token_url = f"https://{shop}/admin/oauth/access_token"
    token_response = requests.post(token_url, json={
        'client_id': SHOPIFY_API_KEY,
        'client_secret': SHOPIFY_API_SECRET,
        'code': code,
    })

    if not token_response.ok:
        return jsonify({
            'error': 'Failed to get access token',
            'details': token_response.text
        }), 500

    token_data = token_response.json()
    access_token = token_data.get('access_token')

    if not access_token:
        return jsonify({'error': 'No access token returned'}), 500

    # Get shop info
    shop_info = get_shop_info(shop, access_token)

    # Create or update tenant
    tenant = Tenant.query.filter_by(shopify_domain=shop).first()

    if not tenant:
        # Create new tenant
        shop_name = shop_info.get('name', shop.replace('.myshopify.com', ''))
        shop_slug = shop.replace('.myshopify.com', '').lower()

        tenant = Tenant(
            shop_name=shop_name,
            shop_slug=shop_slug,
            shopify_domain=shop,
            shopify_access_token=access_token,
            subscription_plan='starter',
            subscription_status='pending',
        )
        db.session.add(tenant)
    else:
        # Update existing tenant
        tenant.shopify_access_token = access_token

    db.session.commit()

    # Register webhooks
    register_webhooks(shop, access_token)

    # Redirect to billing (for new installs) or app dashboard
    if not tenant.subscription_active:
        return redirect(f"{APP_URL}/app?shop={shop}&setup=billing")

    return redirect(f"https://{shop}/admin/apps/{SHOPIFY_API_KEY}")


def get_shop_info(shop: str, access_token: str) -> dict:
    """Fetch shop information from Shopify."""
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json',
    }

    response = requests.get(
        f"https://{shop}/admin/api/2024-01/shop.json",
        headers=headers
    )

    if response.ok:
        return response.json().get('shop', {})
    return {}


def register_webhooks(shop: str, access_token: str):
    """Register required webhooks with Shopify."""
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json',
    }

    webhooks = [
        {
            'topic': 'orders/paid',
            'address': f"{APP_URL}/webhook/shopify/orders/paid",
            'format': 'json',
        },
        {
            'topic': 'orders/fulfilled',
            'address': f"{APP_URL}/webhook/shopify/orders/fulfilled",
            'format': 'json',
        },
        {
            'topic': 'customers/create',
            'address': f"{APP_URL}/webhook/shopify/customers/create",
            'format': 'json',
        },
        {
            'topic': 'app/uninstalled',
            'address': f"{APP_URL}/webhook/shopify/app/uninstalled",
            'format': 'json',
        },
        {
            'topic': 'app_subscriptions/update',
            'address': f"{APP_URL}/webhook/shopify-billing/subscriptions",
            'format': 'json',
        },
    ]

    for webhook in webhooks:
        try:
            requests.post(
                f"https://{shop}/admin/api/2024-01/webhooks.json",
                headers=headers,
                json={'webhook': webhook}
            )
        except Exception as e:
            print(f"[Webhook] Failed to register {webhook['topic']}: {e}")


@shopify_oauth_bp.route('/uninstall', methods=['POST'])
def handle_uninstall():
    """
    Handle app/uninstalled webhook.
    Clean up tenant data when app is uninstalled.
    """
    hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
    if not verify_webhook_hmac(request.get_data(), hmac_header):
        return jsonify({'error': 'Invalid signature'}), 401

    shop = request.headers.get('X-Shopify-Shop-Domain', '')

    tenant = Tenant.query.filter_by(shopify_domain=shop).first()
    if tenant:
        # Mark as inactive, keep data for potential re-install
        tenant.is_active = False
        tenant.shopify_access_token = None
        tenant.subscription_active = False
        tenant.subscription_status = 'uninstalled'
        db.session.commit()

    print(f"[OAuth] App uninstalled from {shop}")
    return jsonify({'success': True})


@shopify_oauth_bp.route('/verify', methods=['GET'])
def verify_installation():
    """
    Verify the app is properly installed for a shop.
    Used by the embedded app to check installation status.
    """
    shop = request.args.get('shop')

    if not shop:
        return jsonify({'error': 'Missing shop parameter'}), 400

    tenant = Tenant.query.filter_by(shopify_domain=shop).first()

    if not tenant or not tenant.shopify_access_token:
        return jsonify({
            'installed': False,
            'message': 'App not installed'
        })

    return jsonify({
        'installed': True,
        'active': tenant.is_active,
        'subscription': {
            'plan': tenant.subscription_plan,
            'status': tenant.subscription_status,
            'active': tenant.subscription_active,
        }
    })
