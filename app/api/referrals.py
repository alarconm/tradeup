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
    """
    Referral program configuration.
    Reads from tenant settings with defaults.
    """
    # Default values
    DEFAULT_REFERRER_CREDIT = Decimal('10.00')
    DEFAULT_REFEREE_CREDIT = Decimal('5.00')
    DEFAULT_GRANT_ON_SIGNUP = True
    DEFAULT_REQUIRE_FIRST_PURCHASE = False
    DEFAULT_MAX_REFERRALS_PER_MONTH = 50

    @classmethod
    def get_config(cls, tenant):
        """Get referral config for a tenant, with defaults."""
        if tenant and tenant.settings and 'referral_config' in tenant.settings:
            config = tenant.settings['referral_config']
            return {
                'referrer_credit': Decimal(str(config.get('referrer_credit', cls.DEFAULT_REFERRER_CREDIT))),
                'referee_credit': Decimal(str(config.get('referee_credit', cls.DEFAULT_REFEREE_CREDIT))),
                'grant_on_signup': config.get('grant_on_signup', cls.DEFAULT_GRANT_ON_SIGNUP),
                'require_first_purchase': config.get('require_first_purchase', cls.DEFAULT_REQUIRE_FIRST_PURCHASE),
                'max_referrals_per_month': config.get('max_referrals_per_month', cls.DEFAULT_MAX_REFERRALS_PER_MONTH),
            }
        return {
            'referrer_credit': cls.DEFAULT_REFERRER_CREDIT,
            'referee_credit': cls.DEFAULT_REFEREE_CREDIT,
            'grant_on_signup': cls.DEFAULT_GRANT_ON_SIGNUP,
            'require_first_purchase': cls.DEFAULT_REQUIRE_FIRST_PURCHASE,
            'max_referrals_per_month': cls.DEFAULT_MAX_REFERRALS_PER_MONTH,
        }

    # Legacy class attributes for backwards compatibility
    REFERRER_CREDIT = DEFAULT_REFERRER_CREDIT
    REFEREE_CREDIT = DEFAULT_REFEREE_CREDIT
    GRANT_ON_SIGNUP = DEFAULT_GRANT_ON_SIGNUP
    REQUIRE_FIRST_PURCHASE = DEFAULT_REQUIRE_FIRST_PURCHASE
    MAX_REFERRALS_PER_MONTH = DEFAULT_MAX_REFERRALS_PER_MONTH


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

    # Get tenant-specific config
    tenant = g.tenant
    config = ReferralConfig.get_config(tenant)

    return jsonify({
        'stats': {
            'total_referrals': total_referrals,
            'total_credit_issued': float(total_referral_credit),
            'referrer_reward': float(config['referrer_credit']),
            'referee_reward': float(config['referee_credit'])
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
    tenant = g.tenant
    config = ReferralConfig.get_config(tenant)

    return jsonify({
        'config': {
            'referrer_credit': float(config['referrer_credit']),
            'referee_credit': float(config['referee_credit']),
            'grant_on_signup': config['grant_on_signup'],
            'require_first_purchase': config['require_first_purchase'],
            'max_referrals_per_month': config['max_referrals_per_month']
        }
    })


@referrals_bp.route('/admin/config', methods=['PUT'])
@require_shopify_auth
def update_referral_config():
    """
    Update referral program configuration.

    Request body:
    {
        "referrer_credit": 10.00,
        "referee_credit": 5.00,
        "grant_on_signup": true,
        "require_first_purchase": false,
        "max_referrals_per_month": 50
    }
    """
    from sqlalchemy.orm.attributes import flag_modified

    data = request.json or {}
    tenant = g.tenant

    # Initialize settings if needed
    if tenant.settings is None:
        tenant.settings = {}

    # Get existing config or create new
    referral_config = tenant.settings.get('referral_config', {})

    # Validate and update fields
    if 'referrer_credit' in data:
        try:
            amount = float(data['referrer_credit'])
            if amount < 0:
                return jsonify({'error': 'Referrer credit cannot be negative'}), 400
            if amount > 1000:
                return jsonify({'error': 'Referrer credit cannot exceed $1000'}), 400
            referral_config['referrer_credit'] = amount
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid referrer credit amount'}), 400

    if 'referee_credit' in data:
        try:
            amount = float(data['referee_credit'])
            if amount < 0:
                return jsonify({'error': 'Referee credit cannot be negative'}), 400
            if amount > 1000:
                return jsonify({'error': 'Referee credit cannot exceed $1000'}), 400
            referral_config['referee_credit'] = amount
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid referee credit amount'}), 400

    if 'grant_on_signup' in data:
        referral_config['grant_on_signup'] = bool(data['grant_on_signup'])

    if 'require_first_purchase' in data:
        referral_config['require_first_purchase'] = bool(data['require_first_purchase'])

    if 'max_referrals_per_month' in data:
        try:
            limit = int(data['max_referrals_per_month'])
            if limit < 1:
                return jsonify({'error': 'Monthly limit must be at least 1'}), 400
            if limit > 1000:
                return jsonify({'error': 'Monthly limit cannot exceed 1000'}), 400
            referral_config['max_referrals_per_month'] = limit
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid monthly limit'}), 400

    # Save back to settings
    tenant.settings['referral_config'] = referral_config
    flag_modified(tenant, 'settings')

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'config': {
                'referrer_credit': referral_config.get('referrer_credit', float(ReferralConfig.DEFAULT_REFERRER_CREDIT)),
                'referee_credit': referral_config.get('referee_credit', float(ReferralConfig.DEFAULT_REFEREE_CREDIT)),
                'grant_on_signup': referral_config.get('grant_on_signup', ReferralConfig.DEFAULT_GRANT_ON_SIGNUP),
                'require_first_purchase': referral_config.get('require_first_purchase', ReferralConfig.DEFAULT_REQUIRE_FIRST_PURCHASE),
                'max_referrals_per_month': referral_config.get('max_referrals_per_month', ReferralConfig.DEFAULT_MAX_REFERRALS_PER_MONTH)
            }
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update referral config: {e}")
        return jsonify({'error': 'Failed to save configuration'}), 500


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

    # Get tenant-specific config
    from ..models.tenant import Tenant
    tenant = Tenant.query.filter_by(id=referrer.tenant_id).first()
    config = ReferralConfig.get_config(tenant)

    return jsonify({
        'valid': True,
        'referrer_name': referrer.name.split()[0] if referrer.name else 'a friend',
        'referee_credit': float(config['referee_credit'])
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

        # Get tenant-specific config
        tenant = g.tenant
        config = ReferralConfig.get_config(tenant)

        # Grant credits if configured for immediate grant
        credits_granted = []
        if config['grant_on_signup']:
            credits_granted = grant_referral_credits(referrer, new_member, config)

        return jsonify({
            'success': True,
            'referrer_name': referrer.name,
            'credits_granted': credits_granted
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Referral apply error: {e}")
        return jsonify({'error': 'Failed to apply referral'}), 500


def grant_referral_credits(referrer: Member, referee: Member, config: dict = None) -> list:
    """
    Grant store credits for a successful referral.

    Args:
        referrer: The member who made the referral
        referee: The new member who was referred
        config: Optional tenant-specific referral config. If not provided, uses defaults.
    """
    from ..services.store_credit_service import store_credit_service

    # Use defaults if config not provided
    if config is None:
        config = {
            'referrer_credit': ReferralConfig.DEFAULT_REFERRER_CREDIT,
            'referee_credit': ReferralConfig.DEFAULT_REFEREE_CREDIT,
        }

    referrer_credit = Decimal(str(config['referrer_credit']))
    referee_credit = Decimal(str(config['referee_credit']))

    credits_granted = []

    try:
        # Credit to referrer
        if referrer_credit > 0:
            store_credit_service.add_credit(
                member_id=referrer.id,
                amount=referrer_credit,
                event_type='referral_bonus',
                description=f'Referral bonus - {referee.name or referee.email} joined',
                source_type='referral',
                source_id=str(referee.id),
                created_by='system'
            )
            referrer.referral_earnings = (
                Decimal(str(referrer.referral_earnings or 0)) +
                referrer_credit
            )
            credits_granted.append({
                'recipient': 'referrer',
                'amount': float(referrer_credit)
            })

        # Credit to referee (new member)
        if referee_credit > 0:
            store_credit_service.add_credit(
                member_id=referee.id,
                amount=referee_credit,
                event_type='referral_bonus',
                description=f'Welcome bonus - referred by {referrer.name or referrer.member_number}',
                source_type='referral',
                source_id=str(referrer.id),
                created_by='system'
            )
            credits_granted.append({
                'recipient': 'referee',
                'amount': float(referee_credit)
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
    Accepts shop_domain query parameter to return tenant-specific config.
    """
    from ..models.tenant import Tenant

    shop_domain = request.args.get('shop_domain') or request.args.get('shop')
    tenant = None
    if shop_domain:
        # Try to find tenant by shop domain
        tenant = Tenant.query.filter(
            (Tenant.shopify_domain == shop_domain) |
            (Tenant.shopify_domain == shop_domain.replace('.myshopify.com', ''))
        ).first()

    config = ReferralConfig.get_config(tenant)

    return jsonify({
        'program': {
            'name': 'Refer a Friend',
            'referrer_reward': float(config['referrer_credit']),
            'referee_reward': float(config['referee_credit']),
            'description': f'Give your friends ${config["referee_credit"]} off, '
                          f'get ${config["referrer_credit"]} for yourself!'
        }
    })


# ==================== REFERRAL PAGE CONFIGURATION ====================

@referrals_bp.route('/page-config', methods=['GET'])
@require_shopify_auth
def get_referral_page_config():
    """
    Get referral landing page customization settings.
    """
    from ..models.tenant import Tenant
    from sqlalchemy.orm.attributes import flag_modified

    tenant = g.tenant

    # Get existing config or return defaults
    page_config = {}
    if tenant.settings and 'referral_page' in tenant.settings:
        page_config = tenant.settings['referral_page']

    # Merge with defaults
    defaults = {
        'enabled': True,
        'headline': 'Give $10, Get $10',
        'description': 'Share with friends and earn rewards when they make their first purchase.',
        'background_color': '#6366f1',
        'cta_text': 'Shop Now',
        'show_social_sharing': True,
        'social_platforms': ['facebook', 'twitter', 'whatsapp', 'email', 'copy']
    }

    config = {**defaults, **page_config}

    return jsonify({
        'success': True,
        'config': config
    })


@referrals_bp.route('/page-config', methods=['PUT'])
@require_shopify_auth
def update_referral_page_config():
    """
    Update referral landing page customization settings.

    Request body:
    {
        "headline": "Give $10, Get $10",
        "description": "Share with friends...",
        "background_color": "#6366f1",
        "cta_text": "Shop Now",
        "show_social_sharing": true,
        "social_platforms": ["facebook", "twitter", "whatsapp", "email", "copy"]
    }
    """
    from ..models.tenant import Tenant
    from sqlalchemy.orm.attributes import flag_modified

    data = request.json or {}
    tenant = g.tenant

    # Initialize settings if needed
    if tenant.settings is None:
        tenant.settings = {}

    # Get existing config
    page_config = tenant.settings.get('referral_page', {})

    # Update allowed fields
    allowed_fields = [
        'enabled', 'headline', 'description', 'background_color',
        'cta_text', 'show_social_sharing', 'social_platforms',
        'background_image', 'logo_url', 'custom_css'
    ]

    for field in allowed_fields:
        if field in data:
            page_config[field] = data[field]

    # Save back to settings
    tenant.settings['referral_page'] = page_config
    flag_modified(tenant, 'settings')

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'config': page_config
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@referrals_bp.route('/share-links/<int:member_id>', methods=['GET'])
@require_shopify_auth
def get_member_share_links(member_id: int):
    """
    Get pre-formatted share links for a member's referral code.
    """
    from ..models.tenant import Tenant

    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Ensure member has a referral code
    code = member.ensure_referral_code()
    db.session.commit()

    tenant = g.tenant
    shop_url = f'https://{tenant.shopify_domain}'
    referral_url = f'{shop_url}/apps/rewards/refer/{code}'

    # Get tenant-specific reward amounts
    config = ReferralConfig.get_config(tenant)
    referrer_reward = float(config['referrer_credit'])
    referee_reward = float(config['referee_credit'])

    # Build share messages
    share_text = f"Get ${referee_reward:.0f} off your first order!"
    share_body = f"I've been shopping at {tenant.shop_name or 'this store'} and thought you'd love it too! Use my link to get ${referee_reward:.0f} off your first order: {referral_url}"

    return jsonify({
        'success': True,
        'referral_code': code,
        'referral_url': referral_url,
        'share_links': {
            'facebook': f'https://www.facebook.com/sharer/sharer.php?u={referral_url}',
            'twitter': f'https://twitter.com/intent/tweet?text={share_text}&url={referral_url}',
            'whatsapp': f'https://wa.me/?text={share_body}',
            'email': f'mailto:?subject=You%27re%20Invited!&body={share_body}',
            'copy': referral_url
        },
        'share_text': share_text,
        'reward_you': referrer_reward,
        'reward_friend': referee_reward
    })
