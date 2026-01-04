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

    # Webhooks
    from .webhooks.shopify import webhooks_bp
    from .webhooks.stripe import stripe_webhook_bp

    # Core API routes
    app.register_blueprint(members_bp, url_prefix='/api/members')
    app.register_blueprint(trade_ins_bp, url_prefix='/api/trade-ins')
    app.register_blueprint(bonuses_bp, url_prefix='/api/bonuses')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')

    # Auth and Membership routes
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(membership_bp, url_prefix='/api/membership')

    # Webhook routes
    app.register_blueprint(webhooks_bp, url_prefix='/webhook')
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
