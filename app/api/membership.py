"""
Membership API endpoints.
Handles tier management, store credit, and member portal.

Tiers are now staff-assigned or earned through activity/purchases.
No Stripe integration - all billing goes through Shopify.
"""
import logging
import os
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify, g
from .auth import get_current_member
from ..extensions import db
from ..models import Member, MembershipTier, StoreCreditLedger
from ..middleware.shopify_auth import require_shopify_auth
from ..services.shopify_client import ShopifyClient
from ..services.tier_service import TierService
from ..services.store_credit_service import store_credit_service
from ..models.promotions import CreditEventType

logger = logging.getLogger(__name__)

membership_bp = Blueprint('membership', __name__)


def get_shopify_client():
    """Create Shopify client from environment."""
    shop_domain = os.getenv('SHOPIFY_DOMAIN')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    if not shop_domain or not access_token:
        return None
    return ShopifyClient(shop_domain, access_token)


# ==================== Public Endpoints ====================

@membership_bp.route('/tiers', methods=['GET'])
def list_tiers():
    """
    List available membership tiers.

    Returns:
        List of active tiers with benefits
    """
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    tiers = MembershipTier.query.filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).order_by(MembershipTier.display_order).all()

    return jsonify({
        'tiers': [t.to_dict() for t in tiers]
    })


@membership_bp.route('/status', methods=['GET'])
def get_membership_status():
    """
    Get current member's tier and status.

    Returns:
        Current tier, status, and expiration info
    """
    member = get_current_member()
    if not member:
        return jsonify({'error': 'Not authenticated'}), 401

    return jsonify({
        'status': member.status,
        'tier': member.tier.to_dict() if member.tier else None,
        'subscription_status': member.subscription_status,
        'tier_assigned_by': member.tier_assigned_by,
        'tier_assigned_at': member.tier_assigned_at.isoformat() if member.tier_assigned_at else None,
        'tier_expires_at': member.tier_expires_at.isoformat() if member.tier_expires_at else None,
        'member_number': member.member_number,
        'stats': {
            'total_credit_earned': float(member.total_credit_earned) if hasattr(member, 'total_credit_earned') else 0.0,
            'total_trade_ins': member.total_trade_ins,
            'total_trade_value': float(member.total_trade_value)
        }
    })


@membership_bp.route('/store-credit', methods=['GET'])
def get_store_credit():
    """
    Get member's store credit balance from Shopify.

    Returns:
        Store credit balance and currency
    """
    member = get_current_member()
    if not member:
        return jsonify({'error': 'Not authenticated'}), 401

    if not member.shopify_customer_id:
        return jsonify({
            'balance': 0,
            'currency': 'USD',
            'message': 'No Shopify account linked'
        })

    client = get_shopify_client()
    if not client:
        return jsonify({'error': 'Shopify not configured'}), 500

    try:
        result = client.get_store_credit_balance(member.shopify_customer_id)
        return jsonify({
            'balance': result['balance'],
            'currency': result['currency'],
            'account_id': result.get('account_id')
        })
    except Exception as e:
        return jsonify({'error': f'Could not fetch balance: {str(e)}'}), 500


