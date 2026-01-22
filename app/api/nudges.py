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


# ==================== Tier Progress Reminder Endpoints ====================


@nudges_bp.route('/tier-progress', methods=['GET'])
@require_shopify_auth
def get_tier_progress_members():
    """
    Get members who are close to reaching the next tier.

    Query params:
        threshold: Minimum progress percentage (0.0-1.0, default: 0.9)
    """
    threshold = request.args.get('threshold', type=float)
    service = get_service()
    members = service.get_members_near_tier_progress(threshold_percent=threshold)

    return jsonify({
        'success': True,
        'members': members,
        'count': len(members),
    })


@nudges_bp.route('/tier-progress/config', methods=['GET'])
@require_shopify_auth
def get_tier_progress_config():
    """Get tier progress nudge configuration."""
    service = get_service()
    config = service.get_tier_progress_config()

    return jsonify({
        'success': True,
        'config': config,
    })


@nudges_bp.route('/tier-progress/config', methods=['PUT'])
@require_shopify_auth
def update_tier_progress_config():
    """
    Update tier progress nudge configuration.

    Body:
        enabled: bool - Enable/disable the nudge
        threshold_percent: float - Minimum progress to trigger (0.0-1.0)
        frequency_days: int - Cooldown days between reminders
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    service = get_service()
    result = service.update_tier_progress_config(
        enabled=data.get('enabled'),
        threshold_percent=data.get('threshold_percent'),
        frequency_days=data.get('frequency_days'),
    )

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@nudges_bp.route('/tier-progress/send/<int:member_id>', methods=['POST'])
@require_shopify_auth
def send_tier_progress_reminder(member_id):
    """
    Send tier progress reminder to a specific member.

    Query params:
        force: bool - Skip cooldown check (default: False)
    """
    force = request.args.get('force', 'false').lower() == 'true'
    service = get_service()
    result = service.send_tier_progress_reminder(member_id, force=force)

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@nudges_bp.route('/tier-progress/process', methods=['POST'])
@require_shopify_auth
def process_tier_progress_reminders():
    """
    Process and send tier progress reminders to all eligible members.

    Query params:
        threshold: float - Minimum progress to include (0.0-1.0)
    """
    threshold = request.args.get('threshold', type=float)
    service = get_service()
    result = service.process_tier_progress_reminders(threshold_percent=threshold)

    return jsonify(result)


@nudges_bp.route('/tier-progress/history', methods=['GET'])
@require_shopify_auth
def get_tier_progress_history():
    """
    Get tier progress nudge history.

    Query params:
        member_id: int - Filter to specific member (optional)
        days: int - Days to look back (default: 30)
    """
    member_id = request.args.get('member_id', type=int)
    days = request.args.get('days', 30, type=int)
    service = get_service()
    history = service.get_tier_progress_nudge_history(member_id=member_id, days=days)

    return jsonify({
        'success': True,
        'history': history,
        'count': len(history),
    })


# ==================== Inactive Member Re-engagement Endpoints ====================


@nudges_bp.route('/reengagement', methods=['GET'])
@require_shopify_auth
def get_inactive_members_for_reengagement():
    """
    Get members who are inactive and eligible for re-engagement.

    Query params:
        days: int - Inactivity threshold in days (default: from config)
    """
    days = request.args.get('days', type=int)
    service = get_service()
    members = service.get_inactive_members_for_reengagement(inactive_days=days)

    return jsonify({
        'success': True,
        'members': members,
        'count': len(members),
    })


@nudges_bp.route('/reengagement/config', methods=['GET'])
@require_shopify_auth
def get_reengagement_config():
    """Get inactive re-engagement nudge configuration."""
    service = get_service()
    config = service.get_inactive_reengagement_config()

    return jsonify({
        'success': True,
        'config': config,
    })


@nudges_bp.route('/reengagement/config', methods=['PUT'])
@require_shopify_auth
def update_reengagement_config():
    """
    Update inactive re-engagement nudge configuration.

    Body:
        enabled: bool - Enable/disable the nudge
        inactive_days: int - Days of inactivity threshold
        frequency_days: int - Cooldown days between emails
        incentive_type: str - Type of incentive (points, credit, discount)
        incentive_amount: float - Amount of incentive
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    service = get_service()
    result = service.update_inactive_reengagement_config(
        enabled=data.get('enabled'),
        inactive_days=data.get('inactive_days'),
        frequency_days=data.get('frequency_days'),
        incentive_type=data.get('incentive_type'),
        incentive_amount=data.get('incentive_amount'),
    )

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@nudges_bp.route('/reengagement/send/<int:member_id>', methods=['POST'])
@require_shopify_auth
def send_reengagement_email(member_id):
    """
    Send re-engagement email to a specific inactive member.

    Query params:
        force: bool - Skip cooldown check (default: False)

    Body (optional):
        incentive_type: str - Override incentive type
        incentive_amount: float - Override incentive amount
    """
    force = request.args.get('force', 'false').lower() == 'true'

    # Check for custom incentive in body
    custom_incentive = None
    data = request.get_json(silent=True)
    if data and ('incentive_type' in data or 'incentive_amount' in data):
        custom_incentive = {
            'type': data.get('incentive_type', 'points'),
            'amount': data.get('incentive_amount', 50),
        }

    service = get_service()
    result = service.send_reengagement_email(
        member_id,
        force=force,
        custom_incentive=custom_incentive
    )

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@nudges_bp.route('/reengagement/process', methods=['POST'])
@require_shopify_auth
def process_reengagement_emails():
    """
    Process and send re-engagement emails to all eligible inactive members.

    Query params:
        days: int - Inactivity threshold (uses config if not provided)
        max_emails: int - Maximum emails to send (default: 50)
    """
    days = request.args.get('days', type=int)
    max_emails = request.args.get('max_emails', 50, type=int)

    service = get_service()
    result = service.process_reengagement_emails(
        inactive_days=days,
        max_emails=max_emails
    )

    return jsonify(result)


