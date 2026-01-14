"""
Member API endpoints.

Shopify-Native Member System:
- Members MUST be linked to existing Shopify customers
- No manual member creation - use search & enroll workflow
- Flow: Search Shopify customers → Enroll as member → Create trade-ins
"""
from flask import Blueprint, request, jsonify, g
from ..extensions import db
from ..models import Member, MembershipTier
from ..services.membership_service import MembershipService
from ..middleware.shopify_auth import require_shopify_auth, require_shopify_auth_debug

members_bp = Blueprint('members', __name__)


# ==================== Debug Endpoint ====================

@members_bp.route('/debug', methods=['GET'])
@require_shopify_auth_debug
def debug_endpoint():
    """Debug endpoint to test auth and DB connectivity."""
    import os
    try:
        tenant_id = g.tenant_id
        tenant = g.tenant

        # Test member count query
        member_count = Member.query.filter_by(tenant_id=tenant_id).count()

        # Test tier query
        tier_count = MembershipTier.query.filter_by(tenant_id=tenant_id).count()

        # Test access token access (this might fail due to encryption)
        access_token_status = 'unknown'
        access_token_error = None
        try:
            has_token = bool(tenant.shopify_access_token)
            access_token_status = 'present' if has_token else 'missing'
        except Exception as e:
            access_token_status = 'error'
            access_token_error = str(e)

        return jsonify({
            'status': 'ok',
            'tenant_id': tenant_id,
            'shop': g.shop,
            'auth_method': g.auth_method,
            'member_count': member_count,
            'tier_count': tier_count,
            'tenant_active': tenant.is_active,
            'subscription_plan': tenant.subscription_plan,
            'access_token_status': access_token_status,
            'access_token_error': access_token_error,
            'env_flask_env': os.getenv('FLASK_ENV'),
            'env_has_encryption_key': bool(os.getenv('ENCRYPTION_KEY'))
        })
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }), 500


# ==================== Shopify Customer Search & Enroll ====================

