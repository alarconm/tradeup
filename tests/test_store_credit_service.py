"""
Tests for the Store Credit Service.

Comprehensive tests for:
- Credit add operations (with mocked Shopify)
- Credit deduct operations (with mocked Shopify)
- Balance queries
- Ledger history retrieval
- Credit expiration logic
- Member stats tracking
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestStoreCreditServiceAddCredit:
    """Tests for StoreCreditService.add_credit method."""

    def test_add_credit_without_shopify_sync(self, app, sample_member):
        """Test adding credit without Shopify sync (internal use)."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()

            entry = service.add_credit(
                member_id=member.id,
                amount=Decimal('25.00'),
                event_type=CreditEventType.MANUAL_ADJUSTMENT.value,
                description='Test credit without sync',
                source_type='manual',
                source_reference='test',
                created_by='test_user',
                sync_to_shopify=False
            )

            assert entry is not None
            assert entry.amount == Decimal('25.00')
            assert entry.event_type == 'adjustment'
            assert entry.description == 'Test credit without sync'
            assert entry.synced_to_shopify is False

    @patch('app.services.store_credit_service.ShopifyClient')
    def test_add_credit_with_shopify_sync(self, mock_shopify_class, app, sample_member):
        """Test adding credit with Shopify sync."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)

            # Setup mock
            mock_client = MagicMock()
            mock_client.add_store_credit.return_value = {
                'success': True,
                'new_balance': 50.00,
                'transaction_id': 'txn_123'
            }
            mock_shopify_class.return_value = mock_client

            service = StoreCreditService()

            entry = service.add_credit(
                member_id=member.id,
                amount=Decimal('25.00'),
                event_type=CreditEventType.MANUAL_ADJUSTMENT.value,
                description='Test credit with sync',
                created_by='test_user',
                sync_to_shopify=True
            )

            assert entry is not None
            assert entry.amount == Decimal('25.00')
            assert entry.balance_after == Decimal('50.00')
            assert entry.synced_to_shopify is True
            assert entry.shopify_credit_id == 'txn_123'

            # Verify Shopify client was called
            mock_client.add_store_credit.assert_called_once()

    def test_add_credit_member_not_found(self, app):
        """Test adding credit to non-existent member raises error."""
        with app.app_context():
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            service = StoreCreditService()

            with pytest.raises(ValueError) as exc_info:
                service.add_credit(
                    member_id=99999,
                    amount=Decimal('10.00'),
                    event_type=CreditEventType.MANUAL_ADJUSTMENT.value,
                    description='Test',
                    sync_to_shopify=False
                )

            assert 'not found' in str(exc_info.value).lower()

    def test_add_credit_updates_member_stats(self, app, sample_member):
        """Test that adding credit updates member stats correctly."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()

            # Add trade-in credit
            service.add_credit(
                member_id=member.id,
                amount=Decimal('50.00'),
                event_type=CreditEventType.TRADE_IN.value,
                description='Trade-in credit',
                sync_to_shopify=False
            )

            stats = service.get_member_stats(member.id)
            assert float(stats.total_earned) >= 50.00
            assert float(stats.trade_in_earned) >= 50.00
            assert stats.last_credit_at is not None

    def test_add_credit_with_expiration(self, app, sample_member):
        """Test adding credit with expiration date."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()
            expires_at = datetime.utcnow() + timedelta(days=30)

            entry = service.add_credit(
                member_id=member.id,
                amount=Decimal('20.00'),
                event_type=CreditEventType.PROMOTION_BONUS.value,
                description='Expiring promo credit',
                expires_at=expires_at,
                sync_to_shopify=False
            )

            assert entry.expires_at is not None
            assert entry.expires_at.date() == expires_at.date()


class TestStoreCreditServiceDeductCredit:
    """Tests for StoreCreditService.deduct_credit method."""

    def test_deduct_credit_member_not_found(self, app):
        """Test deducting credit from non-existent member raises error."""
        with app.app_context():
            from app.services.store_credit_service import StoreCreditService

            service = StoreCreditService()

            with pytest.raises(ValueError) as exc_info:
                service.deduct_credit(
                    member_id=99999,
                    amount=Decimal('10.00'),
                    description='Test',
                    sync_to_shopify=False
                )

            assert 'not found' in str(exc_info.value).lower()

    @patch('app.services.store_credit_service.ShopifyClient')
    def test_deduct_credit_with_shopify_sync(self, mock_shopify_class, app, sample_member):
        """Test deducting credit with Shopify sync."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)

            # Setup mock
            mock_client = MagicMock()
            mock_client.debit_store_credit.return_value = {
                'success': True,
                'new_balance': 25.00,
                'transaction_id': 'txn_debit_123'
            }
            mock_shopify_class.return_value = mock_client

            service = StoreCreditService()

            entry = service.deduct_credit(
                member_id=member.id,
                amount=Decimal('10.00'),
                description='Test deduction',
                sync_to_shopify=True
            )

            assert entry is not None
            assert entry.amount == Decimal('-10.00')  # Negative for deduction
            assert entry.event_type == CreditEventType.REDEMPTION.value
            assert entry.synced_to_shopify is True

    def test_deduct_credit_updates_stats(self, app, sample_member):
        """Test that deducting credit updates member stats."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()

            # First add some credit
            service.add_credit(
                member_id=member.id,
                amount=Decimal('100.00'),
                event_type=CreditEventType.MANUAL_ADJUSTMENT.value,
                description='Initial credit',
                sync_to_shopify=False
            )

            # Mock Shopify debit
            with patch.object(service, 'get_shopify_balance', return_value={'balance': 90}):
                with patch('app.services.store_credit_service.ShopifyClient') as mock_class:
                    mock_client = MagicMock()
                    mock_client.debit_store_credit.return_value = {
                        'success': True,
                        'new_balance': 90.00
                    }
                    mock_class.return_value = mock_client

                    service.deduct_credit(
                        member_id=member.id,
                        amount=Decimal('10.00'),
                        description='Test deduction',
                        sync_to_shopify=True
                    )

            stats = service.get_member_stats(member.id)
            assert float(stats.total_spent) >= 10.00
            assert stats.last_redemption_at is not None


class TestStoreCreditServiceBalance:
    """Tests for balance-related methods."""

    def test_get_member_stats_creates_record(self, app, sample_member):
        """Test that get_member_stats creates record if not exists."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import MemberCreditBalance
            from app.extensions import db

            member = Member.query.get(sample_member.id)

            # Delete any existing balance record
            MemberCreditBalance.query.filter_by(member_id=member.id).delete()
            db.session.commit()

            service = StoreCreditService()
            stats = service.get_member_stats(member.id)

            assert stats is not None
            assert stats.member_id == member.id
            assert stats.total_earned == 0 or stats.total_earned is None

    def test_get_member_stats_returns_existing(self, app, sample_member):
        """Test that get_member_stats returns existing record."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import MemberCreditBalance
            from app.extensions import db

            member = Member.query.get(sample_member.id)

            # Delete any existing and create new balance record
            MemberCreditBalance.query.filter_by(member_id=member.id).delete()
            db.session.commit()

            balance = MemberCreditBalance(
                member_id=member.id,
                total_earned=Decimal('100.00'),
                trade_in_earned=Decimal('50.00')
            )
            db.session.add(balance)
            db.session.commit()

            service = StoreCreditService()
            stats = service.get_member_stats(member.id)

            assert stats is not None
            assert float(stats.total_earned) == 100.00
            assert float(stats.trade_in_earned) == 50.00

    @patch('app.services.store_credit_service.ShopifyClient')
    def test_get_shopify_balance(self, mock_shopify_class, app, sample_member):
        """Test getting balance from Shopify."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService

            member = Member.query.get(sample_member.id)

            mock_client = MagicMock()
            mock_client.get_store_credit_balance.return_value = {
                'balance': 75.50,
                'currency': 'USD',
                'account_id': 'acc_123'
            }
            mock_shopify_class.return_value = mock_client

            service = StoreCreditService()
            result = service.get_shopify_balance(member)

            assert result['balance'] == 75.50
            assert result['currency'] == 'USD'
            assert result['account_id'] == 'acc_123'

    def test_get_shopify_balance_no_customer_id(self, app):
        """Test get_shopify_balance returns zero when no customer ID."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from unittest.mock import MagicMock

            # Create a mock member with no shopify_customer_id
            mock_member = MagicMock(spec=Member)
            mock_member.shopify_customer_id = None
            mock_member.tenant = MagicMock()
            mock_member.tenant.shopify_domain = 'test.myshopify.com'

            service = StoreCreditService()
            result = service.get_shopify_balance(mock_member)

            assert result['balance'] == 0
            assert result['currency'] == 'USD'


class TestStoreCreditServiceHistory:
    """Tests for credit history retrieval."""

    def test_get_member_credit_history(self, app, sample_member):
        """Test getting member credit history."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()

            # Add some credits
            service.add_credit(
                member_id=member.id,
                amount=Decimal('10.00'),
                event_type=CreditEventType.TRADE_IN.value,
                description='Trade-in 1',
                sync_to_shopify=False
            )
            service.add_credit(
                member_id=member.id,
                amount=Decimal('20.00'),
                event_type=CreditEventType.PROMOTION_BONUS.value,
                description='Promo bonus',
                sync_to_shopify=False
            )

            result = service.get_member_credit_history(member.id, limit=10, offset=0)

            assert 'transactions' in result
            assert 'balance' in result
            assert 'total' in result
            assert result['total'] >= 2
            assert len(result['transactions']) >= 2

    def test_get_member_credit_history_pagination(self, app, sample_member):
        """Test credit history pagination."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()

            # Add multiple credits
            for i in range(5):
                service.add_credit(
                    member_id=member.id,
                    amount=Decimal(f'{(i + 1) * 10}.00'),
                    event_type=CreditEventType.MANUAL_ADJUSTMENT.value,
                    description=f'Credit {i + 1}',
                    sync_to_shopify=False
                )

            # Test limit
            result = service.get_member_credit_history(member.id, limit=2, offset=0)
            assert len(result['transactions']) == 2

            # Test offset
            result_offset = service.get_member_credit_history(member.id, limit=2, offset=2)
            assert len(result_offset['transactions']) == 2

            # Verify different transactions
            assert result['transactions'][0]['id'] != result_offset['transactions'][0]['id']

    def test_get_member_credit_history_member_not_found(self, app):
        """Test getting history for non-existent member raises error."""
        with app.app_context():
            from app.services.store_credit_service import StoreCreditService

            service = StoreCreditService()

            with pytest.raises(ValueError) as exc_info:
                service.get_member_credit_history(99999)

            assert 'not found' in str(exc_info.value).lower()


class TestStoreCreditServiceExpiration:
    """Tests for credit expiration functionality."""

    def test_add_credit_with_future_expiration(self, app, sample_member):
        """Test that credit with future expiration is tracked correctly."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType, StoreCreditLedger

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()
            future_date = datetime.utcnow() + timedelta(days=60)

            entry = service.add_credit(
                member_id=member.id,
                amount=Decimal('30.00'),
                event_type=CreditEventType.PROMOTION_BONUS.value,
                description='60-day expiring credit',
                expires_at=future_date,
                sync_to_shopify=False
            )

            # Verify expiration is set
            assert entry.expires_at is not None
            assert entry.expires_at > datetime.utcnow()

            # Query ledger to verify persistence
            ledger_entry = StoreCreditLedger.query.get(entry.id)
            assert ledger_entry.expires_at is not None

    def test_ledger_entry_expiration_tracking(self, app, sample_member):
        """Test that ledger entries track expiration correctly."""
        with app.app_context():
            from app.models import Member
            from app.models.promotions import CreditEventType, StoreCreditLedger
            from app.extensions import db

            member = Member.query.get(sample_member.id)

            # Create entry with past expiration
            past_date = datetime.utcnow() - timedelta(days=1)
            entry = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.PROMOTION_BONUS.value,
                amount=Decimal('15.00'),
                balance_after=Decimal('15.00'),
                description='Expired credit',
                expires_at=past_date,
                synced_to_shopify=False
            )
            db.session.add(entry)
            db.session.commit()

            # Query expired entries
            expired = StoreCreditLedger.query.filter(
                StoreCreditLedger.member_id == member.id,
                StoreCreditLedger.expires_at < datetime.utcnow(),
                StoreCreditLedger.amount > 0
            ).all()

            assert len(expired) >= 1
            assert any(e.id == entry.id for e in expired)

    def test_expiring_credits_query(self, app, sample_member):
        """Test querying credits expiring within a time window."""
        with app.app_context():
            from app.models import Member
            from app.models.promotions import CreditEventType, StoreCreditLedger
            from app.extensions import db

            member = Member.query.get(sample_member.id)

            # Create credits with different expiration times
            now = datetime.utcnow()

            # Expiring in 3 days
            entry1 = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.TRADE_IN.value,
                amount=Decimal('10.00'),
                balance_after=Decimal('10.00'),
                description='Expiring soon',
                expires_at=now + timedelta(days=3),
                synced_to_shopify=False
            )

            # Expiring in 10 days
            entry2 = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.TRADE_IN.value,
                amount=Decimal('20.00'),
                balance_after=Decimal('30.00'),
                description='Expiring later',
                expires_at=now + timedelta(days=10),
                synced_to_shopify=False
            )

            # Not expiring
            entry3 = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.TRADE_IN.value,
                amount=Decimal('30.00'),
                balance_after=Decimal('60.00'),
                description='No expiration',
                expires_at=None,
                synced_to_shopify=False
            )

            db.session.add_all([entry1, entry2, entry3])
            db.session.commit()

            # Query credits expiring within 7 days
            expiring_soon = StoreCreditLedger.query.filter(
                StoreCreditLedger.member_id == member.id,
                StoreCreditLedger.expires_at.isnot(None),
                StoreCreditLedger.expires_at > now,
                StoreCreditLedger.expires_at <= now + timedelta(days=7),
                StoreCreditLedger.amount > 0
            ).all()

            # Should include entry1 but not entry2 or entry3
            assert any(e.id == entry1.id for e in expiring_soon)
            assert not any(e.id == entry2.id for e in expiring_soon)