@nudges_bp.route('/reengagement/stats', methods=['GET'])
@require_shopify_auth
def get_reengagement_stats():
    """
    Get re-engagement nudge effectiveness statistics.

    Query params:
        days: int - Days to analyze (default: 30)
    """
    days = request.args.get('days', 30, type=int)
    service = get_service()
    stats = service.get_reengagement_stats(days=days)

    return jsonify({
        'success': True,
        'stats': stats,
    })


@nudges_bp.route('/reengagement/history', methods=['GET'])
@require_shopify_auth
def get_reengagement_history():
    """
    Get re-engagement email history.

    Query params:
        member_id: int - Filter to specific member (optional)
        days: int - Days to look back (default: 30)
    """
    member_id = request.args.get('member_id', type=int)
    days = request.args.get('days', 30, type=int)
    service = get_service()
    history = service.get_reengagement_history(member_id=member_id, days=days)

    return jsonify({
        'success': True,
        'history': history,
        'count': len(history),
    })


@nudges_bp.route('/reengagement/track/<int:member_id>', methods=['POST'])
@require_shopify_auth
def track_reengagement_response(member_id):
    """
    Track when an inactive member responds to a re-engagement email.

    Body:
        action: str - The action taken ('opened' or 'clicked')
    """
    data = request.get_json()
    if not data or 'action' not in data:
        return jsonify({'error': 'Action is required'}), 400

    action = data['action']
    if action not in ['opened', 'clicked']:
        return jsonify({'error': 'Invalid action. Must be: opened or clicked'}), 400

    service = get_service()
    result = service.track_reengagement_response(member_id, action=action)

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


# ==================== Trade-In Reminder Endpoints ====================


@nudges_bp.route('/trade-in-reminder', methods=['GET'])
@require_shopify_auth
def get_members_for_trade_in_reminder():
    """
    Get members who haven't done a trade-in recently and qualify for a reminder.

    Query params:
        days: int - Minimum days since last trade-in (default: from config, typically 60)
    """
    days = request.args.get('days', type=int)
    service = get_service()
    members = service.get_members_needing_trade_in_reminder(min_days_since_last=days)

    return jsonify({
        'success': True,
        'members': members,
        'count': len(members),
        'trade_ins_enabled': service.is_trade_ins_enabled_for_tenant(),
    })


@nudges_bp.route('/trade-in-reminder/config', methods=['GET'])
@require_shopify_auth
def get_trade_in_reminder_config():
    """Get trade-in reminder nudge configuration."""
    service = get_service()
    config = service.get_trade_in_reminder_config()
    rates = service.get_trade_in_rates_for_tenant()

    return jsonify({
        'success': True,
        'config': config,
        'credit_rates': rates,
        'trade_ins_enabled': service.is_trade_ins_enabled_for_tenant(),
    })


