"""
Dashboard API endpoints.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func
from ..extensions import db
from ..models import Member, TradeInBatch, TradeInItem, StoreCreditLedger

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics overview."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    # Active members count
    active_members = Member.query.filter_by(
        tenant_id=tenant_id,
        status='active'
    ).count()

    # Total members
    total_members = Member.query.filter_by(tenant_id=tenant_id).count()

    # Trade-ins this month
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    trade_ins_this_month = (
        TradeInBatch.query
        .join(Member)
        .filter(
            Member.tenant_id == tenant_id,
            TradeInBatch.created_at >= start_of_month
        )
        .count()
    )

    # Store credit issued this month (join through Member for tenant filtering)
    credit_this_month = db.session.query(
        func.count(StoreCreditLedger.id).label('count'),
        func.sum(StoreCreditLedger.amount).label('total')
    ).join(Member).filter(
        Member.tenant_id == tenant_id,
        StoreCreditLedger.created_at >= start_of_month,
        StoreCreditLedger.amount > 0  # Only credits, not debits
    ).first()

    return jsonify({
        'members': {
            'active': active_members,
            'total': total_members
        },
        'trade_ins_this_month': trade_ins_this_month,
        'credit_this_month': {
            'count': credit_this_month.count or 0,
            'total': float(credit_this_month.total or 0)
        }
    })


@dashboard_bp.route('/trade-in-report', methods=['GET'])
def get_trade_in_report():
    """Get trade-in performance report."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
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
def get_top_members():
    """Get top members by trade-in value."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
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
def get_recent_activity():
    """Get recent trade-ins and credit transactions."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
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
