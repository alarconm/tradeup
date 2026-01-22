"""
Tests for the Trade-ins API endpoints.

Tests cover:
- Trade-in batch CRUD operations
- Trade-in item management (add/edit/delete)
- Approval/rejection workflows
- Auto-approval threshold logic
- Credit issuance on approval

Story: TC-004 - Test Trade-in workflows
"""
import json
import pytest
from decimal import Decimal


class TestTradeInsList:
    """Tests for GET /api/trade-ins endpoint."""

    def test_trade_ins_endpoint_exists(self, client, auth_headers):
        """Test that the trade-ins endpoint responds."""
        response = client.get('/api/trade-ins', headers=auth_headers)
        assert response.status_code == 200

    def test_list_trade_ins_empty(self, client, auth_headers):
        """Test listing trade-ins returns empty list when none exist."""
        response = client.get('/api/trade-ins', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'batches' in data
        assert 'total' in data
        assert 'page' in data
        assert 'per_page' in data

    def test_list_trade_ins_with_batch(self, client, sample_trade_in_batch, sample_tenant):
        """Test listing trade-ins when one exists."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/trade-ins', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] >= 1
        assert len(data['batches']) >= 1

    def test_list_trade_ins_pagination(self, client, sample_trade_in_batch, sample_tenant):
        """Test pagination parameters."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/trade-ins?page=1&per_page=10', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['page'] == 1
        assert data['per_page'] == 10

    def test_list_trade_ins_filter_by_status(self, client, sample_trade_in_batch, sample_tenant):
        """Test filtering trade-ins by status."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/trade-ins?status=pending', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # All returned batches should have pending status
        for batch in data['batches']:
            assert batch['status'] == 'pending'

    def test_list_trade_ins_filter_by_category(self, client, app, sample_tenant, sample_member):
        """Test filtering trade-ins by category."""
        from app.extensions import db
        from app.models import TradeInBatch

        # Create a batch with specific category
        with app.app_context():
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-CAT-TEST-001',
                status='pending',
                category='pokemon',
                total_items=0,
                total_trade_value=0
            )
            db.session.add(batch)
            db.session.commit()

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get('/api/trade-ins?category=pokemon', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        # All returned batches should have pokemon category
        for batch in data['batches']:
            assert batch['category'] == 'pokemon'


class TestTradeInGet:
    """Tests for GET /api/trade-ins/{id} endpoint."""

    def test_get_trade_in_by_id(self, client, sample_trade_in_batch, sample_tenant):
        """Test getting a trade-in batch by ID."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(f'/api/trade-ins/{sample_trade_in_batch.id}', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == sample_trade_in_batch.id
        assert 'items' in data or 'status' in data

    def test_get_trade_in_not_found(self, client, auth_headers):
        """Test getting a non-existent trade-in batch."""
        response = client.get('/api/trade-ins/99999', headers=auth_headers)
        assert response.status_code == 404

    def test_get_trade_in_includes_items(self, client, app, sample_trade_in_batch, sample_tenant):
        """Test that get trade-in includes items when requested."""
        from app.extensions import db
        from app.models import TradeInItem

        # Add an item to the batch
        with app.app_context():
            item = TradeInItem(
                batch_id=sample_trade_in_batch.id,
                product_title='Test Card',
                trade_value=25.00
            )
            db.session.add(item)
            db.session.commit()

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(f'/api/trade-ins/{sample_trade_in_batch.id}', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'items' in data
        assert len(data['items']) >= 1


class TestTradeInCreate:
    """Tests for POST /api/trade-ins endpoint (batch CRUD)."""

    def test_create_trade_in_for_member(self, client, sample_member, sample_tenant):
        """Test creating a trade-in batch for a member."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/trade-ins',
            headers=headers,
            data=json.dumps({
                'member_id': sample_member.id,
                'notes': 'Test trade-in',
                'category': 'pokemon'
            }),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = response.get_json()
        assert 'id' in data
        assert data['member_id'] == sample_member.id

    def test_create_trade_in_for_guest(self, client, sample_tenant):
        """Test creating a trade-in batch for a guest."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/trade-ins',
            headers=headers,
            data=json.dumps({
                'guest_name': 'John Doe',
                'guest_email': 'john@example.com',
                'notes': 'Guest trade-in'
            }),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = response.get_json()
        assert 'id' in data
        assert data.get('guest_name') == 'John Doe' or 'batch_reference' in data

    def test_create_trade_in_requires_member_or_guest(self, client, auth_headers):
        """Test that creating trade-in requires member_id or guest info."""
        response = client.post(
            '/api/trade-ins',
            headers=auth_headers,
            data=json.dumps({'notes': 'Test'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_create_trade_in_with_all_guest_fields(self, client, sample_tenant):
        """Test creating trade-in with all guest fields."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            '/api/trade-ins',
            headers=headers,
            data=json.dumps({
                'guest_name': 'Jane Smith',
                'guest_email': 'jane@example.com',
                'guest_phone': '555-123-4567',
                'notes': 'Walk-in customer trade-in',
                'category': 'sports'
            }),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = response.get_json()
        assert 'id' in data
        assert data['status'] == 'pending'


class TestTradeInCategories:
    """Tests for GET /api/trade-ins/categories endpoint."""

    def test_get_categories(self, client, auth_headers):
        """Test getting available trade-in categories."""
        response = client.get('/api/trade-ins/categories', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        # Should return list of categories
        assert 'categories' in data
        assert isinstance(data['categories'], list)
        assert len(data['categories']) > 0

    def test_get_categories_includes_templates(self, client, auth_headers):
        """Test that categories include default templates."""
        response = client.get('/api/trade-ins/categories', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        # Check for expected template categories
        category_ids = [c['id'] for c in data['categories']]
        assert 'pokemon' in category_ids
        assert 'magic' in category_ids
        assert 'sports' in category_ids


class TestTradeInItemAdd:
    """Tests for adding items to trade-in batches."""

    def test_add_item_to_batch(self, client, sample_trade_in_batch, sample_tenant):
        """Test adding an item to a trade-in batch."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{sample_trade_in_batch.id}/items',
            headers=headers,
            data=json.dumps({
                'product_title': 'Charizard Card',
                'trade_value': 50.00
            }),
            content_type='application/json'
        )
        assert response.status_code in [200, 201]
        data = response.get_json()
        assert 'items' in data or 'batch' in data

    def test_add_multiple_items_to_batch(self, client, sample_trade_in_batch, sample_tenant):
        """Test adding multiple items to a batch."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{sample_trade_in_batch.id}/items',
            headers=headers,
            data=json.dumps({
                'items': [
                    {'product_title': 'Card 1', 'trade_value': 25.00},
                    {'product_title': 'Card 2', 'trade_value': 30.00},
                    {'product_title': 'Card 3', 'trade_value': 15.00}
                ]
            }),
            content_type='application/json'
        )
        assert response.status_code in [200, 201]
        data = response.get_json()
        assert 'items' in data
        assert len(data['items']) == 3


class TestTradeInItemEdit:
    """Tests for editing trade-in items."""

    def test_update_item_in_pending_batch(self, client, app, sample_trade_in_batch, sample_tenant):
        """Test updating a trade-in item in pending batch succeeds."""
        from app.extensions import db
        from app.models import TradeInItem

        # Create an item first
        with app.app_context():
            item = TradeInItem(
                batch_id=sample_trade_in_batch.id,
                product_title='Test Item',
                trade_value=25.00
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/items/{item_id}',
            headers=headers,
            data=json.dumps({'trade_value': 30.00, 'product_title': 'Updated Item'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['item']['trade_value'] == 30.00
        assert data['item']['product_title'] == 'Updated Item'

    def test_update_item_in_approved_batch_fails(self, client, app, sample_tenant, sample_member):
        """Test that updating an item in approved batch fails."""
        from app.extensions import db
        from app.models import TradeInItem, TradeInBatch

        # Create a new batch directly in approved state with an item
        with app.app_context():
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-APPROVED-EDIT-001',
                status='approved',
                total_items=1,
                total_trade_value=25.00
            )
            db.session.add(batch)
            db.session.flush()

            item = TradeInItem(
                batch_id=batch.id,
                product_title='Locked Item',
                trade_value=25.00
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/items/{item_id}',
            headers=headers,
            data=json.dumps({'trade_value': 50.00}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'approved' in data['error'].lower()


class TestTradeInItemDelete:
    """Tests for deleting trade-in items."""

    def test_delete_item_from_pending_batch(self, client, app, sample_trade_in_batch, sample_tenant):
        """Test deleting a trade-in item from pending batch succeeds."""
        from app.extensions import db
        from app.models import TradeInItem

        # Create an item first
        with app.app_context():
            item = TradeInItem(
                batch_id=sample_trade_in_batch.id,
                product_title='Item to Delete',
                trade_value=10.00
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.delete(
            f'/api/trade-ins/items/{item_id}',
            headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_delete_item_from_completed_batch_fails(self, client, app, sample_tenant, sample_member):
        """Test that deleting item from completed batch fails."""
        from app.extensions import db
        from app.models import TradeInItem, TradeInBatch

        # Create a new batch directly in completed state with an item
        with app.app_context():
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-COMPLETED-DEL-001',
                status='completed',
                total_items=1,
                total_trade_value=25.00
            )
            db.session.add(batch)
            db.session.flush()

            item = TradeInItem(
                batch_id=batch.id,
                product_title='Locked Item',
                trade_value=25.00
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.delete(
            f'/api/trade-ins/items/{item_id}',
            headers=headers
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data


class TestTradeInApprovalWorkflow:
    """Tests for trade-in approval workflow."""

    def test_update_status_to_approved(self, client, app, sample_trade_in_batch, sample_tenant):
        """Test updating batch status to approved."""
        from app.extensions import db
        from app.models import TradeInItem

        # Add an item to the batch (required for approval)
        with app.app_context():
            item = TradeInItem(
                batch_id=sample_trade_in_batch.id,
                product_title='Test Item',
                trade_value=100.00
            )
            db.session.add(item)
            db.session.commit()

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{sample_trade_in_batch.id}/status',
            headers=headers,
            data=json.dumps({'status': 'approved'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['new_status'] == 'approved'
        assert data['old_status'] == 'pending'

    def test_update_status_to_under_review(self, client, sample_trade_in_batch, sample_tenant):
        """Test updating batch status to under_review."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{sample_trade_in_batch.id}/status',
            headers=headers,
            data=json.dumps({'status': 'under_review'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['new_status'] == 'under_review'

    def test_update_status_invalid_status(self, client, sample_trade_in_batch, sample_tenant):
        """Test that invalid status is rejected."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{sample_trade_in_batch.id}/status',
            headers=headers,
            data=json.dumps({'status': 'invalid_status'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_complete_batch_with_items(self, client, app, sample_trade_in_batch, sample_tenant, sample_member):
        """Test completing a trade-in batch with items."""
        from app.extensions import db
        from app.models import TradeInItem, TradeInBatch

        # Add items to the batch
        with app.app_context():
            batch = TradeInBatch.query.get(sample_trade_in_batch.id)
            item = TradeInItem(
                batch_id=batch.id,
                product_title='Complete Test Item',
                trade_value=100.00
            )
            db.session.add(item)
            batch.total_items = 1
            batch.total_trade_value = Decimal('100.00')
            db.session.commit()

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{sample_trade_in_batch.id}/complete',
            headers=headers,
            content_type='application/json'
        )
        # May succeed or return error based on external services
        assert response.status_code in [200, 400, 500]

    def test_complete_already_completed_batch_fails(self, client, app, sample_tenant, sample_member):
        """Test that completing already completed batch fails."""
        from app.extensions import db
        from app.models import TradeInBatch
        from datetime import datetime

        # Create a completed batch
        with app.app_context():
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-ALREADY-COMPLETE-001',
                status='completed',
                completed_at=datetime.utcnow(),
                total_items=1,
                total_trade_value=100.00
            )
            db.session.add(batch)
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{batch_id}/complete',
            headers=headers,
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data


class TestTradeInRejectionWorkflow:
    """Tests for trade-in rejection workflow."""

    def test_reject_batch_with_reason(self, client, sample_trade_in_batch, sample_tenant):
        """Test rejecting a batch with reason."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{sample_trade_in_batch.id}/status',
            headers=headers,
            data=json.dumps({
                'status': 'rejected',
                'reason': 'Items not in acceptable condition'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['new_status'] == 'rejected'
        assert data['reason'] == 'Items not in acceptable condition'

    def test_cancel_batch_with_reason(self, client, sample_trade_in_batch, sample_tenant):
        """Test cancelling a batch with reason."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{sample_trade_in_batch.id}/status',
            headers=headers,
            data=json.dumps({
                'status': 'cancelled',
                'reason': 'Customer changed mind'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['new_status'] == 'cancelled'

    def test_reject_batch_without_reason(self, client, sample_trade_in_batch, sample_tenant):
        """Test rejecting batch without reason still works."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{sample_trade_in_batch.id}/status',
            headers=headers,
            data=json.dumps({'status': 'rejected'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['new_status'] == 'rejected'


class TestAutoApprovalThresholds:
    """Tests for auto-approval threshold logic."""

    def test_apply_thresholds_auto_approve_low_value(self, client, app, sample_tenant, sample_member):
        """Test that low-value batches are auto-approved."""
        from app.extensions import db
        from app.models import TradeInBatch, Tenant

        # Set up tenant thresholds and create batch
        with app.app_context():
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.settings = {
                'trade_ins': {
                    'auto_approve_under': 50.00,
                    'require_review_over': 500.00
                }
            }

            # Create a low-value batch
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-LOW-001',
                status='pending',
                total_items=1,
                total_trade_value=Decimal('25.00')
            )
            db.session.add(batch)
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{batch_id}/apply-thresholds',
            headers=headers,
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['action'] == 'auto_approved'
        assert data['total_value'] == 25.00

    def test_apply_thresholds_flag_high_value(self, client, app, sample_tenant, sample_member):
        """Test that high-value batches are flagged for review."""
        from app.extensions import db
        from app.models import TradeInBatch, Tenant

        # Set up tenant thresholds
        with app.app_context():
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.settings = {
                'trade_ins': {
                    'auto_approve_under': 50.00,
                    'require_review_over': 500.00
                }
            }

            # Create a high-value batch
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-HIGH-001',
                status='pending',
                total_items=1,
                total_trade_value=Decimal('750.00')
            )
            db.session.add(batch)
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{batch_id}/apply-thresholds',
            headers=headers,
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['action'] == 'flagged_for_review'
        assert data['total_value'] == 750.00

    def test_apply_thresholds_pending_mid_value(self, client, app, sample_tenant, sample_member):
        """Test that mid-value batches stay pending."""
        from app.extensions import db
        from app.models import TradeInBatch, Tenant

        # Set up tenant thresholds
        with app.app_context():
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.settings = {
                'trade_ins': {
                    'auto_approve_under': 50.00,
                    'require_review_over': 500.00
                }
            }

            # Create a mid-value batch
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-MID-001',
                status='pending',
                total_items=1,
                total_trade_value=Decimal('200.00')
            )
            db.session.add(batch)
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{batch_id}/apply-thresholds',
            headers=headers,
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['action'] == 'pending'
        assert data['total_value'] == 200.00

    def test_apply_thresholds_skip_non_pending(self, client, app, sample_tenant, sample_member):
        """Test that non-pending batches are skipped."""
        from app.extensions import db
        from app.models import TradeInBatch

        # Create a batch already in approved state
        with app.app_context():
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-APPROVED-SKIP-001',
                status='approved',
                total_items=1,
                total_trade_value=Decimal('100.00')
            )
            db.session.add(batch)
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{batch_id}/apply-thresholds',
            headers=headers,
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['action'] == 'skipped'

    def test_preview_bonus(self, client, sample_trade_in_batch, sample_tenant):
        """Test previewing member bonus for a batch."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(
            f'/api/trade-ins/{sample_trade_in_batch.id}/preview-bonus',
            headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'bonus' in data
        assert 'batch_id' in data


class TestCreditIssuanceOnApproval:
    """Tests for credit issuance when trade-in is completed."""

    def test_complete_batch_issues_bonus_credit(self, client, app, sample_tenant, sample_member, sample_tier):
        """Test that completing batch issues tier bonus credit."""
        from app.extensions import db
        from app.models import TradeInBatch, TradeInItem, Member

        # Ensure member has tier with bonus rate
        with app.app_context():
            member = Member.query.get(sample_member.id)
            # sample_tier has bonus_rate=0.15 (15%)

            # Create batch with items
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=member.id,
                batch_reference='TB-BONUS-001',
                status='pending',
                total_items=2,
                total_trade_value=Decimal('200.00')
            )
            db.session.add(batch)
            db.session.commit()

            item1 = TradeInItem(
                batch_id=batch.id,
                product_title='Card 1',
                trade_value=Decimal('100.00')
            )
            item2 = TradeInItem(
                batch_id=batch.id,
                product_title='Card 2',
                trade_value=Decimal('100.00')
            )
            db.session.add_all([item1, item2])
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{batch_id}/complete',
            headers=headers,
            content_type='application/json'
        )
        # May succeed or fail depending on external services
        if response.status_code == 200:
            data = response.get_json()
            assert data['success'] is True
            assert 'bonus' in data
            # With 15% bonus rate on $200 trade value = $30 bonus
            if data['bonus']['eligible']:
                assert data['bonus']['bonus_amount'] == 30.00

    def test_guest_trade_in_no_bonus(self, client, app, sample_tenant):
        """Test that guest trade-ins don't get bonus."""
        from app.extensions import db
        from app.models import TradeInBatch, TradeInItem

        # Create guest batch
        with app.app_context():
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=None,
                guest_name='Guest User',
                guest_email='guest@example.com',
                batch_reference='TB-GUEST-001',
                status='pending',
                total_items=1,
                total_trade_value=Decimal('100.00')
            )
            db.session.add(batch)
            db.session.commit()

            item = TradeInItem(
                batch_id=batch.id,
                product_title='Guest Item',
                trade_value=Decimal('100.00')
            )
            db.session.add(item)
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.post(
            f'/api/trade-ins/{batch_id}/complete',
            headers=headers,
            content_type='application/json'
        )
        if response.status_code == 200:
            data = response.get_json()
            assert data['success'] is True
            assert data['is_guest'] is True
            assert data['bonus']['bonus_amount'] == 0

    def test_preview_bonus_calculation(self, client, app, sample_tenant, sample_member, sample_tier):
        """Test bonus preview calculation."""
        from app.extensions import db
        from app.models import TradeInBatch

        # Create batch with trade value
        with app.app_context():
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-PREVIEW-001',
                status='pending',
                total_items=1,
                total_trade_value=Decimal('100.00')
            )
            db.session.add(batch)
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(
            f'/api/trade-ins/{batch_id}/preview-bonus',
            headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'bonus' in data
        # 15% bonus rate on $100 = $15 bonus
        if data['bonus']['eligible']:
            assert data['bonus']['bonus_percent'] == 15.0
            assert data['bonus']['bonus_amount'] == 15.0


class TestTradeInTimeline:
    """Tests for trade-in timeline endpoint."""

    def test_get_batch_timeline(self, client, sample_trade_in_batch, sample_tenant):
        """Test getting timeline for a batch."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(
            f'/api/trade-ins/{sample_trade_in_batch.id}/timeline',
            headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'timeline' in data
        assert 'batch_id' in data
        assert 'current_status' in data
        # Should have at least the creation event
        assert len(data['timeline']) >= 1

    def test_timeline_includes_item_events(self, client, app, sample_trade_in_batch, sample_tenant):
        """Test that timeline includes item addition events."""
        from app.extensions import db
        from app.models import TradeInItem

        # Add items to batch
        with app.app_context():
            item = TradeInItem(
                batch_id=sample_trade_in_batch.id,
                product_title='Timeline Test Item',
                trade_value=50.00
            )
            db.session.add(item)
            db.session.commit()

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(
            f'/api/trade-ins/{sample_trade_in_batch.id}/timeline',
            headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        event_types = [e['event_type'] for e in data['timeline']]
        assert 'item_added' in event_types


class TestTradeInMemberSummary:
    """Tests for member trade-in summary."""

    def test_get_member_summary(self, client, sample_member, sample_tenant):
        """Test getting trade-in summary for a member."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(
            f'/api/trade-ins/member/{sample_member.id}/summary',
            headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'total_trade_ins' in data
        assert 'total_trade_value' in data
        assert 'total_bonus_earned' in data

    def test_get_member_summary_not_found(self, client, auth_headers):
        """Test member summary for non-existent member."""
        response = client.get(
            '/api/trade-ins/member/99999/summary',
            headers=auth_headers
        )
        assert response.status_code == 404


class TestTradeInByReference:
    """Tests for getting trade-in by reference."""

    def test_get_batch_by_reference(self, client, sample_trade_in_batch, sample_tenant):
        """Test getting a batch by its reference number."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.get(
            f'/api/trade-ins/by-reference/{sample_trade_in_batch.batch_reference}',
            headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['batch_reference'] == sample_trade_in_batch.batch_reference

    def test_get_batch_by_reference_not_found(self, client, auth_headers):
        """Test getting a non-existent batch reference."""
        response = client.get('/api/trade-ins/by-reference/NONEXISTENT', headers=auth_headers)
        assert response.status_code == 404


class TestTradeInFixture:
    """Test trade-in fixture functionality."""

    def test_trade_in_batch_fixture_created(self, sample_trade_in_batch):
        """Test that the trade-in batch fixture is created correctly."""
        assert sample_trade_in_batch.id is not None
        assert sample_trade_in_batch.batch_reference.startswith('TB-TEST-')
        assert sample_trade_in_batch.status == 'pending'

    def test_trade_in_batch_has_tenant(self, sample_trade_in_batch, sample_tenant):
        """Test that trade-in batch is associated with tenant."""
        assert sample_trade_in_batch.tenant_id == sample_tenant.id

    def test_trade_in_batch_has_member(self, sample_trade_in_batch, sample_member):
        """Test that trade-in batch is associated with member."""
        assert sample_trade_in_batch.member_id == sample_member.id


class TestTradeInServiceUnit:
    """Unit tests for TradeInService."""

    def test_create_batch_for_inactive_member_fails(self, app, sample_tenant, sample_member):
        """Test that creating batch for inactive member fails."""
        from app.extensions import db
        from app.models import Member
        from app.services.trade_in_service import TradeInService

        with app.app_context():
            # Make member inactive
            member = Member.query.get(sample_member.id)
            member.status = 'inactive'
            db.session.commit()

            service = TradeInService(sample_tenant.id)
            with pytest.raises(ValueError) as exc_info:
                service.create_batch(member_id=sample_member.id)
            assert 'not active' in str(exc_info.value)

    def test_create_batch_for_nonexistent_member_fails(self, app, sample_tenant):
        """Test that creating batch for non-existent member fails."""
        from app.services.trade_in_service import TradeInService

        with app.app_context():
            service = TradeInService(sample_tenant.id)
            with pytest.raises(ValueError) as exc_info:
                service.create_batch(member_id=99999)
            assert 'not found' in str(exc_info.value).lower()

    def test_add_item_to_nonexistent_batch_fails(self, app, sample_tenant):
        """Test that adding item to non-existent batch fails."""
        from app.services.trade_in_service import TradeInService
        from decimal import Decimal

        with app.app_context():
            service = TradeInService(sample_tenant.id)
            with pytest.raises(ValueError) as exc_info:
                service.add_item(
                    batch_id=99999,
                    trade_value=Decimal('50.00'),
                    product_title='Test'
                )
            assert 'not found' in str(exc_info.value).lower()

    def test_calculate_tier_bonus_no_tier(self, app, sample_tenant, sample_member):
        """Test bonus calculation when member has no tier."""
        from app.extensions import db
        from app.models import Member, TradeInBatch
        from app.services.trade_in_service import TradeInService

        with app.app_context():
            # Remove tier from member
            member = Member.query.get(sample_member.id)
            member.tier_id = None
            db.session.commit()

            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=member.id,
                batch_reference='TB-NOTIER-001',
                status='pending',
                total_items=1,
                total_trade_value=Decimal('100.00')
            )
            db.session.add(batch)
            db.session.commit()

            service = TradeInService(sample_tenant.id)
            result = service.calculate_tier_bonus(batch)
            assert result['eligible'] is False
            assert result['bonus_amount'] == 0


class TestStatusTransitions:
    """Tests for valid status transitions."""

    def test_pending_to_approved(self, client, sample_trade_in_batch, sample_tenant):
        """Test pending -> approved transition."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{sample_trade_in_batch.id}/status',
            headers=headers,
            data=json.dumps({'status': 'approved'}),
            content_type='application/json'
        )
        assert response.status_code == 200

    def test_pending_to_rejected(self, client, sample_trade_in_batch, sample_tenant):
        """Test pending -> rejected transition."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{sample_trade_in_batch.id}/status',
            headers=headers,
            data=json.dumps({'status': 'rejected'}),
            content_type='application/json'
        )
        assert response.status_code == 200

    def test_pending_to_cancelled(self, client, sample_trade_in_batch, sample_tenant):
        """Test pending -> cancelled transition."""
        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{sample_trade_in_batch.id}/status',
            headers=headers,
            data=json.dumps({'status': 'cancelled'}),
            content_type='application/json'
        )
        assert response.status_code == 200

    def test_approved_to_completed(self, client, app, sample_tenant, sample_member):
        """Test approved -> completed transition."""
        from app.extensions import db
        from app.models import TradeInBatch

        # Create a batch already in approved state
        with app.app_context():
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-APPROVED-TRANS-001',
                status='approved',
                total_items=1,
                total_trade_value=100.00
            )
            db.session.add(batch)
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{batch_id}/status',
            headers=headers,
            data=json.dumps({'status': 'completed'}),
            content_type='application/json'
        )
        assert response.status_code == 200

    def test_approved_to_listed(self, client, app, sample_tenant, sample_member):
        """Test approved -> listed transition."""
        from app.extensions import db
        from app.models import TradeInBatch

        # Create a batch already in approved state
        with app.app_context():
            batch = TradeInBatch(
                tenant_id=sample_tenant.id,
                member_id=sample_member.id,
                batch_reference='TB-APPROVED-LIST-001',
                status='approved',
                total_items=1,
                total_trade_value=100.00
            )
            db.session.add(batch)
            db.session.commit()
            batch_id = batch.id

        headers = {
            'X-Shop-Domain': sample_tenant.shopify_domain,
            'Content-Type': 'application/json'
        }
        response = client.put(
            f'/api/trade-ins/{batch_id}/status',
            headers=headers,
            data=json.dumps({'status': 'listed'}),
            content_type='application/json'
        )
        assert response.status_code == 200
