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


@customer_account_bp.route('/extension/badges', methods=['POST'])
def get_extension_badges():
    """
    Get badges data for Customer Account Extension.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        All badges with earned status and progress for the customer
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
            'badges': [],
            'message': 'Not enrolled in rewards program'
        })

    # Import gamification models and service
    from ..models.gamification import Badge, MemberBadge
    from ..services.gamification_service import GamificationService

    # Get gamification service
    service = GamificationService(member.tenant_id)

    # Get all active badges
    all_badges = Badge.query.filter_by(
        tenant_id=member.tenant_id,
        is_active=True
    ).order_by(Badge.display_order).all()

    # Get member's earned badges
    earned_badge_ids = {
        mb.badge_id for mb in MemberBadge.query.filter_by(member_id=member.id).all()
    }

    # Get earned badges with dates
    earned_badges_info = {
        mb.badge_id: mb.earned_at
        for mb in MemberBadge.query.filter_by(member_id=member.id).all()
    }

    # Get member stats for progress calculation
    member_stats = service._get_member_stats(member)

    # Build badge list with progress
    badges_data = []
    for badge in all_badges:
        # Skip secret badges that haven't been earned
        if badge.is_secret and badge.id not in earned_badge_ids:
            continue

        is_earned = badge.id in earned_badge_ids
        earned_at = earned_badges_info.get(badge.id)

        # Calculate progress
        current_progress = service._get_badge_progress_value(badge.criteria_type, member_stats)
        progress_max = badge.criteria_value
        progress_percentage = min(100, int((current_progress / progress_max) * 100)) if progress_max > 0 else 0

        badges_data.append({
            'id': badge.id,
            'name': badge.name,
            'description': badge.description,
            'icon': badge.icon,
            'color': badge.color,
            'criteria_type': badge.criteria_type,
            'criteria_value': badge.criteria_value,
            'points_reward': badge.points_reward,
            'is_earned': is_earned,
            'earned_at': earned_at.isoformat() if earned_at else None,
            'progress': current_progress if not is_earned else progress_max,
            'progress_max': progress_max,
            'progress_percentage': 100 if is_earned else progress_percentage,
        })

    # Separate earned and locked badges
    earned_badges = [b for b in badges_data if b['is_earned']]
    locked_badges = [b for b in badges_data if not b['is_earned']]

    return jsonify({
        'is_member': True,
        'total_badges': len(badges_data),
        'earned_count': len(earned_badges),
        'earned_badges': earned_badges,
        'locked_badges': locked_badges,
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


@customer_account_bp.route('/extension/badges/newly-earned', methods=['POST'])
def get_newly_earned_badges():
    """
    Get badges that have been earned but not yet shown to the customer.
    Used to trigger the achievement celebration modal.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        List of newly earned badges that haven't been shown yet
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
            'newly_earned_badges': [],
            'message': 'Not enrolled in rewards program'
        })

    # Import gamification models
    from ..models.gamification import Badge, MemberBadge

    # Get unnotified badges (earned but not yet shown)
    unnotified_member_badges = MemberBadge.query.filter_by(
        member_id=member.id,
        notified=False
    ).all()

    newly_earned = []
    for mb in unnotified_member_badges:
        badge = Badge.query.get(mb.badge_id)
        if badge:
            newly_earned.append({
                'id': badge.id,
                'member_badge_id': mb.id,
                'name': badge.name,
                'description': badge.description,
                'icon': badge.icon,
                'color': badge.color,
                'points_reward': badge.points_reward,
                'credit_reward': float(badge.credit_reward) if badge.credit_reward else 0,
                'earned_at': mb.earned_at.isoformat() if mb.earned_at else None,
            })

    return jsonify({
        'is_member': True,
        'newly_earned_badges': newly_earned,
        'count': len(newly_earned),
    })


