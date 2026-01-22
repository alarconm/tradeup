"""
Anniversary Rewards API Endpoints

Manage membership anniversary settings and rewards.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from app import db
from sqlalchemy.orm.attributes import flag_modified

anniversary_bp = Blueprint('anniversary', __name__)


def get_anniversary_settings(tenant):
    """Get anniversary reward settings for a tenant."""
    settings = tenant.settings or {}
    anniversary_settings = settings.get('anniversary', {})
    return {
        'enabled': anniversary_settings.get('enabled', False),
        'reward_type': anniversary_settings.get('reward_type', 'points'),  # points, credit, discount_code
        'reward_amount': anniversary_settings.get('reward_amount', 100),
        'email_days_before': anniversary_settings.get('email_days_before', 0),  # 0, 1, 3, or 7
        'message': anniversary_settings.get('message', 'Happy Anniversary! Thank you for being a loyal member!'),
        'tiered_rewards_enabled': anniversary_settings.get('tiered_rewards_enabled', False),
        'tiered_rewards': anniversary_settings.get('tiered_rewards', {}),
    }


@anniversary_bp.route('/settings', methods=['GET'])
@require_shopify_auth
def get_settings():
    """
    Get anniversary reward settings.

    Returns:
        {
            "success": true,
            "settings": {
                "enabled": false,
                "reward_type": "points",
                "reward_amount": 100,
                "email_days_before": 0,
                "message": "Happy Anniversary! ..."
            }
        }
    """
    settings = get_anniversary_settings(g.tenant)

    return jsonify({
        'success': True,
        'settings': settings,
    })


@anniversary_bp.route('/settings', methods=['PUT'])
@require_shopify_auth
def update_settings():
    """
    Update anniversary reward settings.

    Request body:
        enabled: bool - Master toggle for anniversary rewards
        reward_type: str - "points", "credit", or "discount_code"
        reward_amount: int/float - Amount of reward
        email_days_before: int - 0, 1, 3, or 7 days before anniversary
        message: str - Custom anniversary message

    Returns:
        {
            "success": true,
            "settings": { ... updated settings ... }
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate reward_type if provided
    reward_type = data.get('reward_type')
    if reward_type and reward_type not in ['points', 'credit', 'discount_code']:
        return jsonify({
            'error': 'Invalid reward_type. Must be "points", "credit", or "discount_code"'
        }), 400

    # Validate email_days_before if provided
    email_days_before = data.get('email_days_before')
    if email_days_before is not None and email_days_before not in [0, 1, 3, 7]:
        return jsonify({
            'error': 'Invalid email_days_before. Must be 0, 1, 3, or 7'
        }), 400

    # Validate reward_amount if provided
    reward_amount = data.get('reward_amount')
    if reward_amount is not None:
        try:
            reward_amount = float(reward_amount)
            if reward_amount < 0:
                raise ValueError()
        except (ValueError, TypeError):
            return jsonify({
                'error': 'Invalid reward_amount. Must be a non-negative number'
            }), 400

    # Validate tiered_rewards if provided
    tiered_rewards = data.get('tiered_rewards')
    if tiered_rewards is not None:
        if not isinstance(tiered_rewards, dict):
            return jsonify({
                'error': 'Invalid tiered_rewards. Must be an object mapping years to amounts'
            }), 400
        # Validate each tier entry
        for year_str, amount in tiered_rewards.items():
            try:
                year = int(year_str)
                if year < 1:
                    raise ValueError()
            except (ValueError, TypeError):
                return jsonify({
                    'error': f'Invalid tiered_rewards year "{year_str}". Years must be positive integers'
                }), 400
            try:
                amount = float(amount)
                if amount < 0:
                    raise ValueError()
            except (ValueError, TypeError):
                return jsonify({
                    'error': f'Invalid tiered_rewards amount for year {year_str}. Must be a non-negative number'
                }), 400

    # Update tenant settings
    if not g.tenant.settings:
        g.tenant.settings = {}

    # Get current anniversary settings and merge with new values
    current_anniversary = g.tenant.settings.get('anniversary', {})

    g.tenant.settings['anniversary'] = {
        'enabled': data.get('enabled', current_anniversary.get('enabled', False)),
        'reward_type': data.get('reward_type', current_anniversary.get('reward_type', 'points')),
        'reward_amount': data.get('reward_amount', current_anniversary.get('reward_amount', 100)),
        'email_days_before': data.get('email_days_before', current_anniversary.get('email_days_before', 0)),
        'message': data.get('message', current_anniversary.get('message', 'Happy Anniversary! Thank you for being a loyal member!')),
        'tiered_rewards_enabled': data.get('tiered_rewards_enabled', current_anniversary.get('tiered_rewards_enabled', False)),
        'tiered_rewards': data.get('tiered_rewards', current_anniversary.get('tiered_rewards', {})),
    }

    flag_modified(g.tenant, 'settings')
    db.session.commit()

    return jsonify({
        'success': True,
        'settings': g.tenant.settings['anniversary'],
    })


@anniversary_bp.route('/validate', methods=['POST'])
@require_shopify_auth
def validate_settings():
    """
    Validate anniversary settings without saving them.

    Request body: Same as PUT /settings

    Returns:
        {
            "success": true,
            "valid": true,
            "errors": []
        }
        or
        {
            "success": true,
            "valid": false,
            "errors": ["Invalid reward_type", ...]
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({
            'success': True,
            'valid': True,
            'errors': []
        })

    errors = []

    # Validate reward_type
    reward_type = data.get('reward_type')
    if reward_type and reward_type not in ['points', 'credit', 'discount_code']:
        errors.append('Invalid reward_type. Must be "points", "credit", or "discount_code"')

    # Validate email_days_before
    email_days_before = data.get('email_days_before')
    if email_days_before is not None and email_days_before not in [0, 1, 3, 7]:
        errors.append('Invalid email_days_before. Must be 0, 1, 3, or 7')

    # Validate reward_amount
    reward_amount = data.get('reward_amount')
    if reward_amount is not None:
        try:
            reward_amount = float(reward_amount)
            if reward_amount < 0:
                errors.append('reward_amount must be a non-negative number')
        except (ValueError, TypeError):
            errors.append('Invalid reward_amount. Must be a number')

    return jsonify({
        'success': True,
        'valid': len(errors) == 0,
        'errors': errors
    })
