"""
Store Credit Events service.
Port from CardShop for running promotional store credit events like Trade Night.
Enhanced for TradeUp Admin Dashboard with filter-based event builder.
"""
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field, asdict
import httpx


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
        include_authorized: bool = True
    ) -> List[OrderData]:
        """
        Fetch orders in a date range.

        Args:
            start_datetime: ISO format start datetime
            end_datetime: ISO format end datetime
            sources: List of source names to include (e.g., ['pos', 'web'])
            include_authorized: Include authorized (not just paid) orders

        Returns:
            List of OrderData objects
        """
        orders = []
        has_next_page = True
        end_cursor = None

        status_filter = '(displayFinancialStatus:PAID OR displayFinancialStatus:AUTHORIZED)' if include_authorized else 'displayFinancialStatus:PAID'

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
                            }}
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
        include_authorized: bool = True
    ) -> Dict[str, Any]:
        """
        Preview a store credit event without applying credits.

        Returns:
            Preview data including order counts, customer counts, and totals
        """
        orders = self.fetch_orders(start_datetime, end_datetime, sources, include_authorized)
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
        delay_ms: int = 1000
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

        Returns:
            Event results including success/failure counts
        """
        import time

        orders = self.fetch_orders(start_datetime, end_datetime, sources, include_authorized)
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
    """

    def __init__(self, tenant_id: int):
        """Initialize with tenant ID."""
        self.tenant_id = tenant_id
        self._shopify_client = None
        self._events_storage = {}  # In-memory storage for now, use DB in production

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
        List store credit events.

        Returns paginated list of events.
        """
        # For now, return mock data - integrate with database in production
        events = list(self._events_storage.values())

        if status:
            events = [e for e in events if e.get('status') == status]

        # Sort by created_at descending
        events.sort(key=lambda e: e.get('created_at', ''), reverse=True)

        # Paginate
        total = len(events)
        start = (page - 1) * limit
        end = start + limit
        page_events = events[start:end]

        return {
            'events': page_events,
            'total': total,
            'page': page,
            'pages': (total + limit - 1) // limit if total > 0 else 1
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
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run a store credit event.

        Args:
            name: Event name
            description: Event description
            credit_amount: Amount to credit each customer
            filters: Customer filters

        Returns:
            Run result with success status and totals
        """
        import time

        customers = self._get_eligible_customers(filters)
        event_id = str(uuid.uuid4())

        results = []
        successful = 0
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
            except Exception as e:
                errors.append(f"Customer {customer.get('email', customer['id'])}: {str(e)}")

            # Rate limiting
            time.sleep(0.2)

        # Store event record
        event_record = {
            'id': event_id,
            'name': name,
            'description': description,
            'credit_amount': credit_amount,
            'filters': filters,
            'status': 'completed',
            'customers_affected': successful,
            'total_credited': total_credited,
            'created_at': datetime.utcnow().isoformat(),
            'executed_at': datetime.utcnow().isoformat()
        }
        self._events_storage[event_id] = event_record

        return {
            'success': True,
            'event_id': event_id,
            'customers_processed': successful,
            'total_credited': total_credited,
            'errors': errors if errors else None
        }

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event by ID."""
        return self._events_storage.get(event_id)

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
        Filter customers based on their order history.

        This is a simplified implementation. In production, use
        Shopify's order search API with proper filtering.
        """
        if not date_range:
            return customers

        # For now, return all customers - full implementation would
        # query orders and filter based on criteria
        # TODO: Implement full order-based filtering

        return customers

    def _get_customer_tier(self, customer: Dict[str, Any]) -> str:
        """Extract tier from customer tags."""
        tags = customer.get('tags', [])
        for tag in tags:
            if tag.startswith('tu-tier-'):
                tier = tag.replace('tu-tier-', '')
                return tier.capitalize()
        return 'None'
