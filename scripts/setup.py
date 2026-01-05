#!/usr/bin/env python3
"""
One-time setup script for TradeUp development environment.

Run this after cloning the repo:
    python scripts/setup.py
"""

import os
import sys
import shutil
import subprocess

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    print("=" * 60)
    print("TradeUp Development Setup")
    print("=" * 60)

    # 1. Install git hooks
    print("\n[1/4] Installing git hooks...")
    hooks_dir = os.path.join(project_root, '.git', 'hooks')
    pre_push_src = os.path.join(project_root, 'scripts', 'pre-push')
    pre_push_dst = os.path.join(hooks_dir, 'pre-push')

    if os.path.exists(hooks_dir):
        shutil.copy(pre_push_src, pre_push_dst)
        # Make executable on Unix
        if sys.platform != 'win32':
            os.chmod(pre_push_dst, 0o755)
        print("      Pre-push hook installed")
    else:
        print("      WARNING: .git/hooks not found. Run 'git init' first.")

    # 2. Create local env file
    print("\n[2/4] Setting up environment...")
    env_example = os.path.join(project_root, '.env.local.example')
    env_file = os.path.join(project_root, '.env')

    if not os.path.exists(env_file):
        if os.path.exists(env_example):
            shutil.copy(env_example, env_file)
            print("      Created .env from .env.local.example")
        else:
            print("      WARNING: .env.local.example not found")
    else:
        print("      .env already exists, skipping")

    # 3. Install Python dependencies
    print("\n[3/4] Installing Python dependencies...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'],
                      check=True)
        print("      Dependencies installed")
    except subprocess.CalledProcessError:
        print("      WARNING: Failed to install dependencies")

    # 4. Run initial validation
    print("\n[4/4] Running validation...")
    try:
        result = subprocess.run([sys.executable, 'scripts/validate.py'], check=False)
        if result.returncode == 0:
            print("\n      Validation passed!")
        else:
            print("\n      Validation failed - check output above")
    except Exception as e:
        print(f"      WARNING: Could not run validation: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("""
Next steps:
  1. Run 'make dev' to start local server
  2. Run 'make validate' before pushing
  3. Run 'make push' to validate and deploy

Quick reference:
  make help      - Show all commands
  make validate  - Check before pushing
  make push      - Validate + push to Railway
  make status    - Check production health
""")

if __name__ == '__main__':
    main()