@members_bp.route('/search-shopify', methods=['GET'])
@require_shopify_auth
def search_shopify_customers():
    """
    Search Shopify customers for enrollment.

    Query params:
        q: Search query (name, email, phone, or ORB#)

    Returns customers with enrollment status (is_member, member_number, member_tier).
    """
    import os
    import traceback

    tenant_id = g.tenant_id  # Use tenant_id from auth middleware
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify({'error': 'Search query must be at least 2 characters'}), 400

    # Debug: Check environment configuration
    shopify_domain = os.getenv('SHOPIFY_DOMAIN')
    shopify_token = os.getenv('SHOPIFY_ACCESS_TOKEN')

    if not shopify_domain or not shopify_token:
        return jsonify({
            'error': 'Shopify not configured',
            'details': {
                'SHOPIFY_DOMAIN': 'set' if shopify_domain else 'NOT SET',
                'SHOPIFY_ACCESS_TOKEN': 'set' if shopify_token else 'NOT SET'
            }
        }), 500

    service = MembershipService(tenant_id)

    try:
        customers = service.search_shopify_customers(query)
        return jsonify({
            'customers': customers,
            'query': query,
            'count': len(customers)
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # Log full traceback for debugging
        print(f"[TradeUp] Search error: {type(e).__name__}: {e}")
        print(f"[TradeUp] Traceback: {traceback.format_exc()}")
        return jsonify({
            'error': f'Search failed: {str(e)}',
            'error_type': type(e).__name__,
            'shopify_domain': shopify_domain[:10] + '...' if shopify_domain else None
        }), 500


@members_bp.route('/enroll', methods=['POST'])
@require_shopify_auth
def enroll_shopify_customer():
    """
    Enroll an existing Shopify customer as a TradeUp member.

    JSON body:
        shopify_customer_id: Shopify customer ID (numeric) - REQUIRED
        tier_id: Membership tier ID (optional, defaults to lowest tier)
        partner_customer_id: Partner ID like ORB# (optional)
        notes: Internal notes (optional)

    Customer name/email/phone are pulled from Shopify automatically.
    """
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware
    tenant = g.tenant
    data = request.json or {}

    shopify_customer_id = data.get('shopify_customer_id')
    if not shopify_customer_id:
        return jsonify({'error': 'shopify_customer_id is required'}), 400

    # Check plan limits before enrollment
    current_member_count = Member.query.filter_by(tenant_id=tenant_id, status='active').count()
    max_members = tenant.max_members or 50  # Default to Free plan limit

    if current_member_count >= max_members:
        return jsonify({
            'error': 'Member limit reached',
            'message': f'Your plan allows up to {max_members} members. Please upgrade to add more.',
            'current_count': current_member_count,
            'limit': max_members,
            'upgrade_required': True
        }), 403

    service = MembershipService(tenant_id)

    try:
        member = service.enroll_shopify_customer(
            shopify_customer_id=str(shopify_customer_id),
            tier_id=data.get('tier_id'),
            partner_customer_id=data.get('partner_customer_id'),
            notes=data.get('notes')
        )
        return jsonify({
            'success': True,
            'member': member.to_dict(include_stats=True),
            'message': f'Successfully enrolled as {member.member_number}'
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Enrollment failed: {str(e)}'}), 500


@members_bp.route('/create-shopify-customer', methods=['POST'])
@require_shopify_auth
def create_shopify_customer():
    """
    Create a new customer in Shopify.

    JSON body:
        email: Customer email (required)
        first_name: First name (optional)
        last_name: Last name (optional)
        phone: Phone number (optional)

    Returns the created Shopify customer data.
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    email = data.get('email', '').strip()
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    # Validate email format
    if '@' not in email or '.' not in email:
        return jsonify({'error': 'Invalid email format'}), 400

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(tenant_id)

        # Check if customer already exists
        existing = client.get_customer_by_email(email)
        if existing:
            return jsonify({
                'error': 'Customer with this email already exists in Shopify',
                'existing_customer': existing
            }), 409

        # Create customer in Shopify
        customer = client.create_customer(
            email=email,
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            phone=data.get('phone')
        )

        return jsonify({
            'success': True,
            'customer': customer,
            'message': f'Customer created in Shopify'
        }), 201

    except Exception as e:
        return jsonify({'error': f'Failed to create customer: {str(e)}'}), 500


@members_bp.route('/create-and-enroll', methods=['POST'])
@require_shopify_auth
def create_and_enroll_customer():
    """
    Create a new Shopify customer AND enroll them as a TradeUp member in one step.

    JSON body:
        email: Customer email (required)
        first_name: First name (optional)
        last_name: Last name (optional)
        phone: Phone number (optional)
        tier_id: Membership tier ID (optional, defaults to lowest tier)
        notes: Internal notes (optional)

    This is the "Create as New Customer" workflow - everything flows through Shopify.
    """
    tenant_id = g.tenant_id
    tenant = g.tenant
    data = request.json or {}

    email = data.get('email', '').strip()
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    # Validate email format
    if '@' not in email or '.' not in email:
        return jsonify({'error': 'Invalid email format'}), 400

    # Check plan limits before enrollment
    current_member_count = Member.query.filter_by(tenant_id=tenant_id, status='active').count()
    max_members = tenant.max_members or 50  # Default to Free plan limit

    if current_member_count >= max_members:
        return jsonify({
            'error': 'Member limit reached',
            'message': f'Your plan allows up to {max_members} members. Please upgrade to add more.',
            'current_count': current_member_count,
            'limit': max_members,
            'upgrade_required': True
        }), 403

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(tenant_id)

        # Check if customer already exists in Shopify
        existing = client.get_customer_by_email(email)

        if existing:
            # Customer exists - check if already a member
            existing_member = Member.query.filter_by(
                tenant_id=tenant_id,
                shopify_customer_id=existing.get('id')
            ).first()

            if existing_member:
                return jsonify({
                    'error': 'Customer is already enrolled as a member',
                    'member': existing_member.to_dict(include_stats=True)
                }), 409

            # Customer exists but not a member - enroll them
            shopify_customer_id = existing.get('id')
        else:
            # Create new customer in Shopify
            customer = client.create_customer(
                email=email,
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                phone=data.get('phone')
            )
            shopify_customer_id = customer.get('id')

        # Now enroll as member
        service = MembershipService(tenant_id)
        member = service.enroll_shopify_customer(
            shopify_customer_id=str(shopify_customer_id),
            tier_id=data.get('tier_id'),
            notes=data.get('notes')
        )

        return jsonify({
            'success': True,
            'member': member.to_dict(include_stats=True),
            'message': f'Successfully created and enrolled as {member.member_number}',
            'shopify_customer_id': shopify_customer_id
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to create and enroll: {str(e)}'}), 500


# ==================== Member CRUD ====================

@members_bp.route('', methods=['GET'])
@require_shopify_auth
def list_members():
    """List all members for the tenant.

    Query params:
        page: Page number (default: 1)
        per_page: Items per page (default: 50)
        status: Filter by status (active, cancelled, etc.)
        search: Search by name or email
        tier: Filter by tier name (case-insensitive)
    """
    try:
        tenant_id = g.tenant_id  # Use tenant_id from auth middleware

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        status = request.args.get('status')
        search = request.args.get('search', '').strip()
        tier_filter = request.args.get('tier', '').strip()

        query = Member.query.filter_by(tenant_id=tenant_id)

        if status:
            query = query.filter_by(status=status)

        # Search by name or email
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(
                db.or_(
                    Member.name.ilike(search_pattern),
                    Member.email.ilike(search_pattern),
                    Member.first_name.ilike(search_pattern),
                    Member.last_name.ilike(search_pattern),
                    Member.member_number.ilike(search_pattern)
                )
            )

        # Filter by tier name
        if tier_filter:
            tier = MembershipTier.query.filter(
                MembershipTier.tenant_id == tenant_id,
                db.func.lower(MembershipTier.name) == tier_filter.lower()
            ).first()
            if tier:
                query = query.filter(Member.tier_id == tier.id)

        pagination = query.order_by(Member.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'members': [m.to_dict(include_stats=True) for m in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        })
    except Exception as e:
        import traceback
        print(f"[Members] Error listing members: {e}")
        traceback.print_exc()
        return jsonify({
            'error': 'Failed to list members',
            'members': [],
            'total': 0
        }), 500


@members_bp.route('/<int:member_id>', methods=['GET'])
@require_shopify_auth
def get_member(member_id):
    """Get member details."""
    tenant_id = g.tenant_id
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first_or_404()
    return jsonify(member.to_dict(include_stats=True))


@members_bp.route('/by-number/<member_number>', methods=['GET'])
@require_shopify_auth
def get_member_by_number(member_number):
    """Get member by member number (TU1001)."""
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware

    # Normalize member number - support both TU and legacy QF prefixes
    upper_num = member_number.upper()
    if not upper_num.startswith('TU') and not upper_num.startswith('QF'):
        member_number = f'TU{member_number}'
    else:
        member_number = upper_num

    member = Member.query.filter_by(
        tenant_id=tenant_id,
        member_number=member_number
    ).first_or_404()

    return jsonify(member.to_dict(include_stats=True))


@members_bp.route('', methods=['POST'])
@require_shopify_auth
def create_member():
    """Create a new member."""
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware
    data = request.json

    # Validate required fields
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    if 'email' not in data or not data.get('email'):
        return jsonify({'error': 'Email is required'}), 400

    service = MembershipService(tenant_id)

    try:
        member = service.create_member(
            email=data['email'],
            name=data.get('name'),
            phone=data.get('phone'),
            tier_id=data.get('tier_id'),
            shopify_customer_id=data.get('shopify_customer_id'),
            notes=data.get('notes')
        )
        return jsonify(member.to_dict()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@members_bp.route('/<int:member_id>', methods=['PUT'])
@require_shopify_auth
def update_member(member_id):
    """Update member details with tier change tracking."""
    from ..models import TierChangeLog
    from datetime import datetime

    tenant_id = g.tenant_id
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first_or_404()
    data = request.json

    # Track tier change for logging
    previous_tier_id = member.tier_id
    previous_tier_name = member.tier.name if member.tier else None

    # Update allowed fields
    if 'name' in data:
        member.name = data['name']
    if 'phone' in data:
        member.phone = data['phone']
    if 'email' in data:
        member.email = data['email']
    if 'tier_id' in data and data['tier_id'] != previous_tier_id:
        member.tier_id = data['tier_id']
        member.tier_assigned_at = datetime.utcnow()
        member.tier_assigned_by = 'staff'
    if 'status' in data:
        member.status = data['status']
    if 'shopify_customer_id' in data:
        member.shopify_customer_id = data['shopify_customer_id']
    if 'notes' in data:
        member.notes = data['notes']

    db.session.flush()  # Ensure tier relationship is loaded

    # Log tier change if it occurred
    if 'tier_id' in data and data['tier_id'] != previous_tier_id:
        new_tier = MembershipTier.query.get(data['tier_id'])
        new_tier_name = new_tier.name if new_tier else None

        # Determine change type
        if previous_tier_id is None:
            change_type = 'assigned'
        elif data['tier_id'] is None:
            change_type = 'removed'
        else:
            # Check bonus rates to determine upgrade vs downgrade
            prev_tier = MembershipTier.query.get(previous_tier_id)
            prev_bonus = prev_tier.trade_in_bonus_pct if prev_tier else 0
            new_bonus = new_tier.trade_in_bonus_pct if new_tier else 0
            change_type = 'upgraded' if new_bonus > prev_bonus else 'downgraded'

        tier_log = TierChangeLog(
            tenant_id=tenant_id,
            member_id=member_id,
            previous_tier_id=previous_tier_id,
            new_tier_id=data['tier_id'],
            previous_tier_name=previous_tier_name,
            new_tier_name=new_tier_name,
            change_type=change_type,
            source_type='staff',
            source_reference=request.headers.get('X-Staff-Email', 'API'),
            reason=data.get('tier_change_reason', 'Manual tier change via API'),
            created_by=request.headers.get('X-Staff-Email', 'API')
        )
        db.session.add(tier_log)

    db.session.commit()
    return jsonify(member.to_dict())


@members_bp.route('/<int:member_id>', methods=['DELETE'])
@require_shopify_auth
def delete_member(member_id):
    """
    Delete a member from the TradeUp program.

    This is a hard delete - removes the member record entirely.
    Does NOT affect the Shopify customer account.

    Use with caution - typically for cleaning up test data or
    members that were created incorrectly (e.g., not linked to Shopify).
    """
    from sqlalchemy import text, inspect
    tenant_id = g.tenant_id

    # Use raw SQL to get member data to avoid triggering relationship loading
    result = db.session.execute(
        text("SELECT id, member_number, name, email FROM members WHERE id = :mid AND tenant_id = :tid"),
        {'mid': member_id, 'tid': tenant_id}
    ).fetchone()

    if not result:
        return jsonify({'error': 'Member not found'}), 404

    member_number = result.member_number
    member_name = result.name or result.email

    try:
        # Get list of existing tables to avoid errors on non-existent tables
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

        # Delete related records first (to avoid foreign key issues)
        # Use raw SQL to avoid loading relationships on models

        # Delete store credit records
        if 'store_credit_ledger' in existing_tables:
            db.session.execute(
                text("DELETE FROM store_credit_ledger WHERE member_id = :mid"),
                {'mid': member_id}
            )
        if 'member_credit_balances' in existing_tables:
            db.session.execute(
                text("DELETE FROM member_credit_balances WHERE member_id = :mid"),
                {'mid': member_id}
            )

        # Delete tier history records
        if 'tier_change_logs' in existing_tables:
            db.session.execute(
                text("DELETE FROM tier_change_logs WHERE member_id = :mid"),
                {'mid': member_id}
            )
        if 'member_promo_usages' in existing_tables:
            db.session.execute(
                text("DELETE FROM member_promo_usages WHERE member_id = :mid"),
                {'mid': member_id}
            )

        # Delete referral records (if table exists)
        if 'referrals' in existing_tables:
            db.session.execute(
                text("DELETE FROM referrals WHERE referrer_id = :mid OR referee_id = :mid"),
                {'mid': member_id}
            )

        # Unlink trade-in batches (set member_id to NULL instead of deleting)
        if 'trade_in_batches' in existing_tables:
            db.session.execute(
                text("UPDATE trade_in_batches SET member_id = NULL WHERE member_id = :mid"),
                {'mid': member_id}
            )

        # Clear referred_by references from other members (if column exists)
        # Check if referred_by_id column exists in members table
        members_columns = {col['name'] for col in inspector.get_columns('members')}
        if 'referred_by_id' in members_columns:
            db.session.execute(
                text("UPDATE members SET referred_by_id = NULL WHERE referred_by_id = :mid"),
                {'mid': member_id}
            )

        # Delete the member
        db.session.execute(
            text("DELETE FROM members WHERE id = :mid"),
            {'mid': member_id}
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Member {member_number} ({member_name}) has been deleted'
        })
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to delete member: {str(e)}'}), 500


# ==================== Member Status Management ====================

# Valid member statuses with display labels
MEMBER_STATUSES = {
    'pending': 'Pending',
    'active': 'Active',
    'suspended': 'Suspended',
    'paused': 'Suspended',  # Backward compatibility alias
    'cancelled': 'Cancelled',
    'expired': 'Expired'
}


@members_bp.route('/<int:member_id>/suspend', methods=['POST'])
@require_shopify_auth
def suspend_member(member_id):
    """
    Suspend a member's membership.

    Request body (optional):
        reason: string - Reason for suspension

    Returns:
        Updated member details
    """
    tenant_id = g.tenant_id
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first_or_404()
    data = request.get_json(silent=True) or {}

    if member.status == 'suspended':
        return jsonify({'error': 'Member is already suspended'}), 400

    if member.status == 'cancelled':
        return jsonify({'error': 'Cannot suspend a cancelled membership'}), 400

    previous_status = member.status
    member.status = 'suspended'

    # Add reason to notes if provided
    reason = data.get('reason')
    if reason:
        from datetime import datetime
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        note = f'\n[{timestamp}] Suspended: {reason}'
        member.notes = (member.notes or '') + note

    db.session.commit()

    return jsonify({
        'success': True,
        'member': member.to_dict(),
        'previous_status': previous_status,
        'message': 'Member suspended successfully'
    })


@members_bp.route('/<int:member_id>/reactivate', methods=['POST'])
@require_shopify_auth
def reactivate_member(member_id):
    """
    Reactivate a suspended or paused member.

    Request body (optional):
        reason: string - Reason for reactivation

    Returns:
        Updated member details
    """
    tenant_id = g.tenant_id
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first_or_404()
    data = request.get_json(silent=True) or {}

    # Allow reactivation from suspended, paused, or expired status
    if member.status not in ('suspended', 'paused', 'expired'):
        return jsonify({
            'error': f'Cannot reactivate member with status "{member.status}". Only suspended, paused, or expired members can be reactivated.'
        }), 400

    previous_status = member.status
    member.status = 'active'

    # Clear membership_end_date if it was set
    if member.membership_end_date:
        member.membership_end_date = None

    # Add reason to notes if provided
    reason = data.get('reason')
    if reason:
        from datetime import datetime
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        note = f'\n[{timestamp}] Reactivated: {reason}'
        member.notes = (member.notes or '') + note

    db.session.commit()

    return jsonify({
        'success': True,
        'member': member.to_dict(),
        'previous_status': previous_status,
        'message': 'Member reactivated successfully'
    })


@members_bp.route('/<int:member_id>/cancel', methods=['POST'])
@require_shopify_auth
def cancel_member(member_id):
    """
    Cancel a member's membership.

    Request body (optional):
        reason: string - Reason for cancellation

    Returns:
        Updated member details
    """
    from datetime import date
    tenant_id = g.tenant_id
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first_or_404()
    data = request.get_json(silent=True) or {}

    if member.status == 'cancelled':
        return jsonify({'error': 'Member is already cancelled'}), 400

    previous_status = member.status
    member.status = 'cancelled'
    member.membership_end_date = date.today()

    # Add reason to notes if provided
    reason = data.get('reason')
    if reason:
        from datetime import datetime
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        note = f'\n[{timestamp}] Cancelled: {reason}'
        member.notes = (member.notes or '') + note

    db.session.commit()

    return jsonify({
        'success': True,
        'member': member.to_dict(),
        'previous_status': previous_status,
        'message': 'Member cancelled successfully'
    })


@members_bp.route('/tiers', methods=['GET'])
@require_shopify_auth
def list_tiers():
    """List membership tiers for tenant.

    Auto-seeds default tiers if none exist.
    """
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware

    tiers = MembershipTier.query.filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).order_by(MembershipTier.display_order).all()

    # Auto-seed default tiers if none exist
    if not tiers:
        service = MembershipService(tenant_id)
        service.setup_default_tiers()
        tiers = MembershipTier.query.filter_by(
            tenant_id=tenant_id,
            is_active=True
        ).order_by(MembershipTier.display_order).all()

    return jsonify({
        'tiers': [t.to_dict() for t in tiers]
    })


@members_bp.route('/tiers', methods=['POST'])
@require_shopify_auth
def create_tier():
    """Create a new membership tier."""
    tenant_id = g.tenant_id  # Use tenant_id from auth decorator instead of header
    tenant = g.tenant
    data = request.json

    if not data or not data.get('name'):
        return jsonify({'error': 'Tier name is required'}), 400

    # Check plan limits before creating tier
    current_tier_count = MembershipTier.query.filter_by(tenant_id=tenant_id, is_active=True).count()
    max_tiers = tenant.max_tiers or 2  # Default to Free plan limit

    if current_tier_count >= max_tiers:
        return jsonify({
            'error': 'Tier limit reached',
            'message': f'Your plan allows up to {max_tiers} tiers. Please upgrade to add more.',
            'current_count': current_tier_count,
            'limit': max_tiers,
            'upgrade_required': True
        }), 403

    tier = MembershipTier(
        tenant_id=tenant_id,
        name=data['name'],
        monthly_price=data.get('monthly_price', 0),
        yearly_price=data.get('yearly_price'),
        bonus_rate=data.get('bonus_rate', 0),
        purchase_cashback_pct=data.get('purchase_cashback_pct', 0),
        monthly_credit_amount=data.get('monthly_credit_amount', 0),
        credit_expiration_days=data.get('credit_expiration_days'),
        benefits=data.get('benefits', {}),
        display_order=data.get('display_order', 0)
    )

    db.session.add(tier)
    db.session.commit()

    return jsonify(tier.to_dict()), 201


@members_bp.route('/tiers/<int:tier_id>', methods=['GET'])
@require_shopify_auth
def get_tier(tier_id):
    """Get a single membership tier."""
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware

    tier = MembershipTier.query.filter_by(
        id=tier_id,
        tenant_id=tenant_id
    ).first_or_404()

    return jsonify(tier.to_dict())


@members_bp.route('/tiers/<int:tier_id>', methods=['PUT'])
@require_shopify_auth
def update_tier(tier_id):
    """Update a membership tier."""
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware
    data = request.json

    tier = MembershipTier.query.filter_by(
        id=tier_id,
        tenant_id=tenant_id
    ).first_or_404()

    # Update allowed fields
    if 'name' in data:
        tier.name = data['name']
    if 'monthly_price' in data:
        tier.monthly_price = data['monthly_price']
    if 'yearly_price' in data:
        tier.yearly_price = data['yearly_price'] if data['yearly_price'] else None
    if 'bonus_rate' in data:
        tier.bonus_rate = data['bonus_rate']
    if 'purchase_cashback_pct' in data:
        tier.purchase_cashback_pct = data['purchase_cashback_pct']
    if 'monthly_credit_amount' in data:
        tier.monthly_credit_amount = data['monthly_credit_amount']
    if 'credit_expiration_days' in data:
        tier.credit_expiration_days = data['credit_expiration_days'] if data['credit_expiration_days'] else None
    if 'benefits' in data:
        tier.benefits = data['benefits']
    if 'display_order' in data:
        tier.display_order = data['display_order']
    if 'is_active' in data:
        tier.is_active = data['is_active']

    db.session.commit()
    return jsonify(tier.to_dict())


@members_bp.route('/tiers/<int:tier_id>', methods=['DELETE'])
@require_shopify_auth
def delete_tier(tier_id):
    """Delete (deactivate) a membership tier.

    Soft delete - sets is_active=False rather than removing.
    Cannot delete tier if members are using it.
    """
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware

    tier = MembershipTier.query.filter_by(
        id=tier_id,
        tenant_id=tenant_id
    ).first_or_404()

    # Check if any members are using this tier
    member_count = Member.query.filter_by(tier_id=tier_id).count()
    if member_count > 0:
        return jsonify({
            'error': f'Cannot delete tier with {member_count} active members'
        }), 400

    # Soft delete
    tier.is_active = False
    db.session.commit()

    return jsonify({'success': True, 'message': f'Tier "{tier.name}" deleted'})


@members_bp.route('/tiers/reorder', methods=['POST'])
@require_shopify_auth
def reorder_tiers():
    """Reorder membership tiers.

    JSON body:
        tier_ids: List of tier IDs in desired order
    """
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware
    data = request.json

    tier_ids = data.get('tier_ids', [])
    if not tier_ids:
        return jsonify({'error': 'tier_ids is required'}), 400

    # Update display_order for each tier
    for order, tier_id in enumerate(tier_ids):
        tier = MembershipTier.query.filter_by(
            id=tier_id,
            tenant_id=tenant_id
        ).first()
        if tier:
            tier.display_order = order

    db.session.commit()

    # Return updated tiers
    tiers = MembershipTier.query.filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).order_by(MembershipTier.display_order).all()

    return jsonify({
        'success': True,
        'tiers': [t.to_dict() for t in tiers]
    })


# ==================== Bulk Email Operations ====================

@members_bp.route('/email/preview', methods=['POST'])
@require_shopify_auth
def preview_tier_email():
    """
    Preview tier email - get recipient counts without sending.

    JSON body:
        tier_names: List of tier names (e.g., ['GOLD', 'PLATINUM'])

    Returns:
        Counts of members per tier
    """
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware
    data = request.json

    tier_names = data.get('tier_names', [])
    if not tier_names:
        return jsonify({'error': 'tier_names is required'}), 400

    # Get member counts by tier
    tiers = MembershipTier.query.filter(
        MembershipTier.tenant_id == tenant_id,
        MembershipTier.name.in_(tier_names),
        MembershipTier.is_active == True
    ).all()

    if not tiers:
        return jsonify({'error': f'No active tiers found matching: {tier_names}'}), 400

    tier_ids = [t.id for t in tiers]

    # Count active members in these tiers
    member_counts = {}
    total = 0
    for tier in tiers:
        count = Member.query.filter(
            Member.tenant_id == tenant_id,
            Member.tier_id == tier.id,
            Member.status == 'active'
        ).count()
        member_counts[tier.name] = count
        total += count

    return jsonify({
        'tier_names': tier_names,
        'member_counts': member_counts,
        'total_recipients': total
    })


@members_bp.route('/email/send', methods=['POST'])
@require_shopify_auth
def send_tier_email():
    """
    Send bulk email to members in specified tiers.

    JSON body:
        tier_names: List of tier names (e.g., ['GOLD', 'PLATINUM'])
        subject: Email subject line
        message: Plain text message body
        html_message: HTML message body (optional)

    Personalization variables available:
        {member_name} - Member's name
        {member_number} - Member number (TU1001)
        {tier_name} - Member's tier name

    Returns:
        Send results (sent count, failed count, etc.)
    """
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware
    staff_email = request.headers.get('X-Staff-Email', 'admin')
    data = request.json

    tier_names = data.get('tier_names', [])
    subject = data.get('subject', '').strip()
    message = data.get('message', '').strip()
    html_message = data.get('html_message')

    # Validation
    if not tier_names:
        return jsonify({'error': 'tier_names is required'}), 400
    if not subject:
        return jsonify({'error': 'subject is required'}), 400
    if not message:
        return jsonify({'error': 'message is required'}), 400

    # Send via notification service
    from ..services.notification_service import notification_service

    result = notification_service.send_bulk_tier_email(
        tenant_id=tenant_id,
        tier_names=tier_names,
        subject=subject,
        text_content=message,
        html_content=html_message,
        created_by=staff_email
    )

    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400


# ==================== Metafield Sync Operations ====================

@members_bp.route('/<int:member_id>/sync-metafields', methods=['POST'])
@require_shopify_auth
def sync_member_metafields(member_id):
    """
    Sync a member's data to Shopify customer metafields.

    This updates the following metafields in Shopify:
    - tradeup.member_number
    - tradeup.tier
    - tradeup.credit_balance
    - tradeup.trade_in_count
    - tradeup.total_bonus_earned
    - tradeup.status
    - tradeup.joined_date

    Returns:
        Sync result with metafields set
    """
    tenant_id = g.tenant_id
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first_or_404()

    if not member.shopify_customer_id:
        return jsonify({
            'success': False,
            'error': 'Member is not linked to a Shopify customer'
        }), 400

    service = MembershipService(tenant_id)
    result = service.sync_member_metafields_to_shopify(member)

    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 500


@members_bp.route('/<int:member_id>/verify-metafields', methods=['GET'])
@require_shopify_auth
def verify_member_metafields(member_id):
    """
    Verify a member's metafields match Shopify.

    Compares TradeUp member data with Shopify customer metafields
    and reports any discrepancies.

    Returns:
        Verification result with any mismatches
    """
    tenant_id = g.tenant_id
    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first_or_404()

    if not member.shopify_customer_id:
        return jsonify({
            'success': False,
            'error': 'Member is not linked to a Shopify customer'
        }), 400

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(tenant_id)

        # Get current metafields from Shopify
        shopify_result = client.get_customer_metafields(member.shopify_customer_id)

        if not shopify_result.get('success'):
            return jsonify({
                'success': False,
                'error': shopify_result.get('error', 'Failed to fetch Shopify metafields')
            }), 500

        shopify_metafields = shopify_result.get('metafields', {})

        # Build expected values from TradeUp
        expected = {
            'member_number': member.member_number,
            'tier': member.tier.name if member.tier else 'None',
            'status': member.status or 'active'
        }

        # Compare and find mismatches
        mismatches = []
        for key, expected_value in expected.items():
            shopify_value = shopify_metafields.get(key, {}).get('value')
            if shopify_value != expected_value:
                mismatches.append({
                    'field': key,
                    'expected': expected_value,
                    'actual': shopify_value
                })

        in_sync = len(mismatches) == 0

        return jsonify({
            'success': True,
            'member_id': member.id,
            'member_number': member.member_number,
            'shopify_customer_id': member.shopify_customer_id,
            'in_sync': in_sync,
            'mismatches': mismatches,
            'shopify_metafields': shopify_metafields,
            'expected': expected
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@members_bp.route('/sync-all-metafields', methods=['POST'])
@require_shopify_auth
def sync_all_member_metafields():
    """
    Sync all active members' metafields to Shopify.

    Query params:
        dry_run: If true, only reports what would be synced (default: false)

    Returns:
        Sync results with counts and any errors
    """
    tenant_id = g.tenant_id
    dry_run = request.args.get('dry_run', 'false').lower() == 'true'

    # Get all active members with Shopify links
    members = Member.query.filter(
        Member.tenant_id == tenant_id,
        Member.status == 'active',
        Member.shopify_customer_id.isnot(None)
    ).all()

    results = {
        'total': len(members),
        'synced': 0,
        'skipped': 0,
        'failed': 0,
        'errors': [],
        'dry_run': dry_run
    }

    if dry_run:
        return jsonify({
            **results,
            'message': f'Dry run: Would sync {len(members)} members'
        })

    service = MembershipService(tenant_id)

    for member in members:
        try:
            result = service.sync_member_metafields_to_shopify(member)
            if result.get('success'):
                results['synced'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'member_id': member.id,
                    'member_number': member.member_number,
                    'error': result.get('error', 'Unknown error')
                })
        except Exception as e:
            results['failed'] += 1
            results['errors'].append({
                'member_id': member.id,
                'member_number': member.member_number,
                'error': str(e)
            })

    return jsonify(results)


@members_bp.route('/verify-all-metafields', methods=['GET'])
@require_shopify_auth
def verify_all_member_metafields():
    """
    Verify metafields for all active members.

    Query params:
        limit: Max members to check (default: 100)
        only_mismatched: If true, only return members with mismatches (default: false)

    Returns:
        Verification results with sync status for each member
    """
    tenant_id = g.tenant_id
    limit = request.args.get('limit', 100, type=int)
    only_mismatched = request.args.get('only_mismatched', 'false').lower() == 'true'

    # Get members with Shopify links
    members = Member.query.filter(
        Member.tenant_id == tenant_id,
        Member.status == 'active',
        Member.shopify_customer_id.isnot(None)
    ).limit(limit).all()

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(tenant_id)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to initialize Shopify client: {str(e)}'
        }), 500

    results = {
        'total_checked': 0,
        'in_sync': 0,
        'out_of_sync': 0,
        'members': []
    }

    for member in members:
        results['total_checked'] += 1

        try:
            shopify_result = client.get_customer_metafields(member.shopify_customer_id)
            shopify_metafields = shopify_result.get('metafields', {}) if shopify_result.get('success') else {}

            expected = {
                'member_number': member.member_number,
                'tier': member.tier.name if member.tier else 'None',
                'status': member.status or 'active'
            }

            mismatches = []
            for key, expected_value in expected.items():
                shopify_value = shopify_metafields.get(key, {}).get('value')
                if shopify_value != expected_value:
                    mismatches.append({
                        'field': key,
                        'expected': expected_value,
                        'actual': shopify_value
                    })

            in_sync = len(mismatches) == 0

            if in_sync:
                results['in_sync'] += 1
            else:
                results['out_of_sync'] += 1

            # Only include in results if showing all or member is mismatched
            if not only_mismatched or not in_sync:
                results['members'].append({
                    'member_id': member.id,
                    'member_number': member.member_number,
                    'in_sync': in_sync,
                    'mismatches': mismatches
                })

        except Exception as e:
            results['out_of_sync'] += 1
            results['members'].append({
                'member_id': member.id,
                'member_number': member.member_number,
                'in_sync': False,
                'error': str(e)
            })

    results['success'] = True
    return jsonify(results)


@members_bp.route('/email/templates', methods=['GET'])
@require_shopify_auth
def get_email_templates():
    """Get pre-built email templates for common scenarios."""
    templates = [
        {
            'id': 'promotion_announcement',
            'name': 'Promotion Announcement',
            'subject': 'Exclusive Offer for {tier_name} Members!',
            'message': '''Hi {member_name},

As a valued {tier_name} member, you have exclusive access to our latest promotion!

[Describe your promotion here]

Use your member benefits to maximize your savings.

Thank you for being a loyal member!

Best regards,
The Team''',
            'category': 'marketing'
        },
        {
            'id': 'new_arrival',
            'name': 'New Arrivals',
            'subject': 'New Inventory Just Dropped!',
            'message': '''Hi {member_name},

Exciting news! We just got in new inventory you won't want to miss.

[Describe new arrivals here]

As a {tier_name} member, you get early access before the general public.

See you soon!

Best regards,
The Team''',
            'category': 'marketing'
        },
        {
            'id': 'event_invite',
            'name': 'Event Invitation',
            'subject': 'You\'re Invited: {tier_name} Member Event',
            'message': '''Hi {member_name},

You're invited to an exclusive event for our members!

Event Details:
[Date, time, location]

[Event description]

RSVP by replying to this email.

We look forward to seeing you there!

Best regards,
The Team''',
            'category': 'events'
        },
        {
            'id': 'tier_benefit_reminder',
            'name': 'Tier Benefits Reminder',
            'subject': 'Maximize Your {tier_name} Benefits',
            'message': '''Hi {member_name},

Just a friendly reminder of your amazing {tier_name} member benefits:

• Trade-in bonus: Extra credit on every trade
• Purchase cashback: Earn on every order
• Exclusive access to member events

Make sure you're taking full advantage!

Best regards,
The Team''',
            'category': 'engagement'
        }
    ]

    return jsonify({'templates': templates})
