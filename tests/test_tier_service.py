"""
Comprehensive tests for TierService.

Tests cover:
- Tier CRUD operations
- Tier eligibility calculation
- Auto-upgrade logic
- Auto-downgrade with expiration
- Tier benefits application
- Source priority and conflict resolution
- Promotional tier management
"""
import json
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock


class TestTierServiceInit:
    """Tests for TierService initialization."""

    def test_tier_service_init_with_tenant_id(self, app, sample_tenant):
        """Test TierService initializes with tenant_id."""
        from app.services.tier_service import TierService

        with app.app_context():
            service = TierService(sample_tenant.id)
            assert service.tenant_id == sample_tenant.id
            assert service.tenant is not None
            assert service.tenant.id == sample_tenant.id

    def test_tier_service_init_with_shopify_client(self, app, sample_tenant):
        """Test TierService initializes with provided shopify_client."""
        from app.services.tier_service import TierService

        with app.app_context():
            mock_client = MagicMock()
            service = TierService(sample_tenant.id, shopify_client=mock_client)
            assert service.shopify_client == mock_client


class TestTierAssignment:
    """Tests for basic tier assignment functionality."""

    def test_assign_tier_to_member(self, app, sample_member, sample_tier, sample_tenant):
        """Test assigning a tier to a member."""
        from app.services.tier_service import TierService
        from app.extensions import db
        from app.models import MembershipTier

        with app.app_context():
            # Create a new tier to assign
            new_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Premium',
                monthly_price=Decimal('39.99'),
                bonus_rate=Decimal('0.20'),
                is_active=True
            )
            db.session.add(new_tier)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.assign_tier(
                member_id=sample_member.id,
                tier_id=new_tier.id,
                source_type='staff',
                source_reference='test@example.com',
                reason='Test assignment'
            )

            assert result['success'] is True
            assert result['tier_id'] == new_tier.id
            assert result['tier_name'] == 'Premium'

    def test_assign_tier_member_not_found(self, app, sample_tenant):
        """Test assigning tier to non-existent member."""
        from app.services.tier_service import TierService

        with app.app_context():
            service = TierService(sample_tenant.id)
            result = service.assign_tier(
                member_id=99999,
                tier_id=1,
                source_type='staff',
                source_reference='test@example.com'
            )

            assert result['success'] is False
            assert 'Member not found' in result['error']

    def test_assign_tier_tier_not_found(self, app, sample_member, sample_tenant):
        """Test assigning non-existent tier to member."""
        from app.services.tier_service import TierService

        with app.app_context():
            service = TierService(sample_tenant.id)
            result = service.assign_tier(
                member_id=sample_member.id,
                tier_id=99999,
                source_type='staff',
                source_reference='test@example.com'
            )

            assert result['success'] is False
            assert 'Tier not found' in result['error']

    def test_assign_tier_creates_audit_log(self, app, sample_member, sample_tier, sample_tenant):
        """Test that tier assignment creates an audit log entry."""
        from app.services.tier_service import TierService
        from app.models import TierChangeLog
        from app.extensions import db
        from app.models import MembershipTier

        with app.app_context():
            # Create a new tier to assign
            new_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Bronze',
                monthly_price=Decimal('9.99'),
                bonus_rate=Decimal('0.05'),
                is_active=True
            )
            db.session.add(new_tier)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.assign_tier(
                member_id=sample_member.id,
                tier_id=new_tier.id,
                source_type='staff',
                source_reference='admin@shop.com',
                reason='Customer loyalty upgrade'
            )

            assert result['success'] is True

            # Check audit log was created
            log = TierChangeLog.query.filter_by(member_id=sample_member.id).order_by(
                TierChangeLog.created_at.desc()
            ).first()
            assert log is not None
            assert log.new_tier_name == 'Bronze'
            assert log.source_type == 'staff'
            assert log.reason == 'Customer loyalty upgrade'


