"""
Tests for ReviewEligibilityService.

Story: RC-002 - Define review prompt eligibility criteria
"""

import pytest
from datetime import datetime, timedelta

from app.extensions import db
from app.models.tenant import Tenant
from app.models.member import Member, MembershipTier
from app.models.trade_in import TradeInBatch
from app.models.review_prompt import ReviewPrompt
from app.services.review_eligibility_service import (
    ReviewEligibilityService,
    check_review_eligibility,
    is_eligible_for_review,
)


class TestReviewEligibilityService:
    """Tests for the ReviewEligibilityService class."""

    def test_new_tenant_not_eligible(self, app, db_session):
        """A brand new tenant should not be eligible (less than 30 days)."""
        # Create a tenant that was just created
        tenant = Tenant(
            shop_name='New Store',
            shop_slug='new-store',
            created_at=datetime.utcnow()  # Just now
        )
        db.session.add(tenant)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service.check_eligibility()

        assert result['eligible'] is False
        assert result['criteria']['days_active']['passed'] is False
        assert result['criteria']['days_active']['value'] == 0

    def test_old_tenant_without_activity_not_eligible(self, app, db_session):
        """A tenant active 30+ days but with no activity should not be eligible."""
        tenant = Tenant(
            shop_name='Quiet Store',
            shop_slug='quiet-store',
            created_at=datetime.utcnow() - timedelta(days=60)
        )
        db.session.add(tenant)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service.check_eligibility()

        assert result['eligible'] is False
        assert result['criteria']['days_active']['passed'] is True
        assert result['criteria']['activity_threshold']['passed'] is False

    def test_tenant_with_trade_ins_eligible(self, app, db_session):
        """A tenant with 10+ trade-ins should meet activity threshold."""
        tenant = Tenant(
            shop_name='Busy Store',
            shop_slug='busy-store',
            created_at=datetime.utcnow() - timedelta(days=45)
        )
        db.session.add(tenant)
        db.session.commit()

        # Add 10 trade-in batches
        for i in range(10):
            batch = TradeInBatch(
                tenant_id=tenant.id,
                batch_reference=f'TI-TEST-{i:03d}',
                total_items=1,
                total_trade_value=100.00,
                status='completed'
            )
            db.session.add(batch)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service.check_eligibility()

        assert result['criteria']['days_active']['passed'] is True
        assert result['criteria']['activity_threshold']['passed'] is True
        assert result['criteria']['activity_threshold']['value']['trade_ins'] >= 10

    def test_tenant_with_members_eligible(self, app, db_session):
        """A tenant with 50+ members should meet activity threshold."""
        tenant = Tenant(
            shop_name='Popular Store',
            shop_slug='popular-store',
            created_at=datetime.utcnow() - timedelta(days=90)
        )
        db.session.add(tenant)
        db.session.commit()

        # Add 50 active members
        for i in range(50):
            member = Member(
                tenant_id=tenant.id,
                member_number=f'TU{1001 + i}',
                shopify_customer_id=f'{1000 + i}',
                email=f'member{i}@test.com',
                status='active'
            )
            db.session.add(member)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service.check_eligibility()

        assert result['criteria']['days_active']['passed'] is True
        assert result['criteria']['activity_threshold']['passed'] is True
        assert result['criteria']['activity_threshold']['value']['members'] >= 50

    def test_recent_prompt_blocks_eligibility(self, app, db_session):
        """A tenant with a recent review prompt should not be eligible."""
        tenant = Tenant(
            shop_name='Reviewed Store',
            shop_slug='reviewed-store',
            created_at=datetime.utcnow() - timedelta(days=100)
        )
        db.session.add(tenant)
        db.session.commit()

        # Add enough activity
        for i in range(15):
            batch = TradeInBatch(
                tenant_id=tenant.id,
                batch_reference=f'TI-REV-{i:03d}',
                total_items=1,
                total_trade_value=50.00,
                status='completed'
            )
            db.session.add(batch)

        # Add a recent review prompt (30 days ago - within 60 day cooldown)
        prompt = ReviewPrompt(
            tenant_id=tenant.id,
            prompt_shown_at=datetime.utcnow() - timedelta(days=30)
        )
        db.session.add(prompt)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service.check_eligibility()

        assert result['eligible'] is False
        assert result['criteria']['prompt_cooldown']['passed'] is False

    def test_old_prompt_allows_eligibility(self, app, db_session):
        """A tenant with an old review prompt (60+ days) should be eligible."""
        tenant = Tenant(
            shop_name='Ready Store',
            shop_slug='ready-store',
            created_at=datetime.utcnow() - timedelta(days=120)
        )
        db.session.add(tenant)
        db.session.commit()

        # Add enough activity
        for i in range(15):
            batch = TradeInBatch(
                tenant_id=tenant.id,
                batch_reference=f'TI-OLD-{i:03d}',
                total_items=1,
                total_trade_value=50.00,
                status='completed'
            )
            db.session.add(batch)

        # Add an old review prompt (90 days ago - outside 60 day cooldown)
        prompt = ReviewPrompt(
            tenant_id=tenant.id,
            prompt_shown_at=datetime.utcnow() - timedelta(days=90)
        )
        db.session.add(prompt)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service.check_eligibility()

        assert result['criteria']['prompt_cooldown']['passed'] is True

    def test_fully_eligible_tenant(self, app, db_session):
        """A tenant meeting all criteria should be eligible."""
        tenant = Tenant(
            shop_name='Perfect Store',
            shop_slug='perfect-store',
            created_at=datetime.utcnow() - timedelta(days=100)
        )
        db.session.add(tenant)
        db.session.commit()

        # Add 15 trade-ins (above threshold)
        for i in range(15):
            batch = TradeInBatch(
                tenant_id=tenant.id,
                batch_reference=f'TI-PERF-{i:03d}',
                total_items=2,
                total_trade_value=75.00,
                status='completed'
            )
            db.session.add(batch)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service.check_eligibility()

        assert result['eligible'] is True
        assert 'meets all eligibility criteria' in result['reason']
        assert result['criteria']['days_active']['passed'] is True
        assert result['criteria']['activity_threshold']['passed'] is True
        assert result['criteria']['prompt_cooldown']['passed'] is True
        assert result['criteria']['no_support_tickets']['passed'] is True
        assert result['criteria']['no_recent_errors']['passed'] is True

    def test_nonexistent_tenant(self, app, db_session):
        """A nonexistent tenant should not be eligible."""
        service = ReviewEligibilityService(99999)
        result = service.check_eligibility()

        assert result['eligible'] is False
        assert 'Tenant not found' in result['reason']

    def test_convenience_function_check_review_eligibility(self, app, db_session):
        """Test the convenience function returns same result as service."""
        tenant = Tenant(
            shop_name='Convenience Store',
            shop_slug='convenience-store',
            created_at=datetime.utcnow() - timedelta(days=50)
        )
        db.session.add(tenant)
        db.session.commit()

        # Add activity
        for i in range(12):
            batch = TradeInBatch(
                tenant_id=tenant.id,
                batch_reference=f'TI-CONV-{i:03d}',
                total_items=1,
                total_trade_value=50.00,
                status='completed'
            )
            db.session.add(batch)
        db.session.commit()

        result = check_review_eligibility(tenant.id)

        assert result['eligible'] is True
        assert 'criteria' in result

    def test_convenience_function_is_eligible_for_review(self, app, db_session):
        """Test the boolean convenience function."""
        tenant = Tenant(
            shop_name='Boolean Store',
            shop_slug='boolean-store',
            created_at=datetime.utcnow() - timedelta(days=60)
        )
        db.session.add(tenant)
        db.session.commit()

        # Add activity
        for i in range(10):
            batch = TradeInBatch(
                tenant_id=tenant.id,
                batch_reference=f'TI-BOOL-{i:03d}',
                total_items=1,
                total_trade_value=50.00,
                status='completed'
            )
            db.session.add(batch)
        db.session.commit()

        assert is_eligible_for_review(tenant.id) is True

        # New tenant should not be eligible
        new_tenant = Tenant(
            shop_name='New Boolean Store',
            shop_slug='new-boolean-store',
            created_at=datetime.utcnow()
        )
        db.session.add(new_tenant)
        db.session.commit()

        assert is_eligible_for_review(new_tenant.id) is False

    def test_eligibility_summary(self, app, db_session):
        """Test the summary method for admin UI display."""
        tenant = Tenant(
            shop_name='Summary Store',
            shop_slug='summary-store',
            created_at=datetime.utcnow() - timedelta(days=45)
        )
        db.session.add(tenant)
        db.session.commit()

        # Add some activity
        for i in range(5):
            batch = TradeInBatch(
                tenant_id=tenant.id,
                batch_reference=f'TI-SUM-{i:03d}',
                total_items=1,
                total_trade_value=50.00,
                status='completed'
            )
            db.session.add(batch)

        for i in range(25):
            member = Member(
                tenant_id=tenant.id,
                member_number=f'TU{2001 + i}',
                shopify_customer_id=f'{2000 + i}',
                email=f'summary{i}@test.com',
                status='active'
            )
            db.session.add(member)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        summary = service.get_eligibility_summary()

        assert 'eligible' in summary
        assert 'passed_criteria' in summary
        assert 'total_criteria' in summary
        assert summary['days_active'] >= 45
        assert summary['trade_ins'] == 5
        assert summary['members'] == 25

    def test_inactive_members_not_counted(self, app, db_session):
        """Inactive members should not count toward activity threshold."""
        tenant = Tenant(
            shop_name='Mixed Store',
            shop_slug='mixed-store',
            created_at=datetime.utcnow() - timedelta(days=60)
        )
        db.session.add(tenant)
        db.session.commit()

        # Add 60 members, but only 40 active
        for i in range(40):
            member = Member(
                tenant_id=tenant.id,
                member_number=f'TU{3001 + i}',
                shopify_customer_id=f'{3000 + i}',
                email=f'active{i}@test.com',
                status='active'
            )
            db.session.add(member)

        for i in range(20):
            member = Member(
                tenant_id=tenant.id,
                member_number=f'TU{4001 + i}',
                shopify_customer_id=f'{4000 + i}',
                email=f'inactive{i}@test.com',
                status='cancelled'
            )
            db.session.add(member)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service.check_eligibility()

        # Should not be eligible (only 40 active members, need 50)
        assert result['criteria']['activity_threshold']['passed'] is False
        assert result['criteria']['activity_threshold']['value']['members'] == 40

    def test_support_ticket_check_skipped_when_not_configured(self, app, db_session):
        """Support ticket check should pass when Gorgias is not configured."""
        tenant = Tenant(
            shop_name='No Gorgias Store',
            shop_slug='no-gorgias-store',
            created_at=datetime.utcnow() - timedelta(days=60),
            settings={}  # No integrations
        )
        db.session.add(tenant)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service._check_no_recent_support_tickets()

        assert result['passed'] is True
        assert 'skipped' in result['reason'].lower() or 'not configured' in result['reason'].lower()

    def test_error_check_passes_by_default(self, app, db_session):
        """Error check should pass when per-tenant error tracking is not configured."""
        tenant = Tenant(
            shop_name='Error Free Store',
            shop_slug='error-free-store',
            created_at=datetime.utcnow() - timedelta(days=60)
        )
        db.session.add(tenant)
        db.session.commit()

        service = ReviewEligibilityService(tenant.id)
        result = service._check_no_recent_errors()

        assert result['passed'] is True
        assert 'not configured' in result['reason'].lower()