class TestStoreCreditServiceEventTypes:
    """Tests for different credit event types."""

    def test_trade_in_credit_tracking(self, app, sample_member):
        """Test trade-in credit is tracked separately."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()

            service.add_credit(
                member_id=member.id,
                amount=Decimal('100.00'),
                event_type=CreditEventType.TRADE_IN.value,
                description='Trade-in credit',
                sync_to_shopify=False
            )

            stats = service.get_member_stats(member.id)
            assert float(stats.trade_in_earned or 0) >= 100.00

    def test_cashback_credit_tracking(self, app, sample_member):
        """Test cashback credit is tracked separately."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()

            service.add_credit(
                member_id=member.id,
                amount=Decimal('5.00'),
                event_type=CreditEventType.PURCHASE_CASHBACK.value,
                description='Purchase cashback',
                sync_to_shopify=False
            )

            stats = service.get_member_stats(member.id)
            assert float(stats.cashback_earned or 0) >= 5.00

    def test_promo_bonus_credit_tracking(self, app, sample_member):
        """Test promotional bonus credit is tracked separately."""
        with app.app_context():
            from app.models import Member
            from app.services.store_credit_service import StoreCreditService
            from app.models.promotions import CreditEventType

            member = Member.query.get(sample_member.id)
            service = StoreCreditService()

            service.add_credit(
                member_id=member.id,
                amount=Decimal('25.00'),
                event_type=CreditEventType.PROMOTION_BONUS.value,
                description='Promo bonus',
                sync_to_shopify=False
            )

            stats = service.get_member_stats(member.id)
            assert float(stats.promo_bonus_earned or 0) >= 25.00


