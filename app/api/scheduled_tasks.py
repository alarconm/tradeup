"""
Scheduled Tasks API endpoints.

Provides admin endpoints to:
- Run scheduled tasks manually
- Preview task results
- View task history

Also provides internal endpoints for Trigger.dev job processing:
- Batch member processing
- Individual credit issuance
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
from decimal import Decimal
from ..extensions import db
from ..middleware.shopify_auth import require_shopify_auth
from ..services.scheduled_tasks import scheduled_tasks_service
from ..services.store_credit_service import StoreCreditService
from ..models.member import Member, MembershipTier
from ..models.promotions import StoreCreditLedger

scheduled_tasks_bp = Blueprint('scheduled_tasks', __name__)


# ==================== MONTHLY CREDITS ====================

@scheduled_tasks_bp.route('/monthly-credits/preview', methods=['GET'])
@require_shopify_auth
def preview_monthly_credits():
    """
    Preview monthly credit distribution without issuing.

    Returns:
        Preview of what would be distributed
    """
    tenant_id = g.tenant_id

    result = scheduled_tasks_service.get_monthly_credit_preview(tenant_id)

    return jsonify(result)


@scheduled_tasks_bp.route('/monthly-credits/run', methods=['POST'])
@require_shopify_auth
def run_monthly_credits():
    """
    Manually trigger monthly credit distribution.

    This should normally run automatically on the 1st of each month,
    but admins can trigger it manually if needed.
    """
    tenant_id = g.tenant_id

    result = scheduled_tasks_service.distribute_monthly_credits(
        tenant_id=tenant_id,
        dry_run=False
    )

    return jsonify({
        'success': True,
        'message': f"Distributed ${result['total_amount']:.2f} to {result['credited']} members",
        'result': result
    })


# ==================== CREDIT EXPIRATION ====================

@scheduled_tasks_bp.route('/expiration/preview', methods=['GET'])
@require_shopify_auth
def preview_expiration():
    """
    Preview credits that have expired but not yet processed.
    """
    tenant_id = g.tenant_id

    result = scheduled_tasks_service.expire_old_credits(tenant_id, dry_run=True)

    return jsonify(result)


@scheduled_tasks_bp.route('/expiration/run', methods=['POST'])
@require_shopify_auth
def run_expiration():
    """
    Manually trigger credit expiration.
    """
    tenant_id = g.tenant_id

    result = scheduled_tasks_service.expire_old_credits(
        tenant_id=tenant_id,
        dry_run=False
    )

    return jsonify({
        'success': True,
        'message': f"Expired ${result['total_expired']:.2f} from {result['members_affected']} members",
        'result': result
    })


@scheduled_tasks_bp.route('/expiration/upcoming', methods=['GET'])
@require_shopify_auth
def get_upcoming_expirations():
    """
    Get credits expiring soon (for warning notifications).
    """
    tenant_id = g.tenant_id
    days = request.args.get('days', 7, type=int)

    result = scheduled_tasks_service.get_expiring_credits_preview(
        tenant_id=tenant_id,
        days_ahead=days
    )

    return jsonify(result)


# ==================== REFERRAL STATS ====================

@scheduled_tasks_bp.route('/referrals/stats', methods=['GET'])
@require_shopify_auth
def get_referral_stats():
    """
    Get comprehensive referral program statistics.
    """
    tenant_id = g.tenant_id

    stats = scheduled_tasks_service.calculate_referral_stats(tenant_id)

    return jsonify(stats)


# ==================== TRIGGER.DEV INTERNAL ENDPOINTS ====================
# These endpoints are called by the Trigger.dev jobs service
# They use require_shop_auth which accepts internal API keys

@scheduled_tasks_bp.route('/monthly-credits/eligible-batch', methods=['POST'])
@require_shopify_auth
def get_eligible_batch():
    """
    Get a batch of members eligible for monthly credits.
    Used by Trigger.dev for paginated processing.
    """
    tenant_id = g.tenant_id
    data = request.get_json() or {}

    cursor = data.get('cursor')
    batch_size = min(data.get('batchSize', 100), 500)  # Max 500 per batch
    month_key = data.get('monthKey', datetime.utcnow().strftime('%Y-%m'))

    # Parse month key for filtering
    current_month_start = datetime.strptime(month_key + '-01', '%Y-%m-%d')

    # Query eligible members with cursor-based pagination
    query = db.session.query(Member).join(
        MembershipTier, Member.tier_id == MembershipTier.id
    ).filter(
        Member.tenant_id == tenant_id,
        Member.status == 'active',
        MembershipTier.monthly_credit_amount > 0,
        MembershipTier.is_active == True
    )

    if cursor:
        query = query.filter(Member.id > cursor)

    query = query.order_by(Member.id).limit(batch_size + 1)
    members = query.all()

    # Check if there are more
    has_more = len(members) > batch_size
    if has_more:
        members = members[:batch_size]

    # Filter out members who already received credit this month
    eligible_members = []
    for member in members:
        existing = StoreCreditLedger.query.filter(
            StoreCreditLedger.member_id == member.id,
            StoreCreditLedger.event_type == 'monthly_credit',
            StoreCreditLedger.created_at >= current_month_start
        ).first()

        if not existing:
            eligible_members.append({
                'id': member.id,
                'member_number': member.member_number,
                'email': member.email,
                'tier_id': member.tier_id,
                'tier_name': member.tier.name if member.tier else None,
                'monthly_credit_amount': float(member.tier.monthly_credit_amount) if member.tier else 0,
            })

    next_cursor = members[-1].id if members else None

    return jsonify({
        'members': eligible_members,
        'nextCursor': next_cursor,
        'hasMore': has_more,
    })


@scheduled_tasks_bp.route('/monthly-credits/issue', methods=['POST'])
@require_shopify_auth
def issue_single_credit():
    """
    Issue monthly credit to a single member.
    Idempotent - checks if already credited this month.
    Used by Trigger.dev for individual member processing.
    """
    tenant_id = g.tenant_id
    data = request.get_json() or {}

    member_id = data.get('memberId')
    month_key = data.get('monthKey', datetime.utcnow().strftime('%Y-%m'))

    if not member_id:
        return jsonify({'error': 'memberId required'}), 400

    member = Member.query.filter_by(id=member_id, tenant_id=tenant_id).first()
    if not member:
        return jsonify({
            'credited': False,
            'amount': None,
            'reason': 'Member not found'
        })

    if not member.tier or not member.tier.monthly_credit_amount:
        return jsonify({
            'credited': False,
            'amount': None,
            'reason': 'Member tier has no monthly credit'
        })

    # Check for existing credit this month (idempotency)
    current_month_start = datetime.strptime(month_key + '-01', '%Y-%m-%d')
    existing = StoreCreditLedger.query.filter(
        StoreCreditLedger.member_id == member_id,
        StoreCreditLedger.event_type == 'monthly_credit',
        StoreCreditLedger.created_at >= current_month_start
    ).first()

    if existing:
        return jsonify({
            'credited': False,
            'amount': None,
            'reason': 'Already received monthly credit this month'
        })

    # Issue the credit
    try:
        now = datetime.utcnow()
        credit_amount = member.tier.monthly_credit_amount

        expires_at = None
        if member.tier.credit_expiration_days:
            expires_at = now + timedelta(days=member.tier.credit_expiration_days)

        store_credit_service = StoreCreditService()
        store_credit_service.add_credit(
            member_id=member_id,
            amount=credit_amount,
            event_type='monthly_credit',
            description=f'Monthly {member.tier.name} tier credit - {now.strftime("%B %Y")}',
            source_type='monthly_credit',
            source_id=f'monthly-{month_key}',
            created_by='system:trigger-dev',
            expires_at=expires_at
        )

        return jsonify({
            'credited': True,
            'amount': float(credit_amount),
            'reason': 'Credit issued successfully'
        })

    except Exception as e:
        return jsonify({
            'credited': False,
            'amount': None,
            'reason': f'Error: {str(e)}'
        }), 500


@scheduled_tasks_bp.route('/expiration/process-batch', methods=['POST'])
@require_shopify_auth
def process_expiration_batch():
    """
    Process a batch of expired credits.
    Used by Trigger.dev for paginated expiration processing.
    """
    tenant_id = g.tenant_id
    data = request.get_json() or {}

    cursor = data.get('cursor')
    batch_size = min(data.get('batchSize', 100), 500)

    now = datetime.utcnow()

    # Find expired credits
    query = db.session.query(StoreCreditLedger).join(
        Member, StoreCreditLedger.member_id == Member.id
    ).filter(
        Member.tenant_id == tenant_id,
        StoreCreditLedger.expires_at.isnot(None),
        StoreCreditLedger.expires_at < now,
        StoreCreditLedger.amount > 0,
        StoreCreditLedger.event_type != 'expiration'
    )

    if cursor:
        query = query.filter(StoreCreditLedger.id > cursor)

    query = query.order_by(StoreCreditLedger.id).limit(batch_size + 1)
    credits = query.all()

    has_more = len(credits) > batch_size
    if has_more:
        credits = credits[:batch_size]

    processed = 0
    expired = 0
    expired_amount = Decimal('0')
    errors = 0

    for credit in credits:
        processed += 1

        # Check if already expired
        already_expired = StoreCreditLedger.query.filter(
            StoreCreditLedger.member_id == credit.member_id,
            StoreCreditLedger.event_type == 'expiration',
            StoreCreditLedger.source_id == f'expired:{credit.id}'
        ).first()

        if already_expired:
            continue

        try:
            # Create expiration entry
            expiration_entry = StoreCreditLedger(
                member_id=credit.member_id,
                tenant_id=tenant_id,
                event_type='expiration',
                amount=-credit.amount,
                balance_after=Decimal('0'),
                description=f'Credit expired (issued {credit.created_at.strftime("%Y-%m-%d")})',
                source_type='expiration',
                source_id=f'expired:{credit.id}',
                source_reference=credit.source_reference,
                created_by='system:trigger-dev'
            )
            db.session.add(expiration_entry)
            expired += 1
            expired_amount += credit.amount
        except Exception as e:
            errors += 1

    if expired > 0:
        db.session.commit()

    next_cursor = credits[-1].id if credits else None

    return jsonify({
        'processed': processed,
        'expired': expired,
        'expiredAmount': float(expired_amount),
        'errors': errors,
        'nextCursor': next_cursor,
        'hasMore': has_more,
    })


# ==================== NUDGES PROCESSING ====================

@scheduled_tasks_bp.route('/nudges/preview', methods=['GET'])
@require_shopify_auth
def preview_nudges():
    """
    Preview all pending nudges for the tenant.

    Shows members eligible for:
    - Points expiring reminders
    - Tier progress reminders
    - Inactive re-engagement
    - Trade-in reminders
    """
    tenant_id = g.tenant_id
    settings = g.tenant.settings or {}

    from ..services.nudges_service import NudgesService

    nudge_service = NudgesService(tenant_id, settings)
    nudges = nudge_service.get_all_pending_nudges()

    return jsonify(nudges)


@scheduled_tasks_bp.route('/nudges/run', methods=['POST'])
@require_shopify_auth
def run_nudges():
    """
    Manually trigger nudges processing for this tenant.

    Processes all enabled nudge types:
    - Points expiring reminders
    - Tier progress reminders
    - Inactive member re-engagement
    - Trade-in reminders

    Query params:
        max_emails: int - Maximum total emails to send (default: 100)
    """
    tenant_id = g.tenant_id
    settings = g.tenant.settings or {}
    max_emails = request.args.get('max_emails', 100, type=int)

    from ..services.nudges_service import NudgesService

    nudge_service = NudgesService(tenant_id, settings)

    # Check if nudges are enabled
    nudge_settings = nudge_service.get_nudge_settings()
    if not nudge_settings.get('enabled', True):
        return jsonify({
            'success': False,
            'error': 'Nudges are disabled for this tenant',
        }), 400

    results = {
        'success': True,
        'total_sent': 0,
        'points_expiring': None,
        'tier_progress': None,
        'inactive_reengagement': None,
        'trade_in_reminder': None,
    }

    emails_sent = 0
    max_per_type = min(50, max_emails // 4)  # Split across 4 types

    # 1. Points expiring
    if nudge_service.is_nudge_enabled('points_expiring') and emails_sent < max_emails:
        result = nudge_service.process_points_expiring_reminders()
        results['points_expiring'] = result
        if result.get('success'):
            emails_sent += result.get('reminders_sent', 0)

    # 2. Tier progress
    if nudge_service.is_nudge_enabled('tier_progress') and emails_sent < max_emails:
        result = nudge_service.process_tier_progress_reminders()
        results['tier_progress'] = result
        if result.get('success'):
            emails_sent += result.get('reminders_sent', 0)

    # 3. Inactive re-engagement
    if nudge_service.is_nudge_enabled('inactive_reminder') and emails_sent < max_emails:
        remaining = max_emails - emails_sent
        result = nudge_service.process_reengagement_emails(max_emails=remaining)
        results['inactive_reengagement'] = result
        if result.get('success'):
            emails_sent += result.get('emails_sent', 0)

    # 4. Trade-in reminders
    if nudge_service.is_nudge_enabled('trade_in_reminder') and emails_sent < max_emails:
        remaining = max_emails - emails_sent
        result = nudge_service.process_trade_in_reminders(max_emails=remaining)
        results['trade_in_reminder'] = result
        if result.get('success'):
            emails_sent += result.get('reminders_sent', 0)

    results['total_sent'] = emails_sent
    results['message'] = f'Processed nudges: {emails_sent} emails sent'

    return jsonify(results)


@scheduled_tasks_bp.route('/nudges/stats', methods=['GET'])
@require_shopify_auth
def get_nudges_stats():
    """
    Get nudge statistics and effectiveness metrics.

    Query params:
        days: int - Days to analyze (default: 30)
    """
    tenant_id = g.tenant_id
    settings = g.tenant.settings or {}
    days = request.args.get('days', 30, type=int)

    from ..services.nudges_service import NudgesService
    from ..models.nudge_sent import NudgeSent

    nudge_service = NudgesService(tenant_id, settings)

    # Get stats from NudgeSent model
    overall_stats = NudgeSent.get_stats_for_tenant(tenant_id, days=days)

    # Get effectiveness stats for each type
    effectiveness = {
        'reengagement': nudge_service.get_reengagement_stats(days=days),
        'trade_in_reminder': nudge_service.get_trade_in_reminder_stats(days=days),
    }

    return jsonify({
        'success': True,
        'period_days': days,
        'overall': overall_stats,
        'effectiveness': effectiveness,
    })


# ==================== SCHEDULER STATUS ====================

@scheduled_tasks_bp.route('/scheduler/status', methods=['GET'])
@require_shopify_auth
def get_scheduler_status():
    """
    Get background scheduler status and next run times.
    """
    try:
        from ..utils.scheduler import get_next_run_times
        jobs = get_next_run_times()
    except ImportError:
        jobs = {'error': 'APScheduler not installed'}

    return jsonify({
        'scheduler': jobs,
        'message': 'Jobs run automatically in production. Use /run endpoints for manual triggering.'
    })
