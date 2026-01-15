"""
Shopify App Proxy endpoints for TradeUp.

Handles requests from store.myshopify.com/apps/rewards
Provides customer-facing rewards page and API endpoints.

App proxy documentation: https://shopify.dev/docs/apps/build/online-store/display-dynamic-store-data/app-proxies
"""
import hashlib
import hmac
import os
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify, current_app, Response
from sqlalchemy import func
from ..extensions import db
from ..models import Member, MembershipTier
from ..models.tenant import Tenant
from ..models.loyalty_points import Reward, RewardRedemption
from ..models import PointsTransaction
from ..models.referral import ReferralProgram

proxy_bp = Blueprint('proxy', __name__)


def verify_proxy_signature():
    """
    Verify the Shopify proxy request signature.

    Shopify signs all app proxy requests with the app's API secret.
    https://shopify.dev/docs/apps/build/online-store/display-dynamic-store-data/app-proxies#calculate-a-digital-signature

    Returns:
        Tuple of (is_valid, shop_domain)
    """
    signature = request.args.get('signature', '')

    # Build the query string without signature
    query_params = []
    for key in sorted(request.args.keys()):
        if key != 'signature':
            value = request.args.get(key)
            query_params.append(f'{key}={value}')

    query_string = '&'.join(query_params)

    # Calculate expected signature
    api_secret = os.getenv('SHOPIFY_API_SECRET', '')
    expected_signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    is_valid = hmac.compare_digest(signature, expected_signature)
    shop = request.args.get('shop', '')

    return is_valid, shop


def get_tenant_from_shop(shop_domain: str):
    """Get tenant from shop domain."""
    if not shop_domain:
        return None
    return Tenant.query.filter_by(shop_domain=shop_domain).first()


def get_customer_member(tenant_id: int):
    """
    Get member from logged_in_customer_id parameter.
    Shopify passes this for logged-in customers.
    """
    customer_id = request.args.get('logged_in_customer_id')
    if not customer_id:
        return None

    return Member.query.filter_by(
        tenant_id=tenant_id,
        shopify_customer_id=str(customer_id)
    ).first()


# ==============================================================================
# PROXY ENDPOINTS
# ==============================================================================

