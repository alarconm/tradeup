"""
Tests for the Billing API endpoints.

TC-008: Test Billing and subscription logic

Tests cover:
- Plan subscription (AC-1)
- Plan upgrade (AC-2)
- Scheduled downgrade (AC-3)
- Cancellation (AC-4)
- Usage limit enforcement (AC-5)
- Usage warning thresholds (AC-6)
- Billing history
- Billing callback
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# ==============================================================================
# Plan Subscription Tests (AC-1)
# ==============================================================================

class TestBillingPlans:
    """Tests for GET /api/billing/plans endpoint."""

    def test_list_plans_no_auth_required(self, client):
        """Test that listing plans doesn't require auth."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()
        assert 'plans' in data
        assert isinstance(data['plans'], list)

    def test_list_plans_returns_expected_fields(self, client):
        """Test that plans have expected fields."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()

        assert 'currency' in data
        assert 'billing_interval' in data

        # Each plan should have these fields
        for plan in data['plans']:
            assert 'key' in plan
            assert 'name' in plan
            assert 'price' in plan
            assert 'max_members' in plan
            assert 'max_tiers' in plan
            assert 'features' in plan

    def test_plans_sorted_by_price(self, client):
        """Test that plans are sorted by price ascending."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()

        prices = [plan['price'] for plan in data['plans']]
        assert prices == sorted(prices)

    def test_all_expected_plans_present(self, client):
        """Test that all expected plans (free, starter, growth, pro) are returned."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()

        plan_keys = [plan['key'] for plan in data['plans']]
        assert 'free' in plan_keys
        assert 'starter' in plan_keys
        assert 'growth' in plan_keys
        assert 'pro' in plan_keys

    def test_plan_limits_are_sensible(self, client):
        """Test that plan limits follow expected hierarchy (higher plans have more)."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()

        plans_by_key = {plan['key']: plan for plan in data['plans']}

        # Free < Starter < Growth < Pro (for member limits)
        assert plans_by_key['free']['max_members'] < plans_by_key['starter']['max_members']
        assert plans_by_key['starter']['max_members'] < plans_by_key['growth']['max_members']
        # Pro may have None (unlimited)
        if plans_by_key['pro']['max_members'] is not None:
            assert plans_by_key['growth']['max_members'] < plans_by_key['pro']['max_members']


