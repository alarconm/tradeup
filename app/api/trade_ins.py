"""
Trade-in API endpoints.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from ..extensions import db
from ..models import TradeInBatch, TradeInItem, Member
from ..services.trade_in_service import TradeInService

trade_ins_bp = Blueprint('trade_ins', __name__)


@trade_ins_bp.route('', methods=['GET'])
def list_batches():
    """List trade-in batches."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status')
    member_id = request.args.get('member_id', type=int)

    # Join with members to filter by tenant
    query = TradeInBatch.query.join(Member).filter(Member.tenant_id == tenant_id)

    if status:
        query = query.filter(TradeInBatch.status == status)
    if member_id:
        query = query.filter(TradeInBatch.member_id == member_id)

    pagination = query.order_by(TradeInBatch.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'batches': [b.to_dict() for b in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page
    })


@trade_ins_bp.route('/<int:batch_id>', methods=['GET'])
def get_batch(batch_id):
    """Get trade-in batch details with items."""
    batch = TradeInBatch.query.get_or_404(batch_id)
    return jsonify(batch.to_dict(include_items=True))


@trade_ins_bp.route('/by-reference/<batch_reference>', methods=['GET'])
def get_batch_by_reference(batch_reference):
    """Get batch by reference number."""
    batch = TradeInBatch.query.filter_by(batch_reference=batch_reference).first_or_404()
    return jsonify(batch.to_dict(include_items=True))


@trade_ins_bp.route('', methods=['POST'])
def create_batch():
    """Create a new trade-in batch."""
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))
    data = request.json

    service = TradeInService(tenant_id)

    try:
        batch = service.create_batch(
            member_id=data['member_id'],
            notes=data.get('notes'),
            created_by=data.get('created_by', 'API')
        )
        return jsonify(batch.to_dict()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@trade_ins_bp.route('/<int:batch_id>/items', methods=['POST'])
def add_items(batch_id):
    """Add items to a trade-in batch."""
    batch = TradeInBatch.query.get_or_404(batch_id)
    data = request.json

    items_data = data.get('items', [data])  # Support single item or array

    created_items = []
    for item_data in items_data:
        item = TradeInItem(
            batch_id=batch_id,
            product_title=item_data.get('product_title'),
            product_sku=item_data.get('product_sku'),
            trade_value=item_data['trade_value'],
            market_value=item_data.get('market_value'),
            notes=item_data.get('notes')
        )
        db.session.add(item)
        created_items.append(item)

    # Update batch totals
    batch.total_items = batch.items.count() + len(created_items)
    batch.total_trade_value = sum(
        item.trade_value for item in batch.items
    ) + sum(item.trade_value for item in created_items)

    db.session.commit()

    return jsonify({
        'items': [item.to_dict() for item in created_items],
        'batch': batch.to_dict()
    }), 201


@trade_ins_bp.route('/items/<int:item_id>/listed', methods=['PUT'])
def mark_item_listed(item_id):
    """Mark an item as listed in Shopify."""
    item = TradeInItem.query.get_or_404(item_id)
    data = request.json

    item.shopify_product_id = data.get('shopify_product_id')
    item.product_title = data.get('product_title', item.product_title)
    item.listing_price = data.get('listing_price')
    item.listed_date = datetime.utcnow()

    # Update batch status if all items are listed
    batch = item.batch
    unlisted_count = TradeInItem.query.filter_by(
        batch_id=batch.id,
        listed_date=None
    ).count()

    if unlisted_count == 0:
        batch.status = 'listed'

    db.session.commit()

    return jsonify(item.to_dict())


@trade_ins_bp.route('/items/<int:item_id>/sold', methods=['PUT'])
def mark_item_sold(item_id):
    """Mark an item as sold (usually called by webhook)."""
    item = TradeInItem.query.get_or_404(item_id)
    data = request.json

    item.sold_date = datetime.utcnow()
    item.sold_price = data['sold_price']
    item.shopify_order_id = data.get('shopify_order_id')

    # Calculate days to sell
    if item.listed_date:
        item.days_to_sell = item.calculate_days_to_sell()

        # Check bonus eligibility
        member = item.batch.member
        if member and member.tier:
            quick_flip_days = member.tier.quick_flip_days
            item.eligible_for_bonus = item.days_to_sell <= quick_flip_days

    db.session.commit()

    return jsonify(item.to_dict())


@trade_ins_bp.route('/items/by-product/<shopify_product_id>', methods=['GET'])
def get_item_by_product(shopify_product_id):
    """Get trade-in item by Shopify product ID."""
    item = TradeInItem.query.filter_by(
        shopify_product_id=shopify_product_id
    ).first_or_404()

    return jsonify(item.to_dict())
