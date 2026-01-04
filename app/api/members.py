"""
Member API endpoints.
"""
from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import Member, MembershipTier
from ..services.membership_service import MembershipService

members_bp = Blueprint('members', __name__)


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