@proxy_bp.route('/', methods=['GET'])
@proxy_bp.route('', methods=['GET'])
def rewards_page():
    """
    Main rewards landing page.
    Accessible at: store.myshopify.com/apps/rewards

    Renders a beautiful HTML page with:
    - Customer points balance (if logged in)
    - How to earn points
    - Available rewards catalog
    - Tier benefits comparison
    - Referral program info
    """
    # Verify signature in production
    if os.getenv('FLASK_ENV') == 'production':
        is_valid, shop = verify_proxy_signature()
        if not is_valid:
            return Response('Invalid signature', status=401)
    else:
        shop = request.args.get('shop', '')

    tenant = get_tenant_from_shop(shop)
    if not tenant:
        return Response('Store not found', status=404)

    # Get customer data if logged in
    member = get_customer_member(tenant.id)

    # Get tenant configuration
    tiers = MembershipTier.query.filter_by(
        tenant_id=tenant.id,
        is_active=True
    ).order_by(MembershipTier.display_order).all()

    # Get available rewards
    now = datetime.utcnow()
    rewards = Reward.query.filter(
        Reward.tenant_id == tenant.id,
        Reward.is_active == True,
        (Reward.starts_at.is_(None) | (Reward.starts_at <= now)),
        (Reward.ends_at.is_(None) | (Reward.ends_at >= now)),
        (Reward.stock_quantity.is_(None) | (Reward.stock_quantity > 0))
    ).order_by(Reward.points_cost.asc()).limit(12).all()

    # Get referral program
    referral_program = ReferralProgram.query.filter_by(
        tenant_id=tenant.id,
        is_active=True
    ).first()

    # Build member data for template
    member_data = None
    points_balance = 0
    if member:
        points_balance = db.session.query(
            func.coalesce(func.sum(PointsTransaction.points), 0)
        ).filter(
            PointsTransaction.member_id == member.id,
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        member_data = {
            'name': member.name or 'Member',
            'tier': member.tier.name if member.tier else 'Member',
            'points': int(points_balance),
            'member_since': member.membership_start_date.strftime('%B %Y') if member.membership_start_date else None
        }

    # Render the beautiful HTML page
    html = render_rewards_page(
        shop=shop,
        tenant=tenant,
        member=member_data,
        points_balance=int(points_balance),
        tiers=tiers,
        rewards=rewards,
        referral_program=referral_program
    )

    return Response(html, mimetype='text/html')


@proxy_bp.route('/refer/<code>', methods=['GET'])
def referral_landing_page(code):
    """
    Dedicated referral landing page.
    Accessible at: store.myshopify.com/apps/rewards/refer/ABC123

    Shows personalized referral page with:
    - Referrer's name (first name only for privacy)
    - What the new customer gets
    - What the referrer gets
    - CTA to shop now
    """
    # Verify signature in production
    if os.getenv('FLASK_ENV') == 'production':
        is_valid, shop = verify_proxy_signature()
        if not is_valid:
            return Response('Invalid signature', status=401)
    else:
        shop = request.args.get('shop', '')

    tenant = get_tenant_from_shop(shop)
    if not tenant:
        return Response('Store not found', status=404)

    # Find the referrer by code
    referrer = Member.query.filter_by(
        tenant_id=tenant.id,
        referral_code=code.upper()
    ).first()

    # Get referral program settings
    referral_program = ReferralProgram.query.filter_by(
        tenant_id=tenant.id,
        is_active=True
    ).first()

    # Get page customization from tenant settings
    page_config = {}
    if tenant.settings and 'referral_page' in tenant.settings:
        page_config = tenant.settings['referral_page']

    # Default values
    referrer_name = 'a friend'
    if referrer and referrer.name:
        referrer_name = referrer.name.split()[0]  # First name only

    referrer_reward = 10
    referee_reward = 10
    if referral_program:
        referrer_reward = float(referral_program.referrer_reward_amount or 10)
        referee_reward = float(referral_program.referred_reward_amount or 10)

    html = render_referral_landing_page(
        shop=shop,
        tenant=tenant,
        code=code,
        referrer_name=referrer_name,
        referrer_reward=referrer_reward,
        referee_reward=referee_reward,
        valid_code=referrer is not None,
        page_config=page_config
    )

    return Response(html, mimetype='text/html')


@proxy_bp.route('/balance', methods=['GET'])
def get_balance():
    """
    Get customer's points balance.
    Returns JSON for AJAX requests.
    """
    # Verify signature in production
    if os.getenv('FLASK_ENV') == 'production':
        is_valid, shop = verify_proxy_signature()
        if not is_valid:
            return jsonify({'error': 'Invalid signature'}), 401
    else:
        shop = request.args.get('shop', '')

    tenant = get_tenant_from_shop(shop)
    if not tenant:
        return jsonify({'error': 'Store not found'}), 404

    member = get_customer_member(tenant.id)
    if not member:
        return jsonify({
            'is_member': False,
            'message': 'Please log in to view your rewards balance'
        })

    # Get points balance
    points_balance = db.session.query(
        func.coalesce(func.sum(PointsTransaction.points), 0)
    ).filter(
        PointsTransaction.member_id == member.id,
        PointsTransaction.reversed_at.is_(None)
    ).scalar()

    # Get tier info
    tier_info = None
    if member.tier:
        tier_info = {
            'name': member.tier.name,
            'earning_multiplier': float(member.tier.points_earning_multiplier or 1),
            'discount_percent': float(member.tier.purchase_cashback_pct or 0)
        }

    return jsonify({
        'is_member': True,
        'points_balance': int(points_balance),
        'tier': tier_info,
        'member_since': member.membership_start_date.isoformat() if member.membership_start_date else None,
        'lifetime_earned': member.lifetime_points_earned or 0,
        'lifetime_spent': member.lifetime_points_spent or 0
    })


@proxy_bp.route('/rewards', methods=['GET'])
def get_rewards():
    """
    Get available rewards catalog.
    Returns JSON for AJAX requests.
    """
    # Verify signature in production
    if os.getenv('FLASK_ENV') == 'production':
        is_valid, shop = verify_proxy_signature()
        if not is_valid:
            return jsonify({'error': 'Invalid signature'}), 401
    else:
        shop = request.args.get('shop', '')

    tenant = get_tenant_from_shop(shop)
    if not tenant:
        return jsonify({'error': 'Store not found'}), 404

    member = get_customer_member(tenant.id)

    # Get points balance for eligibility check
    points_balance = 0
    if member:
        points_balance = db.session.query(
            func.coalesce(func.sum(PointsTransaction.points), 0)
        ).filter(
            PointsTransaction.member_id == member.id,
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

    # Get available rewards
    now = datetime.utcnow()
    rewards = Reward.query.filter(
        Reward.tenant_id == tenant.id,
        Reward.is_active == True,
        (Reward.starts_at.is_(None) | (Reward.starts_at <= now)),
        (Reward.ends_at.is_(None) | (Reward.ends_at >= now)),
        (Reward.stock_quantity.is_(None) | (Reward.stock_quantity > 0))
    ).order_by(Reward.points_cost.asc()).all()

    # Build response with eligibility info
    rewards_data = []
    for reward in rewards:
        # Check tier restriction
        tier_eligible = True
        if member and reward.tier_ids:
            tier_eligible = member.tier_id in reward.tier_ids

        can_redeem = (
            member is not None and
            int(points_balance) >= reward.points_cost and
            tier_eligible
        )

        rewards_data.append({
            'id': reward.id,
            'name': reward.name,
            'description': reward.description,
            'points_cost': reward.points_cost,
            'reward_type': reward.reward_type,
            'image_url': reward.image_url,
            'can_redeem': can_redeem,
            'points_needed': max(0, reward.points_cost - int(points_balance)) if member else reward.points_cost
        })

    return jsonify({
        'rewards': rewards_data,
        'points_balance': int(points_balance) if member else 0,
        'is_member': member is not None
    })


@proxy_bp.route('/tiers', methods=['GET'])
def get_tiers():
    """
    Get tier benefits comparison.
    Returns JSON for AJAX requests.
    """
    # Verify signature in production
    if os.getenv('FLASK_ENV') == 'production':
        is_valid, shop = verify_proxy_signature()
        if not is_valid:
            return jsonify({'error': 'Invalid signature'}), 401
    else:
        shop = request.args.get('shop', '')

    tenant = get_tenant_from_shop(shop)
    if not tenant:
        return jsonify({'error': 'Store not found'}), 404

    member = get_customer_member(tenant.id)
    current_tier_id = member.tier_id if member else None

    # Get all active tiers
    tiers = MembershipTier.query.filter_by(
        tenant_id=tenant.id,
        is_active=True
    ).order_by(MembershipTier.display_order).all()

    tiers_data = []
    for tier in tiers:
        tiers_data.append({
            'id': tier.id,
            'name': tier.name,
            'is_current': tier.id == current_tier_id,
            'earning_multiplier': float(tier.points_earning_multiplier or 1),
            'discount_percent': float(tier.purchase_cashback_pct or 0),
            'trade_in_bonus_pct': float(tier.trade_in_bonus_pct or 0),
            'monthly_credit': float(tier.monthly_credit_amount or 0),
            'free_shipping_threshold': float(tier.free_shipping_threshold) if tier.free_shipping_threshold else None,
            'benefits': tier.benefits or {}
        })

    return jsonify({
        'tiers': tiers_data,
        'current_tier_id': current_tier_id
    })


# ==============================================================================
# HTML TEMPLATE RENDERING
# ==============================================================================

def render_rewards_page(shop, tenant, member, points_balance, tiers, rewards, referral_program):
    """
    Render the rewards landing page HTML.

    This is a beautiful, responsive page that matches the store's theme.
    Uses Liquid-compatible styles and minimal dependencies.
    """
    # Dollar sign for f-string formatting
    dollar = "$"

    # Build member section
    member_section = ''
    if member:
        member_section = f'''
        <div class="tradeup-member-card">
            <div class="tradeup-member-header">
                <div class="tradeup-avatar">
                    <span>{member['name'][0].upper()}</span>
                </div>
                <div class="tradeup-member-info">
                    <h3>Welcome back, {member['name']}!</h3>
                    <p class="tradeup-tier-badge">{member['tier']}</p>
                </div>
            </div>
            <div class="tradeup-points-display">
                <div class="tradeup-points-value">{points_balance:,}</div>
                <div class="tradeup-points-label">Points Available</div>
            </div>
        </div>
        '''
    else:
        member_section = '''
        <div class="tradeup-cta-card">
            <h3>Join Our Rewards Program</h3>
            <p>Earn points on every purchase and unlock exclusive rewards!</p>
            <a href="/account/login" class="tradeup-btn tradeup-btn-primary">Sign In to Get Started</a>
        </div>
        '''

    # Build tiers section
    tiers_html = ''
    for tier in tiers:
        benefits_html = ''
        if tier.benefits:
            for key, value in tier.benefits.items():
                if value:
                    benefits_html += f'<li>{key.replace("_", " ").title()}: {value}</li>'

        current_class = 'tradeup-tier-current' if (member and tier.name == member['tier']) else ''
        earning_mult = getattr(tier, 'points_earning_multiplier', 1) or 1
        cashback = getattr(tier, 'purchase_cashback_pct', 0) or 0
        trade_bonus = getattr(tier, 'trade_in_bonus_pct', 0) or 0
        monthly_credit = getattr(tier, 'monthly_credit_amount', 0) or 0

        tiers_html += f'''
        <div class="tradeup-tier-card {current_class}">
            <div class="tradeup-tier-header">
                <h4>{tier.name}</h4>
                {f'<span class="tradeup-current-badge">Your Tier</span>' if current_class else ''}
            </div>
            <ul class="tradeup-tier-benefits">
                <li><strong>{earning_mult}x</strong> points on purchases</li>
                {f'<li><strong>{cashback}%</strong> cashback</li>' if cashback else ''}
                {f'<li><strong>{trade_bonus}%</strong> trade-in bonus</li>' if trade_bonus else ''}
                {f'<li><strong>{dollar}{monthly_credit:.0f}</strong> monthly credit</li>' if monthly_credit else ''}
                {benefits_html}
            </ul>
        </div>
        '''

    # Build rewards section
    rewards_html = ''
    for reward in rewards:
        can_redeem = member and points_balance >= reward.points_cost
        disabled_class = '' if can_redeem else 'tradeup-reward-disabled'

        reward_value = ''
        if reward.reward_type == 'discount':
            if hasattr(reward, 'discount_percent') and reward.discount_percent:
                reward_value = f'{reward.discount_percent}% off'
            elif hasattr(reward, 'discount_amount') and reward.discount_amount:
                reward_value = f'{dollar}{reward.discount_amount} off'
        elif reward.reward_type == 'store_credit' and hasattr(reward, 'credit_value') and reward.credit_value:
            reward_value = f'{dollar}{reward.credit_value} credit'
        elif reward.reward_type == 'free_shipping':
            reward_value = 'Free shipping'

        rewards_html += f'''
        <div class="tradeup-reward-card {disabled_class}">
            {f'<img src="{reward.image_url}" alt="{reward.name}" class="tradeup-reward-image" />' if reward.image_url else '<div class="tradeup-reward-placeholder"></div>'}
            <div class="tradeup-reward-content">
                <h4>{reward.name}</h4>
                {f'<p class="tradeup-reward-value">{reward_value}</p>' if reward_value else ''}
                <p class="tradeup-reward-description">{reward.description or ""}</p>
                <div class="tradeup-reward-footer">
                    <span class="tradeup-reward-points">{reward.points_cost:,} pts</span>
                    {'<a href="/account" class="tradeup-btn tradeup-btn-small">Redeem</a>' if can_redeem else f'<span class="tradeup-points-needed">{max(0, reward.points_cost - points_balance):,} more pts needed</span>'}
                </div>
            </div>
        </div>
        '''

    # Build referral section
    referral_html = ''
    if referral_program:
        referrer_reward = getattr(referral_program, 'referrer_reward_amount', 0) or 0
        referred_reward = getattr(referral_program, 'referred_reward_amount', 0) or 0
        referral_html = f'''
        <section class="tradeup-section tradeup-referral">
            <h2>Refer a Friend</h2>
            <div class="tradeup-referral-card">
                <div class="tradeup-referral-rewards">
                    <div class="tradeup-referral-you">
                        <span class="tradeup-reward-amount">{dollar}{referrer_reward:.0f}</span>
                        <span class="tradeup-reward-desc">for you</span>
                    </div>
                    <div class="tradeup-referral-plus">+</div>
                    <div class="tradeup-referral-friend">
                        <span class="tradeup-reward-amount">{dollar}{referred_reward:.0f}</span>
                        <span class="tradeup-reward-desc">for them</span>
                    </div>
                </div>
                <p>{referral_program.description or "Share your referral code with friends. When they make their first purchase, you both get rewarded!"}</p>
                {'<a href="/account" class="tradeup-btn tradeup-btn-secondary">Get Your Referral Link</a>' if member else '<a href="/account/login" class="tradeup-btn tradeup-btn-secondary">Sign In to Refer Friends</a>'}
            </div>
        </section>
        '''

    # Build tiers section
    tiers_section_html = ''
    if tiers_html:
        tiers_section_html = f'''
        <section class="tradeup-section">
            <h2>Membership Tiers</h2>
            <div class="tradeup-tiers-grid">
                {tiers_html}
            </div>
        </section>
        '''

    # Build rewards section
    rewards_section_html = ''
    if rewards_html:
        rewards_section_html = f'''
        <section class="tradeup-section">
            <h2>Rewards Catalog</h2>
            <div class="tradeup-rewards-grid">
                {rewards_html}
            </div>
        </section>
        '''

    # Complete HTML page
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Rewards Program</title>
    <style>
        /* TradeUp Rewards Page Styles */
        :root {{
            --tradeup-primary: #6366f1;
            --tradeup-primary-dark: #4f46e5;
            --tradeup-secondary: #f59e0b;
            --tradeup-success: #10b981;
            --tradeup-text: #1f2937;
            --tradeup-text-light: #6b7280;
            --tradeup-bg: #f9fafb;
            --tradeup-white: #ffffff;
            --tradeup-border: #e5e7eb;
            --tradeup-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --tradeup-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            --tradeup-radius: 12px;
            --tradeup-radius-lg: 16px;
        }}

        .tradeup-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            color: var(--tradeup-text);
        }}

        /* Hero Section */
        .tradeup-hero {{
            text-align: center;
            padding: 60px 20px;
            background: linear-gradient(135deg, var(--tradeup-primary) 0%, var(--tradeup-primary-dark) 100%);
            border-radius: var(--tradeup-radius-lg);
            color: white;
            margin-bottom: 40px;
        }}

        .tradeup-hero h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin: 0 0 16px 0;
        }}

        .tradeup-hero p {{
            font-size: 1.125rem;
            opacity: 0.9;
            max-width: 600px;
            margin: 0 auto;
        }}

        /* Member Card */
        .tradeup-member-card {{
            background: var(--tradeup-white);
            border-radius: var(--tradeup-radius-lg);
            padding: 32px;
            box-shadow: var(--tradeup-shadow-lg);
            margin: -80px auto 40px;
            max-width: 500px;
            position: relative;
            z-index: 10;
        }}

        .tradeup-member-header {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 24px;
        }}

        .tradeup-avatar {{
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--tradeup-primary), var(--tradeup-secondary));
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.5rem;
            font-weight: 600;
        }}

        .tradeup-member-info h3 {{
            margin: 0 0 4px 0;
            font-size: 1.25rem;
        }}

        .tradeup-tier-badge {{
            display: inline-block;
            padding: 4px 12px;
            background: var(--tradeup-bg);
            border-radius: 20px;
            font-size: 0.875rem;
            color: var(--tradeup-primary);
            font-weight: 500;
            margin: 0;
        }}

        .tradeup-points-display {{
            text-align: center;
            padding: 24px;
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border-radius: var(--tradeup-radius);
        }}

        .tradeup-points-value {{
            font-size: 3rem;
            font-weight: 700;
            color: var(--tradeup-primary);
            line-height: 1;
        }}

        .tradeup-points-label {{
            font-size: 0.875rem;
            color: var(--tradeup-text-light);
            margin-top: 8px;
        }}

        /* CTA Card */
        .tradeup-cta-card {{
            background: var(--tradeup-white);
            border-radius: var(--tradeup-radius-lg);
            padding: 40px;
            box-shadow: var(--tradeup-shadow-lg);
            margin: -80px auto 40px;
            max-width: 500px;
            position: relative;
            z-index: 10;
            text-align: center;
        }}

        .tradeup-cta-card h3 {{
            margin: 0 0 12px 0;
            font-size: 1.5rem;
        }}

        .tradeup-cta-card p {{
            color: var(--tradeup-text-light);
            margin: 0 0 24px 0;
        }}

        /* Buttons */
        .tradeup-btn {{
            display: inline-block;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            cursor: pointer;
            border: none;
            font-size: 1rem;
        }}

        .tradeup-btn-primary {{
            background: var(--tradeup-primary);
            color: white;
        }}

        .tradeup-btn-primary:hover {{
            background: var(--tradeup-primary-dark);
            transform: translateY(-1px);
        }}

        .tradeup-btn-secondary {{
            background: var(--tradeup-secondary);
            color: white;
        }}

        .tradeup-btn-secondary:hover {{
            background: #d97706;
            transform: translateY(-1px);
        }}

        .tradeup-btn-small {{
            padding: 8px 16px;
            font-size: 0.875rem;
        }}

        /* Sections */
        .tradeup-section {{
            margin-bottom: 60px;
        }}

        .tradeup-section h2 {{
            text-align: center;
            font-size: 1.875rem;
            margin: 0 0 32px 0;
        }}

        /* How to Earn */
        .tradeup-earn-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 24px;
        }}

        .tradeup-earn-card {{
            background: var(--tradeup-white);
            border-radius: var(--tradeup-radius);
            padding: 24px;
            text-align: center;
            box-shadow: var(--tradeup-shadow);
        }}

        .tradeup-earn-icon {{
            font-size: 2.5rem;
            margin-bottom: 16px;
        }}

        .tradeup-earn-card h4 {{
            margin: 0 0 8px 0;
            font-size: 1.125rem;
        }}

        .tradeup-earn-card p {{
            color: var(--tradeup-text-light);
            margin: 0;
            font-size: 0.875rem;
        }}

        /* Tiers */
        .tradeup-tiers-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 24px;
        }}

        .tradeup-tier-card {{
            background: var(--tradeup-white);
            border-radius: var(--tradeup-radius);
            padding: 24px;
            box-shadow: var(--tradeup-shadow);
            border: 2px solid transparent;
            transition: all 0.2s ease;
        }}

        .tradeup-tier-card:hover {{
            transform: translateY(-4px);
            box-shadow: var(--tradeup-shadow-lg);
        }}

        .tradeup-tier-current {{
            border-color: var(--tradeup-primary);
        }}

        .tradeup-tier-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}

        .tradeup-tier-header h4 {{
            margin: 0;
            font-size: 1.25rem;
        }}

        .tradeup-current-badge {{
            background: var(--tradeup-primary);
            color: white;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .tradeup-tier-benefits {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}

        .tradeup-tier-benefits li {{
            padding: 8px 0;
            border-bottom: 1px solid var(--tradeup-border);
            font-size: 0.875rem;
        }}

        .tradeup-tier-benefits li:last-child {{
            border-bottom: none;
        }}

        .tradeup-tier-benefits strong {{
            color: var(--tradeup-primary);
        }}

        /* Rewards */
        .tradeup-rewards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 24px;
        }}

        .tradeup-reward-card {{
            background: var(--tradeup-white);
            border-radius: var(--tradeup-radius);
            overflow: hidden;
            box-shadow: var(--tradeup-shadow);
            transition: all 0.2s ease;
        }}

        .tradeup-reward-card:hover {{
            transform: translateY(-4px);
            box-shadow: var(--tradeup-shadow-lg);
        }}

        .tradeup-reward-disabled {{
            opacity: 0.7;
        }}

        .tradeup-reward-image {{
            width: 100%;
            height: 160px;
            object-fit: cover;
        }}

        .tradeup-reward-placeholder {{
            width: 100%;
            height: 160px;
            background: linear-gradient(135deg, var(--tradeup-primary), var(--tradeup-secondary));
        }}

        .tradeup-reward-content {{
            padding: 20px;
        }}

        .tradeup-reward-content h4 {{
            margin: 0 0 8px 0;
            font-size: 1.125rem;
        }}

        .tradeup-reward-value {{
            color: var(--tradeup-success);
            font-weight: 600;
            margin: 0 0 8px 0;
        }}

        .tradeup-reward-description {{
            color: var(--tradeup-text-light);
            font-size: 0.875rem;
            margin: 0 0 16px 0;
            line-height: 1.5;
        }}

        .tradeup-reward-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .tradeup-reward-points {{
            font-weight: 600;
            color: var(--tradeup-primary);
        }}

        .tradeup-points-needed {{
            font-size: 0.75rem;
            color: var(--tradeup-text-light);
        }}

        /* Referral */
        .tradeup-referral-card {{
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border-radius: var(--tradeup-radius-lg);
            padding: 40px;
            text-align: center;
            max-width: 600px;
            margin: 0 auto;
        }}

        .tradeup-referral-rewards {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 24px;
            margin-bottom: 24px;
        }}

        .tradeup-referral-you,
        .tradeup-referral-friend {{
            text-align: center;
        }}

        .tradeup-reward-amount {{
            display: block;
            font-size: 2rem;
            font-weight: 700;
            color: var(--tradeup-text);
        }}

        .tradeup-reward-desc {{
            font-size: 0.875rem;
            color: var(--tradeup-text-light);
        }}

        .tradeup-referral-plus {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--tradeup-secondary);
        }}

        .tradeup-referral-card p {{
            color: var(--tradeup-text);
            margin: 0 0 24px 0;
        }}

        /* Footer */
        .tradeup-footer {{
            text-align: center;
            padding: 40px 20px;
            color: var(--tradeup-text-light);
            font-size: 0.875rem;
        }}

        .tradeup-footer a {{
            color: var(--tradeup-primary);
            text-decoration: none;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .tradeup-hero h1 {{
                font-size: 1.875rem;
            }}

            .tradeup-member-card,
            .tradeup-cta-card {{
                margin: -60px 16px 40px;
                padding: 24px;
            }}

            .tradeup-points-value {{
                font-size: 2.5rem;
            }}

            .tradeup-referral-rewards {{
                flex-direction: column;
                gap: 16px;
            }}

            .tradeup-referral-plus {{
                transform: rotate(90deg);
            }}
        }}
    </style>
