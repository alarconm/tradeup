#!/usr/bin/env python3
"""
Comprehensive User Story Testing Script for TradeUp.

Tests all user stories from docs/USER_STORIES_TESTING.md
"""
import sys
import os
import json
import requests
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test configuration
BASE_URL = "http://localhost:5000"
TENANT_HEADER = {"X-Tenant-ID": "1", "Content-Type": "application/json"}

# Track test results
results = {"passed": [], "failed": [], "skipped": []}


def print_header(section_num, title):
    print(f"\n{'='*60}")
    print(f"  SECTION {section_num}: {title}")
    print('='*60)


def print_test(story_id, description, passed, details=""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"\n  [{story_id}] {status}: {description}")
    if details:
        print(f"       {details}")
    if passed:
        results["passed"].append(f"{story_id}: {description}")
    else:
        results["failed"].append(f"{story_id}: {description} - {details}")


def test_api_get(endpoint, expected_keys=None, story_id="", description=""):
    """Test a GET endpoint."""
    try:
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=TENANT_HEADER, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if expected_keys:
                missing = [k for k in expected_keys if k not in data]
                if missing:
                    print_test(story_id, description, False, f"Missing keys: {missing}")
                    return None
            print_test(story_id, description, True)
            return data
        else:
            print_test(story_id, description, False, f"Status {resp.status_code}: {resp.text[:100]}")
            return None
    except Exception as e:
        print_test(story_id, description, False, str(e))
        return None