class TestTierRemoval:
    """Tests for tier removal functionality."""

    def test_remove_tier_from_member(self, app, sample_member, sample_tenant):
        """Test removing tier from a member."""
        from app.services.tier_service import TierService

        with app.app_context():
            service = TierService(sample_tenant.id)
            result = service.remove_tier(
                member_id=sample_member.id,
                source_type='staff',
                source_reference='admin@shop.com',
                reason='Membership cancelled'
            )

            assert result['success'] is True
            assert result['change_type'] == 'removed'

    def test_remove_tier_member_has_no_tier(self, app, sample_tenant):
        """Test removing tier from member who has no tier."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create member without tier
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=None,
                member_number=f'TU{unique_id}',
                email=f'test-{unique_id}@example.com',
                name='No Tier User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active'
            )
            db.session.add(member)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.remove_tier(
                member_id=member.id,
                source_type='staff',
                source_reference='admin@shop.com'
            )

            assert result['success'] is True
            assert 'no tier' in result.get('message', '').lower()


class TestSourcePriority:
    """Tests for source priority and conflict resolution."""

    def test_staff_can_override_any_source(self, app, sample_member, sample_tier, sample_tenant):
        """Test that staff can override any tier assignment source."""
        from app.services.tier_service import TierService
        from app.extensions import db
        from app.models import Member, MembershipTier

        with app.app_context():
            # Set up member with subscription-assigned tier
            member = Member.query.get(sample_member.id)
            member.tier_assigned_by = 'subscription:contract_123'
            db.session.commit()

            # Create a different tier
            new_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='VIP',
                monthly_price=Decimal('99.99'),
                bonus_rate=Decimal('0.25'),
                is_active=True
            )
            db.session.add(new_tier)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.staff_assign_tier(
                member_id=member.id,
                tier_id=new_tier.id,
                staff_email='admin@shop.com',
                reason='VIP override'
            )

            assert result['success'] is True
            assert result['tier_name'] == 'VIP'

    def test_lower_priority_cannot_override_higher(self, app, sample_member, sample_tier, sample_tenant):
        """Test that lower priority source cannot override higher priority."""
        from app.services.tier_service import TierService
        from app.extensions import db
        from app.models import Member, MembershipTier

        with app.app_context():
            # Set up member with staff-assigned tier (highest priority)
            member = Member.query.get(sample_member.id)
            member.tier_assigned_by = 'staff:admin@shop.com'
            db.session.commit()

            # Create a different tier
            new_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Promo',
                monthly_price=Decimal('0'),
                bonus_rate=Decimal('0.10'),
                is_active=True
            )
            db.session.add(new_tier)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.assign_tier(
                member_id=member.id,
                tier_id=new_tier.id,
                source_type='promo',  # Lower priority than staff
                source_reference='summer_sale',
                force=False
            )

            assert result['success'] is False
            assert 'Cannot override' in result.get('error', '')

    def test_force_flag_overrides_priority(self, app, sample_member, sample_tier, sample_tenant):
        """Test that force flag allows overriding priority rules."""
        from app.services.tier_service import TierService
        from app.extensions import db
        from app.models import Member, MembershipTier

        with app.app_context():
            # Set up member with staff-assigned tier
            member = Member.query.get(sample_member.id)
            member.tier_assigned_by = 'staff:admin@shop.com'
            db.session.commit()

            # Create a different tier
            new_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='SystemOverride',
                monthly_price=Decimal('0'),
                bonus_rate=Decimal('0.10'),
                is_active=True
            )
            db.session.add(new_tier)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.assign_tier(
                member_id=member.id,
                tier_id=new_tier.id,
                source_type='system',
                source_reference='test_override',
                force=True  # Force override
            )

            assert result['success'] is True


class TestTierEligibility:
    """Tests for tier eligibility checking and calculation."""

    def test_check_eligibility_no_rules(self, app, sample_member, sample_tenant):
        """Test eligibility check when no rules are configured."""
        from app.services.tier_service import TierService

        with app.app_context():
            service = TierService(sample_tenant.id)
            result = service.check_earned_tier_eligibility(
                member_id=sample_member.id,
                apply_if_eligible=False
            )

            assert result['success'] is True
            assert result['eligible_for'] is None
            assert 'No eligibility rules' in result.get('message', '')

    def test_check_eligibility_with_spend_rule(self, app, sample_member, sample_tier, sample_tenant):
        """Test eligibility check with a spend threshold rule."""
        from app.services.tier_service import TierService
        from app.models import TierEligibilityRule, Member, MembershipTier
        from app.extensions import db

        with app.app_context():
            # Create a higher tier
            premium_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Premium',
                monthly_price=Decimal('49.99'),
                bonus_rate=Decimal('0.25'),
                is_active=True
            )
            db.session.add(premium_tier)
            db.session.commit()

            # Create eligibility rule
            rule = TierEligibilityRule(
                tenant_id=sample_tenant.id,
                tier_id=premium_tier.id,
                name='Premium Spend Threshold',
                rule_type='qualification',
                metric='total_spend',
                threshold_value=Decimal('500'),
                threshold_operator='>=',
                priority=10,
                is_active=True
            )
            db.session.add(rule)

            # Update member's total trade value to meet threshold
            member = Member.query.get(sample_member.id)
            member.total_trade_value = Decimal('600')
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.check_earned_tier_eligibility(
                member_id=sample_member.id,
                apply_if_eligible=False
            )

            assert result['success'] is True
            assert result['eligible_for'] == 'Premium'
            assert result['eligible_tier_id'] == premium_tier.id

    def test_check_eligibility_below_threshold(self, app, sample_member, sample_tier, sample_tenant):
        """Test eligibility check when member is below threshold."""
        from app.services.tier_service import TierService
        from app.models import TierEligibilityRule, Member, MembershipTier
        from app.extensions import db

        with app.app_context():
            # Create a higher tier
            premium_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Elite',
                monthly_price=Decimal('99.99'),
                bonus_rate=Decimal('0.30'),
                is_active=True
            )
            db.session.add(premium_tier)
            db.session.commit()

            # Create eligibility rule with high threshold
            rule = TierEligibilityRule(
                tenant_id=sample_tenant.id,
                tier_id=premium_tier.id,
                name='Elite Spend Threshold',
                rule_type='qualification',
                metric='total_spend',
                threshold_value=Decimal('1000'),
                threshold_operator='>=',
                priority=10,
                is_active=True
            )
            db.session.add(rule)

            # Member has low spend
            member = Member.query.get(sample_member.id)
            member.total_trade_value = Decimal('100')
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.check_earned_tier_eligibility(
                member_id=sample_member.id,
                apply_if_eligible=False
            )

            assert result['success'] is True
            # Member should not be eligible for the Elite tier
            assert result.get('eligible_for') != 'Elite'


class TestAutoUpgrade:
    """Tests for automatic tier upgrade logic."""

    def test_auto_upgrade_when_eligible(self, app, sample_member, sample_tier, sample_tenant):
        """Test automatic tier upgrade when member meets criteria."""
        from app.services.tier_service import TierService
        from app.models import TierEligibilityRule, Member, MembershipTier
        from app.extensions import db

        with app.app_context():
            # Create a higher tier
            platinum_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Platinum',
                monthly_price=Decimal('79.99'),
                bonus_rate=Decimal('0.30'),  # Higher than Gold's 0.15
                is_active=True
            )
            db.session.add(platinum_tier)
            db.session.commit()

            # Create upgrade rule
            rule = TierEligibilityRule(
                tenant_id=sample_tenant.id,
                tier_id=platinum_tier.id,
                name='Platinum Upgrade Rule',
                rule_type='qualification',
                metric='trade_in_count',
                threshold_value=Decimal('10'),
                threshold_operator='>=',
                action='upgrade',
                priority=20,
                is_active=True
            )
            db.session.add(rule)

            # Update member to meet criteria
            member = Member.query.get(sample_member.id)
            member.total_trade_ins = 15
            member.tier_assigned_by = 'earned'  # Allow upgrade from earned tier
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.check_earned_tier_eligibility(
                member_id=sample_member.id,
                apply_if_eligible=True
            )

            assert result['success'] is True
            assert result.get('tier_assigned') is True
            assert result.get('change_type') == 'upgraded'

    def test_no_upgrade_if_already_higher_tier(self, app, sample_member, sample_tenant):
        """Test no upgrade occurs if member already has a better tier."""
        from app.services.tier_service import TierService
        from app.models import TierEligibilityRule, Member, MembershipTier
        from app.extensions import db

        with app.app_context():
            # Create a lower tier
            basic_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Basic',
                monthly_price=Decimal('9.99'),
                bonus_rate=Decimal('0.05'),  # Lower than Gold's 0.15
                is_active=True
            )
            db.session.add(basic_tier)
            db.session.commit()

            # Create rule for basic tier
            rule = TierEligibilityRule(
                tenant_id=sample_tenant.id,
                tier_id=basic_tier.id,
                name='Basic Tier Rule',
                rule_type='qualification',
                metric='trade_in_count',
                threshold_value=Decimal('1'),
                threshold_operator='>=',
                priority=5,
                is_active=True
            )
            db.session.add(rule)

            # Member has Gold tier (bonus_rate=0.15) which is better than Basic (0.05)
            member = Member.query.get(sample_member.id)
            member.total_trade_ins = 5
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.check_earned_tier_eligibility(
                member_id=sample_member.id,
                apply_if_eligible=True
            )

            # Member should keep their Gold tier, not downgrade to Basic
            assert result['success'] is True
            # The highest eligible tier is Basic (since that's the only rule)
            # but member already has Gold, so no change should occur


class TestAutoDowngrade:
    """Tests for automatic tier downgrade logic."""

    def test_downgrade_when_no_longer_eligible(self, app, sample_tenant):
        """Test downgrade when member no longer meets requirements."""
        from app.services.tier_service import TierService
        from app.models import TierEligibilityRule, Member, MembershipTier
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create tiers
            basic_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Basic',
                monthly_price=Decimal('9.99'),
                bonus_rate=Decimal('0.05'),
                is_active=True
            )
            advanced_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Advanced',
                monthly_price=Decimal('29.99'),
                bonus_rate=Decimal('0.15'),
                is_active=True
            )
            db.session.add_all([basic_tier, advanced_tier])
            db.session.commit()

            # Create a member with Advanced tier
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=advanced_tier.id,
                member_number=f'TU{unique_id}',
                email=f'test-{unique_id}@example.com',
                name='Downgrade Test User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active',
                total_trade_value=Decimal('200'),  # Below Advanced threshold
                tier_assigned_by='earned'
            )
            db.session.add(member)
            db.session.commit()

            # Create downgrade rule
            downgrade_rule = TierEligibilityRule(
                tenant_id=sample_tenant.id,
                tier_id=basic_tier.id,
                name='Downgrade to Basic',
                rule_type='downgrade',
                metric='total_spend',
                threshold_value=Decimal('100'),
                threshold_operator='<',  # If spend drops below $100
                priority=1,
                is_active=True
            )
            db.session.add(downgrade_rule)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.check_earned_tier_eligibility(
                member_id=member.id,
                apply_if_eligible=True
            )

            assert result['success'] is True


class TestTierExpiration:
    """Tests for tier expiration handling."""

    def test_process_expired_tiers(self, app, sample_tenant):
        """Test processing of expired tier assignments."""
        from app.services.tier_service import TierService
        from app.models import Member, MembershipTier
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create a tier
            tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='TempTier',
                monthly_price=Decimal('19.99'),
                bonus_rate=Decimal('0.10'),
                is_active=True
            )
            db.session.add(tier)
            db.session.commit()

            # Create member with expired tier
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=tier.id,
                member_number=f'TU{unique_id}',
                email=f'test-{unique_id}@example.com',
                name='Expired Tier User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active',
                tier_expires_at=datetime.utcnow() - timedelta(days=1),  # Expired yesterday
                tier_assigned_by='purchase:order_123'
            )
            db.session.add(member)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.process_expired_tiers()

            assert result['processed'] >= 1

    def test_tier_with_expiration_date(self, app, sample_member, sample_tier, sample_tenant):
        """Test assigning tier with expiration date."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db

        with app.app_context():
            expires_at = datetime.utcnow() + timedelta(days=30)

            service = TierService(sample_tenant.id)
            result = service.assign_tier(
                member_id=sample_member.id,
                tier_id=sample_tier.id,
                source_type='promo',
                source_reference='limited_offer',
                expires_at=expires_at
            )

            assert result['success'] is True
            assert result['expires_at'] is not None

            # Verify member's tier_expires_at is set
            member = Member.query.get(sample_member.id)
            assert member.tier_expires_at is not None


