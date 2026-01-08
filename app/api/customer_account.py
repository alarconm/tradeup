"""
Customer Account API endpoints.

Public endpoints for customer-facing features like:
- Viewing tier status and benefits
- Trade-in history
- Store credit balance
- Rewards activity

These endpoints are authenticated via Shopify customer token,
not the admin API token.
"""
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from decimal import Decimal
from ..extensions import db
from ..models import Member, TradeInBatch, MembershipTier, StoreCreditLedger
from ..models.referral import Referral, ReferralProgram

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

    # Calculate store credit balance from ledger
    store_credit_balance = db.session.query(
        db.func.sum(StoreCreditLedger.amount)
    ).filter(
        StoreCreditLedger.member_id == member.id
    ).scalar() or Decimal('0')

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
            'currency': 'USD'
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

    # Calculate store credit balance from ledger
    store_credit_balance = db.session.query(
        db.func.sum(StoreCreditLedger.amount)
    ).filter(
        StoreCreditLedger.member_id == member.id
    ).scalar() or Decimal('0')

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

    return jsonify({
        'is_member': True,
        'member': {
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