@customer_account_bp.route('/extension/badges/mark-notified', methods=['POST'])
def mark_badges_notified():
    """
    Mark badges as notified after showing the celebration modal.

    Request body:
        customer_id: Shopify customer ID
        badge_ids: List of badge IDs to mark as notified (optional, marks all if not provided)

    Returns:
        Success status
    """
    data = request.json or {}
    customer_id = data.get('customer_id')
    badge_ids = data.get('badge_ids')  # Optional list of specific badge IDs

    if not customer_id:
        return jsonify({'error': 'Missing customer_id'}), 400

    # Find member
    member = Member.query.filter_by(
        shopify_customer_id=str(customer_id)
    ).first()

    if not member:
        return jsonify({'error': 'Not enrolled in rewards program'}), 404

    # Import gamification model
    from ..models.gamification import MemberBadge

    try:
        # Mark specified badges or all unnotified badges as notified
        query = MemberBadge.query.filter_by(
            member_id=member.id,
            notified=False
        )

        if badge_ids:
            query = query.filter(MemberBadge.badge_id.in_(badge_ids))

        updated_count = query.update({'notified': True}, synchronize_session='fetch')
        db.session.commit()

        return jsonify({
            'success': True,
            'badges_marked': updated_count,
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking badges notified: {e}")
        return jsonify({'error': f'Failed to mark badges: {str(e)}'}), 500


# ==================== Milestone Celebration Endpoints ====================

@customer_account_bp.route('/extension/milestones', methods=['POST'])
def get_extension_milestones():
    """
    Get milestones data for Customer Account Extension.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        All milestones with achieved status and progress for the customer
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
            'milestones': [],
            'message': 'Not enrolled in rewards program'
        })

    # Import gamification models and service
    from ..models.gamification import Milestone, MemberMilestone
    from ..services.gamification_service import GamificationService

    # Get gamification service
    service = GamificationService(member.tenant_id)

    # Get all active milestones
    all_milestones = Milestone.query.filter_by(
        tenant_id=member.tenant_id,
        is_active=True
    ).order_by(Milestone.threshold).all()

    # Get member's achieved milestones
    achieved_milestone_ids = {
        mm.milestone_id for mm in MemberMilestone.query.filter_by(member_id=member.id).all()
    }

    # Get achieved milestones with dates
    achieved_milestones_info = {
        mm.milestone_id: mm.achieved_at
        for mm in MemberMilestone.query.filter_by(member_id=member.id).all()
    }

    # Get member stats for progress calculation
    member_stats = service._get_member_stats(member)

    # Build milestone list with progress
    milestones_data = []
    for milestone in all_milestones:
        is_achieved = milestone.id in achieved_milestone_ids
        achieved_at = achieved_milestones_info.get(milestone.id)

        # Calculate progress
        current_progress = service._get_milestone_value(milestone.milestone_type, member_stats)
        progress_max = milestone.threshold
        progress_percentage = min(100, int((current_progress / progress_max) * 100)) if progress_max > 0 else 0

        milestones_data.append({
            'id': milestone.id,
            'name': milestone.name,
            'description': milestone.description,
            'milestone_type': milestone.milestone_type,
            'threshold': milestone.threshold,
            'points_reward': milestone.points_reward,
            'credit_reward': float(milestone.credit_reward) if milestone.credit_reward else 0,
            'celebration_message': milestone.celebration_message,
            'is_achieved': is_achieved,
            'achieved_at': achieved_at.isoformat() if achieved_at else None,
            'progress': current_progress if not is_achieved else progress_max,
            'progress_max': progress_max,
            'progress_percentage': 100 if is_achieved else progress_percentage,
        })

    # Separate achieved and upcoming milestones
    achieved_milestones = [m for m in milestones_data if m['is_achieved']]
    upcoming_milestones = [m for m in milestones_data if not m['is_achieved']]

    return jsonify({
        'is_member': True,
        'total_milestones': len(milestones_data),
        'achieved_count': len(achieved_milestones),
        'achieved_milestones': achieved_milestones,
        'upcoming_milestones': upcoming_milestones,
    })


@customer_account_bp.route('/extension/milestones/newly-achieved', methods=['POST'])
def get_newly_achieved_milestones():
    """
    Get milestones that have been achieved but not yet shown to the customer.
    Used to trigger the milestone celebration modal.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        List of newly achieved milestones that haven't been shown yet
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
            'newly_achieved_milestones': [],
            'message': 'Not enrolled in rewards program'
        })

    # Import gamification models
    from ..models.gamification import Milestone, MemberMilestone

    # Get unnotified milestones (achieved but not yet shown)
    unnotified_member_milestones = MemberMilestone.query.filter_by(
        member_id=member.id,
        notified=False
    ).all()

    newly_achieved = []
    for mm in unnotified_member_milestones:
        milestone = Milestone.query.get(mm.milestone_id)
        if milestone:
            newly_achieved.append({
                'id': milestone.id,
                'member_milestone_id': mm.id,
                'name': milestone.name,
                'description': milestone.description,
                'milestone_type': milestone.milestone_type,
                'threshold': milestone.threshold,
                'points_reward': milestone.points_reward,
                'credit_reward': float(milestone.credit_reward) if milestone.credit_reward else 0,
                'celebration_message': milestone.celebration_message,
                'achieved_at': mm.achieved_at.isoformat() if mm.achieved_at else None,
            })

    return jsonify({
        'is_member': True,
        'newly_achieved_milestones': newly_achieved,
        'count': len(newly_achieved),
    })


