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
        api_key = os.getenv('SHOPIFY_CLIENT_ID', os.getenv('SHOPIFY_API_KEY', ''))

        return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>TradeUp Dashboard</title>
    <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --brand: #e85d27;
            --brand-light: #ff7a42;
            --success: #00d68f;
            --warning: #ffb547;
            --info: #00cfe8;
            --processing: #a855f7;
            --space-xs: 6px; --space-sm: 12px; --space-md: 16px; --space-lg: 24px; --space-xl: 32px;
        }}
        [data-theme="dark"] {{
            --bg-primary: #050508; --bg-secondary: #0d0d12; --bg-card: #16161d;
            --text-primary: #f8f8fa; --text-secondary: #a1a1aa; --border: #27272a;
        }}
        [data-theme="light"] {{
            --bg-primary: #ffffff; --bg-secondary: #f5f5f6; --bg-card: #ffffff;
            --text-primary: #1a1a1a; --text-secondary: #6b7280; --border: #e5e5e5;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding-bottom: 80px;
        }}
        .header {{
            background: var(--bg-secondary);
            padding: var(--space-md) var(--space-lg);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .logo {{ display: flex; align-items: center; gap: var(--space-sm); }}
        .logo-icon {{ font-size: 1.5rem; }}
        .logo-text {{ font-weight: 700; font-size: 1.25rem; }}
        .logo-sub {{ color: var(--text-secondary); font-size: 0.75rem; }}
        .theme-toggle {{
            background: var(--bg-card); border: 1px solid var(--border);
            padding: 8px 12px; border-radius: 8px; cursor: pointer;
            color: var(--text-primary); font-size: 1rem;
        }}
        .container {{ max-width: 900px; margin: 0 auto; padding: var(--space-lg); }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: var(--space-md);
            margin-bottom: var(--space-xl);
        }}
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: var(--space-lg);
            text-align: center;
        }}
        .stat-value {{
            font-size: 2.5rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            background: linear-gradient(135deg, var(--brand) 0%, var(--brand-light) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .stat-label {{ color: var(--text-secondary); margin-top: var(--space-xs); font-size: 0.9rem; }}
        .section {{ margin-bottom: var(--space-xl); }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-md);
        }}
        .section-title {{ font-size: 1.25rem; font-weight: 700; }}
        .badge {{
            background: var(--brand);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .member-list {{ display: flex; flex-direction: column; gap: var(--space-sm); }}
        .member-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: var(--space-md);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .member-info {{ display: flex; align-items: center; gap: var(--space-md); }}
        .member-avatar {{
            width: 48px; height: 48px;
            background: linear-gradient(135deg, var(--brand) 0%, var(--brand-light) 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            color: white;
        }}
        .member-name {{ font-weight: 600; }}
        .member-tier {{ color: var(--text-secondary); font-size: 0.85rem; }}
        .member-credit {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--success);
        }}
        .tier-badge {{
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .tier-silver {{ background: #71717a20; color: #a1a1aa; }}
        .tier-gold {{ background: #fbbf2420; color: #fbbf24; }}
        .tier-platinum {{ background: #a855f720; color: #a855f7; }}
        .quick-actions {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: var(--space-md);
        }}
        .action-btn {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: var(--space-lg);
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            color: var(--text-primary);
        }}
        .action-btn:hover {{
            border-color: var(--brand);
            transform: translateY(-2px);
        }}
        .action-icon {{ font-size: 1.5rem; margin-bottom: var(--space-xs); }}
        .action-label {{ font-size: 0.9rem; font-weight: 500; }}
        .bottom-nav {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: space-around;
            padding: var(--space-sm) 0;
            padding-bottom: max(var(--space-sm), env(safe-area-inset-bottom));
        }}
        .nav-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.75rem;
            cursor: pointer;
            transition: color 0.2s;
        }}
        .nav-item.active, .nav-item:hover {{ color: var(--brand); }}
        .nav-icon {{ font-size: 1.25rem; }}
        .shop-badge {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 6px 12px;
            border-radius: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}
        .empty-state {{
            text-align: center;
            padding: var(--space-xl);
            color: var(--text-secondary);
        }}
        .empty-icon {{ font-size: 3rem; margin-bottom: var(--space-md); opacity: 0.5; }}
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">
            <span class="logo-icon">🚀</span>
            <div>
                <div class="logo-text">TradeUp</div>
                <div class="logo-sub">by Cardflow Labs</div>
            </div>
        </div>
        <div style="display: flex; gap: var(--space-sm); align-items: center;">
            <span class="shop-badge">{shop.replace('.myshopify.com', '')}</span>
            <button class="theme-toggle" onclick="toggleTheme()">🌓</button>
        </div>
    </header>

    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">127</div>
                <div class="stat-label">Total Members</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">$4,280</div>
                <div class="stat-label">Store Credit Issued</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">23</div>
                <div class="stat-label">Active Trade-Ins</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">$892</div>
                <div class="stat-label">Pending Bonuses</div>
            </div>
        </div>

        <div class="section">
            <div class="section-header">
                <h2 class="section-title">Quick Actions</h2>
            </div>
            <div class="quick-actions">
                <a class="action-btn" href="#">
                    <div class="action-icon">👤</div>
                    <div class="action-label">Add Member</div>
                </a>
                <a class="action-btn" href="#">
                    <div class="action-icon">📦</div>
                    <div class="action-label">New Trade-In</div>
                </a>
                <a class="action-btn" href="#">
                    <div class="action-icon">💰</div>
                    <div class="action-label">Process Bonuses</div>
                </a>
                <a class="action-btn" href="#">
                    <div class="action-icon">📊</div>
                    <div class="action-label">View Reports</div>
                </a>
            </div>
        </div>

        <div class="section">
            <div class="section-header">
                <h2 class="section-title">Recent Members</h2>
                <span class="badge">5 new this week</span>
            </div>
            <div class="member-list">
                <div class="member-card">
                    <div class="member-info">
                        <div class="member-avatar">JD</div>
                        <div>
                            <div class="member-name">John Doe</div>
                            <div class="member-tier">Member since Jan 2026</div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: var(--space-md);">
                        <span class="tier-badge tier-platinum">Platinum</span>
                        <span class="member-credit">$245.00</span>
                    </div>
                </div>
                <div class="member-card">
                    <div class="member-info">
                        <div class="member-avatar">SM</div>
                        <div>
                            <div class="member-name">Sarah Miller</div>
                            <div class="member-tier">Member since Dec 2025</div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: var(--space-md);">
                        <span class="tier-badge tier-gold">Gold</span>
                        <span class="member-credit">$128.50</span>
                    </div>
                </div>
                <div class="member-card">
                    <div class="member-info">
                        <div class="member-avatar">MJ</div>
                        <div>
                            <div class="member-name">Mike Johnson</div>
                            <div class="member-tier">Member since Jan 2026</div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: var(--space-md);">
                        <span class="tier-badge tier-silver">Silver</span>
                        <span class="member-credit">$52.00</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <nav class="bottom-nav">
        <a class="nav-item active">
            <span class="nav-icon">🏠</span>
            <span>Home</span>
        </a>
        <a class="nav-item">
            <span class="nav-icon">👥</span>
            <span>Members</span>
        </a>
        <a class="nav-item">
            <span class="nav-icon">📦</span>
            <span>Trade-Ins</span>
        </a>
        <a class="nav-item">
            <span class="nav-icon">💰</span>
            <span>Bonuses</span>
        </a>
        <a class="nav-item">
            <span class="nav-icon">⚙️</span>
            <span>Settings</span>
        </a>
    </nav>

    <script>
        var AppBridge = window['app-bridge'];
        var createApp = AppBridge.default;
        var app = createApp({{ apiKey: '{api_key}', host: '{host}' }});

        function toggleTheme() {{
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            html.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
            localStorage.setItem('tradeup-theme', current === 'dark' ? 'light' : 'dark');
        }}
        const saved = localStorage.getItem('tradeup-theme');
        if (saved) document.documentElement.setAttribute('data-theme', saved);
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
