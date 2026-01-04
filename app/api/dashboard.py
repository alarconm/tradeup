"""
Dashboard API endpoints.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func
from ..extensions import db
from ..models import Member, TradeInBatch, TradeInItem, BonusTransaction

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics overview."""
    tenant_id = request.headers.get('X-Tenant-ID', 1)

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

    # Bonuses issued this month
    bonuses_this_month = db.session.query(
        func.count(BonusTransaction.id).label('count'),
        func.sum(BonusTransaction.bonus_amount).label('total')
    ).join(Member).filter(
        Member.tenant_id == tenant_id,
        BonusTransaction.created_at >= start_of_month,
        BonusTransaction.transaction_type == 'credit'
    ).first()

    # Quick flip success rate (items sold within window / total sold)
    sold_items = (
        TradeInItem.query
        .join(TradeInItem.batch)
        .join(Member)
        .filter(
            Member.tenant_id == tenant_id,
            TradeInItem.sold_date.isnot(None)
        )
    )
    total_sold = sold_items.count()
    quick_flips = sold_items.filter(TradeInItem.eligible_for_bonus == True).count()
    success_rate = (quick_flips / total_sold * 100) if total_sold > 0 else 0

    return jsonify({
        'members': {
            'active': active_members,
            'total': total_members
        },
        'trade_ins_this_month': trade_ins_this_month,
        'bonuses_this_month': {
            'count': bonuses_this_month.count or 0,
            'total': float(bonuses_this_month.total or 0)
        },
        'quick_flip_success_rate': round(success_rate, 1)
    })


@dashboard_bp.route('/quick-flip-report', methods=['GET'])
def get_quick_flip_report():
    """Get Quick Flip performance report."""
    tenant_id = request.headers.get('X-Tenant-ID', 1)
    days = request.args.get('days', 30, type=int)

    start_date = datetime.utcnow() - timedelta(days=days)

    # Get items sold in period with bonus eligibility
    sold_items = (
        TradeInItem.query
        .join(TradeInItem.batch)
        .join(Member)
        .filter(
            Member.tenant_id == tenant_id,
            TradeInItem.sold_date >= start_date,
            TradeInItem.sold_date.isnot(None)
        )
        .all()
    )

    # Aggregate stats
    total_items = len(sold_items)
    eligible_items = [i for i in sold_items if i.eligible_for_bonus]
    total_eligible = len(eligible_items)

    total_bonuses = sum(
        float(i.bonus_amount or 0) for i in sold_items if i.bonus_amount
    )

    avg_days_to_sell = (
        sum(i.days_to_sell or 0 for i in sold_items if i.days_to_sell) / total_items
        if total_items > 0 else 0
    )

    # Group by days to sell
    days_distribution = {}
    for item in sold_items:
        if item.days_to_sell is not None:
            bucket = min(item.days_to_sell, 30)  # Cap at 30 for display
            days_distribution[bucket] = days_distribution.get(bucket, 0) + 1

    return jsonify({
        'period_days': days,
        'total_items_sold': total_items,
        'quick_flip_eligible': total_eligible,
        'success_rate': round((total_eligible / total_items * 100) if total_items > 0 else 0, 1),
        'total_bonuses_issued': total_bonuses,
        'avg_days_to_sell': round(avg_days_to_sell, 1),
        'days_distribution': days_distribution
    })


@dashboard_bp.route('/top-members', methods=['GET'])
def get_top_members():
    """Get top members by bonus earned."""
    tenant_id = request.headers.get('X-Tenant-ID', 1)
    limit = request.args.get('limit', 10, type=int)

    top_members = (
        Member.query
        .filter_by(tenant_id=tenant_id, status='active')
        .order_by(Member.total_bonus_earned.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        'members': [m.to_dict(include_stats=True) for m in top_members]
    })


@dashboard_bp.route('/recent-activity', methods=['GET'])
def get_recent_activity():
    """Get recent trade-ins and bonuses."""
    tenant_id = request.headers.get('X-Tenant-ID', 1)
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

    # Recent bonuses
    recent_bonuses = (
        BonusTransaction.query
        .join(Member)
        .filter(Member.tenant_id == tenant_id)
        .order_by(BonusTransaction.created_at.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        'recent_trade_ins': [b.to_dict() for b in recent_batches],
        'recent_bonuses': [b.to_dict() for b in recent_bonuses]
    })
