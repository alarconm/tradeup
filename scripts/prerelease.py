#!/usr/bin/env python3
"""
Pre-Release Validation Script for TradeUp

Run this before releasing a new version to ensure everything is ready.
Usage: python scripts/prerelease.py
"""

import subprocess
import sys
import os
import json
from pathlib import Path

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

def print_check(name, passed, details=None):
    status = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    print(f"{status} {name}")
    if details and not passed:
        print(f"       {YELLOW}{details}{RESET}")

def run_command(cmd, cwd=None):
    """Run a command and return (success, output)"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=120
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

def check_git_status():
    """Check for uncommitted changes"""
    success, output = run_command("git status --porcelain")
    if not success:
        return False, "Could not check git status"

    # Filter out untracked files that are OK
    lines = [l for l in output.strip().split('\n') if l and not l.startswith('??')]

    if lines:
        return False, f"Uncommitted changes: {len(lines)} files"
    return True, None

def check_git_branch():
    """Check we're on main branch"""
    success, output = run_command("git branch --show-current")
    if not success:
        return False, "Could not determine branch"

    branch = output.strip()
    if branch != "main":
        return False, f"On branch '{branch}', expected 'main'"
    return True, None

def check_git_synced():
    """Check local is synced with remote"""
    run_command("git fetch origin")
    success, output = run_command("git status -uno")

    if "Your branch is behind" in output:
        return False, "Local branch is behind remote"
    if "Your branch is ahead" in output:
        return False, "Local branch has unpushed commits"
    return True, None

def check_validation():
    """Run the validation script"""
    root = Path(__file__).parent.parent
    success, output = run_command("python scripts/validate.py", cwd=root)

    if "ALL CHECKS PASSED" in output:
        return True, None
    return False, "Validation failed - run 'npm run validate' for details"

def check_extensions_build():
    """Check extensions can build"""
    root = Path(__file__).parent.parent
    extensions = ['checkout-ui', 'customer-account-ui', 'post-purchase-ui', 'pos-ui']

    for ext in extensions:
        ext_path = root / 'extensions' / ext
        if not ext_path.exists():
            return False, f"Extension folder missing: {ext}"

        toml_path = ext_path / 'shopify.extension.toml'
        if not toml_path.exists():
            return False, f"Missing shopify.extension.toml in {ext}"

    return True, None

def check_package_version():
    """Check package.json has valid version"""
    root = Path(__file__).parent.parent
    pkg_path = root / 'package.json'

    try:
        with open(pkg_path) as f:
            pkg = json.load(f)

        version = pkg.get('version', '')
        if not version:
            return False, "No version in package.json"

        parts = version.split('.')
        if len(parts) != 3:
            return False, f"Invalid version format: {version}"

        return True, f"v{version}"
    except Exception as e:
        return False, str(e)

def check_env_file():
    """Check .env file exists with basic config"""
    root = Path(__file__).parent.parent
    env_path = root / '.env'

    if not env_path.exists():
        return False, ".env file missing"

    with open(env_path) as f:
        content = f.read()

    # Check for basic config (Shopify keys may be in shopify.app.toml or env)
    if 'SHOPIFY_DOMAIN' not in content and 'DATABASE_URL' not in content:
        return False, "Missing basic config in .env"
    return True, None

def check_health_endpoint():
    """Check production health endpoint"""
    try:
        import urllib.request
        url = "https://app.cardflowlabs.com/health"
        req = urllib.request.Request(url, headers={'User-Agent': 'TradeUp-PreRelease'})
        response = urllib.request.urlopen(req, timeout=10)

        if response.status == 200:
            return True, None
        return False, f"Health check returned {response.status}"
    except Exception as e:
        return False, f"Could not reach health endpoint: {e}"

def main():
    print_header("TradeUp Pre-Release Validation")

    checks = [
        ("Git: On main branch", check_git_branch),
        ("Git: No uncommitted changes", check_git_status),
        ("Git: Synced with remote", check_git_synced),
        ("Package: Valid version", check_package_version),
        ("Config: .env file present", check_env_file),
        ("Extensions: All folders present", check_extensions_build),
        ("Code: Validation passes", check_validation),
        ("Production: Health endpoint OK", check_health_endpoint),
    ]

    results = []
    for name, check_fn in checks:
        try:
            passed, details = check_fn()
            results.append((name, passed, details))
            print_check(name, passed, details)
        except Exception as e:
            results.append((name, False, str(e)))
            print_check(name, False, str(e))

    # Summary
    print_header("Summary")

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)

    if passed == total:
        print(f"{GREEN}{BOLD}ALL CHECKS PASSED ({passed}/{total}){RESET}")
        print(f"\n{GREEN}Ready to release!{RESET}")
        print(f"\nNext steps:")
        print(f"  1. npm run deploy")
        print(f"  2. Test in dev store")
        print(f"  3. npm run release --version=<version>")
        print(f"  4. npm run version:patch (or minor/major)")
        return 0
    else:
        print(f"{RED}{BOLD}CHECKS FAILED ({passed}/{total} passed){RESET}")
        print(f"\n{RED}Fix the issues above before releasing.{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