@membership_bp.route('/credit-history', methods=['GET'])
def get_credit_history_self():
    """
    Get current member's store credit transaction history.

    Query params:
        limit: int (optional, default 20)
        offset: int (optional, default 0)

    Returns:
        List of store credit transactions
    """
    member = get_current_member()
    if not member:
        return jsonify({'error': 'Not authenticated'}), 401

    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)

    transactions = (
        StoreCreditLedger.query
        .filter_by(member_id=member.id)
        .order_by(StoreCreditLedger.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = StoreCreditLedger.query.filter_by(member_id=member.id).count()

    return jsonify({
        'transactions': [t.to_dict() for t in transactions],
        'total': total,
        'limit': limit,
        'offset': offset
    })


@membership_bp.route('/link-shopify', methods=['POST'])
def link_shopify_customer():
    """
    Link member to their Shopify customer account by email.
    Also syncs their tier to Shopify customer tags.

    Returns:
        Linked customer info
    """
    member = get_current_member()
    if not member:
        return jsonify({'error': 'Not authenticated'}), 401

    client = get_shopify_client()
    if not client:
        return jsonify({'error': 'Shopify not configured'}), 500

    try:
        # Find customer by email
        customer = client.get_customer_by_email(member.email)

        if not customer:
            return jsonify({
                'error': 'No Shopify customer found with this email. Please make a purchase first.'
            }), 404

        # Link the customer
        member.shopify_customer_id = customer['id']
        db.session.commit()

        # Add membership tag
        if member.tier:
            tier_tag = f'tu-{member.tier.name.lower()}'
            client.add_customer_tag(customer['id'], tier_tag)
            client.add_customer_tag(customer['id'], f'TU{member.member_number[2:]}')

        # Get their store credit balance
        balance = client.get_store_credit_balance(customer['id'])

        return jsonify({
            'success': True,
            'customer_id': customer['id'],
            'customer_name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            'store_credit_balance': balance['balance'],
            'tags': customer.get('tags', [])
        })

    except Exception as e:
        return jsonify({'error': f'Failed to link account: {str(e)}'}), 500


# ==================== Admin Endpoints ====================

@membership_bp.route('/admin/assign-tier', methods=['POST'])
def admin_assign_tier():
    """
    Admin endpoint to assign a tier to a member.

    Request body:
        member_id: int (required)
        tier_id: int (required, null to remove tier)
        expires_at: string (optional, ISO date for tier expiration)
        reason: string (optional, reason for assignment)

    Returns:
        Updated member info
    """
    # Get admin info from request context
    staff_email = getattr(g, 'staff_id', None) or request.headers.get('X-Staff-Email', 'unknown')
    tenant_id = getattr(g, 'tenant_id', None) or int(request.headers.get('X-Tenant-ID', 1))

    data = request.json
    if not data.get('member_id'):
        return jsonify({'error': 'member_id is required'}), 400

    member = Member.query.filter_by(
        id=data['member_id'],
        tenant_id=tenant_id
    ).first()

    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Get new tier (or None to remove)
    new_tier = None
    if data.get('tier_id'):
        new_tier = MembershipTier.query.filter_by(
            id=data['tier_id'],
            tenant_id=tenant_id,
            is_active=True
        ).first()
        if not new_tier:
            return jsonify({'error': 'Invalid tier'}), 400

    # Update member
    old_tier_name = member.tier.name if member.tier else 'None'
    member.tier_id = new_tier.id if new_tier else None
    member.tier_assigned_by = f'staff:{staff_email}'
    member.tier_assigned_at = datetime.utcnow()

    # Set expiration if provided
    if data.get('expires_at'):
        try:
            member.tier_expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid expires_at format. Use ISO 8601.'}), 400
    else:
        member.tier_expires_at = None

    # Update status
    if new_tier:
        member.status = 'active'
    elif not member.shopify_subscription_contract_id:
        member.status = 'inactive'

    db.session.commit()

    # Sync tier tag to Shopify
    client = get_shopify_client()
    if client and member.shopify_customer_id:
        try:
            # Remove old tier tag
            if old_tier_name != 'None':
                client.remove_customer_tag(member.shopify_customer_id, f'tu-{old_tier_name.lower()}')
            # Add new tier tag
            if new_tier:
                client.add_customer_tag(member.shopify_customer_id, f'tu-{new_tier.name.lower()}')
        except Exception as e:
            logger.warning("Failed to sync tier tag to Shopify: %s", e)

    return jsonify({
        'success': True,
        'member': member.to_dict(include_subscription=True),
        'message': f"Tier changed from {old_tier_name} to {new_tier.name if new_tier else 'None'}"
    })


@membership_bp.route('/admin/bulk-assign-tier', methods=['POST'])
def admin_bulk_assign_tier():
    """
    Admin endpoint to assign a tier to multiple members.

    Request body:
        member_ids: list[int] (required)
        tier_id: int (required)
        expires_at: string (optional)
        reason: string (optional)

    Returns:
        Summary of assignments
    """
    staff_email = getattr(g, 'staff_id', None) or request.headers.get('X-Staff-Email', 'unknown')
    tenant_id = getattr(g, 'tenant_id', None) or int(request.headers.get('X-Tenant-ID', 1))

    data = request.json
    if not data.get('member_ids') or not isinstance(data['member_ids'], list):
        return jsonify({'error': 'member_ids array is required'}), 400

    if not data.get('tier_id'):
        return jsonify({'error': 'tier_id is required'}), 400

    # Verify tier
    tier = MembershipTier.query.filter_by(
        id=data['tier_id'],
        tenant_id=tenant_id,
        is_active=True
    ).first()
    if not tier:
        return jsonify({'error': 'Invalid tier'}), 400

    # Parse expiration
    expires_at = None
    if data.get('expires_at'):
        try:
            expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid expires_at format'}), 400

    # Update members
    members = Member.query.filter(
        Member.id.in_(data['member_ids']),
        Member.tenant_id == tenant_id
    ).all()

    updated_count = 0
    for member in members:
        member.tier_id = tier.id
        member.tier_assigned_by = f'staff:{staff_email}'
        member.tier_assigned_at = datetime.utcnow()
        member.tier_expires_at = expires_at
        member.status = 'active'
        updated_count += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'updated_count': updated_count,
        'tier': tier.to_dict(),
        'message': f"Assigned {tier.name} tier to {updated_count} members"
    })