</head>
<body>
    <div class="tradeup-container">
        <!-- Hero Section -->
        <section class="tradeup-hero">
            <h1>Rewards Program</h1>
            <p>Earn points on every purchase, unlock exclusive rewards, and enjoy member-only benefits.</p>
        </section>

        <!-- Member Card or CTA -->
        {member_section}

        <!-- How to Earn Section -->
        <section class="tradeup-section">
            <h2>How to Earn Points</h2>
            <div class="tradeup-earn-grid">
                <div class="tradeup-earn-card">
                    <div class="tradeup-earn-icon">&#128722;</div>
                    <h4>Shop & Earn</h4>
                    <p>Earn 1 point for every $1 spent on purchases</p>
                </div>
                <div class="tradeup-earn-card">
                    <div class="tradeup-earn-icon">&#127873;</div>
                    <h4>Trade-Ins</h4>
                    <p>Earn bonus points when you trade in your items</p>
                </div>
                <div class="tradeup-earn-card">
                    <div class="tradeup-earn-icon">&#128101;</div>
                    <h4>Refer Friends</h4>
                    <p>Get rewarded when friends make their first purchase</p>
                </div>
                <div class="tradeup-earn-card">
                    <div class="tradeup-earn-icon">&#127881;</div>
                    <h4>Special Events</h4>
                    <p>Bonus point days and exclusive member promotions</p>
                </div>
            </div>
        </section>

        <!-- Tier Benefits Section -->
        {tiers_section_html}

        <!-- Rewards Catalog Section -->
        {rewards_section_html}

        <!-- Referral Section -->
        {referral_html}

        <!-- Footer -->
        <footer class="tradeup-footer">
            <p>Powered by <a href="https://cardflowlabs.com" target="_blank" rel="noopener">TradeUp</a></p>
        </footer>
    </div>