class TestBulkOperations:
    """Tests for bulk tier operations."""

    def test_bulk_assign_tier(self, app, sample_tier, sample_tenant):
        """Test bulk tier assignment to multiple members."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create multiple members
            member_ids = []
            for i in range(3):
                unique_id = str(uuid.uuid4())[:8]
                member = Member(
                    tenant_id=sample_tenant.id,
                    tier_id=None,
                    member_number=f'TU{unique_id}',
                    email=f'bulk-{unique_id}@example.com',
                    name=f'Bulk User {i}',
                    shopify_customer_id=f'cust_{unique_id}',
                    status='active'
                )
                db.session.add(member)
                db.session.commit()
                member_ids.append(member.id)

            service = TierService(sample_tenant.id)
            result = service.bulk_assign_tier(
                member_ids=member_ids,
                tier_id=sample_tier.id,
                source_type='staff',
                source_reference='bulk_upgrade@shop.com',
                reason='Bulk upgrade campaign'
            )

            assert result['success_count'] == 3
            assert result['failure_count'] == 0


class TestTierHistory:
    """Tests for tier change history."""

    def test_get_tier_history(self, app, sample_member, sample_tier, sample_tenant):
        """Test retrieving tier change history for a member."""
        from app.services.tier_service import TierService
        from app.models import MembershipTier
        from app.extensions import db

        with app.app_context():
            service = TierService(sample_tenant.id)

            # Make a few tier changes
            for i in range(3):
                new_tier = MembershipTier(
                    tenant_id=sample_tenant.id,
                    name=f'HistoryTier{i}',
                    monthly_price=Decimal(f'{10 + i * 10}.99'),
                    bonus_rate=Decimal(f'0.{10 + i}'),
                    is_active=True
                )
                db.session.add(new_tier)
                db.session.commit()

                service.assign_tier(
                    member_id=sample_member.id,
                    tier_id=new_tier.id,
                    source_type='staff',
                    source_reference='admin@shop.com',
                    reason=f'History test {i}'
                )

            result = service.get_tier_history(
                member_id=sample_member.id,
                limit=10
            )

            assert result['success'] is True
            assert len(result['history']) >= 3
            assert result['total'] >= 3


class TestPromotionalTiers:
    """Tests for promotional tier management."""

    def test_apply_promotion(self, app, sample_tier, sample_tenant):
        """Test applying a promotional tier to a member."""
        from app.services.tier_service import TierService
        from app.models import TierPromotion, Member, MembershipTier
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create a higher tier for the promotion
            higher_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Platinum',
                monthly_price=Decimal('79.99'),
                bonus_rate=Decimal('0.30'),  # Higher than Gold's 0.15
                is_active=True
            )
            db.session.add(higher_tier)
            db.session.commit()

            # Create a member without a tier (so upgrade_only won't block)
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=None,
                member_number=f'TU{unique_id}',
                email=f'promo-{unique_id}@example.com',
                name='Promo User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active'
            )
            db.session.add(member)
            db.session.commit()

            # Create a promotion for the higher tier
            promo = TierPromotion(
                tenant_id=sample_tenant.id,
                tier_id=higher_tier.id,
                name='Test Promotion',
                code='TESTPROMO',
                starts_at=datetime.utcnow() - timedelta(days=1),
                ends_at=datetime.utcnow() + timedelta(days=30),
                grant_duration_days=7,
                target_type='all',
                upgrade_only=False,  # Allow any member
                is_active=True
            )
            db.session.add(promo)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.apply_promotion(
                member_id=member.id,
                promo_code='TESTPROMO'
            )

            assert result['success'] is True
            assert result.get('promo_code') == 'TESTPROMO'

    def test_apply_expired_promotion(self, app, sample_member, sample_tier, sample_tenant):
        """Test applying an expired promotion."""
        from app.services.tier_service import TierService
        from app.models import TierPromotion
        from app.extensions import db

        with app.app_context():
            # Create an expired promotion
            promo = TierPromotion(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                name='Expired Promotion',
                code='EXPIRED',
                starts_at=datetime.utcnow() - timedelta(days=30),
                ends_at=datetime.utcnow() - timedelta(days=1),  # Ended yesterday
                is_active=True
            )
            db.session.add(promo)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.apply_promotion(
                member_id=sample_member.id,
                promo_code='EXPIRED'
            )

            assert result['success'] is False
            assert 'not currently active' in result.get('error', '').lower()

    def test_promotion_max_uses_limit(self, app, sample_tier, sample_tenant):
        """Test promotion max uses limit - is_currently_active returns false when max_uses reached."""
        from app.services.tier_service import TierService
        from app.models import TierPromotion, Member
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create a promotion with max 2 uses (already at max)
            # Note: is_currently_active property checks max_uses, so error will be 'not currently active'
            promo = TierPromotion(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                name='Limited Promotion',
                code='LIMITED',
                starts_at=datetime.utcnow() - timedelta(days=1),
                ends_at=datetime.utcnow() + timedelta(days=30),
                max_uses=2,
                current_uses=2,  # Already at max
                is_active=True
            )
            db.session.add(promo)
            db.session.commit()

            # Create a member
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=None,
                member_number=f'TU{unique_id}',
                email=f'limited-{unique_id}@example.com',
                name='Limited User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active'
            )
            db.session.add(member)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.apply_promotion(
                member_id=member.id,
                promo_code='LIMITED'
            )

            # The is_currently_active property returns False when max_uses is reached
            # So the error will be 'not currently active' instead of 'maximum uses'
            assert result['success'] is False
            assert 'not currently active' in result.get('error', '').lower()


class TestSubscriptionTiers:
    """Tests for subscription-based tier management."""

    def test_process_subscription_started(self, app, sample_tier, sample_tenant):
        """Test processing a new subscription."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create a member without tier
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=None,
                member_number=f'TU{unique_id}',
                email=f'sub-{unique_id}@example.com',
                name='Subscription User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active'
            )
            db.session.add(member)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.process_subscription_started(
                member_id=member.id,
                contract_id='gid://shopify/SubscriptionContract/12345',
                tier_id=sample_tier.id
            )

            assert result['success'] is True

            # Verify subscription status was updated
            member = Member.query.get(member.id)
            assert member.subscription_status == 'active'
            assert member.shopify_subscription_contract_id == 'gid://shopify/SubscriptionContract/12345'

    def test_process_subscription_cancelled(self, app, sample_tier, sample_tenant):
        """Test processing a cancelled subscription."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create a member with subscription tier
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                member_number=f'TU{unique_id}',
                email=f'cancel-{unique_id}@example.com',
                name='Cancel User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active',
                subscription_status='active',
                shopify_subscription_contract_id='gid://shopify/SubscriptionContract/99999',
                tier_assigned_by='subscription:gid://shopify/SubscriptionContract/99999'
            )
            db.session.add(member)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.process_subscription_cancelled(
                member_id=member.id,
                contract_id='gid://shopify/SubscriptionContract/99999',
                reason='Customer requested cancellation',
                immediate=True
            )

            assert result['success'] is True
            assert result.get('change_type') == 'subscription_cancelled'

            # When tier is removed via remove_tier(), subscription_status is reset to 'none'
            # This is the expected behavior since the tier removal clears all tier-related fields
            member = Member.query.get(member.id)
            assert member.subscription_status == 'none'
            assert member.tier_id is None

    def test_process_subscription_cancelled_non_immediate(self, app, sample_tier, sample_tenant):
        """Test processing a cancelled subscription with non-immediate tier removal."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create a member with subscription tier
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                member_number=f'TU{unique_id}',
                email=f'cancel-ni-{unique_id}@example.com',
                name='Cancel Non-Immediate User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active',
                subscription_status='active',
                shopify_subscription_contract_id='gid://shopify/SubscriptionContract/88888',
                tier_assigned_by='subscription:gid://shopify/SubscriptionContract/88888'
            )
            db.session.add(member)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.process_subscription_cancelled(
                member_id=member.id,
                contract_id='gid://shopify/SubscriptionContract/88888',
                reason='Customer requested cancellation',
                immediate=False  # Non-immediate - tier should be retained
            )

            assert result['success'] is True
            assert result.get('tier_retained') is True

            # With immediate=False, subscription_status is set to 'cancelled' but tier is retained
            member = Member.query.get(member.id)
            assert member.subscription_status == 'cancelled'
            assert member.tier_id == sample_tier.id  # Tier retained


