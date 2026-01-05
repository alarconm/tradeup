"""
Gunicorn configuration for Railway deployment.
"""
import os

# Bind to Railway's PORT or default
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"

# Worker configuration
# Railway has limited memory, use fewer workers
workers = int(os.getenv('GUNICORN_WORKERS', '2'))
worker_class = 'sync'
worker_connections = 1000
timeout = 120  # Longer timeout for slow DB operations
keepalive = 5

# Logging
accesslog = '-'  # stdout
errorlog = '-'   # stderr
loglevel = os.getenv('LOG_LEVEL', 'info')
capture_output = True

# Process naming
proc_name = 'tradeup'

# Preload app for better memory usage
preload_app = True

# Graceful restart
graceful_timeout = 30

# Health check support
def on_starting(server):
    print("[Gunicorn] Starting TradeUp server...")

def on_exit(server):
    print("[Gunicorn] TradeUp server shutting down...")
