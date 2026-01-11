"""
Referral Program API endpoints.

Handles referral code management, tracking, and rewards.
"""
from flask import Blueprint, request, jsonify, current_app, g
from datetime import datetime
from decimal import Decimal
from ..extensions import db
from ..models.member import Member
from ..models.promotions import StoreCreditLedger, CreditEventType
from ..middleware.shopify_auth import require_shopify_auth

referrals_bp = Blueprint('referrals', __name__)


class ReferralConfig:
    """Default referral program configuration."""
    # Credit amounts
    REFERRER_CREDIT = Decimal('10.00')  # Credit given to the person who referred
    REFEREE_CREDIT = Decimal('5.00')    # Credit given to the new member

    # When credit is granted
    GRANT_ON_SIGNUP = True              # Grant on member creation
    REQUIRE_FIRST_PURCHASE = False      # Or require a purchase first

    # Limits
    MAX_REFERRALS_PER_MONTH = 50        # Prevent abuse


# ==================== ADMIN ENDPOINTS ====================

@referrals_bp.route('/admin/stats', methods=['GET'])
@require_shopify_auth
def get_referral_stats():
    """
    Get referral program statistics for admin dashboard.
    """
    tenant_id = g.tenant_id

    # Total referrals
    total_referrals = db.session.query(db.func.count(Member.id)).filter(
        Member.tenant_id == tenant_id,
        Member.referred_by_id.isnot(None)
    ).scalar() or 0

    # Total credit issued for referrals
    total_referral_credit = db.session.query(
        db.func.sum(StoreCreditLedger.amount)
    ).join(Member, StoreCreditLedger.member_id == Member.id).filter(
        Member.tenant_id == tenant_id,
        StoreCreditLedger.event_type == 'referral_bonus'
    ).scalar() or Decimal('0')

    # Top referrers
    top_referrers = db.session.query(
        Member.id,
        Member.name,
        Member.email,
        Member.referral_code,
        Member.referral_count,
        Member.referral_earnings
    ).filter(
        Member.tenant_id == tenant_id,
        Member.referral_count > 0
    ).order_by(Member.referral_count.desc()).limit(10).all()

    # Recent referrals - create alias once and reuse
    ReferrerAlias = db.aliased(Member)
    recent = db.session.query(
        Member.id,
        Member.member_number,
        Member.name.label('referee_name'),
        Member.email.label('referee_email'),
        Member.created_at,
        ReferrerAlias.member_number.label('referrer_member_number')
    ).outerjoin(
        ReferrerAlias,
        Member.referred_by_id == ReferrerAlias.id
    ).filter(
        Member.tenant_id == tenant_id,
        Member.referred_by_id.isnot(None)
    ).order_by(Member.created_at.desc()).limit(10).all()

    return jsonify({
        'stats': {
            'total_referrals': total_referrals,
            'total_credit_issued': float(total_referral_credit),
            'referrer_reward': float(ReferralConfig.REFERRER_CREDIT),
            'referee_reward': float(ReferralConfig.REFEREE_CREDIT)
        },
        'top_referrers': [{
            'id': r.id,
            'name': r.name,
            'email': r.email,
            'referral_code': r.referral_code,
            'referral_count': r.referral_count or 0,
            'referral_earnings': float(r.referral_earnings or 0)
        } for r in top_referrers],
        'recent_referrals': [{
            'id': r.id,
            'member_number': r.member_number,
            'name': r.referee_name,
            'referred_by': r.referrer_member_number,
            'created_at': r.created_at.isoformat() if r.created_at else None
        } for r in recent]
    })


@referrals_bp.route('/admin/config', methods=['GET'])
@require_shopify_auth
def get_referral_config():
    """
    Get referral program configuration.
    """
    return jsonify({
        'config': {
            'referrer_credit': float(ReferralConfig.REFERRER_CREDIT),
            'referee_credit': float(ReferralConfig.REFEREE_CREDIT),
            'grant_on_signup': ReferralConfig.GRANT_ON_SIGNUP,
            'require_first_purchase': ReferralConfig.REQUIRE_FIRST_PURCHASE,
            'max_referrals_per_month': ReferralConfig.MAX_REFERRALS_PER_MONTH
        }
    })


# ==================== MEMBER ENDPOINTS ====================

@referrals_bp.route('/code', methods=['GET'])
@require_shopify_auth
def get_member_referral_code():
    """
    Get the current member's referral code.
    Creates one if it doesn't exist.
    """
    member_id = request.args.get('member_id', type=int)
    if not member_id:
        return jsonify({'error': 'member_id required'}), 400

    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Ensure member has a referral code
    code = member.ensure_referral_code()
    db.session.commit()

    return jsonify({
        'referral_code': code,
        'referral_url': f'/pages/join?ref={code}',  # Store can customize this
        'referral_count': member.referral_count or 0,
        'referral_earnings': float(member.referral_earnings or 0)
    })


