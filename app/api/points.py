"""
Points API endpoints for TradeUp loyalty program.

Handles:
- Points balance and history queries
- Earning rules management (admin)
- Manual point adjustments (admin)
- Customer-facing points endpoints (for extensions)
"""
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, request, jsonify, g, current_app
from sqlalchemy import func, and_
from ..extensions import db
from ..models import Member, PointsTransaction
from ..models.loyalty_points import EarningRule, Reward, PointsBalance
from ..middleware.shopify_auth import require_shopify_auth

points_bp = Blueprint('points', __name__)


# ==============================================================================
# POINTS BALANCE & HISTORY (Member-facing)
# ==============================================================================

@points_bp.route('/balance', methods=['GET'])
@require_shopify_auth
def get_points_balance():
    """
    Get member's points balance.

    Query params:
        member_id: Member ID (required for admin view)

    For customer-facing, use X-Customer-ID header instead.

    Returns:
        Current points balance and tier multiplier info
    """
    tenant_id = g.tenant_id
    member_id = request.args.get('member_id', type=int)

    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400

    member = Member.query.filter_by(
        id=member_id,
        tenant_id=tenant_id
    ).first()

    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Calculate points balance from transactions
    balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id,
        PointsTransaction.reversed_at.is_(None)  # Exclude reversed transactions
    ).scalar()

    # Get tier info for earning multiplier
    tier_info = None
    earning_multiplier = Decimal('1.0')
    if member.tier:
        tier_info = {
            'id': member.tier.id,
            'name': member.tier.name,
            'bonus_rate': float(member.tier.bonus_rate)
        }
        # If tier has bonus_rate, use it as multiplier (e.g., 0.10 = 10% bonus = 1.10x)
        earning_multiplier = Decimal('1.0') + (member.tier.bonus_rate or Decimal('0'))

    return jsonify({
        'member_id': member_id,
        'member_number': member.member_number,
        'points_balance': int(balance),
        'tier': tier_info,
        'earning_multiplier': float(earning_multiplier),
        'as_of': datetime.utcnow().isoformat()
    })


@points_bp.route('/history', methods=['GET'])
@require_shopify_auth
def get_points_history():
    """
    Get member's points transaction history (paginated).

    Query params:
        member_id: Member ID (required)
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)
        transaction_type: Filter by type (earn, redeem, adjustment, expire)
        source: Filter by source (order, referral, admin, etc.)
        start_date: Filter from date (ISO format)
        end_date: Filter to date (ISO format)

    Returns:
        Paginated list of points transactions
    """
    tenant_id = g.tenant_id
    member_id = request.args.get('member_id', type=int)

    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400

    # Verify member belongs to tenant
    member = Member.query.filter_by(
        id=member_id,
        tenant_id=tenant_id
    ).first()

    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    # Build query
    query = PointsTransaction.query.filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id
    )

    # Filters
    transaction_type = request.args.get('transaction_type')
    if transaction_type:
        query = query.filter(PointsTransaction.transaction_type == transaction_type)

    source = request.args.get('source')
    if source:
        query = query.filter(PointsTransaction.source == source)

    start_date = request.args.get('start_date')
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(PointsTransaction.created_at >= start_dt)
        except ValueError:
            pass

    end_date = request.args.get('end_date')
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(PointsTransaction.created_at <= end_dt)
        except ValueError:
            pass

    # Order by most recent first
    query = query.order_by(PointsTransaction.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'transactions': [t.to_dict() for t in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        },
        'member': {
            'id': member.id,
            'member_number': member.member_number,
            'name': member.name
        }
    })


