"""
Configuration management for Quick Flip platform.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Shopify defaults (overridden per-tenant)
    SHOPIFY_API_VERSION = '2024-01'

    # Quick Flip defaults
    DEFAULT_QUICK_FLIP_DAYS = 7
    DEFAULT_BONUS_RATES = {
        'silver': 0.10,
        'gold': 0.20,
        'platinum': 0.30
    }


class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///quick_flip_dev.db'  # SQLite fallback for local dev
    )


class ProductionConfig(BaseConfig):
    """Production configuration."""
    DEBUG = False

    # Handle DATABASE_URL with PostgreSQL SSL (Railway requires this)
    _db_url = os.getenv('DATABASE_URL', '')
    if _db_url.startswith('postgres://'):
        # SQLAlchemy requires postgresql:// not postgres://
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = _db_url

    # PostgreSQL SSL configuration for Railway
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 300,
        'pool_pre_ping': True,  # Verify connections before using
    }

    # Override SECRET_KEY for production - must be set via environment
    SECRET_KEY = os.getenv('SECRET_KEY') or 'MISSING-SECRET-KEY-SET-IN-ENV'


class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}


def get_config(config_name: str = 'development'):
    """Get configuration class by name."""
    return config_map.get(config_name, DevelopmentConfig)