@referrals_bp.route('/validate', methods=['POST'])
def validate_referral_code():
    """
    Validate a referral code before signup.
    Public endpoint - no auth required.
    """
    data = request.json or {}
    code = data.get('code', '').strip().upper()

    if not code:
        return jsonify({'valid': False, 'error': 'No code provided'})

    referrer = Member.query.filter_by(
        referral_code=code,
        status='active'
    ).first()

    if not referrer:
        return jsonify({'valid': False, 'error': 'Invalid or expired code'})

    return jsonify({
        'valid': True,
        'referrer_name': referrer.name.split()[0] if referrer.name else 'a friend',
        'referee_credit': float(ReferralConfig.REFEREE_CREDIT)
    })


@referrals_bp.route('/apply', methods=['POST'])
@require_shopify_auth
def apply_referral():
    """
    Apply a referral code to a new member.
    Called during enrollment if a referral code was provided.
    """
    data = request.json or {}
    member_id = data.get('member_id')
    referral_code = data.get('referral_code', '').strip().upper()

    if not member_id or not referral_code:
        return jsonify({'error': 'member_id and referral_code required'}), 400

    # Get the new member
    new_member = Member.query.get(member_id)
    if not new_member:
        return jsonify({'error': 'Member not found'}), 404

    # Check if already has a referrer
    if new_member.referred_by_id:
        return jsonify({'error': 'Member already has a referrer'}), 400

    # Find the referrer
    referrer = Member.query.filter_by(
        referral_code=referral_code,
        status='active'
    ).first()

    if not referrer:
        return jsonify({'error': 'Invalid referral code'}), 400

    # Can't refer yourself
    if referrer.id == new_member.id:
        return jsonify({'error': 'Cannot use your own referral code'}), 400

    # Apply the referral
    new_member.referred_by_id = referrer.id

    # Update referrer stats
    referrer.referral_count = (referrer.referral_count or 0) + 1

    try:
        db.session.commit()

        # Grant credits if configured for immediate grant
        credits_granted = []
        if ReferralConfig.GRANT_ON_SIGNUP:
            credits_granted = grant_referral_credits(referrer, new_member)

        return jsonify({
            'success': True,
            'referrer_name': referrer.name,
            'credits_granted': credits_granted
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Referral apply error: {e}")
        return jsonify({'error': 'Failed to apply referral'}), 500


def grant_referral_credits(referrer: Member, referee: Member) -> list:
    """
    Grant store credits for a successful referral.
    """
    from ..services.store_credit_service import store_credit_service

    credits_granted = []

    try:
        # Credit to referrer
        if ReferralConfig.REFERRER_CREDIT > 0:
            store_credit_service.add_credit(
                member_id=referrer.id,
                amount=ReferralConfig.REFERRER_CREDIT,
                event_type='referral_bonus',
                description=f'Referral bonus - {referee.name or referee.email} joined',
                source_type='referral',
                source_id=str(referee.id),
                created_by='system'
            )
            referrer.referral_earnings = (
                Decimal(str(referrer.referral_earnings or 0)) +
                ReferralConfig.REFERRER_CREDIT
            )
            credits_granted.append({
                'recipient': 'referrer',
                'amount': float(ReferralConfig.REFERRER_CREDIT)
            })

        # Credit to referee (new member)
        if ReferralConfig.REFEREE_CREDIT > 0:
            store_credit_service.add_credit(
                member_id=referee.id,
                amount=ReferralConfig.REFEREE_CREDIT,
                event_type='referral_bonus',
                description=f'Welcome bonus - referred by {referrer.name or referrer.member_number}',
                source_type='referral',
                source_id=str(referrer.id),
                created_by='system'
            )
            credits_granted.append({
                'recipient': 'referee',
                'amount': float(ReferralConfig.REFEREE_CREDIT)
            })

        db.session.commit()

    except Exception as e:
        current_app.logger.error(f"Referral credit grant error: {e}")
        db.session.rollback()

    return credits_granted


# ==================== PUBLIC STOREFRONT ENDPOINTS ====================

@referrals_bp.route('/public/info', methods=['GET'])
def get_public_referral_info():
    """
    Get referral program info for storefront display.
    Public endpoint - no auth required.
    """
    return jsonify({
        'program': {
            'name': 'Refer a Friend',
            'referrer_reward': float(ReferralConfig.REFERRER_CREDIT),
            'referee_reward': float(ReferralConfig.REFEREE_CREDIT),
            'description': f'Give your friends ${ReferralConfig.REFEREE_CREDIT} off, '
                          f'get ${ReferralConfig.REFERRER_CREDIT} for yourself!'
        }
    })
