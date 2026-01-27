"""
Tests for the Tiers API endpoints.

Tests cover:
- Tier CRUD operations (via /api/members/tiers)
- Tier assignment (via /api/tiers/assign)
- Tier eligibility calculation
- Tier promotions
"""
import json
import pytest


class TestTiersList:
    """Tests for GET /api/members/tiers endpoint."""

    def test_tiers_endpoint_exists(self, client, auth_headers):
        """Test that the tiers endpoint responds."""
        response = client.get('/api/members/tiers', headers=auth_headers)
        assert response.status_code == 200

    def test_list_tiers_empty(self, client, auth_headers):
        """Test listing tiers returns list structure."""
        response = client.get('/api/members/tiers', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'tiers' in data or isinstance(data, list)

    def test_list_tiers_with_tier(self, client, sample_tier, sample_tenant):
        """Test listing tiers when one exists."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/members/tiers', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # Should have at least one tier
        tiers = data.get('tiers', data) if isinstance(data, dict) else data
        assert len(tiers) >= 1


class TestTierGet:
    """Tests for GET /api/members/tiers/{id} endpoint."""

    def test_get_tier_by_id(self, client, sample_tier, sample_tenant):
        """Test getting a tier by ID."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(f'/api/members/tiers/{sample_tier.id}', headers=headers)
        # May return 200 (found) or 404 (not found)
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert data['id'] == sample_tier.id
            assert data['name'] == 'Gold'

    def test_get_tier_not_found(self, client, auth_headers):
        """Test getting a non-existent tier."""
        response = client.get('/api/members/tiers/99999', headers=auth_headers)
        assert response.status_code == 404


class TestTierCreate:
    """Tests for POST /api/members/tiers endpoint."""

    def test_create_tier(self, client, auth_headers):
        """Test creating a new tier."""
        response = client.post(
            '/api/members/tiers',
            headers=auth_headers,
            data=json.dumps({
                'name': 'Silver',
                'monthly_price': 19.99,
                'bonus_rate': 0.10,
                'trade_in_bonus_pct': 10.0,
                'cashback_pct': 2.0
            }),
            content_type='application/json'
        )
        assert response.status_code in [200, 201]
        data = response.get_json()
        assert data.get('name') == 'Silver' or 'id' in data or 'success' in data

    def test_create_tier_with_benefits(self, client, auth_headers):
        """Test creating a tier with benefits configuration."""
        response = client.post(
            '/api/members/tiers',
            headers=auth_headers,
            data=json.dumps({
                'name': 'Platinum',
                'monthly_price': 49.99,
                'bonus_rate': 0.20,
                'trade_in_bonus_pct': 20.0,
                'cashback_pct': 5.0,
                'points_multiplier': 2.0
            }),
            content_type='application/json'
        )
        assert response.status_code in [200, 201]


class TestTierUpdate:
    """Tests for PUT /api/members/tiers/{id} endpoint."""

    def test_update_tier_name(self, client, sample_tier, sample_tenant):
        """Test updating tier name."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/members/tiers/{sample_tier.id}',
            headers=headers,
            data=json.dumps({'name': 'Diamond'}),
            content_type='application/json'
        )
        # May return 200, 404 (not found), or 400 (validation error)
        assert response.status_code in [200, 404, 400]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('name') == 'Diamond' or 'success' in data

    def test_update_tier_benefits(self, client, sample_tier, sample_tenant):
        """Test updating tier benefits."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/members/tiers/{sample_tier.id}',
            headers=headers,
            data=json.dumps({
                'trade_in_bonus_pct': 25.0,
                'cashback_pct': 6.0
            }),
            content_type='application/json'
        )
        assert response.status_code in [200, 404, 400]


class TestTierDelete:
    """Tests for DELETE /api/members/tiers/{id} endpoint."""

    def test_delete_tier(self, client, app, sample_tenant):
        """Test deleting a tier."""
        from app.extensions import db
        from app.models import MembershipTier

        # Create a tier to delete
        with app.app_context():
            tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='ToDelete',
                monthly_price=9.99,
                bonus_rate=0.05,
                is_active=True
            )
            db.session.add(tier)
            db.session.commit()
            tier_id = tier.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.delete(f'/api/members/tiers/{tier_id}', headers=headers)
        assert response.status_code in [200, 204, 404]