@customer_account_bp.route('/extension/milestones/mark-notified', methods=['POST'])
def mark_milestones_notified():
    """
    Mark milestones as notified after showing the celebration modal.

    Request body:
        customer_id: Shopify customer ID
        milestone_ids: List of milestone IDs to mark as notified (optional, marks all if not provided)

    Returns:
        Success status
    """
    data = request.json or {}
    customer_id = data.get('customer_id')
    milestone_ids = data.get('milestone_ids')  # Optional list of specific milestone IDs

    if not customer_id:
        return jsonify({'error': 'Missing customer_id'}), 400

    # Find member
    member = Member.query.filter_by(
        shopify_customer_id=str(customer_id)
    ).first()

    if not member:
        return jsonify({'error': 'Not enrolled in rewards program'}), 404

    # Import gamification model
    from ..models.gamification import MemberMilestone

    try:
        # Mark specified milestones or all unnotified milestones as notified
        query = MemberMilestone.query.filter_by(
            member_id=member.id,
            notified=False
        )

        if milestone_ids:
            query = query.filter(MemberMilestone.milestone_id.in_(milestone_ids))

        updated_count = query.update({'notified': True}, synchronize_session='fetch')
        db.session.commit()

        return jsonify({
            'success': True,
            'milestones_marked': updated_count,
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking milestones notified: {e}")
        return jsonify({'error': f'Failed to mark milestones: {str(e)}'}), 500


@customer_account_bp.route('/extension/milestones/history', methods=['POST'])
def get_milestone_history():
    """
    Get member's milestone achievement history.

    Request body:
        customer_id: Shopify customer ID

    Returns:
        List of achieved milestones with dates
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
            'history': [],
            'message': 'Not enrolled in rewards program'
        })

    # Import gamification models
    from ..models.gamification import Milestone, MemberMilestone

    # Get all achieved milestones for this member
    achieved = MemberMilestone.query.filter_by(
        member_id=member.id
    ).order_by(MemberMilestone.achieved_at.desc()).all()

    history = []
    for mm in achieved:
        milestone = Milestone.query.get(mm.milestone_id)
        if milestone:
            history.append({
                'id': milestone.id,
                'name': milestone.name,
                'description': milestone.description,
                'milestone_type': milestone.milestone_type,
                'threshold': milestone.threshold,
                'points_reward': milestone.points_reward,
                'credit_reward': float(milestone.credit_reward) if milestone.credit_reward else 0,
                'celebration_message': milestone.celebration_message,
                'achieved_at': mm.achieved_at.isoformat() if mm.achieved_at else None,
            })

    return jsonify({
        'is_member': True,
        'history': history,
        'total_achieved': len(history),
    })


# ==================== Nudge Notification Endpoints ====================

@customer_account_bp.route('/extension/nudges', methods=['POST'])
def get_extension_nudges():
    """
    Get pending nudge notifications for Customer Account Extension.

    Shows the same nudge messages as would be sent via email, but displayed
    in-app for immediate visibility.

    Request body:
        customer_id: Shopify customer ID
        shop: Shop domain

    Returns:
        List of pending nudge notifications for the customer
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
            'nudges': [],
            'message': 'Not enrolled in rewards program'
        })

    # Import nudge models and service
    from ..models.nudge_sent import NudgeSent
    from ..models.nudge_config import NudgeConfig, NudgeType
    from ..services.nudges_service import NudgesService

    # Get nudge service
    nudge_service = NudgesService(member.tenant_id)

    # Get applicable nudges for this member
    applicable_nudges = nudge_service.get_nudges_for_member(member.id)

    # Build the nudge notifications list
    notifications = []

    for nudge in applicable_nudges:
        nudge_type = nudge.get('nudge_type')
        notification = _build_nudge_notification(nudge, member, nudge_service)
        if notification:
            notifications.append(notification)

    # Sort by priority (points_expiring most urgent)
    priority_order = {
        'points_expiring': 0,
        'tier_upgrade_near': 1,
        'tier_progress': 2,
        'trade_in_reminder': 3,
        'inactive_member': 4,
        'points_milestone': 5,
    }
    notifications.sort(key=lambda x: priority_order.get(x.get('nudge_type'), 99))

    # Limit to top 3 most important nudges
    notifications = notifications[:3]

    return jsonify({
        'is_member': True,
        'nudges': notifications,
        'count': len(notifications),
    })


