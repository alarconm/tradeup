"""
Shopify Flow API Routes.

Handles Flow action requests from Shopify Flow workflows.
Flow actions allow merchants to automate loyalty operations.

TRIGGER SCHEMAS (GET endpoints):
- GET /flow/triggers/points-earned - Points earned trigger schema
- GET /flow/triggers/points-redeemed - Points redeemed trigger schema
- GET /flow/triggers/tier-upgraded - Tier upgraded trigger schema
- GET /flow/triggers/tier-downgraded - Tier downgraded trigger schema
- GET /flow/triggers/reward-unlocked - Reward unlocked trigger schema
- GET /flow/triggers/member-enrolled - Member enrolled trigger schema
- GET /flow/triggers/trade-in-completed - Trade-in completed trigger schema
- GET /flow/triggers/credit-issued - Store credit issued trigger schema

ACTIONS (POST endpoints):
- POST /flow/actions/add-credit - Add store credit to a customer
- POST /flow/actions/change-tier - Change a member's tier
- POST /flow/actions/get-member - Get member information
- POST /flow/actions/award-bonus-points - Award bonus points to customer
- POST /flow/actions/send-tier-upgrade-email - Send tier upgrade notification
- POST /flow/actions/create-reward-reminder - Send reward reminder
- POST /flow/actions/get-points-balance - Get customer's points balance
"""
from flask import Blueprint, request, jsonify, g
from functools import wraps
import hmac
import hashlib
import base64

from ..middleware.shopify_auth import require_shopify_auth, get_shop_from_request
from ..models import Tenant

flow_bp = Blueprint('flow', __name__)


