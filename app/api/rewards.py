"""
Rewards API endpoints for TradeUp loyalty program.

Handles:
- Rewards catalog management (admin)
- Available rewards listing
- Reward redemption
"""
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify, g, current_app
from sqlalchemy import func, and_
from ..extensions import db
from ..models import Member, PointsTransaction
from ..models.loyalty_points import Reward, RewardRedemption
from ..middleware.shopify_auth import require_shopify_auth

rewards_bp = Blueprint('rewards', __name__)


# ==============================================================================
# REWARDS CATALOG (Admin)
# ==============================================================================

@rewards_bp.route('', methods=['GET'])
@require_shopify_auth
def list_rewards():
    """
    List all rewards for the tenant.

    Query params:
        include_inactive: Include inactive rewards (default false)
        reward_type: Filter by type (discount, product, store_credit, custom)

    Returns:
        List of rewards with redemption stats
    """
    tenant_id = g.tenant_id
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    reward_type = request.args.get('reward_type')

    query = Reward.query.filter_by(tenant_id=tenant_id)

    if not include_inactive:
        query = query.filter(Reward.is_active == True)

    if reward_type:
        query = query.filter(Reward.reward_type == reward_type)

    rewards = query.order_by(Reward.points_cost.asc()).all()

    # Get redemption counts for each reward
    redemption_counts = db.session.query(
        RewardRedemption.reward_id,
        func.count(RewardRedemption.id).label('count')
    ).filter(
        RewardRedemption.tenant_id == tenant_id
    ).group_by(RewardRedemption.reward_id).all()

    counts_map = {r.reward_id: r.count for r in redemption_counts}

    return jsonify({
        'rewards': [{
            **r.to_dict(),
            'redemption_count': counts_map.get(r.id, 0)
        } for r in rewards],
        'count': len(rewards)
    })


