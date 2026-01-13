"""
Dashboard API endpoints.
"""
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
from sqlalchemy import func
from ..extensions import db
from ..models import Member, MembershipTier, TradeInBatch, TradeInItem, StoreCreditLedger, Tenant, TradeInLedger
from ..middleware.shopify_auth import require_shopify_auth

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/stats', methods=['GET'])
@require_shopify_auth
def get_dashboard_stats():
    """
    Get dashboard statistics overview.

    Returns format expected by EmbeddedDashboard.tsx:
    - total_members, active_members (flat)
    - pending_trade_ins, completed_trade_ins
    - total_trade_in_value, total_credits_issued
    - subscription object with plan and usage
    """
    try:
        tenant_id = g.tenant_id

        # Get tenant for subscription info
        tenant = g.tenant

        # Member counts
        total_members = Member.query.filter_by(tenant_id=tenant_id).count()
        active_members = Member.query.filter_by(
            tenant_id=tenant_id,
            status='active'
        ).count()

        # Trade-in ledger stats (simplified)
        ledger_stats = db.session.query(
            func.count(TradeInLedger.id).label('total_count'),
            func.coalesce(func.sum(TradeInLedger.total_value), 0).label('total_value'),
            func.coalesce(func.sum(TradeInLedger.cash_amount), 0).label('total_cash'),
            func.coalesce(func.sum(TradeInLedger.credit_amount), 0).label('total_credit'),
        ).filter(TradeInLedger.tenant_id == tenant_id).first()

        # Use ledger counts for dashboard
        total_trade_ins = ledger_stats.total_count if ledger_stats else 0
        pending_trade_ins = 0  # No pending status in ledger - all entries are complete
        completed_trade_ins = total_trade_ins
        total_trade_in_value = float(ledger_stats.total_value if ledger_stats else 0)
        total_cash_paid = float(ledger_stats.total_cash if ledger_stats else 0)
        total_credit_paid = float(ledger_stats.total_credit if ledger_stats else 0)

        # Total credits issued (all time, positive amounts only)
        total_credits_result = (
            db.session.query(
                func.coalesce(func.sum(StoreCreditLedger.amount), 0)
            )
            .join(Member, StoreCreditLedger.member_id == Member.id)
            .filter(
                Member.tenant_id == tenant_id,
                StoreCreditLedger.amount > 0
            )
            .scalar()
        )
        total_credits_issued = float(total_credits_result or 0)

        # Tier count for usage (only active tiers)
        tier_count = MembershipTier.query.filter_by(tenant_id=tenant_id, is_active=True).count()

        # Build subscription object
        max_members = tenant.max_members if tenant else 100
        max_tiers = tenant.max_tiers if tenant else 3

        member_percentage = (total_members / max_members * 100) if max_members else 0
        tier_percentage = (tier_count / max_tiers * 100) if max_tiers else 0

        subscription = {
            'plan': tenant.subscription_plan if tenant else 'starter',
            'status': tenant.subscription_status if tenant else 'pending',
            'active': tenant.subscription_active if tenant else False,
            'usage': {
                'members': {
                    'current': total_members,
                    'limit': max_members,
                    'percentage': min(100, round(member_percentage, 1))
                },
                'tiers': {
                    'current': tier_count,
                    'limit': max_tiers,
                    'percentage': min(100, round(tier_percentage, 1))
                }
            }
        }

        # Get timezone from tenant settings (synced from Shopify)
        tenant_settings = tenant.settings or {} if tenant else {}
        general_settings = tenant_settings.get('general', {})
        timezone = general_settings.get('timezone', 'America/Los_Angeles')

        # Check membership products status
        products_state = tenant_settings.get('membership_products', {})
        has_products = bool(products_state.get('products'))
        products_draft = products_state.get('draft_mode', False) if has_products else False

        # Check if wizard is in progress
        wizard_state = tenant_settings.get('product_wizard', {})
        wizard_in_progress = wizard_state.get('draft_in_progress', False)

        return jsonify({
            'total_members': total_members,
            'active_members': active_members,
            'total_trade_ins': total_trade_ins,  # Total ledger entries
            'pending_trade_ins': pending_trade_ins,
            'completed_trade_ins': completed_trade_ins,
            'total_trade_in_value': total_trade_in_value,
            'total_cash_paid': total_cash_paid,  # Trade-ins paid in cash
            'total_credit_paid': total_credit_paid,  # Trade-ins paid as credit
            'total_credits_issued': total_credits_issued,
            'subscription': subscription,
            'timezone': timezone,
            # Product wizard status for dashboard warnings
            'membership_products_count': len(products_state.get('products', [])),
            'membership_products_draft': products_draft,
            'product_wizard_in_progress': wizard_in_progress,
        })
    except Exception as e:
        import traceback
        print(f"[Dashboard] Error getting stats: {e}")
        traceback.print_exc()
        # Return safe defaults matching expected interface
        return jsonify({
            'total_members': 0,
            'active_members': 0,
            'total_trade_ins': 0,
            'pending_trade_ins': 0,
            'completed_trade_ins': 0,
            'total_trade_in_value': 0,
            'total_cash_paid': 0,
            'total_credit_paid': 0,
            'total_credits_issued': 0,
            'subscription': {
                'plan': 'starter',
                'status': 'pending',
                'active': False,
                'usage': {
                    'members': {'current': 0, 'limit': 100, 'percentage': 0},
                    'tiers': {'current': 0, 'limit': 3, 'percentage': 0}
                }
            },
            'timezone': 'America/Los_Angeles',
            'membership_products_count': 0,
            'membership_products_draft': False,
            'product_wizard_in_progress': False,
            'error': str(e)
        }), 200