def _build_nudge_notification(nudge: dict, member, nudge_service) -> dict:
    """
    Build a notification object from a nudge data dict.

    Args:
        nudge: The nudge data from NudgesService
        member: The Member instance
        nudge_service: The NudgesService instance

    Returns:
        A notification dict with title, message, action_text, and action_url
    """
    from ..models.tenant import Tenant

    nudge_type = nudge.get('nudge_type')
    tenant = Tenant.query.get(member.tenant_id)
    shop_url = f"https://{tenant.shop_domain}" if tenant else ""

    # Build notification based on nudge type
    if nudge_type == 'points_expiring':
        expiring_points = nudge.get('expiring_points', 0)
        days_until = nudge.get('days_until_expiry', 0)

        if days_until <= 1:
            urgency = 'critical'
            title = 'Points Expiring Tomorrow!'
        elif days_until <= 7:
            urgency = 'warning'
            title = f'Points Expiring in {days_until} Days'
        else:
            urgency = 'info'
            title = f'Points Expiring Soon'

        return {
            'id': f"nudge_points_expiring_{member.id}",
            'nudge_type': nudge_type,
            'urgency': urgency,
            'title': title,
            'message': f"You have {expiring_points:,} points expiring soon. Use them before they're gone!",
            'action_text': 'Redeem Now',
            'action_tab': 'rewards',
            'icon': 'clock',
            'dismissable': True,
        }

    elif nudge_type == 'tier_upgrade_near':
        next_tier = nudge.get('next_tier', {})
        progress = nudge.get('progress_percent', 0)
        points_needed = nudge.get('points_needed', 0)

        return {
            'id': f"nudge_tier_upgrade_{member.id}",
            'nudge_type': nudge_type,
            'urgency': 'success' if progress >= 95 else 'info',
            'title': f"You're {int(progress)}% to {next_tier.get('name', 'Next Tier')}!",
            'message': f"Just {points_needed:,} more points to unlock better rewards and benefits.",
            'action_text': 'View Tier Benefits',
            'action_tab': 'overview',
            'icon': 'star',
            'dismissable': True,
        }

    elif nudge_type == 'tier_progress':
        next_tier = nudge.get('next_tier', {})
        progress = nudge.get('progress_percent', 0)
        points_needed = nudge.get('points_needed', 0)

        return {
            'id': f"nudge_tier_progress_{member.id}",
            'nudge_type': nudge_type,
            'urgency': 'info',
            'title': f"Almost at {next_tier.get('name', 'Next Tier')}!",
            'message': f"You're {int(progress)}% there! Earn {points_needed:,} more points to level up.",
            'action_text': 'See Progress',
            'action_tab': 'overview',
            'icon': 'trending-up',
            'dismissable': True,
        }

    elif nudge_type == 'trade_in_reminder':
        days_since = nudge.get('days_since_last_trade_in', 0)
        tier_bonus = nudge.get('tier_bonus', 0)

        bonus_text = f" Your tier gives you a {int(tier_bonus)}% bonus!" if tier_bonus > 0 else ""

        return {
            'id': f"nudge_trade_in_{member.id}",
            'nudge_type': nudge_type,
            'urgency': 'info',
            'title': "Time for a Trade-In?",
            'message': f"It's been {days_since} days since your last trade-in. Turn your items into store credit!{bonus_text}",
            'action_text': 'Start Trade-In',
            'action_url': f"{shop_url}/pages/trade-in",
            'icon': 'refresh',
            'dismissable': True,
        }

    elif nudge_type == 'inactive_member':
        days_inactive = nudge.get('days_inactive', 0)
        points_balance = nudge.get('points_balance', 0)

        message = f"We miss you! You have {points_balance:,} points waiting to be redeemed."

        return {
            'id': f"nudge_inactive_{member.id}",
            'nudge_type': nudge_type,
            'urgency': 'info',
            'title': "Welcome Back!",
            'message': message,
            'action_text': 'Browse Rewards',
            'action_tab': 'rewards',
            'icon': 'gift',
            'dismissable': True,
        }

    elif nudge_type == 'points_milestone':
        milestone = nudge.get('milestone', 0)
        current_points = nudge.get('current_points', 0)

        return {
            'id': f"nudge_milestone_{member.id}_{milestone}",
            'nudge_type': nudge_type,
            'urgency': 'success',
            'title': f"Milestone Reached: {milestone:,} Points!",
            'message': f"Congratulations! You've earned over {milestone:,} lifetime points. Keep it up!",
            'action_text': 'View Badges',
            'action_tab': 'badges',
            'icon': 'award',
            'dismissable': True,
        }

    return None