@rewards_bp.route('', methods=['POST'])
@require_shopify_auth
def create_reward():
    """
    Create a new reward.

    JSON body:
        name: Reward name (required)
        description: Reward description
        points_cost: Points required to redeem (required)
        reward_type: Type of reward (required) - 'discount', 'product',
                     'store_credit', 'free_shipping', 'custom'
        reward_value: Value amount (for discount/store_credit)
        discount_type: 'percentage' or 'fixed' (for discount type)
        product_id: Shopify product ID (for product type)
        discount_code_prefix: Prefix for generated discount codes
        min_purchase_amount: Minimum purchase to use reward
        max_uses_per_member: Limit per member (null = unlimited)
        stock_quantity: Limited stock (null = unlimited)
        tier_ids: List of tier IDs that can redeem (null = all tiers)
        starts_at: When reward becomes available
        ends_at: When reward expires
        image_url: Reward image URL

    Returns:
        Created reward
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    # Validation
    required = ['name', 'points_cost', 'reward_type']
    for field in required:
        if field not in data or data[field] is None:
            return jsonify({'error': f'{field} is required'}), 400

    valid_reward_types = ['discount', 'product', 'store_credit', 'free_shipping', 'custom']
    if data['reward_type'] not in valid_reward_types:
        return jsonify({'error': f'reward_type must be one of: {valid_reward_types}'}), 400

    try:
        points_cost = int(data['points_cost'])
        if points_cost <= 0:
            return jsonify({'error': 'points_cost must be positive'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'points_cost must be an integer'}), 400

    try:
        reward = Reward(
            tenant_id=tenant_id,
            name=data['name'],
            description=data.get('description'),
            points_cost=points_cost,
            reward_type=data['reward_type'],
            reward_value=Decimal(str(data['reward_value'])) if data.get('reward_value') else None,
            discount_type=data.get('discount_type'),
            product_id=data.get('product_id'),
            discount_code_prefix=data.get('discount_code_prefix'),
            min_purchase_amount=Decimal(str(data['min_purchase_amount'])) if data.get('min_purchase_amount') else None,
            max_uses_per_member=data.get('max_uses_per_member'),
            stock_quantity=data.get('stock_quantity'),
            tier_ids=data.get('tier_ids'),
            is_active=data.get('is_active', True),
            starts_at=datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00')) if data.get('starts_at') else None,
            ends_at=datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00')) if data.get('ends_at') else None,
            image_url=data.get('image_url')
        )

        db.session.add(reward)
        db.session.commit()

        return jsonify({
            'success': True,
            'reward': reward.to_dict(),
            'message': f'Reward "{reward.name}" created'
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating reward: {e}")
        return jsonify({'error': f'Failed to create reward: {str(e)}'}), 500


@rewards_bp.route('/<int:reward_id>', methods=['GET'])
@require_shopify_auth
def get_reward(reward_id):
    """Get a single reward with redemption stats."""
    tenant_id = g.tenant_id

    reward = Reward.query.filter_by(
        id=reward_id,
        tenant_id=tenant_id
    ).first()

    if not reward:
        return jsonify({'error': 'Reward not found'}), 404

    # Get redemption count
    redemption_count = RewardRedemption.query.filter_by(
        reward_id=reward_id,
        tenant_id=tenant_id
    ).count()

    result = reward.to_dict()
    result['redemption_count'] = redemption_count

    return jsonify(result)


@rewards_bp.route('/<int:reward_id>', methods=['PUT'])
@require_shopify_auth
def update_reward(reward_id):
    """
    Update a reward.

    JSON body:
        All fields from create are updatable

    Returns:
        Updated reward
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    reward = Reward.query.filter_by(
        id=reward_id,
        tenant_id=tenant_id
    ).first()

    if not reward:
        return jsonify({'error': 'Reward not found'}), 404

    try:
        # Update fields
        if 'name' in data:
            reward.name = data['name']
        if 'description' in data:
            reward.description = data['description']
        if 'points_cost' in data:
            reward.points_cost = int(data['points_cost'])
        if 'reward_type' in data:
            reward.reward_type = data['reward_type']
        if 'reward_value' in data:
            reward.reward_value = Decimal(str(data['reward_value'])) if data['reward_value'] else None
        if 'discount_type' in data:
            reward.discount_type = data['discount_type']
        if 'product_id' in data:
            reward.product_id = data['product_id']
        if 'discount_code_prefix' in data:
            reward.discount_code_prefix = data['discount_code_prefix']
        if 'min_purchase_amount' in data:
            reward.min_purchase_amount = Decimal(str(data['min_purchase_amount'])) if data['min_purchase_amount'] else None
        if 'max_uses_per_member' in data:
            reward.max_uses_per_member = data['max_uses_per_member']
        if 'stock_quantity' in data:
            reward.stock_quantity = data['stock_quantity']
        if 'tier_ids' in data:
            reward.tier_ids = data['tier_ids']
        if 'is_active' in data:
            reward.is_active = data['is_active']
        if 'starts_at' in data:
            reward.starts_at = datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00')) if data['starts_at'] else None
        if 'ends_at' in data:
            reward.ends_at = datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00')) if data['ends_at'] else None
        if 'image_url' in data:
            reward.image_url = data['image_url']

        reward.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'reward': reward.to_dict(),
            'message': f'Reward "{reward.name}" updated'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating reward: {e}")
        return jsonify({'error': f'Failed to update reward: {str(e)}'}), 500


@rewards_bp.route('/<int:reward_id>', methods=['DELETE'])
@require_shopify_auth
def delete_reward(reward_id):
    """
    Delete a reward.

    Soft delete - sets is_active=False.
    """
    tenant_id = g.tenant_id

    reward = Reward.query.filter_by(
        id=reward_id,
        tenant_id=tenant_id
    ).first()

    if not reward:
        return jsonify({'error': 'Reward not found'}), 404

    # Soft delete
    reward.is_active = False
    reward.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Reward "{reward.name}" deleted'
    })


