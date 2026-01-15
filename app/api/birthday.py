"""
Birthday Rewards API Endpoints

Manage birthday collection and rewards.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from app.services.birthday_service import BirthdayService
from app.models.member import Member

birthday_bp = Blueprint('birthday', __name__)


def get_service():
    """Get birthday service for current tenant."""
    settings = g.tenant.settings or {}
    return BirthdayService(g.tenant.id, settings)


@birthday_bp.route('/settings', methods=['GET'])
@require_shopify_auth
def get_birthday_settings():
    """Get birthday reward settings."""
    service = get_service()
    settings = service.get_birthday_settings()

    return jsonify({
        'success': True,
        'settings': settings,
    })


@birthday_bp.route('/settings', methods=['PUT'])
@require_shopify_auth
def update_birthday_settings():
    """Update birthday reward settings."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Update tenant settings
    if not g.tenant.settings:
        g.tenant.settings = {}

    g.tenant.settings['birthday'] = {
        'enabled': data.get('enabled', False),
        'reward_type': data.get('reward_type', 'credit'),
        'reward_amount': data.get('reward_amount', 10),
        'send_email': data.get('send_email', True),
        'email_days_before': data.get('email_days_before', 0),
        'message': data.get('message', 'Happy Birthday! Enjoy your special reward!'),
    }

    from app import db
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(g.tenant, 'settings')
    db.session.commit()

    return jsonify({
        'success': True,
        'settings': g.tenant.settings['birthday'],
    })


@birthday_bp.route('/stats', methods=['GET'])
@require_shopify_auth
def get_birthday_stats():
    """Get birthday statistics."""
    service = get_service()
    stats = service.get_birthday_stats()

    return jsonify({
        'success': True,
        'stats': stats,
    })


@birthday_bp.route('/upcoming', methods=['GET'])
@require_shopify_auth
def get_upcoming_birthdays():
    """Get members with upcoming birthdays."""
    days = request.args.get('days', 7, type=int)
    service = get_service()
    upcoming = service.get_members_with_upcoming_birthdays(days_ahead=days)

    return jsonify({
        'success': True,
        'upcoming': upcoming,
    })


@birthday_bp.route('/members/<int:member_id>/birthday', methods=['PUT'])
@require_shopify_auth
def set_member_birthday(member_id):
    """Set a member's birthday."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    month = data.get('month')
    day = data.get('day')

    if not month or not day:
        return jsonify({'error': 'Month and day required'}), 400

    service = get_service()
    try:
        member = service.set_member_birthday(member_id, month, day)
        if not member:
            return jsonify({'error': 'Member not found'}), 404

        return jsonify({
            'success': True,
            'member': member.to_dict(),
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@birthday_bp.route('/members/<int:member_id>/birthday/reward', methods=['POST'])
@require_shopify_auth
def issue_birthday_reward(member_id):
    """Manually issue birthday reward to a member."""
    member = Member.query.filter_by(
        id=member_id,
        tenant_id=g.tenant.id
    ).first()

    if not member:
        return jsonify({'error': 'Member not found'}), 404

    service = get_service()
    result = service.issue_birthday_reward(member)

    if not result.get('success'):
        return jsonify({'error': result.get('error')}), 400

    return jsonify({
        'success': True,
        'result': result,
    })


@birthday_bp.route('/process', methods=['POST'])
@require_shopify_auth
def process_birthday_rewards():
    """Process birthday rewards for all members with birthdays today."""
    service = get_service()
    result = service.process_birthday_rewards()

    return jsonify({
        'success': True,
        **result,
    })