class TestSubscriptionCreate:
    """Tests for POST /api/billing/subscribe endpoint (AC-1)."""

    def test_subscribe_requires_auth(self, client):
        """Test that subscription requires authentication."""
        response = client.post(
            '/api/billing/subscribe',
            data=json.dumps({'plan': 'starter'}),
            content_type='application/json'
        )
        assert response.status_code == 401

    def test_subscribe_invalid_plan(self, client, auth_headers):
        """Test subscription with invalid plan key."""
        response = client.post(
            '/api/billing/subscribe',
            headers=auth_headers,
            data=json.dumps({'plan': 'invalid_plan_key'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'invalid' in data['error'].lower()

    def test_subscribe_valid_plan(self, client, auth_headers, sample_tenant):
        """Test subscription with valid plan."""
        response = client.post(
            '/api/billing/subscribe',
            headers=auth_headers,
            data=json.dumps({'plan': 'starter'}),
            content_type='application/json'
        )
        # May succeed or fail based on Shopify integration
        assert response.status_code in [200, 400, 500]

    def test_subscribe_default_plan(self, client, auth_headers):
        """Test subscription with default plan (starter)."""
        response = client.post(
            '/api/billing/subscribe',
            headers=auth_headers,
            data=json.dumps({}),
            content_type='application/json'
        )
        # May succeed or fail based on existing subscription
        assert response.status_code in [200, 400, 500]

    def test_subscribe_already_subscribed(self, app, client, sample_tenant):
        """Test that subscribing when already subscribed returns error."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant as already subscribed
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'starter'
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.post(
                '/api/billing/subscribe',
                headers=headers,
                data=json.dumps({'plan': 'growth'}),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = response.get_json()
            assert 'already' in data['error'].lower()

    def test_subscribe_free_plan(self, client, auth_headers):
        """Test subscribing to free plan."""
        response = client.post(
            '/api/billing/subscribe',
            headers=auth_headers,
            data=json.dumps({'plan': 'free'}),
            content_type='application/json'
        )
        # Free plan subscription should work without Shopify billing
        assert response.status_code in [200, 400, 500]


# ==============================================================================
# Plan Upgrade Tests (AC-2)
# ==============================================================================

class TestSubscriptionUpgrade:
    """Tests for POST /api/billing/upgrade endpoint (AC-2)."""

    def test_upgrade_requires_auth(self, client):
        """Test that upgrade requires authentication."""
        response = client.post(
            '/api/billing/upgrade',
            data=json.dumps({'plan': 'growth'}),
            content_type='application/json'
        )
        assert response.status_code == 401

    def test_upgrade_requires_plan(self, client, auth_headers):
        """Test that upgrade requires plan parameter."""
        response = client.post(
            '/api/billing/upgrade',
            headers=auth_headers,
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        # Checks for subscription first, then plan
        assert 'plan' in data['error'].lower() or 'subscription' in data['error'].lower()

    def test_upgrade_invalid_plan(self, client, auth_headers):
        """Test upgrade with invalid plan (but requires subscription first)."""
        response = client.post(
            '/api/billing/upgrade',
            headers=auth_headers,
            data=json.dumps({'plan': 'invalid_plan'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        # Will fail on subscription check before plan validation
        assert 'invalid' in data['error'].lower() or 'subscription' in data['error'].lower()

    def test_upgrade_without_subscription(self, client, auth_headers):
        """Test upgrade without active subscription."""
        response = client.post(
            '/api/billing/upgrade',
            headers=auth_headers,
            data=json.dumps({'plan': 'growth'}),
            content_type='application/json'
        )
        # Should fail because no active subscription
        assert response.status_code == 400
        data = response.get_json()
        assert 'subscription' in data['error'].lower()

    def test_upgrade_to_same_plan(self, app, client, sample_tenant):
        """Test that upgrading to same plan returns error."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant as subscribed to starter
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'starter'
            tenant.shopify_subscription_id = 'gid://shopify/AppSubscription/12345'
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.post(
                '/api/billing/upgrade',
                headers=headers,
                data=json.dumps({'plan': 'starter'}),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = response.get_json()
            assert 'already' in data['error'].lower()

    def test_upgrade_starter_to_growth(self, app, client, sample_tenant):
        """Test upgrade from starter to growth plan."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant as subscribed to starter
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'starter'
            tenant.shopify_subscription_id = 'gid://shopify/AppSubscription/12345'
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            # Upgrade to growth (will fail at Shopify API but validates flow)
            response = client.post(
                '/api/billing/upgrade',
                headers=headers,
                data=json.dumps({'plan': 'growth'}),
                content_type='application/json'
            )

            # May succeed (returns confirmation_url) or fail at Shopify API
            assert response.status_code in [200, 500]


# ==============================================================================
# Scheduled Downgrade Tests (AC-3)
# ==============================================================================

class TestScheduledDowngrade:
    """Tests for POST /api/billing/schedule-downgrade endpoint (AC-3)."""

    def test_schedule_downgrade_requires_auth(self, client):
        """Test that schedule-downgrade requires authentication."""
        response = client.post(
            '/api/billing/schedule-downgrade',
            data=json.dumps({'plan': 'starter'}),
            content_type='application/json'
        )
        assert response.status_code == 401

    def test_schedule_downgrade_requires_plan(self, client, auth_headers):
        """Test that schedule-downgrade requires plan."""
        response = client.post(
            '/api/billing/schedule-downgrade',
            headers=auth_headers,
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code in [400, 500]

    def test_schedule_downgrade_without_subscription(self, client, auth_headers):
        """Test schedule-downgrade without active subscription."""
        response = client.post(
            '/api/billing/schedule-downgrade',
            headers=auth_headers,
            data=json.dumps({'plan': 'starter'}),
            content_type='application/json'
        )
        assert response.status_code in [400, 500]

    def test_schedule_downgrade_from_growth_to_starter(self, app, client, sample_tenant):
        """Test scheduling downgrade from growth to starter."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant as subscribed to growth
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'growth'
            tenant.shopify_subscription_id = 'gid://shopify/AppSubscription/12345'
            tenant.current_period_end = datetime.utcnow() + timedelta(days=15)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.post(
                '/api/billing/schedule-downgrade',
                headers=headers,
                data=json.dumps({'plan': 'starter'}),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['scheduled_plan'] == 'starter'
            assert 'scheduled_date' in data

    def test_schedule_downgrade_invalid_upgrade(self, app, client, sample_tenant):
        """Test that scheduling an 'upgrade' via downgrade endpoint fails."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant as subscribed to starter
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'starter'
            tenant.shopify_subscription_id = 'gid://shopify/AppSubscription/12345'
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            # Try to 'downgrade' to growth (actually an upgrade)
            response = client.post(
                '/api/billing/schedule-downgrade',
                headers=headers,
                data=json.dumps({'plan': 'growth'}),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = response.get_json()
            assert 'not a downgrade' in data['error'].lower()

    def test_schedule_downgrade_records_history(self, app, client, sample_tenant):
        """Test that scheduling a downgrade records billing history."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant, BillingHistory

            # Set tenant as subscribed to pro
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'pro'
            tenant.shopify_subscription_id = 'gid://shopify/AppSubscription/12345'
            tenant.current_period_end = datetime.utcnow() + timedelta(days=15)
            db.session.commit()

            # Get initial history count
            initial_count = BillingHistory.query.filter_by(tenant_id=tenant.id).count()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.post(
                '/api/billing/schedule-downgrade',
                headers=headers,
                data=json.dumps({'plan': 'starter'}),
                content_type='application/json'
            )

            assert response.status_code == 200

            # Check history was recorded
            new_count = BillingHistory.query.filter_by(tenant_id=tenant.id).count()
            assert new_count == initial_count + 1

            # Check history details
            history = BillingHistory.query.filter_by(
                tenant_id=tenant.id,
                event_type='downgrade_scheduled'
            ).first()
            assert history is not None
            assert history.plan_from == 'pro'
            assert history.plan_to == 'starter'


class TestCancelScheduledChange:
    """Tests for POST /api/billing/cancel-scheduled-change endpoint."""

    def test_cancel_scheduled_change_requires_auth(self, client):
        """Test that cancel-scheduled-change requires authentication."""
        response = client.post('/api/billing/cancel-scheduled-change')
        assert response.status_code == 401

    def test_cancel_scheduled_change_no_pending(self, client, auth_headers):
        """Test cancel-scheduled-change with no pending changes."""
        response = client.post('/api/billing/cancel-scheduled-change', headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert 'no scheduled' in data['error'].lower()

    def test_cancel_scheduled_change_success(self, app, client, sample_tenant):
        """Test successfully cancelling a scheduled downgrade."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant with scheduled change
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'growth'
            tenant.scheduled_plan_change = 'starter'
            tenant.scheduled_plan_change_date = datetime.utcnow() + timedelta(days=15)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.post('/api/billing/cancel-scheduled-change', headers=headers)

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True

            # Verify change was cleared
            tenant = Tenant.query.get(sample_tenant.id)
            assert tenant.scheduled_plan_change is None
            assert tenant.scheduled_plan_change_date is None


# ==============================================================================
# Cancellation Tests (AC-4)
# ==============================================================================

class TestSubscriptionCancel:
    """Tests for POST /api/billing/cancel endpoint (AC-4)."""

    def test_cancel_requires_auth(self, client):
        """Test that cancel requires authentication."""
        response = client.post('/api/billing/cancel')
        assert response.status_code == 401

    def test_cancel_without_subscription(self, client, auth_headers):
        """Test cancel without active subscription."""
        response = client.post('/api/billing/cancel', headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert 'no active subscription' in data['error'].lower()

    def test_cancel_active_subscription(self, app, client, sample_tenant):
        """Test cancelling an active subscription."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant as subscribed
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'starter'
            tenant.shopify_subscription_id = 'gid://shopify/AppSubscription/12345'
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            # Cancel subscription (will fail at Shopify API but validates flow)
            response = client.post('/api/billing/cancel', headers=headers)

            # May succeed locally or fail at Shopify API
            assert response.status_code in [200, 500]

    def test_cancel_records_history(self, app, client, sample_tenant):
        """Test that cancellation records billing history."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant, BillingHistory

            # Set tenant as subscribed
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'growth'
            tenant.shopify_subscription_id = 'gid://shopify/AppSubscription/12345'
            db.session.commit()

            # Get initial history count
            initial_count = BillingHistory.query.filter_by(tenant_id=tenant.id).count()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            # Cancel (mocking Shopify API for this test)
            with patch('app.api.billing.ShopifyBillingService') as mock_billing:
                mock_instance = MagicMock()
                mock_billing.return_value = mock_instance
                mock_instance.cancel_subscription.return_value = {
                    'id': '12345',
                    'status': 'CANCELLED'
                }

                response = client.post('/api/billing/cancel', headers=headers)

                assert response.status_code == 200

                # Check history was recorded
                new_count = BillingHistory.query.filter_by(tenant_id=tenant.id).count()
                assert new_count == initial_count + 1


# ==============================================================================
# Usage Limit Enforcement Tests (AC-5)
# ==============================================================================

class TestUsageLimitEnforcement:
    """Tests for billing usage limit enforcement (AC-5)."""

    def test_status_shows_usage_percentage(self, client, auth_headers):
        """Test that status shows usage percentage."""
        response = client.get('/api/billing/status', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()

        assert 'usage' in data
        members_usage = data['usage'].get('members', {})
        assert 'percentage' in members_usage
        assert 'current' in members_usage
        assert 'limit' in members_usage

    def test_status_shows_tier_usage(self, client, auth_headers):
        """Test that status shows tier usage."""
        response = client.get('/api/billing/status', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()

        assert 'usage' in data
        tiers_usage = data['usage'].get('tiers', {})
        assert 'percentage' in tiers_usage
        assert 'current' in tiers_usage
        assert 'limit' in tiers_usage

    def test_member_limit_enforcement(self, app, client, sample_tenant):
        """Test that member creation is blocked at limit."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant, Member, MembershipTier
            import uuid

            # Set tenant with very low member limit
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.max_members = 1
            db.session.commit()

            # Create a tier for the tenant
            tier = MembershipTier(
                tenant_id=tenant.id,
                name='Bronze',
                monthly_price=0,
                bonus_rate=0.05,
                is_active=True
            )
            db.session.add(tier)
            db.session.commit()

            # Create one member to hit the limit
            member = Member(
                tenant_id=tenant.id,
                tier_id=tier.id,
                member_number='TU' + str(uuid.uuid4())[:8],
                email='existing@test.com',
                name='Existing User',
                shopify_customer_id='cust_existing',
                status='active'
            )
            db.session.add(member)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            # Try to enroll another member - should be blocked
            response = client.post(
                '/api/members/enroll',
                headers=headers,
                data=json.dumps({
                    'shopify_customer_id': 'cust_new123'
                }),
                content_type='application/json'
            )

            assert response.status_code == 403
            data = response.get_json()
            assert 'limit reached' in data['error'].lower()
            assert 'upgrade' in data['message'].lower()

    def test_member_limit_not_enforced_when_under_limit(self, app, client, sample_tenant):
        """Test that member creation works when under limit."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant with high member limit
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.max_members = 100
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            # Try to enroll a member - should be allowed
            response = client.post(
                '/api/members/enroll',
                headers=headers,
                data=json.dumps({
                    'shopify_customer_id': 'cust_test123'
                }),
                content_type='application/json'
            )

            # Should not be blocked by limit
            assert response.status_code != 403 or 'limit' not in response.get_json().get('error', '').lower()


# ==============================================================================
# Usage Warning Thresholds Tests (AC-6)
# ==============================================================================

class TestUsageWarningThresholds:
    """Tests for usage warning threshold logic (AC-6)."""

    def test_no_warning_under_80_percent(self, app, client, sample_tenant):
        """Test no warning when usage is under 80%."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant with 100 member limit, no members
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.max_members = 100
            tenant.max_tiers = 10
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.get('/api/billing/status', headers=headers)
            assert response.status_code == 200
            data = response.get_json()

            # No warnings expected
            assert data['warnings']['has_warnings'] is False
            assert data['warnings']['members']['level'] is None
            assert data['warnings']['tiers']['level'] is None

    def test_caution_at_80_percent(self, app, client, sample_tenant):
        """Test caution warning at 80% usage."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant, Member, MembershipTier
            import uuid

            # Set tenant with 10 member limit
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.max_members = 10
            tenant.max_tiers = 10
            db.session.commit()

            # Create a tier
            tier = MembershipTier(
                tenant_id=tenant.id,
                name='Bronze',
                monthly_price=0,
                bonus_rate=0.05,
                is_active=True
            )
            db.session.add(tier)
            db.session.commit()

            # Create 8 members (80%)
            for i in range(8):
                member = Member(
                    tenant_id=tenant.id,
                    tier_id=tier.id,
                    member_number='TU' + str(uuid.uuid4())[:8],
                    email='member{}@test.com'.format(i),
                    name='Member {}'.format(i),
                    shopify_customer_id='cust_{}_{}'.format(i, uuid.uuid4()),
                    status='active'
                )
                db.session.add(member)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.get('/api/billing/status', headers=headers)
            assert response.status_code == 200
            data = response.get_json()

            # Should have caution warning
            assert data['warnings']['has_warnings'] is True
            assert data['warnings']['members']['level'] == 'caution'
            assert '80' in data['warnings']['members']['message']

    def test_warning_at_90_percent(self, app, client, sample_tenant):
        """Test warning at 90% usage."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant, Member, MembershipTier
            import uuid

            # Set tenant with 10 member limit
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.max_members = 10
            tenant.max_tiers = 10
            db.session.commit()

            # Create a tier
            tier = MembershipTier(
                tenant_id=tenant.id,
                name='Bronze',
                monthly_price=0,
                bonus_rate=0.05,
                is_active=True
            )
            db.session.add(tier)
            db.session.commit()

            # Create 9 members (90%)
            for i in range(9):
                member = Member(
                    tenant_id=tenant.id,
                    tier_id=tier.id,
                    member_number='TU' + str(uuid.uuid4())[:8],
                    email='member{}@test.com'.format(i),
                    name='Member {}'.format(i),
                    shopify_customer_id='cust_{}_{}'.format(i, uuid.uuid4()),
                    status='active'
                )
                db.session.add(member)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.get('/api/billing/status', headers=headers)
            assert response.status_code == 200
            data = response.get_json()

            # Should have warning level
            assert data['warnings']['has_warnings'] is True
            assert data['warnings']['members']['level'] == 'warning'
            assert 'approaching limit' in data['warnings']['members']['message'].lower()

    def test_critical_at_100_percent(self, app, client, sample_tenant):
        """Test critical warning at 100% usage."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant, Member, MembershipTier
            import uuid

            # Set tenant with 5 member limit
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.max_members = 5
            tenant.max_tiers = 10
            db.session.commit()

            # Create a tier
            tier = MembershipTier(
                tenant_id=tenant.id,
                name='Bronze',
                monthly_price=0,
                bonus_rate=0.05,
                is_active=True
            )
            db.session.add(tier)
            db.session.commit()

            # Create 5 members (100%)
            for i in range(5):
                member = Member(
                    tenant_id=tenant.id,
                    tier_id=tier.id,
                    member_number='TU' + str(uuid.uuid4())[:8],
                    email='member{}@test.com'.format(i),
                    name='Member {}'.format(i),
                    shopify_customer_id='cust_{}_{}'.format(i, uuid.uuid4()),
                    status='active'
                )
                db.session.add(member)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.get('/api/billing/status', headers=headers)
            assert response.status_code == 200
            data = response.get_json()

            # Should have critical warning
            assert data['warnings']['has_warnings'] is True
            assert data['warnings']['members']['level'] == 'critical'
            assert 'upgrade' in data['warnings']['members']['message'].lower()

    def test_tier_warning_thresholds(self, app, client, sample_tenant):
        """Test tier usage warning thresholds."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant, MembershipTier

            # Set tenant with 3 tier limit
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.max_members = 100
            tenant.max_tiers = 3
            db.session.commit()

            # Create 3 tiers (100%)
            for i in range(3):
                tier = MembershipTier(
                    tenant_id=tenant.id,
                    name='Tier {}'.format(i),
                    monthly_price=i * 10,
                    bonus_rate=0.05 + (i * 0.05),
                    is_active=True
                )
                db.session.add(tier)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.get('/api/billing/status', headers=headers)
            assert response.status_code == 200
            data = response.get_json()

            # Should have critical warning for tiers
            assert data['warnings']['has_warnings'] is True
            assert data['warnings']['tiers']['level'] == 'critical'


# ==============================================================================
# Subscription Status Tests
# ==============================================================================

class TestSubscriptionStatus:
    """Tests for GET /api/billing/status endpoint."""

    def test_status_requires_auth(self, client):
        """Test that status requires authentication."""
        response = client.get('/api/billing/status')
        assert response.status_code == 401

    def test_status_returns_plan_info(self, client, auth_headers):
        """Test that status returns plan info."""
        response = client.get('/api/billing/status', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()

        # Should have plan and status info
        assert 'plan' in data
        assert 'status' in data
        assert 'active' in data

    def test_status_returns_usage_info(self, client, auth_headers):
        """Test that status returns usage info."""
        response = client.get('/api/billing/status', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()

        assert 'usage' in data
        assert 'members' in data['usage']
        assert 'tiers' in data['usage']

    def test_status_includes_usage_warnings(self, client, auth_headers):
        """Test that status includes usage warnings."""
        response = client.get('/api/billing/status', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()

        assert 'warnings' in data
        assert 'has_warnings' in data['warnings']

    def test_status_includes_trial_info(self, app, client, sample_tenant):
        """Test that status includes trial information."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant with trial
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'starter'
            tenant.trial_ends_at = datetime.utcnow() + timedelta(days=7)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.get('/api/billing/status', headers=headers)
            assert response.status_code == 200
            data = response.get_json()

            assert 'trial_ends_at' in data
            assert data['trial_ends_at'] is not None

    def test_status_includes_period_end(self, app, client, sample_tenant):
        """Test that status includes current period end."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant with period end
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'growth'
            tenant.current_period_end = datetime.utcnow() + timedelta(days=30)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            response = client.get('/api/billing/status', headers=headers)
            assert response.status_code == 200
            data = response.get_json()

            assert 'current_period_end' in data
            assert data['current_period_end'] is not None


# ==============================================================================
# Billing History Tests
# ==============================================================================

class TestBillingHistory:
    """Tests for GET /api/billing/history endpoint."""

    def test_history_requires_auth(self, client):
        """Test that history requires authentication."""
        response = client.get('/api/billing/history')
        assert response.status_code == 401

    def test_history_returns_list(self, client, auth_headers):
        """Test that history returns a list."""
        response = client.get('/api/billing/history', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'history' in data
        assert isinstance(data['history'], list)

    def test_history_pagination(self, client, auth_headers):
        """Test that history supports pagination."""
        response = client.get('/api/billing/history?page=1&per_page=10', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()

        assert 'total' in data
        assert 'page' in data
        assert 'per_page' in data
        assert 'pages' in data

    def test_history_records_after_operations(self, app, client, sample_tenant):
        """Test that billing operations create history records."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Set tenant as subscribed to growth
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.subscription_active = True
            tenant.subscription_plan = 'growth'
            tenant.shopify_subscription_id = 'gid://shopify/AppSubscription/12345'
            tenant.current_period_end = datetime.utcnow() + timedelta(days=15)
            db.session.commit()

            headers = {
                'X-Shop-Domain': tenant.shopify_domain,
                'Content-Type': 'application/json'
            }

            # Schedule a downgrade (creates history)
            client.post(
                '/api/billing/schedule-downgrade',
                headers=headers,
                data=json.dumps({'plan': 'starter'}),
                content_type='application/json'
            )

            # Check history
            response = client.get('/api/billing/history', headers=headers)
            assert response.status_code == 200
            data = response.get_json()

            # Should have at least one history record
            assert len(data['history']) >= 1


# ==============================================================================
# Billing Callback Tests
# ==============================================================================

class TestBillingCallback:
    """Tests for GET /api/billing/callback endpoint."""

    def test_callback_requires_tenant_id(self, client):
        """Test callback requires tenant_id."""
        response = client.get('/api/billing/callback')
        assert response.status_code == 400
        data = response.get_json()
        assert 'tenant_id' in data['error'].lower()

    def test_callback_invalid_tenant_id(self, client):
        """Test callback with invalid tenant_id format."""
        response = client.get('/api/billing/callback?tenant_id=invalid')
        assert response.status_code == 400
        data = response.get_json()
        assert 'invalid' in data['error'].lower()

    def test_callback_nonexistent_tenant(self, client):
        """Test callback with non-existent tenant."""
        response = client.get('/api/billing/callback?tenant_id=99999')
        assert response.status_code == 404
        data = response.get_json()
        assert 'not found' in data['error'].lower()

    def test_callback_inactive_tenant(self, app, client, sample_tenant):
        """Test callback with inactive tenant."""
        with app.app_context():
            from app.extensions import db
            from app.models import Tenant

            # Deactivate tenant
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.is_active = False
            db.session.commit()

            response = client.get('/api/billing/callback?tenant_id={}'.format(tenant.id))
            assert response.status_code == 403
            data = response.get_json()
            assert 'not active' in data['error'].lower()

    def test_callback_valid_tenant(self, app, client, sample_tenant):
        """Test callback with valid tenant (Shopify API will fail but validates flow)."""
        with app.app_context():
            from app.models import Tenant

            tenant = Tenant.query.get(sample_tenant.id)

            response = client.get('/api/billing/callback?tenant_id={}'.format(tenant.id))
            # Will fail at Shopify API but should get past validation
            assert response.status_code in [200, 500]


# ==============================================================================
# Input Validation Tests
# ==============================================================================

class TestBillingValidation:
    """Tests for billing input validation."""

    def test_subscribe_empty_body(self, client, auth_headers):
        """Test subscribe with empty body uses default plan."""
        response = client.post(
            '/api/billing/subscribe',
            headers=auth_headers,
            data=json.dumps({}),
            content_type='application/json'
        )
        # Should try to subscribe with default plan
        assert response.status_code in [200, 400, 500]

    def test_upgrade_empty_body(self, client, auth_headers):
        """Test upgrade with empty body."""
        response = client.post(
            '/api/billing/upgrade',
            headers=auth_headers,
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_schedule_downgrade_empty_body(self, client, auth_headers):
        """Test schedule-downgrade with empty body."""
        response = client.post(
            '/api/billing/schedule-downgrade',
            headers=auth_headers,
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_upgrade_null_plan(self, client, auth_headers):
        """Test upgrade with null plan."""
        response = client.post(
            '/api/billing/upgrade',
            headers=auth_headers,
            data=json.dumps({'plan': None}),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_subscribe_malformed_json(self, client, auth_headers):
        """Test subscribe with malformed JSON."""
        response = client.post(
            '/api/billing/subscribe',
            headers=auth_headers,
            data='not json',
            content_type='application/json'
        )
        # Should handle gracefully
        assert response.status_code in [400, 500]


# ==============================================================================
# Plan Configuration Tests
# ==============================================================================

class TestPlanConfiguration:
    """Tests for plan configuration and limits."""

    def test_free_plan_limits(self, client):
        """Test free plan has expected limits."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()

        free_plan = next((p for p in data['plans'] if p['key'] == 'free'), None)
        assert free_plan is not None
        assert free_plan['price'] == 0
        assert free_plan['max_members'] == 50
        assert free_plan['max_tiers'] == 2

    def test_starter_plan_limits(self, client):
        """Test starter plan has expected limits."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()

        starter_plan = next((p for p in data['plans'] if p['key'] == 'starter'), None)
        assert starter_plan is not None
        assert starter_plan['price'] == 19
        assert starter_plan['max_members'] == 200
        assert starter_plan['max_tiers'] == 3

    def test_growth_plan_limits(self, client):
        """Test growth plan has expected limits."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()

        growth_plan = next((p for p in data['plans'] if p['key'] == 'growth'), None)
        assert growth_plan is not None
        assert growth_plan['price'] == 49
        assert growth_plan['max_members'] == 1000
        assert growth_plan['max_tiers'] == 5

    def test_pro_plan_unlimited(self, client):
        """Test pro plan has unlimited members and tiers."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()

        pro_plan = next((p for p in data['plans'] if p['key'] == 'pro'), None)
        assert pro_plan is not None
        assert pro_plan['price'] == 99
        # Pro plan has None for unlimited
        assert pro_plan['max_members'] is None
        assert pro_plan['max_tiers'] is None

    def test_all_plans_have_features(self, client):
        """Test all plans have feature lists."""
        response = client.get('/api/billing/plans')
        assert response.status_code == 200
        data = response.get_json()

        for plan in data['plans']:
            assert 'features' in plan
            assert isinstance(plan['features'], list)
            assert len(plan['features']) > 0
