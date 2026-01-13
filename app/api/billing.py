"""
Billing API endpoints for TradeUp.
Handles subscription management via Shopify Billing API.
"""
import os
from flask import Blueprint, request, jsonify, url_for, g
from ..services.shopify_billing import (
    ShopifyBillingService,
    get_plan_config,
    get_all_plans,
    TRADEUP_PLANS
)
from ..models import Tenant, BillingHistory
from ..extensions import db
from ..middleware.shopify_auth import require_shopify_auth
from datetime import datetime, timedelta

billing_bp = Blueprint('billing', __name__)


@billing_bp.route('/plans', methods=['GET'])
def list_plans():
    """
    List all available subscription plans.

    Returns:
        List of plans with features and pricing
    """
    plans = []
    for key, config in TRADEUP_PLANS.items():
        plans.append({
            'key': key,
            'name': config['name'],
            'price': config['price'],
            'max_members': config['max_members'],
            'max_tiers': config['max_tiers'],
            'features': config['features']
        })

    return jsonify({
        'plans': sorted(plans, key=lambda x: x['price']),
        'currency': 'USD',
        'billing_interval': 'monthly'
    })


@billing_bp.route('/subscribe', methods=['POST'])
@require_shopify_auth
def create_subscription():
    """
    Create a new subscription for the tenant.

    Request body:
        plan: Plan key (starter, growth, pro)

    Returns:
        Confirmation URL to redirect merchant for approval
    """
    tenant = g.tenant

    data = request.get_json() or {}
    plan_key = data.get('plan', 'starter')

    plan = get_plan_config(plan_key)
    if not plan:
        return jsonify({'error': f'Invalid plan: {plan_key}'}), 400

    # Check if already subscribed
    if tenant.subscription_active:
        return jsonify({
            'error': 'Already subscribed',
            'current_plan': tenant.subscription_plan
        }), 400

    # Create Shopify billing service
    if not tenant.shopify_domain or not tenant.shopify_access_token:
        return jsonify({'error': 'Shopify not connected'}), 400

    billing = ShopifyBillingService(
        tenant.shopify_domain,
        tenant.shopify_access_token
    )

    # Build return URL
    base_url = os.getenv('APP_URL', 'https://gettradeup.com')
    return_url = f"{base_url}/billing/callback?tenant_id={tenant.id}"

    try:
        result = billing.create_subscription(
            plan_name=plan['name'],
            price=plan['price'],
            return_url=return_url,
            trial_days=7
        )

        # Store subscription ID for tracking
        if result.get('subscription'):
            tenant.shopify_subscription_id = result['subscription']['id']
            tenant.subscription_plan = plan_key
            tenant.subscription_status = 'pending'
            db.session.commit()

        return jsonify({
            'success': True,
            'confirmation_url': result['confirmation_url'],
            'plan': plan_key,
            'message': 'Redirect merchant to confirmation_url to approve subscription'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@billing_bp.route('/callback', methods=['GET'])
def billing_callback():
    """
    Handle redirect after merchant approves/declines subscription.

    Query params:
        tenant_id: Tenant ID
        charge_id: Shopify charge ID (optional)

    Note: This is a Shopify redirect callback so standard auth can't be used.
    We validate tenant existence and active status instead.
    """
    tenant_id = request.args.get('tenant_id')
    if not tenant_id:
        return jsonify({'error': 'Missing tenant_id'}), 400

    try:
        tenant_id_int = int(tenant_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid tenant_id'}), 400

    tenant = Tenant.query.get(tenant_id_int)
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Validate tenant has valid Shopify credentials
    if not tenant.shopify_domain or not tenant.shopify_access_token:
        return jsonify({'error': 'Tenant not properly configured'}), 400

    if not tenant.is_active:
        return jsonify({'error': 'Tenant is not active'}), 403

    # Check subscription status
    billing = ShopifyBillingService(
        tenant.shopify_domain,
        tenant.shopify_access_token
    )

    try:
        subscriptions = billing.get_active_subscriptions()

        if subscriptions:
            # Subscription was approved
            active_sub = subscriptions[0]
            tenant.shopify_subscription_id = active_sub['id']
            tenant.subscription_status = 'active'
            tenant.subscription_active = True

            # Set limits based on plan
            plan = get_plan_config(tenant.subscription_plan)
            if plan:
                tenant.max_members = plan['max_members']
                tenant.max_tiers = plan['max_tiers']
                tenant.monthly_price = plan['price']

            db.session.commit()

            return jsonify({
                'success': True,
                'status': 'active',
                'plan': tenant.subscription_plan,
                'message': 'Subscription activated!'
            })
        else:
            # Subscription was declined
            tenant.subscription_status = 'declined'
            tenant.subscription_active = False
            db.session.commit()

            return jsonify({
                'success': False,
                'status': 'declined',
                'message': 'Subscription was declined by merchant'
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@billing_bp.route('/status', methods=['GET'])
@require_shopify_auth
def subscription_status():
    """
    Get current subscription status for tenant.

    Returns:
        Current plan, status, and usage
    """
    tenant = g.tenant

    # Get member count for usage tracking
    from ..models import Member
    member_count = Member.query.filter_by(
        tenant_id=tenant.id,
        status='active'
    ).count()

    tier_count = tenant.membership_tiers.count()

    # Calculate usage percentages and warnings
    member_pct = (member_count / tenant.max_members * 100) if tenant.max_members else 0
    tier_pct = (tier_count / tenant.max_tiers * 100) if tenant.max_tiers else 0

    def get_usage_warning(percentage: float, current: int, limit: int) -> dict:
        """Get usage warning level and message."""
        if limit is None or limit == 0:
            return {'level': None, 'message': None}  # Unlimited
        if percentage >= 100:
            return {
                'level': 'critical',
                'message': f'Limit reached ({current}/{limit}). Upgrade to add more.'
            }
        elif percentage >= 90:
            return {
                'level': 'warning',
                'message': f'Approaching limit ({current}/{limit}). Consider upgrading soon.'
            }
        elif percentage >= 80:
            return {
                'level': 'caution',
                'message': f'Usage at {percentage:.0f}% ({current}/{limit}).'
            }
        return {'level': None, 'message': None}

    member_warning = get_usage_warning(member_pct, member_count, tenant.max_members)
    tier_warning = get_usage_warning(tier_pct, tier_count, tenant.max_tiers)

    return jsonify({
        'plan': tenant.subscription_plan,
        'status': tenant.subscription_status,
        'active': tenant.subscription_active,
        'trial_ends_at': tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
        'current_period_end': tenant.current_period_end.isoformat() if tenant.current_period_end else None,
        'usage': {
            'members': {
                'current': member_count,
                'limit': tenant.max_members,
                'percentage': member_pct,
                'warning': member_warning
            },
            'tiers': {
                'current': tier_count,
                'limit': tenant.max_tiers,
                'percentage': tier_pct,
                'warning': tier_warning
            }
        },
        'warnings': {
            'has_warnings': member_warning['level'] is not None or tier_warning['level'] is not None,
            'members': member_warning,
            'tiers': tier_warning
        }
    })


@billing_bp.route('/upgrade', methods=['POST'])
@require_shopify_auth
def upgrade_subscription():
    """
    Upgrade or downgrade subscription plan.

    Request body:
        plan: New plan key
    """
    tenant = g.tenant

    if not tenant.subscription_active:
        return jsonify({'error': 'No active subscription to upgrade'}), 400

    data = request.get_json() or {}
    new_plan_key = data.get('plan')

    if not new_plan_key:
        return jsonify({'error': 'Plan required'}), 400

    new_plan = get_plan_config(new_plan_key)
    if not new_plan:
        return jsonify({'error': f'Invalid plan: {new_plan_key}'}), 400

    if new_plan_key == tenant.subscription_plan:
        return jsonify({'error': 'Already on this plan'}), 400

    billing = ShopifyBillingService(
        tenant.shopify_domain,
        tenant.shopify_access_token
    )

    base_url = os.getenv('APP_URL', 'https://gettradeup.com')
    return_url = f"{base_url}/billing/callback?tenant_id={tenant.id}"

    try:
        result = billing.upgrade_subscription(
            current_subscription_id=tenant.shopify_subscription_id,
            new_plan_name=new_plan['name'],
            new_price=new_plan['price'],
            return_url=return_url
        )

        # Update tenant with new plan (pending approval)
        tenant.subscription_plan = new_plan_key
        tenant.subscription_status = 'pending'
        db.session.commit()

        return jsonify({
            'success': True,
            'confirmation_url': result['confirmation_url'],
            'new_plan': new_plan_key,
            'message': 'Redirect merchant to approve plan change'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@billing_bp.route('/cancel', methods=['POST'])
@require_shopify_auth
def cancel_subscription():
    """
    Cancel the current subscription.
    """
    tenant = g.tenant

    if not tenant.subscription_active:
        return jsonify({'error': 'No active subscription'}), 400

    billing = ShopifyBillingService(
        tenant.shopify_domain,
        tenant.shopify_access_token
    )

    try:
        result = billing.cancel_subscription(tenant.shopify_subscription_id)

        # Record cancellation in billing history
        _record_billing_event(
            tenant_id=tenant.id,
            event_type='subscription_cancelled',
            description=f'Subscription cancelled from {tenant.subscription_plan} plan',
            plan_from=tenant.subscription_plan,
        )

        tenant.subscription_status = 'cancelled'
        tenant.subscription_active = False
        db.session.commit()

        return jsonify({
            'success': True,
            'status': 'cancelled',
            'message': 'Subscription cancelled'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _record_billing_event(tenant_id: int, event_type: str, description: str,
                          plan_from: str = None, plan_to: str = None,
                          amount: float = None, extra_data: dict = None):
    """Helper to record billing history events."""
    history = BillingHistory(
        tenant_id=tenant_id,
        event_type=event_type,
        event_description=description,
        plan_from=plan_from,
        plan_to=plan_to,
        amount=amount,
        extra_data=extra_data or {}
    )
    db.session.add(history)
    return history


@billing_bp.route('/schedule-downgrade', methods=['POST'])
@require_shopify_auth
def schedule_downgrade():
    """
    Schedule a plan downgrade to take effect at end of billing cycle.

    Request body:
        plan: New plan key to downgrade to

    Returns:
        Scheduled change details
    """
    tenant = g.tenant

    if not tenant.subscription_active:
        return jsonify({'error': 'No active subscription'}), 400

    data = request.get_json() or {}
    new_plan_key = data.get('plan')

    if not new_plan_key:
        return jsonify({'error': 'Plan required'}), 400

    new_plan = get_plan_config(new_plan_key)
    if not new_plan:
        return jsonify({'error': f'Invalid plan: {new_plan_key}'}), 400

    current_plan = get_plan_config(tenant.subscription_plan)

    # Check if this is actually a downgrade
    if new_plan['price'] >= current_plan['price']:
        return jsonify({
            'error': 'This is not a downgrade. Use /upgrade for upgrades.'
        }), 400

    if new_plan_key == tenant.subscription_plan:
        return jsonify({'error': 'Already on this plan'}), 400

    # Schedule the downgrade for end of current billing period
    # Use current_period_end if set, otherwise estimate 30 days from now
    scheduled_date = tenant.current_period_end or (datetime.utcnow() + timedelta(days=30))

    tenant.scheduled_plan_change = new_plan_key
    tenant.scheduled_plan_change_date = scheduled_date

    # Record in billing history
    _record_billing_event(
        tenant_id=tenant.id,
        event_type='downgrade_scheduled',
        description=f'Downgrade scheduled from {tenant.subscription_plan} to {new_plan_key}',
        plan_from=tenant.subscription_plan,
        plan_to=new_plan_key,
        extra_data={'scheduled_date': scheduled_date.isoformat()}
    )

    db.session.commit()

    return jsonify({
        'success': True,
        'scheduled_plan': new_plan_key,
        'scheduled_date': scheduled_date.isoformat(),
        'current_plan': tenant.subscription_plan,
        'message': f'Downgrade to {new_plan["name"]} scheduled for {scheduled_date.strftime("%B %d, %Y")}'
    })


@billing_bp.route('/cancel-scheduled-change', methods=['POST'])
@require_shopify_auth
def cancel_scheduled_change():
    """
    Cancel a scheduled plan change (downgrade).
    """
    tenant = g.tenant

    if not tenant.scheduled_plan_change:
        return jsonify({'error': 'No scheduled plan change'}), 400

    old_scheduled_plan = tenant.scheduled_plan_change

    # Record cancellation in history
    _record_billing_event(
        tenant_id=tenant.id,
        event_type='scheduled_change_cancelled',
        description=f'Cancelled scheduled downgrade to {old_scheduled_plan}',
        plan_from=tenant.subscription_plan,
        plan_to=old_scheduled_plan,
    )

    tenant.scheduled_plan_change = None
    tenant.scheduled_plan_change_date = None
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Scheduled plan change cancelled',
        'current_plan': tenant.subscription_plan
    })


@billing_bp.route('/history', methods=['GET'])
@require_shopify_auth
def billing_history():
    """
    Get billing history for the tenant.

    Query params:
        page: Page number (default: 1)
        per_page: Items per page (default: 20, max: 100)

    Returns:
        Billing history events
    """
    tenant = g.tenant

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    history = BillingHistory.query.filter_by(tenant_id=tenant.id)\
        .order_by(BillingHistory.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'history': [h.to_dict() for h in history.items],
        'total': history.total,
        'page': page,
        'per_page': per_page,
        'pages': history.pages
    })
