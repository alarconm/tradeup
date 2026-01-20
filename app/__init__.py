"""
TradeUp Membership Platform
Flask application factory
"""
import os
import logging
from flask import Flask
from flask_cors import CORS

from .extensions import db, migrate
from .config import get_config
from .utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Optional compression (graceful fallback if not installed)
try:
    from flask_compress import Compress
    compress = Compress()
except ImportError:
    compress = None


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

    # Setup logging before anything else
    setup_logging()

    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    # Initialize Sentry error tracking (before other extensions for full coverage)
    try:
        from .utils.sentry import init_sentry
        init_sentry(app)
    except ImportError:
        pass

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize caching (Redis with graceful fallback)
    try:
        from .utils.cache import init_cache
        init_cache(app)
    except ImportError:
        pass  # Flask-Caching not installed

    # Initialize compression (gzip/brotli for responses)
    if compress:
        compress.init_app(app)
        app.config['COMPRESS_MIMETYPES'] = [
            'text/html', 'text/css', 'text/xml', 'text/javascript',
            'application/json', 'application/javascript', 'application/xml'
        ]
        app.config['COMPRESS_LEVEL'] = 6  # Balance between speed and compression
        app.config['COMPRESS_MIN_SIZE'] = 500  # Only compress responses > 500 bytes

    # Configure CORS - allow frontend origins
    import re
    cors_origins = [
        'http://localhost:5173',
        'http://localhost:5174',
        'http://localhost:5175',
        'http://localhost:5176',
        'http://127.0.0.1:5173',
        'https://admin.shopify.com',
        re.compile(r'https://.*\.myshopify\.com'),
    ]
    # Allow Cloudflare tunnels in development
    if config_name != 'production':
        cors_origins.append(re.compile(r'https://.*\.trycloudflare\.com'))
    CORS(app, origins=cors_origins, supports_credentials=True, allow_headers=['Content-Type', 'Authorization', 'X-Shop-Domain'])

    # Initialize rate limiter (production only)
    if config_name == 'production' or os.getenv('ENABLE_RATE_LIMITING') == 'true':
        from .middleware import init_rate_limiter
        if init_rate_limiter:
            init_rate_limiter(app)
            logger.info('Rate limiting enabled')
        else:
            logger.info('Flask-Limiter not installed, rate limiting disabled')

    # Initialize query profiler (set QUERY_PROFILING=true to enable)
    from .middleware import init_query_profiler
    init_query_profiler(app)

    # Initialize request ID tracking for request tracing
    from .middleware import init_request_id_tracking
    init_request_id_tracking(app)

    # Register blueprints
    register_blueprints(app)

    # Serve React frontend assets from frontend/dist/
    serve_frontend_assets(app)

    # Register CLI commands
    from .commands import init_app as init_commands
    init_commands(app)

    # Initialize background scheduler for automated tasks (production only)
    # Handles: monthly credits, credit expiration, expiration warnings
    try:
        from .utils.scheduler import init_scheduler
        init_scheduler(app)
    except ImportError:
        logger.info('APScheduler not installed, automated tasks disabled')

    # Register error handlers
    register_error_handlers(app)

    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'tradeup'}

    # Debug endpoint to see what params Shopify sends
    @app.route('/debug/params')
    def debug_params():
        from flask import request
        return {
            'args': dict(request.args),
            'headers': {k: v for k, v in request.headers if k.lower() in ['host', 'referer', 'origin', 'x-shop-domain']},
            'url': request.url,
            'base_url': request.base_url,
        }

    # Static pages (privacy policy, support, terms)
    @app.route('/privacy-policy.html')
    @app.route('/privacy-policy')
    def privacy_policy():
        from flask import send_from_directory
        return send_from_directory('static', 'privacy-policy.html')

    @app.route('/support.html')
    @app.route('/support')
    def support_page():
        from flask import send_from_directory
        return send_from_directory('static', 'support.html')

    @app.route('/terms-of-service.html')
    @app.route('/terms-of-service')
    @app.route('/terms')
    def terms_of_service():
        from flask import send_from_directory
        return send_from_directory('static', 'terms-of-service.html')

    # Landing pages (marketing/A/B test variants)
    @app.route('/landing')
    @app.route('/landing/')
    def landing_index():
        from flask import send_from_directory
        app_dir = os.path.dirname(os.path.abspath(__file__))
        landing_dir = os.path.join(os.path.dirname(app_dir), 'landing-pages')
        return send_from_directory(landing_dir, 'index.html')

    @app.route('/landing/<variant>')
    def landing_variant(variant):
        from flask import send_from_directory, abort
        import os as os_module
        app_dir = os.path.dirname(os.path.abspath(__file__))
        landing_dir = os.path.join(os.path.dirname(app_dir), 'landing-pages')
        # Support both with and without .html extension
        filename = f'{variant}.html' if not variant.endswith('.html') else variant
        filepath = os.path.join(landing_dir, filename)
        if not os_module.path.exists(filepath):
            abort(404)
        return send_from_directory(landing_dir, filename)

    # Root route - redirect to app
    @app.route('/')
    def index():
        from flask import request, redirect
        shop = request.args.get('shop')
        if shop:
            return redirect(f'/app?shop={shop}')
        return {'service': 'TradeUp by Cardflow Labs', 'status': 'running', 'version': '2.0.0'}

    # Shopify embedded app route - Serve React SPA
    # Note: /app/ (with trailing slash) is required because Shopify accesses it that way
    @app.route('/app')
    @app.route('/app/')
    @app.route('/app/<path:path>')
    def shopify_app(path=None):
        from flask import request, make_response
        shop = request.args.get('shop', '')
        host = request.args.get('host', '')
        logger.debug(f'/app request: shop={shop}, host={host}, path={path}')
        api_key = os.getenv('SHOPIFY_CLIENT_ID', os.getenv('SHOPIFY_API_KEY', ''))
        # Get app URL - use request.url_root for local dev, APP_URL for production
        # This ensures local dev always uses the correct port from the actual request
        railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
        if railway_domain:
            app_url = f'https://{railway_domain}'
        elif os.getenv('FLASK_ENV') == 'development' or os.getenv('FLASK_DEBUG'):
            # Local dev: always use request URL to get correct port
            app_url = request.url_root.rstrip('/')
        else:
            app_url = os.getenv('APP_URL', request.url_root.rstrip('/'))

        # Create response with cache-control headers to prevent Shopify iframe caching
        response = make_response(get_spa_html(shop, host, api_key, app_url))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    return app


