"""
Middleware package for TradeUp.
"""
from .shopify_auth import require_shopify_auth, get_shop_from_request
from .shop_auth import require_shop_auth, require_subscription

# Rate limiting is optional - only import if flask_limiter is installed
try:
    from .rate_limit import (
        limiter,
        init_rate_limiter,
        ratelimit_standard,
        ratelimit_strict,
        ratelimit_relaxed,
        ratelimit_webhook,
    )
except ImportError:
    # Flask-Limiter not installed - provide no-op decorators
    limiter = None
    init_rate_limiter = None

    def ratelimit_standard(f):
        return f

    def ratelimit_strict(f):
        return f

    def ratelimit_relaxed(f):
        return f

    def ratelimit_webhook(f):
        return f