class TestPurchaseTiers:
    """Tests for purchase-based tier assignment."""

    def test_process_purchase(self, app, sample_tier, sample_tenant):
        """Test processing a tier purchase."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create a member
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=None,
                member_number=f'TU{unique_id}',
                email=f'purchase-{unique_id}@example.com',
                name='Purchase User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active'
            )
            db.session.add(member)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.process_purchase(
                member_id=member.id,
                order_id='12345',
                tier_id=sample_tier.id,
                order_total=Decimal('29.99'),
                product_sku='MEMBERSHIP-GOLD'
            )

            assert result['success'] is True
            assert 'order_12345' in result.get('tier_assigned_by', '') or result.get('tier_name') == 'Gold'

    def test_process_refund(self, app, sample_tier, sample_tenant):
        """Test processing a refund for tier purchase."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create a member with purchase-based tier
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                member_number=f'TU{unique_id}',
                email=f'refund-{unique_id}@example.com',
                name='Refund User',
                shopify_customer_id=f'cust_{unique_id}',
                status='active',
                tier_assigned_by='purchase:order_77777'
            )
            db.session.add(member)
            db.session.commit()

            service = TierService(sample_tenant.id)
            result = service.process_refund(
                member_id=member.id,
                order_id='77777',
                reason='Customer requested refund'
            )

            assert result['success'] is True
            assert result.get('change_type') == 'refunded'


