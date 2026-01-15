"""
Guest Points API Endpoints

Manage points for guest (non-member) customers.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from app.services.guest_points_service import GuestPointsService

guest_points_bp = Blueprint('guest_points', __name__)


def get_service():
    """Get guest points service for current tenant."""
    settings = g.tenant.settings or {}
    return GuestPointsService(g.tenant.id, settings)


@guest_points_bp.route('/settings', methods=['GET'])
@require_shopify_auth
def get_guest_points_settings():
    """Get guest points settings."""
    service = get_service()
    settings = service.get_guest_points_settings()

    return jsonify({
        'success': True,
        'settings': settings,
    })


@guest_points_bp.route('/settings', methods=['PUT'])
@require_shopify_auth
def update_guest_points_settings():
    """Update guest points settings."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Update tenant settings
    if not g.tenant.settings:
        g.tenant.settings = {}

    g.tenant.settings['guest_points'] = {
        'enabled': data.get('enabled', False),
        'points_per_dollar': data.get('points_per_dollar', 1),
        'expiry_days': data.get('expiry_days', 90),
        'min_order_value': data.get('min_order_value', 0),
        'welcome_message': data.get('welcome_message',
            'You earned {points} points! Create an account to claim them.'),
    }

    from app import db
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(g.tenant, 'settings')
    db.session.commit()

    return jsonify({
        'success': True,
        'settings': g.tenant.settings['guest_points'],
    })


@guest_points_bp.route('/stats', methods=['GET'])
@require_shopify_auth
def get_guest_points_stats():
    """Get guest points statistics."""
    service = get_service()
    stats = service.get_guest_points_stats()

    return jsonify(stats)


@guest_points_bp.route('/pending', methods=['GET'])
@require_shopify_auth
def get_pending_points():
    """Get pending points for an email."""
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400

    service = get_service()
    result = service.get_pending_points(email)

    return jsonify(result)


@guest_points_bp.route('/award', methods=['POST'])
@require_shopify_auth
def award_guest_points():
    """Award points to a guest customer."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email')
    points = data.get('points')

    if not email or not points:
        return jsonify({'error': 'Email and points required'}), 400

    service = get_service()
    result = service.award_guest_points(
        email=email,
        points=points,
        source_type=data.get('source_type', 'manual'),
        source_id=data.get('source_id'),
        description=data.get('description'),
        order_number=data.get('order_number'),
        order_total=data.get('order_total'),
        shopify_customer_id=data.get('shopify_customer_id'),
    )

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@guest_points_bp.route('/claim', methods=['POST'])
@require_shopify_auth
def claim_guest_points():
    """Claim pending points for a member."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email')
    member_id = data.get('member_id')

    if not email or not member_id:
        return jsonify({'error': 'Email and member_id required'}), 400

    service = get_service()
    result = service.claim_points(email, member_id)

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@guest_points_bp.route('/calculate', methods=['POST'])
@require_shopify_auth
def calculate_guest_points():
    """Calculate points for a potential order."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    order_total = data.get('order_total')
    if order_total is None:
        return jsonify({'error': 'order_total required'}), 400

    service = get_service()
    result = service.calculate_guest_points_for_order(
        order_total=order_total,
        order_id=data.get('order_id'),
    )

    return jsonify(result)


@guest_points_bp.route('/expire', methods=['POST'])
@require_shopify_auth
def expire_guest_points():
    """Expire old guest points (admin/scheduled task)."""
    service = get_service()
    result = service.expire_old_points()

    return jsonify(result)
