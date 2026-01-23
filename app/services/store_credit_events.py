"""
Store Credit Events service.
Port from CardShop for running promotional store credit events like Trade Night.
Enhanced for TradeUp Admin Dashboard with filter-based event builder.
"""
import os
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field, asdict
import httpx
from flask import current_app


# Strict datetime pattern for GraphQL injection prevention
# Accepts: 2024-01-15, 2024-01-15T14:30:00, 2024-01-15T14:30:00Z, 2024-01-15T14:30:00+00:00
DATETIME_PATTERN = re.compile(
    r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$'
)


def validate_datetime_string(value: str, field_name: str) -> str:
    """
    Validate and sanitize a datetime string to prevent GraphQL injection.

    Args:
        value: The datetime string to validate
        field_name: Name of the field for error messages

    Returns:
        The validated datetime string

    Raises:
        ValueError: If the datetime format is invalid
    """
    if not value:
        raise ValueError(f'{field_name} is required')

    if not isinstance(value, str):
        raise ValueError(f'{field_name} must be a string')

    # Strip whitespace
    value = value.strip()

    # Check against strict pattern
    if not DATETIME_PATTERN.match(value):
        raise ValueError(
            f'{field_name} has invalid format. '
            f'Expected ISO 8601 format like "2024-01-15" or "2024-01-15T14:30:00"'
        )

    return value


@dataclass
class OrderData:
    """Represents a Shopify order for credit calculation."""
    id: str
    order_number: str
    customer_id: Optional[str]
    customer_email: Optional[str]
    customer_name: Optional[str]
    customer_tags: List[str]
    total_price: Decimal
    source_name: str
    created_at: str
    financial_status: str
    transactions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CustomerCredit:
    """Calculated credit for a customer."""
    customer_id: str
    customer_email: Optional[str]
    customer_name: Optional[str]
    total_spent: Decimal
    credit_amount: Decimal
    order_count: int
    existing_tags: List[str] = field(default_factory=list)


@dataclass
class CreditResult:
    """Result of applying credit to a customer."""
    customer_id: str
    customer_email: Optional[str]
    credit_amount: float
    success: bool
    error: Optional[str] = None
    transaction_id: Optional[str] = None
    skipped: bool = False


