#!/usr/bin/env python3
"""
TradeUp Store Data Migration Script

Copies products, collections, customers, and orders from a source Shopify store
to a destination store for testing purposes.

Usage:
    python scripts/migrate_store_data.py

Environment variables required:
    SOURCE_SHOP_DOMAIN - e.g., uy288y-nx.myshopify.com
    SOURCE_ACCESS_TOKEN - Admin API access token for source store
    DEST_SHOP_DOMAIN - e.g., your-dev-store.myshopify.com
    DEST_ACCESS_TOKEN - Admin API access token for destination store

To get access tokens:
    1. Go to Shopify Admin > Settings > Apps and sales channels > Develop apps
    2. Create an app with Admin API access
    3. Configure scopes: read_products, write_products, read_customers, write_customers,
       read_orders, write_orders, read_inventory, write_inventory
    4. Install the app and copy the Admin API access token
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
@dataclass
class ShopifyStore:
    domain: str
    access_token: str
    api_version: str = "2024-01"

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}/admin/api/{self.api_version}"

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }


class ShopifyMigrator:
    """Handles migration of data between Shopify stores."""

    def __init__(self, source: ShopifyStore, dest: ShopifyStore):
        self.source = source
        self.dest = dest
        self.product_id_map: Dict[int, int] = {}  # source_id -> dest_id
        self.variant_id_map: Dict[int, int] = {}
        self.customer_id_map: Dict[int, int] = {}
        self.collection_id_map: Dict[int, int] = {}
        self.stats = {
            "products_migrated": 0,
            "products_failed": 0,
            "collections_migrated": 0,
            "collections_failed": 0,
            "customers_migrated": 0,
            "customers_failed": 0,
            "orders_migrated": 0,
            "orders_failed": 0,
        }

    def _get(self, store: ShopifyStore, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request to Shopify API."""
        url = f"{store.base_url}/{endpoint}"
        response = requests.get(url, headers=store.headers, params=params)

        # Handle rate limiting
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", 2))
            print(f"  Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            return self._get(store, endpoint, params)

        response.raise_for_status()
        return response.json()

    def _post(self, store: ShopifyStore, endpoint: str, data: Dict) -> Dict:
        """Make POST request to Shopify API."""
        url = f"{store.base_url}/{endpoint}"
        response = requests.post(url, headers=store.headers, json=data)

        # Handle rate limiting
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", 2))
            print(f"  Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            return self._post(store, endpoint, data)

        if not response.ok:
            print(f"  API Error: {response.status_code} - {response.text[:500]}")

        response.raise_for_status()
        return response.json()

    def _put(self, store: ShopifyStore, endpoint: str, data: Dict) -> Dict:
        """Make PUT request to Shopify API."""
        url = f"{store.base_url}/{endpoint}"
        response = requests.put(url, headers=store.headers, json=data)

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", 2))
            time.sleep(retry_after)
            return self._put(store, endpoint, data)

        response.raise_for_status()
        return response.json()

    def _paginate(self, store: ShopifyStore, endpoint: str, key: str, params: Dict = None) -> List[Dict]:
        """Paginate through all results."""
        results = []
        params = params or {}
        params["limit"] = 250

        while True:
            response = requests.get(
                f"{store.base_url}/{endpoint}",
                headers=store.headers,
                params=params
            )

            if response.status_code == 429:
                time.sleep(float(response.headers.get("Retry-After", 2)))
                continue

            response.raise_for_status()
            data = response.json()

            items = data.get(key, [])
            results.extend(items)

            # Check for next page
            link_header = response.headers.get("Link", "")
            if 'rel="next"' not in link_header:
                break

            # Extract next page URL
            for link in link_header.split(","):
                if 'rel="next"' in link:
                    next_url = link.split(";")[0].strip("<> ")
                    # Extract page_info from URL
                    if "page_info=" in next_url:
                        page_info = next_url.split("page_info=")[1].split("&")[0]
                        params = {"limit": 250, "page_info": page_info}
                    break

        return results

    # ==================== PRODUCTS ====================

    def migrate_products(self, limit: int = None) -> None:
        """Migrate products from source to destination."""
        print("\n" + "="*60)
        print("MIGRATING PRODUCTS")
        print("="*60)

        # Get source products
        print("Fetching products from source store...")
        products = self._paginate(self.source, "products.json", "products")

        if limit:
            products = products[:limit]

        print(f"Found {len(products)} products to migrate")

        for i, product in enumerate(products, 1):
            try:
                print(f"  [{i}/{len(products)}] {product['title'][:50]}...", end=" ")

                source_id = product["id"]

                # Prepare product for creation (remove IDs, timestamps)
                new_product = self._prepare_product_for_import(product)

                # Create in destination
                result = self._post(self.dest, "products.json", {"product": new_product})
                dest_product = result["product"]

                # Map IDs
                self.product_id_map[source_id] = dest_product["id"]

                # Map variant IDs
                for src_var, dest_var in zip(product["variants"], dest_product["variants"]):
                    self.variant_id_map[src_var["id"]] = dest_var["id"]

                self.stats["products_migrated"] += 1
                print("OK")

            except Exception as e:
                self.stats["products_failed"] += 1
                print(f"FAIL Error: {str(e)[:100]}")

        print(f"\nProducts: {self.stats['products_migrated']} migrated, {self.stats['products_failed']} failed")

    def _prepare_product_for_import(self, product: Dict) -> Dict:
        """Prepare a product dict for import (remove IDs, etc)."""
        # Fields to copy
        fields = [
            "title", "body_html", "vendor", "product_type", "tags",
            "template_suffix", "status", "published_scope"
        ]

        new_product = {k: product.get(k) for k in fields if product.get(k) is not None}

        # Handle variants
        if product.get("variants"):
            new_product["variants"] = []
            for var in product["variants"]:
                new_var = {
                    "title": var.get("title"),
                    "price": var.get("price"),
                    "compare_at_price": var.get("compare_at_price"),
                    "sku": var.get("sku"),
                    "barcode": var.get("barcode"),
                    "weight": var.get("weight"),
                    "weight_unit": var.get("weight_unit"),
                    "inventory_management": var.get("inventory_management"),
                    "inventory_policy": var.get("inventory_policy"),
                    "fulfillment_service": var.get("fulfillment_service"),
                    "option1": var.get("option1"),
                    "option2": var.get("option2"),
                    "option3": var.get("option3"),
                    "taxable": var.get("taxable"),
                    "requires_shipping": var.get("requires_shipping"),
                }
                new_product["variants"].append({k: v for k, v in new_var.items() if v is not None})

        # Handle images
        if product.get("images"):
            new_product["images"] = []
            for img in product["images"]:
                new_product["images"].append({
                    "src": img.get("src"),
                    "alt": img.get("alt"),
                    "position": img.get("position"),
                })

        # Handle options
        if product.get("options"):
            new_product["options"] = []
            for opt in product["options"]:
                new_product["options"].append({
                    "name": opt.get("name"),
                    "values": opt.get("values"),
                })

        return new_product

    # ==================== COLLECTIONS ====================

    def migrate_collections(self) -> None:
        """Migrate collections from source to destination."""
        print("\n" + "="*60)
        print("MIGRATING COLLECTIONS")
        print("="*60)

        # Custom collections first
        print("Fetching custom collections...")
        custom_collections = self._paginate(self.source, "custom_collections.json", "custom_collections")
        print(f"Found {len(custom_collections)} custom collections")

        for i, coll in enumerate(custom_collections, 1):
            try:
                print(f"  [{i}/{len(custom_collections)}] {coll['title'][:40]}...", end=" ")

                new_coll = {
                    "title": coll["title"],
                    "body_html": coll.get("body_html"),
                    "sort_order": coll.get("sort_order"),
                    "template_suffix": coll.get("template_suffix"),
                    "published": coll.get("published", True),
                }

                # Add image if present
                if coll.get("image"):
                    new_coll["image"] = {"src": coll["image"].get("src")}

                result = self._post(self.dest, "custom_collections.json", {"custom_collection": new_coll})
                dest_coll = result["custom_collection"]

                self.collection_id_map[coll["id"]] = dest_coll["id"]

                # Add products to collection (collects)
                self._migrate_collection_products(coll["id"], dest_coll["id"])

                self.stats["collections_migrated"] += 1
                print("OK")

            except Exception as e:
                self.stats["collections_failed"] += 1
                print(f"FAIL Error: {str(e)[:100]}")

        # Smart collections
        print("\nFetching smart collections...")
        smart_collections = self._paginate(self.source, "smart_collections.json", "smart_collections")
        print(f"Found {len(smart_collections)} smart collections")

        for i, coll in enumerate(smart_collections, 1):
            try:
                print(f"  [{i}/{len(smart_collections)}] {coll['title'][:40]}...", end=" ")

                new_coll = {
                    "title": coll["title"],
                    "body_html": coll.get("body_html"),
                    "sort_order": coll.get("sort_order"),
                    "template_suffix": coll.get("template_suffix"),
                    "published": coll.get("published", True),
                    "disjunctive": coll.get("disjunctive", False),
                    "rules": coll.get("rules", []),
                }

                if coll.get("image"):
                    new_coll["image"] = {"src": coll["image"].get("src")}

                result = self._post(self.dest, "smart_collections.json", {"smart_collection": new_coll})
                self.collection_id_map[coll["id"]] = result["smart_collection"]["id"]

                self.stats["collections_migrated"] += 1
                print("OK")

            except Exception as e:
                self.stats["collections_failed"] += 1
                print(f"FAIL Error: {str(e)[:100]}")

        print(f"\nCollections: {self.stats['collections_migrated']} migrated, {self.stats['collections_failed']} failed")

    def _migrate_collection_products(self, source_coll_id: int, dest_coll_id: int) -> None:
        """Add products to a custom collection."""
        try:
            collects = self._paginate(
                self.source,
                "collects.json",
                "collects",
                {"collection_id": source_coll_id}
            )

            for collect in collects:
                source_product_id = collect["product_id"]
                dest_product_id = self.product_id_map.get(source_product_id)

                if dest_product_id:
                    try:
                        self._post(self.dest, "collects.json", {
                            "collect": {
                                "collection_id": dest_coll_id,
                                "product_id": dest_product_id
                            }
                        })
                    except:
                        pass  # Product might already be in collection
        except:
            pass

    # ==================== CUSTOMERS ====================

    def migrate_customers(self, limit: int = None) -> None:
        """Migrate customers from source to destination."""
        print("\n" + "="*60)
        print("MIGRATING CUSTOMERS")
        print("="*60)

        print("Fetching customers from source store...")
        customers = self._paginate(self.source, "customers.json", "customers")

        if limit:
            customers = customers[:limit]

        print(f"Found {len(customers)} customers to migrate")

        for i, customer in enumerate(customers, 1):
            try:
                print(f"  [{i}/{len(customers)}] {customer.get('email', 'no-email')[:40]}...", end=" ")

                source_id = customer["id"]

                new_customer = {
                    "first_name": customer.get("first_name"),
                    "last_name": customer.get("last_name"),
                    "email": customer.get("email"),
                    "phone": customer.get("phone"),
                    "tags": customer.get("tags"),
                    "note": customer.get("note"),
                    "tax_exempt": customer.get("tax_exempt", False),
                    "verified_email": True,
                    "send_email_welcome": False,
                }

                # Add addresses
                if customer.get("addresses"):
                    new_customer["addresses"] = []
                    for addr in customer["addresses"]:
                        new_customer["addresses"].append({
                            "address1": addr.get("address1"),
                            "address2": addr.get("address2"),
                            "city": addr.get("city"),
                            "province": addr.get("province"),
                            "country": addr.get("country"),
                            "zip": addr.get("zip"),
                            "phone": addr.get("phone"),
                            "company": addr.get("company"),
                            "first_name": addr.get("first_name"),
                            "last_name": addr.get("last_name"),
                            "default": addr.get("default", False),
                        })

                # Remove None values
                new_customer = {k: v for k, v in new_customer.items() if v is not None}

                result = self._post(self.dest, "customers.json", {"customer": new_customer})
                self.customer_id_map[source_id] = result["customer"]["id"]

                self.stats["customers_migrated"] += 1
                print("OK")

            except Exception as e:
                # Customer might already exist (duplicate email)
                if "has already been taken" in str(e):
                    print("(exists)")
                    # Try to find existing customer
                    try:
                        existing = self._get(
                            self.dest,
                            "customers/search.json",
                            {"query": f"email:{customer.get('email')}"}
                        )
                        if existing.get("customers"):
                            self.customer_id_map[source_id] = existing["customers"][0]["id"]
                    except:
                        pass
                else:
                    self.stats["customers_failed"] += 1
                    print(f"FAIL Error: {str(e)[:100]}")

        print(f"\nCustomers: {self.stats['customers_migrated']} migrated, {self.stats['customers_failed']} failed")

    # ==================== ORDERS ====================

    def migrate_orders(self, days_back: int = 90, limit: int = None) -> None:
        """Migrate orders from source to destination."""
        print("\n" + "="*60)
        print("MIGRATING ORDERS")
        print("="*60)

        # Get orders from last N days
        since_date = (datetime.now() - timedelta(days=days_back)).isoformat()

        print(f"Fetching orders from last {days_back} days...")
        orders = self._paginate(
            self.source,
            "orders.json",
            "orders",
            {"status": "any", "created_at_min": since_date}
        )

        if limit:
            orders = orders[:limit]

        print(f"Found {len(orders)} orders to migrate")

        for i, order in enumerate(orders, 1):
            try:
                source_name = order.get("name", f"#{order['id']}")
                print(f"  [{i}/{len(orders)}] Order {source_name}...", end=" ")

                new_order = self._prepare_order_for_import(order)

                if new_order:
                    result = self._post(self.dest, "orders.json", {"order": new_order})
                    self.stats["orders_migrated"] += 1
                    print("OK")
                else:
                    print("(skipped - no valid items)")

            except Exception as e:
                self.stats["orders_failed"] += 1
                print(f"FAIL Error: {str(e)[:100]}")

        print(f"\nOrders: {self.stats['orders_migrated']} migrated, {self.stats['orders_failed']} failed")

    def _prepare_order_for_import(self, order: Dict) -> Optional[Dict]:
        """Prepare an order for import."""
        # Map customer
        source_customer_id = order.get("customer", {}).get("id")
        dest_customer_id = self.customer_id_map.get(source_customer_id) if source_customer_id else None

        # Build line items
        line_items = []
        for item in order.get("line_items", []):
            source_variant_id = item.get("variant_id")
            dest_variant_id = self.variant_id_map.get(source_variant_id)

            if dest_variant_id:
                line_items.append({
                    "variant_id": dest_variant_id,
                    "quantity": item.get("quantity", 1),
                    "price": item.get("price"),
                })
            else:
                # Create custom line item if variant not found
                line_items.append({
                    "title": item.get("title", "Unknown Item"),
                    "quantity": item.get("quantity", 1),
                    "price": item.get("price", "0.00"),
                })

        if not line_items:
            return None

        # Sanitize tags - convert to string if needed
        tags = order.get("tags")
        if tags and isinstance(tags, list):
            tags = ", ".join(str(t) for t in tags)
        elif tags and not isinstance(tags, str):
            tags = str(tags)

        new_order = {
            "line_items": line_items,
            "financial_status": "paid",
            "fulfillment_status": order.get("fulfillment_status"),
            "source_name": order.get("source_name", "web"),
            "note": order.get("note"),
            "processed_at": order.get("created_at"),
            "send_receipt": False,
            "send_fulfillment_receipt": False,
            "inventory_behaviour": "bypass",  # Don't affect inventory
        }

        # Only add tags if valid
        if tags and isinstance(tags, str) and tags.strip():
            new_order["tags"] = tags

        if dest_customer_id:
            new_order["customer"] = {"id": dest_customer_id}
        elif order.get("email"):
            new_order["email"] = order.get("email")

        # Add shipping address if present
        if order.get("shipping_address"):
            addr = order["shipping_address"]
            new_order["shipping_address"] = {
                "first_name": addr.get("first_name"),
                "last_name": addr.get("last_name"),
                "address1": addr.get("address1"),
                "address2": addr.get("address2"),
                "city": addr.get("city"),
                "province": addr.get("province"),
                "country": addr.get("country"),
                "zip": addr.get("zip"),
                "phone": addr.get("phone"),
            }

        # Add billing address if present
        if order.get("billing_address"):
            addr = order["billing_address"]
            new_order["billing_address"] = {
                "first_name": addr.get("first_name"),
                "last_name": addr.get("last_name"),
                "address1": addr.get("address1"),
                "address2": addr.get("address2"),
                "city": addr.get("city"),
                "province": addr.get("province"),
                "country": addr.get("country"),
                "zip": addr.get("zip"),
                "phone": addr.get("phone"),
            }

        return new_order

    # ==================== MAIN ====================

    def run_full_migration(
        self,
        products: bool = True,
        collections: bool = True,
        customers: bool = True,
        orders: bool = True,
        product_limit: int = None,
        customer_limit: int = None,
        order_limit: int = None,
        order_days: int = 90
    ) -> Dict:
        """Run complete migration."""
        print("\n" + "="*60)
        print("SHOPIFY STORE MIGRATION")
        print("="*60)
        print(f"Source: {self.source.domain}")
        print(f"Destination: {self.dest.domain}")
        print("="*60)

        start_time = datetime.now()

        if products:
            self.migrate_products(limit=product_limit)

        if collections:
            self.migrate_collections()

        if customers:
            self.migrate_customers(limit=customer_limit)

        if orders:
            self.migrate_orders(days_back=order_days, limit=order_limit)

        elapsed = datetime.now() - start_time

        print("\n" + "="*60)
        print("MIGRATION COMPLETE")
        print("="*60)
        print(f"Time elapsed: {elapsed}")
        print(f"Products: {self.stats['products_migrated']} migrated, {self.stats['products_failed']} failed")
        print(f"Collections: {self.stats['collections_migrated']} migrated, {self.stats['collections_failed']} failed")
        print(f"Customers: {self.stats['customers_migrated']} migrated, {self.stats['customers_failed']} failed")
        print(f"Orders: {self.stats['orders_migrated']} migrated, {self.stats['orders_failed']} failed")

        # Save ID mappings for reference
        mappings = {
            "product_id_map": self.product_id_map,
            "variant_id_map": self.variant_id_map,
            "customer_id_map": self.customer_id_map,
            "collection_id_map": self.collection_id_map,
            "stats": self.stats,
        }

        mapping_file = f"migration_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(mapping_file, "w") as f:
            json.dump(mappings, f, indent=2, default=str)
        print(f"\nID mappings saved to: {mapping_file}")

        return self.stats


def main():
    """Main entry point."""
    # Check for required environment variables
    required_vars = [
        "SOURCE_SHOP_DOMAIN",
        "SOURCE_ACCESS_TOKEN",
        "DEST_SHOP_DOMAIN",
        "DEST_ACCESS_TOKEN"
    ]

    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        print("Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nTo set these, create a .env.migration file or export them:")
        print("""
export SOURCE_SHOP_DOMAIN=uy288y-nx.myshopify.com
export SOURCE_ACCESS_TOKEN=shpat_xxxxx
export DEST_SHOP_DOMAIN=your-dev-store.myshopify.com
export DEST_ACCESS_TOKEN=shpat_xxxxx
        """)
        print("\nTo get access tokens:")
        print("1. Go to Shopify Admin > Settings > Apps and sales channels > Develop apps")
        print("2. Create/select an app")
        print("3. Configure Admin API scopes (see script header)")
        print("4. Install app and copy Admin API access token")
        sys.exit(1)

    # Create store objects
    source = ShopifyStore(
        domain=os.environ["SOURCE_SHOP_DOMAIN"],
        access_token=os.environ["SOURCE_ACCESS_TOKEN"]
    )

    dest = ShopifyStore(
        domain=os.environ["DEST_SHOP_DOMAIN"],
        access_token=os.environ["DEST_ACCESS_TOKEN"]
    )

    # Confirm before proceeding
    print(f"\nThis will copy data from:")
    print(f"  Source: {source.domain}")
    print(f"  To: {dest.domain}")
    print("\nWARNING: This will create new products, customers, and orders in the destination store.")

    confirm = input("\nType 'yes' to proceed: ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        sys.exit(0)

    # Run migration
    migrator = ShopifyMigrator(source, dest)
    migrator.run_full_migration(
        products=True,
        collections=True,
        customers=True,
        orders=True,
        order_days=180,  # Last 6 months of orders
    )


if __name__ == "__main__":
    main()