@customer_account_bp.route('/extension/nudges/dismiss', methods=['POST'])
def dismiss_extension_nudge():
    """
    Dismiss a nudge notification in the customer account extension.

    This records that the customer has seen/dismissed the nudge so it
    won't be shown again for the configured cooldown period.

    Request body:
        customer_id: Shopify customer ID
        nudge_id: The ID of the nudge to dismiss (format: nudge_{type}_{member_id})
        nudge_type: The type of nudge being dismissed

    Returns:
        Success status
    """
    data = request.json or {}
    customer_id = data.get('customer_id')
    nudge_id = data.get('nudge_id')
    nudge_type = data.get('nudge_type')

    if not customer_id:
        return jsonify({'error': 'Missing customer_id'}), 400

    if not nudge_type:
        return jsonify({'error': 'Missing nudge_type'}), 400

    # Find member
    member = Member.query.filter_by(
        shopify_customer_id=str(customer_id)
    ).first()

    if not member:
        return jsonify({'error': 'Not enrolled in rewards program'}), 404

    # Import nudge model
    from ..models.nudge_sent import NudgeSent

    try:
        # Record that this nudge was "sent" (shown in-app) and dismissed
        # This uses the same mechanism as email nudges for cooldown tracking
        NudgeSent.record_sent(
            tenant_id=member.tenant_id,
            member_id=member.id,
            nudge_type=nudge_type,
            context_data={
                'dismissed_in_app': True,
                'nudge_id': nudge_id,
            },
            delivery_method='in_app'
        )

        return jsonify({
            'success': True,
            'message': 'Nudge dismissed',
            'nudge_id': nudge_id,
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error dismissing nudge: {e}")
        return jsonify({'error': f'Failed to dismiss nudge: {str(e)}'}), 500


@customer_account_bp.route('/extension/nudges/sync', methods=['POST'])
def sync_nudge_status():
    """
    Sync nudge status between email and in-app notifications.

    Returns the nudge types that have been sent via email so the
    in-app notification can reflect the same status.

    Request body:
        customer_id: Shopify customer ID

    Returns:
        List of nudge types with their last sent timestamps
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
            'nudge_status': {},
        })

    # Import nudge model
    from ..models.nudge_sent import NudgeSent
    from ..models.nudge_config import NudgeType

    # Get recent nudges for this member (last 30 days)
    recent_nudges = NudgeSent.get_member_nudge_history(
        tenant_id=member.tenant_id,
        member_id=member.id,
        limit=50
    )

    # Build status dict by nudge type
    nudge_status = {}
    for nudge in recent_nudges:
        if nudge.nudge_type not in nudge_status:
            nudge_status[nudge.nudge_type] = {
                'last_sent_at': nudge.sent_at.isoformat() if nudge.sent_at else None,
                'delivery_method': nudge.delivery_method,
                'was_opened': nudge.opened_at is not None,
                'was_clicked': nudge.clicked_at is not None,
            }

    return jsonify({
        'is_member': True,
        'nudge_status': nudge_status,
    })
