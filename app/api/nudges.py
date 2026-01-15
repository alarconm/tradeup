"""
Nudges & Reminders API Endpoints

Manage member engagement nudges and reminders.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from app.services.nudges_service import NudgesService

nudges_bp = Blueprint('nudges', __name__)


def get_service():
    """Get nudges service for current tenant."""
    settings = g.tenant.settings or {}
    return NudgesService(g.tenant.id, settings)


@nudges_bp.route('/settings', methods=['GET'])
@require_shopify_auth
def get_nudge_settings():
    """Get nudge settings."""
    service = get_service()
    settings = service.get_nudge_settings()

    return jsonify({
        'success': True,
        'settings': settings,
    })


@nudges_bp.route('/settings', methods=['PUT'])
@require_shopify_auth
def update_nudge_settings():
    """Update nudge settings."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Update tenant settings
    if not g.tenant.settings:
        g.tenant.settings = {}

    g.tenant.settings['nudges'] = {
        'enabled': data.get('enabled', True),
        'points_expiry_days': data.get('points_expiry_days', [30, 7, 1]),
        'tier_upgrade_threshold': data.get('tier_upgrade_threshold', 0.9),
        'inactive_days': data.get('inactive_days', 30),
        'welcome_reminder_days': data.get('welcome_reminder_days', 3),
        'points_milestones': data.get('points_milestones', [100, 500, 1000, 5000]),
        'email_enabled': data.get('email_enabled', True),
        'max_nudges_per_day': data.get('max_nudges_per_day', 1),
    }

    from app import db
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(g.tenant, 'settings')
    db.session.commit()

    return jsonify({
        'success': True,
        'settings': g.tenant.settings['nudges'],
    })


@nudges_bp.route('/stats', methods=['GET'])
@require_shopify_auth
def get_nudge_stats():
    """Get nudge statistics."""
    service = get_service()
    stats = service.get_nudge_stats()

    return jsonify(stats)


@nudges_bp.route('/', methods=['GET'])
@require_shopify_auth
def get_all_nudges():
    """Get all pending nudges."""
    service = get_service()
    nudges = service.get_all_pending_nudges()

    return jsonify(nudges)


@nudges_bp.route('/points-expiring', methods=['GET'])
@require_shopify_auth
def get_points_expiring():
    """Get members with points expiring soon."""
    days = request.args.get('days', 30, type=int)
    service = get_service()
    members = service.get_members_with_expiring_points(days_ahead=days)

    return jsonify({
        'success': True,
        'members': members,
        'count': len(members),
    })


@nudges_bp.route('/tier-upgrade-near', methods=['GET'])
@require_shopify_auth
def get_tier_upgrade_near():
    """Get members near tier upgrade."""
    threshold = request.args.get('threshold', 0.9, type=float)
    service = get_service()
    members = service.get_members_near_tier_upgrade(threshold=threshold)

    return jsonify({
        'success': True,
        'members': members,
        'count': len(members),
    })


@nudges_bp.route('/inactive', methods=['GET'])
@require_shopify_auth
def get_inactive_members():
    """Get inactive members."""
    days = request.args.get('days', 30, type=int)
    service = get_service()
    members = service.get_inactive_members(days_inactive=days)

    return jsonify({
        'success': True,
        'members': members,
        'count': len(members),
    })


@nudges_bp.route('/members/<int:member_id>', methods=['GET'])
@require_shopify_auth
def get_member_nudges(member_id):
    """Get nudges for a specific member."""
    service = get_service()
    nudges = service.get_nudges_for_member(member_id)

    return jsonify({
        'success': True,
        'nudges': nudges,
        'count': len(nudges),
    })
