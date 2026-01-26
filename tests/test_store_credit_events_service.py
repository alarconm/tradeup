"""
Comprehensive tests for Store Credit Events Service.

Tests cover:
- Collection filtering logic
- Order fetching with date ranges
- Credit calculation with and without filters
- Preview functionality
- Run functionality with idempotency
- Edge cases
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta

from app.services.store_credit_events import (
    StoreCreditEventsService,
    OrderData,
    CustomerCredit,
    CreditResult,
    validate_datetime_string,
)


class TestDatetimeValidation:
    """Test datetime validation and sanitization."""

    def test_valid_date_only(self):
        """Should accept date-only format."""
        result = validate_datetime_string('2026-01-24', 'test_field')
        assert result == '2026-01-24'

    def test_valid_datetime_with_time(self):
        """Should accept datetime with time."""
        result = validate_datetime_string('2026-01-24T17:00:00', 'test_field')
        assert result == '2026-01-24T17:00:00'

    def test_valid_datetime_with_z(self):
        """Should accept datetime with Z timezone."""
        result = validate_datetime_string('2026-01-24T17:00:00Z', 'test_field')
        assert result == '2026-01-24T17:00:00Z'

    def test_valid_datetime_with_offset(self):
        """Should accept datetime with timezone offset."""
        result = validate_datetime_string('2026-01-24T17:00:00+00:00', 'test_field')
        assert result == '2026-01-24T17:00:00+00:00'

    def test_strips_whitespace(self):
        """Should strip whitespace from input."""
        result = validate_datetime_string('  2026-01-24  ', 'test_field')
        assert result == '2026-01-24'

    def test_rejects_empty_string(self):
        """Should reject empty string."""
        with pytest.raises(ValueError, match='test_field is required'):
            validate_datetime_string('', 'test_field')

    def test_rejects_none(self):
        """Should reject None."""
        with pytest.raises(ValueError, match='test_field is required'):
            validate_datetime_string(None, 'test_field')

    def test_rejects_invalid_format(self):
        """Should reject invalid datetime formats."""
        with pytest.raises(ValueError, match='invalid format'):
            validate_datetime_string('01/24/2026', 'test_field')

    def test_rejects_sql_injection_attempt(self):
        """Should reject SQL/GraphQL injection attempts."""
        with pytest.raises(ValueError, match='invalid format'):
            validate_datetime_string("2026-01-24'; DROP TABLE orders;--", 'test_field')

    def test_rejects_graphql_injection(self):
        """Should reject GraphQL injection attempts."""
        with pytest.raises(ValueError, match='invalid format'):
            validate_datetime_string('2026-01-24" OR 1=1 OR "', 'test_field')


class TestOrderDataModel:
    """Test OrderData dataclass."""

    def test_order_data_creation(self):
        """Should create OrderData with all fields."""
        order = OrderData(
            id='gid://shopify/Order/123',
            order_number='#1001',
            customer_id='gid://shopify/Customer/456',
            customer_email='test@example.com',
            customer_name='Test User',
            customer_tags=['vip', 'member'],
            total_price=Decimal('100.00'),
            source_name='Point of Sale',
            created_at='2026-01-24T17:00:00Z',
            financial_status='paid'
        )
        assert order.id == 'gid://shopify/Order/123'
        assert order.total_price == Decimal('100.00')
        assert order.qualifying_subtotal is None

    def test_order_data_with_qualifying_subtotal(self):
        """Should support qualifying_subtotal for filtered orders."""
        order = OrderData(
            id='gid://shopify/Order/123',
            order_number='#1001',
            customer_id='gid://shopify/Customer/456',
            customer_email='test@example.com',
            customer_name='Test User',
            customer_tags=[],
            total_price=Decimal('100.00'),
            source_name='Point of Sale',
            created_at='2026-01-24T17:00:00Z',
            financial_status='paid',
            qualifying_subtotal=Decimal('60.00'),
            line_items=[{'product_id': 1, 'price': '60.00', 'quantity': 1}]
        )
        assert order.qualifying_subtotal == Decimal('60.00')
        assert len(order.line_items) == 1


class TestCalculateCredits:
    """Test credit calculation logic."""

    def test_basic_credit_calculation(self):
        """Should calculate 10% credit on order total."""
        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id='gid://shopify/Customer/100',
                customer_email='customer@example.com',
                customer_name='Test Customer',
                customer_tags=[],
                total_price=Decimal('100.00'),
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            )
        ]

        credits = service.calculate_credits(orders, credit_percent=10.0)

        assert len(credits) == 1
        customer_credit = credits['gid://shopify/Customer/100']
        assert customer_credit.credit_amount == Decimal('10.00')
        assert customer_credit.total_spent == Decimal('100.00')
        assert customer_credit.order_count == 1

    def test_credit_with_qualifying_subtotal(self):
        """Should use qualifying_subtotal when set (collection filtering)."""
        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id='gid://shopify/Customer/100',
                customer_email='customer@example.com',
                customer_name='Test Customer',
                customer_tags=[],
                total_price=Decimal('100.00'),  # Full order total
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid',
                qualifying_subtotal=Decimal('60.00')  # Only $60 qualifies
            )
        ]

        credits = service.calculate_credits(orders, credit_percent=10.0)

        customer_credit = credits['gid://shopify/Customer/100']
        # Should calculate on $60, not $100
        assert customer_credit.credit_amount == Decimal('6.00')
        assert customer_credit.total_spent == Decimal('60.00')

    def test_multiple_orders_same_customer(self):
        """Should aggregate credits for same customer."""
        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id='gid://shopify/Customer/100',
                customer_email='customer@example.com',
                customer_name='Test Customer',
                customer_tags=[],
                total_price=Decimal('50.00'),
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            ),
            OrderData(
                id='gid://shopify/Order/2',
                order_number='#1002',
                customer_id='gid://shopify/Customer/100',
                customer_email='customer@example.com',
                customer_name='Test Customer',
                customer_tags=[],
                total_price=Decimal('50.00'),
                source_name='pos',
                created_at='2026-01-24T18:00:00Z',
                financial_status='paid'
            )
        ]

        credits = service.calculate_credits(orders, credit_percent=10.0)

        assert len(credits) == 1
        customer_credit = credits['gid://shopify/Customer/100']
        assert customer_credit.credit_amount == Decimal('10.00')  # 10% of $100
        assert customer_credit.total_spent == Decimal('100.00')
        assert customer_credit.order_count == 2

    def test_skips_orders_without_customer(self):
        """Should skip orders without customer_id."""
        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id=None,  # No customer
                customer_email=None,
                customer_name=None,
                customer_tags=[],
                total_price=Decimal('100.00'),
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            )
        ]

        credits = service.calculate_credits(orders, credit_percent=10.0)
        assert len(credits) == 0

    def test_multiple_customers(self):
        """Should calculate separate credits for different customers."""
        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id='gid://shopify/Customer/100',
                customer_email='customer1@example.com',
                customer_name='Customer One',
                customer_tags=[],
                total_price=Decimal('100.00'),
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            ),
            OrderData(
                id='gid://shopify/Order/2',
                order_number='#1002',
                customer_id='gid://shopify/Customer/200',
                customer_email='customer2@example.com',
                customer_name='Customer Two',
                customer_tags=[],
                total_price=Decimal('200.00'),
                source_name='pos',
                created_at='2026-01-24T18:00:00Z',
                financial_status='paid'
            )
        ]

        credits = service.calculate_credits(orders, credit_percent=10.0)

        assert len(credits) == 2
        assert credits['gid://shopify/Customer/100'].credit_amount == Decimal('10.00')
        assert credits['gid://shopify/Customer/200'].credit_amount == Decimal('20.00')

    def test_rounds_to_two_decimal_places(self):
        """Should round credit amounts to 2 decimal places."""
        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id='gid://shopify/Customer/100',
                customer_email='customer@example.com',
                customer_name='Test Customer',
                customer_tags=[],
                total_price=Decimal('33.33'),  # 10% = 3.333
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            )
        ]

        credits = service.calculate_credits(orders, credit_percent=10.0)
        # Should round 3.333 to 3.33
        assert credits['gid://shopify/Customer/100'].credit_amount == Decimal('3.33')


class TestCollectionProductIds:
    """Test collection product ID fetching."""

    def test_empty_collection_ids(self):
        """Should return empty set for empty collection_ids."""
        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service._get_collection_product_ids([])
        assert result == set()

    @patch.object(StoreCreditEventsService, '_execute_rest')
    def test_fetches_products_from_collection(self, mock_rest):
        """Should fetch product IDs from collection."""
        mock_rest.return_value = (
            {'products': [{'id': 123}, {'id': 456}, {'id': 789}]},
            {}  # No pagination
        )

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service._get_collection_product_ids(['gid://shopify/Collection/1001'])

        assert result == {123, 456, 789}
        mock_rest.assert_called_once()

    @patch.object(StoreCreditEventsService, '_execute_rest')
    def test_handles_pagination(self, mock_rest):
        """Should handle paginated results."""
        mock_rest.side_effect = [
            ({'products': [{'id': 1}, {'id': 2}]}, {'link': '<https://test.myshopify.com/next>; rel="next"'}),
            ({'products': [{'id': 3}]}, {})
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service._get_collection_product_ids(['gid://shopify/Collection/1001'])

        assert result == {1, 2, 3}
        assert mock_rest.call_count == 2

    @patch.object(StoreCreditEventsService, '_execute_rest')
    def test_merges_multiple_collections(self, mock_rest):
        """Should merge products from multiple collections."""
        mock_rest.side_effect = [
            ({'products': [{'id': 1}, {'id': 2}]}, {}),
            ({'products': [{'id': 2}, {'id': 3}]}, {})  # ID 2 is in both
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service._get_collection_product_ids([
            'gid://shopify/Collection/1001',
            'gid://shopify/Collection/1002'
        ])

        assert result == {1, 2, 3}  # Deduplicated

    @patch.object(StoreCreditEventsService, '_execute_rest')
    def test_handles_collection_error_gracefully(self, mock_rest):
        """Should continue with other collections if one fails."""
        mock_rest.side_effect = [
            Exception("API Error"),
            ({'products': [{'id': 3}]}, {})
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service._get_collection_product_ids([
            'gid://shopify/Collection/1001',
            'gid://shopify/Collection/1002'
        ])

        # Should still get products from second collection
        assert result == {3}


class TestFetchOrders:
    """Test order fetching with filtering."""

    @patch.object(StoreCreditEventsService, '_fetch_orders_rest')
    @patch.object(StoreCreditEventsService, '_get_collection_product_ids')
    def test_no_collection_filter(self, mock_collection, mock_rest):
        """Should return full order totals when no collection filter."""
        mock_rest.return_value = [
            {
                'id': 1,
                'name': '#1001',
                'total_price': '100.00',
                'source_name': 'Point of Sale',
                'created_at': '2026-01-24T17:00:00Z',
                'financial_status': 'paid',
                'customer': {'id': 100, 'email': 'test@example.com', 'first_name': 'Test', 'last_name': 'User', 'tags': ''},
                'line_items': [{'product_id': 1, 'price': '100.00', 'quantity': 1}]
            }
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = service.fetch_orders(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=['pos']
        )

        assert len(orders) == 1
        assert orders[0].total_price == Decimal('100.00')
        assert orders[0].qualifying_subtotal is None  # No filter
        mock_collection.assert_not_called()

    @patch.object(StoreCreditEventsService, '_fetch_orders_rest')
    @patch.object(StoreCreditEventsService, '_get_collection_product_ids')
    def test_collection_filter_calculates_qualifying_subtotal(self, mock_collection, mock_rest):
        """Should calculate qualifying_subtotal based on collection products."""
        mock_collection.return_value = {1}  # Only product 1 is in collection

        mock_rest.return_value = [
            {
                'id': 1,
                'name': '#1001',
                'total_price': '100.00',
                'source_name': 'Point of Sale',
                'created_at': '2026-01-24T17:00:00Z',
                'financial_status': 'paid',
                'customer': {'id': 100, 'email': 'test@example.com', 'first_name': 'Test', 'last_name': 'User', 'tags': ''},
                'line_items': [
                    {'product_id': 1, 'price': '60.00', 'quantity': 1},  # In collection
                    {'product_id': 2, 'price': '40.00', 'quantity': 1}   # NOT in collection
                ]
            }
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = service.fetch_orders(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=['pos'],
            collection_ids=['gid://shopify/Collection/1001']
        )

        assert len(orders) == 1
        assert orders[0].total_price == Decimal('100.00')
        assert orders[0].qualifying_subtotal == Decimal('60.00')  # Only product 1

    @patch.object(StoreCreditEventsService, '_fetch_orders_rest')
    @patch.object(StoreCreditEventsService, '_get_collection_product_ids')
    def test_collection_filter_skips_non_qualifying_orders(self, mock_collection, mock_rest):
        """Should skip orders with no qualifying items."""
        mock_collection.return_value = {1}  # Only product 1 is in collection

        mock_rest.return_value = [
            {
                'id': 1,
                'name': '#1001',
                'total_price': '100.00',
                'source_name': 'Point of Sale',
                'created_at': '2026-01-24T17:00:00Z',
                'financial_status': 'paid',
                'customer': {'id': 100, 'email': 'test@example.com', 'first_name': 'Test', 'last_name': 'User', 'tags': ''},
                'line_items': [
                    {'product_id': 2, 'price': '50.00', 'quantity': 1},  # NOT in collection
                    {'product_id': 3, 'price': '50.00', 'quantity': 1}   # NOT in collection
                ]
            }
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = service.fetch_orders(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=['pos'],
            collection_ids=['gid://shopify/Collection/1001']
        )

        # Order should be skipped - no qualifying items
        assert len(orders) == 0

    @patch.object(StoreCreditEventsService, '_fetch_orders_rest')
    def test_source_filtering(self, mock_rest):
        """Should filter orders by source."""
        mock_rest.return_value = [
            {
                'id': 1,
                'name': '#1001',
                'total_price': '100.00',
                'source_name': 'Point of Sale',
                'created_at': '2026-01-24T17:00:00Z',
                'financial_status': 'paid',
                'customer': {'id': 100, 'email': 'test@example.com', 'first_name': 'Test', 'last_name': 'User', 'tags': ''},
                'line_items': []
            },
            {
                'id': 2,
                'name': '#1002',
                'total_price': '50.00',
                'source_name': 'web',
                'created_at': '2026-01-24T18:00:00Z',
                'financial_status': 'paid',
                'customer': {'id': 200, 'email': 'other@example.com', 'first_name': 'Other', 'last_name': 'User', 'tags': ''},
                'line_items': []
            }
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = service.fetch_orders(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=['pos']  # Only POS
        )

        assert len(orders) == 1
        assert orders[0].source_name == 'Point of Sale'

    @patch.object(StoreCreditEventsService, '_fetch_orders_rest')
    def test_financial_status_filtering(self, mock_rest):
        """Should filter by financial status."""
        mock_rest.return_value = [
            {
                'id': 1,
                'name': '#1001',
                'total_price': '100.00',
                'source_name': 'pos',
                'created_at': '2026-01-24T17:00:00Z',
                'financial_status': 'paid',
                'customer': {'id': 100, 'email': 'test@example.com', 'first_name': 'Test', 'last_name': 'User', 'tags': ''},
                'line_items': []
            },
            {
                'id': 2,
                'name': '#1002',
                'total_price': '50.00',
                'source_name': 'pos',
                'created_at': '2026-01-24T18:00:00Z',
                'financial_status': 'pending',  # Not paid
                'customer': {'id': 200, 'email': 'other@example.com', 'first_name': 'Other', 'last_name': 'User', 'tags': ''},
                'line_items': []
            }
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        orders = service.fetch_orders(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=[],
            include_authorized=False  # Only paid
        )

        assert len(orders) == 1
        assert orders[0].financial_status == 'paid'


class TestPreviewEvent:
    """Test preview_event functionality."""

    @patch.object(StoreCreditEventsService, 'fetch_orders')
    @patch.object(StoreCreditEventsService, 'calculate_credits')
    def test_preview_returns_all_customers(self, mock_calc, mock_fetch):
        """Should return ALL customers, not limited."""
        mock_fetch.return_value = [
            OrderData(
                id=f'gid://shopify/Order/{i}',
                order_number=f'#{i}',
                customer_id=f'gid://shopify/Customer/{i}',
                customer_email=f'customer{i}@example.com',
                customer_name=f'Customer {i}',
                customer_tags=[],
                total_price=Decimal('100.00'),
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            )
            for i in range(1, 26)  # 25 customers
        ]

        mock_calc.return_value = {
            f'gid://shopify/Customer/{i}': CustomerCredit(
                customer_id=f'gid://shopify/Customer/{i}',
                customer_email=f'customer{i}@example.com',
                customer_name=f'Customer {i}',
                total_spent=Decimal('100.00'),
                credit_amount=Decimal('10.00'),
                order_count=1
            )
            for i in range(1, 26)
        }

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.preview_event(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=['pos'],
            credit_percent=10.0
        )

        # Should return ALL 25 customers, not just top 10
        assert len(result['top_customers']) == 25

    @patch.object(StoreCreditEventsService, 'fetch_orders')
    def test_preview_calculates_totals(self, mock_fetch):
        """Should calculate correct totals."""
        mock_fetch.return_value = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id='gid://shopify/Customer/100',
                customer_email='test@example.com',
                customer_name='Test User',
                customer_tags=[],
                total_price=Decimal('100.00'),
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            ),
            OrderData(
                id='gid://shopify/Order/2',
                order_number='#1002',
                customer_id='gid://shopify/Customer/200',
                customer_email='other@example.com',
                customer_name='Other User',
                customer_tags=[],
                total_price=Decimal('200.00'),
                source_name='web',
                created_at='2026-01-24T18:00:00Z',
                financial_status='paid'
            )
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.preview_event(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=[],
            credit_percent=10.0
        )

        assert result['total_orders'] == 2
        assert result['unique_customers'] == 2
        assert result['total_order_value'] == 300.0
        assert result['total_credit_amount'] == 30.0  # 10% of $300


class TestRunEvent:
    """Test run_event functionality with idempotency."""

    @patch.object(StoreCreditEventsService, 'fetch_orders')
    @patch.object(StoreCreditEventsService, 'apply_credit')
    @patch.object(StoreCreditEventsService, 'add_customer_tag')
    def test_run_applies_credits(self, mock_tag, mock_apply, mock_fetch):
        """Should apply credits to customers."""
        mock_fetch.return_value = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id='gid://shopify/Customer/100',
                customer_email='test@example.com',
                customer_name='Test User',
                customer_tags=[],
                total_price=Decimal('100.00'),
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            )
        ]

        mock_apply.return_value = CreditResult(
            customer_id='gid://shopify/Customer/100',
            customer_email='test@example.com',
            credit_amount=10.0,
            success=True,
            transaction_id='txn_123'
        )
        mock_tag.return_value = True

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.run_event(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=['pos'],
            credit_percent=10.0,
            job_id='test-job-123'
        )

        assert result['summary']['successful'] == 1
        assert result['summary']['total_credited'] == 10.0
        mock_apply.assert_called_once()
        mock_tag.assert_called_once()

    @patch.object(StoreCreditEventsService, 'fetch_orders')
    @patch.object(StoreCreditEventsService, 'apply_credit')
    @patch.object(StoreCreditEventsService, 'add_customer_tag')
    def test_run_skips_already_credited(self, mock_tag, mock_apply, mock_fetch):
        """Should skip customers who already received credit (idempotency)."""
        mock_fetch.return_value = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id='gid://shopify/Customer/100',
                customer_email='test@example.com',
                customer_name='Test User',
                customer_tags=['received-credit-test-job-123'],  # Already has tag
                total_price=Decimal('100.00'),
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            )
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.run_event(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=['pos'],
            credit_percent=10.0,
            job_id='test-job-123'
        )

        assert result['summary']['successful'] == 0
        assert result['summary']['skipped'] == 1
        mock_apply.assert_not_called()  # Should not try to apply

    @patch.object(StoreCreditEventsService, 'fetch_orders')
    @patch.object(StoreCreditEventsService, 'apply_credit')
    def test_run_handles_failures(self, mock_apply, mock_fetch):
        """Should track failed credit applications."""
        mock_fetch.return_value = [
            OrderData(
                id='gid://shopify/Order/1',
                order_number='#1001',
                customer_id='gid://shopify/Customer/100',
                customer_email='test@example.com',
                customer_name='Test User',
                customer_tags=[],
                total_price=Decimal('100.00'),
                source_name='pos',
                created_at='2026-01-24T17:00:00Z',
                financial_status='paid'
            )
        ]

        mock_apply.return_value = CreditResult(
            customer_id='gid://shopify/Customer/100',
            customer_email='test@example.com',
            credit_amount=10.0,
            success=False,
            error='API Error'
        )

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.run_event(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=['pos'],
            credit_percent=10.0
        )

        assert result['summary']['failed'] == 1
        assert result['summary']['successful'] == 0


class TestApplyCredit:
    """Test the apply_credit GraphQL mutation."""

    @patch.object(StoreCreditEventsService, '_execute_graphql')
    def test_apply_credit_success(self, mock_graphql):
        """Should successfully apply credit."""
        mock_graphql.return_value = {
            'storeCreditAccountCredit': {
                'storeCreditAccountTransaction': {
                    'id': 'gid://shopify/StoreCreditAccountTransaction/123',
                    'amount': {'amount': '10.00', 'currencyCode': 'USD'}
                },
                'userErrors': []
            }
        }

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.apply_credit('gid://shopify/Customer/100', 10.0)

        assert result.success is True
        assert result.credit_amount == 10.0
        assert result.transaction_id == 'gid://shopify/StoreCreditAccountTransaction/123'

    @patch.object(StoreCreditEventsService, '_execute_graphql')
    def test_apply_credit_handles_user_errors(self, mock_graphql):
        """Should handle Shopify user errors."""
        mock_graphql.return_value = {
            'storeCreditAccountCredit': {
                'storeCreditAccountTransaction': None,
                'userErrors': [{'message': 'Customer not found', 'field': 'id'}]
            }
        }

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.apply_credit('gid://shopify/Customer/999', 10.0)

        assert result.success is False
        assert result.error == 'Customer not found'

    @patch.object(StoreCreditEventsService, '_execute_graphql')
    def test_apply_credit_handles_exception(self, mock_graphql):
        """Should handle API exceptions."""
        mock_graphql.side_effect = Exception('Network error')

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.apply_credit('gid://shopify/Customer/100', 10.0)

        assert result.success is False
        assert 'Network error' in result.error


class TestIntegrationScenarios:
    """Integration tests for complete scenarios."""

    @patch.object(StoreCreditEventsService, '_execute_rest')
    @patch.object(StoreCreditEventsService, '_execute_graphql')
    def test_full_collection_filtered_flow(self, mock_graphql, mock_rest):
        """Test complete flow: collection filter -> preview -> credit calc."""
        # Setup: Collection 1001 contains products 1, 2, 3 (Sports)
        # Order has products 1 ($60 Sports) and 5 ($40 Pokemon)
        # Should only credit based on $60

        mock_rest.side_effect = [
            # First call: get collection products
            ({'products': [{'id': 1}, {'id': 2}, {'id': 3}]}, {}),
            # Second call: get orders
            ({
                'orders': [{
                    'id': 1,
                    'name': '#1001',
                    'total_price': '100.00',
                    'source_name': 'Point of Sale',
                    'created_at': '2026-01-24T17:00:00Z',
                    'financial_status': 'paid',
                    'customer': {
                        'id': 100,
                        'email': 'test@example.com',
                        'first_name': 'Test',
                        'last_name': 'User',
                        'tags': ''
                    },
                    'line_items': [
                        {'product_id': 1, 'price': '60.00', 'quantity': 1},  # Sports
                        {'product_id': 5, 'price': '40.00', 'quantity': 1}   # Pokemon
                    ]
                }]
            }, {})
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.preview_event(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=['pos'],
            credit_percent=10.0,
            collection_ids=['gid://shopify/Collection/1001']
        )

        # Should calculate credit on $60, not $100
        assert result['total_credit_amount'] == 6.0  # 10% of $60
        assert result['unique_customers'] == 1
        assert len(result['top_customers']) == 1
        assert result['top_customers'][0]['credit_amount'] == 6.0

    @patch.object(StoreCreditEventsService, '_execute_rest')
    def test_mixed_order_filtering(self, mock_rest):
        """Test filtering mixed orders (some qualify, some don't)."""
        mock_rest.side_effect = [
            # Collection products
            ({'products': [{'id': 1}]}, {}),
            # Orders
            ({
                'orders': [
                    {
                        'id': 1,
                        'name': '#1001',
                        'total_price': '100.00',
                        'source_name': 'pos',
                        'created_at': '2026-01-24T17:00:00Z',
                        'financial_status': 'paid',
                        'customer': {'id': 100, 'email': 'a@test.com', 'first_name': 'A', 'last_name': '', 'tags': ''},
                        'line_items': [
                            {'product_id': 1, 'price': '100.00', 'quantity': 1}  # Qualifies
                        ]
                    },
                    {
                        'id': 2,
                        'name': '#1002',
                        'total_price': '50.00',
                        'source_name': 'pos',
                        'created_at': '2026-01-24T18:00:00Z',
                        'financial_status': 'paid',
                        'customer': {'id': 200, 'email': 'b@test.com', 'first_name': 'B', 'last_name': '', 'tags': ''},
                        'line_items': [
                            {'product_id': 99, 'price': '50.00', 'quantity': 1}  # Doesn't qualify
                        ]
                    }
                ]
            }, {})
        ]

        service = StoreCreditEventsService('test.myshopify.com', 'token')
        result = service.preview_event(
            '2026-01-24T17:00:00Z',
            '2026-01-24T20:00:00Z',
            sources=[],
            credit_percent=10.0,
            collection_ids=['gid://shopify/Collection/1001']
        )

        # Only customer A should be included
        assert result['unique_customers'] == 1
        assert result['total_credit_amount'] == 10.0  # 10% of $100
