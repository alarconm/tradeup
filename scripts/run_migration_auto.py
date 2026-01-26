#!/usr/bin/env python3
"""
Auto-runner for migration script that loads .env.migration
"""
import os
import sys

# Load .env.migration file
env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.migration')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    print(f"Loaded environment from {env_file}")
else:
    print(f"Error: {env_file} not found")
    sys.exit(1)

# Now import and run the migrator
from migrate_store_data import ShopifyStore, ShopifyMigrator

source = ShopifyStore(
    domain=os.environ["SOURCE_SHOP_DOMAIN"],
    access_token=os.environ["SOURCE_ACCESS_TOKEN"]
)

dest = ShopifyStore(
    domain=os.environ["DEST_SHOP_DOMAIN"],
    access_token=os.environ["DEST_ACCESS_TOKEN"]
)

print(f"\nMigrating data from:")
print(f"  Source: {source.domain}")
print(f"  To: {dest.domain}")
print("\nStarting migration automatically...\n")

migrator = ShopifyMigrator(source, dest)
migrator.run_full_migration(
    products=True,
    collections=False,  # Already migrated
    customers=True,
    orders=True,
    product_limit=50,  # More products for realistic testing
    customer_limit=30,
    order_limit=100,
    order_days=90,
)