class TestStoreCreditLedgerModel:
    """Tests for StoreCreditLedger model."""

    def test_ledger_entry_to_dict(self, app, sample_member):
        """Test ledger entry serialization."""
        with app.app_context():
            from app.models import Member
            from app.models.promotions import StoreCreditLedger
            from app.extensions import db

            member = Member.query.get(sample_member.id)

            entry = StoreCreditLedger(
                member_id=member.id,
                event_type='manual',
                amount=Decimal('50.00'),
                balance_after=Decimal('50.00'),
                description='Test entry',
                source_type='test',
                source_id='test_123',
                channel='online',
                created_by='test_user',
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(entry)
            db.session.commit()

            data = entry.to_dict()

            assert data['id'] == entry.id
            assert data['member_id'] == member.id
            assert data['event_type'] == 'manual'
            assert data['amount'] == 50.00
            assert data['balance_after'] == 50.00
            assert data['description'] == 'Test entry'
            assert data['source_type'] == 'test'
            assert data['channel'] == 'online'
            assert data['created_by'] == 'test_user'
            assert data['expires_at'] is not None


class TestMemberCreditBalanceModel:
    """Tests for MemberCreditBalance model."""

    def test_balance_to_dict(self, app, sample_member):
        """Test balance serialization."""
        with app.app_context():
            from app.models import Member
            from app.models.promotions import MemberCreditBalance
            from app.extensions import db

            member = Member.query.get(sample_member.id)

            # Delete any existing balance for this member
            MemberCreditBalance.query.filter_by(member_id=member.id).delete()
            db.session.commit()

            balance = MemberCreditBalance(
                member_id=member.id,
                total_balance=Decimal('100.00'),
                available_balance=Decimal('90.00'),
                pending_balance=Decimal('10.00'),
                total_earned=Decimal('150.00'),
                total_spent=Decimal('50.00'),
                cashback_earned=Decimal('20.00'),
                trade_in_earned=Decimal('100.00'),
                promo_bonus_earned=Decimal('30.00')
            )
            db.session.add(balance)
            db.session.commit()

            data = balance.to_dict()

            assert data['member_id'] == member.id
            assert data['total_balance'] == 100.00
            assert data['available_balance'] == 90.00
            assert data['pending_balance'] == 10.00
            assert data['total_earned'] == 150.00
            assert data['total_spent'] == 50.00
            assert data['cashback_earned'] == 20.00
            assert data['trade_in_earned'] == 100.00
            assert data['promo_bonus_earned'] == 30.00