@rewards_bp.route('/<int:reward_id>/toggle', methods=['POST'])
@require_shopify_auth
def toggle_reward(reward_id):
    """
    Enable or disable a reward.

    Returns:
        Updated reward with new status
    """
    tenant_id = g.tenant_id

    reward = Reward.query.filter_by(
        id=reward_id,
        tenant_id=tenant_id
    ).first()

    if not reward:
        return jsonify({'error': 'Reward not found'}), 404

    reward.is_active = not reward.is_active
    reward.updated_at = datetime.utcnow()
    db.session.commit()

    status = 'enabled' if reward.is_active else 'disabled'
    return jsonify({
        'success': True,
        'reward': reward.to_dict(),
        'message': f'Reward "{reward.name}" {status}'
    })


# ==============================================================================
# AVAILABLE REWARDS (Member-facing)
# ==============================================================================

@rewards_bp.route('/available', methods=['GET'])
@require_shopify_auth
def get_available_rewards():
    """
    Get rewards available to a member, filtered by points balance.

    Query params:
        member_id: Member ID (required)

    Returns:
        List of rewards the member can redeem
    """
    tenant_id = g.tenant_id
    member_id = request.args.get('member_id', type=int)

    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400

    # Verify member
    member = Member.query.filter_by(
        id=member_id,
        tenant_id=tenant_id
    ).first()

    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Get member's points balance
    balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    # Get active rewards
    now = datetime.utcnow()
    query = Reward.query.filter(
        Reward.tenant_id == tenant_id,
        Reward.is_active == True,
        (Reward.starts_at.is_(None) | (Reward.starts_at <= now)),
        (Reward.ends_at.is_(None) | (Reward.ends_at >= now))
    )

    rewards = query.order_by(Reward.points_cost.asc()).all()

    # Filter by tier eligibility and check redemption limits
    available_rewards = []
    for reward in rewards:
        # Check tier restriction
        if reward.tier_ids and member.tier_id not in reward.tier_ids:
            continue

        # Check stock
        in_stock = reward.stock_quantity is None or reward.stock_quantity > 0

        # Check member's usage limit
        uses_remaining = None
        if reward.max_uses_per_member:
            member_redemptions = RewardRedemption.query.filter_by(
                reward_id=reward.id,
                member_id=member_id
            ).count()
            uses_remaining = max(0, reward.max_uses_per_member - member_redemptions)

        can_redeem = (
            int(balance) >= reward.points_cost and
            in_stock and
            (uses_remaining is None or uses_remaining > 0)
        )

        available_rewards.append({
            **reward.to_dict(),
            'can_redeem': can_redeem,
            'in_stock': in_stock,
            'uses_remaining': uses_remaining,
            'points_needed': max(0, reward.points_cost - int(balance))
        })

    return jsonify({
        'member_id': member_id,
        'points_balance': int(balance),
        'rewards': available_rewards,
        'count': len(available_rewards)
    })


# ==============================================================================
# REDEMPTION
# ==============================================================================

