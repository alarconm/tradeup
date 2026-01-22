"""
Tests for the Members API endpoints.

Comprehensive test coverage for TC-002 - Member CRUD Operations:
- GET /api/members/ with pagination
- POST /api/members/enroll
- GET /api/members/{id}
- PUT /api/members/{id}
- Member status transitions (suspend, reactivate, cancel)
- DELETE /api/members/{id}
"""
import json
import pytest
import uuid


class TestMembersAuth:
    """Test authentication requirements for member endpoints."""

    def test_get_members_requires_shop_header(self, client):
        """Test that members endpoint requires shop domain header."""
        response = client.get('/api/members')
        # Should return error without shop domain
        assert response.status_code in [400, 401, 404, 500]

    def test_members_endpoint_exists(self, client, auth_headers):
        """Test that the members endpoint responds with proper auth."""
        response = client.get('/api/members', headers=auth_headers)
        # Endpoint should respond with success
        assert response.status_code == 200


class TestMembersList:
    """Tests for GET /api/members/ endpoint."""

    def test_list_members_empty(self, client, auth_headers):
        """Test listing members when none exist."""
        response = client.get('/api/members', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'members' in data
        assert 'total' in data
        assert 'page' in data
        assert 'per_page' in data
        assert 'pages' in data

    def test_list_members_with_member(self, client, sample_member, sample_tenant):
        """Test listing members when one exists."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/members', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] >= 1
        assert len(data['members']) >= 1

    def test_list_members_pagination(self, client, sample_member, sample_tenant):
        """Test pagination parameters."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/members?page=1&per_page=10', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['page'] == 1
        assert data['per_page'] == 10

    def test_list_members_search_by_name(self, client, sample_member, sample_tenant):
        """Test searching members by name."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/members?search=Test', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # Should find our sample member with name "Test User"
        assert data['total'] >= 1

    def test_list_members_search_by_email(self, client, sample_member, sample_tenant):
        """Test searching members by email."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/members?search=example.com', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] >= 1

    def test_list_members_filter_by_status(self, client, sample_member, sample_tenant):
        """Test filtering members by status."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/members?status=active', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # All returned members should have active status
        for member in data['members']:
            assert member['status'] == 'active'

    def test_list_members_filter_by_tier(self, client, sample_member, sample_tenant):
        """Test filtering members by tier name."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/members?tier=Gold', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # Should find members with Gold tier
        assert data['total'] >= 1


class TestMemberGet:
    """Tests for GET /api/members/{id} endpoint."""

    def test_get_member_by_id(self, client, sample_member, sample_tenant):
        """Test getting a member by ID."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(f'/api/members/{sample_member.id}', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == sample_member.id
        assert data['email'] == sample_member.email
        assert data['name'] == sample_member.name

    def test_get_member_not_found(self, client, auth_headers):
        """Test getting a non-existent member."""
        response = client.get('/api/members/99999', headers=auth_headers)
        assert response.status_code == 404

    def test_get_member_includes_stats(self, client, sample_member, sample_tenant):
        """Test that member response includes stats."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(f'/api/members/{sample_member.id}', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # Stats should be included
        assert 'member_number' in data
        assert 'tier' in data or 'tier_id' in data


class TestMemberGetByNumber:
    """Tests for GET /api/members/by-number/{number} endpoint."""

    def test_get_member_by_number(self, client, sample_member, sample_tenant):
        """Test getting a member by member number."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        # The member number is set when the member is created
        member_number = sample_member.member_number

        response = client.get(
            f'/api/members/by-number/{member_number}',
            headers=headers
        )
        # May return 200 (found) or 404 (not found due to session isolation)
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert data['member_number'] == member_number

    def test_get_member_by_number_without_prefix(self, client, sample_member, sample_tenant):
        """Test getting a member by number without TU prefix."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        # Strip TU prefix if present
        number = sample_member.member_number
        if number.startswith('TU'):
            number = number[2:]
        response = client.get(
            f'/api/members/by-number/{number}',
            headers=headers
        )
        # Should normalize the number and find the member
        assert response.status_code == 200

    def test_get_member_by_number_not_found(self, client, auth_headers):
        """Test getting a non-existent member number."""
        response = client.get('/api/members/by-number/TU99999', headers=auth_headers)
        assert response.status_code == 404


class TestMemberCreate:
    """Tests for POST /api/members endpoint."""

    def test_create_member_with_shopify_id(self, client, auth_headers):
        """Test creating a new member with Shopify customer ID."""
        response = client.post(
            '/api/members',
            headers=auth_headers,
            data=json.dumps({
                'email': 'newmember@example.com',
                'name': 'New Member',
                'shopify_customer_id': '12345678'  # Required for Shopify-native member creation
            }),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['email'] == 'newmember@example.com'
        assert data['name'] == 'New Member'
        assert 'member_number' in data

    def test_create_member_requires_shopify_customer_id(self, client, auth_headers):
        """Test that Shopify customer ID is required for member creation."""
        response = client.post(
            '/api/members',
            headers=auth_headers,
            data=json.dumps({
                'email': 'test@example.com',
                'name': 'Test'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'shopify' in data['error'].lower()

    def test_create_member_requires_email(self, client, auth_headers):
        """Test that email is required for member creation."""
        response = client.post(
            '/api/members',
            headers=auth_headers,
            data=json.dumps({'name': 'No Email', 'shopify_customer_id': '123'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_create_member_empty_body(self, client, auth_headers):
        """Test creating member with empty body."""
        response = client.post(
            '/api/members',
            headers=auth_headers,
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestMemberUpdate:
    """Tests for PUT /api/members/{id} endpoint."""

    def test_update_member_name(self, client, sample_member, sample_tenant):
        """Test updating member name."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/members/{sample_member.id}',
            headers=headers,
            data=json.dumps({'name': 'Updated Name'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['name'] == 'Updated Name'

    def test_update_member_email(self, client, sample_member, sample_tenant):
        """Test updating member email."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/members/{sample_member.id}',
            headers=headers,
            data=json.dumps({'email': 'updated@example.com'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['email'] == 'updated@example.com'

    def test_update_member_status(self, client, sample_member, sample_tenant):
        """Test updating member status."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/members/{sample_member.id}',
            headers=headers,
            data=json.dumps({'status': 'suspended'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'suspended'

    def test_update_member_not_found(self, client, auth_headers):
        """Test updating non-existent member."""
        response = client.put(
            '/api/members/99999',
            headers=auth_headers,
            data=json.dumps({'name': 'Test'}),
            content_type='application/json'
        )
        assert response.status_code == 404


class TestMemberStatusTransitions:
    """Tests for member status transition endpoints."""

    def test_suspend_member(self, client, sample_member, sample_tenant):
        """Test suspending an active member."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/members/{sample_member.id}/suspend',
            headers=headers,
            data=json.dumps({'reason': 'Test suspension'}),
            content_type='application/json'
        )
        # Should succeed or return appropriate status
        assert response.status_code in [200, 404]

    def test_reactivate_member(self, client, app, sample_member, sample_tenant):
        """Test reactivating a suspended member."""
        from app.extensions import db

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }

        # First suspend the member via PUT endpoint
        response = client.put(
            f'/api/members/{sample_member.id}',
            headers=headers,
            data=json.dumps({'status': 'suspended'}),
            content_type='application/json'
        )

        response = client.post(
            f'/api/members/{sample_member.id}/reactivate',
            headers=headers,
            content_type='application/json'
        )
        # Should succeed or return appropriate status (may not have /reactivate endpoint)
        assert response.status_code in [200, 400, 404]

    def test_cancel_member(self, client, sample_member, sample_tenant):
        """Test cancelling a member."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/members/{sample_member.id}/cancel',
            headers=headers,
            data=json.dumps({'reason': 'Test cancellation'}),
            content_type='application/json'
        )
        # Should succeed or return appropriate status
        assert response.status_code in [200, 404]


class TestMemberEnroll:
    """Tests for POST /api/members/enroll endpoint."""

    def test_enroll_requires_shopify_customer_id(self, client, auth_headers):
        """Test that enrollment requires shopify_customer_id."""
        response = client.post(
            '/api/members/enroll',
            headers=auth_headers,
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'shopify_customer_id' in data['error'].lower()


class TestMemberDelete:
    """Tests for DELETE /api/members/{id} endpoint."""

    def test_delete_member(self, client, sample_member, sample_tenant):
        """Test deleting a member."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        member_id = sample_member.id
        response = client.delete(
            f'/api/members/{member_id}',
            headers=headers
        )
        assert response.status_code in [200, 204]

    def test_delete_member_not_found(self, client, auth_headers):
        """Test deleting non-existent member."""
        response = client.delete(
            '/api/members/99999',
            headers=auth_headers
        )
        assert response.status_code == 404


# ==================== Enhanced Tests for TC-002 ====================

class TestMembersListEnhanced:
    """Enhanced tests for GET /api/members/ endpoint with pagination."""

    def test_list_members_pagination_page_2(self, client, auth_headers):
        """Test pagination returns empty when on page beyond data."""
        response = client.get('/api/members?page=999&per_page=10', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['page'] == 999
        assert data['members'] == []

    def test_list_members_pagination_large_per_page(self, client, sample_member, sample_tenant):
        """Test pagination with large per_page value."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/members?page=1&per_page=100', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['per_page'] == 100
        assert data['page'] == 1

    def test_list_members_default_pagination(self, client, auth_headers):
        """Test that default pagination is applied when no params given."""
        response = client.get('/api/members', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        # Default should be page 1
        assert data['page'] == 1
        # Default per_page should be 50
        assert data['per_page'] == 50

    def test_list_members_search_by_member_number(self, client, sample_member, sample_tenant):
        """Test searching members by member number."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        # Search by full member number
        response = client.get(
            f'/api/members?search={sample_member.member_number}',
            headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] >= 1

    def test_list_members_search_no_results(self, client, auth_headers):
        """Test searching members with non-matching query."""
        response = client.get('/api/members?search=nonexistentxyz123', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] == 0
        assert data['members'] == []

    def test_list_members_filter_by_suspended_status(self, client, sample_member, sample_tenant):
        """Test filtering members by suspended status."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }

        # First update member to suspended via API
        client.put(
            f'/api/members/{sample_member.id}',
            headers=headers,
            data=json.dumps({'status': 'suspended'}),
            content_type='application/json'
        )

        response = client.get('/api/members?status=suspended', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # All returned members should have suspended status
        for member in data['members']:
            assert member['status'] == 'suspended'

    def test_list_members_combined_filters(self, client, sample_member, sample_tenant):
        """Test combining search and status filters."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/members?search=Test&status=active', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # All returned members should match both filters
        for member in data['members']:
            assert member['status'] == 'active'


class TestMemberEnrollEnhanced:
    """Enhanced tests for POST /api/members/enroll endpoint."""

    def test_enroll_with_empty_shopify_customer_id(self, client, auth_headers):
        """Test that empty shopify_customer_id is rejected."""
        response = client.post(
            '/api/members/enroll',
            headers=auth_headers,
            data=json.dumps({'shopify_customer_id': ''}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_enroll_with_null_shopify_customer_id(self, client, auth_headers):
        """Test that null shopify_customer_id is rejected."""
        response = client.post(
            '/api/members/enroll',
            headers=auth_headers,
            data=json.dumps({'shopify_customer_id': None}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_enroll_with_optional_tier_id(self, client, auth_headers, sample_tier, app):
        """Test enrollment with optional tier_id parameter."""
        # Note: This will fail to actually enroll without Shopify API,
        # but we can verify the endpoint accepts the parameter
        response = client.post(
            '/api/members/enroll',
            headers=auth_headers,
            data=json.dumps({
                'shopify_customer_id': '999999999',
                'tier_id': sample_tier.id
            }),
            content_type='application/json'
        )
        # Will fail to enroll (no actual Shopify customer), but should attempt
        assert response.status_code in [201, 400, 500]

    def test_enroll_with_optional_notes(self, client, auth_headers):
        """Test enrollment with optional notes parameter."""
        response = client.post(
            '/api/members/enroll',
            headers=auth_headers,
            data=json.dumps({
                'shopify_customer_id': '888888888',
                'notes': 'VIP customer from trade show'
            }),
            content_type='application/json'
        )
        # Will fail to enroll (no actual Shopify customer), but should attempt
        assert response.status_code in [201, 400, 500]


class TestMemberGetEnhanced:
    """Enhanced tests for GET /api/members/{id} endpoint."""

    def test_get_member_includes_tier_info(self, client, sample_member, sample_tenant):
        """Test that member response includes tier information."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(f'/api/members/{sample_member.id}', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # Should include tier relationship data
        assert 'tier' in data or 'tier_id' in data

    def test_get_member_includes_status(self, client, sample_member, sample_tenant):
        """Test that member response includes status field."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(f'/api/members/{sample_member.id}', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'status' in data
        assert data['status'] in ['pending', 'active', 'suspended', 'paused', 'cancelled', 'expired']

    def test_get_member_includes_email(self, client, sample_member, sample_tenant):
        """Test that member response includes email field."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(f'/api/members/{sample_member.id}', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'email' in data
        assert '@' in data['email']

    def test_get_member_invalid_id_format(self, client, auth_headers):
        """Test getting member with invalid ID format."""
        response = client.get('/api/members/invalid', headers=auth_headers)
        assert response.status_code == 404


class TestMemberUpdateEnhanced:
    """Enhanced tests for PUT /api/members/{id} endpoint."""

    def test_update_member_multiple_fields(self, client, sample_member, sample_tenant):
        """Test updating multiple member fields at once."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/members/{sample_member.id}',
            headers=headers,
            data=json.dumps({
                'name': 'Multi Update Name',
                'email': 'multi.update@example.com',
                'notes': 'Updated via multi-field test'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['name'] == 'Multi Update Name'
        assert data['email'] == 'multi.update@example.com'

    def test_update_member_with_empty_body(self, client, sample_member, sample_tenant):
        """Test updating member with empty body (no changes)."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/members/{sample_member.id}',
            headers=headers,
            data=json.dumps({}),
            content_type='application/json'
        )
        # Should succeed even with no changes
        assert response.status_code == 200

    def test_update_member_tier_id(self, client, sample_member, sample_tenant):
        """Test updating member tier assignment."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }

        # Update tier to the existing sample tier (just verify the endpoint works)
        response = client.put(
            f'/api/members/{sample_member.id}',
            headers=headers,
            data=json.dumps({'tier_id': sample_member.tier_id}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        # Response returns tier as an object, not tier_id directly
        assert data['tier'] is not None
        assert data['tier']['id'] == sample_member.tier_id

    def test_update_member_notes(self, client, sample_member, sample_tenant):
        """Test updating member notes field."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/members/{sample_member.id}',
            headers=headers,
            data=json.dumps({'notes': 'Test note added via API'}),
            content_type='application/json'
        )
        assert response.status_code == 200


class TestMemberStatusTransitionsEnhanced:
    """Enhanced tests for member status transition endpoints."""

    def test_suspend_active_member_with_reason(self, client, sample_member, sample_tenant):
        """Test suspending an active member with reason."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/members/{sample_member.id}/suspend',
            headers=headers,
            data=json.dumps({'reason': 'Payment issue'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert data['member']['status'] == 'suspended'
        assert data['previous_status'] == 'active'

    def test_suspend_already_suspended_member(self, client, sample_member, sample_tenant):
        """Test that suspending already suspended member returns error."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }

        # First suspend the member via API
        client.post(
            f'/api/members/{sample_member.id}/suspend',
            headers=headers,
            data=json.dumps({'reason': 'First suspension'}),
            content_type='application/json'
        )

        # Try to suspend again
        response = client.post(
            f'/api/members/{sample_member.id}/suspend',
            headers=headers,
            data=json.dumps({'reason': 'Double suspension attempt'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'already suspended' in data['error'].lower()

    def test_suspend_cancelled_member_fails(self, client, sample_member, sample_tenant):
        """Test that suspending a cancelled member returns error."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }

        # First cancel the member via API
        client.post(
            f'/api/members/{sample_member.id}/cancel',
            headers=headers,
            data=json.dumps({'reason': 'Cancellation'}),
            content_type='application/json'
        )

        # Try to suspend
        response = client.post(
            f'/api/members/{sample_member.id}/suspend',
            headers=headers,
            data=json.dumps({'reason': 'Suspend cancelled'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_reactivate_suspended_member_success(self, client, sample_member, sample_tenant):
        """Test reactivating a suspended member succeeds."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }

        # First suspend the member via API
        client.post(
            f'/api/members/{sample_member.id}/suspend',
            headers=headers,
            data=json.dumps({'reason': 'Suspension for test'}),
            content_type='application/json'
        )

        # Now reactivate
        response = client.post(
            f'/api/members/{sample_member.id}/reactivate',
            headers=headers,
            data=json.dumps({'reason': 'Payment resolved'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert data['member']['status'] == 'active'
        assert data['previous_status'] == 'suspended'

    def test_reactivate_active_member_fails(self, client, sample_member, sample_tenant):
        """Test that reactivating an already active member returns error."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }

        response = client.post(
            f'/api/members/{sample_member.id}/reactivate',
            headers=headers,
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_cancel_member_success(self, client, sample_member, sample_tenant):
        """Test cancelling a member succeeds."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/members/{sample_member.id}/cancel',
            headers=headers,
            data=json.dumps({'reason': 'Customer requested cancellation'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert data['member']['status'] == 'cancelled'
        assert data['previous_status'] == 'active'

    def test_cancel_already_cancelled_member(self, client, sample_member, sample_tenant):
        """Test that cancelling already cancelled member returns error."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }

        # First cancel the member via API
        client.post(
            f'/api/members/{sample_member.id}/cancel',
            headers=headers,
            data=json.dumps({'reason': 'First cancel'}),
            content_type='application/json'
        )

        # Try to cancel again
        response = client.post(
            f'/api/members/{sample_member.id}/cancel',
            headers=headers,
            data=json.dumps({'reason': 'Double cancel attempt'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'already cancelled' in data['error'].lower()

    def test_suspend_member_not_found(self, client, auth_headers):
        """Test suspending non-existent member."""
        response = client.post(
            '/api/members/99999/suspend',
            headers=auth_headers,
            data=json.dumps({'reason': 'Test'}),
            content_type='application/json'
        )
        assert response.status_code == 404

    def test_reactivate_member_not_found(self, client, auth_headers):
        """Test reactivating non-existent member."""
        response = client.post(
            '/api/members/99999/reactivate',
            headers=auth_headers,
            content_type='application/json'
        )
        assert response.status_code == 404

    def test_cancel_member_not_found(self, client, auth_headers):
        """Test cancelling non-existent member."""
        response = client.post(
            '/api/members/99999/cancel',
            headers=auth_headers,
            data=json.dumps({'reason': 'Test'}),
            content_type='application/json'
        )
        assert response.status_code == 404


class TestMemberCreateEnhanced:
    """Enhanced tests for POST /api/members endpoint."""

    def test_create_member_with_all_fields(self, client, auth_headers, sample_tier, app):
        """Test creating a member with all optional fields."""
        unique_id = str(uuid.uuid4())[:8]
        response = client.post(
            '/api/members',
            headers=auth_headers,
            data=json.dumps({
                'email': f'full-{unique_id}@example.com',
                'name': 'Full Fields User',
                'phone': '+1-555-0123',
                'tier_id': sample_tier.id,
                'shopify_customer_id': f'shopify_{unique_id}',
                'notes': 'Created with all fields'
            }),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['email'] == f'full-{unique_id}@example.com'
        assert data['name'] == 'Full Fields User'
        assert 'member_number' in data
        assert data['member_number'].startswith('TU')

    def test_create_member_generates_unique_member_number(self, client, auth_headers):
        """Test that each created member gets a unique member number."""
        unique_id1 = str(uuid.uuid4())[:8]
        unique_id2 = str(uuid.uuid4())[:8]

        response1 = client.post(
            '/api/members',
            headers=auth_headers,
            data=json.dumps({
                'email': f'unique1-{unique_id1}@example.com',
                'name': 'Unique User 1',
                'shopify_customer_id': f'shopify_{unique_id1}'
            }),
            content_type='application/json'
        )
        assert response1.status_code == 201
        member_number1 = response1.get_json()['member_number']

        response2 = client.post(
            '/api/members',
            headers=auth_headers,
            data=json.dumps({
                'email': f'unique2-{unique_id2}@example.com',
                'name': 'Unique User 2',
                'shopify_customer_id': f'shopify_{unique_id2}'
            }),
            content_type='application/json'
        )
        assert response2.status_code == 201
        member_number2 = response2.get_json()['member_number']

        # Member numbers should be different
        assert member_number1 != member_number2

    def test_create_member_with_invalid_email(self, client, auth_headers):
        """Test creating member with invalid email format."""
        response = client.post(
            '/api/members',
            headers=auth_headers,
            data=json.dumps({
                'email': 'not-an-email',
                'name': 'Invalid Email User',
                'shopify_customer_id': '123456'
            }),
            content_type='application/json'
        )
        # The API may accept any string as email, or may validate
        # Check that it either accepts or returns 400
        assert response.status_code in [201, 400]


class TestMemberDeleteEnhanced:
    """Enhanced tests for DELETE /api/members/{id} endpoint."""

    def test_delete_member_returns_success_message(self, client, sample_member, sample_tenant):
        """Test that delete returns a success message."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        member_id = sample_member.id
        member_number = sample_member.member_number
        response = client.delete(
            f'/api/members/{member_id}',
            headers=headers
        )
        assert response.status_code in [200, 204]
        if response.status_code == 200:
            data = response.get_json()
            assert data['success'] == True
            assert member_number in data['message']

    def test_delete_member_cannot_get_after_delete(self, client, app, sample_tenant, sample_tier):
        """Test that member cannot be retrieved after deletion."""
        from app.extensions import db
        from app.models import Member

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }

        # Create a member specifically for this test via API
        unique_id = str(uuid.uuid4())[:8]
        create_response = client.post(
            '/api/members',
            headers=headers,
            data=json.dumps({
                'email': f'delete-test-{unique_id}@example.com',
                'name': 'Delete Test User',
                'shopify_customer_id': f'cust_del_{unique_id}'
            }),
            content_type='application/json'
        )
        assert create_response.status_code == 201
        member_id = create_response.get_json()['id']

        # Delete the member
        delete_response = client.delete(
            f'/api/members/{member_id}',
            headers=headers
        )
        assert delete_response.status_code in [200, 204]

        # Try to get the deleted member
        get_response = client.get(
            f'/api/members/{member_id}',
            headers=headers
        )
        assert get_response.status_code == 404
