"""
Customer Account API endpoints.

Public endpoints for customer-facing features like:
- Viewing tier status and benefits
- Trade-in history
- Store credit balance (from Shopify - source of truth)
- Rewards activity

These endpoints are authenticated via Shopify customer token,
not the admin API token.
"""
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func
from ..extensions import db
from ..models import Member, TradeInBatch, MembershipTier, StoreCreditLedger, PointsTransaction
from ..models.referral import Referral, ReferralProgram
from ..models.loyalty_points import Reward, RewardRedemption
from ..services.shopify_client import ShopifyClient

customer_account_bp = Blueprint('customer_account', __name__)


def get_member_from_customer_token() -> tuple:
    """
    Get member from Shopify customer token in Authorization header.

    Returns:
        Tuple of (member, error_response, status_code)
    """
    auth_header = request.headers.get('Authorization', '')
    shop_domain = request.headers.get('X-Shop-Domain', '')

    if not auth_header.startswith('Bearer '):
        return None, {'error': 'Missing authorization'}, 401

    # For now, we'll accept the Shopify customer ID directly
    # In production, this would validate a customer access token
    customer_id = request.headers.get('X-Customer-ID')

    if not customer_id:
        return None, {'error': 'Missing customer ID'}, 401

    # Find member by Shopify customer ID
    member = Member.query.filter_by(
        shopify_customer_id=customer_id
    ).first()

    if not member:
        return None, {'error': 'Not a member'}, 404

    return member, None, None


@customer_account_bp.route('/status', methods=['GET'])
def get_customer_status():
    """
    Get customer's membership status.

    Returns:
        Member tier, balance, and basic stats
    """
    member, error, status = get_member_from_customer_token()
    if error:
        return jsonify(error), status

    tier = member.tier
    tier_info = None
    if tier:
        tier_info = {
            'id': tier.id,
            'name': tier.name,
            'bonus_rate': float(tier.bonus_rate),
            'bonus_percent': float(tier.bonus_rate * 100),
            'benefits': tier.benefits or {}
        }

    # Get store credit balance from Shopify (source of truth)
    store_credit_balance = Decimal('0')
    currency = 'USD'
    if member.shopify_customer_id:
        try:
            shopify_client = ShopifyClient(member.tenant_id)
            balance_info = shopify_client.get_store_credit_balance(member.shopify_customer_id)
            store_credit_balance = Decimal(str(balance_info.get('balance', 0)))
            currency = balance_info.get('currency', 'USD')
        except Exception as e:
            current_app.logger.warning(f"Could not fetch Shopify balance for member {member.id}: {e}")

    return jsonify({
        'member': {
            'member_number': member.member_number,
            'name': member.name,
            'email': member.email,
            'status': member.status,
            'tier': tier_info,
            'member_since': member.membership_start_date.isoformat() if member.membership_start_date else None,
        },
        'stats': {
            'total_trade_ins': member.total_trade_ins or 0,
            'total_trade_value': float(member.total_trade_value or 0),
            'total_bonus_earned': float(member.total_bonus_earned or 0),
        },
        'store_credit': {
            'balance': float(store_credit_balance),
            'currency': currency
        }
    })


@customer_account_bp.route('/tiers', methods=['GET'])
def get_available_tiers():
    """
    Get all available membership tiers.

    Returns:
        List of tiers with benefits
    """
    member, error, status = get_member_from_customer_token()
    if error:
        return jsonify(error), status

    tiers = MembershipTier.query.filter_by(
        tenant_id=member.tenant_id,
        is_active=True
    ).order_by(MembershipTier.display_order).all()

    current_tier_id = member.tier_id

    return jsonify({
        'tiers': [{
            'id': tier.id,
            'name': tier.name,
            'bonus_rate': float(tier.bonus_rate),
            'bonus_percent': float(tier.bonus_rate * 100),
            'benefits': tier.benefits or {},
            'is_current': tier.id == current_tier_id
        } for tier in tiers],
        'current_tier_id': current_tier_id
    })


