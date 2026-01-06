#!/usr/bin/env python3
"""
Test Shopify Customer Integration for TradeUp.

Tests the full flow:
1. Shopify customer lookup by email
2. Member creation with Shopify link
3. Tier tag sync to Shopify
4. Store credit balance display
"""
import os
import sys
from pathlib import Path
from decimal import Decimal

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Test configuration
TEST_EMAIL = "michael.alarconii@gmail.com"
TEST_NAME = "Michael Alarcon"


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_success(msg):
    print(f"  [OK] {msg}")


def print_error(msg):
    print(f"  [FAIL] {msg}")


def print_info(msg):
    print(f"  [INFO] {msg}")


def test_shopify_connection():
    """Test 1: Verify Shopify connection and find customer."""
    print_section("TEST 1: Shopify Connection & Customer Lookup")

    from app.services.shopify_client import ShopifyClient

    shop_domain = os.getenv('SHOPIFY_DOMAIN')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')

    if not shop_domain or not access_token:
        print_error("Missing SHOPIFY_DOMAIN or SHOPIFY_ACCESS_TOKEN")
        return None

    print_info(f"Shop domain: {shop_domain}")

    client = ShopifyClient(shop_domain, access_token)

    # Find customer by email
    print_info(f"Looking up customer: {TEST_EMAIL}")
    customer = client.get_customer_by_email(TEST_EMAIL)

    if not customer:
        print_error(f"Customer not found: {TEST_EMAIL}")
        return None

    print_success(f"Customer found!")
    print(f"      ID: {customer['id']}")
    print(f"      Name: {customer.get('firstName', '')} {customer.get('lastName', '')}")
    print(f"      Email: {customer.get('email', '')}")
    print(f"      Tags: {customer.get('tags', [])}")

    # Get store credit balance
    balance = client.get_store_credit_balance(customer['id'])
    print_success(f"Store Credit Balance: ${balance['balance']:.2f} {balance['currency']}")

    return {
        'customer_id': customer['id'],
        'customer': customer,
        'balance': balance,
        'client': client
    }


def test_membership_service(shopify_data):
    """Test 2: Test MembershipService with real Shopify data."""
    print_section("TEST 2: MembershipService - Create & Link Member")

    from app import create_app
    from app.extensions import db
    from app.models import Member, MembershipTier
    from app.services.membership_service import MembershipService

    app = create_app('development')

    with app.app_context():
        # Check if member already exists
        existing = Member.query.filter_by(email=TEST_EMAIL).first()
        if existing:
            print_info(f"Member already exists: {existing.member_number}")
            member = existing
        else:
            # Get default tier (should be Silver)
            default_tier = MembershipTier.query.filter_by(
                tenant_id=1,
                is_active=True
            ).order_by(MembershipTier.display_order).first()

            if not default_tier:
                print_error("No membership tiers found. Run seed script first.")
                return None

            print_info(f"Creating member with tier: {default_tier.name}")

            # Create member
            service = MembershipService(tenant_id=1)
            try:
                member = service.create_member(
                    email=TEST_EMAIL,
                    name=TEST_NAME,
                    tier_id=default_tier.id,
                    shopify_customer_id=shopify_data['customer_id']
                )
                print_success(f"Member created: {member.member_number}")
            except ValueError as e:
                print_error(f"Failed to create member: {e}")
                return None

        # Display member info
        print(f"\n      Member Number: {member.member_number}")
        print(f"      Email: {member.email}")
        print(f"      Name: {member.name}")
        print(f"      Tier: {member.tier.name if member.tier else 'None'}")
        print(f"      Shopify ID: {member.shopify_customer_id}")
        print(f"      Status: {member.status}")

        return member


def test_tag_sync(member):
    """Test 3: Test tier tag sync to Shopify."""
    print_section("TEST 3: Sync Tier Tags to Shopify")

    from app import create_app
    from app.services.membership_service import MembershipService

    app = create_app('development')

    with app.app_context():
        service = MembershipService(tenant_id=1)

        if not member.shopify_customer_id:
            print_info("Linking to Shopify customer first...")
            link_result = service.link_shopify_customer(member)
            if not link_result.get('success'):
                print_error(f"Failed to link: {link_result.get('error')}")
                return False
            print_success(f"Linked to: {link_result.get('customer_id')}")

        # Sync tags
        print_info("Syncing tier tags to Shopify...")
        sync_result = service.sync_member_tags(member)

        if sync_result.get('success'):
            print_success(f"Tags synced: {sync_result.get('tags_added')}")
            return True
        else:
            print_error(f"Sync failed: {sync_result.get('error')}")
            return False


