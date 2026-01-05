#!/usr/bin/env python3
"""
Seed ORB Sports Cards as the initial tenant with membership tiers.

Usage:
    python scripts/seed_orb.py

Or with Flask CLI:
    flask seed-orb
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models import Tenant, MembershipTier, APIKey


def seed_orb_tenant():
    """Create ORB Sports Cards tenant with default tiers."""
    import os
    config_name = os.getenv('FLASK_ENV', 'production')
    print(f"[Seed] Using config: {config_name}")

    app = create_app(config_name)

    with app.app_context():
        # Test database connection first
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            print("[Seed] Database connection OK")
        except Exception as e:
            print(f"[Seed] WARNING: Database connection failed: {e}")
            print("[Seed] Skipping seed - will retry on next deploy")
            return  # Don't crash, just skip seeding
        # Check if ORB tenant already exists
        existing = Tenant.query.filter_by(shop_slug="orb").first()
        if existing:
            print(f"ORB tenant already exists (ID: {existing.id})")
            tenant = existing
        else:
            # Create ORB tenant
            tenant = Tenant(
                shop_name="ORB Sports Cards & Collectibles",
                shop_slug="orb",
                shopify_domain=os.getenv("SHOPIFY_DOMAIN", "uy288y-nx.myshopify.com"),
                subscription_plan="pro",
                subscription_active=True,
                monthly_price=Decimal("0"),  # Internal use
                max_members=10000,  # Unlimited for ORB
                max_tiers=10,
                is_active=True,
            )
            db.session.add(tenant)
            db.session.commit()
            print(f"Created ORB tenant (ID: {tenant.id})")

        # Check for existing tiers
        existing_tiers = MembershipTier.query.filter_by(tenant_id=tenant.id).count()
        if existing_tiers > 0:
            print(f"Tiers already exist ({existing_tiers} tiers)")
        else:
            # Create default tiers
            tiers = [
                MembershipTier(
                    tenant_id=tenant.id,
                    name="Silver",
                    monthly_price=Decimal("10.00"),
                    bonus_rate=Decimal("0.10"),
                    quick_flip_days=7,
                    benefits={
                        "discount": 5,
                        "early_access": True,
                    },
                    display_order=1,
                ),
                MembershipTier(
                    tenant_id=tenant.id,
                    name="Gold",
                    monthly_price=Decimal("25.00"),
                    bonus_rate=Decimal("0.20"),
                    quick_flip_days=7,
                    benefits={
                        "discount": 10,
                        "early_access": True,
                        "free_shipping": True,
                        "events": True,
                    },
                    display_order=2,
                ),
                MembershipTier(
                    tenant_id=tenant.id,
                    name="Platinum",
                    monthly_price=Decimal("50.00"),
                    bonus_rate=Decimal("0.30"),
                    quick_flip_days=7,
                    benefits={
                        "discount": 15,
                        "early_access": True,
                        "free_shipping": True,
                        "events": True,
                        "vip_perks": True,
                    },
                    display_order=3,
                ),
            ]

            for tier in tiers:
                db.session.add(tier)

            db.session.commit()
            print("Created membership tiers: Silver, Gold, Platinum")

        # Create API key if none exists
        existing_key = APIKey.query.filter_by(tenant_id=tenant.id, is_active=True).first()
        if existing_key:
            print(f"API key already exists: {existing_key.key_prefix}...")
        else:
            import secrets

            key = secrets.token_urlsafe(32)
            api_key = APIKey(
                tenant_id=tenant.id,
                key_hash=key,  # In production, this should be hashed
                key_prefix=key[:8],
                name="Default API Key",
                permissions={"all": True},
            )
            db.session.add(api_key)
            db.session.commit()
            print(f"Created API key: {key}")
            print("  (Save this key - it won't be shown again!)")

        print()
        print("ORB Sports Cards setup complete!")
        print(f"  Tenant ID: {tenant.id}")
        print(f"  Slug: {tenant.shop_slug}")
        print(f"  Shopify: {tenant.shopify_domain}")


if __name__ == "__main__":
    seed_orb_tenant()
