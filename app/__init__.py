"""
Quick Flip Membership Platform
Flask application factory
"""
import os
from flask import Flask
from flask_cors import CORS

from .extensions import db, migrate
from .config import get_config


def create_app(config_name: str = None) -> Flask:
    """
    Application factory for creating Flask app instances.

    Args:
        config_name: Configuration environment (development, production, testing)

    Returns:
        Configured Flask application
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'quick-flip'}

    # Root route - redirect to app
    @app.route('/')
    def index():
        from flask import request, redirect
        shop = request.args.get('shop')
        if shop:
            return redirect(f'/app?shop={shop}')
        return {'service': 'TradeUp by Cardflow Labs', 'status': 'running'}

    # Shopify embedded app route
    @app.route('/app')
    def shopify_app():
        from flask import request
        shop = request.args.get('shop', '')
        host = request.args.get('host', '')
        setup = request.args.get('setup', '')

        api_key = os.getenv('SHOPIFY_CLIENT_ID', os.getenv('SHOPIFY_API_KEY', ''))

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TradeUp by Cardflow Labs</title>
    <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            background: white;
            padding: 3rem;
            border-radius: 16px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            text-align: center;
            max-width: 500px;
        }}
        h1 {{
            color: #1a1a2e;
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            color: #667eea;
            font-size: 1.1rem;
            margin-bottom: 2rem;
        }}
        .status {{
            background: #f0fdf4;
            border: 1px solid #86efac;
            color: #166534;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
        }}
        .info {{
            color: #6b7280;
            font-size: 0.9rem;
            line-height: 1.6;
        }}
        .shop {{
            background: #f3f4f6;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-family: monospace;
            margin: 1rem 0;
        }}
        .btn {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 0.75rem 2rem;
            border-radius: 8px;
            text-decoration: none;
            margin-top: 1.5rem;
            transition: background 0.2s;
        }}
        .btn:hover {{
            background: #5a67d8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 TradeUp</h1>
        <p class="subtitle">by Cardflow Labs</p>

        <div class="status">
            ✅ App installed successfully!
        </div>

        <p class="info">
            Your membership rewards platform is connected.
        </p>

        <div class="shop">{shop}</div>

        <p class="info">
            {"Setup billing to activate your subscription." if setup == "billing" else "Dashboard coming soon!"}
        </p>

        {"<a href='/api/billing/plans?shop=" + shop + "' class='btn'>Set Up Billing</a>" if setup == "billing" else ""}
    </div>

    <script>
        var AppBridge = window['app-bridge'];
        var createApp = AppBridge.default;
        var app = createApp({{
            apiKey: '{api_key}',
            host: '{host}',
        }});
    </script>
</body>
</html>'''

    return app


def register_blueprints(app: Flask) -> None:
    """Register all API blueprints."""
    # Core API
    from .api.members import members_bp
    from .api.trade_ins import trade_ins_bp
    from .api.bonuses import bonuses_bp
    from .api.dashboard import dashboard_bp

    # Auth and Membership
    from .api.auth import auth_bp
    from .api.membership import membership_bp

    # Shopify OAuth
    from .api.shopify_oauth import shopify_oauth_bp

    # Store Credit Events
    from .api.store_credit_events import store_credit_events_bp

    # Admin API
    from .api.admin import admin_bp

    # Billing (Shopify Billing API - replaces Stripe)
    from .api.billing import billing_bp

    # Webhooks
    from .webhooks.shopify import webhooks_bp
    from .webhooks.shopify_billing import shopify_billing_webhook_bp
    # Note: Stripe webhooks kept for migration period
    from .webhooks.stripe import stripe_webhook_bp

    # Core API routes
    app.register_blueprint(members_bp, url_prefix='/api/members')
    app.register_blueprint(trade_ins_bp, url_prefix='/api/trade-ins')
    app.register_blueprint(bonuses_bp, url_prefix='/api/bonuses')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')

    # Auth and Membership routes
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(membership_bp, url_prefix='/api/membership')

    # Shopify OAuth routes
    app.register_blueprint(shopify_oauth_bp, url_prefix='/api/shopify')

    # Store Credit Events routes
    app.register_blueprint(store_credit_events_bp, url_prefix='/api/store-credit-events')

    # Admin API routes
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    # Billing API routes (Shopify Billing)
    app.register_blueprint(billing_bp, url_prefix='/api/billing')

    # Webhook routes
    app.register_blueprint(webhooks_bp, url_prefix='/webhook')
    app.register_blueprint(shopify_billing_webhook_bp, url_prefix='/webhook/shopify-billing')
    # Stripe webhooks (deprecated - kept for migration)
    app.register_blueprint(stripe_webhook_bp, url_prefix='/webhook/stripe')


def register_error_handlers(app: Flask) -> None:
    """Register error handlers."""

    @app.errorhandler(400)
    def bad_request(error):
        return {'error': 'Bad request', 'message': str(error)}, 400

    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found', 'message': str(error)}, 404

    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error', 'message': str(error)}, 500