@nudges_bp.route('/trade-in-reminder/config', methods=['PUT'])
@require_shopify_auth
def update_trade_in_reminder_config():
    """
    Update trade-in reminder nudge configuration.

    Body:
        enabled: bool - Enable/disable the nudge
        min_days_since_last: int - Days since last trade-in to trigger reminder
        frequency_days: int - Cooldown days between reminders
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    service = get_service()
    result = service.update_trade_in_reminder_config(
        enabled=data.get('enabled'),
        min_days_since_last=data.get('min_days_since_last'),
        frequency_days=data.get('frequency_days'),
    )

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@nudges_bp.route('/trade-in-reminder/send/<int:member_id>', methods=['POST'])
@require_shopify_auth
def send_trade_in_reminder(member_id):
    """
    Send trade-in reminder to a specific member.

    Query params:
        force: bool - Skip cooldown check (default: False)
    """
    force = request.args.get('force', 'false').lower() == 'true'
    service = get_service()
    result = service.send_trade_in_reminder(member_id, force=force)

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@nudges_bp.route('/trade-in-reminder/process', methods=['POST'])
@require_shopify_auth
def process_trade_in_reminders():
    """
    Process and send trade-in reminders to all eligible members.

    Query params:
        days: int - Minimum days since last trade-in (uses config if not provided)
        max_emails: int - Maximum emails to send (default: 50)
    """
    days = request.args.get('days', type=int)
    max_emails = request.args.get('max_emails', 50, type=int)

    service = get_service()
    result = service.process_trade_in_reminders(
        min_days_since_last=days,
        max_emails=max_emails
    )

    return jsonify(result)


@nudges_bp.route('/trade-in-reminder/stats', methods=['GET'])
@require_shopify_auth
def get_trade_in_reminder_stats():
    """
    Get trade-in reminder effectiveness statistics.

    Query params:
        days: int - Days to analyze (default: 30)
    """
    days = request.args.get('days', 30, type=int)
    service = get_service()
    stats = service.get_trade_in_reminder_stats(days=days)

    return jsonify({
        'success': True,
        'stats': stats,
    })


@nudges_bp.route('/trade-in-reminder/history', methods=['GET'])
@require_shopify_auth
def get_trade_in_reminder_history():
    """
    Get trade-in reminder history.

    Query params:
        member_id: int - Filter to specific member (optional)
        days: int - Days to look back (default: 30)
    """
    member_id = request.args.get('member_id', type=int)
    days = request.args.get('days', 30, type=int)
    service = get_service()
    history = service.get_trade_in_reminder_history(member_id=member_id, days=days)

    return jsonify({
        'success': True,
        'history': history,
        'count': len(history),
    })


# ==================== All Configs Endpoint ====================


@nudges_bp.route('/configs', methods=['GET'])
@require_shopify_auth
def get_all_configs():
    """
    Get all nudge configurations for the tenant.

    Returns all nudge types with their current settings.
    """
    service = get_service()
    configs = service.get_all_nudge_configs()

    # If no configs exist, create defaults
    if not configs:
        from app.models.nudge_config import NudgeConfig
        configs = NudgeConfig.create_defaults_for_tenant(g.tenant.id)

    return jsonify({
        'success': True,
        'configs': [c.to_dict() for c in configs],
    })


@nudges_bp.route('/configs/<nudge_type>', methods=['PUT'])
@require_shopify_auth
def update_nudge_config(nudge_type):
    """
    Update a specific nudge configuration.

    Body:
        is_enabled: bool - Enable/disable the nudge
        frequency_days: int - Days between nudges
        message_template: str - Message template with placeholders
        config_options: dict - Type-specific options
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    from app.models.nudge_config import NudgeConfig

    config = NudgeConfig.get_by_type(g.tenant.id, nudge_type)

    if not config:
        # Create config if it doesn't exist
        from app.models.nudge_config import NudgeConfig, NudgeType, DEFAULT_NUDGE_TEMPLATES, DEFAULT_NUDGE_FREQUENCY
        try:
            nudge_type_enum = NudgeType(nudge_type)
        except ValueError:
            return jsonify({'error': f'Invalid nudge type: {nudge_type}'}), 400

        config = NudgeConfig(
            tenant_id=g.tenant.id,
            nudge_type=nudge_type,
            is_enabled=data.get('is_enabled', True),
            frequency_days=data.get('frequency_days', DEFAULT_NUDGE_FREQUENCY.get(nudge_type_enum, 7)),
            message_template=data.get('message_template', DEFAULT_NUDGE_TEMPLATES.get(nudge_type_enum, '')),
            config_options=data.get('config_options', {}),
        )
        from app import db
        db.session.add(config)
    else:
        # Update existing config
        if 'is_enabled' in data:
            config.is_enabled = data['is_enabled']
        if 'frequency_days' in data:
            config.frequency_days = data['frequency_days']
        if 'message_template' in data:
            config.message_template = data['message_template']
        if 'config_options' in data:
            config.config_options = data['config_options']

    from app import db
    db.session.commit()

    return jsonify({
        'success': True,
        'config': config.to_dict(),
    })