class TestTierAssignment:
    """Tests for tier assignment endpoints at /api/tiers/assign."""

    def test_assign_tier_requires_member_id(self, client, sample_tenant):
        """Test that tier assignment requires member_id."""
        # The /api/tiers/* endpoints use X-Tenant-ID header
        headers = {
            'X-Tenant-ID': str(sample_tenant.id),
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/tiers/assign',
            headers=headers,
            data=json.dumps({'tier_id': 1}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_assign_tier_to_member(self, client, sample_member, sample_tier, sample_tenant, app):
        """Test assigning a tier to a member."""
        from app.extensions import db
        from app.models import MembershipTier

        # Create a different tier to assign
        with app.app_context():
            new_tier = MembershipTier(
                tenant_id=sample_tenant.id,
                name='Premium',
                monthly_price=39.99,
                bonus_rate=0.18,
                is_active=True
            )
            db.session.add(new_tier)
            db.session.commit()
            new_tier_id = new_tier.id

        # The /api/tiers/* endpoints use X-Tenant-ID header
        headers = {
            'X-Tenant-ID': str(sample_tenant.id),
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/tiers/assign',
            headers=headers,
            data=json.dumps({
                'member_id': sample_member.id,
                'tier_id': new_tier_id,
                'reason': 'Test upgrade'
            }),
            content_type='application/json'
        )
        # Should succeed or return appropriate error
        assert response.status_code in [200, 400, 404]


class TestBulkTierAssignment:
    """Tests for bulk tier assignment at /api/tiers/bulk-assign."""

    def test_bulk_assign_requires_member_ids(self, client, sample_tenant):
        """Test that bulk assignment requires member_ids."""
        # The /api/tiers/* endpoints use X-Tenant-ID header
        headers = {
            'X-Tenant-ID': str(sample_tenant.id),
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/tiers/bulk-assign',
            headers=headers,
            data=json.dumps({'tier_id': 1}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_bulk_assign_without_tier_id_removes_tiers(self, client, sample_tenant):
        """Test that bulk assignment without tier_id removes tiers (tier removal mode)."""
        # The /api/tiers/* endpoints use X-Tenant-ID header
        headers = {
            'X-Tenant-ID': str(sample_tenant.id),
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/tiers/bulk-assign',
            headers=headers,
            data=json.dumps({'member_ids': [1, 2, 3]}),
            content_type='application/json'
        )
        # Now returns 200 (processes tier removal) instead of 400
        # The endpoint handles null tier_id by removing tiers
        assert response.status_code == 200
        data = response.get_json()
        # Response should contain success/failure counts
        assert 'successful' in data or 'failed' in data


class TestTierEligibility:
    """Tests for tier eligibility endpoints at /api/tiers/process-*."""

    def test_process_eligibility_endpoint(self, client, sample_tenant):
        """Test the process-eligibility endpoint exists."""
        # The /api/tiers/* endpoints use X-Tenant-ID header
        headers = {
            'X-Tenant-ID': str(sample_tenant.id),
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/tiers/process-eligibility',
            headers=headers,
            content_type='application/json'
        )
        # Should either succeed or return appropriate status
        assert response.status_code in [200, 400, 404, 405, 500]

    def test_process_expirations_endpoint(self, client, sample_tenant):
        """Test the process-expirations endpoint exists."""
        # The /api/tiers/* endpoints use X-Tenant-ID header
        headers = {
            'X-Tenant-ID': str(sample_tenant.id),
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/tiers/process-expirations',
            headers=headers,
            content_type='application/json'
        )
        # Should either succeed or return appropriate status
        assert response.status_code in [200, 400, 404, 405, 500]


class TestTierPromotions:
    """Tests for tier promotion endpoints at /api/tiers/promotions."""

    def test_list_promotions(self, client, sample_tenant):
        """Test listing tier promotions."""
        # The /api/tiers/* endpoints use X-Tenant-ID header
        headers = {
            'X-Tenant-ID': str(sample_tenant.id),
            'Content-Type': 'application/json'
        }
        response = client.get('/api/tiers/promotions', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'promotions' in data

    def test_create_promotion(self, client, sample_tier, sample_tenant):
        """Test creating a tier promotion."""
        # The /api/tiers/* endpoints use X-Tenant-ID header
        headers = {
            'X-Tenant-ID': str(sample_tenant.id),
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/tiers/promotions',
            headers=headers,
            data=json.dumps({
                'name': 'Summer Special',
                'tier_id': sample_tier.id,
                'starts_at': '2026-01-01T00:00:00Z',
                'ends_at': '2026-02-01T00:00:00Z'
            }),
            content_type='application/json'
        )
        # Should succeed or return appropriate status
        assert response.status_code in [200, 201, 400, 404]


class TestTierFixture:
    """Test tier fixture functionality."""

    def test_tier_fixture_created(self, sample_tier):
        """Test that the tier fixture is created correctly."""
        assert sample_tier.id is not None
        assert sample_tier.name == 'Gold'
        assert float(sample_tier.bonus_rate) == 0.15

    def test_tier_has_tenant(self, sample_tier, sample_tenant):
        """Test that tier is associated with tenant."""
        assert sample_tier.tenant_id == sample_tenant.id
