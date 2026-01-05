#!/usr/bin/env python3
"""
Pre-deployment validation script for TradeUp.

Run this BEFORE pushing to main to catch issues that would cause Railway deploy failures.

Usage:
    python scripts/validate.py

Exit codes:
    0 - All checks passed, safe to push
    1 - Validation failed, do not push
"""

import os
import sys
import importlib
import traceback

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Set up environment for testing
os.environ.setdefault('DATABASE_URL', 'sqlite:///test.db')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('FLASK_ENV', 'development')

def print_status(check_name: str, passed: bool, message: str = ""):
    """Print check status."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {check_name}")
    if message and not passed:
        print(f"   └── {message}")

def check_imports():
    """Verify all app modules can be imported without errors."""
    print("\n[1/4] Checking imports...")

    modules_to_check = [
        'app',
        'app.extensions',
        'app.config',
        'app.models',
        'app.models.member',
        'app.models.tenant',
        'app.models.trade_in',
        'app.models.promotions',
        'app.services.store_credit_service',
        'app.services.shopify_client',
        'app.api.promotions',
        'app.webhooks.shopify',
    ]

    all_passed = True
    for module in modules_to_check:
        try:
            importlib.import_module(module)
            print_status(f"Import {module}", True)
        except Exception as e:
            print_status(f"Import {module}", False, str(e))
            all_passed = False

    return all_passed

def check_app_creation():
    """Verify Flask app can be created."""
    print("\n[2/4] Checking app creation...")

    try:
        from app import create_app
        app = create_app()
        print_status("Flask app creation", True)

        # Count routes
        routes = list(app.url_map.iter_rules())
        print_status(f"Routes registered: {len(routes)}", True)

        # Check specific blueprints
        promotions_routes = [r for r in routes if 'promotions' in r.rule]
        print_status(f"Promotions routes: {len(promotions_routes)}", len(promotions_routes) > 0)

        return True
    except Exception as e:
        print_status("Flask app creation", False, str(e))
        traceback.print_exc()
        return False

def check_migrations():
    """Check migration files for syntax errors."""
    print("\n[3/4] Checking migrations...")

    migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'versions')
    if not os.path.exists(migrations_dir):
        print_status("Migrations directory", False, "migrations/versions not found")
        return False

    all_passed = True
    for filename in os.listdir(migrations_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            filepath = os.path.join(migrations_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    code = f.read()
                compile(code, filepath, 'exec')
                print_status(f"Migration {filename[:20]}...", True)
            except SyntaxError as e:
                print_status(f"Migration {filename[:20]}...", False, str(e))
                all_passed = False

    return all_passed

def check_models_have_columns():
    """Verify model definitions match expected schema."""
    print("\n[4/4] Checking model definitions...")

    try:
        from app.models.promotions import (
            Promotion, StoreCreditLedger, MemberCreditBalance,
            BulkCreditOperation, TierConfiguration
        )

        # Check TierConfiguration has icon column
        if hasattr(TierConfiguration, 'icon'):
            print_status("TierConfiguration.icon column", True)
        else:
            print_status("TierConfiguration.icon column", False, "Missing icon column")
            return False

        print_status("Promotions models complete", True)
        return True
    except Exception as e:
        print_status("Model check", False, str(e))
        return False

def main():
    """Run all validation checks."""
    print("=" * 60)
    print("TradeUp Pre-Deployment Validation")
    print("=" * 60)

    # Change to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    sys.path.insert(0, project_root)

    checks = [
        ("Imports", check_imports),
        ("App Creation", check_app_creation),
        ("Migrations", check_migrations),
        ("Models", check_models_have_columns),
    ]

    results = []
    for name, check_fn in checks:
        try:
            results.append((name, check_fn()))
        except Exception as e:
            print(f"\n[CRASH] {name} check crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        print_status(name, passed)
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("ALL CHECKS PASSED! Safe to push to main.")
        return 0
    else:
        print("CHECKS FAILED. Fix issues before pushing.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