def require_flow_auth(f):
    """
    Authenticate Shopify Flow requests.

    Flow requests include HMAC signature for verification.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get shop from request
        shop = get_shop_from_request()
        if not shop:
            # Try to get from request body
            data = request.get_json(silent=True) or {}
            shop = data.get('shop_domain') or data.get('shopDomain')

        if not shop:
            return jsonify({'error': 'Shop domain required'}), 400

        tenant = Tenant.query.filter_by(shopify_domain=shop).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404

        g.tenant_id = tenant.id
        g.tenant = tenant
        g.shop = shop

        # Verify HMAC if present
        hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
        if hmac_header and tenant.shopify_secret:
            body = request.get_data()
            computed = base64.b64encode(
                hmac.new(
                    tenant.shopify_secret.encode('utf-8'),
                    body,
                    hashlib.sha256
                ).digest()
            ).decode('utf-8')

            if not hmac.compare_digest(computed, hmac_header):
                return jsonify({'error': 'Invalid signature'}), 401

        return f(*args, **kwargs)

    return decorated_function


# ==================== Flow Actions ====================

@flow_bp.route('/actions/add-credit', methods=['POST'])
@require_flow_auth
def action_add_credit():
    """
    Flow Action: Add store credit to a customer.

    Request body:
        customer_email: Email of the customer
        amount: Credit amount to add
        reason: Optional reason/description

    Returns:
        success: Whether credit was added
        new_balance: Updated credit balance
    """
    data = request.get_json()

    customer_email = data.get('customer_email') or data.get('customerEmail')
    amount = data.get('amount')
    reason = data.get('reason', 'Shopify Flow automation')

    if not customer_email:
        return jsonify({
            'success': False,
            'error': 'customer_email is required'
        }), 400

    if not amount or float(amount) <= 0:
        return jsonify({
            'success': False,
            'error': 'Valid amount is required'
        }), 400

    try:
        from ..services.flow_service import FlowService
        from ..services.shopify_client import ShopifyClient

        client = ShopifyClient(g.tenant_id)
        flow_svc = FlowService(g.tenant_id, client)

        result = flow_svc.action_add_credit(
            customer_email=customer_email,
            amount=float(amount),
            reason=reason
        )

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@flow_bp.route('/actions/change-tier', methods=['POST'])
@require_flow_auth
def action_change_tier():
    """
    Flow Action: Change a member's tier.

    Request body:
        customer_email: Email of the customer
        new_tier: Name of the new tier (Bronze, Silver, Gold)
        reason: Optional reason for the change

    Returns:
        success: Whether tier was changed
        old_tier: Previous tier name
        new_tier: New tier name
    """
    data = request.get_json()

    customer_email = data.get('customer_email') or data.get('customerEmail')
    new_tier = data.get('new_tier') or data.get('newTier') or data.get('tier')
    reason = data.get('reason', 'Shopify Flow automation')

    if not customer_email:
        return jsonify({
            'success': False,
            'error': 'customer_email is required'
        }), 400

    if not new_tier:
        return jsonify({
            'success': False,
            'error': 'new_tier is required'
        }), 400

    try:
        from ..services.flow_service import FlowService
        from ..services.shopify_client import ShopifyClient

        client = ShopifyClient(g.tenant_id)
        flow_svc = FlowService(g.tenant_id, client)

        result = flow_svc.action_change_tier(
            customer_email=customer_email,
            new_tier_name=new_tier,
            reason=reason
        )

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@flow_bp.route('/actions/get-member', methods=['POST'])
@require_flow_auth
def action_get_member():
    """
    Flow Action: Get member information.

    Request body:
        customer_email: Email of the customer

    Returns:
        is_member: Whether customer is a member
        member: Member details (if found)
    """
    data = request.get_json()

    customer_email = data.get('customer_email') or data.get('customerEmail')

    if not customer_email:
        return jsonify({
            'success': False,
            'error': 'customer_email is required'
        }), 400

    try:
        from ..services.flow_service import FlowService

        flow_svc = FlowService(g.tenant_id)
        result = flow_svc.action_get_member(customer_email=customer_email)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== Flow Trigger Endpoints ====================
# These are called by Shopify to get trigger schema/configuration

@flow_bp.route('/triggers/member-enrolled', methods=['GET'])
def trigger_member_enrolled_schema():
    """Return schema for member enrolled trigger."""
    return jsonify({
        'name': 'TradeUp: Member Enrolled',
        'description': 'Triggered when a new member enrolls in the loyalty program',
        'properties': [
            {'name': 'member_id', 'type': 'number', 'description': 'Internal member ID'},
            {'name': 'member_number', 'type': 'string', 'description': 'Member number (e.g., TU1001)'},
            {'name': 'email', 'type': 'string', 'description': 'Member email address'},
            {'name': 'tier_name', 'type': 'string', 'description': 'Initial tier name'},
            {'name': 'shopify_customer_id', 'type': 'string', 'description': 'Shopify customer GID'}
        ]
    })


@flow_bp.route('/triggers/tier-changed', methods=['GET'])
def trigger_tier_changed_schema():
    """Return schema for tier changed trigger."""
    return jsonify({
        'name': 'TradeUp: Tier Changed',
        'description': 'Triggered when a member\'s tier is upgraded or downgraded',
        'properties': [
            {'name': 'member_id', 'type': 'number', 'description': 'Internal member ID'},
            {'name': 'member_number', 'type': 'string', 'description': 'Member number'},
            {'name': 'email', 'type': 'string', 'description': 'Member email address'},
            {'name': 'old_tier', 'type': 'string', 'description': 'Previous tier name'},
            {'name': 'new_tier', 'type': 'string', 'description': 'New tier name'},
            {'name': 'change_type', 'type': 'string', 'description': 'upgrade or downgrade'},
            {'name': 'source', 'type': 'string', 'description': 'What triggered the change'},
            {'name': 'shopify_customer_id', 'type': 'string', 'description': 'Shopify customer GID'}
        ]
    })


@flow_bp.route('/triggers/trade-in-completed', methods=['GET'])
def trigger_trade_in_completed_schema():
    """Return schema for trade-in completed trigger."""
    return jsonify({
        'name': 'TradeUp: Trade-In Completed',
        'description': 'Triggered when a trade-in batch is completed',
        'properties': [
            {'name': 'member_id', 'type': 'number', 'description': 'Internal member ID'},
            {'name': 'member_number', 'type': 'string', 'description': 'Member number'},
            {'name': 'email', 'type': 'string', 'description': 'Member email address'},
            {'name': 'batch_reference', 'type': 'string', 'description': 'Trade-in batch reference'},
            {'name': 'trade_value', 'type': 'number', 'description': 'Base trade value'},
            {'name': 'bonus_amount', 'type': 'number', 'description': 'Tier bonus amount'},
            {'name': 'total_credit', 'type': 'number', 'description': 'Total credit issued'},
            {'name': 'item_count', 'type': 'number', 'description': 'Number of items'},
            {'name': 'category', 'type': 'string', 'description': 'Trade-in category'},
            {'name': 'shopify_customer_id', 'type': 'string', 'description': 'Shopify customer GID'}
        ]
    })


@flow_bp.route('/triggers/credit-issued', methods=['GET'])
def trigger_credit_issued_schema():
    """Return schema for credit issued trigger."""
    return jsonify({
        'name': 'TradeUp: Store Credit Issued',
        'description': 'Triggered when store credit is added to a member\'s account',
        'properties': [
            {'name': 'member_id', 'type': 'number', 'description': 'Internal member ID'},
            {'name': 'member_number', 'type': 'string', 'description': 'Member number'},
            {'name': 'email', 'type': 'string', 'description': 'Member email address'},
            {'name': 'amount', 'type': 'number', 'description': 'Credit amount added'},
            {'name': 'event_type', 'type': 'string', 'description': 'Type of credit event'},
            {'name': 'description', 'type': 'string', 'description': 'Credit description'},
            {'name': 'new_balance', 'type': 'number', 'description': 'New credit balance'},
            {'name': 'shopify_customer_id', 'type': 'string', 'description': 'Shopify customer GID'}
        ]
    })


# ==================== Points Trigger Schemas ====================

@flow_bp.route('/triggers/points-earned', methods=['GET'])
def trigger_points_earned_schema():
    """Return schema for points earned trigger."""
    return jsonify({
        'name': 'TradeUp: Points Earned',
        'description': 'Triggered when a customer earns points from purchases, referrals, or other activities',
        'properties': [
            {'name': 'member_id', 'type': 'number', 'description': 'Internal member ID'},
            {'name': 'member_number', 'type': 'string', 'description': 'Member number (e.g., TU1001)'},
            {'name': 'email', 'type': 'string', 'description': 'Member email address'},
            {'name': 'points_earned', 'type': 'number', 'description': 'Number of points earned'},
            {'name': 'source', 'type': 'string', 'description': 'Source of points (purchase, referral, signup, trade_in, bonus)'},
            {'name': 'source_id', 'type': 'string', 'description': 'Reference ID (order ID, referral ID, etc.)'},
            {'name': 'new_balance', 'type': 'number', 'description': 'New total points balance'},
            {'name': 'tier_name', 'type': 'string', 'description': 'Member current tier name'},
            {'name': 'order_id', 'type': 'string', 'description': 'Shopify order GID (if from purchase)'},
            {'name': 'shopify_customer_id', 'type': 'string', 'description': 'Shopify customer GID'}
        ]
    })


@flow_bp.route('/triggers/points-redeemed', methods=['GET'])
def trigger_points_redeemed_schema():
    """Return schema for points redeemed trigger."""
    return jsonify({
        'name': 'TradeUp: Points Redeemed',
        'description': 'Triggered when a customer redeems points for a reward',
        'properties': [
            {'name': 'member_id', 'type': 'number', 'description': 'Internal member ID'},
            {'name': 'member_number', 'type': 'string', 'description': 'Member number'},
            {'name': 'email', 'type': 'string', 'description': 'Member email address'},
            {'name': 'points_redeemed', 'type': 'number', 'description': 'Number of points redeemed'},
            {'name': 'reward_type', 'type': 'string', 'description': 'Type of reward (store_credit, discount_code, product, custom)'},
            {'name': 'reward_value', 'type': 'number', 'description': 'Dollar value of the reward'},
            {'name': 'reward_name', 'type': 'string', 'description': 'Name of the reward'},
            {'name': 'new_balance', 'type': 'number', 'description': 'New total points balance after redemption'},
            {'name': 'shopify_customer_id', 'type': 'string', 'description': 'Shopify customer GID'}
        ]
    })


@flow_bp.route('/triggers/tier-upgraded', methods=['GET'])
def trigger_tier_upgraded_schema():
    """Return schema for tier upgraded trigger."""
    return jsonify({
        'name': 'TradeUp: Tier Upgraded',
        'description': 'Triggered when a customer is upgraded to a higher tier',
        'properties': [
            {'name': 'member_id', 'type': 'number', 'description': 'Internal member ID'},
            {'name': 'member_number', 'type': 'string', 'description': 'Member number'},
            {'name': 'email', 'type': 'string', 'description': 'Member email address'},
            {'name': 'old_tier', 'type': 'string', 'description': 'Previous tier name'},
            {'name': 'new_tier', 'type': 'string', 'description': 'New tier name'},
            {'name': 'old_tier_bonus_percent', 'type': 'number', 'description': 'Previous tier bonus rate as percentage'},
            {'name': 'new_tier_bonus_percent', 'type': 'number', 'description': 'New tier bonus rate as percentage'},
            {'name': 'source', 'type': 'string', 'description': 'What triggered the upgrade (activity, purchase, subscription, staff)'},
            {'name': 'change_type', 'type': 'string', 'description': 'Always "upgrade"'},
            {'name': 'shopify_customer_id', 'type': 'string', 'description': 'Shopify customer GID'}
        ]
    })


@flow_bp.route('/triggers/tier-downgraded', methods=['GET'])
def trigger_tier_downgraded_schema():
    """Return schema for tier downgraded trigger."""
    return jsonify({
        'name': 'TradeUp: Tier Downgraded',
        'description': 'Triggered when a customer is downgraded to a lower tier',
        'properties': [
            {'name': 'member_id', 'type': 'number', 'description': 'Internal member ID'},
            {'name': 'member_number', 'type': 'string', 'description': 'Member number'},
            {'name': 'email', 'type': 'string', 'description': 'Member email address'},
            {'name': 'old_tier', 'type': 'string', 'description': 'Previous tier name'},
            {'name': 'new_tier', 'type': 'string', 'description': 'New tier name (or "None" if removed)'},
            {'name': 'old_tier_bonus_percent', 'type': 'number', 'description': 'Previous tier bonus rate as percentage'},
            {'name': 'new_tier_bonus_percent', 'type': 'number', 'description': 'New tier bonus rate as percentage'},
            {'name': 'reason', 'type': 'string', 'description': 'Why downgraded (inactivity, subscription_cancelled, refund, expired)'},
            {'name': 'change_type', 'type': 'string', 'description': 'Always "downgrade"'},
            {'name': 'shopify_customer_id', 'type': 'string', 'description': 'Shopify customer GID'}
        ]
    })


@flow_bp.route('/triggers/reward-unlocked', methods=['GET'])
def trigger_reward_unlocked_schema():
    """Return schema for reward unlocked trigger."""
    return jsonify({
        'name': 'TradeUp: Reward Unlocked',
        'description': 'Triggered when a customer has enough points to unlock a reward',
        'properties': [
            {'name': 'member_id', 'type': 'number', 'description': 'Internal member ID'},
            {'name': 'member_number', 'type': 'string', 'description': 'Member number'},
            {'name': 'email', 'type': 'string', 'description': 'Member email address'},
            {'name': 'reward_id', 'type': 'number', 'description': 'Reward configuration ID'},
            {'name': 'reward_name', 'type': 'string', 'description': 'Name of the unlocked reward'},
            {'name': 'points_required', 'type': 'number', 'description': 'Points needed for this reward'},
            {'name': 'reward_value', 'type': 'number', 'description': 'Dollar value of the reward'},
            {'name': 'current_balance', 'type': 'number', 'description': 'Customer current points balance'},
            {'name': 'points_surplus', 'type': 'number', 'description': 'Points above the requirement'},
            {'name': 'shopify_customer_id', 'type': 'string', 'description': 'Shopify customer GID'}
        ]
    })


# ==================== Points Action Endpoints ====================

@flow_bp.route('/actions/award-bonus-points', methods=['POST'])
@require_flow_auth
def action_award_bonus_points():
    """
    Flow Action: Award bonus points to a customer.

    Request body:
        customer_email: Email of the customer (required)
        points: Number of points to award (required, positive integer)
        reason: Optional reason/description
        idempotency_key: Optional unique key to prevent duplicate awards

    Returns:
        success: Whether points were awarded
        member_id: Member's internal ID
        points_awarded: Number of points awarded
        new_balance: New points balance
        was_duplicate: True if this was a duplicate request
    """
    data = request.get_json()

    customer_email = data.get('customer_email') or data.get('customerEmail')
    points = data.get('points')
    reason = data.get('reason', 'Shopify Flow bonus')
    idempotency_key = data.get('idempotency_key') or data.get('idempotencyKey')

    if not customer_email:
        return jsonify({
            'success': False,
            'error': 'customer_email is required'
        }), 400

    if not points:
        return jsonify({
            'success': False,
            'error': 'points is required'
        }), 400

    try:
        points = int(points)
        if points <= 0:
            return jsonify({
                'success': False,
                'error': 'points must be a positive integer'
            }), 400
    except (TypeError, ValueError):
        return jsonify({
            'success': False,
            'error': 'points must be a valid integer'
        }), 400

    try:
        from ..services.flow_service import FlowService
        from ..services.shopify_client import ShopifyClient

        client = ShopifyClient(g.tenant_id)
        flow_svc = FlowService(g.tenant_id, client)

        result = flow_svc.action_award_bonus_points(
            customer_email=customer_email,
            points=points,
            reason=reason,
            idempotency_key=idempotency_key
        )

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@flow_bp.route('/actions/send-tier-upgrade-email', methods=['POST'])
@require_flow_auth
def action_send_tier_upgrade_email():
    """
    Flow Action: Send tier upgrade notification email.

    Request body:
        customer_email: Email of the customer (required)
        old_tier: Previous tier name (optional)
        new_tier: New tier name (optional)

    Returns:
        success: Whether email was sent
        member_id: Member's internal ID
        email_sent: True if email was successfully queued
    """
    data = request.get_json()

    customer_email = data.get('customer_email') or data.get('customerEmail')
    old_tier = data.get('old_tier') or data.get('oldTier')
    new_tier = data.get('new_tier') or data.get('newTier')

    if not customer_email:
        return jsonify({
            'success': False,
            'error': 'customer_email is required'
        }), 400

    try:
        from ..services.flow_service import FlowService
        from ..services.shopify_client import ShopifyClient

        client = ShopifyClient(g.tenant_id)
        flow_svc = FlowService(g.tenant_id, client)

        result = flow_svc.action_send_tier_upgrade_email(
            customer_email=customer_email,
            old_tier=old_tier,
            new_tier=new_tier
        )

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@flow_bp.route('/actions/create-reward-reminder', methods=['POST'])
@require_flow_auth
def action_create_reward_reminder():
    """
    Flow Action: Send a reward reminder to a customer.

    Request body:
        customer_email: Email of the customer (required)
        reward_name: Name of the reward to highlight (optional)
        points_needed: Points needed to reach next reward (optional)
        custom_message: Custom message for the reminder (optional)

    Returns:
        success: Whether reminder was created/sent
        member_id: Member's internal ID
        reminder_type: Type of reminder sent (available or progress)
        available_rewards: List of rewards member can redeem
    """
    data = request.get_json()

    customer_email = data.get('customer_email') or data.get('customerEmail')
    reward_name = data.get('reward_name') or data.get('rewardName')
    points_needed = data.get('points_needed') or data.get('pointsNeeded')
    custom_message = data.get('custom_message') or data.get('customMessage')

    if not customer_email:
        return jsonify({
            'success': False,
            'error': 'customer_email is required'
        }), 400

    try:
        from ..services.flow_service import FlowService
        from ..services.shopify_client import ShopifyClient

        client = ShopifyClient(g.tenant_id)
        flow_svc = FlowService(g.tenant_id, client)

        result = flow_svc.action_create_reward_reminder(
            customer_email=customer_email,
            reward_name=reward_name,
            points_needed=int(points_needed) if points_needed else None,
            custom_message=custom_message
        )

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@flow_bp.route('/actions/get-points-balance', methods=['POST'])
@require_flow_auth
def action_get_points_balance():
    """
    Flow Action: Get customer's points balance and tier info.

    Useful for Flow conditions and branching logic.

    Request body:
        customer_email: Email of the customer (required)

    Returns:
        success: Whether lookup succeeded
        points_balance: Current points balance
        tier: Current tier name
        tier_bonus_percent: Tier bonus rate as percentage
        available_rewards_count: Number of rewards they can redeem
        next_reward: Info about the next reward they're working toward
    """
    data = request.get_json()

    customer_email = data.get('customer_email') or data.get('customerEmail')

    if not customer_email:
        return jsonify({
            'success': False,
            'error': 'customer_email is required'
        }), 400

    try:
        from ..services.flow_service import FlowService

        flow_svc = FlowService(g.tenant_id)
        result = flow_svc.action_get_points_balance(customer_email=customer_email)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