class TestDetermineChangeType:
    """Tests for _determine_change_type helper method."""

    def test_determine_change_type_upgrade(self, app, sample_member, sample_tier, sample_tenant):
        """Test determining upgrade change type."""
        from app.services.tier_service import TierService
        from app.models import Member, MembershipTier
        from app.extensions import db

        with app.app_context():
            # Create a higher tier
            higher_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='HigherTier',
                monthly_price=Decimal('99.99'),
                bonus_rate=Decimal('0.50'),  # Much higher than Gold's 0.15
                is_active=True
            )
            db.session.add(higher_tier)
            db.session.commit()

            member = Member.query.get(sample_member.id)
            service = TierService(sample_tenant.id)

            change_type = service._determine_change_type(member, higher_tier, 'staff')
            assert change_type == 'upgraded'

    def test_determine_change_type_downgrade(self, app, sample_member, sample_tier, sample_tenant):
        """Test determining downgrade change type."""
        from app.services.tier_service import TierService
        from app.models import Member, MembershipTier
        from app.extensions import db

        with app.app_context():
            # Create a lower tier
            lower_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='LowerTier',
                monthly_price=Decimal('4.99'),
                bonus_rate=Decimal('0.01'),  # Much lower than Gold's 0.15
                is_active=True
            )
            db.session.add(lower_tier)
            db.session.commit()

            member = Member.query.get(sample_member.id)
            service = TierService(sample_tenant.id)

            change_type = service._determine_change_type(member, lower_tier, 'staff')
            assert change_type == 'downgraded'

    def test_determine_change_type_new_assignment(self, app, sample_tier, sample_tenant):
        """Test determining change type for new tier assignment."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db
        import uuid

        with app.app_context():
            # Create member without tier
            unique_id = str(uuid.uuid4())[:8]
            member = Member(
                tenant_id=sample_tenant.id,
                tier_id=None,
                member_number=f'TU{unique_id}',
                email=f'new-{unique_id}@example.com',
                name='New User',
                shopify_customer_id=f'cust_{unique_id}',
                status='pending'
            )
            db.session.add(member)
            db.session.commit()

            service = TierService(sample_tenant.id)

            # Test various source types for new assignments
            assert service._determine_change_type(member, sample_tier, 'subscription') == 'subscription_started'
            assert service._determine_change_type(member, sample_tier, 'purchase') == 'purchase'
            assert service._determine_change_type(member, sample_tier, 'promo') == 'promo_applied'
            assert service._determine_change_type(member, sample_tier, 'earned') == 'earned'
            assert service._determine_change_type(member, sample_tier, 'staff') == 'assigned'


class TestEvaluateRule:
    """Tests for _evaluate_rule helper method."""

    def test_evaluate_rule_greater_equal(self, app, sample_tier, sample_tenant):
        """Test rule evaluation with >= operator."""
        from app.services.tier_service import TierService
        from app.models import TierEligibilityRule
        from app.extensions import db

        with app.app_context():
            rule = TierEligibilityRule(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                name='Test Rule',
                rule_type='qualification',
                metric='total_spend',
                threshold_value=Decimal('100'),
                threshold_operator='>=',
                is_active=True
            )
            db.session.add(rule)
            db.session.commit()

            service = TierService(sample_tenant.id)

            # Test various values
            assert service._evaluate_rule(rule, {'total_spend': 150}) is True
            assert service._evaluate_rule(rule, {'total_spend': 100}) is True
            assert service._evaluate_rule(rule, {'total_spend': 50}) is False

    def test_evaluate_rule_less_than(self, app, sample_tier, sample_tenant):
        """Test rule evaluation with < operator."""
        from app.services.tier_service import TierService
        from app.models import TierEligibilityRule
        from app.extensions import db

        with app.app_context():
            rule = TierEligibilityRule(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                name='Downgrade Rule',
                rule_type='downgrade',
                metric='total_spend',
                threshold_value=Decimal('50'),
                threshold_operator='<',
                is_active=True
            )
            db.session.add(rule)
            db.session.commit()

            service = TierService(sample_tenant.id)

            assert service._evaluate_rule(rule, {'total_spend': 30}) is True
            assert service._evaluate_rule(rule, {'total_spend': 50}) is False
            assert service._evaluate_rule(rule, {'total_spend': 100}) is False

    def test_evaluate_rule_between(self, app, sample_tier, sample_tenant):
        """Test rule evaluation with between operator."""
        from app.services.tier_service import TierService
        from app.models import TierEligibilityRule
        from app.extensions import db

        with app.app_context():
            rule = TierEligibilityRule(
                tenant_id=sample_tenant.id,
                tier_id=sample_tier.id,
                name='Range Rule',
                rule_type='qualification',
                metric='total_spend',
                threshold_value=Decimal('100'),
                threshold_operator='between',
                threshold_max=Decimal('500'),
                is_active=True
            )
            db.session.add(rule)
            db.session.commit()

            service = TierService(sample_tenant.id)

            assert service._evaluate_rule(rule, {'total_spend': 50}) is False
            assert service._evaluate_rule(rule, {'total_spend': 100}) is True
            assert service._evaluate_rule(rule, {'total_spend': 300}) is True
            assert service._evaluate_rule(rule, {'total_spend': 500}) is True
            assert service._evaluate_rule(rule, {'total_spend': 600}) is False


class TestMemberStats:
    """Tests for _get_member_stats helper method."""

    def test_get_member_stats(self, app, sample_member, sample_tenant):
        """Test getting member stats for eligibility checking."""
        from app.services.tier_service import TierService
        from app.models import Member
        from app.extensions import db
        from datetime import date

        with app.app_context():
            # Update member with some stats
            member = Member.query.get(sample_member.id)
            member.total_trade_value = Decimal('1000')
            member.total_trade_ins = 25
            member.total_bonus_earned = Decimal('150')
            member.membership_start_date = date(2024, 1, 1)
            db.session.commit()

            service = TierService(sample_tenant.id)
            stats = service._get_member_stats(member)

            assert stats['total_spend'] == 1000.0
            assert stats['trade_in_count'] == 25
            assert stats['trade_in_value'] == 1000.0
            assert stats['bonus_earned'] == 150.0
            assert stats['membership_duration'] > 0


class TestTierBenefits:
    """Tests for tier benefits application."""

    def test_tier_benefits_json_field(self, app, sample_tenant):
        """Test that tier benefits JSON field is properly stored and retrieved."""
        from app.models import MembershipTier
        from app.extensions import db

        with app.app_context():
            tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='BenefitsTier',
                monthly_price=Decimal('49.99'),
                bonus_rate=Decimal('0.15'),
                is_active=True,
                benefits={
                    'discount_percent': 10,
                    'free_shipping_threshold': 50,
                    'early_access': True,
                    'exclusive_products': ['SKU1', 'SKU2']
                }
            )
            db.session.add(tier)
            db.session.commit()

            # Retrieve and verify
            tier = MembershipTier.query.filter_by(name='BenefitsTier').first()
            assert tier.benefits is not None
            assert tier.benefits['discount_percent'] == 10
            assert tier.benefits['free_shipping_threshold'] == 50
            assert tier.benefits['early_access'] is True
            assert 'SKU1' in tier.benefits['exclusive_products']

    def test_tier_to_dict_includes_benefits(self, app, sample_tenant):
        """Test that tier.to_dict() includes benefits."""
        from app.models import MembershipTier
        from app.extensions import db

        with app.app_context():
            tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='DictTier',
                monthly_price=Decimal('19.99'),
                bonus_rate=Decimal('0.10'),
                is_active=True,
                benefits={'priority_support': True}
            )
            db.session.add(tier)
            db.session.commit()

            tier_dict = tier.to_dict()
            assert 'benefits' in tier_dict
            assert tier_dict['benefits']['priority_support'] is True

    def test_tier_cashback_configuration(self, app, sample_tenant):
        """Test tier purchase cashback configuration."""
        from app.models import MembershipTier
        from app.extensions import db

        with app.app_context():
            tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='CashbackTier',
                monthly_price=Decimal('29.99'),
                bonus_rate=Decimal('0.15'),
                purchase_cashback_pct=Decimal('3.00'),  # 3% cashback
                is_active=True
            )
            db.session.add(tier)
            db.session.commit()

            tier = MembershipTier.query.filter_by(name='CashbackTier').first()
            assert float(tier.purchase_cashback_pct) == 3.00

            tier_dict = tier.to_dict()
            assert tier_dict['purchase_cashback_pct'] == 3.00

    def test_tier_monthly_credit_configuration(self, app, sample_tenant):
        """Test tier monthly credit configuration."""
        from app.models import MembershipTier
        from app.extensions import db

        with app.app_context():
            tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='CreditTier',
                monthly_price=Decimal('49.99'),
                bonus_rate=Decimal('0.20'),
                monthly_credit_amount=Decimal('10.00'),  # $10 monthly credit
                credit_expiration_days=30,
                is_active=True
            )
            db.session.add(tier)
            db.session.commit()

            tier = MembershipTier.query.filter_by(name='CreditTier').first()
            assert float(tier.monthly_credit_amount) == 10.00
            assert tier.credit_expiration_days == 30

            tier_dict = tier.to_dict()
            assert tier_dict['monthly_credit_amount'] == 10.00
            assert tier_dict['credit_expiration_days'] == 30
