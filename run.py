"""
Quick Flip platform entry point.
"""
import os
from app import create_app

# Default to production for Railway deployment
# Set FLASK_ENV=development explicitly for local development
config_name = os.getenv('FLASK_ENV', 'production')
print(f"[TradeUp] Starting with config: {config_name}")

app = create_app(config_name)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('FLASK_ENV') == 'development'
    )
