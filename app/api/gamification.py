"""
Gamification API Endpoints

Badges, achievements, streaks, and milestones.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from app.services.gamification_service import GamificationService
from app.models.gamification import Badge, MemberBadge, Milestone

gamification_bp = Blueprint('gamification', __name__)


def get_service():
    """Get gamification service for current tenant."""
    return GamificationService(g.tenant.id)


# Badge Endpoints
@gamification_bp.route('/badges', methods=['GET'])
@require_shopify_auth
def list_badges():
    """List all badges."""
    service = get_service()
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    badges = service.get_badges(include_inactive=include_inactive)

    return jsonify({
        'success': True,
        'badges': [b.to_dict() for b in badges],
    })


@gamification_bp.route('/badges', methods=['POST'])
@require_shopify_auth
def create_badge():
    """Create a new badge."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    required = ['name', 'criteria_type']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    service = get_service()
    badge = service.create_badge(data)

    return jsonify({
        'success': True,
        'badge': badge.to_dict(),
    }), 201


@gamification_bp.route('/badges/<int:badge_id>', methods=['GET'])
@require_shopify_auth
def get_badge(badge_id):
    """Get a specific badge."""
    service = get_service()
    badge = service.get_badge(badge_id)

    if not badge:
        return jsonify({'error': 'Badge not found'}), 404

    return jsonify({
        'success': True,
        'badge': badge.to_dict(),
    })


@gamification_bp.route('/badges/<int:badge_id>', methods=['PUT'])
@require_shopify_auth
def update_badge(badge_id):
    """Update a badge."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    service = get_service()
    badge = service.update_badge(badge_id, data)

    if not badge:
        return jsonify({'error': 'Badge not found'}), 404

    return jsonify({
        'success': True,
        'badge': badge.to_dict(),
    })


@gamification_bp.route('/badges/<int:badge_id>', methods=['DELETE'])
@require_shopify_auth
def delete_badge(badge_id):
    """Delete a badge."""
    service = get_service()
    success = service.delete_badge(badge_id)

    if not success:
        return jsonify({'error': 'Badge not found'}), 404

    return jsonify({
        'success': True,
        'message': 'Badge deleted',
    })


# Milestone Endpoints
@gamification_bp.route('/milestones', methods=['GET'])
@require_shopify_auth
def list_milestones():
    """List all milestones."""
    service = get_service()
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    milestones = service.get_milestones(include_inactive=include_inactive)

    return jsonify({
        'success': True,
        'milestones': [m.to_dict() for m in milestones],
    })


@gamification_bp.route('/milestones', methods=['POST'])
@require_shopify_auth
def create_milestone():
    """Create a new milestone."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    required = ['name', 'milestone_type', 'threshold']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    milestone = Milestone(
        tenant_id=g.tenant.id,
        name=data['name'],
        description=data.get('description', ''),
        milestone_type=data['milestone_type'],
        threshold=data['threshold'],
        points_reward=data.get('points_reward', 0),
        credit_reward=data.get('credit_reward', 0),
        badge_id=data.get('badge_id'),
        celebration_message=data.get('celebration_message', ''),
        is_active=data.get('is_active', True),
    )

    from app import db
    db.session.add(milestone)
    db.session.commit()

    return jsonify({
        'success': True,
        'milestone': milestone.to_dict(),
    }), 201


# Member Badge Endpoints
@gamification_bp.route('/members/<int:member_id>/badges', methods=['GET'])
@require_shopify_auth
def get_member_badges(member_id):
    """Get badges earned by a member."""
    service = get_service()
    badges = service.get_member_badges(member_id)

    return jsonify({
        'success': True,
        'badges': [b.to_dict() for b in badges],
    })


@gamification_bp.route('/members/<int:member_id>/badges/<int:badge_id>', methods=['POST'])
@require_shopify_auth
def award_badge_to_member(member_id, badge_id):
    """Manually award a badge to a member."""
    service = get_service()
    member_badge = service.award_badge(member_id, badge_id)

    if not member_badge:
        return jsonify({'error': 'Badge not found'}), 404

    return jsonify({
        'success': True,
        'member_badge': member_badge.to_dict(),
    })


@gamification_bp.route('/members/<int:member_id>/check-badges', methods=['POST'])
@require_shopify_auth
def check_member_badges(member_id):
    """Check and award any earned badges for a member."""
    service = get_service()
    awarded = service.check_and_award_badges(member_id)

    return jsonify({
        'success': True,
        'awarded': [b.to_dict() for b in awarded],
        'count': len(awarded),
    })


# Streak Endpoints
@gamification_bp.route('/members/<int:member_id>/streak', methods=['GET'])
@require_shopify_auth
def get_member_streak(member_id):
    """Get member's current streak."""
    service = get_service()
    streak = service.get_member_streak(member_id)

    return jsonify({
        'success': True,
        'streak': streak.to_dict() if streak else None,
    })


@gamification_bp.route('/members/<int:member_id>/streak', methods=['POST'])
@require_shopify_auth
def update_member_streak(member_id):
    """Record activity and update streak."""
    service = get_service()
    streak = service.update_streak(member_id)

    return jsonify({
        'success': True,
        'streak': streak.to_dict(),
    })


# Progress Endpoints
@gamification_bp.route('/members/<int:member_id>/progress', methods=['GET'])
@require_shopify_auth
def get_member_progress(member_id):
    """Get member's progress toward badges and milestones."""
    service = get_service()
    progress = service.get_member_progress(member_id)

    return jsonify({
        'success': True,
        **progress,
    })


@gamification_bp.route('/members/<int:member_id>/achievements/unnotified', methods=['GET'])
@require_shopify_auth
def get_unnotified_achievements(member_id):
    """Get achievements that haven't been shown to the member."""
    service = get_service()
    achievements = service.get_unnotified_achievements(member_id)

    return jsonify({
        'success': True,
        **achievements,
    })


@gamification_bp.route('/members/<int:member_id>/achievements/mark-notified', methods=['POST'])
@require_shopify_auth
def mark_achievements_notified(member_id):
    """Mark all achievements as shown."""
    service = get_service()
    service.mark_achievements_notified(member_id)

    return jsonify({
        'success': True,
        'message': 'Achievements marked as notified',
    })


# Initialize Defaults
@gamification_bp.route('/initialize', methods=['POST'])
@require_shopify_auth
def initialize_defaults():
    """Initialize default badges and milestones."""
    service = get_service()
    result = service.initialize_defaults()

    return jsonify({
        'success': True,
        **result,
    })


# Stats
@gamification_bp.route('/stats', methods=['GET'])
@require_shopify_auth
def get_gamification_stats():
    """Get gamification statistics."""
    service = get_service()

    badges = service.get_badges()
    milestones = service.get_milestones()

    # Count earned badges across all members
    total_earned = MemberBadge.query.join(Badge).filter(
        Badge.tenant_id == g.tenant.id
    ).count()

    return jsonify({
        'success': True,
        'stats': {
            'total_badges': len(badges),
            'total_milestones': len(milestones),
            'total_badges_earned': total_earned,
        },
    })