# ==================== Test Send Endpoint ====================


@nudges_bp.route('/test-send', methods=['POST'])
@require_shopify_auth
def send_test_nudge():
    """
    Send a test nudge to the store owner.

    Body:
        nudge_type: str - Type of nudge to test
        to_email: str - Email to send to (optional, defaults to store email)
        to_name: str - Name for greeting (optional)
    """
    data = request.get_json()
    if not data or 'nudge_type' not in data:
        return jsonify({'error': 'nudge_type is required'}), 400

    nudge_type = data['nudge_type']
    to_email = data.get('to_email') or g.tenant.owner_email
    to_name = data.get('to_name') or g.tenant.shop_name or 'Store Owner'

    # Get the nudge config
    service = get_service()
    config = service.get_nudge_config(nudge_type)

    if not config:
        # Use default template
        from app.models.nudge_config import NudgeType, DEFAULT_NUDGE_TEMPLATES
        try:
            nudge_type_enum = NudgeType(nudge_type)
            template = DEFAULT_NUDGE_TEMPLATES.get(nudge_type_enum, 'Test nudge message')
        except ValueError:
            return jsonify({'error': f'Invalid nudge type: {nudge_type}'}), 400
    else:
        template = config.message_template

    # Fill in template with test data
    test_message = template.format(
        member_name=to_name,
        shop_name=g.tenant.shop_name or 'Your Store',
        expiring_points='100',
        days_until='7',
        progress_percent='85',
        next_tier='Gold',
        points_needed='150',
        days_inactive='30',
    )

    # Try to send email
    try:
        from app.services.email_service import EmailService
        email_service = EmailService(g.tenant.id)
        result = email_service.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=f'[TEST] {nudge_type.replace("_", " ").title()} Nudge from {g.tenant.shop_name or "TradeUp"}',
            body_text=test_message,
            body_html=f'<p>{test_message}</p><hr><p><em>This is a test nudge. In production, this would be sent to actual members.</em></p>',
        )

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f'Test nudge sent to {to_email}',
                'nudge_type': nudge_type,
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to send test nudge'),
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ==================== Nudge Effectiveness Tracking Endpoints ====================


@nudges_bp.route('/track/open/<tracking_id>', methods=['GET'])
def track_nudge_open(tracking_id):
    """
    Track email open via tracking pixel.

    This endpoint is called when the tracking pixel in an email is loaded.
    Returns a 1x1 transparent GIF.

    No authentication required - tracking pixels are embedded in emails.
    """
    from app.models.nudge_sent import NudgeSent
    import base64

    # Find the nudge by tracking ID
    nudge = NudgeSent.get_by_tracking_id(tracking_id)

    if nudge and not nudge.opened_at:
        nudge.mark_opened()

    # Return a 1x1 transparent GIF
    gif_data = base64.b64decode(
        'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
    )

    from flask import Response
    return Response(gif_data, mimetype='image/gif')


