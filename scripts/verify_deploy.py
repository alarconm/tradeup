#!/usr/bin/env python3
"""
Verify TradeUp deployment is healthy.

Usage:
    python scripts/verify_deploy.py [--wait SECONDS] [--retries N]

Options:
    --wait      Seconds to wait before first check (default: 60)
    --retries   Number of retry attempts (default: 5)
"""
import sys
import time
import argparse
import urllib.request
import urllib.error
import json

PROD_URL = "https://tradeup-production.up.railway.app"

def check_endpoint(url, name):
    """Check if endpoint returns 200 and valid JSON."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'TradeUp-Verify/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return True, data
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"Connection error: {e.reason}"
    except json.JSONDecodeError:
        return False, "Invalid JSON response"
    except Exception as e:
        return False, str(e)

def verify_deployment(expected_version=None):
    """Verify all critical endpoints are working."""
    print("=" * 60)
    print("TradeUp Post-Deploy Verification")
    print("=" * 60)
    print()

    checks = [
        (f"{PROD_URL}/", "Root"),
        (f"{PROD_URL}/health", "Health"),
        (f"{PROD_URL}/api/promotions/health", "Promotions API"),
        (f"{PROD_URL}/api/promotions/tiers", "Tiers"),
    ]

    all_passed = True
    version = None

    for url, name in checks:
        success, result = check_endpoint(url, name)
        if success:
            print(f"[PASS] {name}")
            if name == "Root" and isinstance(result, dict):
                version = result.get('version', 'unknown')
        else:
            print(f"[FAIL] {name}: {result}")
            all_passed = False

    print()
    if version:
        print(f"Deployed version: {version}")
        if expected_version and version != expected_version:
            print(f"[WARN] Expected {expected_version}, got {version}")
            print("       Deployment may still be in progress.")
            all_passed = False

    print()
    if all_passed:
        print("[SUCCESS] All endpoints healthy!")
        return 0
    else:
        print("[WARNING] Some checks failed - review above")
        return 1

def main():
    parser = argparse.ArgumentParser(description='Verify TradeUp deployment')
    parser.add_argument('--wait', type=int, default=60,
                       help='Seconds to wait before first check (default: 60)')
    parser.add_argument('--retries', type=int, default=5,
                       help='Number of retry attempts (default: 5)')
    parser.add_argument('--version', type=str, default=None,
                       help='Expected version to verify')
    parser.add_argument('--quick', action='store_true',
                       help='Skip initial wait, check immediately')
    args = parser.parse_args()

    if not args.quick and args.wait > 0:
        print(f"Waiting {args.wait}s for Railway deployment...")
        for i in range(args.wait, 0, -10):
            print(f"  {i}s remaining...")
            time.sleep(min(10, i))
        print()

    for attempt in range(1, args.retries + 1):
        result = verify_deployment(args.version)
        if result == 0:
            return 0

        if attempt < args.retries:
            print(f"\nRetrying in 15s... (attempt {attempt}/{args.retries})")
            time.sleep(15)

    print("\n[FAILED] Deployment verification failed after retries")
    return 1

if __name__ == '__main__':
    sys.exit(main())
