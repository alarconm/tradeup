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