@customer_account_bp.route('/trade-ins', methods=['GET'])
def get_trade_in_history():
    """
    Get customer's trade-in history.

    Query params:
        limit: Number of records (default 10, max 50)
        offset: Pagination offset

    Returns:
        List of trade-in batches with summary
    """
    member, error, status = get_member_from_customer_token()
    if error:
        return jsonify(error), status

    limit = min(request.args.get('limit', 10, type=int), 50)
    offset = request.args.get('offset', 0, type=int)

    batches = TradeInBatch.query.filter_by(
        member_id=member.id
    ).order_by(
        TradeInBatch.created_at.desc()
    ).offset(offset).limit(limit).all()

    total = TradeInBatch.query.filter_by(member_id=member.id).count()

    return jsonify({
        'trade_ins': [{
            'id': batch.id,
            'batch_reference': batch.batch_reference,
            'status': batch.status,
            'category': batch.category,
            'total_items': batch.total_items,
            'trade_value': float(batch.total_trade_value or 0),
            'bonus_amount': float(batch.bonus_amount or 0),
            'created_at': batch.created_at.isoformat() if batch.created_at else None,
            'completed_at': batch.completed_at.isoformat() if batch.completed_at else None
        } for batch in batches],
        'pagination': {
            'total': total,
            'limit': limit,
            'offset': offset,
            'has_more': offset + limit < total
        }
    })


@customer_account_bp.route('/trade-ins/<batch_reference>', methods=['GET'])
def get_trade_in_detail(batch_reference):
    """
    Get details of a specific trade-in batch.

    Returns:
        Batch details with items
    """
    member, error, status = get_member_from_customer_token()
    if error:
        return jsonify(error), status

    batch = TradeInBatch.query.filter_by(
        member_id=member.id,
        batch_reference=batch_reference
    ).first()

    if not batch:
        return jsonify({'error': 'Trade-in not found'}), 404

    items = [{
        'id': item.id,
        'product_title': item.product_title,
        'product_sku': item.product_sku,
        'trade_value': float(item.trade_value or 0),
        'market_value': float(item.market_value) if item.market_value else None,
        'listed_date': item.listed_date.isoformat() if item.listed_date else None,
        'sold_date': item.sold_date.isoformat() if item.sold_date else None
    } for item in batch.items]

    return jsonify({
        'batch': {
            'id': batch.id,
            'batch_reference': batch.batch_reference,
            'status': batch.status,
            'category': batch.category,
            'total_items': batch.total_items,
            'trade_value': float(batch.total_trade_value or 0),
            'bonus_amount': float(batch.bonus_amount or 0),
            'created_at': batch.created_at.isoformat() if batch.created_at else None,
            'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
            'notes': batch.notes
        },
        'items': items
    })


@customer_account_bp.route('/activity', methods=['GET'])
def get_activity_feed():
    """
    Get recent activity (trade-ins, credits, tier changes).

    Query params:
        limit: Number of records (default 20, max 100)

    Returns:
        Combined activity feed
    """
    member, error, status = get_member_from_customer_token()
    if error:
        return jsonify(error), status

    limit = min(request.args.get('limit', 20, type=int), 100)

    # Get recent trade-ins
    trade_ins = TradeInBatch.query.filter_by(
        member_id=member.id
    ).order_by(
        TradeInBatch.created_at.desc()
    ).limit(limit).all()

    # Build activity feed
    activities = []

    for batch in trade_ins:
        # Trade-in created
        activities.append({
            'type': 'trade_in_created',
            'date': batch.created_at.isoformat() if batch.created_at else None,
            'data': {
                'batch_reference': batch.batch_reference,
                'item_count': batch.total_items,
                'trade_value': float(batch.total_trade_value or 0),
                'category': batch.category
            }
        })

        # Trade-in completed
        if batch.status == 'completed' and batch.completed_at:
            activities.append({
                'type': 'trade_in_completed',
                'date': batch.completed_at.isoformat(),
                'data': {
                    'batch_reference': batch.batch_reference,
                    'trade_value': float(batch.total_trade_value or 0),
                    'bonus_amount': float(batch.bonus_amount or 0)
                }
            })

    # Sort by date descending
    activities.sort(key=lambda x: x['date'] or '', reverse=True)

    return jsonify({
        'activities': activities[:limit]
    })