@rewards_bp.route('/<int:reward_id>/redeem', methods=['POST'])
@require_shopify_auth
def redeem_reward(reward_id):
    """
    Redeem a reward for a member.

    JSON body:
        member_id: Member ID (required)
        notes: Optional redemption notes

    Returns:
        Redemption details including discount code if applicable
    """
    tenant_id = g.tenant_id
    staff_id = g.staff_id or 'admin'
    data = request.json or {}

    member_id = data.get('member_id')
    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400

    # Get reward
    reward = Reward.query.filter_by(
        id=reward_id,
        tenant_id=tenant_id
    ).first()

    if not reward:
        return jsonify({'error': 'Reward not found'}), 404

    # Get member
    member = Member.query.filter_by(
        id=member_id,
        tenant_id=tenant_id
    ).first()

    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Validate reward is active and within date range
    now = datetime.utcnow()
    if not reward.is_active:
        return jsonify({'error': 'This reward is no longer available'}), 400

    if reward.starts_at and reward.starts_at > now:
        return jsonify({'error': 'This reward is not yet available'}), 400

    if reward.ends_at and reward.ends_at < now:
        return jsonify({'error': 'This reward has expired'}), 400

    # Check tier restriction
    if reward.tier_ids and member.tier_id not in reward.tier_ids:
        return jsonify({'error': 'This reward is not available for your membership tier'}), 403

    # Check stock
    if reward.stock_quantity is not None and reward.stock_quantity <= 0:
        return jsonify({'error': 'This reward is out of stock'}), 400

    # Check member's usage limit
    if reward.max_uses_per_member:
        member_redemptions = RewardRedemption.query.filter_by(
            reward_id=reward_id,
            member_id=member_id
        ).count()
        if member_redemptions >= reward.max_uses_per_member:
            return jsonify({'error': 'You have reached the maximum redemptions for this reward'}), 400

    # Check points balance
    balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member_id,
        PointsTransaction.tenant_id == tenant_id,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    if int(balance) < reward.points_cost:
        return jsonify({
            'error': 'Insufficient points',
            'points_balance': int(balance),
            'points_needed': reward.points_cost
        }), 400

    try:
        # Generate discount code if applicable
        discount_code = None
        if reward.reward_type in ['discount', 'store_credit', 'free_shipping']:
            import secrets
            import string
            prefix = reward.discount_code_prefix or 'REWARD'
            random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            discount_code = f"{prefix}-{random_part}"

            # TODO: Create discount code in Shopify via GraphQL
            # This would call ShopifyClient.create_discount_code()

        # Create points deduction transaction
        points_transaction = PointsTransaction(
            tenant_id=tenant_id,
            member_id=member_id,
            points=-reward.points_cost,
            transaction_type='redeem',
            source='reward',
            reference_id=str(reward_id),
            reference_type='reward_redemption',
            description=f"Redeemed: {reward.name}"
        )
        db.session.add(points_transaction)

        # Create redemption record
        redemption = RewardRedemption(
            tenant_id=tenant_id,
            member_id=member_id,
            reward_id=reward_id,
            points_spent=reward.points_cost,
            discount_code=discount_code,
            status='completed' if reward.reward_type != 'product' else 'pending',
            notes=data.get('notes'),
            redeemed_by=staff_id
        )
        db.session.add(redemption)

        # Update stock if applicable
        if reward.stock_quantity is not None:
            reward.stock_quantity -= 1

        db.session.commit()

        # Calculate new balance
        new_balance = db.session.query(
            func.coalesce(func.sum(PointsTransaction.points), 0)
        ).filter(
            PointsTransaction.member_id == member_id,
            PointsTransaction.tenant_id == tenant_id,
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        response = {
            'success': True,
            'redemption': {
                'id': redemption.id,
                'reward_name': reward.name,
                'reward_type': reward.reward_type,
                'points_spent': reward.points_cost,
                'status': redemption.status,
                'redeemed_at': redemption.created_at.isoformat()
            },
            'new_balance': int(new_balance),
            'message': f'Successfully redeemed "{reward.name}"'
        }

        # Include discount code if generated
        if discount_code:
            response['redemption']['discount_code'] = discount_code
            if reward.reward_type == 'discount':
                response['redemption']['discount_value'] = float(reward.reward_value) if reward.reward_value else None
                response['redemption']['discount_type'] = reward.discount_type
            elif reward.reward_type == 'store_credit':
                response['redemption']['credit_amount'] = float(reward.reward_value) if reward.reward_value else None

        return jsonify(response), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error redeeming reward: {e}")
        return jsonify({'error': f'Failed to redeem reward: {str(e)}'}), 500


@rewards_bp.route('/redemptions', methods=['GET'])
@require_shopify_auth
def list_redemptions():
    """
    List redemption history.

    Query params:
        member_id: Filter by member
        reward_id: Filter by reward
        status: Filter by status (pending, completed, cancelled)
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)

    Returns:
        Paginated list of redemptions
    """
    tenant_id = g.tenant_id

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = RewardRedemption.query.filter_by(tenant_id=tenant_id)

    # Filters
    member_id = request.args.get('member_id', type=int)
    if member_id:
        query = query.filter(RewardRedemption.member_id == member_id)

    reward_id = request.args.get('reward_id', type=int)
    if reward_id:
        query = query.filter(RewardRedemption.reward_id == reward_id)

    status = request.args.get('status')
    if status:
        query = query.filter(RewardRedemption.status == status)

    # Order and paginate
    query = query.order_by(RewardRedemption.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'redemptions': [r.to_dict() for r in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@rewards_bp.route('/redemptions/<int:redemption_id>', methods=['GET'])
@require_shopify_auth
def get_redemption(redemption_id):
    """Get a single redemption with details."""
    tenant_id = g.tenant_id

    redemption = RewardRedemption.query.filter_by(
        id=redemption_id,
        tenant_id=tenant_id
    ).first()

    if not redemption:
        return jsonify({'error': 'Redemption not found'}), 404

    return jsonify(redemption.to_dict())


@rewards_bp.route('/redemptions/<int:redemption_id>/cancel', methods=['POST'])
@require_shopify_auth
def cancel_redemption(redemption_id):
    """
    Cancel a redemption and refund points.

    JSON body:
        reason: Cancellation reason (required)

    Returns:
        Updated redemption and refunded points
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    reason = data.get('reason', '').strip()
    if not reason:
        return jsonify({'error': 'reason is required for cancellation'}), 400

    redemption = RewardRedemption.query.filter_by(
        id=redemption_id,
        tenant_id=tenant_id
    ).first()

    if not redemption:
        return jsonify({'error': 'Redemption not found'}), 404

    if redemption.status == 'cancelled':
        return jsonify({'error': 'Redemption is already cancelled'}), 400

    try:
        # Find the original points transaction
        original_transaction = PointsTransaction.query.filter(
            PointsTransaction.member_id == redemption.member_id,
            PointsTransaction.reference_id == str(redemption.reward_id),
            PointsTransaction.reference_type == 'reward_redemption',
            PointsTransaction.transaction_type == 'redeem',
            PointsTransaction.reversed_at.is_(None)
        ).first()

        if original_transaction:
            # Create refund transaction
            refund_transaction = PointsTransaction(
                tenant_id=tenant_id,
                member_id=redemption.member_id,
                points=redemption.points_spent,  # Positive to add back
                transaction_type='adjustment',
                source='redemption_cancelled',
                reference_id=str(redemption_id),
                reference_type='redemption_refund',
                description=f"Refund for cancelled redemption: {reason}",
                related_transaction_id=original_transaction.id
            )
            db.session.add(refund_transaction)

            # Mark original as reversed
            original_transaction.reversed_at = datetime.utcnow()
            original_transaction.reversed_reason = reason

        # Update redemption status
        redemption.status = 'cancelled'
        redemption.cancelled_at = datetime.utcnow()
        redemption.cancelled_reason = reason

        # Restore stock if applicable
        reward = Reward.query.get(redemption.reward_id)
        if reward and reward.stock_quantity is not None:
            reward.stock_quantity += 1

        db.session.commit()

        # Calculate new balance
        new_balance = db.session.query(
            func.coalesce(func.sum(PointsTransaction.points), 0)
        ).filter(
            PointsTransaction.member_id == redemption.member_id,
            PointsTransaction.tenant_id == tenant_id,
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        return jsonify({
            'success': True,
            'redemption': redemption.to_dict(),
            'points_refunded': redemption.points_spent,
            'new_balance': int(new_balance),
            'message': f'{redemption.points_spent} points refunded'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelling redemption: {e}")
        return jsonify({'error': f'Failed to cancel redemption: {str(e)}'}), 500
