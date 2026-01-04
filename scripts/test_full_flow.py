#!/usr/bin/env python3
"""
Test the complete Quick Flip flow locally.

This simulates:
1. Creating a member
2. Recording a trade-in
3. Marking item as listed in Shopify
4. Simulating an order/paid webhook from Shopify
5. Processing the bonus
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000"
TENANT_HEADER = {"X-Tenant-ID": "1"}

def print_step(step, title):
    print(f"\n{'='*60}")
    print(f"STEP {step}: {title}")
    print('='*60)

def print_response(label, data):
    print(f"\n{label}:")
    print(json.dumps(data, indent=2, default=str))

def main():
    print("\n" + "🚀 QUICK FLIP FULL FLOW TEST ".center(60, "="))

    # Step 1: Create a test member
    print_step(1, "Create Test Member (Gold Tier)")

    member_resp = requests.post(
        f"{BASE_URL}/api/members",
        headers={**TENANT_HEADER, "Content-Type": "application/json"},
        json={
            "email": "testmember@example.com",
            "name": "Test Gold Member",
            "tier_id": 2  # Gold tier
        }
    )

    if member_resp.status_code == 201:
        member = member_resp.json()
        print_response("✅ Member Created", member)
        member_id = member["id"]
        member_number = member["member_number"]
    else:
        # Member might already exist, try to get by email
        print(f"Member creation returned {member_resp.status_code}, checking if exists...")
        members_resp = requests.get(f"{BASE_URL}/api/members", headers=TENANT_HEADER)
        members = members_resp.json()["members"]
        member = next((m for m in members if m["email"] == "testmember@example.com"), None)
        if member:
            member_id = member["id"]
            member_number = member["member_number"]
            print_response("📋 Using Existing Member", member)
        else:
            print("❌ Failed to create or find member")
            return

    # Step 2: Create a trade-in batch
    print_step(2, "Create Trade-In Batch")

    batch_resp = requests.post(
        f"{BASE_URL}/api/trade-ins",
        headers={**TENANT_HEADER, "Content-Type": "application/json"},
        json={
            "member_id": member_id,
            "notes": "Full flow test batch"
        }
    )
    batch = batch_resp.json()
    print_response("✅ Batch Created", batch)
    batch_id = batch["id"]

    # Step 3: Add items to the batch
    print_step(3, "Add Trade-In Items")

    items_resp = requests.post(
        f"{BASE_URL}/api/trade-ins/{batch_id}/items",
        headers={**TENANT_HEADER, "Content-Type": "application/json"},
        json={
            "items": [
                {"product_title": "Pikachu VMAX Alt Art", "trade_value": 150.00},
                {"product_title": "Charizard UPC Promo", "trade_value": 80.00},
            ]
        }
    )
    items_data = items_resp.json()
    print_response("✅ Items Added", items_data)

    # Get item IDs
    item_ids = [item["id"] for item in items_data["items"]]

    # Step 4: Mark items as listed in Shopify (simulating ORB_repo push)
    print_step(4, "Mark Items as Listed in Shopify")

    # Simulate Shopify product IDs
    shopify_products = [
        {"id": "gid://shopify/Product/1111111111", "price": 200.00},
        {"id": "gid://shopify/Product/2222222222", "price": 120.00},
    ]

    for i, item_id in enumerate(item_ids):
        listed_resp = requests.put(
            f"{BASE_URL}/api/trade-ins/items/{item_id}/listed",
            headers={**TENANT_HEADER, "Content-Type": "application/json"},
            json={
                "shopify_product_id": shopify_products[i]["id"],
                "listing_price": shopify_products[i]["price"]
            }
        )
        print(f"  Item {item_id} listed: {listed_resp.json()['product_title']} @ ${shopify_products[i]['price']}")

    # Step 5: Simulate Shopify order/paid webhook
    print_step(5, "Simulate Shopify Order/Paid Webhook")

    # Build a realistic Shopify webhook payload
    webhook_payload = {
        "id": 5555555555,
        "order_number": 1234,
        "financial_status": "paid",
        "total_price": "320.00",
        "customer": {
            "id": 9999999999,
            "email": "buyer@example.com"
        },
        "line_items": [
            {
                "id": 11111,
                "product_id": 1111111111,  # Matches our Pikachu
                "title": "Pikachu VMAX Alt Art",
                "price": "195.00",  # Sold for $195 (profit = $195 - $150 = $45)
                "quantity": 1,
                "sku": "PKM-001"
            },
            {
                "id": 22222,
                "product_id": 2222222222,  # Matches our Charizard
                "title": "Charizard UPC Promo",
                "price": "115.00",  # Sold for $115 (profit = $115 - $80 = $35)
                "quantity": 1,
                "sku": "PKM-002"
            }
        ]
    }

    # The webhook expects tenant slug in URL
    webhook_resp = requests.post(
        f"{BASE_URL}/webhook/shopify/orb/order-paid",
        headers={"Content-Type": "application/json"},
        json=webhook_payload
    )
    print_response("📨 Webhook Response", webhook_resp.json())

    # Step 6: Check pending bonuses
    print_step(6, "Check Pending Bonuses")

    pending_resp = requests.get(
        f"{BASE_URL}/api/bonuses/pending",
        headers=TENANT_HEADER
    )
    pending = pending_resp.json()
    print_response("📋 Pending Bonuses", pending)

    # Step 7: Calculate bonuses for each item
    print_step(7, "Calculate Individual Bonuses")

    for item_id in item_ids:
        calc_resp = requests.get(
            f"{BASE_URL}/api/bonuses/calculate/{item_id}",
            headers=TENANT_HEADER
        )
        calc = calc_resp.json()
        print(f"\n  Item {item_id}: {calc.get('calculation', {}).get('tier_name', 'N/A')} tier")
        if calc.get("eligible"):
            print(f"    ✅ Eligible! Bonus: ${calc['bonus_amount']:.2f}")
            print(f"    Profit: ${calc['calculation']['profit']:.2f} × {calc['calculation']['bonus_rate']*100:.0f}% = ${calc['bonus_amount']:.2f}")
        else:
            print(f"    ❌ Not eligible: {calc.get('reason', 'Unknown')}")

    # Step 8: Process bonuses (dry run)
    print_step(8, "Process Bonuses (Dry Run)")

    process_resp = requests.post(
        f"{BASE_URL}/api/bonuses/process",
        headers={**TENANT_HEADER, "Content-Type": "application/json"},
        json={"dry_run": True}
    )
    process_result = process_resp.json()
    print_response("🔍 Dry Run Results", process_result)

    # Summary
    print("\n" + "📊 TEST SUMMARY ".center(60, "="))
    print(f"""
Member: {member.get('name')} ({member_number})
Tier: Gold (20% bonus rate)
Items Traded: 2
Total Trade Value: $230.00

Expected Bonuses (if sold within 7 days):
  - Pikachu VMAX: $195 - $150 = $45 profit × 20% = $9.00 bonus
  - Charizard UPC: $115 - $80 = $35 profit × 20% = $7.00 bonus

Total Expected Bonus: $16.00

Actual Results from API:
  - Processed: {process_result.get('processed', 0)}
  - Would Issue: ${process_result.get('total_bonus_amount', 0):.2f}
""")

    print("\n✅ Full flow test complete!")
    print("\nTo issue bonuses for real (with store credit), run:")
    print('  curl -X POST http://localhost:5000/api/bonuses/process -H "Content-Type: application/json" -d \'{"dry_run": false}\'')


if __name__ == "__main__":
    main()