# ==================== Proxy Endpoint for Customer Account Extension ====================
# This endpoint is called by the Shopify Customer Account Extension

@customer_account_bp.route('/extension/data', methods=['POST'])
def get_extension_data():
    """
    Get all data needed for the Customer Account Extension in one call.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        Combined data for the extension UI (member info, stats, trade-ins, referrals)
    """
    data = request.json or {}
    customer_id = data.get('customer_id')
    shop = data.get('shop')

    if not customer_id:
        return jsonify({'error': 'Missing customer_id'}), 400

    # Find member
    member = Member.query.filter_by(
        shopify_customer_id=str(customer_id)
    ).first()

    if not member:
        return jsonify({
            'is_member': False,
            'message': 'Not enrolled in rewards program'
        })

    # Get tier info
    tier = member.tier
    tier_info = None
    if tier:
        tier_info = {
            'name': tier.name,
            'bonus_percent': float(tier.bonus_rate * 100),
            'trade_in_bonus_pct': float(tier.trade_in_bonus_pct or 0),
            'purchase_cashback_pct': float(tier.purchase_cashback_pct or 0),
            'monthly_credit_amount': float(tier.monthly_credit_amount or 0),
            'benefits': tier.benefits or {}
        }

    # Get recent trade-ins
    recent_trade_ins = TradeInBatch.query.filter_by(
        member_id=member.id
    ).order_by(
        TradeInBatch.created_at.desc()
    ).limit(5).all()

    # Get store credit balance from Shopify (source of truth)
    store_credit_balance = Decimal('0')
    if member.shopify_customer_id:
        try:
            shopify_client = ShopifyClient(member.tenant_id)
            balance_info = shopify_client.get_store_credit_balance(member.shopify_customer_id)
            store_credit_balance = Decimal(str(balance_info.get('balance', 0)))
        except Exception as e:
            current_app.logger.warning(f"Could not fetch Shopify balance for member {member.id}: {e}")

    # Get referral data
    referral_data = None
    program = ReferralProgram.query.filter_by(
        tenant_id=member.tenant_id,
        is_active=True
    ).first()

    if program:
        # Get or create referral code for this member
        referral = Referral.query.filter_by(
            member_id=member.id,
            program_id=program.id
        ).first()

        if not referral:
            import random
            import string
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            referral = Referral(
                member_id=member.id,
                program_id=program.id,
                referral_code=code,
                created_at=datetime.utcnow()
            )
            db.session.add(referral)
            db.session.commit()

        # Count successful referrals
        successful_referrals = Referral.query.filter(
            Referral.referred_by_id == member.id,
            Referral.status == 'completed'
        ).count()

        # Calculate referral rewards earned
        referral_rewards = db.session.query(
            db.func.sum(StoreCreditLedger.amount)
        ).filter(
            StoreCreditLedger.member_id == member.id,
            StoreCreditLedger.source_type == 'referral'
        ).scalar() or Decimal('0')

        # Build share URL
        from ..models.tenant import Tenant
        tenant = Tenant.query.get(member.tenant_id)
        shop_domain = tenant.shop_domain if tenant else shop
        share_url = f"https://{shop_domain}?ref={referral.referral_code}"

        referral_data = {
            'program_active': True,
            'referral_code': referral.referral_code,
            'share_url': share_url,
            'referral_count': successful_referrals,
            'referral_earnings': float(referral_rewards),
            'rewards': {
                'referrer_amount': float(program.referrer_reward_amount),
                'referred_amount': float(program.referred_reward_amount),
                'reward_type': program.reward_type
            },
            'program': {
                'name': program.name,
                'description': program.description
            }
        }

    # ========== POINTS DATA ==========
    # Get points balance from PointsTransaction
    points_balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    # Get points earned this month
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    earned_this_month = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.transaction_type == 'earn',
        PointsTransaction.created_at >= thirty_days_ago,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    # Get recent points activity
    recent_points_activity = PointsTransaction.query.filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.reversed_at.is_(None)
    ).order_by(
        PointsTransaction.created_at.desc()
    ).limit(10).all()

    # Get available rewards count
    now = datetime.utcnow()
    available_rewards_count = Reward.query.filter(
        Reward.tenant_id == member.tenant_id,
        Reward.is_active == True,
        Reward.points_cost <= int(points_balance),
        (Reward.starts_at.is_(None) | (Reward.starts_at <= now)),
        (Reward.ends_at.is_(None) | (Reward.ends_at >= now)),
        (Reward.stock_quantity.is_(None) | (Reward.stock_quantity > 0))
    ).count()

    # Calculate tier progress (points to next tier)
    all_tiers = MembershipTier.query.filter_by(
        tenant_id=member.tenant_id,
        is_active=True
    ).order_by(MembershipTier.display_order).all()

    next_tier = None
    points_to_next_tier = 0
    tier_progress = 0

    if tier and all_tiers:
        current_tier_index = next((i for i, t in enumerate(all_tiers) if t.id == tier.id), -1)
        if current_tier_index >= 0 and current_tier_index < len(all_tiers) - 1:
            next_tier = all_tiers[current_tier_index + 1]
            # For simplicity, assume tier thresholds based on monthly price * 100 points
            # In production, you'd have explicit tier thresholds in the model
            next_tier_threshold = int((next_tier.monthly_price or 0) * 100)
            current_tier_threshold = int((tier.monthly_price or 0) * 100)
            if next_tier_threshold > current_tier_threshold:
                points_to_next_tier = max(0, next_tier_threshold - int(member.lifetime_points_earned or 0))
                tier_progress = min(1.0, (member.lifetime_points_earned or 0) / next_tier_threshold) if next_tier_threshold > 0 else 0

    points_data = {
        'balance': int(points_balance),
        'earned_this_month': int(earned_this_month),
        'available_rewards': available_rewards_count,
        'lifetime_earned': member.lifetime_points_earned or 0,
        'lifetime_spent': member.lifetime_points_spent or 0,
    }

    recent_activity = [{
        'type': t.transaction_type,
        'points': t.points,
        'description': t.description,
        'source': t.source,
        'date': t.created_at.isoformat() if t.created_at else None
    } for t in recent_points_activity]

    tier_progress_data = None
    if next_tier:
        tier_progress_data = {
            'next_tier_name': next_tier.name,
            'points_to_next_tier': points_to_next_tier,
            'progress': tier_progress,
        }

    return jsonify({
        'is_member': True,
        'member': {
            'id': member.id,
            'member_number': member.member_number,
            'name': member.name,
            'tier': tier_info,
            'member_since': member.membership_start_date.isoformat() if member.membership_start_date else None,
        },
        'stats': {
            'total_trade_ins': member.total_trade_ins or 0,
            'total_trade_value': float(member.total_trade_value or 0),
            'total_bonus_earned': float(member.total_bonus_earned or 0),
            'store_credit_balance': float(store_credit_balance)
        },
        'points': points_data,
        'recent_activity': recent_activity,
        'tier_progress': tier_progress_data,
        'recent_trade_ins': [{
            'batch_reference': batch.batch_reference,
            'status': batch.status,
            'trade_value': float(batch.total_trade_value or 0),
            'bonus_amount': float(batch.bonus_amount or 0),
            'created_at': batch.created_at.isoformat() if batch.created_at else None
        } for batch in recent_trade_ins],
        'referral': referral_data
    })


