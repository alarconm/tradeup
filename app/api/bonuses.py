"""
Bonus API endpoints.
"""
from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import BonusTransaction, TradeInItem, Member
from ..services.bonus_calculator import BonusCalculator
from ..services.bonus_processor import BonusProcessor

bonuses_bp = Blueprint('bonuses', __name__)


@bonuses_bp.route('/pending', methods=['GET'])
def get_pending_bonuses():
    """Get items eligible for bonus but not yet processed."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    # Find items that are eligible but not yet issued
    pending_items = (
        TradeInItem.query
        .join(TradeInItem.batch)
        .join(Member)
        .filter(
            Member.tenant_id == tenant_id,
            TradeInItem.eligible_for_bonus == True,
            TradeInItem.bonus_status == 'pending'
        )
        .all()
    )

    return jsonify({
        'pending_count': len(pending_items),
        'items': [item.to_dict() for item in pending_items]
    })


@bonuses_bp.route('/process', methods=['POST'])
def process_bonuses():
    """Process all pending bonuses and issue store credits."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
    data = request.json or {}

    processor = BonusProcessor(tenant_id)

    try:
        results = processor.process_pending_bonuses(
            dry_run=data.get('dry_run', False),
            created_by=data.get('created_by', 'API')
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bonuses_bp.route('/calculate/<int:item_id>', methods=['GET'])
def calculate_bonus(item_id):
    """Calculate potential bonus for an item (preview, doesn't issue)."""
    item = TradeInItem.query.get_or_404(item_id)

    calculator = BonusCalculator()
    bonus_info = calculator.calculate_bonus(item)

    return jsonify(bonus_info)


@bonuses_bp.route('/history', methods=['GET'])
def get_bonus_history():
    """Get bonus transaction history."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    member_id = request.args.get('member_id', type=int)

    query = (
        BonusTransaction.query
        .join(Member)
        .filter(Member.tenant_id == tenant_id)
    )

    if member_id:
        query = query.filter(BonusTransaction.member_id == member_id)

    pagination = query.order_by(BonusTransaction.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'transactions': [t.to_dict() for t in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page
    })


@bonuses_bp.route('/stats', methods=['GET'])
def get_bonus_stats():
    """Get bonus statistics."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    # Total bonuses issued
    from sqlalchemy import func

    stats = db.session.query(
        func.count(BonusTransaction.id).label('total_transactions'),
        func.sum(BonusTransaction.bonus_amount).label('total_amount')
    ).join(Member).filter(
        Member.tenant_id == tenant_id,
        BonusTransaction.transaction_type == 'credit'
    ).first()

    # Pending bonuses
    pending_count = (
        TradeInItem.query
        .join(TradeInItem.batch)
        .join(Member)
        .filter(
            Member.tenant_id == tenant_id,
            TradeInItem.eligible_for_bonus == True,
            TradeInItem.bonus_status == 'pending'
        )
        .count()
    )

    return jsonify({
        'total_transactions': stats.total_transactions or 0,
        'total_amount_issued': float(stats.total_amount or 0),
        'pending_count': pending_count
    })