@nudges_bp.route('/track/click/<tracking_id>', methods=['GET'])
def track_nudge_click(tracking_id):
    """
    Track link click and redirect to the destination URL.

    Query params:
        url: The destination URL to redirect to (required)

    No authentication required - tracking links are embedded in emails.
    """
    from app.models.nudge_sent import NudgeSent
    from flask import redirect, request

    # Find the nudge by tracking ID
    nudge = NudgeSent.get_by_tracking_id(tracking_id)

    if nudge:
        nudge.mark_clicked()

    # Get the redirect URL from query params
    redirect_url = request.args.get('url', '/')

    return redirect(redirect_url)


@nudges_bp.route('/track/conversion', methods=['POST'])
@require_shopify_auth
def track_nudge_conversion():
    """
    Track nudge conversion (purchase after nudge).

    Body:
        tracking_id: str - The nudge tracking ID (optional, will find most recent for member)
        member_id: int - The member who converted (required if no tracking_id)
        order_id: str - Shopify order ID (optional)
        order_total: float - Order total amount (optional)

    This can be called:
    1. With tracking_id - directly track a specific nudge
    2. With member_id - find the most recent nudge sent to member within conversion window
    """
    from app.models.nudge_sent import NudgeSent
    from datetime import datetime, timedelta

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    tracking_id = data.get('tracking_id')
    member_id = data.get('member_id')
    order_id = data.get('order_id')
    order_total = data.get('order_total')

    nudge = None

    if tracking_id:
        # Direct tracking by ID
        nudge = NudgeSent.get_by_tracking_id(tracking_id)
    elif member_id:
        # Find most recent nudge for this member within conversion window (7 days)
        conversion_window = datetime.utcnow() - timedelta(days=7)
        nudge = NudgeSent.query.filter(
            NudgeSent.tenant_id == g.tenant.id,
            NudgeSent.member_id == member_id,
            NudgeSent.sent_at >= conversion_window,
            NudgeSent.converted_at.is_(None)  # Not already converted
        ).order_by(NudgeSent.sent_at.desc()).first()
    else:
        return jsonify({'error': 'Either tracking_id or member_id is required'}), 400

    if not nudge:
        return jsonify({
            'success': False,
            'error': 'No nudge found for conversion tracking'
        }), 404

    # Mark as converted
    nudge.mark_converted(order_id=order_id, order_total=order_total)

    return jsonify({
        'success': True,
        'nudge_id': nudge.id,
        'nudge_type': nudge.nudge_type,
        'converted_at': nudge.converted_at.isoformat(),
        'order_id': nudge.order_id,
        'order_total': float(nudge.order_total) if nudge.order_total else None,
    })


@nudges_bp.route('/metrics', methods=['GET'])
@require_shopify_auth
def get_nudge_effectiveness_metrics():
    """
    Get comprehensive nudge effectiveness metrics.

    Query params:
        days: int - Number of days to analyze (default: 30)
        nudge_type: str - Filter to specific nudge type (optional)

    Returns overall metrics including open rate, click rate, conversion rate, and ROI.
    """
    from app.models.nudge_sent import NudgeSent

    days = request.args.get('days', 30, type=int)
    nudge_type = request.args.get('nudge_type')

    metrics = NudgeSent.get_effectiveness_metrics(
        tenant_id=g.tenant.id,
        nudge_type=nudge_type,
        days=days
    )

    return jsonify({
        'success': True,
        'metrics': metrics,
    })


@nudges_bp.route('/metrics/by-type', methods=['GET'])
@require_shopify_auth
def get_nudge_metrics_by_type():
    """
    Get nudge effectiveness metrics broken down by nudge type.

    Query params:
        days: int - Number of days to analyze (default: 30)

    Returns metrics for each nudge type.
    """
    from app.models.nudge_sent import NudgeSent

    days = request.args.get('days', 30, type=int)

    metrics_by_type = NudgeSent.get_metrics_by_type(
        tenant_id=g.tenant.id,
        days=days
    )

    # Calculate totals across all types
    totals = {
        'total_sent': sum(m['total_sent'] for m in metrics_by_type),
        'total_opened': sum(m['opened'] for m in metrics_by_type),
        'total_clicked': sum(m['clicked'] for m in metrics_by_type),
        'total_converted': sum(m['converted'] for m in metrics_by_type),
        'total_revenue': sum(m['total_revenue'] for m in metrics_by_type),
    }

    if totals['total_sent'] > 0:
        totals['overall_open_rate'] = round(totals['total_opened'] / totals['total_sent'] * 100, 2)
        totals['overall_click_rate'] = round(totals['total_clicked'] / totals['total_sent'] * 100, 2)
        totals['overall_conversion_rate'] = round(totals['total_converted'] / totals['total_sent'] * 100, 2)
        totals['overall_revenue_per_send'] = round(totals['total_revenue'] / totals['total_sent'], 2)
    else:
        totals['overall_open_rate'] = 0.0
        totals['overall_click_rate'] = 0.0
        totals['overall_conversion_rate'] = 0.0
        totals['overall_revenue_per_send'] = 0.0

    return jsonify({
        'success': True,
        'period_days': days,
        'by_type': metrics_by_type,
        'totals': totals,
    })