# ==================== Referral Endpoints ====================

@customer_account_bp.route('/referral', methods=['GET'])
def get_customer_referral():
    """
    Get customer's referral code and stats.

    Returns:
        Referral code, share URL, and referral stats
    """
    member, error, status = get_member_from_customer_token()
    if error:
        return jsonify(error), status

    # Get active referral program
    program = ReferralProgram.query.filter_by(
        tenant_id=member.tenant_id,
        is_active=True
    ).first()

    if not program:
        return jsonify({
            'program_active': False,
            'message': 'Referral program is not currently active'
        })

    # Get or create referral code
    referral = Referral.query.filter_by(
        member_id=member.id,
        program_id=program.id
    ).first()

    if not referral:
        # Generate referral code for this member
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        referral = Referral(
            member_id=member.id,
            program_id=program.id,
            referral_code=code,
            created_at=datetime.utcnow()
        )
        db.session.add(referral)
        db.session.commit()

    # Count successful referrals
    successful_referrals = Referral.query.filter(
        Referral.referred_by_id == member.id,
        Referral.status == 'completed'
    ).count()

    # Calculate total rewards earned
    total_rewards = db.session.query(
        db.func.sum(StoreCreditLedger.amount)
    ).filter(
        StoreCreditLedger.member_id == member.id,
        StoreCreditLedger.source_type == 'referral'
    ).scalar() or Decimal('0')

    # Build share URL
    from ..models.tenant import Tenant
    tenant = Tenant.query.get(member.tenant_id)
    shop_domain = tenant.shop_domain if tenant else ''
    share_url = f"https://{shop_domain}?ref={referral.referral_code}"

    return jsonify({
        'program_active': True,
        'referral_code': referral.referral_code,
        'share_url': share_url,
        'rewards': {
            'referrer_reward': float(program.referrer_reward_amount),
            'referred_reward': float(program.referred_reward_amount),
            'reward_type': program.reward_type
        },
        'stats': {
            'successful_referrals': successful_referrals,
            'total_rewards_earned': float(total_rewards)
        },
        'program': {
            'name': program.name,
            'description': program.description
        }
    })


