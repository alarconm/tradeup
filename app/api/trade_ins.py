"""
Trade-in API endpoints.
"""
from flask import Blueprint, request, jsonify, g
from datetime import datetime
from ..extensions import db
from ..models import TradeInBatch, TradeInItem, Member
from ..services.trade_in_service import TradeInService
from ..middleware.shopify_auth import require_shopify_auth

trade_ins_bp = Blueprint('trade_ins', __name__)


@trade_ins_bp.route('', methods=['GET'])
@require_shopify_auth
def list_batches():
    """
    List trade-in batches (both member and guest).

    Query params:
        - page: Page number (default: 1)
        - per_page: Items per page (default: 50)
        - status: Filter by status
        - member_id: Filter by specific member
        - guest_only: If 'true', show only guest trade-ins
    """
    try:
        tenant_id = g.tenant_id

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)  # Cap at 100
        status = request.args.get('status')
        member_id = request.args.get('member_id', type=int)
        guest_only = request.args.get('guest_only', '').lower() == 'true'

        # Use outer join to include both member and guest trade-ins
        # Filter by tenant: either through member or by checking there's no member (guest)
        query = TradeInBatch.query.outerjoin(
            Member, TradeInBatch.member_id == Member.id
        ).filter(
            db.or_(
                Member.tenant_id == tenant_id,
                TradeInBatch.member_id.is_(None)  # Guest trade-ins
            )
        )

        if status and status != 'all':
            query = query.filter(TradeInBatch.status == status)
        if member_id:
            query = query.filter(TradeInBatch.member_id == member_id)
        if guest_only:
            query = query.filter(TradeInBatch.member_id.is_(None))

        pagination = query.order_by(TradeInBatch.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Safely convert to dict, handling any relationship issues
        batches = []
        for batch in pagination.items:
            try:
                batches.append(batch.to_dict())
            except Exception as e:
                # If to_dict fails for a batch, include basic info
                batches.append({
                    'id': batch.id,
                    'batch_reference': batch.batch_reference,
                    'status': batch.status,
                    'total_items': batch.total_items or 0,
                    'total_trade_value': float(batch.total_trade_value or 0),
                    'created_at': batch.created_at.isoformat() if batch.created_at else None,
                    'error': f'Serialization error: {str(e)}'
                })

        return jsonify({
            'batches': batches,
            'total': pagination.total,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        import traceback
        print(f"[TradeIns] Error listing batches: {e}")
        traceback.print_exc()
        return jsonify({
            'batches': [],
            'total': 0,
            'page': 1,
            'per_page': per_page if 'per_page' in dir() else 50,
            'error': str(e)
        }), 200  # Return 200 with error for graceful degradation


@trade_ins_bp.route('/<int:batch_id>', methods=['GET'])
@require_shopify_auth
def get_batch(batch_id):
    """Get trade-in batch details with items."""
    batch = TradeInBatch.query.get_or_404(batch_id)
    return jsonify(batch.to_dict(include_items=True))


@trade_ins_bp.route('/by-reference/<batch_reference>', methods=['GET'])
@require_shopify_auth
def get_batch_by_reference(batch_reference):
    """Get batch by reference number."""
    batch = TradeInBatch.query.filter_by(batch_reference=batch_reference).first_or_404()
    return jsonify(batch.to_dict(include_items=True))


@trade_ins_bp.route('', methods=['POST'])
@require_shopify_auth
def create_batch():
    """
    Create a new trade-in batch.

    Supports both member and non-member (guest) trade-ins:
    - For members: provide member_id
    - For guests: provide guest_name, guest_email, and optionally guest_phone
    """
    tenant_id = g.tenant_id
    data = request.json

    member_id = data.get('member_id')
    guest_name = data.get('guest_name')
    guest_email = data.get('guest_email')
    guest_phone = data.get('guest_phone')

    # Require either member_id or guest info
    if not member_id and not (guest_name or guest_email):
        return jsonify({'error': 'Either member_id or guest info (guest_name/guest_email) is required'}), 400

    service = TradeInService(tenant_id)

    try:
        batch = service.create_batch(
            member_id=member_id,
            guest_name=guest_name,
            guest_email=guest_email,
            guest_phone=guest_phone,
            notes=data.get('notes'),
            created_by=data.get('created_by', 'API'),
            category=data.get('category', 'other')
        )
        return jsonify(batch.to_dict()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@trade_ins_bp.route('/categories', methods=['GET'])
@require_shopify_auth
def get_categories():
    """
    Get available trade-in categories.

    Returns a mix of:
    1. Default templates (Pokemon, Magic, Sports, etc.)
    2. Store's Shopify collections (if available)

    Query params:
        - include_collections: If 'true', fetch collections from Shopify
    """
    # Default category templates for TCGs and collectibles
    default_templates = [
        {'id': 'pokemon', 'icon': '⚡', 'name': 'Pokemon', 'is_template': True},
        {'id': 'magic', 'icon': '🔮', 'name': 'Magic: The Gathering', 'is_template': True},
        {'id': 'yugioh', 'icon': '🃏', 'name': 'Yu-Gi-Oh!', 'is_template': True},
        {'id': 'sports', 'icon': '🏈', 'name': 'Sports Cards', 'is_template': True},
        {'id': 'baseball', 'icon': '⚾', 'name': 'Baseball Cards', 'is_template': True},
        {'id': 'basketball', 'icon': '🏀', 'name': 'Basketball Cards', 'is_template': True},
        {'id': 'football', 'icon': '🏈', 'name': 'Football Cards', 'is_template': True},
        {'id': 'hockey', 'icon': '🏒', 'name': 'Hockey Cards', 'is_template': True},
        {'id': 'one_piece', 'icon': '🏴‍☠️', 'name': 'One Piece', 'is_template': True},
        {'id': 'disney_lorcana', 'icon': '✨', 'name': 'Disney Lorcana', 'is_template': True},
        {'id': 'flesh_blood', 'icon': '⚔️', 'name': 'Flesh and Blood', 'is_template': True},
        {'id': 'digimon', 'icon': '🦖', 'name': 'Digimon', 'is_template': True},
        {'id': 'weiss', 'icon': '🎭', 'name': 'Weiss Schwarz', 'is_template': True},
        {'id': 'tcg_other', 'icon': '🎴', 'name': 'Other TCG', 'is_template': True},
        {'id': 'videogames', 'icon': '🎮', 'name': 'Video Games', 'is_template': True},
        {'id': 'comics', 'icon': '📚', 'name': 'Comics', 'is_template': True},
        {'id': 'figures', 'icon': '🎨', 'name': 'Figures & Toys', 'is_template': True},
        {'id': 'other', 'icon': '📦', 'name': 'Other', 'is_template': True},
    ]

    categories = list(default_templates)

    # Try to fetch Shopify collections
    include_collections = request.args.get('include_collections', 'true').lower() == 'true'
    if include_collections:
        try:
            from ..services.shopify_client import ShopifyClient
            tenant = g.tenant
            if tenant and tenant.shopify_domain and tenant.shopify_access_token:
                client = ShopifyClient(g.tenant_id)
                collections = client.get_collections()

                # Add collections that aren't already in templates
                template_names_lower = {t['name'].lower() for t in default_templates}
                for coll in collections:
                    if coll and coll.get('title'):
                        # Skip if name matches a template
                        if coll['title'].lower() not in template_names_lower:
                            categories.append({
                                'id': f"collection_{coll['id']}",
                                'icon': '📁',
                                'name': coll['title'],
                                'is_template': False,
                                'collection_id': coll['id']
                            })
        except Exception as e:
            # Log but don't fail - just return templates
            print(f"[TradeIns] Failed to fetch collections: {e}")

    return jsonify({
        'categories': categories,
        'templates_count': len(default_templates),
        'has_collections': len(categories) > len(default_templates)
    })


@trade_ins_bp.route('/<int:batch_id>/items', methods=['POST'])
@require_shopify_auth
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
@require_shopify_auth
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
@require_shopify_auth
def mark_item_sold(item_id):
    """Mark an item as sold (usually called by webhook)."""
    item = TradeInItem.query.get_or_404(item_id)
    data = request.json

    item.sold_date = datetime.utcnow()
    item.sold_price = data['sold_price']
    item.shopify_order_id = data.get('shopify_order_id')

    # Calculate days to sell (for analytics)
    if item.listed_date:
        item.days_to_sell = item.calculate_days_to_sell()

    db.session.commit()

    return jsonify(item.to_dict())


@trade_ins_bp.route('/items/by-product/<shopify_product_id>', methods=['GET'])
@require_shopify_auth
def get_item_by_product(shopify_product_id):
    """Get trade-in item by Shopify product ID."""
    item = TradeInItem.query.filter_by(
        shopify_product_id=shopify_product_id
    ).first_or_404()

    return jsonify(item.to_dict())


@trade_ins_bp.route('/<int:batch_id>/preview-bonus', methods=['GET'])
@require_shopify_auth
def preview_batch_bonus(batch_id):
    """
    Preview the tier bonus for a batch (without issuing it).

    Returns:
        Bonus calculation based on member's tier
    """
    tenant_id = g.tenant_id
    service = TradeInService(tenant_id)

    try:
        result = service.preview_batch_bonus(batch_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@trade_ins_bp.route('/<int:batch_id>/complete', methods=['POST'])
@require_shopify_auth
def complete_batch(batch_id):
    """
    Complete a trade-in batch and issue tier bonus credit.

    This marks the batch as completed and issues store credit
    based on the member's tier bonus rate.

    Bonus = total_trade_value × tier.bonus_rate

    Request body (optional):
        created_by: string - Who completed the batch

    Returns:
        Completion details with bonus info
    """
    tenant_id = g.tenant_id
    staff_email = request.headers.get('X-Staff-Email', 'API')

    data = request.json or {}
    created_by = data.get('created_by', staff_email)

    service = TradeInService(tenant_id)

    try:
        result = service.complete_batch(
            batch_id=batch_id,
            created_by=created_by
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to complete batch: {str(e)}'}), 500