@membership_bp.route('/admin/expire-tiers', methods=['POST'])
def admin_expire_tiers():
    """
    Admin endpoint to process expired tiers.
    Automatically removes tier from members whose tier_expires_at has passed.

    Returns:
        Count of expired memberships processed
    """
    tenant_id = getattr(g, 'tenant_id', None) or int(request.headers.get('X-Tenant-ID', 1))

    # Find expired members
    expired_members = Member.query.filter(
        Member.tenant_id == tenant_id,
        Member.tier_id.isnot(None),
        Member.tier_expires_at <= datetime.utcnow()
    ).all()

    expired_count = 0
    for member in expired_members:
        old_tier_name = member.tier.name if member.tier else 'None'
        member.tier_id = None
        member.tier_assigned_by = 'system:expiration'
        member.tier_assigned_at = datetime.utcnow()
        member.tier_expires_at = None
        member.status = 'inactive'
        expired_count += 1

        # Remove Shopify tag
        client = get_shopify_client()
        if client and member.shopify_customer_id:
            try:
                client.remove_customer_tag(member.shopify_customer_id, f'tu-{old_tier_name.lower()}')
            except Exception as e:
                current_app.logger.warning(f"Failed to remove Shopify tag for member {member.id}: {e}")

    db.session.commit()

    return jsonify({
        'success': True,
        'expired_count': expired_count,
        'message': f"Processed {expired_count} expired memberships"
    })


# ==================== Tier Assignment & History (Frontend API) ====================

@membership_bp.route('/tiers/assign', methods=['POST'])
def assign_tier():
    """
    Assign a tier to a member with full audit trail.
    Used by the embedded app for staff tier assignments.

    Request body:
        member_id: int (required)
        tier_id: int (required, null to remove tier)
        reason: string (optional)

    Returns:
        Assignment result with member info
    """
    staff_email = getattr(g, 'staff_id', None) or request.headers.get('X-Staff-Email', 'staff')
    tenant_id = getattr(g, 'tenant_id', None) or int(request.headers.get('X-Tenant-ID', 1))

    data = request.json
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    member_id = data.get('member_id')
    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400

    tier_id = data.get('tier_id')
    reason = data.get('reason', 'Staff assigned')

    tier_service = TierService(tenant_id)

    # Handle tier removal (tier_id is null or empty)
    if not tier_id:
        result = tier_service.remove_tier(
            member_id=member_id,
            source_type='staff',
            source_reference=staff_email,
            reason=reason,
            created_by=staff_email
        )
    else:
        result = tier_service.assign_tier(
            member_id=member_id,
            tier_id=tier_id,
            source_type='staff',
            source_reference=staff_email,
            reason=reason,
            created_by=staff_email
        )

    if not result.get('success'):
        return jsonify({'error': result.get('error', 'Assignment failed')}), 400

    return jsonify(result)


@membership_bp.route('/tiers/history/<int:member_id>', methods=['GET'])
def get_tier_history(member_id: int):
    """
    Get tier change history for a member.
    Returns audit trail of all tier changes.

    Args:
        member_id: Member ID to get history for

    Query params:
        limit: Max records (default 20)
        offset: Pagination offset (default 0)

    Returns:
        List of tier change records
    """
    tenant_id = getattr(g, 'tenant_id', None) or int(request.headers.get('X-Tenant-ID', 1))

    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)

    tier_service = TierService(tenant_id)
    result = tier_service.get_tier_history(
        member_id=member_id,
        limit=limit,
        offset=offset
    )

    return jsonify(result)


# ==================== Store Credit Admin Endpoints ====================