@customer_account_bp.route('/referral/share', methods=['POST'])
def track_referral_share():
    """
    Track when a customer shares their referral link.
    Used for analytics.

    Request body:
        platform: Where they shared (e.g., 'email', 'facebook', 'twitter', 'copy')

    Returns:
        Success confirmation
    """
    member, error, status = get_member_from_customer_token()
    if error:
        return jsonify(error), status

    data = request.json or {}
    platform = data.get('platform', 'unknown')

    # Log the share (for analytics)
    current_app.logger.info(f"Referral share: member={member.id}, platform={platform}")

    # Could add to a shares table for detailed analytics
    # For now, just acknowledge

    return jsonify({
        'success': True,
        'message': 'Share tracked'
    })


@customer_account_bp.route('/extension/referral', methods=['POST'])
def get_referral_extension_data():
    """
    Get referral data for Customer Account Extension.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        Referral program info and customer's referral data
    """
    data = request.json or {}
    customer_id = data.get('customer_id')
    shop = data.get('shop')

    if not customer_id:
        return jsonify({'error': 'Missing customer_id'}), 400

    # Find member
    member = Member.query.filter_by(
        shopify_customer_id=str(customer_id)
    ).first()

    if not member:
        return jsonify({
            'is_member': False,
            'program_active': False,
            'message': 'Not enrolled in rewards program'
        })

    # Get active referral program
    program = ReferralProgram.query.filter_by(
        tenant_id=member.tenant_id,
        is_active=True
    ).first()

    if not program:
        return jsonify({
            'is_member': True,
            'program_active': False,
            'message': 'Referral program is not currently active'
        })

    # Get or create referral code
    referral = Referral.query.filter_by(
        member_id=member.id,
        program_id=program.id
    ).first()

    if not referral:
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        referral = Referral(
            member_id=member.id,
            program_id=program.id,
            referral_code=code,
            created_at=datetime.utcnow()
        )
        db.session.add(referral)
        db.session.commit()

    # Count successful referrals
    successful_referrals = Referral.query.filter(
        Referral.referred_by_id == member.id,
        Referral.status == 'completed'
    ).count()

    # Get recent referrals
    recent_referrals = Referral.query.filter(
        Referral.referred_by_id == member.id
    ).order_by(Referral.created_at.desc()).limit(5).all()

    # Build share URL
    from ..models.tenant import Tenant
    tenant = Tenant.query.get(member.tenant_id)
    shop_domain = tenant.shop_domain if tenant else shop
    share_url = f"https://{shop_domain}?ref={referral.referral_code}"

    return jsonify({
        'is_member': True,
        'program_active': True,
        'member_name': member.name or member.email.split('@')[0],
        'referral_code': referral.referral_code,
        'share_url': share_url,
        'rewards': {
            'referrer_amount': float(program.referrer_reward_amount),
            'referred_amount': float(program.referred_reward_amount),
            'reward_type': program.reward_type
        },
        'stats': {
            'total_referrals': successful_referrals,
            'pending_referrals': len([r for r in recent_referrals if r.status == 'pending'])
        },
        'recent_referrals': [{
            'name': 'Friend',  # Privacy - don't expose actual names
            'status': r.status,
            'created_at': r.created_at.isoformat() if r.created_at else None
        } for r in recent_referrals],
        'program': {
            'name': program.name,
            'description': program.description or f"Share your code and you both get ${program.referrer_reward_amount} credit!"
        }
    })


