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
from ..middleware.shopify_auth import require_shopify_auth

members_bp = Blueprint('members', __name__)


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
@require_shopify_auth
def list_members():
    """List all members for the tenant."""
    tenant_id = g.tenant_id  # Use tenant_id from auth middleware

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
@require_shopify_auth
def get_member(member_id):
    """Get member details."""
    member = Member.query.get_or_404(member_id)
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
    data = request.json

    if not data or not data.get('name'):
        return jsonify({'error': 'Tier name is required'}), 400

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