@membership_bp.route('/store-credit/add', methods=['POST'])
@require_shopify_auth
def add_store_credit():
    """
    Add one-off store credit to a member.
    Syncs to Shopify's native store credit.

    Request body:
        member_id: int (required)
        amount: float (required, positive number)
        description: string (optional, defaults to "Manual credit")
        expires_at: string (optional, ISO date for credit expiration)

    Returns:
        Ledger entry with new balance
    """
    staff_email = getattr(g, 'staff_id', None) or request.headers.get('X-Staff-Email', 'staff')
    tenant_id = getattr(g, 'tenant_id', None) or int(request.headers.get('X-Tenant-ID', 1))

    data = request.json
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    member_id = data.get('member_id')
    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400

    amount = data.get('amount')
    if not amount or float(amount) <= 0:
        return jsonify({'error': 'amount must be a positive number'}), 400

    # Verify member exists and belongs to tenant
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first()
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    description = data.get('description', 'Manual credit')
    expires_at = None
    if data.get('expires_at'):
        try:
            expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid expires_at format. Use ISO 8601.'}), 400

    try:
        entry = store_credit_service.add_credit(
            member_id=member_id,
            amount=Decimal(str(amount)),
            event_type=CreditEventType.MANUAL_ADJUSTMENT.value,
            description=description,
            source_type='manual',
            source_reference='admin',
            created_by=staff_email,
            sync_to_shopify=True,
            expires_at=expires_at,
        )

        balance = store_credit_service.get_member_balance(member_id)

        return jsonify({
            'success': True,
            'entry': entry.to_dict(),
            'new_balance': float(balance.total_balance),
            'message': f'Added ${amount:.2f} store credit to {member.name or member.email}'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to add credit: {str(e)}'}), 500


@membership_bp.route('/store-credit/deduct', methods=['POST'])
@require_shopify_auth
def deduct_store_credit():
    """
    Deduct store credit from a member.
    Syncs to Shopify's native store credit.

    Request body:
        member_id: int (required)
        amount: float (required, positive number)
        description: string (optional, defaults to "Manual deduction")

    Returns:
        Ledger entry with new balance
    """
    staff_email = getattr(g, 'staff_id', None) or request.headers.get('X-Staff-Email', 'staff')
    tenant_id = getattr(g, 'tenant_id', None) or int(request.headers.get('X-Tenant-ID', 1))

    data = request.json
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    member_id = data.get('member_id')
    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400

    amount = data.get('amount')
    if not amount or float(amount) <= 0:
        return jsonify({'error': 'amount must be a positive number'}), 400

    # Verify member exists and belongs to tenant
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first()
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    description = data.get('description', 'Manual deduction')

    try:
        entry = store_credit_service.deduct_credit(
            member_id=member_id,
            amount=Decimal(str(amount)),
            description=description,
            source_type='manual',
            source_id='admin',
            created_by=staff_email,
            sync_to_shopify=True,
        )

        balance = store_credit_service.get_member_balance(member_id)

        return jsonify({
            'success': True,
            'entry': entry.to_dict(),
            'new_balance': float(balance.total_balance),
            'message': f'Deducted ${amount:.2f} store credit from {member.name or member.email}'
        })

    except ValueError as e:
        # Insufficient balance
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to deduct credit: {str(e)}'}), 500


@membership_bp.route('/store-credit/history/<int:member_id>', methods=['GET'])
def get_credit_history(member_id: int):
    """
    Get full store credit ledger history for a member.

    Args:
        member_id: Member ID

    Query params:
        limit: Max records (default 50)
        offset: Pagination offset (default 0)

    Returns:
        Balance info and transaction list
    """
    tenant_id = getattr(g, 'tenant_id', None) or int(request.headers.get('X-Tenant-ID', 1))

    # Verify member belongs to tenant
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first()
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    result = store_credit_service.get_member_credit_history(
        member_id=member_id,
        limit=limit,
        offset=offset
    )

    return jsonify(result)


@membership_bp.route('/store-credit/balance/<int:member_id>', methods=['GET'])
def get_member_credit_balance(member_id: int):
    """
    Get store credit balance for a member.
    Returns both local ledger balance and Shopify balance.

    Args:
        member_id: Member ID

    Returns:
        Balance info from both systems
    """
    tenant_id = getattr(g, 'tenant_id', None) or int(request.headers.get('X-Tenant-ID', 1))

    # Verify member belongs to tenant
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first()
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Get local balance
    local_balance = store_credit_service.get_member_balance(member_id)

    # Get Shopify balance if linked
    shopify_balance = None
    if member.shopify_customer_id:
        try:
            client = get_shopify_client()
            if client:
                shopify_balance = client.get_store_credit_balance(member.shopify_customer_id)
        except Exception as e:
            shopify_balance = {'error': str(e)}

    return jsonify({
        'member_id': member_id,
        'local_balance': local_balance.to_dict(),
        'shopify_balance': shopify_balance,
        'in_sync': (
            shopify_balance and
            'balance' in shopify_balance and
            abs(float(local_balance.total_balance) - shopify_balance['balance']) < 0.01
        ) if shopify_balance and not shopify_balance.get('error') else None
    })
