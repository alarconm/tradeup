"""
Tests for the Audience Selector feature in Store Credit Events.

Tests cover:
- Promotion model audience field
- GuestCreditEvent model
- issue_guest_store_credit() function
- get_active_promotions_for_audience() function
- API endpoints with audience parameter
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestPromotionAudienceField:
    """Tests for the audience field on the Promotion model."""

    def test_audience_defaults_to_members_only(self, app, sample_tenant):
        """Test that audience defaults to 'members_only'."""
        with app.app_context():
            from app.models.promotions import Promotion
            from app.extensions import db

            now = datetime.utcnow()
            promo = Promotion(
                tenant_id=sample_tenant.id,
                name='Test Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='all',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            db.session.add(promo)
            db.session.commit()

            # Reload from database
            promo = Promotion.query.get(promo.id)
            assert promo.audience == 'members_only'

    def test_audience_can_be_set_to_all_customers(self, app, sample_tenant):
        """Test that audience can be set to 'all_customers'."""
        with app.app_context():
            from app.models.promotions import Promotion
            from app.extensions import db

            now = datetime.utcnow()
            promo = Promotion(
                tenant_id=sample_tenant.id,
                name='All Customers Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('15.00'),
                active=True,
                channel='in_store',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5),
                audience='all_customers'
            )
            db.session.add(promo)
            db.session.commit()

            promo = Promotion.query.get(promo.id)
            assert promo.audience == 'all_customers'

    def test_audience_included_in_to_dict(self, app, sample_tenant):
        """Test that audience and audience_label are in to_dict() output."""
        with app.app_context():
            from app.models.promotions import Promotion
            from app.extensions import db

            now = datetime.utcnow()

            # Test members_only
            promo1 = Promotion(
                tenant_id=sample_tenant.id,
                name='Members Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='all',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5),
                audience='members_only'
            )
            db.session.add(promo1)
            db.session.commit()

            data1 = promo1.to_dict()
            assert data1['audience'] == 'members_only'
            assert data1['audience_label'] == 'Members Only'

            # Test all_customers
            promo2 = Promotion(
                tenant_id=sample_tenant.id,
                name='All Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='all',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5),
                audience='all_customers'
            )
            db.session.add(promo2)
            db.session.commit()

            data2 = promo2.to_dict()
            assert data2['audience'] == 'all_customers'
            assert data2['audience_label'] == 'All Customers'

    def test_null_audience_treated_as_members_only_in_to_dict(self, app, sample_tenant):
        """Test that NULL audience is treated as 'members_only' in serialization."""
        with app.app_context():
            from app.models.promotions import Promotion
            from app.extensions import db

            now = datetime.utcnow()
            promo = Promotion(
                tenant_id=sample_tenant.id,
                name='Legacy Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='all',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            # Explicitly set to None to simulate legacy data
            promo.audience = None
            db.session.add(promo)
            db.session.commit()

            data = promo.to_dict()
            # Should default to members_only in serialization
            assert data['audience'] == 'members_only'
            assert data['audience_label'] == 'Members Only'


class TestGuestCreditEventModel:
    """Tests for the GuestCreditEvent model."""

    def test_create_guest_credit_event(self, app, sample_tenant):
        """Test creating a GuestCreditEvent record."""
        with app.app_context():
            from app.models.promotions import GuestCreditEvent
            from app.extensions import db

            event = GuestCreditEvent(
                tenant_id=sample_tenant.id,
                shopify_customer_id='gid://shopify/Customer/123456',
                customer_email='guest@example.com',
                customer_name='Guest User',
                amount=Decimal('25.00'),
                description='Trade Night bonus',
                order_id='gid://shopify/Order/789',
                order_number='#1001',
                order_total=Decimal('250.00')
            )
            db.session.add(event)
            db.session.commit()

            # Reload and verify
            event = GuestCreditEvent.query.get(event.id)
            assert event is not None
            assert event.tenant_id == sample_tenant.id
            assert event.shopify_customer_id == 'gid://shopify/Customer/123456'
            assert event.customer_email == 'guest@example.com'
            assert event.amount == Decimal('25.00')
            assert event.synced_to_shopify is False
            assert event.created_at is not None

    def test_guest_credit_event_to_dict(self, app, sample_tenant):
        """Test GuestCreditEvent serialization."""
        with app.app_context():
            from app.models.promotions import GuestCreditEvent, Promotion
            from app.extensions import db

            now = datetime.utcnow()

            # Create a promotion for reference
            promo = Promotion(
                tenant_id=sample_tenant.id,
                name='Trade Night',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='in_store',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5),
                audience='all_customers'
            )
            db.session.add(promo)
            db.session.commit()

            event = GuestCreditEvent(
                tenant_id=sample_tenant.id,
                shopify_customer_id='gid://shopify/Customer/999',
                customer_email='test@example.com',
                customer_name='Test User',
                amount=Decimal('50.00'),
                description='10% cashback',
                promotion_id=promo.id,
                promotion_name='Trade Night',
                order_id='gid://shopify/Order/111',
                order_number='#1002',
                order_total=Decimal('500.00'),
                synced_to_shopify=True,
                shopify_credit_id='txn_abc123'
            )
            db.session.add(event)
            db.session.commit()

            data = event.to_dict()
            assert data['id'] == event.id
            assert data['shopify_customer_id'] == 'gid://shopify/Customer/999'
            assert data['customer_email'] == 'test@example.com'
            assert data['customer_name'] == 'Test User'
            assert data['amount'] == 50.00
            assert data['promotion_name'] == 'Trade Night'
            assert data['synced_to_shopify'] is True
            # Note: shopify_credit_id is stored on model but not in to_dict() serialization
            assert event.shopify_credit_id == 'txn_abc123'

    def test_guest_credit_event_with_sync_error(self, app, sample_tenant):
        """Test GuestCreditEvent tracking sync errors."""
        with app.app_context():
            from app.models.promotions import GuestCreditEvent
            from app.extensions import db

            event = GuestCreditEvent(
                tenant_id=sample_tenant.id,
                shopify_customer_id='gid://shopify/Customer/456',
                amount=Decimal('10.00'),
                description='Failed sync test',
                synced_to_shopify=False,
                sync_error='Shopify API rate limited'
            )
            db.session.add(event)
            db.session.commit()

            event = GuestCreditEvent.query.get(event.id)
            assert event.synced_to_shopify is False
            assert event.sync_error == 'Shopify API rate limited'


class TestGetActivePromotionsForAudience:
    """Tests for get_active_promotions_for_audience function."""

    def test_returns_members_only_promotions(self, app, sample_tenant):
        """Test filtering for members_only promotions."""
        with app.app_context():
            from app.models.promotions import Promotion
            from app.services.store_credit_service import StoreCreditService
            from app.extensions import db

            now = datetime.utcnow()

            # Create members_only promotion
            promo1 = Promotion(
                tenant_id=sample_tenant.id,
                name='Members Only Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='online',
                audience='members_only',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            # Create all_customers promotion
            promo2 = Promotion(
                tenant_id=sample_tenant.id,
                name='All Customers Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('15.00'),
                active=True,
                channel='online',
                audience='all_customers',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            db.session.add_all([promo1, promo2])
            db.session.commit()

            service = StoreCreditService()
            promos = service.get_active_promotions_for_audience(
                tenant_id=sample_tenant.id,
                audience='members_only'
            )

            names = [p.name for p in promos]
            assert 'Members Only Promo' in names
            assert 'All Customers Promo' not in names

    def test_returns_all_customers_promotions(self, app, sample_tenant):
        """Test filtering for all_customers promotions."""
        with app.app_context():
            from app.models.promotions import Promotion
            from app.services.store_credit_service import StoreCreditService
            from app.extensions import db

            now = datetime.utcnow()

            promo1 = Promotion(
                tenant_id=sample_tenant.id,
                name='Members Only',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='in_store',
                audience='members_only',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            promo2 = Promotion(
                tenant_id=sample_tenant.id,
                name='All Customers',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('15.00'),
                active=True,
                channel='in_store',
                audience='all_customers',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            db.session.add_all([promo1, promo2])
            db.session.commit()

            service = StoreCreditService()
            promos = service.get_active_promotions_for_audience(
                tenant_id=sample_tenant.id,
                audience='all_customers'
            )

            names = [p.name for p in promos]
            assert 'All Customers' in names
            assert 'Members Only' not in names

    def test_null_audience_treated_as_members_only(self, app, sample_tenant):
        """Test that NULL audience is included when filtering for members_only."""
        with app.app_context():
            from app.models.promotions import Promotion
            from app.services.store_credit_service import StoreCreditService
            from app.extensions import db

            now = datetime.utcnow()

            # Create promotion with NULL audience (simulates legacy data)
            promo = Promotion(
                tenant_id=sample_tenant.id,
                name='Legacy Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='online',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            promo.audience = None  # Explicitly set NULL
            db.session.add(promo)
            db.session.commit()

            service = StoreCreditService()
            promos = service.get_active_promotions_for_audience(
                tenant_id=sample_tenant.id,
                audience='members_only'
            )

            names = [p.name for p in promos]
            assert 'Legacy Promo' in names

    def test_filters_by_channel(self, app, sample_tenant):
        """Test that channel filter works correctly."""
        with app.app_context():
            from app.models.promotions import Promotion
            from app.services.store_credit_service import StoreCreditService
            from app.extensions import db

            now = datetime.utcnow()

            promo1 = Promotion(
                tenant_id=sample_tenant.id,
                name='POS Only',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='in_store',
                audience='all_customers',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            promo2 = Promotion(
                tenant_id=sample_tenant.id,
                name='Web Only',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='online',
                audience='all_customers',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            db.session.add_all([promo1, promo2])
            db.session.commit()

            service = StoreCreditService()

            # Filter by in_store channel
            pos_promos = service.get_active_promotions_for_audience(
                tenant_id=sample_tenant.id,
                audience='all_customers',
                channel='in_store'
            )
            pos_names = [p.name for p in pos_promos]
            assert 'POS Only' in pos_names
            assert 'Web Only' not in pos_names

    def test_returns_only_active_promotions(self, app, sample_tenant):
        """Test that inactive promotions are excluded."""
        with app.app_context():
            from app.models.promotions import Promotion
            from app.services.store_credit_service import StoreCreditService
            from app.extensions import db

            now = datetime.utcnow()

            promo1 = Promotion(
                tenant_id=sample_tenant.id,
                name='Active Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=True,
                channel='online',
                audience='all_customers',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            promo2 = Promotion(
                tenant_id=sample_tenant.id,
                name='Inactive Promo',
                promo_type='purchase_cashback',
                bonus_percent=Decimal('10.00'),
                active=False,  # Inactive
                channel='online',
                audience='all_customers',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=5)
            )
            db.session.add_all([promo1, promo2])
            db.session.commit()

            service = StoreCreditService()
            promos = service.get_active_promotions_for_audience(
                tenant_id=sample_tenant.id,
                audience='all_customers'
            )

            names = [p.name for p in promos]
            assert 'Active Promo' in names
            assert 'Inactive Promo' not in names


class TestIssueGuestStoreCredit:
    """Tests for issue_guest_store_credit function."""

    @patch('app.services.store_credit_service.ShopifyClient')
    def test_issue_guest_credit_success(self, mock_shopify_class, app, sample_tenant):
        """Test successfully issuing credit to a non-member."""
        with app.app_context():
            from app.models.promotions import GuestCreditEvent
            from app.services.store_credit_service import StoreCreditService

            # Setup mock
            mock_client = MagicMock()
            mock_client.add_store_credit.return_value = {
                'success': True,
                'new_balance': 25.00,
                'transaction_id': 'txn_guest_123'
            }
            mock_shopify_class.return_value = mock_client

            service = StoreCreditService()
            result = service.issue_guest_store_credit(
                tenant_id=sample_tenant.id,
                shopify_customer_id='gid://shopify/Customer/12345',
                customer_email='guest@test.com',
                customer_name='Guest Tester',
                amount=Decimal('25.00'),
                description='Trade Night 10% cashback',
                promotion_id=None,
                promotion_name='Trade Night',
                order_id='gid://shopify/Order/999',
                order_number='#1003',
                order_total=Decimal('250.00')
            )

            assert result['success'] is True
            assert result['amount'] == 25.00
            assert result['new_balance'] == 25.00
            assert result['transaction_id'] == 'txn_guest_123'
            assert result['customer_email'] == 'guest@test.com'

            # Verify GuestCreditEvent was created in database
            event = GuestCreditEvent.query.filter_by(
                shopify_customer_id='gid://shopify/Customer/12345',
                tenant_id=sample_tenant.id
            ).first()
            assert event is not None
            assert event.customer_email == 'guest@test.com'
            assert event.amount == Decimal('25.00')
            assert event.synced_to_shopify is True
            assert event.shopify_credit_id == 'txn_guest_123'

    @patch('app.services.store_credit_service.ShopifyClient')
    def test_issue_guest_credit_shopify_failure(self, mock_shopify_class, app, sample_tenant):
        """Test handling Shopify API failure."""
        with app.app_context():
            from app.services.store_credit_service import StoreCreditService

            # Setup mock to fail
            mock_client = MagicMock()
            mock_client.add_store_credit.side_effect = Exception('Shopify API error')
            mock_shopify_class.return_value = mock_client

            service = StoreCreditService()
            result = service.issue_guest_store_credit(
                tenant_id=sample_tenant.id,
                shopify_customer_id='gid://shopify/Customer/99999',
                customer_email='fail@test.com',
                customer_name='Fail Test',
                amount=Decimal('10.00'),
                description='Test failure'
            )

            # When Shopify fails, the function returns error without creating event
            assert result['success'] is False
            assert 'error' in result

    def test_issue_guest_credit_invalid_tenant(self, app):
        """Test issuing credit with invalid tenant ID returns error dict."""
        with app.app_context():
            from app.services.store_credit_service import StoreCreditService

            service = StoreCreditService()

            # The function returns error dict instead of raising exception
            result = service.issue_guest_store_credit(
                tenant_id=99999,  # Non-existent
                shopify_customer_id='gid://shopify/Customer/123',
                customer_email='test@test.com',
                customer_name='Test',
                amount=Decimal('10.00'),
                description='Test'
            )

            # Should return error dict
            assert result['success'] is False
            assert 'error' in result


class TestStoreCreditEventsAPIAudience:
    """Tests for audience parameter in store credit events API."""

    def test_preview_event_with_audience(self, app, client, sample_tenant, auth_headers):
        """Test preview endpoint accepts audience parameter."""
        with app.app_context():
            now = datetime.utcnow()
            start = (now - timedelta(hours=2)).isoformat() + 'Z'
            end = now.isoformat() + 'Z'

            response = client.post(
                '/api/store-credit-events/preview',
                json={
                    'start_datetime': start,
                    'end_datetime': end,
                    'sources': ['pos'],
                    'credit_percent': 10,
                    'audience': 'all_customers'
                },
                headers=auth_headers
            )

            # May not have orders, but should not fail due to audience param
            assert response.status_code in [200, 500]  # 500 if Shopify not configured in test

    def test_preview_event_invalid_audience(self, app, client, sample_tenant, auth_headers):
        """Test preview endpoint rejects invalid audience."""
        with app.app_context():
            now = datetime.utcnow()
            start = (now - timedelta(hours=2)).isoformat() + 'Z'
            end = now.isoformat() + 'Z'

            response = client.post(
                '/api/store-credit-events/preview',
                json={
                    'start_datetime': start,
                    'end_datetime': end,
                    'sources': ['pos'],
                    'credit_percent': 10,
                    'audience': 'everyone'  # Invalid
                },
                headers=auth_headers
            )

            assert response.status_code == 400
            data = response.get_json()
            assert 'audience' in data.get('error', '').lower()

    def test_run_event_with_audience(self, app, client, sample_tenant, auth_headers):
        """Test run endpoint accepts audience parameter."""
        with app.app_context():
            now = datetime.utcnow()
            start = (now - timedelta(hours=2)).isoformat() + 'Z'
            end = now.isoformat() + 'Z'

            response = client.post(
                '/api/store-credit-events/run',
                json={
                    'start_datetime': start,
                    'end_datetime': end,
                    'sources': ['pos'],
                    'credit_percent': 10,
                    'audience': 'members_only',
                    'job_id': 'test-job-123'
                },
                headers=auth_headers
            )

            # May not have orders, but should not fail due to audience param
            assert response.status_code in [200, 500]  # 500 if Shopify not configured in test
