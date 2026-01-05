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
        return {'service': 'TradeUp by Cardflow Labs', 'status': 'running', 'version': '1.1.3'}

    # Shopify embedded app route - Full SPA
    @app.route('/app')
    def shopify_app():
        from flask import request, make_response
        shop = request.args.get('shop', '')
        host = request.args.get('host', '')
        api_key = os.getenv('SHOPIFY_CLIENT_ID', os.getenv('SHOPIFY_API_KEY', ''))
        # Get app URL from environment or construct from Railway domain
        app_url = os.getenv('APP_URL')
        if not app_url:
            railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
            if railway_domain:
                app_url = f'https://{railway_domain}'
            else:
                app_url = request.url_root.rstrip('/')

        # Create response with cache-control headers to prevent Shopify iframe caching
        response = make_response(get_spa_html(shop, host, api_key, app_url))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    return app


def get_spa_html(shop: str, host: str, api_key: str, app_url: str) -> str:
    """Return the full SPA HTML for the TradeUp dashboard."""
    return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=1">
    <title>TradeUp Dashboard</title>
    <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --brand: #e85d27;
            --brand-light: #ff7a42;
            --brand-dark: #c94d1f;
            --success: #00d68f;
            --warning: #ffb547;
            --info: #00cfe8;
            --danger: #ff4757;
            --processing: #a855f7;
            --space-xs: 6px;
            --space-sm: 12px;
            --space-md: 16px;
            --space-lg: 24px;
            --space-xl: 32px;
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-full: 50px;
        }}
        [data-theme="dark"] {{
            --bg-primary: #050508;
            --bg-secondary: #0d0d12;
            --bg-card: #16161d;
            --bg-input: #1e1e26;
            --text-primary: #f8f8fa;
            --text-secondary: #a1a1aa;
            --text-muted: #71717a;
            --border: #27272a;
            --border-focus: #e85d27;
        }}
        [data-theme="light"] {{
            --bg-primary: #f8f9fa;
            --bg-secondary: #ffffff;
            --bg-card: #ffffff;
            --bg-input: #f1f1f1;
            --text-primary: #1a1a1a;
            --text-secondary: #6b7280;
            --text-muted: #9ca3af;
            --border: #e5e5e5;
            --border-focus: #e85d27;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            min-height: 100dvh;
            padding-bottom: 80px;
            -webkit-font-smoothing: antialiased;
        }}

        /* Header */
        .header {{
            background: var(--bg-secondary);
            padding: var(--space-sm) var(--space-md);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .logo {{ display: flex; align-items: center; gap: var(--space-sm); }}
        .logo-icon {{ font-size: 1.25rem; }}
        .logo-text {{ font-weight: 700; font-size: 1.1rem; }}
        .logo-sub {{ color: var(--text-secondary); font-size: 0.65rem; }}
        .header-actions {{ display: flex; gap: var(--space-xs); align-items: center; }}
        .shop-badge {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 4px 8px;
            border-radius: var(--radius-sm);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            color: var(--text-secondary);
            display: none;
        }}
        @media (min-width: 480px) {{ .shop-badge {{ display: block; }} }}
        .icon-btn {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            width: 36px;
            height: 36px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            color: var(--text-primary);
            font-size: 1rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }}
        .icon-btn:hover {{ border-color: var(--brand); }}

        /* Container */
        .container {{ max-width: 800px; margin: 0 auto; padding: var(--space-md); }}
        @media (max-width: 480px) {{ .container {{ padding: var(--space-sm); }} }}

        /* Pages */
        .page {{ display: none; animation: fadeIn 0.3s ease; }}
        .page.active {{ display: block; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}

        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: var(--space-sm);
            margin-bottom: var(--space-lg);
        }}
        @media (min-width: 600px) {{ .stats-grid {{ grid-template-columns: repeat(4, 1fr); }} }}
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: var(--space-md);
            text-align: center;
        }}
        .stat-value {{
            font-size: 1.75rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            background: linear-gradient(135deg, var(--brand) 0%, var(--brand-light) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        @media (max-width: 480px) {{ .stat-value {{ font-size: 1.5rem; }} }}
        .stat-label {{ color: var(--text-secondary); margin-top: 4px; font-size: 0.75rem; }}

        /* Section */
        .section {{ margin-bottom: var(--space-lg); }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-sm);
        }}
        .section-title {{ font-size: 1rem; font-weight: 700; }}
        .badge {{
            background: var(--brand);
            color: white;
            padding: 3px 10px;
            border-radius: var(--radius-full);
            font-size: 0.7rem;
            font-weight: 600;
        }}
        .badge-outline {{
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-secondary);
        }}

        /* Quick Actions */
        .quick-actions {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: var(--space-sm);
        }}
        @media (min-width: 600px) {{ .quick-actions {{ grid-template-columns: repeat(4, 1fr); }} }}
        .action-btn {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: var(--space-md);
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            color: var(--text-primary);
        }}
        .action-btn:hover {{ border-color: var(--brand); transform: translateY(-2px); }}
        .action-btn:active {{ transform: translateY(0); }}
        .action-icon {{ font-size: 1.5rem; margin-bottom: var(--space-xs); }}
        .action-label {{ font-size: 0.8rem; font-weight: 500; }}

        /* Member List */
        .member-list {{ display: flex; flex-direction: column; gap: var(--space-sm); }}
        .member-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: var(--space-md);
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .member-card:hover {{ border-color: var(--brand); }}
        .member-info {{ display: flex; align-items: center; gap: var(--space-sm); flex: 1; min-width: 0; }}
        .member-avatar {{
            width: 40px;
            height: 40px;
            min-width: 40px;
            background: linear-gradient(135deg, var(--brand) 0%, var(--brand-light) 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.85rem;
            color: white;
        }}
        .member-details {{ min-width: 0; }}
        .member-name {{ font-weight: 600; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .member-meta {{ color: var(--text-secondary); font-size: 0.75rem; }}
        .member-right {{ display: flex; align-items: center; gap: var(--space-sm); flex-shrink: 0; }}
        .member-credit {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--success);
            font-size: 0.85rem;
        }}

        /* Tier Badges */
        .tier-badge {{
            padding: 3px 8px;
            border-radius: var(--radius-sm);
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .tier-silver {{ background: #71717a20; color: #a1a1aa; }}
        .tier-gold {{ background: #fbbf2420; color: #fbbf24; }}
        .tier-platinum {{ background: #a855f720; color: #a855f7; }}

        /* Forms */
        .form-group {{ margin-bottom: var(--space-md); }}
        .form-label {{
            display: block;
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: var(--space-xs);
            color: var(--text-secondary);
        }}
        .form-input {{
            width: 100%;
            padding: var(--space-sm) var(--space-md);
            background: var(--bg-input);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
            font-size: 1rem;
            font-family: inherit;
            transition: border-color 0.2s;
        }}
        .form-input:focus {{ outline: none; border-color: var(--border-focus); }}
        .form-input::placeholder {{ color: var(--text-muted); }}
        .form-select {{
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='%23a1a1aa' viewBox='0 0 24 24'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
            background-size: 20px;
            padding-right: 40px;
        }}

        /* Buttons */
        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: var(--space-xs);
            padding: var(--space-sm) var(--space-lg);
            border-radius: var(--radius-sm);
            font-size: 0.9rem;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
            text-decoration: none;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, var(--brand) 0%, var(--brand-light) 100%);
            color: white;
        }}
        .btn-primary:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(232, 93, 39, 0.3); }}
        .btn-secondary {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--text-primary);
        }}
        .btn-secondary:hover {{ border-color: var(--brand); }}
        .btn-success {{ background: var(--success); color: white; }}
        .btn-danger {{ background: var(--danger); color: white; }}
        .btn-block {{ width: 100%; }}
        .btn-sm {{ padding: var(--space-xs) var(--space-sm); font-size: 0.8rem; }}

        /* Modal */
        .modal-overlay {{
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: flex-end;
            justify-content: center;
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s;
        }}
        .modal-overlay.active {{ opacity: 1; visibility: visible; }}
        @media (min-width: 600px) {{ .modal-overlay {{ align-items: center; }} }}
        .modal {{
            background: var(--bg-secondary);
            width: 100%;
            max-width: 500px;
            max-height: 90vh;
            overflow-y: auto;
            border-radius: var(--radius-lg) var(--radius-lg) 0 0;
            transform: translateY(100%);
            transition: transform 0.3s;
        }}
        .modal-overlay.active .modal {{ transform: translateY(0); }}
        @media (min-width: 600px) {{ .modal {{ border-radius: var(--radius-lg); }} }}
        .modal-header {{
            padding: var(--space-md);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .modal-title {{ font-weight: 700; font-size: 1.1rem; }}
        .modal-close {{
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: var(--text-secondary);
            line-height: 1;
        }}
        .modal-body {{ padding: var(--space-md); }}
        .modal-footer {{ padding: var(--space-md); border-top: 1px solid var(--border); display: flex; gap: var(--space-sm); }}

        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: var(--space-xl);
            color: var(--text-secondary);
        }}
        .empty-icon {{ font-size: 3rem; margin-bottom: var(--space-md); opacity: 0.5; }}
        .empty-text {{ font-size: 0.9rem; }}

        /* Loading */
        .loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            padding: var(--space-xl);
        }}
        .spinner {{
            width: 32px;
            height: 32px;
            border: 3px solid var(--border);
            border-top-color: var(--brand);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

        /* Toast */
        .toast-container {{
            position: fixed;
            top: var(--space-md);
            left: 50%;
            transform: translateX(-50%);
            z-index: 2000;
            display: flex;
            flex-direction: column;
            gap: var(--space-sm);
        }}
        .toast {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: var(--space-sm) var(--space-md);
            border-radius: var(--radius-sm);
            font-size: 0.85rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            animation: slideDown 0.3s ease;
        }}
        .toast-success {{ border-left: 3px solid var(--success); }}
        .toast-error {{ border-left: 3px solid var(--danger); }}
        @keyframes slideDown {{ from {{ opacity: 0; transform: translateY(-10px); }} }}

        /* Bottom Nav */
        .bottom-nav {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: space-around;
            padding: var(--space-xs) 0;
            padding-bottom: max(var(--space-xs), env(safe-area-inset-bottom));
            z-index: 100;
        }}
        .nav-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.65rem;
            cursor: pointer;
            padding: var(--space-xs) var(--space-sm);
            border-radius: var(--radius-sm);
            transition: all 0.2s;
            -webkit-tap-highlight-color: transparent;
        }}
        .nav-item.active {{ color: var(--brand); }}
        .nav-item:hover {{ color: var(--brand); }}
        .nav-icon {{ font-size: 1.25rem; }}

        /* Trade-in & Bonus Cards */
        .item-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: var(--space-md);
            margin-bottom: var(--space-sm);
        }}
        .item-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: var(--space-sm);
        }}
        .item-title {{ font-weight: 600; }}
        .item-meta {{ color: var(--text-secondary); font-size: 0.8rem; }}
        .item-amount {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 1.1rem;
        }}
        .amount-positive {{ color: var(--success); }}
        .amount-pending {{ color: var(--warning); }}

        /* Status Badges */
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 8px;
            border-radius: var(--radius-full);
            font-size: 0.7rem;
            font-weight: 600;
        }}
        .status-active {{ background: #00d68f20; color: var(--success); }}
        .status-pending {{ background: #ffb54720; color: var(--warning); }}
        .status-processing {{ background: #a855f720; color: var(--processing); }}
        .status-completed {{ background: #00cfe820; color: var(--info); }}

        /* Tier Cards */
        .tier-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
        }}
        .tier-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .tier-card-name {{
            font-weight: 600;
            font-size: 1.1rem;
        }}
        .tier-card-price {{
            color: var(--primary);
            font-weight: 600;
        }}
        .tier-card-details {{
            display: flex;
            gap: 16px;
            margin-bottom: 12px;
        }}
        .tier-stat {{
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
        .tier-stat strong {{
            color: var(--text-primary);
        }}
        .tier-card-benefits {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 12px;
        }}
        .benefit-tag {{
            background: rgba(232, 93, 39, 0.15);
            color: var(--primary);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        .tier-card-actions {{
            display: flex;
            gap: 8px;
            justify-content: flex-end;
            padding-top: 12px;
            border-top: 1px solid var(--border-color);
        }}
        .btn-danger {{
            background: #ef4444 !important;
            border-color: #ef4444 !important;
        }}
        .btn-danger:hover {{
            background: #dc2626 !important;
            border-color: #dc2626 !important;
        }}

        /* Checkbox Group */
        .checkbox-group {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .checkbox-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .checkbox-item input[type="checkbox"] {{
            width: 18px;
            height: 18px;
            accent-color: var(--primary);
        }}
        .checkbox-item label {{
            margin: 0;
            cursor: pointer;
        }}
        .inline-input {{
            width: 60px;
            padding: 4px 8px;
            margin-left: 8px;
        }}

        /* Settings */
        .settings-section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            margin-bottom: var(--space-md);
            overflow: hidden;
        }}
        .settings-header {{
            padding: var(--space-md);
            border-bottom: 1px solid var(--border);
            font-weight: 600;
        }}
        .settings-item {{
            padding: var(--space-md);
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }}
        .settings-item:last-child {{ border-bottom: none; }}
        .settings-label {{ font-size: 0.9rem; }}
        .settings-value {{ color: var(--text-secondary); font-size: 0.85rem; }}

        /* Category Grid */
        .category-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: var(--space-sm);
            margin-bottom: var(--space-md);
        }}
        .category-item {{
            background: var(--bg-card);
            border: 2px solid var(--border);
            border-radius: var(--radius-md);
            padding: var(--space-md);
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .category-item:hover {{ border-color: var(--brand); transform: translateY(-2px); }}
        .category-item.selected {{
            border-color: var(--brand);
            background: linear-gradient(135deg, rgba(232, 93, 39, 0.1) 0%, rgba(255, 122, 66, 0.1) 100%);
        }}
        .category-icon {{ font-size: 1.75rem; margin-bottom: var(--space-xs); }}
        .category-name {{ font-size: 0.8rem; font-weight: 600; }}

        /* Utility */
        .text-center {{ text-align: center; }}
        .text-success {{ color: var(--success); }}
        .text-warning {{ color: var(--warning); }}
        .text-muted {{ color: var(--text-muted); }}
        .mt-sm {{ margin-top: var(--space-sm); }}
        .mt-md {{ margin-top: var(--space-md); }}
        .mb-sm {{ margin-bottom: var(--space-sm); }}
        .mb-md {{ margin-bottom: var(--space-md); }}
        .flex {{ display: flex; }}
        .gap-sm {{ gap: var(--space-sm); }}
        .hidden {{ display: none !important; }}
    </style>
</head>
<body>
    <div id="toast-container" class="toast-container"></div>

    <header class="header">
        <div class="logo">
            <span class="logo-icon">🚀</span>
            <div>
                <div class="logo-text">TradeUp</div>
                <div class="logo-sub">by Cardflow Labs v1.7</div>
            </div>
        </div>
        <div class="header-actions">
            <span class="shop-badge">{shop.replace('.myshopify.com', '')}</span>
            <button class="icon-btn" onclick="toggleTheme()" title="Toggle theme">🌓</button>
        </div>
    </header>

    <!-- HOME PAGE -->
    <div id="page-home" class="page active">
        <div class="container">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="stat-members">--</div>
                    <div class="stat-label">Members</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-credit">--</div>
                    <div class="stat-label">Credit Issued</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-tradeins">--</div>
                    <div class="stat-label">Trade-Ins</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-bonuses">--</div>
                    <div class="stat-label">Bonuses</div>
                </div>
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Quick Actions</h2>
                </div>
                <div class="quick-actions">
                    <div class="action-btn" onclick="openModal('enroll-customer')">
                        <div class="action-icon">🔍</div>
                        <div class="action-label">Enroll Customer</div>
                    </div>
                    <div class="action-btn" onclick="openModal('new-tradein')">
                        <div class="action-icon">📦</div>
                        <div class="action-label">New Trade-In</div>
                    </div>
                    <div class="action-btn" onclick="navigateTo('bonuses')">
                        <div class="action-icon">💰</div>
                        <div class="action-label">Bonuses</div>
                    </div>
                    <div class="action-btn" onclick="navigateTo('settings')">
                        <div class="action-icon">⚙️</div>
                        <div class="action-label">Settings</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Recent Members</h2>
                    <span class="badge" id="new-members-badge">--</span>
                </div>
                <div class="member-list" id="recent-members">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>
        </div>
    </div>

    <!-- MEMBERS PAGE -->
    <div id="page-members" class="page">
        <div class="container">
            <div class="section-header">
                <h2 class="section-title">All Members</h2>
                <button class="btn btn-primary btn-sm" onclick="openModal('enroll-customer')">+ Enroll</button>
            </div>
            <div class="form-group">
                <input type="text" class="form-input" id="member-search" placeholder="Search by name or email..." oninput="filterMembers(this.value)">
            </div>
            <div class="member-list" id="all-members">
                <div class="loading"><div class="spinner"></div></div>
            </div>
        </div>
    </div>

    <!-- TRADE-INS PAGE -->
    <div id="page-tradeins" class="page">
        <div class="container">
            <div class="section-header">
                <h2 class="section-title">Trade-Ins</h2>
                <button class="btn btn-primary btn-sm" onclick="openModal('new-tradein')">+ New</button>
            </div>
            <div id="tradein-list">
                <div class="loading"><div class="spinner"></div></div>
            </div>
        </div>
    </div>

    <!-- BONUSES PAGE -->
    <div id="page-bonuses" class="page">
        <div class="container">
            <div class="section-header">
                <h2 class="section-title">Pending Bonuses</h2>
            </div>
            <div id="bonus-list">
                <div class="loading"><div class="spinner"></div></div>
            </div>
        </div>
    </div>

    <!-- SETTINGS PAGE -->
    <div id="page-settings" class="page">
        <div class="container">
            <h2 class="section-title mb-md">Settings</h2>

            <div class="settings-section">
                <div class="settings-header">Membership Tiers</div>
                <div id="tiers-list">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>

            <div class="settings-section">
                <div class="settings-header">Branding</div>
                <div id="branding-settings">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>

            <div class="settings-section">
                <div class="settings-header">Features</div>
                <div id="feature-settings" class="checkbox-group" style="padding: 12px 0;">
                    <div class="checkbox-item">
                        <input type="checkbox" id="feature-points" onchange="toggleFeature('points_enabled', this.checked)">
                        <label for="feature-points">Points Program</label>
                    </div>
                    <div class="checkbox-item">
                        <input type="checkbox" id="feature-referrals" onchange="toggleFeature('referrals_enabled', this.checked)">
                        <label for="feature-referrals">Referral Program</label>
                    </div>
                    <div class="checkbox-item">
                        <input type="checkbox" id="feature-self-signup" onchange="toggleFeature('self_signup_enabled', this.checked)">
                        <label for="feature-self-signup">Self Signup (Members can sign up themselves)</label>
                    </div>
                </div>
            </div>

            <div class="settings-section">
                <div class="settings-header">Shop Info</div>
                <div class="settings-item">
                    <span class="settings-label">Shop Domain</span>
                    <span class="settings-value">{shop}</span>
                </div>
                <div class="settings-item">
                    <span class="settings-label">Plan</span>
                    <span class="settings-value">Pro (Unlimited)</span>
                </div>
            </div>

            <div class="settings-section">
                <div class="settings-header">App Info</div>
                <div class="settings-item">
                    <span class="settings-label">Version</span>
                    <span class="settings-value">1.0.0</span>
                </div>
                <div class="settings-item">
                    <span class="settings-label">Support</span>
                    <span class="settings-value">support@cardflowlabs.com</span>
                </div>
            </div>
        </div>
    </div>

    <!-- ENROLL CUSTOMER MODAL -->
    <div id="modal-enroll-customer" class="modal-overlay" onclick="closeModalOnOverlay(event)">
        <div class="modal" style="max-width: 500px;">
            <div class="modal-header">
                <span class="modal-title">Enroll Shopify Customer</span>
                <button class="modal-close" onclick="closeModal('enroll-customer')">&times;</button>
            </div>
            <div class="modal-body">
                <!-- Search Section -->
                <div class="form-group">
                    <label class="form-label">Search Shopify Customers</label>
                    <input type="text" class="form-input" id="customer-search-input"
                           placeholder="Search by name, email, phone, or ORB#..."
                           oninput="debounceCustomerSearch(this.value)">
                    <small class="text-muted" style="display:block;margin-top:4px;">
                        Search your Shopify customers to enroll them in Quick Flip
                    </small>
                </div>

                <!-- Search Results -->
                <div id="customer-search-results" class="customer-results" style="max-height: 250px; overflow-y: auto; margin: 12px 0;">
                    <div class="text-muted text-center" style="padding: 20px;">
                        Enter a search term to find customers
                    </div>
                </div>

                <!-- Enrollment Form (hidden until customer selected) -->
                <div id="enroll-form-section" style="display: none; border-top: 1px solid var(--border-color); padding-top: 16px; margin-top: 16px;">
                    <div class="selected-customer-card" style="background: var(--bg-secondary); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div id="selected-customer-name" style="font-weight: 600;"></div>
                                <div id="selected-customer-email" class="text-muted" style="font-size: 13px;"></div>
                                <div id="selected-customer-orb" class="text-muted" style="font-size: 12px;"></div>
                            </div>
                            <button class="btn btn-sm" onclick="clearSelectedCustomer()" style="padding: 4px 8px;">✕</button>
                        </div>
                    </div>
                    <input type="hidden" id="selected-customer-id">
                    <div class="form-group">
                        <label class="form-label">Membership Tier</label>
                        <select class="form-input form-select" id="enroll-tier-select">
                            <option value="">Default (Lowest Tier)</option>
                        </select>
                    </div>
                    <button class="btn btn-primary btn-block" onclick="submitEnrollment()">
                        Enroll Customer
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- NEW TRADE-IN MODAL -->
    <div id="modal-new-tradein" class="modal-overlay" onclick="closeModalOnOverlay(event)">
        <div class="modal">
            <div class="modal-header">
                <span class="modal-title">New Trade-In</span>
                <button class="modal-close" onclick="closeModal('new-tradein')">&times;</button>
            </div>
            <div class="modal-body">
                <form id="new-tradein-form" onsubmit="submitNewTradeIn(event)">
                    <div class="form-group">
                        <label class="form-label">Member *</label>
                        <select class="form-input form-select" name="member_id" id="tradein-member-select" required>
                            <option value="">Select member...</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Category *</label>
                        <input type="hidden" name="category" id="tradein-category" value="other">
                        <div class="category-grid" id="category-grid">
                            <div class="category-item" data-category="sports" onclick="selectCategory('sports')">
                                <div class="category-icon">🏈</div>
                                <div class="category-name">Sports</div>
                            </div>
                            <div class="category-item" data-category="pokemon" onclick="selectCategory('pokemon')">
                                <div class="category-icon">⚡</div>
                                <div class="category-name">Pokemon</div>
                            </div>
                            <div class="category-item" data-category="magic" onclick="selectCategory('magic')">
                                <div class="category-icon">🔮</div>
                                <div class="category-name">Magic</div>
                            </div>
                            <div class="category-item" data-category="riftbound" onclick="selectCategory('riftbound')">
                                <div class="category-icon">🌀</div>
                                <div class="category-name">Riftbound</div>
                            </div>
                            <div class="category-item" data-category="tcg_other" onclick="selectCategory('tcg_other')">
                                <div class="category-icon">🎴</div>
                                <div class="category-name">TCG Other</div>
                            </div>
                            <div class="category-item selected" data-category="other" onclick="selectCategory('other')">
                                <div class="category-icon">📦</div>
                                <div class="category-name">Other</div>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Item Description *</label>
                        <input type="text" class="form-input" name="description" required placeholder="Pokemon Charizard VMAX">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Trade-In Value *</label>
                        <input type="number" class="form-input" name="value" required step="0.01" min="0" placeholder="50.00">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Notes</label>
                        <input type="text" class="form-input" name="notes" placeholder="Condition, grade, etc.">
                    </div>
                    <button type="submit" class="btn btn-primary btn-block">Create Trade-In</button>
                </form>
            </div>
        </div>
    </div>

    <!-- MEMBER DETAIL MODAL -->
    <div id="modal-member-detail" class="modal-overlay" onclick="closeModalOnOverlay(event)">
        <div class="modal">
            <div class="modal-header">
                <span class="modal-title">Member Details</span>
                <button class="modal-close" onclick="closeModal('member-detail')">&times;</button>
            </div>
            <div class="modal-body" id="member-detail-content">
                <div class="loading"><div class="spinner"></div></div>
            </div>
        </div>
    </div>

    <!-- TIER EDIT MODAL -->
    <div id="modal-tier-edit" class="modal-overlay" onclick="closeModalOnOverlay(event)">
        <div class="modal" style="max-width: 500px;">
            <div class="modal-header">
                <span class="modal-title" id="tier-modal-title">Create New Tier</span>
                <button class="modal-close" onclick="closeTierModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="tier-edit-form" onsubmit="saveTier(event)">
                    <div class="form-group">
                        <label class="form-label">Tier Name *</label>
                        <input type="text" class="form-input" id="tier-name" required
                               placeholder="e.g., Silver, Gold, Platinum">
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                        <div class="form-group">
                            <label class="form-label">Monthly Price *</label>
                            <input type="number" class="form-input" id="tier-monthly-price" required
                                   min="0" step="0.01" placeholder="0.00">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Bonus Rate % *</label>
                            <input type="number" class="form-input" id="tier-bonus-rate" required
                                   min="0" max="100" step="1" placeholder="10">
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Quick Flip Window (Days)</label>
                        <input type="number" class="form-input" id="tier-qf-days"
                               min="1" max="30" value="7">
                        <small class="text-muted" style="display:block;margin-top:4px;">
                            How many days members have to flip items for bonus
                        </small>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Benefits</label>
                        <div class="checkbox-group">
                            <div class="checkbox-item">
                                <input type="checkbox" id="benefit-discount">
                                <label for="benefit-discount">Store Discount</label>
                                <input type="number" class="form-input inline-input" id="benefit-discount-value"
                                       min="1" max="50" value="5" placeholder="%">
                                <span class="text-muted">%</span>
                            </div>
                            <div class="checkbox-item">
                                <input type="checkbox" id="benefit-early-access">
                                <label for="benefit-early-access">Early Access to New Products</label>
                            </div>
                            <div class="checkbox-item">
                                <input type="checkbox" id="benefit-free-shipping">
                                <label for="benefit-free-shipping">Free Shipping</label>
                            </div>
                            <div class="checkbox-item">
                                <input type="checkbox" id="benefit-events">
                                <label for="benefit-events">Event Access</label>
                            </div>
                            <div class="checkbox-item">
                                <input type="checkbox" id="benefit-vip">
                                <label for="benefit-vip">VIP Perks</label>
                            </div>
                        </div>
                    </div>

                    <button type="submit" class="btn btn-primary btn-block">Save Tier</button>
                </form>
            </div>
        </div>
    </div>

    <!-- BOTTOM NAV -->
    <nav class="bottom-nav">
        <a class="nav-item active" data-page="home" onclick="navigateTo('home')">
            <span class="nav-icon">🏠</span>
            <span>Home</span>
        </a>
        <a class="nav-item" data-page="members" onclick="navigateTo('members')">
            <span class="nav-icon">👥</span>
            <span>Members</span>
        </a>
        <a class="nav-item" data-page="tradeins" onclick="navigateTo('tradeins')">
            <span class="nav-icon">📦</span>
            <span>Trade-Ins</span>
        </a>
        <a class="nav-item" data-page="bonuses" onclick="navigateTo('bonuses')">
            <span class="nav-icon">💰</span>
            <span>Bonuses</span>
        </a>
        <a class="nav-item" data-page="settings" onclick="navigateTo('settings')">
            <span class="nav-icon">⚙️</span>
            <span>Settings</span>
        </a>
    </nav>

    <script>
        // App Bridge initialization (optional - works embedded in Shopify)
        var app = null;
        try {{
            var AppBridge = window['app-bridge'];
            if (AppBridge && AppBridge.default) {{
                var createApp = AppBridge.default;
                app = createApp({{ apiKey: '{api_key}', host: '{host}' }});
            }}
        }} catch (e) {{ console.log('App Bridge not available, running standalone'); }}

        // State (using var to avoid temporal dead zone in embedded contexts)
        var currentPage = 'home';
        var membersData = [];
        var tiersData = [];
        const API_BASE = '{app_url}/api';

        // Debug: Confirm script execution
        console.log('[TradeUp v1.7] Script loaded, API_BASE:', API_BASE);

        // Theme toggle
        function toggleTheme() {{
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            localStorage.setItem('tradeup-theme', next);
        }}

        // Load saved theme
        const savedTheme = localStorage.getItem('tradeup-theme');
        if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);

        // Navigation
        function navigateTo(page) {{
            currentPage = page;
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById('page-' + page).classList.add('active');
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.querySelector('[data-page="' + page + '"]').classList.add('active');

            // Load page data
            if (page === 'members') loadAllMembers();
            if (page === 'tradeins') loadTradeIns();
            if (page === 'bonuses') loadBonuses();
            if (page === 'settings') loadSettings();
        }}

        // Modal functions
        function openModal(name) {{
            document.getElementById('modal-' + name).classList.add('active');
            document.body.style.overflow = 'hidden';
            if (name === 'add-member') loadTierOptions();
            if (name === 'new-tradein') loadMemberOptions();
        }}

        function closeModal(name) {{
            document.getElementById('modal-' + name).classList.remove('active');
            document.body.style.overflow = '';
        }}

        function closeModalOnOverlay(e) {{
            if (e.target.classList.contains('modal-overlay')) {{
                e.target.classList.remove('active');
                document.body.style.overflow = '';
            }}
        }}

        // Toast notifications
        function showToast(message, type = 'success') {{
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = 'toast toast-' + type;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }}

        // API helpers - using XMLHttpRequest (fetch doesn't work in Shopify iframes)
        function apiGet(endpoint) {{
            const url = API_BASE + endpoint;
            console.log('[TradeUp v1.7] API GET:', url);

            return new Promise((resolve, reject) => {{
                const xhr = new XMLHttpRequest();
                xhr.open('GET', url, true);
                xhr.setRequestHeader('X-Tenant-ID', '1');

                xhr.onreadystatechange = function() {{
                    if (xhr.readyState === 4) {{
                        if (xhr.status === 200) {{
                            try {{
                                const data = JSON.parse(xhr.responseText);
                                console.log('[TradeUp v1.7] API GET success:', endpoint);
                                resolve(data);
                            }} catch (e) {{
                                console.error('[TradeUp v1.7] JSON parse error:', e);
                                reject(e);
                            }}
                        }} else {{
                            console.error('[TradeUp v1.7] API GET failed:', xhr.status);
                            reject(new Error('API request failed: ' + xhr.status));
                        }}
                    }}
                }};

                xhr.onerror = function() {{
                    console.error('[TradeUp v1.7] XHR network error');
                    reject(new Error('Network error'));
                }};

                xhr.send();
            }});
        }}

        function apiPost(endpoint, data) {{
            const url = API_BASE + endpoint;
            console.log('[TradeUp v1.7] API POST:', url);

            return new Promise((resolve, reject) => {{
                const xhr = new XMLHttpRequest();
                xhr.open('POST', url, true);
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.setRequestHeader('X-Tenant-ID', '1');

                xhr.onreadystatechange = function() {{
                    if (xhr.readyState === 4) {{
                        try {{
                            const json = JSON.parse(xhr.responseText);
                            if (xhr.status >= 200 && xhr.status < 300) {{
                                console.log('[TradeUp v1.7] API POST success:', endpoint);
                                resolve(json);
                            }} else {{
                                console.error('[TradeUp v1.7] API POST failed:', xhr.status, json);
                                reject(new Error(json.error || 'API request failed'));
                            }}
                        }} catch (e) {{
                            console.error('[TradeUp v1.7] JSON parse error:', e);
                            reject(e);
                        }}
                    }}
                }};

                xhr.onerror = function() {{
                    console.error('[TradeUp v1.7] XHR network error');
                    reject(new Error('Network error'));
                }};

                xhr.send(JSON.stringify(data));
            }});
        }}

        // Format helpers
        function formatCurrency(amount) {{
            return '$' + Number(amount || 0).toLocaleString('en-US', {{ minimumFractionDigits: 0, maximumFractionDigits: 0 }});
        }}

        function formatDate(dateStr) {{
            if (!dateStr) return '';
            const d = new Date(dateStr);
            return d.toLocaleDateString('en-US', {{ month: 'short', year: 'numeric' }});
        }}

        function getInitials(name) {{
            if (!name) return '??';
            return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
        }}

        function getTierClass(tierName) {{
            if (!tierName) return '';
            const name = tierName.toLowerCase();
            if (name.includes('plat')) return 'tier-platinum';
            if (name.includes('gold')) return 'tier-gold';
            return 'tier-silver';
        }}

        // Load dashboard stats - using XHR as fallback for debugging
        function loadDashboardStats() {{
            console.log('[TradeUp v1.7] loadDashboardStats() called');
            const url = API_BASE + '/dashboard/stats';
            console.log('[TradeUp v1.7] Using XHR for:', url);

            const xhr = new XMLHttpRequest();
            xhr.open('GET', url, true);
            xhr.setRequestHeader('X-Tenant-ID', '1');

            xhr.onreadystatechange = function() {{
                console.log('[TradeUp v1.7] XHR readyState:', xhr.readyState);
                if (xhr.readyState === 4) {{
                    console.log('[TradeUp v1.7] XHR status:', xhr.status);
                    if (xhr.status === 200) {{
                        try {{
                            const stats = JSON.parse(xhr.responseText);
                            console.log('[TradeUp v1.7] Stats loaded:', stats);
                            document.getElementById('stat-members').textContent = stats.members?.total || 0;
                            document.getElementById('stat-credit').textContent = formatCurrency(stats.bonuses_this_month?.total || 0);
                            document.getElementById('stat-tradeins').textContent = stats.trade_ins_this_month || 0;
                            document.getElementById('stat-bonuses').textContent = formatCurrency(stats.bonuses_this_month?.total || 0);
                            console.log('[TradeUp v1.7] Stats applied to DOM!');
                        }} catch (e) {{
                            console.error('[TradeUp v1.7] JSON parse error:', e);
                        }}
                    }} else {{
                        console.error('[TradeUp v1.7] XHR failed with status:', xhr.status);
                    }}
                }}
            }};

            xhr.onerror = function() {{
                console.error('[TradeUp v1.7] XHR network error');
            }};

            console.log('[TradeUp v1.7] Sending XHR...');
            xhr.send();
        }}

        // Load recent members
        async function loadRecentMembers() {{
            console.log('[TradeUp] loadRecentMembers() called');
            try {{
                const data = await apiGet('/members?per_page=5');
                membersData = data.members || [];

                const container = document.getElementById('recent-members');
                if (!membersData.length) {{
                    container.innerHTML = '<div class="empty-state"><div class="empty-icon">👥</div><div class="empty-text">No members yet</div><button class="btn btn-primary btn-sm mt-md" onclick="openModal(\\'add-member\\')">Add First Member</button></div>';
                    document.getElementById('new-members-badge').textContent = '0 members';
                    return;
                }}

                document.getElementById('new-members-badge').textContent = data.total + ' total';
                container.innerHTML = membersData.map(m => memberCardHTML(m)).join('');
            }} catch (e) {{
                console.error('Failed to load members:', e);
                document.getElementById('recent-members').innerHTML = '<div class="empty-state text-muted">Failed to load members</div>';
            }}
        }}

        // Load all members
        async function loadAllMembers() {{
            try {{
                const data = await apiGet('/members?per_page=100');
                membersData = data.members || [];

                const container = document.getElementById('all-members');
                if (!membersData.length) {{
                    container.innerHTML = '<div class="empty-state"><div class="empty-icon">👥</div><div class="empty-text">No members yet</div></div>';
                    return;
                }}

                container.innerHTML = membersData.map(m => memberCardHTML(m)).join('');
            }} catch (e) {{
                console.error('Failed to load members:', e);
            }}
        }}

        function memberCardHTML(m) {{
            const tierName = m.tier?.name || 'Silver';
            return `<div class="member-card" onclick="showMemberDetail(${{m.id}})">
                <div class="member-info">
                    <div class="member-avatar">${{getInitials(m.name)}}</div>
                    <div class="member-details">
                        <div class="member-name">${{m.name || m.email}}</div>
                        <div class="member-meta">${{m.member_number}} · ${{formatDate(m.created_at)}}</div>
                    </div>
                </div>
                <div class="member-right">
                    <span class="tier-badge ${{getTierClass(tierName)}}">${{tierName}}</span>
                    <span class="member-credit">${{formatCurrency(m.stats?.total_bonus_earned)}}</span>
                </div>
            </div>`;
        }}

        function filterMembers(query) {{
            const q = query.toLowerCase();
            const filtered = membersData.filter(m =>
                (m.name && m.name.toLowerCase().includes(q)) ||
                (m.email && m.email.toLowerCase().includes(q)) ||
                (m.member_number && m.member_number.toLowerCase().includes(q))
            );
            document.getElementById('all-members').innerHTML = filtered.map(m => memberCardHTML(m)).join('');
        }}

        // Show member detail
        async function showMemberDetail(id) {{
            openModal('member-detail');
            const container = document.getElementById('member-detail-content');
            container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

            try {{
                const m = await apiGet('/members/' + id);
                container.innerHTML = `
                    <div class="text-center mb-md">
                        <div class="member-avatar" style="width:64px;height:64px;font-size:1.25rem;margin:0 auto">${{getInitials(m.name)}}</div>
                        <h3 class="mt-sm">${{m.name || 'No Name'}}</h3>
                        <div class="text-muted">${{m.member_number}}</div>
                        <span class="tier-badge ${{getTierClass(m.tier?.name)}} mt-sm">${{m.tier?.name || 'Silver'}}</span>
                    </div>
                    <div class="settings-section">
                        <div class="settings-item"><span>Email</span><span class="text-muted">${{m.email}}</span></div>
                        <div class="settings-item"><span>Phone</span><span class="text-muted">${{m.phone || '-'}}</span></div>
                        <div class="settings-item"><span>Status</span><span class="status-badge status-${{m.status}}">${{m.status}}</span></div>
                        <div class="settings-item"><span>Member Since</span><span class="text-muted">${{formatDate(m.created_at)}}</span></div>
                    </div>
                    <div class="stats-grid mt-md">
                        <div class="stat-card"><div class="stat-value" style="font-size:1.5rem">${{m.stats?.total_trade_ins || 0}}</div><div class="stat-label">Trade-Ins</div></div>
                        <div class="stat-card"><div class="stat-value" style="font-size:1.5rem">${{formatCurrency(m.stats?.total_bonus_earned)}}</div><div class="stat-label">Earned</div></div>
                    </div>
                `;
            }} catch (e) {{
                container.innerHTML = '<div class="empty-state text-muted">Failed to load member</div>';
            }}
        }}

        // Category icons mapping
        const CATEGORY_ICONS = {{
            'sports': '🏈',
            'pokemon': '⚡',
            'magic': '🔮',
            'riftbound': '🌀',
            'tcg_other': '🎴',
            'other': '📦'
        }};

        function getCategoryIcon(category) {{
            return CATEGORY_ICONS[category] || CATEGORY_ICONS['other'];
        }}

        // Load trade-ins
        async function loadTradeIns() {{
            try {{
                const data = await apiGet('/trade-ins?per_page=20');
                const items = data.batches || [];

                const container = document.getElementById('tradein-list');
                if (!items.length) {{
                    container.innerHTML = '<div class="empty-state"><div class="empty-icon">📦</div><div class="empty-text">No trade-ins yet</div><button class="btn btn-primary btn-sm mt-md" onclick="openModal(\\'new-tradein\\')">Create Trade-In</button></div>';
                    return;
                }}

                container.innerHTML = items.map(t => `
                    <div class="item-card">
                        <div class="item-header">
                            <div>
                                <div class="item-title">${{getCategoryIcon(t.category)}} ${{t.member_name || t.batch_reference}}</div>
                                <div class="item-meta">${{formatDate(t.created_at)}} · ${{t.batch_reference}}</div>
                            </div>
                            <div class="item-amount amount-positive">${{formatCurrency(t.total_trade_value)}}</div>
                        </div>
                        <div class="flex gap-sm">
                            <span class="status-badge status-${{t.status}}">${{t.status}}</span>
                            <span class="text-muted">${{t.total_items || 0}} items</span>
                        </div>
                    </div>
                `).join('');
            }} catch (e) {{
                document.getElementById('tradein-list').innerHTML = '<div class="empty-state"><div class="empty-icon">📦</div><div class="empty-text">No trade-ins yet</div></div>';
            }}
        }}

        // Load bonuses
        async function loadBonuses() {{
            try {{
                const data = await apiGet('/bonuses?status=pending&per_page=20');
                const items = data.transactions || [];

                const container = document.getElementById('bonus-list');
                if (!items.length) {{
                    container.innerHTML = '<div class="empty-state"><div class="empty-icon">💰</div><div class="empty-text">No pending bonuses</div></div>';
                    return;
                }}

                container.innerHTML = items.map(b => `
                    <div class="item-card">
                        <div class="item-header">
                            <div>
                                <div class="item-title">${{b.member?.name || 'Member'}}</div>
                                <div class="item-meta">${{b.description || 'Quick Flip Bonus'}}</div>
                            </div>
                            <div class="item-amount amount-pending">${{formatCurrency(b.bonus_amount)}}</div>
                        </div>
                        <button class="btn btn-success btn-sm" onclick="processBonus(${{b.id}})">Process</button>
                    </div>
                `).join('');
            }} catch (e) {{
                document.getElementById('bonus-list').innerHTML = '<div class="empty-state"><div class="empty-icon">💰</div><div class="empty-text">No pending bonuses</div></div>';
            }}
        }}

        async function processBonus(id) {{
            try {{
                await apiPost('/bonuses/' + id + '/process', {{}});
                showToast('Bonus processed!');
                loadBonuses();
                loadDashboardStats();
            }} catch (e) {{
                showToast('Failed to process bonus', 'error');
            }}
        }}

        // Global branding data
        var brandingData = {{}};
        var featuresData = {{}};

        // Load settings (tiers, branding, features)
        async function loadSettings() {{
            // Load tiers
            loadTiers();
            // Load branding
            loadBranding();
            // Load features
            loadFeatures();
        }}

        // Load tiers
        async function loadTiers() {{
            try {{
                const data = await apiGet('/members/tiers');
                tiersData = data.tiers || [];

                const container = document.getElementById('tiers-list');
                if (!tiersData.length) {{
                    container.innerHTML = `
                        <div class="settings-item" style="justify-content: center;">
                            <span class="text-muted">No tiers configured</span>
                        </div>
                        <button class="btn btn-primary btn-block mt-md" onclick="openTierModal()">
                            + Add First Tier
                        </button>`;
                    return;
                }}

                container.innerHTML = tiersData.map((t, i) => `
                    <div class="tier-card" data-tier-id="${{t.id}}">
                        <div class="tier-card-header">
                            <div class="tier-card-name">${{t.name}}</div>
                            <div class="tier-card-price">${{formatCurrency(t.monthly_price)}}/mo</div>
                        </div>
                        <div class="tier-card-details">
                            <span class="tier-stat"><strong>${{(t.bonus_rate * 100).toFixed(0)}}%</strong> bonus</span>
                            <span class="tier-stat"><strong>${{t.quick_flip_days}}</strong> day window</span>
                        </div>
                        ${{t.benefits && Object.keys(t.benefits).length > 0 ? `
                            <div class="tier-card-benefits">
                                ${{Object.entries(t.benefits).map(([k, v]) =>
                                    v ? `<span class="benefit-tag">${{formatBenefitName(k)}}</span>` : ''
                                ).join('')}}
                            </div>
                        ` : ''}}
                        <div class="tier-card-actions">
                            <button class="btn btn-sm" onclick="openTierModal(${{t.id}})">Edit</button>
                            <button class="btn btn-sm btn-danger" onclick="deleteTier(${{t.id}}, '${{t.name}}')">Delete</button>
                        </div>
                    </div>
                `).join('') + `
                    <button class="btn btn-primary btn-block mt-md" onclick="openTierModal()">
                        + Add New Tier
                    </button>`;
            }} catch (e) {{
                console.error('Failed to load tiers:', e);
                document.getElementById('tiers-list').innerHTML = '<div class="text-muted">Failed to load tiers</div>';
            }}
        }}

        function formatBenefitName(key) {{
            const names = {{
                'discount': 'Discount',
                'early_access': 'Early Access',
                'free_shipping': 'Free Shipping',
                'events': 'Events',
                'vip_perks': 'VIP Perks'
            }};
            return names[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }}

        // Tier CRUD functions
        let editingTierId = null;

        function openTierModal(tierId = null) {{
            editingTierId = tierId;
            const modal = document.getElementById('modal-tier-edit');
            const title = document.getElementById('tier-modal-title');
            const form = document.getElementById('tier-edit-form');

            if (tierId) {{
                title.textContent = 'Edit Tier';
                const tier = tiersData.find(t => t.id === tierId);
                if (tier) {{
                    document.getElementById('tier-name').value = tier.name;
                    document.getElementById('tier-monthly-price').value = tier.monthly_price;
                    document.getElementById('tier-bonus-rate').value = (tier.bonus_rate * 100).toFixed(0);
                    document.getElementById('tier-qf-days').value = tier.quick_flip_days;
                    // Set benefit checkboxes
                    const benefits = tier.benefits || {{}};
                    document.getElementById('benefit-discount').checked = !!benefits.discount;
                    document.getElementById('benefit-early-access').checked = !!benefits.early_access;
                    document.getElementById('benefit-free-shipping').checked = !!benefits.free_shipping;
                    document.getElementById('benefit-events').checked = !!benefits.events;
                    document.getElementById('benefit-vip').checked = !!benefits.vip_perks;
                    if (benefits.discount && typeof benefits.discount === 'number') {{
                        document.getElementById('benefit-discount-value').value = benefits.discount;
                    }}
                }}
            }} else {{
                title.textContent = 'Create New Tier';
                form.reset();
                document.getElementById('tier-bonus-rate').value = '10';
                document.getElementById('tier-qf-days').value = '7';
            }}

            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }}

        function closeTierModal() {{
            document.getElementById('modal-tier-edit').classList.remove('active');
            document.body.style.overflow = '';
            editingTierId = null;
        }}

        async function saveTier(e) {{
            e.preventDefault();

            const benefits = {{}};
            if (document.getElementById('benefit-discount').checked) {{
                benefits.discount = parseInt(document.getElementById('benefit-discount-value').value) || 5;
            }}
            if (document.getElementById('benefit-early-access').checked) benefits.early_access = true;
            if (document.getElementById('benefit-free-shipping').checked) benefits.free_shipping = true;
            if (document.getElementById('benefit-events').checked) benefits.events = true;
            if (document.getElementById('benefit-vip').checked) benefits.vip_perks = true;

            const data = {{
                name: document.getElementById('tier-name').value,
                monthly_price: parseFloat(document.getElementById('tier-monthly-price').value),
                bonus_rate: parseFloat(document.getElementById('tier-bonus-rate').value) / 100,
                quick_flip_days: parseInt(document.getElementById('tier-qf-days').value),
                benefits: benefits
            }};

            try {{
                if (editingTierId) {{
                    await apiPut('/members/tiers/' + editingTierId, data);
                    showToast('Tier updated!');
                }} else {{
                    await apiPost('/members/tiers', data);
                    showToast('Tier created!');
                }}
                closeTierModal();
                loadSettings();
            }} catch (e) {{
                showToast(e.message || 'Failed to save tier', 'error');
            }}
        }}

        async function deleteTier(tierId, tierName) {{
            if (!confirm(`Delete tier "${{tierName}}"? This cannot be undone.`)) return;

            try {{
                await apiDelete('/members/tiers/' + tierId);
                showToast('Tier deleted!');
                loadSettings();
            }} catch (e) {{
                showToast(e.message || 'Failed to delete tier', 'error');
            }}
        }}

        // API DELETE helper
        function apiDelete(endpoint) {{
            const url = API_BASE + endpoint;
            return new Promise((resolve, reject) => {{
                const xhr = new XMLHttpRequest();
                xhr.open('DELETE', url, true);
                xhr.setRequestHeader('X-Tenant-ID', '1');
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.onreadystatechange = function() {{
                    if (xhr.readyState === 4) {{
                        if (xhr.status >= 200 && xhr.status < 300) {{
                            try {{
                                resolve(JSON.parse(xhr.responseText));
                            }} catch (e) {{
                                resolve({{}});
                            }}
                        }} else {{
                            try {{
                                const err = JSON.parse(xhr.responseText);
                                reject(new Error(err.error || 'Request failed'));
                            }} catch (e) {{
                                reject(new Error('Request failed'));
                            }}
                        }}
                    }}
                }};
                xhr.onerror = () => reject(new Error('Network error'));
                xhr.send();
            }});
        }}

        // API PUT helper
        function apiPut(endpoint, data) {{
            const url = API_BASE + endpoint;
            return new Promise((resolve, reject) => {{
                const xhr = new XMLHttpRequest();
                xhr.open('PUT', url, true);
                xhr.setRequestHeader('X-Tenant-ID', '1');
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.onreadystatechange = function() {{
                    if (xhr.readyState === 4) {{
                        if (xhr.status >= 200 && xhr.status < 300) {{
                            try {{
                                resolve(JSON.parse(xhr.responseText));
                            }} catch (e) {{
                                resolve({{}});
                            }}
                        }} else {{
                            try {{
                                const err = JSON.parse(xhr.responseText);
                                reject(new Error(err.error || 'Request failed'));
                            }} catch (e) {{
                                reject(new Error('Request failed'));
                            }}
                        }}
                    }}
                }};
                xhr.onerror = () => reject(new Error('Network error'));
                xhr.send(JSON.stringify(data));
            }});
        }}

        // API PATCH helper
        function apiPatch(endpoint, data) {{
            const url = API_BASE + endpoint;
            return new Promise((resolve, reject) => {{
                const xhr = new XMLHttpRequest();
                xhr.open('PATCH', url, true);
                xhr.setRequestHeader('X-Tenant-ID', '1');
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.onreadystatechange = function() {{
                    if (xhr.readyState === 4) {{
                        if (xhr.status >= 200 && xhr.status < 300) {{
                            try {{
                                resolve(JSON.parse(xhr.responseText));
                            }} catch (e) {{
                                resolve({{}});
                            }}
                        }} else {{
                            try {{
                                const err = JSON.parse(xhr.responseText);
                                reject(new Error(err.error || 'Request failed'));
                            }} catch (e) {{
                                reject(new Error('Request failed'));
                            }}
                        }}
                    }}
                }};
                xhr.onerror = () => reject(new Error('Network error'));
                xhr.send(JSON.stringify(data));
            }});
        }}

        // Load branding settings
        async function loadBranding() {{
            try {{
                const data = await apiGet('/settings/branding');
                brandingData = data.branding || {{}};

                const container = document.getElementById('branding-settings');
                container.innerHTML = `
                    <div class="form-group">
                        <label class="form-label">App Name</label>
                        <input type="text" class="form-input" id="branding-app-name"
                               value="${{brandingData.app_name || 'Quick Flip'}}"
                               placeholder="Your app name" onchange="updateBranding('app_name', this.value)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Tagline</label>
                        <input type="text" class="form-input" id="branding-tagline"
                               value="${{brandingData.tagline || 'Trade-in Loyalty Program'}}"
                               placeholder="Short tagline" onchange="updateBranding('tagline', this.value)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Primary Color</label>
                        <div style="display: flex; gap: 12px; align-items: center;">
                            <input type="color" id="branding-primary-color"
                                   value="${{brandingData.colors?.primary || '#e85d27'}}"
                                   onchange="updateBrandingColor('primary', this.value)"
                                   style="width: 60px; height: 40px; border: none; cursor: pointer;">
                            <input type="text" class="form-input" id="branding-primary-hex"
                                   value="${{brandingData.colors?.primary || '#e85d27'}}"
                                   placeholder="#e85d27" style="flex: 1;"
                                   onchange="updateBrandingColor('primary', this.value)">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Style</label>
                        <select class="form-input form-select" id="branding-style"
                                onchange="updateBranding('style', this.value)">
                            <option value="glass" ${{brandingData.style === 'glass' ? 'selected' : ''}}>Glass (Modern)</option>
                            <option value="solid" ${{brandingData.style === 'solid' ? 'selected' : ''}}>Solid (Classic)</option>
                            <option value="minimal" ${{brandingData.style === 'minimal' ? 'selected' : ''}}>Minimal (Clean)</option>
                        </select>
                    </div>
                `;
            }} catch (e) {{
                console.error('Failed to load branding:', e);
                document.getElementById('branding-settings').innerHTML =
                    '<div class="text-muted">Failed to load branding settings</div>';
            }}
        }}

        async function updateBranding(key, value) {{
            try {{
                const data = {{}};
                data[key] = value;
                await apiPatch('/settings/branding', data);
                showToast('Branding updated!');
            }} catch (e) {{
                showToast('Failed to update branding', 'error');
            }}
        }}

        async function updateBrandingColor(colorKey, value) {{
            try {{
                // Validate hex color
                if (!/^#[0-9A-Fa-f]{{6}}$/.test(value)) {{
                    showToast('Invalid color format', 'error');
                    return;
                }}
                await apiPatch('/settings/branding', {{
                    colors: {{ [colorKey]: value }}
                }});
                // Update both color picker and hex input
                document.getElementById('branding-primary-color').value = value;
                document.getElementById('branding-primary-hex').value = value;
                // Update CSS variable for live preview
                document.documentElement.style.setProperty('--primary', value);
                showToast('Color updated!');
            }} catch (e) {{
                showToast('Failed to update color', 'error');
            }}
        }}

        // Load feature settings
        async function loadFeatures() {{
            try {{
                const data = await apiGet('/settings/features');
                featuresData = data.features || {{}};

                // Set checkbox states
                document.getElementById('feature-points').checked = featuresData.points_enabled || false;
                document.getElementById('feature-referrals').checked = featuresData.referrals_enabled || false;
                document.getElementById('feature-self-signup').checked = featuresData.self_signup_enabled !== false;
            }} catch (e) {{
                console.error('Failed to load features:', e);
            }}
        }}

        async function toggleFeature(key, enabled) {{
            try {{
                const data = {{}};
                data[key] = enabled;
                await apiPatch('/settings/features', data);
                showToast(`Feature ${{enabled ? 'enabled' : 'disabled'}}!`);
            }} catch (e) {{
                showToast('Failed to update feature', 'error');
                // Revert checkbox
                loadFeatures();
            }}
        }}

        // Load tier options for form
        async function loadTierOptions() {{
            if (!tiersData.length) {{
                const data = await apiGet('/members/tiers');
                tiersData = data.tiers || [];
            }}
            const select = document.getElementById('tier-select');
            select.innerHTML = '<option value="">Select tier...</option>' +
                tiersData.map(t => `<option value="${{t.id}}">${{t.name}} - ${{formatCurrency(t.monthly_price)}}/mo</option>`).join('');
        }}

        // Load member options for trade-in form
        async function loadMemberOptions() {{
            if (!membersData.length) {{
                const data = await apiGet('/members?per_page=100');
                membersData = data.members || [];
            }}
            const select = document.getElementById('tradein-member-select');
            select.innerHTML = '<option value="">Select member...</option>' +
                membersData.map(m => `<option value="${{m.id}}">${{m.name || m.email}} (${{m.member_number}})</option>`).join('');
        }}

        // ==================== Shopify Customer Search & Enroll ====================

        let searchTimeout = null;
        let selectedCustomer = null;

        function debounceCustomerSearch(query) {{
            if (searchTimeout) clearTimeout(searchTimeout);
            if (!query || query.length < 2) {{
                document.getElementById('customer-search-results').innerHTML =
                    '<div class="text-muted text-center" style="padding: 20px;">Enter at least 2 characters to search</div>';
                return;
            }}
            document.getElementById('customer-search-results').innerHTML =
                '<div class="loading"><div class="spinner"></div></div>';
            searchTimeout = setTimeout(() => searchShopifyCustomers(query), 300);
        }}

        async function searchShopifyCustomers(query) {{
            try {{
                const result = await apiGet('/members/search-shopify?q=' + encodeURIComponent(query));
                renderCustomerResults(result.customers || []);
            }} catch (e) {{
                document.getElementById('customer-search-results').innerHTML =
                    '<div class="text-muted text-center" style="padding: 20px;">Search failed: ' + (e.message || 'Unknown error') + '</div>';
            }}
        }}

        function renderCustomerResults(customers) {{
            const container = document.getElementById('customer-search-results');
            if (!customers.length) {{
                container.innerHTML = '<div class="text-muted text-center" style="padding: 20px;">No customers found</div>';
                return;
            }}

            container.innerHTML = customers.map(c => `
                <div class="customer-result-item" onclick="selectCustomer(${{JSON.stringify(c).replace(/"/g, '&quot;')}})"
                     style="padding: 12px; border-radius: 8px; margin-bottom: 8px; cursor: pointer;
                            background: var(--bg-secondary); border: 2px solid transparent;
                            ${{c.is_member ? 'opacity: 0.6;' : ''}}"
                     onmouseover="this.style.borderColor='var(--primary)'"
                     onmouseout="this.style.borderColor='transparent'">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 600;">${{c.name || c.email || 'Unknown'}}</div>
                            <div class="text-muted" style="font-size: 13px;">${{c.email || ''}}</div>
                            ${{c.orb_number ? `<div style="font-size: 12px; color: var(--primary);">#${{c.orb_number}}</div>` : ''}}
                        </div>
                        <div style="text-align: right;">
                            ${{c.is_member
                                ? `<span class="status-badge status-active">${{c.member_number}}</span>`
                                : '<span class="status-badge" style="background: var(--success); color: white;">Available</span>'
                            }}
                            ${{c.storeCredit > 0 ? `<div style="font-size: 12px; margin-top: 4px;">$${{c.storeCredit.toFixed(2)}} credit</div>` : ''}}
                        </div>
                    </div>
                </div>
            `).join('');
        }}

        function selectCustomer(customer) {{
            if (customer.is_member) {{
                showToast(`${{customer.name}} is already enrolled as ${{customer.member_number}}`, 'error');
                return;
            }}

            selectedCustomer = customer;
            document.getElementById('selected-customer-id').value = customer.id;
            document.getElementById('selected-customer-name').textContent = customer.name || customer.email;
            document.getElementById('selected-customer-email').textContent = customer.email || '';
            document.getElementById('selected-customer-orb').textContent = customer.orb_number ? '#' + customer.orb_number : '';

            document.getElementById('enroll-form-section').style.display = 'block';
            document.getElementById('customer-search-results').style.display = 'none';

            // Populate tier dropdown
            populateEnrollTierSelect();
        }}

        function clearSelectedCustomer() {{
            selectedCustomer = null;
            document.getElementById('selected-customer-id').value = '';
            document.getElementById('enroll-form-section').style.display = 'none';
            document.getElementById('customer-search-results').style.display = 'block';
        }}

        function populateEnrollTierSelect() {{
            const select = document.getElementById('enroll-tier-select');
            const tiers = tiersData || [];
            select.innerHTML = '<option value="">Default (Lowest Tier)</option>' +
                tiers.map(t => `<option value="${{t.id}}">${{t.name}} - $${{t.monthly_price}}/mo (${{(t.bonus_rate * 100).toFixed(0)}}% bonus)</option>`).join('');
        }}

        async function submitEnrollment() {{
            if (!selectedCustomer) {{
                showToast('Please select a customer first', 'error');
                return;
            }}

            const tierId = document.getElementById('enroll-tier-select').value;
            const data = {{
                shopify_customer_id: selectedCustomer.id,
                partner_customer_id: selectedCustomer.orb_number || null
            }};
            if (tierId) data.tier_id = parseInt(tierId);

            try {{
                const result = await apiPost('/members/enroll', data);
                showToast(`Enrolled as ${{result.member.member_number}}!`);
                closeModal('enroll-customer');
                resetEnrollModal();
                loadRecentMembers();
                loadDashboardStats();
                if (currentPage === 'members') loadAllMembers();
            }} catch (e) {{
                showToast(e.message || 'Enrollment failed', 'error');
            }}
        }}

        function resetEnrollModal() {{
            selectedCustomer = null;
            document.getElementById('customer-search-input').value = '';
            document.getElementById('selected-customer-id').value = '';
            document.getElementById('enroll-form-section').style.display = 'none';
            document.getElementById('customer-search-results').style.display = 'block';
            document.getElementById('customer-search-results').innerHTML =
                '<div class="text-muted text-center" style="padding: 20px;">Enter a search term to find customers</div>';
        }}

        // Category selection
        let selectedCategory = 'other';

        function selectCategory(category) {{
            selectedCategory = category;
            document.getElementById('tradein-category').value = category;

            // Update visual selection
            document.querySelectorAll('.category-item').forEach(item => {{
                if (item.dataset.category === category) {{
                    item.classList.add('selected');
                }} else {{
                    item.classList.remove('selected');
                }}
            }});
        }}

        // Reset category when opening modal
        function resetCategorySelection() {{
            selectedCategory = 'other';
            document.getElementById('tradein-category').value = 'other';
            document.querySelectorAll('.category-item').forEach(item => {{
                if (item.dataset.category === 'other') {{
                    item.classList.add('selected');
                }} else {{
                    item.classList.remove('selected');
                }}
            }});
        }}

        // Submit new trade-in
        async function submitNewTradeIn(e) {{
            e.preventDefault();
            const form = e.target;
            const data = Object.fromEntries(new FormData(form));
            data.member_id = parseInt(data.member_id);
            data.category = selectedCategory;
            data.items = [{{
                description: data.description,
                trade_value: parseFloat(data.value),
                notes: data.notes
            }}];

            try {{
                await apiPost('/trade-ins', data);
                showToast('Trade-in created!');
                closeModal('new-tradein');
                form.reset();
                resetCategorySelection();
                loadDashboardStats();
                if (currentPage === 'tradeins') loadTradeIns();
            }} catch (e) {{
                showToast('Failed to create trade-in', 'error');
            }}
        }}

        // Initialize
        console.log('[TradeUp v1.7] Setting up DOMContentLoaded listener, readyState:', document.readyState);
        document.addEventListener('DOMContentLoaded', () => {{
            console.log('[TradeUp v1.7] DOMContentLoaded fired!');
            loadDashboardStats();
            loadRecentMembers();
        }});

        // Fallback if DOMContentLoaded already fired
        if (document.readyState === 'complete' || document.readyState === 'interactive') {{
            console.log('[TradeUp v1.7] DOM already ready, calling init directly');
            setTimeout(() => {{
                loadDashboardStats();
                loadRecentMembers();
            }}, 100);
        }}
    </script>
</body>
</html>'''


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

    # Tenant Settings
    from .api.settings import settings_bp

    # Billing (Shopify Billing API - replaces Stripe)
    from .api.billing import billing_bp

    # Partner Integrations
    from .api.partners import partners_bp

    # Promotions & Store Credit
    from .api.promotions import promotions_bp

    # Webhooks
    from .webhooks.shopify import webhooks_bp
    from .webhooks.shopify_billing import shopify_billing_webhook_bp
    from .webhooks.customer_lifecycle import customer_lifecycle_bp
    from .webhooks.order_lifecycle import order_lifecycle_bp
    from .webhooks.app_lifecycle import app_lifecycle_bp

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

    # Tenant Settings routes
    app.register_blueprint(settings_bp, url_prefix='/api/settings')

    # Billing API routes (Shopify Billing)
    app.register_blueprint(billing_bp, url_prefix='/api/billing')

    # Partner Integration routes
    app.register_blueprint(partners_bp, url_prefix='/api/partners')

    # Promotions & Store Credit routes
    app.register_blueprint(promotions_bp, url_prefix='/api/promotions')

    # Webhook routes
    app.register_blueprint(webhooks_bp, url_prefix='/webhook')
    app.register_blueprint(shopify_billing_webhook_bp, url_prefix='/webhook/shopify-billing')
    app.register_blueprint(customer_lifecycle_bp, url_prefix='/webhook')
    app.register_blueprint(order_lifecycle_bp, url_prefix='/webhook')
    app.register_blueprint(app_lifecycle_bp, url_prefix='/webhook')


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