@points_bp.route('/summary', methods=['GET'])
@require_shopify_auth
def get_points_summary():
    """
    Get earning and redemption summary statistics.

    Query params:
        member_id: Member ID (required)
        period: Time period - 'all', '30d', '90d', '1y' (default 'all')

    Returns:
        Summary stats including total earned, redeemed, expired, etc.
    """
    tenant_id = g.tenant_id
    member_id = request.args.get('member_id', type=int)
    period = request.args.get('period', 'all')

    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400

    # Verify member
    member = Member.query.filter_by(
        id=member_id,
        tenant_id=tenant_id
    ).first()

    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Calculate date filter
    date_filter = None
    if period == '30d':
        date_filter = datetime.utcnow() - timedelta(days=30)
    elif period == '90d':
        date_filter = datetime.utcnow() - timedelta(days=90)
    elif period == '1y':
        date_filter = datetime.utcnow() - timedelta(days=365)

    # Base query
    base_query = PointsTransaction.query.filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id,
        PointsTransaction.reversed_at.is_(None)
    )

    if date_filter:
        base_query = base_query.filter(PointsTransaction.created_at >= date_filter)

    # Total earned (positive transactions from earning)
    total_earned = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id,
        PointsTransaction.transaction_type == 'earn',
        PointsTransaction.reversed_at.is_(None),
        PointsTransaction.created_at >= date_filter if date_filter else True
    ).scalar()

    # Total redeemed (negative transactions from redemption)
    total_redeemed = db.session.query(
        func.coalesce(func.sum(func.abs(PointsTransaction.points)), 0)
    ).filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id,
        PointsTransaction.transaction_type == 'redeem',
        PointsTransaction.reversed_at.is_(None),
        PointsTransaction.created_at >= date_filter if date_filter else True
    ).scalar()

    # Total expired
    total_expired = db.session.query(
        func.coalesce(func.sum(func.abs(PointsTransaction.points)), 0)
    ).filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id,
        PointsTransaction.transaction_type == 'expire',
        PointsTransaction.reversed_at.is_(None),
        PointsTransaction.created_at >= date_filter if date_filter else True
    ).scalar()

    # Breakdown by source
    source_breakdown = db.session.query(
        PointsTransaction.source,
        func.sum(PointsTransaction.points).label('total')
    ).filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id,
        PointsTransaction.transaction_type == 'earn',
        PointsTransaction.reversed_at.is_(None),
        PointsTransaction.created_at >= date_filter if date_filter else True
    ).group_by(PointsTransaction.source).all()

    # Current balance
    current_balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    return jsonify({
        'member_id': member_id,
        'period': period,
        'summary': {
            'current_balance': int(current_balance),
            'total_earned': int(total_earned),
            'total_redeemed': int(total_redeemed),
            'total_expired': int(total_expired),
            'net_change': int(total_earned) - int(total_redeemed) - int(total_expired)
        },
        'breakdown_by_source': {
            row.source or 'other': int(row.total)
            for row in source_breakdown
        },
        'as_of': datetime.utcnow().isoformat()
    })


# ==============================================================================
# EARNING RULES (Admin)
# ==============================================================================

@points_bp.route('/rules', methods=['GET'])
@require_shopify_auth
def list_earning_rules():
    """
    List all points earning rules for the tenant.

    Returns:
        List of earning rules with their configurations
    """
    tenant_id = g.tenant_id

    rules = EarningRule.query.filter_by(
        tenant_id=tenant_id
    ).order_by(EarningRule.priority.desc()).all()

    return jsonify({
        'rules': [r.to_dict() for r in rules],
        'count': len(rules)
    })