@nudges_bp.route('/metrics/daily', methods=['GET'])
@require_shopify_auth
def get_nudge_daily_metrics():
    """
    Get daily breakdown of nudge metrics for trending charts.

    Query params:
        days: int - Number of days to include (default: 30)
        nudge_type: str - Filter to specific nudge type (optional)

    Returns daily metrics for charting trends.
    """
    from app.models.nudge_sent import NudgeSent

    days = request.args.get('days', 30, type=int)
    nudge_type = request.args.get('nudge_type')

    daily_metrics = NudgeSent.get_daily_metrics(
        tenant_id=g.tenant.id,
        nudge_type=nudge_type,
        days=days
    )

    return jsonify({
        'success': True,
        'period_days': days,
        'nudge_type': nudge_type,
        'daily': daily_metrics,
    })


@nudges_bp.route('/metrics/roi', methods=['GET'])
@require_shopify_auth
def get_nudge_roi_metrics():
    """
    Get ROI metrics for nudge campaigns.

    Query params:
        days: int - Number of days to analyze (default: 30)

    Returns ROI calculations including revenue, conversions, and value metrics.
    """
    from app.models.nudge_sent import NudgeSent
    from app.models.nudge_config import NudgeType

    days = request.args.get('days', 30, type=int)

    # Get metrics by type
    metrics_by_type = NudgeSent.get_metrics_by_type(
        tenant_id=g.tenant.id,
        days=days
    )

    # Calculate ROI metrics
    total_revenue = sum(m['total_revenue'] for m in metrics_by_type)
    total_conversions = sum(m['converted'] for m in metrics_by_type)
    total_sent = sum(m['total_sent'] for m in metrics_by_type)

    # Estimate cost (can be customized per tenant)
    # For now, assume $0.01 per email sent (typical email service cost)
    estimated_cost_per_email = 0.01
    total_cost = total_sent * estimated_cost_per_email

    # Calculate ROI
    roi_percentage = 0.0
    if total_cost > 0:
        roi_percentage = round((total_revenue - total_cost) / total_cost * 100, 2)

    # Best performing nudge type by conversion rate
    best_by_conversion = None
    best_by_revenue = None

    if metrics_by_type:
        # Filter to types with at least some conversions
        with_conversions = [m for m in metrics_by_type if m['converted'] > 0]
        if with_conversions:
            best_by_conversion = max(with_conversions, key=lambda x: x['conversion_rate'])
            best_by_revenue = max(with_conversions, key=lambda x: x['total_revenue'])

    return jsonify({
        'success': True,
        'period_days': days,
        'roi_metrics': {
            'total_revenue': round(total_revenue, 2),
            'total_conversions': total_conversions,
            'total_nudges_sent': total_sent,
            'estimated_cost': round(total_cost, 2),
            'roi_percentage': roi_percentage,
            'revenue_per_nudge': round(total_revenue / total_sent, 2) if total_sent > 0 else 0.0,
            'cost_per_conversion': round(total_cost / total_conversions, 2) if total_conversions > 0 else 0.0,
        },
        'best_performers': {
            'by_conversion_rate': {
                'nudge_type': best_by_conversion['nudge_type'] if best_by_conversion else None,
                'conversion_rate': best_by_conversion['conversion_rate'] if best_by_conversion else 0.0,
            } if best_by_conversion else None,
            'by_revenue': {
                'nudge_type': best_by_revenue['nudge_type'] if best_by_revenue else None,
                'total_revenue': best_by_revenue['total_revenue'] if best_by_revenue else 0.0,
            } if best_by_revenue else None,
        },
        'by_type': metrics_by_type,
    })