def get_spa_html(shop: str, host: str, api_key: str, app_url: str) -> str:
    """
    Serve the React frontend with Shopify App Bridge script injected.

    Reads the built frontend from frontend/dist/index.html and injects
    the App Bridge CDN script for Shopify embedded app functionality.
    """
    import os

    # Find frontend dist directory (relative to app/ folder)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(app_dir)
    dist_path = os.path.join(project_root, 'frontend', 'dist', 'index.html')

    try:
        with open(dist_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except FileNotFoundError:
        # Fallback: return error message if build doesn't exist
        return f'''<!DOCTYPE html>
<html><head><title>TradeUp - Build Required</title></head>
<body style="font-family: system-ui; padding: 40px; text-align: center;">
<h1>Frontend Build Not Found</h1>
<p>Run <code>cd frontend && npm run build</code> to build the React app.</p>
<p>Looking for: {dist_path}</p>
</body></html>'''

    # Inject Shopify context before </head>
    # App Bridge CDN is already in index.html, don't add it again
    # Only inject shop if present (otherwise let App Bridge provide it)
    shop_js = f'"{shop}"' if shop else 'null'
    host_js = f'"{host}"' if host else 'null'
    context_script = f'''
    <script>
      window.__TRADEUP_CONFIG__ = {{
        shop: {shop_js},
        host: {host_js},
        apiKey: "{api_key}",
        appUrl: "{app_url}"
      }};
    </script>'''

    # Insert config script before </head> (App Bridge is already in the HTML)
    html = html.replace('</head>', f'{context_script}\n  </head>')

    return html


# LEGACY INLINE SPA REMOVED - Now serving React frontend from frontend/dist/
# The old inline SPA (2000+ lines) was replaced Jan 2026.


def serve_frontend_assets(app: Flask) -> None:
    """
    Serve static assets from the React frontend build.
    This handles /assets/* requests for JS, CSS, and other static files.
    Assets have content hashes in filenames, enabling aggressive caching.
    """
    from flask import send_from_directory, make_response
    import os

    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(app_dir)
    assets_dir = os.path.join(project_root, 'frontend', 'dist', 'assets')
    dist_dir = os.path.join(project_root, 'frontend', 'dist')

    @app.route('/assets/<path:filename>')
    def frontend_assets(filename):
        response = make_response(send_from_directory(assets_dir, filename))
        # Assets have content hashes - cache for 1 year (immutable)
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response

    @app.route('/vite.svg')
    def vite_svg():
        response = make_response(send_from_directory(dist_dir, 'vite.svg'))
        response.headers['Cache-Control'] = 'public, max-age=86400'  # 1 day
        return response

    @app.route('/tradeup-icon.svg')
    def tradeup_icon_svg():
        response = make_response(send_from_directory(dist_dir, 'tradeup-icon.svg'))
        response.headers['Cache-Control'] = 'public, max-age=86400'  # 1 day
        return response



def register_blueprints(app: Flask) -> None:
    """Register all API blueprints."""
    # Core API
    from .api.members import members_bp
    from .api.trade_ins import trade_ins_bp
    from .api.trade_ledger import trade_ledger_bp
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

    # Tenant Settings
    from .api.settings import settings_bp

    # Product Setup Wizard
    from .api.product_wizard import product_wizard_bp

    # Billing (Shopify Billing API - replaces Stripe)
    from .api.billing import billing_bp

    # Partner Integrations
    from .api.partners import partners_bp

    # Promotions & Store Credit
    from .api.promotions import promotions_bp

    # Bonuses API
    from .api.bonuses import bonuses_bp

    # Tier Management
    from .api.tiers import tiers_bp

    # Customer Account (public facing)
    from .api.customer_account import customer_account_bp

    # Referral Program
    from .api.referrals import referrals_bp

    # Onboarding
    from .api.onboarding import onboarding_bp

    # Setup Checklist (progress tracking, milestones)
    from .api.setup_checklist import setup_checklist_bp

    # Shopify Data (collections, vendors, product types)
    from .api.shopify_data import shopify_data_bp

    # Scheduled Tasks (monthly credits, expiration, etc.)
    from .api.scheduled_tasks import scheduled_tasks_bp

    # Analytics
    from .api.analytics import analytics_bp

    # Member Import
    from .api.member_import import member_import_bp

    # Email Notifications
    from .api.email import email_bp

    # Webhooks
    from .webhooks.shopify import webhooks_bp
    from .webhooks.shopify_billing import shopify_billing_webhook_bp
    from .webhooks.customer_lifecycle import customer_lifecycle_bp
    from .webhooks.order_lifecycle import order_lifecycle_bp
    from .webhooks.subscription_lifecycle import subscription_lifecycle_bp
    from .webhooks.app_lifecycle import app_lifecycle_bp

    # Core API routes
    app.register_blueprint(members_bp, url_prefix='/api/members')
    app.register_blueprint(trade_ins_bp, url_prefix='/api/trade-ins')
    app.register_blueprint(trade_ledger_bp, url_prefix='/api/trade-ledger')
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

    # Tenant Settings routes
    app.register_blueprint(settings_bp, url_prefix='/api/settings')

    # Product Setup Wizard routes
    app.register_blueprint(product_wizard_bp, url_prefix='/api/products/wizard')

    # Billing API routes (Shopify Billing)
    app.register_blueprint(billing_bp, url_prefix='/api/billing')

    # Partner Integration routes
    app.register_blueprint(partners_bp, url_prefix='/api/partners')

    # Promotions & Store Credit routes
    app.register_blueprint(promotions_bp, url_prefix='/api/promotions')

    # Bonuses API routes
    app.register_blueprint(bonuses_bp, url_prefix='/api/bonuses')

    # Tier Management routes
    app.register_blueprint(tiers_bp)

    # Customer Account routes (public facing)
    app.register_blueprint(customer_account_bp, url_prefix='/api/customer')

    # Referral Program routes
    app.register_blueprint(referrals_bp, url_prefix='/api/referrals')

    # Onboarding routes
    app.register_blueprint(onboarding_bp, url_prefix='/api/onboarding')

    # Setup Checklist routes (progress tracking, milestones)
    app.register_blueprint(setup_checklist_bp, url_prefix='/api/setup')

    # Shopify Data routes (collections, vendors, etc.)
    app.register_blueprint(shopify_data_bp, url_prefix='/api/shopify-data')

    # Scheduled Tasks routes (monthly credits, expiration)
    app.register_blueprint(scheduled_tasks_bp, url_prefix='/api/scheduled-tasks')

    # Analytics routes
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')

    # Member Import routes
    app.register_blueprint(member_import_bp, url_prefix='/api/members/import')

    # Email Notification routes
    app.register_blueprint(email_bp, url_prefix='/api/email')

    # Webhook routes
    app.register_blueprint(webhooks_bp, url_prefix='/webhook')
    app.register_blueprint(shopify_billing_webhook_bp, url_prefix='/webhook/shopify-billing')
    app.register_blueprint(customer_lifecycle_bp, url_prefix='/webhook')
    app.register_blueprint(order_lifecycle_bp, url_prefix='/webhook')
    app.register_blueprint(subscription_lifecycle_bp, url_prefix='/webhook')
    app.register_blueprint(app_lifecycle_bp, url_prefix='/webhook')

    # Shopify Flow integration
    from .api.flow import flow_bp
    app.register_blueprint(flow_bp, url_prefix='/flow')

    # Points and Rewards (Loyalty System)
    from .api.points import points_bp
    from .api.rewards import rewards_bp
    app.register_blueprint(points_bp, url_prefix='/api/points')
    app.register_blueprint(rewards_bp, url_prefix='/api/rewards')

    # App Proxy (customer-facing rewards page at /apps/rewards)
    from .api.proxy import proxy_bp
    app.register_blueprint(proxy_bp, url_prefix='/proxy')

    # Customer Segments (Shopify Email + Flow integration)
    from .api.segments import segments_bp
    app.register_blueprint(segments_bp, url_prefix='/api/segments')

    # Cashback Campaigns
    from .api.cashback import cashback_bp
    app.register_blueprint(cashback_bp, url_prefix='/api/cashback')

    # Third-Party Integrations (Klaviyo, SMS, etc.)
    from .api.integrations.klaviyo import klaviyo_bp
    from .api.integrations.sms import sms_bp
    from .api.integrations.thirdparty import thirdparty_bp
    app.register_blueprint(klaviyo_bp, url_prefix='/api/integrations/klaviyo')
    app.register_blueprint(sms_bp, url_prefix='/api/integrations/sms')
    app.register_blueprint(thirdparty_bp, url_prefix='/api/integrations')

    # Benchmark Reports
    from .api.benchmarks import benchmarks_bp
    app.register_blueprint(benchmarks_bp, url_prefix='/api/benchmarks')

    # Gamification (Badges, Achievements, Streaks)
    from .api.gamification import gamification_bp
    app.register_blueprint(gamification_bp, url_prefix='/api/gamification')

    # Birthday Rewards
    from .api.birthday import birthday_bp
    app.register_blueprint(birthday_bp, url_prefix='/api/birthday')

    # Nudges & Reminders
    from .api.nudges import nudges_bp
    app.register_blueprint(nudges_bp, url_prefix='/api/nudges')

    # Loyalty Page Builder
    from .api.page_builder import page_builder_bp
    app.register_blueprint(page_builder_bp, url_prefix='/api/page-builder')

    # Widget Visual Builder
    from .api.widget_builder import widget_builder_bp
    app.register_blueprint(widget_builder_bp, url_prefix='/api/widget-builder')

    # Guest Checkout Points
    from .api.guest_points import guest_points_bp
    app.register_blueprint(guest_points_bp, url_prefix='/api/guest-points')


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