@points_bp.route('/rules', methods=['POST'])
@require_shopify_auth
def create_earning_rule():
    """
    Create a new points earning rule.

    JSON body:
        name: Rule name (required)
        rule_type: Type of rule (required) - 'purchase', 'referral', 'signup',
                   'review', 'birthday', 'custom'
        points_type: How points are calculated (required) - 'fixed', 'per_dollar',
                     'percentage'
        points_value: Points amount or rate (required)
        min_order_amount: Minimum order amount to qualify (optional)
        max_points_per_order: Cap on points per order (optional)
        product_collection_id: Limit to specific collection (optional)
        tier_multipliers: Dict of tier_id -> multiplier (optional)
        conditions: Additional conditions JSON (optional)
        starts_at: Rule start date (optional)
        ends_at: Rule end date (optional)

    Returns:
        Created rule
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    # Validation
    required = ['name', 'rule_type', 'points_type', 'points_value']
    for field in required:
        if field not in data or data[field] is None:
            return jsonify({'error': f'{field} is required'}), 400

    valid_rule_types = ['purchase', 'referral', 'signup', 'review', 'birthday', 'custom']
    if data['rule_type'] not in valid_rule_types:
        return jsonify({'error': f'rule_type must be one of: {valid_rule_types}'}), 400

    valid_points_types = ['fixed', 'per_dollar', 'percentage']
    if data['points_type'] not in valid_points_types:
        return jsonify({'error': f'points_type must be one of: {valid_points_types}'}), 400

    try:
        # Calculate priority (newer rules get higher priority by default)
        max_priority = db.session.query(
            func.coalesce(func.max(EarningRule.priority), 0)
        ).filter(EarningRule.tenant_id == tenant_id).scalar()

        rule = EarningRule(
            tenant_id=tenant_id,
            name=data['name'],
            description=data.get('description'),
            rule_type=data['rule_type'],
            points_type=data['points_type'],
            points_value=Decimal(str(data['points_value'])),
            min_order_amount=Decimal(str(data['min_order_amount'])) if data.get('min_order_amount') else None,
            max_points_per_order=data.get('max_points_per_order'),
            product_collection_id=data.get('product_collection_id'),
            tier_multipliers=data.get('tier_multipliers', {}),
            conditions=data.get('conditions', {}),
            priority=max_priority + 1,
            is_active=data.get('is_active', True),
            starts_at=datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00')) if data.get('starts_at') else None,
            ends_at=datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00')) if data.get('ends_at') else None
        )

        db.session.add(rule)
        db.session.commit()

        return jsonify({
            'success': True,
            'rule': rule.to_dict(),
            'message': f'Earning rule "{rule.name}" created'
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating earning rule: {e}")
        return jsonify({'error': f'Failed to create rule: {str(e)}'}), 500


@points_bp.route('/rules/<int:rule_id>', methods=['GET'])
@require_shopify_auth
def get_earning_rule(rule_id):
    """Get a single earning rule."""
    tenant_id = g.tenant_id

    rule = EarningRule.query.filter_by(
        id=rule_id,
        tenant_id=tenant_id
    ).first()

    if not rule:
        return jsonify({'error': 'Rule not found'}), 404

    return jsonify(rule.to_dict())


@points_bp.route('/rules/<int:rule_id>', methods=['PUT'])
@require_shopify_auth
def update_earning_rule(rule_id):
    """
    Update an earning rule.

    JSON body:
        All fields from create are updatable

    Returns:
        Updated rule
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    rule = EarningRule.query.filter_by(
        id=rule_id,
        tenant_id=tenant_id
    ).first()

    if not rule:
        return jsonify({'error': 'Rule not found'}), 404

    try:
        # Update fields
        if 'name' in data:
            rule.name = data['name']
        if 'description' in data:
            rule.description = data['description']
        if 'rule_type' in data:
            rule.rule_type = data['rule_type']
        if 'points_type' in data:
            rule.points_type = data['points_type']
        if 'points_value' in data:
            rule.points_value = Decimal(str(data['points_value']))
        if 'min_order_amount' in data:
            rule.min_order_amount = Decimal(str(data['min_order_amount'])) if data['min_order_amount'] else None
        if 'max_points_per_order' in data:
            rule.max_points_per_order = data['max_points_per_order']
        if 'product_collection_id' in data:
            rule.product_collection_id = data['product_collection_id']
        if 'tier_multipliers' in data:
            rule.tier_multipliers = data['tier_multipliers']
        if 'conditions' in data:
            rule.conditions = data['conditions']
        if 'priority' in data:
            rule.priority = data['priority']
        if 'is_active' in data:
            rule.is_active = data['is_active']
        if 'starts_at' in data:
            rule.starts_at = datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00')) if data['starts_at'] else None
        if 'ends_at' in data:
            rule.ends_at = datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00')) if data['ends_at'] else None

        rule.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'rule': rule.to_dict(),
            'message': f'Rule "{rule.name}" updated'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating earning rule: {e}")
        return jsonify({'error': f'Failed to update rule: {str(e)}'}), 500


@points_bp.route('/rules/<int:rule_id>', methods=['DELETE'])
@require_shopify_auth
def delete_earning_rule(rule_id):
    """
    Delete an earning rule.

    Soft delete - sets is_active=False.
    """
    tenant_id = g.tenant_id

    rule = EarningRule.query.filter_by(
        id=rule_id,
        tenant_id=tenant_id
    ).first()

    if not rule:
        return jsonify({'error': 'Rule not found'}), 404

    # Soft delete
    rule.is_active = False
    rule.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Rule "{rule.name}" deleted'
    })


