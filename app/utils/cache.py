"""
Cache utilities for TradeUp.

Provides Redis-backed caching with graceful fallback to simple in-memory caching.
Uses Flask-Caching for integration with Flask app.

Usage:
    from app.utils.cache import cache

    @cache.memoize(timeout=300)  # 5 minute cache
    def get_expensive_data(param):
        ...

    # Manual cache operations
    cache.set('key', value, timeout=300)
    value = cache.get('key')
    cache.delete('key')

Environment Variables:
    REDIS_URL: Redis connection URL (e.g., redis://localhost:6379/0)
              Falls back to simple cache if not set or unavailable.
"""
import os
import logging
from flask_caching import Cache

logger = logging.getLogger(__name__)

# Global cache instance - initialized in init_cache()
cache = Cache()

# Default cache configuration
DEFAULT_CACHE_CONFIG = {
    'CACHE_TYPE': 'SimpleCache',  # Fallback: in-memory
    'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes
}


def init_cache(app):
    """
    Initialize Flask-Caching with Redis or fallback to simple cache.

    Args:
        app: Flask application instance

    Returns:
        bool: True if Redis connected, False if using fallback
    """
    redis_url = os.getenv('REDIS_URL')

    if redis_url:
        try:
            # Test Redis connection before configuring
            import redis
            r = redis.from_url(redis_url, socket_connect_timeout=2)
            r.ping()

            # Configure Redis cache
            app.config['CACHE_TYPE'] = 'RedisCache'
            app.config['CACHE_REDIS_URL'] = redis_url
            app.config['CACHE_DEFAULT_TIMEOUT'] = 300
            app.config['CACHE_KEY_PREFIX'] = 'tradeup:'

            cache.init_app(app)
            logger.info('[TradeUp] Redis cache connected: %s', redis_url.split('@')[-1])
            return True

        except Exception as e:
            logger.warning('[TradeUp] Redis unavailable (%s), using simple cache', str(e))

    # Fallback to simple in-memory cache
    app.config['CACHE_TYPE'] = 'SimpleCache'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300

    cache.init_app(app)
    logger.info('[TradeUp] Using simple in-memory cache (no Redis)')
    return False


def cache_key(*args, **kwargs):
    """
    Generate a cache key from function arguments.

    Useful for manual cache operations:
        key = cache_key('tenant_settings', tenant_id=123)
        cache.set(key, data, timeout=300)
    """
    parts = list(args)
    for k, v in sorted(kwargs.items()):
        parts.append(f'{k}={v}')
    return ':'.join(str(p) for p in parts)


def invalidate_pattern(pattern: str):
    """
    Invalidate all cache keys matching a pattern.

    Only works with Redis backend. Falls back to clear() for simple cache.

    Args:
        pattern: Redis key pattern (e.g., 'tradeup:tenant:123:*')
    """
    try:
        if hasattr(cache.cache, '_read_client'):
            # Redis backend - use SCAN to find and delete matching keys
            client = cache.cache._read_client
            keys = list(client.scan_iter(match=pattern))
            if keys:
                client.delete(*keys)
                logger.debug('Invalidated %d cache keys matching %s', len(keys), pattern)
        else:
            # Simple cache - can't do pattern matching, just log
            logger.debug('Pattern invalidation not supported for simple cache')
    except Exception as e:
        logger.warning('Cache invalidation failed: %s', e)


# Cache decorators with common TTLs
def cached_5min(key_prefix=''):
    """Cache for 5 minutes (300 seconds)."""
    return cache.memoize(timeout=300, key_prefix=key_prefix)


def cached_1hr(key_prefix=''):
    """Cache for 1 hour (3600 seconds)."""
    return cache.memoize(timeout=3600, key_prefix=key_prefix)


def cached_1day(key_prefix=''):
    """Cache for 1 day (86400 seconds)."""
    return cache.memoize(timeout=86400, key_prefix=key_prefix)