class StoreCreditEventsService:
    """
    Service for running promotional store credit events.

    Supports:
    - Fetching orders in a date range
    - Filtering by source (POS, web, shop, etc.)
    - Calculating credits (percentage of order total)
    - Previewing before execution
    - Idempotent credit application with tags
    - Batch processing with rate limiting
    """

    # Source name aliases for matching
    SOURCE_ALIASES = {
        'web': ['online store', 'web'],
        'pos': ['point of sale', 'pos'],
        'shop': ['shop app', 'shop'],
        'ebay': ['ebay'],
        'facebook': ['facebook', 'facebook & instagram', 'instagram'],
        'google': ['google', 'google & youtube', 'youtube'],
    }

    def __init__(self, shop_domain: str, access_token: str, api_version: str = '2024-01'):
        self.shop_domain = shop_domain.replace('https://', '').replace('http://', '').rstrip('/')
        self.access_token = access_token
        self.api_version = api_version
        self.graphql_url = f'https://{self.shop_domain}/admin/api/{api_version}/graphql.json'

    @classmethod
    def from_env(cls) -> 'StoreCreditEventsService':
        """Create service from environment variables."""
        shop_domain = os.getenv('SHOPIFY_DOMAIN')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        if not shop_domain or not access_token:
            raise ValueError('Missing SHOPIFY_DOMAIN or SHOPIFY_ACCESS_TOKEN')
        return cls(shop_domain, access_token)

    def _execute_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }

        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        with httpx.Client() as client:
            response = client.post(
                self.graphql_url,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")

            return result.get('data', {})

    def fetch_orders(
        self,
        start_datetime: str,
        end_datetime: str,
        sources: List[str],
        include_authorized: bool = True,
        collection_ids: Optional[List[str]] = None,
        product_tags: Optional[List[str]] = None
    ) -> List[OrderData]:
        """
        Fetch orders in a date range.

        Args:
            start_datetime: ISO format start datetime
            end_datetime: ISO format end datetime
            sources: List of source names to include (e.g., ['pos', 'web'])
            include_authorized: Include authorized (not just paid) orders
            collection_ids: Optional list of collection GIDs to filter by
            product_tags: Optional list of product tags to filter by

        Returns:
            List of OrderData objects

        Raises:
            ValueError: If datetime parameters have invalid format
        """
        # Validate datetime parameters to prevent GraphQL injection
        start_datetime = validate_datetime_string(start_datetime, 'start_datetime')
        end_datetime = validate_datetime_string(end_datetime, 'end_datetime')

        orders = []
        has_next_page = True
        end_cursor = None

        status_filter = '(displayFinancialStatus:PAID OR displayFinancialStatus:AUTHORIZED)' if include_authorized else 'displayFinancialStatus:PAID'

        # Determine if we need line items for filtering
        need_line_items = bool(collection_ids or product_tags)

        # Build line items clause if needed
        line_items_clause = ""
        if need_line_items:
            line_items_clause = """
                            lineItems(first: 50) {
                                edges {
                                    node {
                                        product {
                                            id
                                            tags
                                            collections(first: 20) {
                                                edges {
                                                    node {
                                                        id
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }"""

        while has_next_page:
            cursor_clause = f'after: "{end_cursor}"' if end_cursor else ''

            query = f"""
            query {{
                orders(
                    first: 250
                    {cursor_clause}
                    query: "created_at:>={start_datetime} AND created_at:<={end_datetime} AND {status_filter}"
                ) {{
                    edges {{
                        node {{
                            id
                            name
                            totalPriceSet {{ shopMoney {{ amount }} }}
                            displayFinancialStatus
                            sourceName
                            createdAt
                            customer {{
                                id
                                email
                                firstName
                                lastName
                                tags
                            }}
                            transactions(first: 25) {{
                                gateway
                                amountSet {{ shopMoney {{ amount }} }}
                            }}{line_items_clause}
                        }}
                    }}
                    pageInfo {{ hasNextPage endCursor }}
                }}
            }}
            """

            result = self._execute_graphql(query)
            page_edges = result.get('orders', {}).get('edges', [])

            # Normalize and expand selected sources
            selected_lower = [s.lower() for s in sources]
            expanded = set(selected_lower)
            for src in selected_lower:
                if src in self.SOURCE_ALIASES:
                    expanded.update(self.SOURCE_ALIASES[src])

            for edge in page_edges:
                node = edge['node']
                source_name = (node.get('sourceName') or '').lower()

                # Check if source matches
                if selected_lower and not any(s in source_name or source_name in expanded for s in expanded):
                    continue

                # Check collection/tag filters if specified
                if need_line_items:
                    matches_filter = False
                    line_items = node.get('lineItems', {}).get('edges', [])

                    for item_edge in line_items:
                        product = item_edge.get('node', {}).get('product')
                        if not product:
                            continue

                        # Check product tags (case-insensitive, null-safe)
                        if product_tags:
                            item_tags = [t.lower() for t in (product.get('tags') or []) if t]
                            if any(tag.lower() in item_tags for tag in product_tags):
                                matches_filter = True
                                break

                        # Check collections
                        if collection_ids:
                            item_collections = product.get('collections', {}).get('edges', [])
                            item_collection_ids = [c.get('node', {}).get('id') for c in item_collections]
                            if any(coll_id in item_collection_ids for coll_id in collection_ids):
                                matches_filter = True
                                break

                    # Skip order if it doesn't match the filter
                    if not matches_filter:
                        continue

                customer = node.get('customer')
                orders.append(OrderData(
                    id=node['id'],
                    order_number=node['name'],
                    customer_id=customer['id'] if customer else None,
                    customer_email=customer.get('email') if customer else None,
                    customer_name=f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip() if customer else None,
                    customer_tags=customer.get('tags', []) if customer else [],
                    total_price=Decimal(str(node['totalPriceSet']['shopMoney']['amount'])),
                    source_name=node.get('sourceName', 'unknown'),
                    created_at=node['createdAt'],
                    financial_status=node['displayFinancialStatus'],
                    transactions=node.get('transactions', [])
                ))

            page_info = result.get('orders', {}).get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            end_cursor = page_info.get('endCursor')

        return orders

    def calculate_credits(
        self,
        orders: List[OrderData],
        credit_percent: float = 10.0,
        exclude_store_credit_payments: bool = True
    ) -> Dict[str, CustomerCredit]:
        """
        Calculate store credits for each customer.

        Args:
            orders: List of orders
            credit_percent: Percentage of order total to credit
            exclude_store_credit_payments: Subtract store credit/gift card payments from total

        Returns:
            Dict mapping customer_id to CustomerCredit
        """
        customer_credits: Dict[str, CustomerCredit] = {}

        for order in orders:
            if not order.customer_id:
                continue

            order_total = order.total_price

            # Subtract store credit / gift card payments
            if exclude_store_credit_payments and order.transactions:
                for tx in order.transactions:
                    gateway = (tx.get('gateway') or '').lower()
                    if 'gift_card' in gateway or 'store_credit' in gateway or 'store credit' in gateway:
                        amount = Decimal(str(tx.get('amountSet', {}).get('shopMoney', {}).get('amount', 0)))
                        order_total -= amount

            order_total = max(Decimal('0'), order_total)
            credit_amount = order_total * Decimal(str(credit_percent / 100))
            credit_amount = credit_amount.quantize(Decimal('0.01'))

            if order.customer_id in customer_credits:
                existing = customer_credits[order.customer_id]
                existing.total_spent += order_total
                existing.credit_amount += credit_amount
                existing.order_count += 1
            else:
                customer_credits[order.customer_id] = CustomerCredit(
                    customer_id=order.customer_id,
                    customer_email=order.customer_email,
                    customer_name=order.customer_name,
                    total_spent=order_total,
                    credit_amount=credit_amount,
                    order_count=1,
                    existing_tags=order.customer_tags
                )

        return customer_credits

    def preview_event(
        self,
        start_datetime: str,
        end_datetime: str,
        sources: List[str],
        credit_percent: float = 10.0,
        include_authorized: bool = True,
        collection_ids: Optional[List[str]] = None,
        product_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Preview a store credit event without applying credits.

        Returns:
            Preview data including order counts, customer counts, and totals
        """
        orders = self.fetch_orders(
            start_datetime, end_datetime, sources, include_authorized,
            collection_ids=collection_ids, product_tags=product_tags
        )
        credits = self.calculate_credits(orders, credit_percent)

        # Orders by source
        by_source: Dict[str, int] = {}
        for order in orders:
            source = order.source_name or 'unknown'
            by_source[source] = by_source.get(source, 0) + 1

        # Top customers
        top_customers = sorted(
            credits.values(),
            key=lambda c: c.credit_amount,
            reverse=True
        )[:10]

        # Orders without customers
        orders_without_customer = len([o for o in orders if not o.customer_id])

        return {
            'start_datetime': start_datetime,
            'end_datetime': end_datetime,
            'sources': sources,
            'credit_percent': credit_percent,
            'total_orders': len(orders),
            'orders_with_customer': len(orders) - orders_without_customer,
            'orders_without_customer': orders_without_customer,
            'unique_customers': len(credits),
            'total_credit_amount': float(sum(c.credit_amount for c in credits.values())),
            'by_source': by_source,
            'top_customers': [
                {
                    'customer_id': c.customer_id,
                    'email': c.customer_email,
                    'name': c.customer_name,
                    'total_spent': float(c.total_spent),
                    'credit_amount': float(c.credit_amount),
                    'order_count': c.order_count
                }
                for c in top_customers
            ]
        }

    def apply_credit(
        self,
        customer_id: str,
        amount: float,
        expires_at: Optional[str] = None
    ) -> CreditResult:
        """
        Apply store credit to a single customer.

        Args:
            customer_id: Shopify customer GID
            amount: Credit amount
            expires_at: Optional expiration datetime

        Returns:
            CreditResult with success/failure info
        """
        gid = customer_id if customer_id.startswith('gid://') else f'gid://shopify/Customer/{customer_id}'

        mutation = """
        mutation storeCreditAccountCredit($id: ID!, $creditInput: StoreCreditAccountCreditInput!) {
            storeCreditAccountCredit(id: $id, creditInput: $creditInput) {
                storeCreditAccountTransaction {
                    id
                    amount { amount currencyCode }
                }
                userErrors { field message }
            }
        }
        """

        variables = {
            'id': gid,
            'creditInput': {
                'creditAmount': {
                    'amount': str(amount),
                    'currencyCode': 'USD'
                }
            }
        }

        if expires_at:
            variables['creditInput']['expiresAt'] = expires_at

        try:
            result = self._execute_graphql(mutation, variables)
            mutation_result = result.get('storeCreditAccountCredit', {})
            user_errors = mutation_result.get('userErrors', [])

            if user_errors:
                return CreditResult(
                    customer_id=gid,
                    customer_email=None,
                    credit_amount=amount,
                    success=False,
                    error=user_errors[0].get('message', 'Unknown error')
                )

            transaction = mutation_result.get('storeCreditAccountTransaction', {})
            return CreditResult(
                customer_id=gid,
                customer_email=None,
                credit_amount=amount,
                success=True,
                transaction_id=transaction.get('id')
            )

        except Exception as e:
            return CreditResult(
                customer_id=gid,
                customer_email=None,
                credit_amount=amount,
                success=False,
                error=str(e)
            )

    def add_customer_tag(self, customer_id: str, tag: str) -> bool:
        """Add a tag to a customer for idempotency tracking."""
        mutation = """
        mutation tagsAdd($id: ID!, $tags: [String!]!) {
            tagsAdd(id: $id, tags: $tags) {
                userErrors { message }
            }
        }
        """

        try:
            result = self._execute_graphql(mutation, {'id': customer_id, 'tags': [tag]})
            return not result.get('tagsAdd', {}).get('userErrors', [])
        except Exception:
            return False

    def run_event(
        self,
        start_datetime: str,
        end_datetime: str,
        sources: List[str],
        credit_percent: float = 10.0,
        include_authorized: bool = True,
        job_id: Optional[str] = None,
        expires_at: Optional[str] = None,
        batch_size: int = 5,
        delay_ms: int = 1000,
        collection_ids: Optional[List[str]] = None,
        product_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run a store credit event (apply credits to all eligible customers).

        Args:
            start_datetime: Event start datetime
            end_datetime: Event end datetime
            sources: Order sources to include
            credit_percent: Percentage to credit
            include_authorized: Include authorized orders
            job_id: Unique job ID for idempotency tagging
            expires_at: Credit expiration datetime
            batch_size: Customers to process per batch
            delay_ms: Delay between batches in milliseconds
            collection_ids: Optional list of collection GIDs to filter by
            product_tags: Optional list of product tags to filter by

        Returns:
            Event results including success/failure counts
        """
        import time

        orders = self.fetch_orders(
            start_datetime, end_datetime, sources, include_authorized,
            collection_ids=collection_ids, product_tags=product_tags
        )
        credits = self.calculate_credits(orders, credit_percent)

        results: List[CreditResult] = []
        customers = list(credits.values())
        idempotency_tag = f'received-credit-{job_id}' if job_id else None

        for i in range(0, len(customers), batch_size):
            batch = customers[i:i + batch_size]

            for customer in batch:
                # Idempotency check
                if idempotency_tag and idempotency_tag in customer.existing_tags:
                    results.append(CreditResult(
                        customer_id=customer.customer_id,
                        customer_email=customer.customer_email,
                        credit_amount=float(customer.credit_amount),
                        success=True,
                        skipped=True,
                        error='Already received credit for this event'
                    ))
                    continue

                result = self.apply_credit(
                    customer.customer_id,
                    float(customer.credit_amount),
                    expires_at
                )
                result.customer_email = customer.customer_email

                # Add idempotency tag on success
                if result.success and idempotency_tag:
                    self.add_customer_tag(customer.customer_id, idempotency_tag)

                results.append(result)

            # Rate limiting between batches
            if i + batch_size < len(customers):
                time.sleep(delay_ms / 1000)

        successful = [r for r in results if r.success and not r.skipped]
        skipped = [r for r in results if r.skipped]
        failed = [r for r in results if not r.success]

        return {
            'event': {
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'sources': sources,
                'credit_percent': credit_percent,
                'job_id': job_id
            },
            'summary': {
                'total_customers': len(customers),
                'successful': len(successful),
                'skipped': len(skipped),
                'failed': len(failed),
                'total_credited': sum(r.credit_amount for r in successful)
            },
            'results': [asdict(r) for r in results]
        }


class StoreCreditEventService:
    """
    New-style event service for TradeUp Admin Dashboard.
    Supports filter-based event creation with flat credit amounts.
    Now uses database persistence for production reliability.
    """

    def __init__(self, tenant_id: int):
        """Initialize with tenant ID."""
        self.tenant_id = tenant_id
        self._shopify_client = None

    @property
    def shopify_client(self):
        """Lazy-load Shopify client."""
        if self._shopify_client is None:
            from .shopify_client import ShopifyClient
            self._shopify_client = ShopifyClient(self.tenant_id)
        return self._shopify_client

    def list_events(
        self,
        page: int = 1,
        limit: int = 15,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List store credit events from database.

        Returns paginated list of events.
        """
        from ..models.promotions import StoreCreditEvent
        from ..extensions import db

        query = StoreCreditEvent.query.filter_by(tenant_id=self.tenant_id)

        if status:
            query = query.filter(StoreCreditEvent.status == status)

        # Sort by created_at descending
        query = query.order_by(StoreCreditEvent.created_at.desc())

        # Paginate
        pagination = query.paginate(page=page, per_page=limit, error_out=False)

        return {
            'events': [e.to_dict() for e in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages if pagination.pages > 0 else 1
        }

    def preview_event(
        self,
        credit_amount: float,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Preview event impact before running.

        Args:
            credit_amount: Flat amount to credit each customer
            filters: Dict with date_range, sources, collections, product_tags, customer_tags, tiers, min_spend

        Returns:
            Preview with customer count, total credit, breakdown
        """
        customers = self._get_eligible_customers(filters)

        # Group by tier
        breakdown_by_tier = {}
        for customer in customers:
            tier = self._get_customer_tier(customer)
            breakdown_by_tier[tier] = breakdown_by_tier.get(tier, 0) + 1

        return {
            'customer_count': len(customers),
            'total_credit': len(customers) * credit_amount,
            'breakdown_by_tier': breakdown_by_tier,
            'sample_customers': [
                {
                    'id': c.get('id', ''),
                    'email': c.get('email', ''),
                    'name': f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(),
                    'tier': self._get_customer_tier(c)
                }
                for c in customers[:10]
            ]
        }

    def run_event(
        self,
        name: str,
        description: str,
        credit_amount: float,
        filters: Dict[str, Any],
        created_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Run a store credit event and persist to database.

        Args:
            name: Event name
            description: Event description
            credit_amount: Amount to credit each customer
            filters: Customer filters
            created_by: Who created the event

        Returns:
            Run result with success status and totals
        """
        import time
        import json
        from ..models.promotions import StoreCreditEvent, StoreCreditEventStatus
        from ..extensions import db

        customers = self._get_eligible_customers(filters)
        event_uuid = str(uuid.uuid4())

        # Create event record in database
        event = StoreCreditEvent(
            tenant_id=self.tenant_id,
            event_uuid=event_uuid,
            name=name,
            description=description,
            credit_amount=credit_amount,
            filters=json.dumps(filters) if filters else None,
            status=StoreCreditEventStatus.RUNNING.value,
            customers_targeted=len(customers),
            idempotency_tag=f'tradeup-event-{event_uuid[:8]}',
            created_by=created_by,
            executed_at=datetime.utcnow()
        )
        db.session.add(event)
        db.session.commit()

        results = []
        successful = 0
        skipped = 0
        failed = 0
        total_credited = 0
        errors = []

        for customer in customers:
            try:
                result = self.shopify_client.add_store_credit(
                    customer_id=customer['id'],
                    amount=credit_amount,
                    note=f"TradeUp Event: {name}"
                )
                if result.get('success'):
                    successful += 1
                    total_credited += credit_amount
                    results.append({
                        'customer_id': customer['id'],
                        'email': customer.get('email'),
                        'success': True,
                        'amount': credit_amount
                    })
                else:
                    failed += 1
                    error_msg = result.get('error', 'Unknown error')
                    errors.append(f"Customer {customer.get('email', customer['id'])}: {error_msg}")
                    results.append({
                        'customer_id': customer['id'],
                        'email': customer.get('email'),
                        'success': False,
                        'error': error_msg
                    })
            except Exception as e:
                failed += 1
                errors.append(f"Customer {customer.get('email', customer['id'])}: {str(e)}")
                results.append({
                    'customer_id': customer['id'],
                    'email': customer.get('email'),
                    'success': False,
                    'error': str(e)
                })

            # Rate limiting
            time.sleep(0.2)

        # Update event record with results
        event.status = StoreCreditEventStatus.COMPLETED.value
        event.customers_processed = successful
        event.customers_skipped = skipped
        event.customers_failed = failed
        event.total_credit_amount = total_credited
        event.execution_results = json.dumps(results)
        event.completed_at = datetime.utcnow()
        if errors:
            event.error_message = '\n'.join(errors[:50])  # Limit stored errors

        db.session.commit()

        return {
            'success': True,
            'event_id': event_uuid,
            'event_db_id': event.id,
            'customers_processed': successful,
            'customers_failed': failed,
            'total_credited': total_credited,
            'errors': errors if errors else None
        }

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event by UUID or database ID."""
        from ..models.promotions import StoreCreditEvent

        # Try UUID first
        event = StoreCreditEvent.query.filter_by(
            tenant_id=self.tenant_id,
            event_uuid=event_id
        ).first()

        # Try database ID if UUID not found
        if not event:
            try:
                event = StoreCreditEvent.query.filter_by(
                    tenant_id=self.tenant_id,
                    id=int(event_id)
                ).first()
            except ValueError:
                pass

        return event.to_dict(include_results=True) if event else None

    def delete_event(self, event_id: str) -> bool:
        """Delete an event by UUID or database ID."""
        from ..models.promotions import StoreCreditEvent
        from ..extensions import db

        event = StoreCreditEvent.query.filter_by(
            tenant_id=self.tenant_id,
            event_uuid=event_id
        ).first()

        if not event:
            try:
                event = StoreCreditEvent.query.filter_by(
                    tenant_id=self.tenant_id,
                    id=int(event_id)
                ).first()
            except ValueError:
                pass

        if event:
            db.session.delete(event)
            db.session.commit()
            return True
        return False

    def _get_eligible_customers(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get customers matching the filters.

        In production, this would use Shopify's customer segment API or
        order queries with GraphQL filtering.
        """
        # Build query from filters
        query_parts = []

        # Tier filter - match TradeUp member tags
        tiers = filters.get('tiers', [])
        if tiers:
            tier_queries = [f"tag:tu-tier-{tier.lower()}" for tier in tiers]
            query_parts.append(f"({' OR '.join(tier_queries)})")

        # Customer tags filter
        customer_tags = filters.get('customer_tags', [])
        if customer_tags:
            tag_queries = [f"tag:{tag}" for tag in customer_tags]
            query_parts.append(f"({' OR '.join(tag_queries)})")

        # Build final query
        search_query = ' AND '.join(query_parts) if query_parts else '*'

        # Fetch customers from Shopify
        customers = self._fetch_customers_by_query(search_query)

        # Apply additional filters that can't be done via Shopify query
        date_range = filters.get('date_range')
        sources = filters.get('sources', [])
        collections = filters.get('collections', [])
        product_tags = filters.get('product_tags', [])
        min_spend = filters.get('min_spend')

        # If we have order-based filters, we need to fetch orders
        if date_range or sources or collections or product_tags or min_spend:
            customers = self._filter_by_orders(
                customers,
                date_range=date_range,
                sources=sources,
                collections=collections,
                product_tags=product_tags,
                min_spend=min_spend
            )

        return customers

    def _fetch_customers_by_query(self, query: str) -> List[Dict[str, Any]]:
        """Fetch customers from Shopify by search query."""
        graphql_query = """
        query getCustomers($query: String!, $first: Int!, $after: String) {
            customers(first: $first, query: $query, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        email
                        firstName
                        lastName
                        tags
                    }
                }
            }
        }
        """

        all_customers = []
        has_next_page = True
        cursor = None

        # Limit to 500 customers for performance
        max_pages = 5

        while has_next_page and max_pages > 0:
            variables = {'query': query, 'first': 100}
            if cursor:
                variables['after'] = cursor

            result = self.shopify_client._execute_query(graphql_query, variables)
            customers_data = result.get('customers', {})

            edges = customers_data.get('edges', [])
            for edge in edges:
                all_customers.append(edge.get('node', {}))

            page_info = customers_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            max_pages -= 1

        return all_customers

    def _filter_by_orders(
        self,
        customers: List[Dict[str, Any]],
        date_range: Optional[Dict[str, str]] = None,
        sources: Optional[List[str]] = None,
        collections: Optional[List[str]] = None,
        product_tags: Optional[List[str]] = None,
        min_spend: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter customers based on their order history using Shopify API.

        Args:
            customers: List of customer dicts from initial filter
            date_range: {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}
            sources: List of order sources ('web', 'pos', etc.)
            collections: List of collection IDs
            product_tags: List of product tags
            min_spend: Minimum total spend amount

        Returns:
            Filtered list of customers matching order criteria
        """
        if not any([date_range, sources, collections, product_tags, min_spend]):
            return customers

        # Build customer ID list for efficient lookup
        customer_ids = {c.get('id'): c for c in customers}
        if not customer_ids:
            return []

        # Build order query
        query_parts = []

        if date_range:
            start = date_range.get('start')
            end = date_range.get('end')
            if start:
                query_parts.append(f'created_at:>={start}')
            if end:
                query_parts.append(f'created_at:<={end}')

        # Add financial status filter
        query_parts.append('(financial_status:paid OR financial_status:authorized)')

        query_string = ' AND '.join(query_parts) if query_parts else ''

        # Fetch orders and aggregate by customer
        customer_order_totals: Dict[str, float] = {}
        customer_sources: Dict[str, set] = {}

        graphql_query = """
        query getOrders($query: String!, $first: Int!, $after: String) {
            orders(first: $first, query: $query, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        customer {
                            id
                        }
                        totalPriceSet {
                            shopMoney {
                                amount
                            }
                        }
                        sourceName
                        lineItems(first: 50) {
                            edges {
                                node {
                                    product {
                                        id
                                        tags
                                        collections(first: 10) {
                                            edges {
                                                node {
                                                    id
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        has_next_page = True
        cursor = None
        max_pages = 10  # Limit pages to prevent timeout

        while has_next_page and max_pages > 0:
            variables = {'query': query_string, 'first': 100}
            if cursor:
                variables['after'] = cursor

            try:
                result = self.shopify_client._execute_query(graphql_query, variables)
                orders_data = result.get('orders', {})
            except Exception as e:
                current_app.logger.error(f"[StoreCreditEvents] Error fetching orders: {e}")
                break

            edges = orders_data.get('edges', [])
            for edge in edges:
                order = edge.get('node', {})
                customer = order.get('customer')
                if not customer:
                    continue

                customer_id = customer.get('id')
                if customer_id not in customer_ids:
                    continue

                # Source filtering
                source_name = (order.get('sourceName') or '').lower()
                if sources:
                    source_aliases = {
                        'web': ['online store', 'web'],
                        'pos': ['point of sale', 'pos'],
                        'shop': ['shop app', 'shop'],
                    }
                    expanded_sources = set()
                    for s in sources:
                        s_lower = s.lower()
                        expanded_sources.add(s_lower)
                        if s_lower in source_aliases:
                            expanded_sources.update(source_aliases[s_lower])

                    if not any(src in source_name or source_name in expanded_sources for src in expanded_sources):
                        continue

                # Collection and product tag filtering
                if collections or product_tags:
                    line_items = order.get('lineItems', {}).get('edges', [])
                    matches_filter = False

                    for item_edge in line_items:
                        product = item_edge.get('node', {}).get('product')
                        if not product:
                            continue

                        # Check product tags (case-insensitive, null-safe)
                        if product_tags:
                            item_tags = [t.lower() for t in (product.get('tags') or []) if t]
                            if any(tag.lower() in item_tags for tag in product_tags):
                                matches_filter = True
                                break

                        # Check collections
                        if collections:
                            item_collections = product.get('collections', {}).get('edges', [])
                            item_collection_ids = [c.get('node', {}).get('id') for c in item_collections]
                            if any(coll in item_collection_ids for coll in collections):
                                matches_filter = True
                                break

                    if (collections or product_tags) and not matches_filter:
                        continue

                # Aggregate order totals
                total = float(order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0))
                customer_order_totals[customer_id] = customer_order_totals.get(customer_id, 0) + total

                if customer_id not in customer_sources:
                    customer_sources[customer_id] = set()
                customer_sources[customer_id].add(source_name)

            page_info = orders_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            max_pages -= 1

        # Apply min_spend filter
        eligible_customer_ids = set(customer_order_totals.keys())
        if min_spend:
            eligible_customer_ids = {
                cid for cid, total in customer_order_totals.items()
                if total >= min_spend
            }

        # Return filtered customers
        return [c for c in customers if c.get('id') in eligible_customer_ids]

    def _get_customer_tier(self, customer: Dict[str, Any]) -> str:
        """Extract tier from customer tags."""
        tags = customer.get('tags', [])
        for tag in tags:
            if tag.startswith('tu-tier-'):
                tier = tag.replace('tu-tier-', '')
                return tier.capitalize()
        return 'None'