# ==================== Customer Rewards Endpoints ====================

@customer_account_bp.route('/extension/rewards', methods=['POST'])
def get_extension_rewards():
    """
    Get available rewards for Customer Account Extension.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        List of rewards the customer can redeem
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
            'rewards': [],
            'message': 'Not enrolled in rewards program'
        })

    # Get points balance
    points_balance = db.session.query(
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
        (Reward.ends_at.is_(None) | (Reward.ends_at >= now))
    ).order_by(Reward.points_cost.asc()).all()

    # Filter and annotate rewards
    result_rewards = []
    for reward in rewards:
        # Check tier restriction
        tier_ids = reward.tier_ids if hasattr(reward, 'tier_ids') and reward.tier_ids else None
        if tier_ids and member.tier_id not in tier_ids:
            continue

        # Check stock
        in_stock = reward.stock_quantity is None or reward.stock_quantity > 0

        # Check member's usage limit
        uses_remaining = None
        if reward.max_uses_per_member:
            member_redemptions = RewardRedemption.query.filter_by(
                reward_id=reward.id,
                member_id=member.id
            ).count()
            uses_remaining = max(0, reward.max_uses_per_member - member_redemptions)

        can_redeem = (
            int(points_balance) >= reward.points_cost and
            in_stock and
            (uses_remaining is None or uses_remaining > 0)
        )

        result_rewards.append({
            'id': reward.id,
            'name': reward.name,
            'description': reward.description,
            'points_cost': reward.points_cost,
            'reward_type': reward.reward_type,
            'reward_value': float(reward.reward_value) if hasattr(reward, 'reward_value') and reward.reward_value else None,
            'image_url': reward.image_url,
            'can_redeem': can_redeem,
            'in_stock': in_stock,
            'uses_remaining': uses_remaining,
            'points_needed': max(0, reward.points_cost - int(points_balance))
        })

    return jsonify({
        'is_member': True,
        'points_balance': int(points_balance),
        'rewards': result_rewards
    })


@customer_account_bp.route('/extension/rewards/<int:reward_id>/redeem', methods=['POST'])
def redeem_extension_reward(reward_id):
    """
    Redeem a reward from Customer Account Extension.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        Redemption details including discount code if applicable
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
        return jsonify({'error': 'Not enrolled in rewards program'}), 404

    # Get reward
    reward = Reward.query.filter_by(
        id=reward_id,
        tenant_id=member.tenant_id
    ).first()

    if not reward:
        return jsonify({'error': 'Reward not found'}), 404

    # Validate reward is active and within date range
    now = datetime.utcnow()
    if not reward.is_active:
        return jsonify({'error': 'This reward is no longer available'}), 400

    if reward.starts_at and reward.starts_at > now:
        return jsonify({'error': 'This reward is not yet available'}), 400

    if reward.ends_at and reward.ends_at < now:
        return jsonify({'error': 'This reward has expired'}), 400

    # Check tier restriction
    tier_ids = reward.tier_ids if hasattr(reward, 'tier_ids') and reward.tier_ids else None
    if tier_ids and member.tier_id not in tier_ids:
        return jsonify({'error': 'This reward is not available for your membership tier'}), 403

    # Check stock
    if reward.stock_quantity is not None and reward.stock_quantity <= 0:
        return jsonify({'error': 'This reward is out of stock'}), 400

    # Check member's usage limit
    if reward.max_uses_per_member:
        member_redemptions = RewardRedemption.query.filter_by(
            reward_id=reward_id,
            member_id=member.id
        ).count()
        if member_redemptions >= reward.max_uses_per_member:
            return jsonify({'error': 'You have reached the maximum redemptions for this reward'}), 400

    # Check points balance
    points_balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    if int(points_balance) < reward.points_cost:
        return jsonify({
            'error': 'Insufficient points',
            'points_balance': int(points_balance),
            'points_needed': reward.points_cost
        }), 400

    try:
        # Generate discount code if applicable
        import secrets
        import string
        discount_code = None
        if reward.reward_type in ['discount', 'store_credit', 'free_shipping']:
            prefix = reward.discount_code_prefix if hasattr(reward, 'discount_code_prefix') and reward.discount_code_prefix else 'REWARD'
            random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            discount_code = f"{prefix}-{random_part}"

        # Create points deduction transaction
        points_transaction = PointsTransaction(
            tenant_id=member.tenant_id,
            member_id=member.id,
            points=-reward.points_cost,
            transaction_type='redeem',
            source='reward',
            reference_id=str(reward_id),
            reference_type='reward_redemption',
            description=f"Redeemed: {reward.name}"
        )
        db.session.add(points_transaction)

        # Generate redemption code
        redemption_code = f"RD-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

        # Create redemption record
        redemption = RewardRedemption(
            tenant_id=member.tenant_id,
            member_id=member.id,
            reward_id=reward_id,
            redemption_code=redemption_code,
            points_spent=reward.points_cost,
            status='completed' if reward.reward_type != 'product' else 'pending',
            reward_type=reward.reward_type,
            reward_name=reward.name,
            reward_value=reward.credit_value if hasattr(reward, 'credit_value') else None,
            voucher_code=discount_code,
            voucher_expires_at=datetime.utcnow() + timedelta(days=reward.voucher_valid_days or 30),
            notes=data.get('notes'),
            created_by='customer'
        )
        db.session.add(redemption)

        # Update stock if applicable
        if reward.stock_quantity is not None:
            reward.stock_quantity -= 1
            reward.redeemed_quantity = (reward.redeemed_quantity or 0) + 1

        # Update member points on the Member model
        member.points_balance = (member.points_balance or 0) - reward.points_cost
        member.lifetime_points_spent = (member.lifetime_points_spent or 0) + reward.points_cost

        db.session.commit()

        # Calculate new balance
        new_balance = db.session.query(
            func.coalesce(func.sum(PointsTransaction.points), 0)
        ).filter(
            PointsTransaction.member_id == member.id,
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        response = {
            'success': True,
            'redemption': {
                'id': redemption.id,
                'redemption_code': redemption_code,
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
                response['redemption']['discount_value'] = float(reward.discount_amount or reward.discount_percent or 0)
                response['redemption']['discount_type'] = 'percent' if reward.discount_percent else 'fixed'
            elif reward.reward_type == 'store_credit':
                response['redemption']['credit_amount'] = float(reward.credit_value) if reward.credit_value else None

        return jsonify(response), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error redeeming reward: {e}")
        return jsonify({'error': f'Failed to redeem reward: {str(e)}'}), 500
