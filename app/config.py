"""
Configuration management for TradeUp platform.
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

    # TradeUp defaults - tier bonus rates
    DEFAULT_BONUS_RATES = {
        'silver': 0.05,   # 5% trade-in bonus
        'gold': 0.10,     # 10% trade-in bonus
        'platinum': 0.15  # 15% trade-in bonus
    }


class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///tradeup_dev.db'  # SQLite fallback for local dev
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
    _secret_key = os.getenv('SECRET_KEY', '')

    @classmethod
    def validate_secret_key(cls) -> str:
        """
        Validate SECRET_KEY in production environment.

        Raises:
            RuntimeError: If SECRET_KEY is missing, empty, or contains unsafe values
        """
        if not cls._secret_key:
            raise RuntimeError(
                "CRITICAL: SECRET_KEY environment variable is not set!\n"
                "Production deployments MUST have a secure SECRET_KEY.\n"
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )

        # Check for obvious insecure values
        insecure_patterns = ['dev', 'change', 'default', 'test', 'secret', 'password']
        lower_key = cls._secret_key.lower()
        for pattern in insecure_patterns:
            if pattern in lower_key:
                raise RuntimeError(
                    f"CRITICAL: SECRET_KEY contains '{pattern}' which suggests it's not secure!\n"
                    "Production deployments require a unique, random SECRET_KEY.\n"
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )

        # Minimum length check
        if len(cls._secret_key) < 32:
            raise RuntimeError(
                "CRITICAL: SECRET_KEY is too short (minimum 32 characters required)!\n"
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )

        return cls._secret_key

    SECRET_KEY = _secret_key  # Will be validated at app startup


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


def validate_config(config_name: str = 'development') -> None:
    """
    Validate configuration before app startup.

    In production, this ensures SECRET_KEY is properly configured.
    Called from create_app() after loading config.

    Args:
        config_name: The configuration environment name

    Raises:
        RuntimeError: If validation fails in production
    """
    if config_name == 'production':
        ProductionConfig.validate_secret_key()