</body>
</html>
'''

    return html


def render_referral_landing_page(shop, tenant, code, referrer_name, referrer_reward, referee_reward, valid_code, page_config):
    """
    Render a dedicated referral landing page.

    Features:
    - Personalized greeting with referrer's name
    - Clear value proposition (what both parties get)
    - Social sharing buttons
    - Strong CTA to shop
    """
    # Pre-format reward amounts to avoid f-string issues
    referee_reward_str = f"${referee_reward:.0f}"
    referrer_reward_str = f"${referrer_reward:.0f}"

    # Get customization from config or use defaults
    headline = page_config.get('headline', f'{referrer_name} sent you a gift!')
    description = page_config.get('description',
        f'Shop now and get {referee_reward_str} off your first order. '
        f'{referrer_name} will get {referrer_reward_str} too!')
    background_color = page_config.get('background_color', '#6366f1')
    cta_text = page_config.get('cta_text', 'Shop Now')

    # Build the shop URL
    shop_url = f'https://{shop}' if shop else '/'

    # Error state for invalid codes
    if not valid_code:
        headline = 'Oops! Code Not Found'
        description = "This referral code doesn't seem to be valid. Check with your friend for the correct link!"
        cta_text = 'Browse Store'

    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>You're Invited! - Get {referee_reward_str} Off</title>
    <meta property="og:title" content="{referrer_name} sent you a gift!">
    <meta property="og:description" content="Get {referee_reward_str} off your first order">
    <meta property="og:type" content="website">
    <meta name="twitter:card" content="summary_large_image">
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, {background_color} 0%, #4f46e5 100%);
            padding: 20px;
        }}

        .referral-container {{
            background: white;
            border-radius: 24px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            max-width: 500px;
            width: 100%;
            overflow: hidden;
            text-align: center;
        }}

        .referral-header {{
            background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
            padding: 40px 30px;
            color: #1f2937;
        }}

        .gift-icon {{
            font-size: 4rem;
            margin-bottom: 16px;
            display: block;
        }}

        .referral-header h1 {{
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 12px;
            line-height: 1.2;
        }}

        .referral-header p {{
            font-size: 1.125rem;
            opacity: 0.9;
        }}

        .rewards-display {{
            display: flex;
            justify-content: center;
            gap: 30px;
            padding: 40px 30px;
            background: #f9fafb;
        }}

        .reward-item {{
            text-align: center;
        }}

        .reward-amount {{
            font-size: 2.5rem;
            font-weight: 700;
            color: #059669;
            display: block;
        }}

        .reward-label {{
            font-size: 0.875rem;
            color: #6b7280;
            margin-top: 4px;
        }}

        .reward-divider {{
            display: flex;
            align-items: center;
            font-size: 1.5rem;
            color: #d1d5db;
        }}

        .referral-body {{
            padding: 30px;
        }}

        .cta-button {{
            display: inline-block;
            background: linear-gradient(135deg, {background_color} 0%, #4f46e5 100%);
            color: white;
            font-size: 1.125rem;
            font-weight: 600;
            padding: 16px 48px;
            border-radius: 12px;
            text-decoration: none;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-bottom: 20px;
        }}

        .cta-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(99, 102, 241, 0.3);
        }}

        .referral-code-display {{
            background: #f3f4f6;
            padding: 12px 24px;
            border-radius: 8px;
            display: inline-block;
            margin-bottom: 20px;
        }}

        .referral-code-label {{
            font-size: 0.75rem;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .referral-code-value {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #1f2937;
            font-family: monospace;
        }}

        .terms {{
            font-size: 0.75rem;
            color: #9ca3af;
            line-height: 1.5;
        }}

        .social-share {{
            display: flex;
            justify-content: center;
            gap: 12px;
            padding: 20px 30px;
            border-top: 1px solid #e5e7eb;
        }}

        .social-btn {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            color: white;
            font-size: 1.25rem;
            transition: transform 0.2s;
        }}

        .social-btn:hover {{
            transform: scale(1.1);
        }}

        .social-facebook {{ background: #1877f2; }}
        .social-twitter {{ background: #1da1f2; }}
        .social-whatsapp {{ background: #25d366; }}
        .social-email {{ background: #6b7280; }}

        @media (max-width: 480px) {{
            .referral-header h1 {{
                font-size: 1.5rem;
            }}

            .rewards-display {{
                flex-direction: column;
                gap: 20px;
            }}

            .reward-divider {{
                transform: rotate(90deg);
            }}

            .reward-amount {{
                font-size: 2rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="referral-container">
        <div class="referral-header">
            <span class="gift-icon">&#127873;</span>
            <h1>{headline}</h1>
            <p>{description}</p>
        </div>

        {'<div class="rewards-display">' if valid_code else ''}
        {f'''
            <div class="reward-item">
                <span class="reward-amount">{referee_reward_str}</span>
                <span class="reward-label">for you</span>
            </div>
            <div class="reward-divider">+</div>
            <div class="reward-item">
                <span class="reward-amount">{referrer_reward_str}</span>
                <span class="reward-label">for {referrer_name}</span>
            </div>
        ''' if valid_code else ''}
        {'</div>' if valid_code else ''}

        <div class="referral-body">
            {f'''
            <div class="referral-code-display">
                <div class="referral-code-label">Your referral code</div>
                <div class="referral-code-value">{code.upper()}</div>
            </div>
            ''' if valid_code else ''}

            <a href="{shop_url}{'?ref=' + code if valid_code else ''}" class="cta-button">{cta_text}</a>

            <p class="terms">
                {'Code will be automatically applied at checkout. Valid for new customers only. Cannot be combined with other offers.' if valid_code else 'Visit our store to browse our collection.'}
            </p>
        </div>

        {'<div class="social-share">' if valid_code else ''}
        {f'''
            <a href="https://www.facebook.com/sharer/sharer.php?u={shop_url}/apps/rewards/refer/{code}" target="_blank" class="social-btn social-facebook" title="Share on Facebook">f</a>
            <a href="https://twitter.com/intent/tweet?text=Get%20{referee_reward_str}%20off%20at%20our%20favorite%20store!&url={shop_url}/apps/rewards/refer/{code}" target="_blank" class="social-btn social-twitter" title="Share on Twitter">t</a>
            <a href="https://wa.me/?text=Get%20{referee_reward_str}%20off%20with%20my%20referral%20link!%20{shop_url}/apps/rewards/refer/{code}" target="_blank" class="social-btn social-whatsapp" title="Share on WhatsApp">w</a>
            <a href="mailto:?subject=You%27re%20Invited!&body=Get%20{referee_reward_str}%20off%20your%20first%20order:%20{shop_url}/apps/rewards/refer/{code}" class="social-btn social-email" title="Share via Email">&#9993;</a>
        ''' if valid_code else ''}
        {'</div>' if valid_code else ''}
    </div>
</body>
</html>'''

    return html
