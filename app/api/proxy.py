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
from ..models.loyalty_page import LoyaltyPage

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
    return Tenant.query.filter_by(shopify_domain=shop_domain).first()


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


def check_proxy_auth():
    """
    Verify proxy signature and return shop domain.

    Returns:
        Tuple of (error_response, shop_domain)
        If error_response is not None, return it immediately.
    """
    # Allow bypassing signature verification for development/testing
    skip_signature = os.getenv('SKIP_PROXY_SIGNATURE', '').lower() == 'true'

    if os.getenv('FLASK_ENV') == 'production' and not skip_signature:
        is_valid, shop = verify_proxy_signature()
        if not is_valid:
            current_app.logger.warning(f"Proxy signature verification failed. Params: {list(request.args.keys())}")
            return Response('Invalid signature', status=401), None
        return None, shop
    else:
        return None, request.args.get('shop', '')


# ==============================================================================
# PROXY ENDPOINTS
# ==============================================================================

@proxy_bp.route('/', methods=['GET'])
@proxy_bp.route('', methods=['GET'])
def rewards_page():
    """
    Main rewards landing page.
    Accessible at: store.myshopify.com/apps/rewards

    If a custom loyalty page is published, renders that page.
    Otherwise, renders the default rewards page with:
    - Customer points balance (if logged in)
    - How to earn points
    - Available rewards catalog
    - Tier benefits comparison
    - Referral program info
    """
    error_response, shop = check_proxy_auth()
    if error_response:
        return error_response

    tenant = get_tenant_from_shop(shop)
    if not tenant:
        return Response('Store not found', status=404)

    # Check for published custom loyalty page
    loyalty_page = LoyaltyPage.query.filter_by(
        tenant_id=tenant.id,
        is_published=True
    ).first()

    if loyalty_page and loyalty_page.is_published:
        # Render the published custom loyalty page
        published_config = loyalty_page.get_published_config()
        if published_config:
            # Get customer data for personalization
            member = get_customer_member(tenant.id)
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
                    'member_id': member.id,
                    'name': member.name or 'Member',
                    'tier': member.tier.name if member.tier else 'Member',
                    'points': int(points_balance),
                    'member_since': member.membership_start_date.strftime('%B %Y') if member.membership_start_date else None
                }

            # Get live data for dynamic sections
            tiers = MembershipTier.query.filter_by(
                tenant_id=tenant.id,
                is_active=True
            ).order_by(MembershipTier.display_order).all()

            now = datetime.utcnow()
            rewards = Reward.query.filter(
                Reward.tenant_id == tenant.id,
                Reward.is_active == True,
                (Reward.starts_at.is_(None) | (Reward.starts_at <= now)),
                (Reward.ends_at.is_(None) | (Reward.ends_at >= now)),
                (Reward.available_quantity.is_(None) | (Reward.available_quantity > 0))
            ).order_by(Reward.points_cost.asc()).limit(12).all()

            referral_program = ReferralProgram.query.filter_by(
                tenant_id=tenant.id,
                is_active=True
            ).first()

            html = render_published_loyalty_page(
                config=published_config,
                shop=shop,
                tenant=tenant,
                member=member_data,
                points_balance=int(points_balance),
                tiers=tiers,
                rewards=rewards,
                referral_program=referral_program
            )
            return Response(html, mimetype='text/html')

    # Fallback: Render the default rewards page
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
        (Reward.available_quantity.is_(None) | (Reward.available_quantity > 0))
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
            'member_id': member.id,
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
    error_response, shop = check_proxy_auth()
    if error_response:
        return error_response

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
    error_response, shop = check_proxy_auth()
    if error_response:
        return jsonify({'error': 'Invalid signature'}), 401

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
            'earning_multiplier': float(getattr(member.tier, 'points_earning_multiplier', 1) or 1),
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
    error_response, shop = check_proxy_auth()
    if error_response:
        return jsonify({'error': 'Invalid signature'}), 401

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
        (Reward.available_quantity.is_(None) | (Reward.available_quantity > 0))
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
    error_response, shop = check_proxy_auth()
    if error_response:
        return jsonify({'error': 'Invalid signature'}), 401

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
        benefits = tier.benefits or {}
        tiers_data.append({
            'id': tier.id,
            'name': tier.name,
            'is_current': tier.id == current_tier_id,
            'earning_multiplier': float(getattr(tier, 'points_earning_multiplier', 1) or 1),
            'discount_percent': float(tier.purchase_cashback_pct or 0),
            'trade_in_bonus_pct': float(tier.bonus_rate or 0) * 100,  # Convert from decimal (0.05) to percent (5)
            'monthly_credit': float(tier.monthly_credit_amount or 0),
            'free_shipping_threshold': float(benefits.get('free_shipping_threshold')) if benefits.get('free_shipping_threshold') else None,
            'benefits': benefits
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
    Adapts terminology based on loyalty mode (store_credit vs points).
    """
    # Dollar sign for f-string formatting
    dollar = "$"

    # Get loyalty settings to determine mode
    loyalty_settings = {}
    if tenant.settings and 'loyalty' in tenant.settings:
        loyalty_settings = tenant.settings['loyalty']
    loyalty_mode = loyalty_settings.get('mode', 'store_credit')
    is_points_mode = loyalty_mode == 'points'

    # Terminology based on mode
    points_name = loyalty_settings.get('points_name', 'points') if is_points_mode else 'Store Credit'
    points_symbol = loyalty_settings.get('points_currency_symbol', 'pts') if is_points_mode else '$'
    points_to_credit = loyalty_settings.get('points_to_credit_value', 0.01) if is_points_mode else 1

    # Format balance display based on mode
    if is_points_mode:
        balance_display = f'{points_balance:,}'
        balance_label = f'{points_name.title()} Available'
    else:
        # Store credit mode - show as dollar amount
        credit_value = points_balance * points_to_credit if points_to_credit else 0
        balance_display = f'${credit_value:,.2f}'
        balance_label = 'Store Credit Available'

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
                <div class="tradeup-points-value">{balance_display}</div>
                <div class="tradeup-points-label">{balance_label}</div>
            </div>
        </div>
        '''
    else:
        earn_text = 'Earn points on every purchase' if is_points_mode else 'Earn store credit on every purchase'
        member_section = f'''
        <div class="tradeup-cta-card">
            <h3>Join Our Rewards Program</h3>
            <p>{earn_text} and unlock exclusive rewards!</p>
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

        # Mode-specific earning description
        if is_points_mode:
            earning_desc = f'<li><strong>{earning_mult}x</strong> {points_name} on purchases</li>'
        else:
            earning_desc = f'<li><strong>{cashback}%</strong> cashback on purchases</li>' if cashback else ''

        tiers_html += f'''
        <div class="tradeup-tier-card {current_class}">
            <div class="tradeup-tier-header">
                <h4>{tier.name}</h4>
                {f'<span class="tradeup-current-badge">Your Tier</span>' if current_class else ''}
            </div>
            <ul class="tradeup-tier-benefits">
                {earning_desc}
                {f'<li><strong>{cashback}%</strong> cashback</li>' if is_points_mode and cashback else ''}
                {f'<li><strong>{trade_bonus}%</strong> trade-in bonus</li>' if trade_bonus else ''}
                {f'<li><strong>{dollar}{monthly_credit:.0f}</strong> monthly credit</li>' if monthly_credit else ''}
                {benefits_html}
            </ul>
        </div>
        '''

    # Build rewards section (only shown in points mode where customers redeem points)
    rewards_html = ''
    if is_points_mode:
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
                        <span class="tradeup-reward-points">{reward.points_cost:,} {points_symbol}</span>
                        {'<a href="/account" class="tradeup-btn tradeup-btn-small">Redeem</a>' if can_redeem else f'<span class="tradeup-points-needed">{max(0, reward.points_cost - points_balance):,} more {points_symbol} needed</span>'}
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

    # Build rewards section (points mode) or how it works section (store credit mode)
    rewards_section_html = ''
    if is_points_mode and rewards_html:
        rewards_section_html = f'''
        <section class="tradeup-section">
            <h2>Rewards Catalog</h2>
            <div class="tradeup-rewards-grid">
                {rewards_html}
            </div>
        </section>
        '''
    elif not is_points_mode:
        # Store credit mode - show "How It Works" section
        rewards_section_html = '''
        <section class="tradeup-section">
            <h2>How Store Credit Works</h2>
            <div class="tradeup-how-it-works">
                <div class="tradeup-step">
                    <div class="tradeup-step-number">1</div>
                    <h4>Earn Credit</h4>
                    <p>Earn cashback on purchases and bonus credit on trade-ins. Higher tiers earn more!</p>
                </div>
                <div class="tradeup-step">
                    <div class="tradeup-step-number">2</div>
                    <h4>Automatic Savings</h4>
                    <p>Your store credit balance is automatically applied at checkout. No codes needed!</p>
                </div>
                <div class="tradeup-step">
                    <div class="tradeup-step-number">3</div>
                    <h4>Never Expires</h4>
                    <p>Your store credit never expires. Use it whenever you&apos;re ready to shop.</p>
                </div>
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

        /* How It Works (Store Credit Mode) */
        .tradeup-how-it-works {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 32px;
            padding: 20px 0;
        }}

        .tradeup-step {{
            text-align: center;
            padding: 24px;
        }}

        .tradeup-step-number {{
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--tradeup-primary) 0%, var(--tradeup-primary-dark) 100%);
            color: white;
            font-size: 1.5rem;
            font-weight: 700;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px;
        }}

        .tradeup-step h4 {{
            font-size: 1.125rem;
            font-weight: 600;
            margin: 0 0 8px 0;
            color: var(--tradeup-text);
        }}

        .tradeup-step p {{
            font-size: 0.875rem;
            color: var(--tradeup-text-light);
            margin: 0;
            line-height: 1.5;
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
{get_analytics_tracking_script(shop, member)}
</body>
</html>
'''

    return html


def render_published_loyalty_page(config, shop, tenant, member, points_balance, tiers, rewards, referral_program):
    """
    Render the published custom loyalty page from page builder configuration.

    Uses the published config to render a customized loyalty page with:
    - Custom sections (hero, how it works, tiers, rewards, FAQ, referrals)
    - Custom colors and typography
    - Custom styles (button shape, spacing, etc.)
    - SEO meta tags from configuration
    - Live data for tiers, rewards, and referral program

    Args:
        config: Published page configuration from LoyaltyPage model
        shop: Shop domain
        tenant: Tenant instance
        member: Member data dict (or None)
        points_balance: Customer's points balance
        tiers: List of MembershipTier objects
        rewards: List of Reward objects
        referral_program: ReferralProgram instance (or None)

    Returns:
        HTML string
    """
    # Dollar sign for f-string formatting
    dollar = "$"

    # Get active sections sorted by order
    active_sections = [s for s in config.get('sections', []) if s.get('enabled', False)]
    active_sections.sort(key=lambda s: s.get('order', 999))

    # Get colors with defaults
    colors = config.get('colors', {
        'primary': '#e85d27',
        'secondary': '#666666',
        'accent': '#ffd700',
        'background': '#ffffff',
    })

    # Get styles with defaults
    styles = config.get('styles', {
        'fontFamily': 'system-ui',
        'headingFontFamily': '',
        'buttonStyle': 'rounded',
        'buttonSize': 'medium',
        'sectionSpacing': 'normal',
        'borderRadius': 'medium',
    })

    # Get SEO meta tags
    meta = config.get('meta', {
        'title': 'Rewards Program',
        'description': 'Join our rewards program and earn points on every purchase',
    })

    # Map font family to CSS
    font_map = {
        'system-ui': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        'Inter': '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
        'Roboto': '"Roboto", -apple-system, BlinkMacSystemFont, sans-serif',
        'Open Sans': '"Open Sans", -apple-system, BlinkMacSystemFont, sans-serif',
        'Lato': '"Lato", -apple-system, BlinkMacSystemFont, sans-serif',
        'Poppins': '"Poppins", -apple-system, BlinkMacSystemFont, sans-serif',
        'Montserrat': '"Montserrat", -apple-system, BlinkMacSystemFont, sans-serif',
        'Source Sans Pro': '"Source Sans Pro", -apple-system, BlinkMacSystemFont, sans-serif',
        'Nunito': '"Nunito", -apple-system, BlinkMacSystemFont, sans-serif',
        'Playfair Display': '"Playfair Display", Georgia, serif',
        'Oswald': '"Oswald", -apple-system, BlinkMacSystemFont, sans-serif',
    }

    button_radius_map = {
        'square': '0px',
        'rounded': '8px',
        'pill': '999px',
    }

    button_padding_map = {
        'small': '8px 16px',
        'medium': '12px 24px',
        'large': '16px 32px',
    }

    section_padding_map = {
        'compact': '40px 20px',
        'normal': '60px 20px',
        'relaxed': '80px 20px',
    }

    border_radius_map = {
        'none': '0px',
        'small': '4px',
        'medium': '8px',
        'large': '16px',
    }

    # Compute style values
    font_family = styles.get('fontFamily', 'system-ui')
    heading_font = styles.get('headingFontFamily') or font_family

    body_font_css = font_map.get(font_family, font_map['system-ui'])
    heading_font_css = font_map.get(heading_font, body_font_css)
    btn_radius = button_radius_map.get(styles.get('buttonStyle', 'rounded'), '8px')
    btn_padding = button_padding_map.get(styles.get('buttonSize', 'medium'), '12px 24px')
    section_padding = section_padding_map.get(styles.get('sectionSpacing', 'normal'), '60px 20px')
    card_radius = border_radius_map.get(styles.get('borderRadius', 'medium'), '8px')

    # Google Fonts imports for custom fonts
    google_fonts = []
    for font in [font_family, heading_font]:
        if font and font != 'system-ui' and font in font_map:
            google_fonts.append(font.replace(' ', '+'))
    google_fonts_link = ''
    if google_fonts:
        unique_fonts = list(set(google_fonts))
        google_fonts_link = f'<link href="https://fonts.googleapis.com/css2?family={":wght@400;500;600;700&family=".join(unique_fonts)}:wght@400;500;600;700&display=swap" rel="stylesheet">'

    # Build member section for personalization
    member_section = ''
    if member:
        member_section = f'''
        <div class="lp-member-card">
            <div class="lp-member-header">
                <div class="lp-avatar">
                    <span>{member['name'][0].upper()}</span>
                </div>
                <div class="lp-member-info">
                    <h3>Welcome back, {member['name']}!</h3>
                    <p class="lp-tier-badge">{member['tier']}</p>
                </div>
            </div>
            <div class="lp-points-display">
                <div class="lp-points-value">{points_balance:,}</div>
                <div class="lp-points-label">Points Available</div>
            </div>
        </div>
        '''
    else:
        member_section = '''
        <div class="lp-cta-card">
            <h3>Join Our Rewards Program</h3>
            <p>Earn points on every purchase and unlock exclusive rewards!</p>
            <a href="/account/login" class="lp-btn lp-btn-primary">Sign In to Get Started</a>
        </div>
        '''

    # Start building HTML
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>{meta.get("title", "Rewards Program")}</title>',
        f'<meta name="description" content="{meta.get("description", "")}">',
        # Open Graph meta tags for social sharing
        f'<meta property="og:title" content="{meta.get("title", "Rewards Program")}">',
        f'<meta property="og:description" content="{meta.get("description", "")}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:url" content="https://{shop}/apps/rewards">',
        # Twitter card meta tags
        '<meta name="twitter:card" content="summary">',
        f'<meta name="twitter:title" content="{meta.get("title", "Rewards Program")}">',
        f'<meta name="twitter:description" content="{meta.get("description", "")}">',
        google_fonts_link,
        '<style>',
        ':root {',
        f'  --lp-primary: {colors.get("primary", "#e85d27")};',
        f'  --lp-secondary: {colors.get("secondary", "#666666")};',
        f'  --lp-accent: {colors.get("accent", "#ffd700")};',
        f'  --lp-background: {colors.get("background", "#ffffff")};',
        f'  --lp-font-body: {body_font_css};',
        f'  --lp-font-heading: {heading_font_css};',
        f'  --lp-btn-radius: {btn_radius};',
        f'  --lp-btn-padding: {btn_padding};',
        f'  --lp-section-padding: {section_padding};',
        f'  --lp-card-radius: {card_radius};',
        '}',
        '''
        * { box-sizing: border-box; }
        body {
            font-family: var(--lp-font-body);
            margin: 0;
            padding: 0;
            background: var(--lp-background);
            color: #1f2937;
            line-height: 1.5;
        }
        h1, h2, h3, h4, h5, h6 {
            font-family: var(--lp-font-heading);
            margin: 0 0 0.5em 0;
        }
        .lp-container { max-width: 1200px; margin: 0 auto; }

        /* Hero Section */
        .lp-hero {
            padding: 80px 20px;
            text-align: center;
            color: white;
        }
        .lp-hero h1 {
            font-size: 2.5rem;
            margin-bottom: 16px;
        }
        .lp-hero p {
            font-size: 1.25rem;
            opacity: 0.9;
            max-width: 600px;
            margin: 0 auto 24px;
        }

        /* Sections */
        .lp-section {
            padding: var(--lp-section-padding);
            max-width: 1200px;
            margin: 0 auto;
        }
        .lp-section-title {
            font-size: 2rem;
            text-align: center;
            margin-bottom: 40px;
            color: var(--lp-primary);
        }

        /* Buttons */
        .lp-btn {
            display: inline-block;
            padding: var(--lp-btn-padding);
            border-radius: var(--lp-btn-radius);
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            cursor: pointer;
            border: none;
            font-family: var(--lp-font-body);
        }
        .lp-btn-primary {
            background: var(--lp-primary);
            color: white;
        }
        .lp-btn-primary:hover {
            opacity: 0.9;
            transform: translateY(-2px);
        }
        .lp-btn-secondary {
            background: white;
            color: var(--lp-primary);
            border: 2px solid var(--lp-primary);
        }

        /* Member Card */
        .lp-member-card {
            background: white;
            border-radius: var(--lp-card-radius);
            padding: 32px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            margin: -60px auto 40px;
            max-width: 500px;
            position: relative;
            z-index: 10;
        }
        .lp-member-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 24px;
        }
        .lp-avatar {
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--lp-primary), var(--lp-accent));
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.5rem;
            font-weight: 600;
        }
        .lp-member-info h3 { margin: 0 0 4px 0; font-size: 1.25rem; }
        .lp-tier-badge {
            display: inline-block;
            padding: 4px 12px;
            background: #f3f4f6;
            border-radius: 20px;
            font-size: 0.875rem;
            color: var(--lp-primary);
            font-weight: 500;
            margin: 0;
        }
        .lp-points-display {
            text-align: center;
            padding: 24px;
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border-radius: var(--lp-card-radius);
        }
        .lp-points-value {
            font-size: 3rem;
            font-weight: 700;
            color: var(--lp-primary);
            line-height: 1;
        }
        .lp-points-label {
            font-size: 0.875rem;
            color: #6b7280;
            margin-top: 8px;
        }

        /* CTA Card */
        .lp-cta-card {
            background: white;
            border-radius: var(--lp-card-radius);
            padding: 40px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            margin: -60px auto 40px;
            max-width: 500px;
            position: relative;
            z-index: 10;
            text-align: center;
        }
        .lp-cta-card h3 { margin: 0 0 12px 0; font-size: 1.5rem; }
        .lp-cta-card p { color: #6b7280; margin: 0 0 24px 0; }

        /* Steps (How It Works) */
        .lp-steps {
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
        }
        .lp-step {
            text-align: center;
            max-width: 250px;
            background: white;
            padding: 30px;
            border-radius: var(--lp-card-radius);
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }
        .lp-step-icon {
            font-size: 2.5rem;
            margin-bottom: 16px;
        }
        .lp-step h4 {
            color: var(--lp-primary);
            margin-bottom: 8px;
        }
        .lp-step p {
            color: #6b7280;
            font-size: 0.9rem;
            margin: 0;
        }

        /* Tiers Grid */
        .lp-tiers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 24px;
        }
        .lp-tier-card {
            background: white;
            border-radius: var(--lp-card-radius);
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border: 2px solid transparent;
            transition: all 0.2s ease;
        }
        .lp-tier-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }
        .lp-tier-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .lp-tier-header h4 { margin: 0; font-size: 1.25rem; }
        .lp-tier-benefits { list-style: none; padding: 0; margin: 0; }
        .lp-tier-benefits li {
            padding: 8px 0;
            border-bottom: 1px solid #e5e7eb;
            font-size: 0.875rem;
        }
        .lp-tier-benefits li:last-child { border-bottom: none; }
        .lp-tier-benefits strong { color: var(--lp-primary); }

        /* Rewards Grid */
        .lp-rewards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 24px;
        }
        .lp-reward-card {
            background: white;
            border-radius: var(--lp-card-radius);
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            transition: all 0.2s ease;
        }
        .lp-reward-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }
        .lp-reward-placeholder {
            width: 100%;
            height: 160px;
            background: linear-gradient(135deg, var(--lp-primary), var(--lp-accent));
        }
        .lp-reward-content { padding: 20px; }
        .lp-reward-content h4 { margin: 0 0 8px 0; font-size: 1.125rem; }
        .lp-reward-points {
            font-weight: 600;
            color: var(--lp-primary);
        }

        /* FAQ */
        .lp-faq-item {
            background: #f9fafb;
            padding: 20px;
            margin-bottom: 12px;
            border-radius: var(--lp-card-radius);
        }
        .lp-faq-item strong { color: var(--lp-primary); display: block; margin-bottom: 8px; }
        .lp-faq-item p { margin: 0; color: #4b5563; }

        /* Referral Banner */
        .lp-referral-banner {
            background: linear-gradient(135deg, var(--lp-primary), var(--lp-accent));
            border-radius: var(--lp-card-radius);
            padding: 40px;
            text-align: center;
            color: white;
        }
        .lp-referral-banner h2 { color: white; margin-bottom: 16px; }
        .lp-referral-banner p { margin: 0 0 24px 0; opacity: 0.9; }

        /* Footer */
        .lp-footer {
            text-align: center;
            padding: 40px 20px;
            color: #6b7280;
            font-size: 0.875rem;
        }
        .lp-footer a { color: var(--lp-primary); text-decoration: none; }

        /* Responsive */
        @media (max-width: 768px) {
            .lp-hero h1 { font-size: 1.875rem; }
            .lp-hero p { font-size: 1rem; }
            .lp-member-card, .lp-cta-card {
                margin: -40px 16px 30px;
                padding: 24px;
            }
            .lp-points-value { font-size: 2.5rem; }
            .lp-steps { flex-direction: column; align-items: center; }
            .lp-step { max-width: 100%; }
        }
        ''',
        config.get('custom_css', ''),
        '</style>',
        '</head>',
        '<body>',
    ]

    # Render sections
    for section in active_sections:
        section_type = section.get('type')
        settings = section.get('settings', {})

        if section_type == 'hero':
            bg_color = settings.get('background_color', colors.get('primary', '#e85d27'))
            text_color = settings.get('text_color', '#ffffff')
            html_parts.append(f'''
            <div class="lp-hero" style="background: {bg_color}; color: {text_color};">
                <h1>{settings.get("title", "Join Our Rewards Program")}</h1>
                <p>{settings.get("subtitle", "Earn points on every purchase")}</p>
                <a href="{settings.get("cta_link", "/account/register")}" class="lp-btn" style="background: {text_color}; color: {bg_color};">{settings.get("cta_text", "Join Now")}</a>
            </div>
            {member_section}
            ''')

        elif section_type == 'how_it_works':
            steps_html = ''
            icon_map = {
                'star': '&#11088;', 'shopping-cart': '&#128722;', 'gift': '&#127873;',
                'user-plus': '&#128100;', 'shopping-bag': '&#128092;', 'arrow-up-circle': '&#9650;',
                'check-circle': '&#10004;', 'coins': '&#128176;', 'sparkles': '&#10024;',
                'trophy': '&#127942;', 'zap': '&#9889;', 'award': '&#127941;',
            }
            for step in settings.get('steps', []):
                icon = icon_map.get(step.get('icon', 'star'), '&#11088;')
                steps_html += f'''
                <div class="lp-step">
                    <div class="lp-step-icon">{icon}</div>
                    <h4>{step.get("title", "")}</h4>
                    <p>{step.get("description", "")}</p>
                </div>
                '''
            html_parts.append(f'''
            <div class="lp-section">
                <h2 class="lp-section-title">{settings.get("title", "How It Works")}</h2>
                <div class="lp-steps">{steps_html}</div>
            </div>
            ''')

        elif section_type == 'tier_comparison':
            # Render live tier data
            tiers_html = ''
            for tier in tiers:
                earning_mult = getattr(tier, 'points_earning_multiplier', 1) or 1
                cashback = getattr(tier, 'purchase_cashback_pct', 0) or 0
                trade_bonus = getattr(tier, 'trade_in_bonus_pct', 0) or 0
                monthly_credit = getattr(tier, 'monthly_credit_amount', 0) or 0

                tiers_html += f'''
                <div class="lp-tier-card">
                    <div class="lp-tier-header">
                        <h4>{tier.name}</h4>
                    </div>
                    <ul class="lp-tier-benefits">
                        <li><strong>{earning_mult}x</strong> points on purchases</li>
                        {f'<li><strong>{cashback}%</strong> cashback</li>' if cashback else ''}
                        {f'<li><strong>{trade_bonus}%</strong> trade-in bonus</li>' if trade_bonus else ''}
                        {f'<li><strong>{dollar}{monthly_credit:.0f}</strong> monthly credit</li>' if monthly_credit else ''}
                    </ul>
                </div>
                '''

            html_parts.append(f'''
            <div class="lp-section">
                <h2 class="lp-section-title">{settings.get("title", "Membership Tiers")}</h2>
                <div class="lp-tiers-grid">{tiers_html}</div>
            </div>
            ''')

        elif section_type == 'rewards_catalog':
            # Render live rewards data
            max_items = settings.get('max_items', 6)
            display_rewards = rewards[:max_items] if rewards else []
            rewards_html = ''

            for reward in display_rewards:
                rewards_html += f'''
                <div class="lp-reward-card">
                    <div class="lp-reward-placeholder"></div>
                    <div class="lp-reward-content">
                        <h4>{reward.name}</h4>
                        <span class="lp-reward-points">{reward.points_cost:,} pts</span>
                    </div>
                </div>
                '''

            if not rewards_html:
                rewards_html = '<p style="text-align: center; color: #6b7280;">No rewards available yet.</p>'

            html_parts.append(f'''
            <div class="lp-section">
                <h2 class="lp-section-title">{settings.get("title", "Available Rewards")}</h2>
                <div class="lp-rewards-grid">{rewards_html}</div>
            </div>
            ''')

        elif section_type == 'earning_rules':
            html_parts.append(f'''
            <div class="lp-section">
                <h2 class="lp-section-title">{settings.get("title", "Ways to Earn")}</h2>
                <div class="lp-steps">
                    <div class="lp-step">
                        <div class="lp-step-icon">&#128722;</div>
                        <h4>Shop & Earn</h4>
                        <p>Earn points on every purchase</p>
                    </div>
                    <div class="lp-step">
                        <div class="lp-step-icon">&#127873;</div>
                        <h4>Trade-Ins</h4>
                        <p>Earn bonus points when you trade in items</p>
                    </div>
                    <div class="lp-step">
                        <div class="lp-step-icon">&#128101;</div>
                        <h4>Referrals</h4>
                        <p>Get rewarded when friends join</p>
                    </div>
                </div>
            </div>
            ''')

        elif section_type == 'faq':
            faq_html = ''
            for item in settings.get('items', []):
                faq_html += f'''
                <div class="lp-faq-item">
                    <strong>{item.get("question", "")}</strong>
                    <p>{item.get("answer", "")}</p>
                </div>
                '''
            html_parts.append(f'''
            <div class="lp-section">
                <h2 class="lp-section-title">{settings.get("title", "FAQ")}</h2>
                {faq_html}
            </div>
            ''')

        elif section_type == 'referral_banner':
            cta_link = '/account' if member else '/account/login'
            cta_text = 'Get Your Referral Link' if member else 'Sign In to Refer Friends'
            html_parts.append(f'''
            <div class="lp-section">
                <div class="lp-referral-banner">
                    <h2>{settings.get("title", "Refer Friends & Earn")}</h2>
                    <p>{settings.get("description", "Share with friends and earn rewards")}</p>
                    <a href="{cta_link}" class="lp-btn" style="background: white; color: var(--lp-primary);">{cta_text}</a>
                </div>
            </div>
            ''')

    # Footer
    html_parts.extend([
        '<footer class="lp-footer">',
        '<p>Powered by <a href="https://cardflowlabs.com" target="_blank" rel="noopener">TradeUp</a></p>',
        '</footer>',
    ])

    # Add analytics tracking script
    tracking_script = get_analytics_tracking_script(shop, member)
    html_parts.append(tracking_script)

    html_parts.extend([
        '</body>',
        '</html>',
    ])

    return '\n'.join(html_parts)


def get_analytics_tracking_script(shop: str, member: dict = None) -> str:
    """
    Generate JavaScript tracking script for the loyalty page.

    Tracks:
    - Page views (with device type, referrer, UTM params)
    - Section engagement (scroll depth, time in view)
    - CTA clicks (button clicks with context)

    Args:
        shop: Shop domain (e.g., 'store.myshopify.com')
        member: Member data dict (or None for guests)

    Returns:
        HTML script tag with tracking code
    """
    import os
    import json

    # Get the app URL for API calls
    app_url = os.getenv('APP_URL', 'https://app.cardflowlabs.com')

    # Member info for tracking (anonymized)
    member_id = member.get('member_id') if member else None
    is_member = member is not None

    return f'''
<!-- TradeUp Analytics Tracking -->
<script>
(function() {{
    'use strict';

    // Configuration
    var CONFIG = {{
        shop: '{shop}',
        apiUrl: '{app_url}/api/loyalty-page/analytics',
        memberId: {json.dumps(member_id)},
        isMember: {json.dumps(is_member)},
        sessionId: null
    }};

    // Generate or retrieve session ID
    function getSessionId() {{
        var key = 'tradeup_session_id';
        var id = sessionStorage.getItem(key);
        if (!id) {{
            id = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            sessionStorage.setItem(key, id);
        }}
        return id;
    }}

    // Detect device type
    function getDeviceType() {{
        var ua = navigator.userAgent;
        if (/tablet|ipad|playbook|silk/i.test(ua)) return 'tablet';
        if (/mobile|iphone|ipod|android|blackberry|opera mini|iemobile/i.test(ua)) return 'mobile';
        return 'desktop';
    }}

    // Get UTM parameters from URL
    function getUtmParams() {{
        var params = new URLSearchParams(window.location.search);
        return {{
            utm_source: params.get('utm_source'),
            utm_medium: params.get('utm_medium'),
            utm_campaign: params.get('utm_campaign')
        }};
    }}

    // Send tracking data
    function track(endpoint, data) {{
        var payload = Object.assign({{}}, data, {{
            shop: CONFIG.shop,
            session_id: CONFIG.sessionId,
            member_id: CONFIG.memberId,
            is_member: CONFIG.isMember
        }});

        // Use sendBeacon if available (reliable for page unload)
        if (navigator.sendBeacon) {{
            navigator.sendBeacon(CONFIG.apiUrl + endpoint, JSON.stringify(payload));
        }} else {{
            fetch(CONFIG.apiUrl + endpoint, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload),
                keepalive: true
            }}).catch(function() {{}});
        }}
    }}

    // Track page view
    function trackPageView() {{
        var utmParams = getUtmParams();
        track('/track/view', {{
            device_type: getDeviceType(),
            browser: navigator.userAgent.split(' ').pop().split('/')[0],
            referrer: document.referrer || null,
            utm_source: utmParams.utm_source,
            utm_medium: utmParams.utm_medium,
            utm_campaign: utmParams.utm_campaign
        }});
    }}

    // Track section visibility and scroll depth
    function setupScrollTracking() {{
        var sections = document.querySelectorAll('[class*="lp-section"], .lp-hero, [class*="section"]');
        var sectionData = {{}};
        var lastScrollDepth = 0;

        // Initialize section data
        sections.forEach(function(section, index) {{
            var id = section.id || section.className.match(/lp-(\\w+)/)?.[1] || 'section_' + index;
            sectionData[id] = {{
                section_id: id,
                section_type: section.className.match(/lp-(\\w+)/)?.[1] || 'unknown',
                time_in_view_seconds: 0,
                scroll_depth_percent: 0,
                was_visible: false,
                lastVisible: null
            }};
        }});

        // Intersection Observer for section visibility
        var observer = new IntersectionObserver(function(entries) {{
            entries.forEach(function(entry) {{
                var id = entry.target.id || entry.target.className.match(/lp-(\\w+)/)?.[1] || 'unknown';
                if (sectionData[id]) {{
                    if (entry.isIntersecting) {{
                        sectionData[id].was_visible = true;
                        sectionData[id].lastVisible = Date.now();
                        // Calculate scroll depth
                        var rect = entry.target.getBoundingClientRect();
                        var visible = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0);
                        var percent = Math.round((visible / rect.height) * 100);
                        sectionData[id].scroll_depth_percent = Math.max(sectionData[id].scroll_depth_percent, percent);
                    }} else if (sectionData[id].lastVisible) {{
                        sectionData[id].time_in_view_seconds += Math.round((Date.now() - sectionData[id].lastVisible) / 1000);
                        sectionData[id].lastVisible = null;
                    }}
                }}
            }});
        }}, {{ threshold: [0, 0.25, 0.5, 0.75, 1] }});

        sections.forEach(function(section) {{
            observer.observe(section);
        }});

        // Track overall scroll depth
        window.addEventListener('scroll', function() {{
            var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            var docHeight = document.documentElement.scrollHeight - window.innerHeight;
            var scrollPercent = Math.round((scrollTop / docHeight) * 100);
            lastScrollDepth = Math.max(lastScrollDepth, scrollPercent);
        }});

        // Send engagement data on page unload
        window.addEventListener('beforeunload', function() {{
            // Finalize time tracking
            Object.keys(sectionData).forEach(function(id) {{
                if (sectionData[id].lastVisible) {{
                    sectionData[id].time_in_view_seconds += Math.round((Date.now() - sectionData[id].lastVisible) / 1000);
                }}
            }});

            var sections = Object.values(sectionData).filter(function(s) {{ return s.was_visible; }});
            if (sections.length > 0) {{
                track('/track/engagement', {{ sections: sections }});
            }}
        }});
    }}

    // Track CTA clicks
    function setupClickTracking() {{
        document.addEventListener('click', function(e) {{
            var target = e.target.closest('a, button, [role="button"], .lp-btn');
            if (!target) return;

            var ctaId = target.id || target.className.match(/lp-(\\w+-?\\w*)/)?.[0] || 'unknown_cta';
            var ctaText = target.textContent.trim().substring(0, 200);
            var ctaUrl = target.href || target.dataset.href || null;
            var section = target.closest('[class*="lp-section"], .lp-hero, [class*="section"]');
            var sectionId = section ? (section.id || section.className.match(/lp-(\\w+)/)?.[1] || 'unknown') : null;

            track('/track/click', {{
                cta_id: ctaId,
                cta_text: ctaText,
                cta_url: ctaUrl,
                section_id: sectionId
            }});
        }});
    }}

    // Initialize tracking
    function init() {{
        CONFIG.sessionId = getSessionId();

        // Track page view immediately
        trackPageView();

        // Setup engagement tracking after page load
        if (document.readyState === 'complete') {{
            setupScrollTracking();
            setupClickTracking();
        }} else {{
            window.addEventListener('load', function() {{
                setupScrollTracking();
                setupClickTracking();
            }});
        }}
    }}

    // Start tracking
    init();
}})();
</script>
'''


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

    # Pre-build conditional HTML sections (avoids nested f-string issues)
    if valid_code:
        rewards_display_html = f'''
        <div class="rewards-display">
            <div class="reward-item">
                <span class="reward-amount">{referee_reward_str}</span>
                <span class="reward-label">for you</span>
            </div>
            <div class="reward-divider">+</div>
            <div class="reward-item">
                <span class="reward-amount">{referrer_reward_str}</span>
                <span class="reward-label">for {referrer_name}</span>
            </div>
        </div>'''
        referral_code_html = f'''
            <div class="referral-code-display">
                <div class="referral-code-label">Your referral code</div>
                <div class="referral-code-value">{code.upper()}</div>
            </div>'''
        social_share_html = f'''
        <div class="social-share">
            <a href="https://www.facebook.com/sharer/sharer.php?u={shop_url}/apps/rewards/refer/{code}" target="_blank" class="social-btn social-facebook" title="Share on Facebook">f</a>
            <a href="https://twitter.com/intent/tweet?text=Get%20{referee_reward_str}%20off%20at%20our%20favorite%20store!&url={shop_url}/apps/rewards/refer/{code}" target="_blank" class="social-btn social-twitter" title="Share on Twitter">t</a>
            <a href="https://wa.me/?text=Get%20{referee_reward_str}%20off%20with%20my%20referral%20link!%20{shop_url}/apps/rewards/refer/{code}" target="_blank" class="social-btn social-whatsapp" title="Share on WhatsApp">w</a>
            <a href="mailto:?subject=You%27re%20Invited!&body=Get%20{referee_reward_str}%20off%20your%20first%20order:%20{shop_url}/apps/rewards/refer/{code}" class="social-btn social-email" title="Share via Email">&#9993;</a>
        </div>'''
        terms_text = 'Code will be automatically applied at checkout. Valid for new customers only. Cannot be combined with other offers.'
        cta_url = f'{shop_url}?ref={code}'
    else:
        rewards_display_html = ''
        referral_code_html = ''
        social_share_html = ''
        terms_text = 'Visit our store to browse our collection.'
        cta_url = shop_url

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

        {rewards_display_html}

        <div class="referral-body">
            {referral_code_html}

            <a href="{cta_url}" class="cta-button">{cta_text}</a>

            <p class="terms">
                {terms_text}
            </p>
        </div>

        {social_share_html}
    </div>
</body>
</html>'''

    return html