@dashboard_bp.route('/stats/period', methods=['GET'])
@require_shopify_auth
def get_dashboard_stats_for_period():
    """
    Get dashboard statistics for a specific time period.

    Query params:
    - start_date: ISO format date string (YYYY-MM-DD)
    - end_date: ISO format date string (YYYY-MM-DD)
    - period: 'today', 'week', 'month', 'quarter', 'year' (alternative to start/end)

    Returns stats filtered to the specified date range.
    """
    try:
        tenant_id = g.tenant_id

        # Parse date range
        period = request.args.get('period')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        now = datetime.utcnow()

        if period:
            # Use predefined period
            if period == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = now
            elif period == 'week':
                start_date = now - timedelta(days=7)
                end_date = now
            elif period == 'month':
                start_date = now - timedelta(days=30)
                end_date = now
            elif period == 'quarter':
                start_date = now - timedelta(days=90)
                end_date = now
            elif period == 'year':
                start_date = now - timedelta(days=365)
                end_date = now
            else:
                return jsonify({'error': f'Invalid period: {period}'}), 400
        elif start_date_str and end_date_str:
            # Parse custom date range
            try:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}), 400
        else:
            # Default to last 30 days
            start_date = now - timedelta(days=30)
            end_date = now

        # Members created in period
        new_members = Member.query.filter(
            Member.tenant_id == tenant_id,
            Member.created_at >= start_date,
            Member.created_at <= end_date
        ).count()

        # Trade-in ledger stats for period
        ledger_stats = db.session.query(
            func.count(TradeInLedger.id).label('total_count'),
            func.coalesce(func.sum(TradeInLedger.total_value), 0).label('total_value'),
            func.coalesce(func.sum(TradeInLedger.cash_amount), 0).label('total_cash'),
            func.coalesce(func.sum(TradeInLedger.credit_amount), 0).label('total_credit'),
        ).filter(
            TradeInLedger.tenant_id == tenant_id,
            TradeInLedger.created_at >= start_date,
            TradeInLedger.created_at <= end_date
        ).first()

        trade_ins_count = ledger_stats.total_count if ledger_stats else 0
        trade_in_value = float(ledger_stats.total_value if ledger_stats else 0)
        cash_paid = float(ledger_stats.total_cash if ledger_stats else 0)
        credit_paid = float(ledger_stats.total_credit if ledger_stats else 0)

        # Credits issued in period (positive amounts only)
        credits_result = (
            db.session.query(
                func.coalesce(func.sum(StoreCreditLedger.amount), 0)
            )
            .join(Member, StoreCreditLedger.member_id == Member.id)
            .filter(
                Member.tenant_id == tenant_id,
                StoreCreditLedger.amount > 0,
                StoreCreditLedger.created_at >= start_date,
                StoreCreditLedger.created_at <= end_date
            )
            .scalar()
        )
        credits_issued = float(credits_result or 0)

        # Calculate comparison with previous period
        period_length = (end_date - start_date).days
        prev_start = start_date - timedelta(days=period_length)
        prev_end = start_date

        # Previous period trade-ins
        prev_ledger_stats = db.session.query(
            func.count(TradeInLedger.id).label('total_count'),
            func.coalesce(func.sum(TradeInLedger.total_value), 0).label('total_value'),
        ).filter(
            TradeInLedger.tenant_id == tenant_id,
            TradeInLedger.created_at >= prev_start,
            TradeInLedger.created_at <= prev_end
        ).first()

        prev_trade_ins = prev_ledger_stats.total_count if prev_ledger_stats else 0
        prev_trade_in_value = float(prev_ledger_stats.total_value if prev_ledger_stats else 0)

        # Previous period members
        prev_new_members = Member.query.filter(
            Member.tenant_id == tenant_id,
            Member.created_at >= prev_start,
            Member.created_at <= prev_end
        ).count()

        # Calculate percentage changes
        def calc_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 1)

        return jsonify({
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': period_length
            },
            'current': {
                'new_members': new_members,
                'trade_ins': trade_ins_count,
                'trade_in_value': trade_in_value,
                'cash_paid': cash_paid,
                'credit_paid': credit_paid,
                'credits_issued': credits_issued,
            },
            'previous': {
                'new_members': prev_new_members,
                'trade_ins': prev_trade_ins,
                'trade_in_value': prev_trade_in_value,
            },
            'changes': {
                'new_members': calc_change(new_members, prev_new_members),
                'trade_ins': calc_change(trade_ins_count, prev_trade_ins),
                'trade_in_value': calc_change(trade_in_value, prev_trade_in_value),
            }
        })

    except Exception as e:
        import traceback
        print(f"[Dashboard] Error getting period stats: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/trade-in-report', methods=['GET'])
@require_shopify_auth
def get_trade_in_report():
    """Get trade-in performance report."""
    tenant_id = g.tenant_id
    days = request.args.get('days', 30, type=int)

    start_date = datetime.utcnow() - timedelta(days=days)

    # Get trade-ins in period
    trade_ins = (
        TradeInBatch.query
        .join(Member)
        .filter(
            Member.tenant_id == tenant_id,
            TradeInBatch.created_at >= start_date
        )
        .all()
    )

    total_batches = len(trade_ins)
    total_items = sum(b.total_items or 0 for b in trade_ins)  # Use stored count, not items relationship
    total_value = sum(float(b.total_trade_value or 0) for b in trade_ins)

    # Status breakdown
    status_counts = {}
    for batch in trade_ins:
        status = batch.status
        status_counts[status] = status_counts.get(status, 0) + 1

    return jsonify({
        'period_days': days,
        'total_batches': total_batches,
        'total_items': total_items,
        'total_value': round(total_value, 2),
        'status_breakdown': status_counts
    })


@dashboard_bp.route('/top-members', methods=['GET'])
@require_shopify_auth
def get_top_members():
    """Get top members by trade-in value."""
    tenant_id = g.tenant_id
    limit = request.args.get('limit', 10, type=int)

    top_members = (
        Member.query
        .filter_by(tenant_id=tenant_id, status='active')
        .order_by(Member.total_trade_value.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        'members': [m.to_dict(include_stats=True) for m in top_members]
    })


@dashboard_bp.route('/recent-activity', methods=['GET'])
@require_shopify_auth
def get_recent_activity():
    """Get recent trade-ins and credit transactions."""
    tenant_id = g.tenant_id
    limit = request.args.get('limit', 20, type=int)

    # Recent trade-ins
    recent_batches = (
        TradeInBatch.query
        .join(Member)
        .filter(Member.tenant_id == tenant_id)
        .order_by(TradeInBatch.created_at.desc())
        .limit(limit)
        .all()
    )

    # Recent credit transactions (join through Member for tenant filtering)
    recent_credits = (
        StoreCreditLedger.query
        .join(Member)
        .filter(Member.tenant_id == tenant_id)
        .order_by(StoreCreditLedger.created_at.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        'recent_trade_ins': [b.to_dict() for b in recent_batches],
        'recent_credits': [c.to_dict() for c in recent_credits]
    })


@dashboard_bp.route('/activity', methods=['GET'])
@require_shopify_auth
def get_activity():
    """
    Get recent activity feed for dashboard.

    Returns format expected by EmbeddedDashboard.tsx:
    [{id, type, member_name, description, amount, created_at}, ...]
    """
    try:
        tenant_id = g.tenant_id
        limit = request.args.get('limit', 10, type=int)

        activities = []

        # Get recent trade-ins
        recent_batches = (
            TradeInBatch.query
            .join(Member, isouter=True)
            .filter(
                db.or_(
                    Member.tenant_id == tenant_id,
                    TradeInBatch.member_id.is_(None)
                )
            )
            .order_by(TradeInBatch.created_at.desc())
            .limit(limit)
            .all()
        )

        for batch in recent_batches:
            member_name = 'Guest'
            if batch.member:
                member_name = batch.member.name or batch.member.email or 'Member'
            elif batch.guest_name:
                member_name = batch.guest_name

            activities.append({
                'id': batch.id,
                'type': 'trade_in',
                'member_name': member_name,
                'description': f"{batch.total_items or 0} items trade-in ({batch.status})",
                'amount': float(batch.total_trade_value or 0),
                'created_at': batch.created_at.isoformat() if batch.created_at else None
            })

        # Get recent credit transactions
        recent_credits = (
            StoreCreditLedger.query
            .join(Member)
            .filter(Member.tenant_id == tenant_id)
            .order_by(StoreCreditLedger.created_at.desc())
            .limit(limit)
            .all()
        )

        for credit in recent_credits:
            member_name = credit.member.name or credit.member.email or 'Member'
            credit_type = 'credit' if credit.amount > 0 else 'debit'

            activities.append({
                'id': credit.id + 100000,  # Offset to avoid ID collision
                'type': credit_type,
                'member_name': member_name,
                'description': credit.description or f"Store {credit_type}",
                'amount': abs(float(credit.amount)),
                'created_at': credit.created_at.isoformat() if credit.created_at else None
            })

        # Sort by created_at and limit
        activities.sort(key=lambda x: x['created_at'] or '', reverse=True)
        activities = activities[:limit]

        return jsonify(activities)
    except Exception as e:
        import traceback
        print(f"[Dashboard] Error getting activity: {e}")
        traceback.print_exc()
        return jsonify([]), 200


@dashboard_bp.route('/daily-report', methods=['GET'])
@require_shopify_auth
def get_daily_report():
    """
    Get daily report with comprehensive metrics for the dashboard widget.

    Query params:
    - date: ISO date (YYYY-MM-DD), defaults to today

    Returns:
    - date: Report date
    - metrics: Key performance indicators
    - comparison: Comparison with previous day
    - top_trade_ins: Highest value trade-ins today
    - new_members_list: Members enrolled today
    - summary: Human-readable summary text
    """
    try:
        tenant_id = g.tenant_id

        # Parse date (default to today)
        date_str = request.args.get('date')
        if date_str:
            try:
                report_date = datetime.fromisoformat(date_str).date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            report_date = datetime.utcnow().date()

        # Date range for today (start of day to end of day)
        start_of_day = datetime.combine(report_date, datetime.min.time())
        end_of_day = datetime.combine(report_date, datetime.max.time())

        # Previous day range
        prev_date = report_date - timedelta(days=1)
        prev_start = datetime.combine(prev_date, datetime.min.time())
        prev_end = datetime.combine(prev_date, datetime.max.time())

        # ==================== Today's Metrics ====================

        # New members today
        new_members_today = Member.query.filter(
            Member.tenant_id == tenant_id,
            Member.created_at >= start_of_day,
            Member.created_at <= end_of_day
        ).all()
        new_members_count = len(new_members_today)

        # Trade-in ledger stats for today
        today_ledger_stats = db.session.query(
            func.count(TradeInLedger.id).label('total_count'),
            func.coalesce(func.sum(TradeInLedger.total_value), 0).label('total_value'),
            func.coalesce(func.sum(TradeInLedger.cash_amount), 0).label('total_cash'),
            func.coalesce(func.sum(TradeInLedger.credit_amount), 0).label('total_credit'),
            func.coalesce(func.sum(TradeInLedger.bonus_amount), 0).label('total_bonus'),
        ).filter(
            TradeInLedger.tenant_id == tenant_id,
            TradeInLedger.created_at >= start_of_day,
            TradeInLedger.created_at <= end_of_day
        ).first()

        trade_ins_today = today_ledger_stats.total_count if today_ledger_stats else 0
        trade_in_value_today = float(today_ledger_stats.total_value if today_ledger_stats else 0)
        cash_paid_today = float(today_ledger_stats.total_cash if today_ledger_stats else 0)
        credit_paid_today = float(today_ledger_stats.total_credit if today_ledger_stats else 0)
        bonus_today = float(today_ledger_stats.total_bonus if today_ledger_stats else 0)

        # Credits issued today (positive amounts only, from ledger)
        credits_result = (
            db.session.query(
                func.coalesce(func.sum(StoreCreditLedger.amount), 0)
            )
            .join(Member, StoreCreditLedger.member_id == Member.id)
            .filter(
                Member.tenant_id == tenant_id,
                StoreCreditLedger.amount > 0,
                StoreCreditLedger.created_at >= start_of_day,
                StoreCreditLedger.created_at <= end_of_day
            )
            .scalar()
        )
        credits_issued_today = float(credits_result or 0)

        # ==================== Yesterday's Metrics ====================

        # New members yesterday
        new_members_yesterday = Member.query.filter(
            Member.tenant_id == tenant_id,
            Member.created_at >= prev_start,
            Member.created_at <= prev_end
        ).count()

        # Trade-in ledger stats for yesterday
        prev_ledger_stats = db.session.query(
            func.count(TradeInLedger.id).label('total_count'),
            func.coalesce(func.sum(TradeInLedger.total_value), 0).label('total_value'),
        ).filter(
            TradeInLedger.tenant_id == tenant_id,
            TradeInLedger.created_at >= prev_start,
            TradeInLedger.created_at <= prev_end
        ).first()

        trade_ins_yesterday = prev_ledger_stats.total_count if prev_ledger_stats else 0
        trade_in_value_yesterday = float(prev_ledger_stats.total_value if prev_ledger_stats else 0)

        # ==================== Top Trade-ins Today ====================

        top_trade_ins_today = (
            TradeInLedger.query
            .filter(
                TradeInLedger.tenant_id == tenant_id,
                TradeInLedger.created_at >= start_of_day,
                TradeInLedger.created_at <= end_of_day
            )
            .order_by(TradeInLedger.total_value.desc())
            .limit(5)
            .all()
        )

        # ==================== Calculate Changes ====================

        def calc_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 1)

        # ==================== Build Summary ====================

        summary_parts = []
        if new_members_count > 0:
            summary_parts.append(f"{new_members_count} new member{'s' if new_members_count != 1 else ''}")
        if trade_ins_today > 0:
            summary_parts.append(f"{trade_ins_today} trade-in{'s' if trade_ins_today != 1 else ''} (${trade_in_value_today:,.2f})")
        if credits_issued_today > 0:
            summary_parts.append(f"${credits_issued_today:,.2f} in credits issued")

        summary = ', '.join(summary_parts) if summary_parts else 'No activity today'

        return jsonify({
            'success': True,
            'date': report_date.isoformat(),
            'day_of_week': report_date.strftime('%A'),

            # Key metrics
            'metrics': {
                'new_members': new_members_count,
                'trade_ins': trade_ins_today,
                'trade_in_value': trade_in_value_today,
                'cash_paid': cash_paid_today,
                'credit_paid': credit_paid_today,
                'bonus_issued': bonus_today,
                'credits_issued': credits_issued_today,
            },

            # Comparison with yesterday
            'comparison': {
                'new_members': {
                    'today': new_members_count,
                    'yesterday': new_members_yesterday,
                    'change_pct': calc_change(new_members_count, new_members_yesterday)
                },
                'trade_ins': {
                    'today': trade_ins_today,
                    'yesterday': trade_ins_yesterday,
                    'change_pct': calc_change(trade_ins_today, trade_ins_yesterday)
                },
                'trade_in_value': {
                    'today': trade_in_value_today,
                    'yesterday': trade_in_value_yesterday,
                    'change_pct': calc_change(trade_in_value_today, trade_in_value_yesterday)
                }
            },

            # Top trade-ins today
            'top_trade_ins': [
                {
                    'id': ti.id,
                    'member_name': ti.member_name or 'Guest',
                    'total_value': float(ti.total_value or 0),
                    'items': ti.items_json.get('count', 0) if ti.items_json else 0,
                    'payment_method': ti.payment_method or 'credit'
                }
                for ti in top_trade_ins_today
            ],

            # New members today (limited info)
            'new_members_list': [
                {
                    'id': m.id,
                    'name': m.name or m.email,
                    'member_number': m.member_number,
                    'tier': m.tier.name if m.tier else 'None'
                }
                for m in new_members_today[:5]  # Limit to 5
            ],

            # Human-readable summary
            'summary': summary
        })

    except Exception as e:
        import traceback
        print(f"[Dashboard] Error getting daily report: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'date': datetime.utcnow().date().isoformat(),
            'metrics': {
                'new_members': 0,
                'trade_ins': 0,
                'trade_in_value': 0,
                'cash_paid': 0,
                'credit_paid': 0,
                'bonus_issued': 0,
                'credits_issued': 0,
            },
            'comparison': {},
            'top_trade_ins': [],
            'new_members_list': [],
            'summary': 'Error loading report'
        }), 200