def test_api_post(endpoint, payload, expected_keys=None, story_id="", description=""):
    """Test a POST endpoint."""
    try:
        resp = requests.post(f"{BASE_URL}{endpoint}", headers=TENANT_HEADER, json=payload, timeout=10)
        if resp.status_code in [200, 201]:
            data = resp.json()
            if expected_keys:
                missing = [k for k in expected_keys if k not in data]
                if missing:
                    print_test(story_id, description, False, f"Missing keys: {missing}")
                    return None
            print_test(story_id, description, True)
            return data
        else:
            print_test(story_id, description, False, f"Status {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print_test(story_id, description, False, str(e))
        return None


def test_api_put(endpoint, payload, story_id="", description=""):
    """Test a PUT endpoint."""
    try:
        resp = requests.put(f"{BASE_URL}{endpoint}", headers=TENANT_HEADER, json=payload, timeout=10)
        if resp.status_code in [200, 201]:
            print_test(story_id, description, True)
            return resp.json()
        else:
            print_test(story_id, description, False, f"Status {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print_test(story_id, description, False, str(e))
        return None


def test_api_patch(endpoint, payload, story_id="", description=""):
    """Test a PATCH endpoint."""
    try:
        resp = requests.patch(f"{BASE_URL}{endpoint}", headers=TENANT_HEADER, json=payload, timeout=10)
        if resp.status_code in [200, 201]:
            print_test(story_id, description, True)
            return resp.json()
        else:
            print_test(story_id, description, False, f"Status {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print_test(story_id, description, False, str(e))
        return None


# ============================================================
# SECTION 1: Dashboard & Authentication
# ============================================================
def test_section_1():
    print_header("1", "Merchant Dashboard & Authentication")

    # 1.1 Dashboard Access (via API)
    test_api_get("/health", ["status"], "1.1", "Health endpoint accessible")

    # 1.2 Dashboard Statistics
    data = test_api_get("/api/dashboard/stats", None, "1.2a", "Dashboard stats endpoint")
    if data:
        # Actual API returns: members, trade_ins_this_month, credit_this_month
        expected = ["members", "trade_ins_this_month", "credit_this_month"]
        missing = [k for k in expected if k not in data]
        if missing:
            print_test("1.2b", f"Dashboard has required stats", False, f"Missing: {missing}")
        else:
            print_test("1.2b", f"Dashboard has all required stats", True)
            print(f"       Stats: {data['members']['total']} members, {data['trade_ins_this_month']} trade-ins")

    # Recent activity
    test_api_get("/api/dashboard/recent-activity", None, "1.2c", "Recent activity endpoint")


# ============================================================
# SECTION 2: Member Management
# ============================================================
def test_section_2():
    print_header("2", "Member Management")

    # 2.1 View All Members
    data = test_api_get("/api/members", ["members"], "2.1", "List all members")
    member_id = None

    # 2.2 Enroll New Member (requires Shopify customer ID)
    new_member = test_api_post("/api/members", {
        "email": f"test-user-{os.getpid()}@example.com",
        "name": "Test User",
        "tier_id": 1,
        "shopify_customer_id": f"test-{os.getpid()}"  # Mock Shopify ID for testing
    }, None, "2.2", "Enroll new member")

    if new_member:
        member_id = new_member.get("id")
        print(f"       Created member ID: {member_id}")

    # 2.3 Search Members
    test_api_get("/api/members?search=test", ["members"], "2.3", "Search members")

    # 2.4 View Member Details
    if member_id:
        data = test_api_get(f"/api/members/{member_id}", None, "2.4", "View member details")
        if data:
            expected = ["id", "email", "name", "tier", "status"]
            missing = [k for k in expected if k not in data]
            if missing:
                print_test("2.4b", "Member has required fields", False, f"Missing: {missing}")
            else:
                print_test("2.4b", "Member has all required fields", True)

    # 2.5 Manually Adjust Tier
    if member_id:
        result = test_api_put(f"/api/members/{member_id}", {
            "tier_id": 2
        }, "2.5", "Change member tier")

    # 2.6 Add Store Credit Manually
    if member_id:
        result = test_api_post("/api/promotions/credit/add", {
            "member_id": member_id,
            "amount": 25.00,
            "description": "Test credit"
        }, None, "2.6", "Add store credit to member")

    # 2.7 Deduct Store Credit
    if member_id:
        result = test_api_post("/api/promotions/credit/add", {
            "member_id": member_id,
            "amount": -10.00,
            "description": "Test deduction"
        }, None, "2.7", "Deduct store credit from member")

    return member_id


# ============================================================
# SECTION 3: Tier Configuration
# ============================================================
def test_section_3():
    print_header("3", "Tier Configuration")

    # 3.1 View All Tiers
    data = test_api_get("/api/members/tiers", ["tiers"], "3.1", "View all membership tiers")
    tier_id = None
    if data and data.get("tiers"):
        tier_id = data["tiers"][0].get("id")
        print(f"       Found {len(data['tiers'])} tiers")

    # 3.2 Edit Tier Settings
    if tier_id:
        result = test_api_put(f"/api/members/tiers/{tier_id}", {
            "trade_in_rate": 0.65,
            "cashback_rate": 0.02
        }, "3.2", "Edit tier settings")

    # 3.3 View Individual Tier
    if tier_id:
        test_api_get(f"/api/members/tiers/{tier_id}", None, "3.3", "View individual tier")


# ============================================================
# SECTION 4: Trade-In Management
# ============================================================
def test_section_4(member_id):
    print_header("4", "Trade-In Management")

    # 4.1 View All Trade-Ins
    data = test_api_get("/api/trade-ins", None, "4.1", "View all trade-ins")

    # 4.2 Create New Trade-In
    trade_in = None
    if member_id:
        trade_in = test_api_post("/api/trade-ins", {
            "member_id": member_id,
            "notes": "Test trade-in batch"
        }, None, "4.2", "Create new trade-in")

    batch_id = trade_in.get("id") if trade_in else None

    # 4.3 Add Items to Trade-In
    if batch_id:
        items = test_api_post(f"/api/trade-ins/{batch_id}/items", {
            "items": [
                {"product_title": "Test Card 1", "trade_value": 50.00},
                {"product_title": "Test Card 2", "trade_value": 25.00}
            ]
        }, None, "4.3", "Add items to trade-in")

    # 4.4 View Trade-In Details
    if batch_id:
        test_api_get(f"/api/trade-ins/{batch_id}", None, "4.4", "View trade-in details")

    # 4.5 Complete Trade-In (uses POST)
    if batch_id:
        result = test_api_post(f"/api/trade-ins/{batch_id}/complete", {}, None, "4.5", "Complete trade-in")

    return batch_id


# ============================================================
# SECTION 5: Store Credit System
# ============================================================
def test_section_5(member_id):
    print_header("5", "Store Credit System")

    # 5.1 Check Credit Balance via API
    if member_id:
        data = test_api_get(f"/api/promotions/credit/balance/{member_id}", None, "5.1", "Check credit balance")
        if data:
            # Response structure: { balance: {...}, transactions: [...] }
            expected = ["balance", "transactions"]
            missing = [k for k in expected if k not in data]
            if missing:
                print_test("5.1b", "Balance has required fields", False, f"Missing: {missing}")
            else:
                balance = data.get('balance', {})
                print_test("5.1b", "Balance has all required fields", True, f"Balance: ${balance.get('total_balance', 0):.2f}")

    # 5.2 View Credit Ledger
    if member_id:
        test_api_get(f"/api/membership/store-credit/history/{member_id}", None, "5.2", "View credit ledger")


# ============================================================
# SECTION 6: Cashback System
# ============================================================
def test_section_6():
    print_header("6", "Cashback Settings")

    # 6.1 Get Cashback Settings
    data = test_api_get("/api/settings/cashback", None, "6.1", "Get cashback settings")

    # 6.2 Update Cashback Settings
    if data:
        result = test_api_patch("/api/settings/cashback", {
            "purchase_cashback_enabled": True,
            "rounding_mode": "down"
        }, "6.2", "Update cashback settings")


# ============================================================
# SECTION 7: Settings & Configuration
# ============================================================
def test_section_7():
    print_header("7", "Settings & Configuration")

    # 7.1 Get Subscription Settings
    test_api_get("/api/settings/subscriptions", None, "7.1", "Get subscription settings")

    # 7.2 Get Branding Settings
    test_api_get("/api/settings/branding", None, "7.2", "Get branding settings")

    # 7.3 Get Auto-Enrollment Settings
    test_api_get("/api/settings/auto-enrollment", None, "7.3", "Get auto-enrollment settings")

    # 7.4 Get Notification Settings
    test_api_get("/api/settings/notifications", None, "7.4", "Get notification settings")


# ============================================================
# SECTION 8: API Endpoints Testing
# ============================================================
def test_section_8():
    print_header("8", "API Endpoints Verification")

    # 8.1 GET /api/promotions/tiers
    test_api_get("/api/promotions/tiers", None, "8.1", "GET /api/promotions/tiers")

    # 8.2 GET /api/promotions/stats
    test_api_get("/api/promotions/stats", None, "8.2", "GET /api/promotions/stats")

    # 8.3 Promotions health
    test_api_get("/api/promotions/health", None, "8.3", "GET /api/promotions/health")

    # 8.4 Billing plans
    test_api_get("/api/billing/plans", None, "8.4", "GET /api/billing/plans")

    # 8.5 Dashboard report
    test_api_get("/api/dashboard/trade-in-report", None, "8.5", "GET /api/dashboard/trade-in-report")


# ============================================================
# SECTION 9: Error Handling
# ============================================================
def test_section_9():
    print_header("9", "Error Handling")

    # 9.1 Invalid Tier Assignment
    try:
        resp = requests.put(f"{BASE_URL}/api/members/99999",
            headers=TENANT_HEADER, json={"tier_id": 99999}, timeout=10)
        if resp.status_code in [400, 404]:
            print_test("9.1", "Invalid tier assignment returns error", True)
        else:
            print_test("9.1", "Invalid tier assignment returns error", False, f"Got status {resp.status_code}")
    except Exception as e:
        print_test("9.1", "Invalid tier assignment returns error", False, str(e))

    # 9.2 Invalid Member ID
    try:
        resp = requests.get(f"{BASE_URL}/api/members/99999", headers=TENANT_HEADER, timeout=10)
        if resp.status_code == 404:
            print_test("9.2", "Non-existent member returns 404", True)
        else:
            print_test("9.2", "Non-existent member returns 404", False, f"Got status {resp.status_code}")
    except Exception as e:
        print_test("9.2", "Non-existent member returns 404", False, str(e))

    # 9.3 Missing Required Fields
    try:
        resp = requests.post(f"{BASE_URL}/api/members",
            headers=TENANT_HEADER, json={}, timeout=10)
        if resp.status_code == 400:
            print_test("9.3", "Missing fields returns 400", True)
        else:
            print_test("9.3", "Missing fields returns 400", False, f"Got status {resp.status_code}")
    except Exception as e:
        print_test("9.3", "Missing fields returns 400", False, str(e))


# ============================================================
# Main
# ============================================================
def main():
    print("\n" + "TRADEUP USER STORY TESTING".center(60, "="))
    print(f"Server: {BASE_URL}")
    print("="*60)

    # Check server is running
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code != 200:
            print("[FAIL] Server not responding correctly")
            return
    except:
        print("[FAIL] Server not running. Start with: python run.py")
        return

    print("[OK] Server is healthy\n")

    # Run all tests
    test_section_1()  # Dashboard
    member_id = test_section_2()  # Members
    test_section_3()  # Tiers
    test_section_4(member_id)  # Trade-Ins
    test_section_5(member_id)  # Store Credit
    test_section_6()  # Cashback
    test_section_7()  # Settings
    test_section_8()  # API Endpoints
    test_section_9()  # Error Handling

    # Summary
    print("\n" + "TEST SUMMARY".center(60, "="))
    print(f"  Passed: {len(results['passed'])}")
    print(f"  Failed: {len(results['failed'])}")
    print(f"  Skipped: {len(results['skipped'])}")

    if results["failed"]:
        print("\n  FAILED TESTS:")
        for f in results["failed"]:
            print(f"    - {f}")

    print("="*60)

    return len(results["failed"]) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
