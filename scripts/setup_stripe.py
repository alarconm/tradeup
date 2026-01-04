#!/usr/bin/env python3
"""
Set up Stripe products and prices for Quick Flip membership tiers.

Usage:
    python scripts/setup_stripe.py --tenant orb

This will create Stripe Products and Prices for each tier:
    - Silver ($10/mo)
    - Gold ($25/mo)
    - Platinum ($50/mo)

And update the database with the Stripe IDs.
"""
import os
import sys
import argparse
import stripe
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


def setup_stripe_products(tenant_slug: str, dry_run: bool = False):
    """Create Stripe products and prices for membership tiers."""

    # Initialize Stripe
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        print("Error: STRIPE_SECRET_KEY not set in environment")
        sys.exit(1)

    # Import Flask app for database access
    from app import create_app
    from app.extensions import db
    from app.models import Tenant, MembershipTier

    app = create_app()

    with app.app_context():
        # Find tenant
        tenant = Tenant.query.filter_by(slug=tenant_slug).first()
        if not tenant:
            print(f"Error: Tenant '{tenant_slug}' not found")
            sys.exit(1)

        print(f"Setting up Stripe for tenant: {tenant.name} ({tenant.slug})")
        print()

        # Get all tiers for this tenant
        tiers = MembershipTier.query.filter_by(tenant_id=tenant.id).all()
        if not tiers:
            print("No membership tiers found. Creating default tiers...")

            # Create default tiers if none exist
            default_tiers = [
                {
                    'name': 'Silver',
                    'monthly_price': 10.00,
                    'bonus_rate': 0.10,
                    'quick_flip_days': 7,
                    'benefits': {'discount_percent': 5},
                    'display_order': 1
                },
                {
                    'name': 'Gold',
                    'monthly_price': 25.00,
                    'bonus_rate': 0.20,
                    'quick_flip_days': 7,
                    'benefits': {'discount_percent': 10},
                    'display_order': 2
                },
                {
                    'name': 'Platinum',
                    'monthly_price': 50.00,
                    'bonus_rate': 0.30,
                    'quick_flip_days': 14,
                    'benefits': {'discount_percent': 15, 'early_access': True},
                    'display_order': 3
                }
            ]

            for tier_data in default_tiers:
                tier = MembershipTier(
                    tenant_id=tenant.id,
                    **tier_data
                )
                db.session.add(tier)

            db.session.commit()
            tiers = MembershipTier.query.filter_by(tenant_id=tenant.id).all()

        # Create Stripe products and prices for each tier
        for tier in tiers:
            print(f"Processing tier: {tier.name} (${tier.monthly_price}/mo)")

            # Skip if already has Stripe IDs
            if tier.stripe_product_id and tier.stripe_price_id:
                print(f"  [EXISTS] Product: {tier.stripe_product_id}, Price: {tier.stripe_price_id}")
                continue

            if dry_run:
                print(f"  [DRY RUN] Would create product and price")
                continue

            # Create Stripe Product
            product = stripe.Product.create(
                name=f"{tenant.name} - {tier.name} Membership",
                description=f"{tier.name} tier membership with {int(tier.bonus_rate * 100)}% Quick Flip bonus",
                metadata={
                    'tenant_id': str(tenant.id),
                    'tenant_slug': tenant.slug,
                    'tier_id': str(tier.id),
                    'tier_name': tier.name
                }
            )
            print(f"  [CREATED] Product: {product.id}")

            # Create Stripe Price (monthly subscription)
            price = stripe.Price.create(
                product=product.id,
                unit_amount=int(float(tier.monthly_price) * 100),  # Convert to cents
                currency='usd',
                recurring={'interval': 'month'},
                metadata={
                    'tenant_id': str(tenant.id),
                    'tier_id': str(tier.id)
                }
            )
            print(f"  [CREATED] Price: {price.id} (${tier.monthly_price}/mo)")

            # Update tier with Stripe IDs
            tier.stripe_product_id = product.id
            tier.stripe_price_id = price.id

        db.session.commit()
        print()
        print("Stripe setup complete!")
        print()

        # Print summary
        print("=== Stripe Configuration Summary ===")
        for tier in tiers:
            print(f"{tier.name}:")
            print(f"  Product ID: {tier.stripe_product_id}")
            print(f"  Price ID:   {tier.stripe_price_id}")
            print(f"  Price:      ${tier.monthly_price}/mo")
            print()


def list_stripe_webhooks():
    """List existing Stripe webhook endpoints."""
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        print("Error: STRIPE_SECRET_KEY not set")
        return

    print("Existing Stripe Webhook Endpoints:")
    endpoints = stripe.WebhookEndpoint.list()
    for endpoint in endpoints.data:
        print(f"  {endpoint.id}: {endpoint.url}")
        print(f"    Events: {', '.join(endpoint.enabled_events)}")
        print(f"    Status: {endpoint.status}")
        print()


def create_stripe_webhook(base_url: str, tenant_slug: str):
    """Create a Stripe webhook endpoint."""
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        print("Error: STRIPE_SECRET_KEY not set")
        return

    webhook_url = f"{base_url.rstrip('/')}/webhook/stripe"

    print(f"Creating webhook endpoint: {webhook_url}")

    try:
        endpoint = stripe.WebhookEndpoint.create(
            url=webhook_url,
            enabled_events=[
                'checkout.session.completed',
                'invoice.paid',
                'invoice.payment_failed',
                'customer.subscription.updated',
                'customer.subscription.deleted',
            ],
            description=f"Quick Flip webhook for {tenant_slug}"
        )

        print(f"Webhook created successfully!")
        print(f"  ID: {endpoint.id}")
        print(f"  Secret: {endpoint.secret}")
        print()
        print("IMPORTANT: Add this to your environment variables:")
        print(f"  STRIPE_WEBHOOK_SECRET={endpoint.secret}")

    except stripe.error.InvalidRequestError as e:
        print(f"Error creating webhook: {e}")


def main():
    parser = argparse.ArgumentParser(description="Set up Stripe for Quick Flip")
    parser.add_argument('--tenant', required=True, help="Tenant slug (e.g., orb)")
    parser.add_argument('--dry-run', action='store_true', help="Preview without creating")
    parser.add_argument('--list-webhooks', action='store_true', help="List existing webhooks")
    parser.add_argument('--create-webhook', metavar='BASE_URL', help="Create webhook endpoint")
    args = parser.parse_args()

    if args.list_webhooks:
        list_stripe_webhooks()
    elif args.create_webhook:
        create_stripe_webhook(args.create_webhook, args.tenant)
    else:
        setup_stripe_products(args.tenant, args.dry_run)


if __name__ == "__main__":
    main()
