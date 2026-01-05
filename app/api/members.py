"""
Member API endpoints.

Shopify-Native Member System:
- Members MUST be linked to existing Shopify customers
- No manual member creation - use search & enroll workflow
- Flow: Search Shopify customers → Enroll as member → Create trade-ins
"""
from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import Member, MembershipTier
from ..services.membership_service import MembershipService

members_bp = Blueprint('members', __name__)


# ==================== Shopify Customer Search & Enroll ====================

@members_bp.route('/search-shopify', methods=['GET'])
def search_shopify_customers():
    """
    Search Shopify customers for enrollment.

    Query params:
        q: Search query (name, email, phone, or ORB#)

    Returns customers with enrollment status (is_member, member_number, member_tier).
    """
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify({'error': 'Search query must be at least 2 characters'}), 400

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
        return jsonify({'error': f'Search failed: {str(e)}'}), 500


@members_bp.route('/enroll', methods=['POST'])
def enroll_shopify_customer():
    """
    Enroll an existing Shopify customer as a Quick Flip member.

    JSON body:
        shopify_customer_id: Shopify customer ID (numeric) - REQUIRED
        tier_id: Membership tier ID (optional, defaults to lowest tier)
        partner_customer_id: Partner ID like ORB# (optional)
        notes: Internal notes (optional)

    Customer name/email/phone are pulled from Shopify automatically.
    """
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
    data = request.json or {}

    shopify_customer_id = data.get('shopify_customer_id')
    if not shopify_customer_id:
        return jsonify({'error': 'shopify_customer_id is required'}), 400

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


# ==================== Member CRUD ====================

@members_bp.route('', methods=['GET'])
def list_members():
    """List all members for the tenant."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))  # Default to tenant 1 for MVP

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status')

    query = Member.query.filter_by(tenant_id=tenant_id)

    if status:
        query = query.filter_by(status=status)

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


@members_bp.route('/<int:member_id>', methods=['GET'])
def get_member(member_id):
    """Get member details."""
    member = Member.query.get_or_404(member_id)
    return jsonify(member.to_dict(include_stats=True))


@members_bp.route('/by-number/<member_number>', methods=['GET'])
def get_member_by_number(member_number):
    """Get member by member number (QF1001)."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    # Normalize member number
    if not member_number.upper().startswith('QF'):
        member_number = f'QF{member_number}'

    member = Member.query.filter_by(
        tenant_id=tenant_id,
        member_number=member_number.upper()
    ).first_or_404()

    return jsonify(member.to_dict(include_stats=True))


@members_bp.route('', methods=['POST'])
def create_member():
    """Create a new member."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
    data = request.json

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
def update_member(member_id):
    """Update member details."""
    member = Member.query.get_or_404(member_id)
    data = request.json

    # Update allowed fields
    if 'name' in data:
        member.name = data['name']
    if 'phone' in data:
        member.phone = data['phone']
    if 'email' in data:
        member.email = data['email']
    if 'tier_id' in data:
        member.tier_id = data['tier_id']
    if 'status' in data:
        member.status = data['status']
    if 'shopify_customer_id' in data:
        member.shopify_customer_id = data['shopify_customer_id']
    if 'notes' in data:
        member.notes = data['notes']

    db.session.commit()
    return jsonify(member.to_dict())


@members_bp.route('/tiers', methods=['GET'])
def list_tiers():
    """List membership tiers for tenant."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    tiers = MembershipTier.query.filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).order_by(MembershipTier.display_order).all()

    return jsonify({
        'tiers': [t.to_dict() for t in tiers]
    })


@members_bp.route('/tiers', methods=['POST'])
def create_tier():
    """Create a new membership tier."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
    data = request.json

    tier = MembershipTier(
        tenant_id=tenant_id,
        name=data['name'],
        monthly_price=data['monthly_price'],
        bonus_rate=data['bonus_rate'],
        quick_flip_days=data.get('quick_flip_days', 7),
        benefits=data.get('benefits', {}),
        display_order=data.get('display_order', 0)
    )

    db.session.add(tier)
    db.session.commit()

    return jsonify(tier.to_dict()), 201


@members_bp.route('/tiers/<int:tier_id>', methods=['GET'])
def get_tier(tier_id):
    """Get a single membership tier."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    tier = MembershipTier.query.filter_by(
        id=tier_id,
        tenant_id=tenant_id
    ).first_or_404()

    return jsonify(tier.to_dict())


@members_bp.route('/tiers/<int:tier_id>', methods=['PUT'])
def update_tier(tier_id):
    """Update a membership tier."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
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
    if 'bonus_rate' in data:
        tier.bonus_rate = data['bonus_rate']
    if 'quick_flip_days' in data:
        tier.quick_flip_days = data['quick_flip_days']
    if 'benefits' in data:
        tier.benefits = data['benefits']
    if 'display_order' in data:
        tier.display_order = data['display_order']
    if 'is_active' in data:
        tier.is_active = data['is_active']

    db.session.commit()
    return jsonify(tier.to_dict())


@members_bp.route('/tiers/<int:tier_id>', methods=['DELETE'])
def delete_tier(tier_id):
    """Delete (deactivate) a membership tier.

    Soft delete - sets is_active=False rather than removing.
    Cannot delete tier if members are using it.
    """
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

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
def reorder_tiers():
    """Reorder membership tiers.

    JSON body:
        tier_ids: List of tier IDs in desired order
    """
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
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
