"""
Quick Flip platform entry point.
"""
import os
import sys
import traceback

print("[TradeUp] ========================================")
print("[TradeUp] Starting TradeUp v1.2.4")
print("[TradeUp] ========================================")

# Default to production for Railway deployment
config_name = os.getenv('FLASK_ENV', 'production')
print(f"[TradeUp] Config: {config_name}")
print(f"[TradeUp] PORT: {os.getenv('PORT', 'not set')}")
print(f"[TradeUp] DATABASE_URL: {'set' if os.getenv('DATABASE_URL') else 'NOT SET'}")

try:
    print("[TradeUp] Importing create_app...")
    from app import create_app
    print("[TradeUp] Creating Flask app...")
    app = create_app(config_name)
    print("[TradeUp] App created successfully!")
    print(f"[TradeUp] Routes: {len(list(app.url_map.iter_rules()))}")
except Exception as e:
    print(f"[TradeUp] FATAL ERROR during app creation: {e}")
    traceback.print_exc()
    sys.exit(1)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('FLASK_ENV') == 'development'
    )
