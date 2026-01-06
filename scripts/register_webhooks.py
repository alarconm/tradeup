#!/usr/bin/env python3
"""
Register Shopify webhooks for TradeUp platform.

Usage:
    python scripts/register_webhooks.py --base-url https://tradeup.cardflowlabs.com --tenant orb

This will register:
    - orders/create → /webhook/orders/create (auto-enrollment, points)
    - orders/paid → /webhook/orders/paid
    - orders/cancelled → /webhook/orders/cancelled
    - customers/create → /webhook/customers/create
    - products/create → /webhook/products/create
"""
import os
import sys
import argparse
import httpx
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_API_VERSION = "2024-01"

WEBHOOKS_TO_REGISTER = [
    {
        "topic": "ORDERS_CREATE",
        "path": "/webhook/orders/create",
        "format": "JSON",
    },
    {
        "topic": "ORDERS_PAID",
        "path": "/webhook/orders/paid",
        "format": "JSON",
    },
    {
        "topic": "ORDERS_CANCELLED",
        "path": "/webhook/orders/cancelled",
        "format": "JSON",
    },
    {
        "topic": "ORDERS_FULFILLED",
        "path": "/webhook/orders/fulfilled",
        "format": "JSON",
    },
    {
        "topic": "CUSTOMERS_CREATE",
        "path": "/webhook/customers/create",
        "format": "JSON",
    },
    {
        "topic": "CUSTOMERS_UPDATE",
        "path": "/webhook/customers/update",
        "format": "JSON",
    },
    {
        "topic": "PRODUCTS_CREATE",
        "path": "/webhook/products/create",
        "format": "JSON",
    },
]


def get_existing_webhooks(shop_domain: str, access_token: str) -> list:
    """Get list of existing webhook subscriptions."""
    url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    query = """
    query {
        webhookSubscriptions(first: 100) {
            edges {
                node {
                    id
                    topic
                    callbackUrl
                    format
                }
            }
        }
    }
    """

    response = httpx.post(url, headers=headers, json={"query": query}, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        print(f"GraphQL errors: {data['errors']}")
        return []

    edges = data.get("data", {}).get("webhookSubscriptions", {}).get("edges", [])
    return [edge["node"] for edge in edges]


def delete_webhook(shop_domain: str, access_token: str, webhook_id: str) -> bool:
    """Delete a webhook subscription."""
    url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    mutation = """
    mutation webhookSubscriptionDelete($id: ID!) {
        webhookSubscriptionDelete(id: $id) {
            userErrors {
                field
                message
            }
            deletedWebhookSubscriptionId
        }
    }
    """

    response = httpx.post(
        url,
        headers=headers,
        json={"query": mutation, "variables": {"id": webhook_id}},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    result = data.get("data", {}).get("webhookSubscriptionDelete", {})
    if result.get("userErrors"):
        print(f"Error deleting webhook: {result['userErrors']}")
        return False

    return True


def register_webhook(
    shop_domain: str, access_token: str, topic: str, callback_url: str, format: str = "JSON"
) -> dict:
    """Register a new webhook subscription."""
    url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    mutation = """
    mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
        webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
            webhookSubscription {
                id
                topic
                callbackUrl
                format
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    variables = {
        "topic": topic,
        "webhookSubscription": {
            "callbackUrl": callback_url,
            "format": format,
        },
    }

    response = httpx.post(
        url, headers=headers, json={"query": mutation, "variables": variables}, timeout=30
    )
    response.raise_for_status()
    data = response.json()

    result = data.get("data", {}).get("webhookSubscriptionCreate", {})
    if result.get("userErrors"):
        return {"success": False, "errors": result["userErrors"]}

    return {"success": True, "webhook": result.get("webhookSubscription")}


def main():
    parser = argparse.ArgumentParser(description="Register Shopify webhooks for TradeUp")
    parser.add_argument("--base-url", required=True, help="Base URL of TradeUp deployment")
    parser.add_argument("--tenant", default="orb", help="Tenant slug (default: orb)")
    parser.add_argument("--clean", action="store_true", help="Delete existing TradeUp webhooks first")
    args = parser.parse_args()

    shop_domain = os.getenv("SHOPIFY_DOMAIN")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")

    if not shop_domain or not access_token:
        print("Error: SHOPIFY_DOMAIN and SHOPIFY_ACCESS_TOKEN must be set in .env")
        sys.exit(1)

    base_url = args.base_url.rstrip("/")
    tenant = args.tenant

    print(f"Shop: {shop_domain}")
    print(f"Base URL: {base_url}")
    print(f"Tenant: {tenant}")
    print()

    # Get existing webhooks
    print("Checking existing webhooks...")
    existing = get_existing_webhooks(shop_domain, access_token)

    # Clean up existing TradeUp webhooks if requested
    if args.clean:
        for webhook in existing:
            if "/webhook/shopify/" in webhook.get("callbackUrl", ""):
                print(f"  Deleting: {webhook['topic']} -> {webhook['callbackUrl']}")
                delete_webhook(shop_domain, access_token, webhook["id"])

    # Register new webhooks
    print()
    print("Registering webhooks...")
    for webhook_config in WEBHOOKS_TO_REGISTER:
        path = webhook_config["path"].format(tenant=tenant)
        callback_url = f"{base_url}{path}"

        # Check if already exists
        existing_match = next(
            (w for w in existing if w["topic"] == webhook_config["topic"] and w["callbackUrl"] == callback_url),
            None,
        )
        if existing_match:
            print(f"  [EXISTS] {webhook_config['topic']} -> {callback_url}")
            continue

        result = register_webhook(
            shop_domain,
            access_token,
            webhook_config["topic"],
            callback_url,
            webhook_config["format"],
        )

        if result["success"]:
            print(f"  [OK] {webhook_config['topic']} -> {callback_url}")
        else:
            print(f"  [FAIL] {webhook_config['topic']}: {result['errors']}")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
