"""
Tests for Scheduled Tasks Service - Credit Operations.

Comprehensive tests for:
- Monthly credit distribution
- Credit expiration processing
- Expiring credits preview
- Balance recalculation
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestMonthlyCreditDistribution:
    """Tests for monthly credit distribution."""

    @pytest.fixture
    def member_with_tier_credit(self, app, sample_tenant):
        """Create a member with a tier that has monthly credit."""
        with app.app_context():
            import uuid
            from app.models import Member, MembershipTier
            from app.extensions import db

            unique_id = str(uuid.uuid4())[:8]

            # Create tier with monthly credit
            tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Premium',
                monthly_price=Decimal('29.99'),
                monthly_credit_amount=Decimal('25.00'),
                bonus_rate=Decimal('0.10'),
                is_active=True
            )
            db.session.add(tier)
            db.session.commit()

            # Create member
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=tier.id,
                member_number=f'TU{unique_id}',
                email=f'monthly-{unique_id}@example.com',
                name='Monthly Credit Test',
                shopify_customer_id=f'cust_{unique_id}',
                status='active'
            )
            db.session.add(member)
            db.session.commit()

            yield member, tier

            # Cleanup
            try:
                Member.query.filter_by(id=member.id).delete()
                MembershipTier.query.filter_by(id=tier.id).delete()
                db.session.commit()
            except Exception:
                db.session.rollback()

    def test_distribute_monthly_credits_dry_run(self, app, member_with_tier_credit, sample_tenant):
        """Test monthly credit distribution in dry run mode."""
        with app.app_context():
            from app.services.scheduled_tasks import ScheduledTasksService

            member, tier = member_with_tier_credit

            service = ScheduledTasksService()
            result = service.distribute_monthly_credits(sample_tenant.id, dry_run=True)

            assert result['dry_run'] is True
            assert result['processed'] >= 1
            assert result['credited'] >= 1
            assert float(result['total_amount']) >= 25.00

    @patch('app.services.store_credit_service.ShopifyClient')
    def test_distribute_monthly_credits_actual(self, mock_shopify_class, app, member_with_tier_credit, sample_tenant):
        """Test actual monthly credit distribution."""
        with app.app_context():
            from app.services.scheduled_tasks import ScheduledTasksService
            from app.models.promotions import StoreCreditLedger

            member, tier = member_with_tier_credit

            # Mock Shopify client
            mock_client = MagicMock()
            mock_client.add_store_credit.return_value = {
                'success': True,
                'new_balance': 25.00,
                'transaction_id': 'monthly_txn_123'
            }
            mock_shopify_class.return_value = mock_client

            service = ScheduledTasksService()
            result = service.distribute_monthly_credits(sample_tenant.id, dry_run=False)

            assert result['dry_run'] is False
            assert result['credited'] >= 1

            # Verify ledger entry was created
            entry = StoreCreditLedger.query.filter_by(
                member_id=member.id,
                event_type='monthly_credit'
            ).order_by(StoreCreditLedger.created_at.desc()).first()

            assert entry is not None
            assert float(entry.amount) == 25.00

    def test_distribute_monthly_credits_skips_already_credited(self, app, member_with_tier_credit, sample_tenant):
        """Test that monthly credit is not distributed twice in same month."""
        with app.app_context():
            from app.services.scheduled_tasks import ScheduledTasksService
            from app.models.promotions import StoreCreditLedger
            from app.extensions import db

            member, tier = member_with_tier_credit

            # Manually create a monthly credit entry for this month
            now = datetime.utcnow()
            existing_entry = StoreCreditLedger(
                member_id=member.id,
                event_type='monthly_credit',
                amount=Decimal('25.00'),
                balance_after=Decimal('25.00'),
                description=f'Monthly credit - {now.strftime("%B %Y")}',
                source_type='monthly_credit',
                source_id=f'monthly-{now.strftime("%Y-%m")}',
                created_by='system:scheduler',
                synced_to_shopify=False
            )
            db.session.add(existing_entry)
            db.session.commit()

            service = ScheduledTasksService()
            result = service.distribute_monthly_credits(sample_tenant.id, dry_run=True)

            # Member should be skipped
            skipped_member = next(
                (d for d in result['details'] if d['member_id'] == member.id and d['status'] == 'skipped'),
                None
            )
            assert skipped_member is not None
            assert 'Already received' in skipped_member.get('reason', '')


class TestCreditExpiration:
    """Tests for credit expiration processing."""

    @pytest.fixture
    def member_with_expiring_credit(self, app, sample_tenant, sample_tier):
        """Create a member with expiring credit."""
        with app.app_context():
            import uuid
            from app.models import Member
            from app.models.promotions import StoreCreditLedger, MemberCreditBalance
            from app.extensions import db

            unique_id = str(uuid.uuid4())[:8]

            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                member_number=f'TU{unique_id}',
                email=f'expiring-{unique_id}@example.com',
                name='Expiring Credit Test',
                shopify_customer_id=f'cust_{unique_id}',
                status='active'
            )
            db.session.add(member)
            db.session.commit()

            yield member

            # Cleanup
            try:
                StoreCreditLedger.query.filter_by(member_id=member.id).delete()
                MemberCreditBalance.query.filter_by(member_id=member.id).delete()
                Member.query.filter_by(id=member.id).delete()
                db.session.commit()
            except Exception:
                db.session.rollback()

    def test_expire_old_credits_dry_run(self, app, member_with_expiring_credit, sample_tenant):
        """Test credit expiration in dry run mode."""
        with app.app_context():
            from app.services.scheduled_tasks import ScheduledTasksService
            from app.models.promotions import CreditEventType, StoreCreditLedger
            from app.extensions import db

            member = member_with_expiring_credit

            # Create an expired credit
            past_date = datetime.utcnow() - timedelta(days=5)
            expired_credit = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.PROMOTION_BONUS.value,
                amount=Decimal('50.00'),
                balance_after=Decimal('50.00'),
                description='Expired promo credit',
                expires_at=past_date,
                synced_to_shopify=False
            )
            db.session.add(expired_credit)
            db.session.commit()

            service = ScheduledTasksService()
            result = service.expire_old_credits(sample_tenant.id, dry_run=True)

            assert result['dry_run'] is True
            assert result['members_affected'] >= 1
            assert result['expired_entries'] >= 1
            assert float(result['total_expired']) >= 50.00

    def test_expire_old_credits_actual(self, app, member_with_expiring_credit, sample_tenant):
        """Test actual credit expiration processing."""
        with app.app_context():
            from app.services.scheduled_tasks import ScheduledTasksService
            from app.models.promotions import CreditEventType, StoreCreditLedger
            from app.extensions import db

            member = member_with_expiring_credit

            # Create an expired credit
            past_date = datetime.utcnow() - timedelta(days=5)
            expired_credit = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.TRADE_IN.value,
                amount=Decimal('30.00'),
                balance_after=Decimal('30.00'),
                description='Expired trade-in credit',
                expires_at=past_date,
                synced_to_shopify=False
            )
            db.session.add(expired_credit)
            db.session.commit()
            expired_credit_id = expired_credit.id

            service = ScheduledTasksService()
            result = service.expire_old_credits(sample_tenant.id, dry_run=False)

            assert result['dry_run'] is False
            assert result['expired_entries'] >= 1

            # Verify expiration entry was created
            expiration_entry = StoreCreditLedger.query.filter_by(
                member_id=member.id,
                event_type='expiration',
                source_id=f'expired:{expired_credit_id}'
            ).first()

            assert expiration_entry is not None
            assert float(expiration_entry.amount) == -30.00

    def test_expire_old_credits_does_not_double_expire(self, app, member_with_expiring_credit, sample_tenant):
        """Test that credits are not expired twice."""
        with app.app_context():
            from app.services.scheduled_tasks import ScheduledTasksService
            from app.models.promotions import CreditEventType, StoreCreditLedger
            from app.extensions import db

            member = member_with_expiring_credit

            # Create an expired credit
            past_date = datetime.utcnow() - timedelta(days=5)
            expired_credit = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.PROMOTION_BONUS.value,
                amount=Decimal('40.00'),
                balance_after=Decimal('40.00'),
                description='Already expired credit',
                expires_at=past_date,
                synced_to_shopify=False
            )
            db.session.add(expired_credit)
            db.session.commit()

            # Also create an expiration entry for it
            expiration_entry = StoreCreditLedger(
                member_id=member.id,
                event_type='expiration',
                amount=Decimal('-40.00'),
                balance_after=Decimal('0.00'),
                description='Credit expired',
                source_type='expiration',
                source_id=f'expired:{expired_credit.id}',
                synced_to_shopify=False
            )
            db.session.add(expiration_entry)
            db.session.commit()

            service = ScheduledTasksService()
            result = service.expire_old_credits(sample_tenant.id, dry_run=False)

            # Count expiration entries for this credit
            expiration_count = StoreCreditLedger.query.filter(
                StoreCreditLedger.member_id == member.id,
                StoreCreditLedger.event_type == 'expiration',
                StoreCreditLedger.source_id == f'expired:{expired_credit.id}'
            ).count()

            # Should still only have one expiration entry
            assert expiration_count == 1


class TestExpiringCreditsPreview:
    """Tests for previewing credits about to expire."""

    @pytest.fixture
    def member_with_soon_expiring_credit(self, app, sample_tenant, sample_tier):
        """Create a member with credit expiring soon."""
        with app.app_context():
            import uuid
            from app.models import Member
            from app.models.promotions import StoreCreditLedger
            from app.extensions import db

            unique_id = str(uuid.uuid4())[:8]

            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                member_number=f'TU{unique_id}',
                email=f'soon-expiring-{unique_id}@example.com',
                name='Soon Expiring Test',
                shopify_customer_id=f'cust_{unique_id}',
                status='active'
            )
            db.session.add(member)
            db.session.commit()

            yield member

            # Cleanup
            try:
                StoreCreditLedger.query.filter_by(member_id=member.id).delete()
                Member.query.filter_by(id=member.id).delete()
                db.session.commit()
            except Exception:
                db.session.rollback()

    def test_get_expiring_credits_preview(self, app, member_with_soon_expiring_credit, sample_tenant):
        """Test getting preview of credits expiring soon."""
        with app.app_context():
            from app.services.scheduled_tasks import ScheduledTasksService
            from app.models.promotions import CreditEventType, StoreCreditLedger
            from app.extensions import db

            member = member_with_soon_expiring_credit
            now = datetime.utcnow()

            # Create credit expiring in 3 days
            soon_credit = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.TRADE_IN.value,
                amount=Decimal('75.00'),
                balance_after=Decimal('75.00'),
                description='Expiring in 3 days',
                expires_at=now + timedelta(days=3),
                synced_to_shopify=False
            )

            # Create credit expiring in 10 days (outside 7-day window)
            later_credit = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.TRADE_IN.value,
                amount=Decimal('50.00'),
                balance_after=Decimal('125.00'),
                description='Expiring in 10 days',
                expires_at=now + timedelta(days=10),
                synced_to_shopify=False
            )

            db.session.add_all([soon_credit, later_credit])
            db.session.commit()

            service = ScheduledTasksService()
            result = service.get_expiring_credits_preview(sample_tenant.id, days_ahead=7)

            assert result['days_ahead'] == 7
            assert result['members_with_expiring_credits'] >= 1
            assert float(result['total_amount_expiring']) >= 75.00

            # Check member details
            member_data = next(
                (m for m in result['members'] if m['member_id'] == member.id),
                None
            )
            assert member_data is not None
            assert float(member_data['total_expiring']) >= 75.00

    def test_get_expiring_credits_preview_no_expiring(self, app, sample_tenant):
        """Test preview when no credits are expiring."""
        with app.app_context():
            from app.services.scheduled_tasks import ScheduledTasksService

            service = ScheduledTasksService()
            result = service.get_expiring_credits_preview(sample_tenant.id, days_ahead=7)

            assert result['days_ahead'] == 7
            # May have some or no members depending on test isolation
            assert 'members_with_expiring_credits' in result
            assert 'total_amount_expiring' in result


class TestBalanceRecalculation:
    """Tests for balance recalculation."""

    def test_recalculate_member_balance(self, app, sample_member):
        """Test recalculating member balance from ledger."""
        with app.app_context():
            from app.models import Member
            from app.services.scheduled_tasks import ScheduledTasksService
            from app.models.promotions import StoreCreditLedger, MemberCreditBalance
            from app.extensions import db

            member = Member.query.get(sample_member.id)

            # Clear existing balance
            MemberCreditBalance.query.filter_by(member_id=member.id).delete()
            db.session.commit()

            # Create some ledger entries
            entry1 = StoreCreditLedger(
                member_id=member.id,
                event_type='manual',
                amount=Decimal('100.00'),
                balance_after=Decimal('100.00'),
                description='Credit 1',
                synced_to_shopify=False
            )
            entry2 = StoreCreditLedger(
                member_id=member.id,
                event_type='redemption',
                amount=Decimal('-30.00'),
                balance_after=Decimal('70.00'),
                description='Redemption',
                synced_to_shopify=False
            )
            entry3 = StoreCreditLedger(
                member_id=member.id,
                event_type='manual',
                amount=Decimal('50.00'),
                balance_after=Decimal('120.00'),
                description='Credit 2',
                synced_to_shopify=False
            )
            db.session.add_all([entry1, entry2, entry3])
            db.session.commit()

            service = ScheduledTasksService()
            service._recalculate_member_balance(member.id)

            balance = MemberCreditBalance.query.filter_by(member_id=member.id).first()
            assert balance is not None
            # 100 - 30 + 50 = 120
            assert float(balance.total_balance) == 120.00


class TestScheduledTasksServiceIntegration:
    """Integration tests for scheduled tasks service."""

    def test_monthly_credit_preview(self, app, sample_tenant):
        """Test getting monthly credit distribution preview."""
        with app.app_context():
            from app.services.scheduled_tasks import ScheduledTasksService

            service = ScheduledTasksService()
            result = service.get_monthly_credit_preview(sample_tenant.id)

            assert result['dry_run'] is True
            assert 'processed' in result
            assert 'credited' in result
            assert 'total_amount' in result

    def test_scheduled_tasks_singleton(self, app):
        """Test that scheduled_tasks_service is a singleton."""
        with app.app_context():
            from app.services.scheduled_tasks import scheduled_tasks_service, ScheduledTasksService

            assert scheduled_tasks_service is not None
            assert isinstance(scheduled_tasks_service, ScheduledTasksService)


class TestCreditExpirationEdgeCases:
    """Edge case tests for credit expiration."""

    def test_expire_credits_with_zero_balance(self, app, sample_member):
        """Test expiring credits when result is zero balance."""
        with app.app_context():
            from app.models import Member
            from app.services.scheduled_tasks import ScheduledTasksService
            from app.models.promotions import CreditEventType, StoreCreditLedger, MemberCreditBalance
            from app.extensions import db

            member = Member.query.get(sample_member.id)

            # Create a small expired credit
            past_date = datetime.utcnow() - timedelta(days=1)
            expired_credit = StoreCreditLedger(
                member_id=member.id,
                event_type=CreditEventType.PROMOTION_BONUS.value,
                amount=Decimal('5.00'),
                balance_after=Decimal('5.00'),
                description='Small expired credit',
                expires_at=past_date,
                synced_to_shopify=False
            )
            db.session.add(expired_credit)
            db.session.commit()

            # Create balance record with same amount
            balance = MemberCreditBalance.query.filter_by(member_id=member.id).first()
            if not balance:
                balance = MemberCreditBalance(member_id=member.id, total_balance=Decimal('5.00'))
                db.session.add(balance)
                db.session.commit()

            service = ScheduledTasksService()
            # Run expiration - should handle zero balance case
            result = service.expire_old_credits(member.tenant_id, dry_run=False)

            # Should complete without error
            assert 'errors' in result

    def test_expire_credits_multiple_members(self, app, sample_tenant, sample_tier):
        """Test expiring credits for multiple members at once."""
        with app.app_context():
            import uuid
            from app.models import Member
            from app.services.scheduled_tasks import ScheduledTasksService
            from app.models.promotions import CreditEventType, StoreCreditLedger
            from app.extensions import db

            # Create multiple members with expired credits
            members = []
            for i in range(3):
                unique_id = str(uuid.uuid4())[:8]
                member = Member(
                    tenant_id=sample_tenant.id,
                    tier_id=sample_tier.id,
                    member_number=f'TU{unique_id}',
                    email=f'multi-{unique_id}@example.com',
                    name=f'Multi Test {i}',
                    shopify_customer_id=f'cust_{unique_id}',
                    status='active'
                )
                db.session.add(member)
                members.append(member)

            db.session.commit()

            # Add expired credits for each
            past_date = datetime.utcnow() - timedelta(days=2)
            for i, member in enumerate(members):
                credit = StoreCreditLedger(
                    member_id=member.id,
                    event_type=CreditEventType.PROMOTION_BONUS.value,
                    amount=Decimal(f'{(i + 1) * 10}.00'),
                    balance_after=Decimal(f'{(i + 1) * 10}.00'),
                    description=f'Expired credit {i}',
                    expires_at=past_date,
                    synced_to_shopify=False
                )
                db.session.add(credit)
            db.session.commit()

            service = ScheduledTasksService()
            result = service.expire_old_credits(sample_tenant.id, dry_run=True)

            # Should process all members
            assert result['members_affected'] >= 3
            # Total: 10 + 20 + 30 = 60
            assert float(result['total_expired']) >= 60.00

            # Cleanup
            for member in members:
                StoreCreditLedger.query.filter_by(member_id=member.id).delete()
                Member.query.filter_by(id=member.id).delete()
            db.session.commit()