def test_verify_shopify_tags(shopify_data):
    """Test 4: Verify tags were applied in Shopify."""
    print_section("TEST 4: Verify Tags in Shopify")

    client = shopify_data['client']

    # Refresh customer data
    customer = client.get_customer_by_email(TEST_EMAIL)

    if not customer:
        print_error("Customer not found after sync")
        return False

    tags = customer.get('tags', [])
    print_info(f"Current Shopify tags: {tags}")

    # Check for TradeUp tags
    tu_tags = [t for t in tags if t.startswith('tu-')]

    if tu_tags:
        print_success(f"TradeUp tags found: {tu_tags}")

        # Parse tags
        for tag in tu_tags:
            if tag.startswith('tu-tier-'):
                tier_name = tag.replace('tu-tier-', '')
                print(f"      - Tier: {tier_name}")
            elif tag.startswith('tu-member-'):
                member_num = tag.replace('tu-member-', '')
                print(f"      - Member #: TU{member_num}")
        return True
    else:
        print_error("No TradeUp tags found")
        return False


def test_api_endpoints():
    """Test 5: Test the API endpoints."""
    print_section("TEST 5: API Endpoints")

    import requests

    BASE_URL = "http://localhost:5000"

    # Note: These tests require the server to be running
    print_info("Note: Start the Flask server first with 'flask run'")
    print_info("Skipping API tests for now (run manually)")

    print("""
    Manual API test commands:

    # Get store credit balance
    curl -X GET "http://localhost:5000/api/membership/store-credit" \\
        -H "Authorization: Bearer <token>"

    # Get bonus history
    curl -X GET "http://localhost:5000/api/membership/bonus-history" \\
        -H "Authorization: Bearer <token>"

    # Link Shopify account
    curl -X POST "http://localhost:5000/api/membership/link-shopify" \\
        -H "Authorization: Bearer <token>"
    """)

    return True


def test_store_credit_events():
    """Test 6: Test Store Credit Events service."""
    print_section("TEST 6: Store Credit Events Service")

    from datetime import datetime, timedelta
    from app.services.store_credit_events import StoreCreditEventsService

    try:
        service = StoreCreditEventsService.from_env()
        print_success(f"Connected to: {service.shop_domain}")
    except Exception as e:
        print_error(f"Failed to connect: {e}")
        return False

    # Get orders from last 7 days
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=7)

    start_iso = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_iso = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    print_info(f"Previewing event: {start_dt.date()} to {end_dt.date()}")

    try:
        preview = service.preview_event(
            start_datetime=start_iso,
            end_datetime=end_iso,
            sources=['pos', 'web', 'shop'],
            credit_percent=10
        )

        print_success("Event preview generated!")
        print(f"      Total orders: {preview['total_orders']}")
        print(f"      Unique customers: {preview['unique_customers']}")
        print(f"      Total credit: ${preview['total_credit_amount']:.2f}")

        # Check if test user is in top customers
        for c in preview['top_customers']:
            if c['email'] == TEST_EMAIL:
                print_success(f"Test user found in top customers!")
                print(f"      Spent: ${c['total_spent']:.2f}")
                print(f"      Would receive: ${c['credit_amount']:.2f}")
                break

        return True

    except Exception as e:
        print_error(f"Preview failed: {e}")
        return False


def main():
    print("\n" + "TRADEUP SHOPIFY INTEGRATION TEST".center(60, "="))
    print(f"Test Account: {TEST_EMAIL}")
    print("=" * 60)

    # Track results
    results = {}

    # Test 1: Shopify connection
    shopify_data = test_shopify_connection()
    results['shopify_connection'] = shopify_data is not None

    if not shopify_data:
        print("\n[FAIL] Cannot proceed without Shopify connection")
        return

    # Test 2: Membership service
    member = test_membership_service(shopify_data)
    results['member_creation'] = member is not None

    if not member:
        print("\n[FAIL] Cannot proceed without member")
        return

    # Test 3: Tag sync
    results['tag_sync'] = test_tag_sync(member)

    # Test 4: Verify tags
    results['verify_tags'] = test_verify_shopify_tags(shopify_data)

    # Test 5: API endpoints info
    results['api_info'] = test_api_endpoints()

    # Test 6: Store Credit Events
    results['store_credit_events'] = test_store_credit_events()

    # Summary
    print_section("TEST SUMMARY")

    all_passed = all(results.values())

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {test_name}: {status}")

    print(f"\n{'ALL TESTS PASSED!' if all_passed else 'SOME TESTS FAILED'}")

    if all_passed:
        print("""
Next Steps:
1. Start the Flask server: flask run
2. Start the React frontend: cd frontend && npm run dev
3. Login with your Shopify account
4. Verify dashboard shows correct store credit balance
5. Test the bonus history display
        """)


if __name__ == "__main__":
    main()