@points_bp.route('/rules/<int:rule_id>/toggle', methods=['POST'])
@require_shopify_auth
def toggle_earning_rule(rule_id):
    """
    Enable or disable an earning rule.

    Returns:
        Updated rule with new status
    """
    tenant_id = g.tenant_id

    rule = EarningRule.query.filter_by(
        id=rule_id,
        tenant_id=tenant_id
    ).first()

    if not rule:
        return jsonify({'error': 'Rule not found'}), 404

    rule.is_active = not rule.is_active
    rule.updated_at = datetime.utcnow()
    db.session.commit()

    status = 'enabled' if rule.is_active else 'disabled'
    return jsonify({
        'success': True,
        'rule': rule.to_dict(),
        'message': f'Rule "{rule.name}" {status}'
    })


# ==============================================================================
# MANUAL ADJUSTMENTS (Admin)
# ==============================================================================

@points_bp.route('/adjust', methods=['POST'])
@require_shopify_auth
def adjust_points():
    """
    Manually adjust a member's points balance.

    JSON body:
        member_id: Member ID (required)
        points: Points to add (positive) or remove (negative) (required)
        reason: Reason for adjustment (required)
        reference_id: Optional reference (e.g., ticket number)

    Returns:
        Created adjustment transaction and new balance
    """
    tenant_id = g.tenant_id
    staff_id = g.staff_id or 'admin'
    data = request.json or {}

    # Validation
    member_id = data.get('member_id')
    points = data.get('points')
    reason = data.get('reason', '').strip()

    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400
    if points is None:
        return jsonify({'error': 'points is required'}), 400
    if not reason:
        return jsonify({'error': 'reason is required for manual adjustments'}), 400

    try:
        points = int(points)
    except (ValueError, TypeError):
        return jsonify({'error': 'points must be an integer'}), 400

    if points == 0:
        return jsonify({'error': 'points cannot be zero'}), 400

    # Verify member
    member = Member.query.filter_by(
        id=member_id,
        tenant_id=tenant_id
    ).first()

    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Check if deduction would result in negative balance
    if points < 0:
        current_balance = db.session.query(
            func.coalesce(func.sum(PointsTransaction.points), 0)
        ).filter(
            PointsTransaction.member_id == member_id,
            PointsTransaction.tenant_id == tenant_id,
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        if current_balance + points < 0:
            return jsonify({
                'error': 'Insufficient points',
                'current_balance': int(current_balance),
                'requested_deduction': abs(points)
            }), 400

    try:
        # Create adjustment transaction
        transaction = PointsTransaction(
            tenant_id=tenant_id,
            member_id=member_id,
            points=points,
            transaction_type='adjustment',
            source='admin',
            reference_id=data.get('reference_id'),
            reference_type='manual_adjustment',
            description=f"Manual adjustment: {reason}"
        )

        db.session.add(transaction)
        db.session.commit()

        # Calculate new balance
        new_balance = db.session.query(
            func.coalesce(func.sum(PointsTransaction.points), 0)
        ).filter(
            PointsTransaction.member_id == member_id,
            PointsTransaction.tenant_id == tenant_id,
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        action = 'added' if points > 0 else 'removed'
        return jsonify({
            'success': True,
            'transaction': transaction.to_dict(),
            'new_balance': int(new_balance),
            'message': f'{abs(points)} points {action} for {member.member_number}'
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adjusting points: {e}")
        return jsonify({'error': f'Failed to adjust points: {str(e)}'}), 500


# ==============================================================================
# CUSTOMER-FACING ENDPOINTS (For Extensions)
# ==============================================================================

@points_bp.route('/customer/points', methods=['GET'])
def get_customer_points():
    """
    Get points for authenticated customer (via session token).
    Used by customer account extensions.

    Headers:
        Authorization: Bearer <session_token>
        X-Customer-ID: Shopify customer ID

    Returns:
        Points balance and recent history
    """
    customer_id = request.headers.get('X-Customer-ID')

    if not customer_id:
        return jsonify({'error': 'Missing customer ID'}), 401

    # Find member by Shopify customer ID
    member = Member.query.filter_by(
        shopify_customer_id=str(customer_id)
    ).first()

    if not member:
        return jsonify({
            'is_member': False,
            'message': 'Not enrolled in rewards program',
            'points_balance': 0
        })

    # Get balance
    balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    # Get recent transactions (last 5)
    recent_transactions = PointsTransaction.query.filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.reversed_at.is_(None)
    ).order_by(
        PointsTransaction.created_at.desc()
    ).limit(5).all()

    # Get tier multiplier
    earning_multiplier = 1.0
    if member.tier:
        earning_multiplier = 1.0 + float(member.tier.bonus_rate or 0)

    return jsonify({
        'is_member': True,
        'member_number': member.member_number,
        'points_balance': int(balance),
        'tier': {
            'name': member.tier.name if member.tier else None,
            'earning_multiplier': earning_multiplier
        },
        'recent_activity': [{
            'type': t.transaction_type,
            'points': t.points,
            'description': t.description,
            'date': t.created_at.isoformat() if t.created_at else None
        } for t in recent_transactions]
    })


@points_bp.route('/customer/rewards', methods=['GET'])
def get_customer_rewards():
    """
    Get available rewards for authenticated customer.
    Used by customer account extensions.

    Headers:
        Authorization: Bearer <session_token>
        X-Customer-ID: Shopify customer ID

    Returns:
        List of rewards the customer can redeem based on their balance
    """
    customer_id = request.headers.get('X-Customer-ID')

    if not customer_id:
        return jsonify({'error': 'Missing customer ID'}), 401

    # Find member
    member = Member.query.filter_by(
        shopify_customer_id=str(customer_id)
    ).first()

    if not member:
        return jsonify({
            'is_member': False,
            'message': 'Not enrolled in rewards program',
            'rewards': []
        })

    # Get balance
    balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    # Get active rewards
    now = datetime.utcnow()
    rewards = Reward.query.filter(
        Reward.tenant_id == member.tenant_id,
        Reward.is_active == True,
        (Reward.starts_at.is_(None) | (Reward.starts_at <= now)),
        (Reward.ends_at.is_(None) | (Reward.ends_at >= now)),
        (Reward.stock_quantity.is_(None) | (Reward.stock_quantity > 0))
    ).order_by(Reward.points_cost.asc()).all()

    return jsonify({
        'is_member': True,
        'points_balance': int(balance),
        'rewards': [{
            'id': r.id,
            'name': r.name,
            'description': r.description,
            'points_cost': r.points_cost,
            'reward_type': r.reward_type,
            'reward_value': float(r.reward_value) if r.reward_value else None,
            'image_url': r.image_url,
            'can_redeem': int(balance) >= r.points_cost,
            'in_stock': r.stock_quantity is None or r.stock_quantity > 0
        } for r in rewards]
    })


# ==============================================================================
# EXTENSION PROXY ENDPOINT
# ==============================================================================

@points_bp.route('/extension/data', methods=['POST'])
def get_points_extension_data():
    """
    Get all points data for Customer Account Extension in one call.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        Combined points data for the extension UI
    """
    data = request.json or {}
    customer_id = data.get('customer_id')

    if not customer_id:
        return jsonify({'error': 'Missing customer_id'}), 400

    # Find member
    member = Member.query.filter_by(
        shopify_customer_id=str(customer_id)
    ).first()

    if not member:
        return jsonify({
            'is_member': False,
            'points_enabled': False,
            'message': 'Not enrolled in rewards program'
        })

    # Get balance
    balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    # Get earning stats for the period
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    earned_this_month = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.transaction_type == 'earn',
        PointsTransaction.created_at >= thirty_days_ago,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    # Get recent transactions
    recent = PointsTransaction.query.filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.reversed_at.is_(None)
    ).order_by(
        PointsTransaction.created_at.desc()
    ).limit(5).all()

    # Get available rewards count
    now = datetime.utcnow()
    available_rewards = Reward.query.filter(
        Reward.tenant_id == member.tenant_id,
        Reward.is_active == True,
        Reward.points_cost <= int(balance),
        (Reward.starts_at.is_(None) | (Reward.starts_at <= now)),
        (Reward.ends_at.is_(None) | (Reward.ends_at >= now)),
        (Reward.stock_quantity.is_(None) | (Reward.stock_quantity > 0))
    ).count()

    # Tier info
    tier_info = None
    if member.tier:
        tier_info = {
            'name': member.tier.name,
            'earning_bonus': float(member.tier.bonus_rate * 100) if member.tier.bonus_rate else 0
        }

    return jsonify({
        'is_member': True,
        'points_enabled': True,
        'member_number': member.member_number,
        'points': {
            'balance': int(balance),
            'earned_this_month': int(earned_this_month),
            'available_rewards': available_rewards
        },
        'tier': tier_info,
        'recent_activity': [{
            'type': t.transaction_type,
            'points': t.points,
            'description': t.description,
            'source': t.source,
            'date': t.created_at.isoformat() if t.created_at else None
        } for t in recent]
    })
