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
        - search: Search by batch reference, guest name/email, or member name/email
        - category: Filter by category
    """
    try:
        tenant_id = g.tenant_id

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)  # Cap at 100
        status = request.args.get('status')
        member_id = request.args.get('member_id', type=int)
        guest_only = request.args.get('guest_only', '').lower() == 'true'
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()

        # Filter directly by tenant_id (now stored on batch for both member and guest trade-ins)
        query = TradeInBatch.query.filter_by(tenant_id=tenant_id)

        if status and status != 'all':
            query = query.filter(TradeInBatch.status == status)
        if member_id:
            query = query.filter(TradeInBatch.member_id == member_id)
        if guest_only:
            query = query.filter(TradeInBatch.member_id.is_(None))

        # Search by batch reference, guest info, or member info
        if search:
            search_pattern = f'%{search}%'
            # Join with Member table for member name/email search
            query = query.outerjoin(Member, TradeInBatch.member_id == Member.id)
            query = query.filter(
                db.or_(
                    TradeInBatch.batch_reference.ilike(search_pattern),
                    TradeInBatch.guest_name.ilike(search_pattern),
                    TradeInBatch.guest_email.ilike(search_pattern),
                    Member.name.ilike(search_pattern),
                    Member.email.ilike(search_pattern),
                    Member.member_number.ilike(search_pattern)
                )
            )

        # Filter by category
        if category:
            query = query.filter(TradeInBatch.category == category)

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
            'error': 'Failed to list trade-in batches',
            'batches': [],
            'total': 0
        }), 500


@trade_ins_bp.route('/<int:batch_id>', methods=['GET'])
@require_shopify_auth
def get_batch(batch_id):
    """Get trade-in batch details with items."""
    tenant_id = g.tenant_id
    batch = TradeInBatch.query.filter_by(id=batch_id, tenant_id=tenant_id).first_or_404()
    return jsonify(batch.to_dict(include_items=True))


@trade_ins_bp.route('/by-reference/<batch_reference>', methods=['GET'])
@require_shopify_auth
def get_batch_by_reference(batch_reference):
    """Get batch by reference number."""
    tenant_id = g.tenant_id
    batch = TradeInBatch.query.filter_by(batch_reference=batch_reference, tenant_id=tenant_id).first_or_404()
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
    tenant_id = g.tenant_id
    batch = TradeInBatch.query.filter_by(id=batch_id, tenant_id=tenant_id).first_or_404()
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
    tenant_id = g.tenant_id
    item = TradeInItem.query.join(TradeInBatch).filter(
        TradeInItem.id == item_id,
        TradeInBatch.tenant_id == tenant_id
    ).first_or_404()
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
    tenant_id = g.tenant_id
    item = TradeInItem.query.join(TradeInBatch).filter(
        TradeInItem.id == item_id,
        TradeInBatch.tenant_id == tenant_id
    ).first_or_404()
    data = request.json

    item.sold_date = datetime.utcnow()
    item.sold_price = data['sold_price']
    item.shopify_order_id = data.get('shopify_order_id')

    # Calculate days to sell (for analytics)
    if item.listed_date:
        item.days_to_sell = item.calculate_days_to_sell()

    db.session.commit()

    return jsonify(item.to_dict())


@trade_ins_bp.route('/items/<int:item_id>', methods=['PUT'])
@require_shopify_auth
def update_item(item_id):
    """
    Update a trade-in item.

    Only allows updates to items in pending/in_review batches.
    Once a batch is approved/completed, items cannot be edited.

    Request body:
        product_title: string (optional)
        product_sku: string (optional)
        trade_value: number (optional)
        market_value: number (optional)
        notes: string (optional)

    Returns:
        Updated item details
    """
    tenant_id = g.tenant_id
    item = TradeInItem.query.join(TradeInBatch).filter(
        TradeInItem.id == item_id,
        TradeInBatch.tenant_id == tenant_id
    ).first_or_404()

    batch = item.batch

    # Only allow edits on pending/in_review batches
    if batch.status not in ('pending', 'in_review'):
        return jsonify({
            'error': f'Cannot edit items in a {batch.status} batch. Items can only be edited before approval.'
        }), 400

    # Also block if item is already listed/sold
    if item.listed_date:
        return jsonify({
            'error': 'Cannot edit an item that has already been listed.'
        }), 400

    if item.sold_date:
        return jsonify({
            'error': 'Cannot edit an item that has already been sold.'
        }), 400

    data = request.json
    old_trade_value = item.trade_value

    # Update allowed fields
    if 'product_title' in data:
        item.product_title = data['product_title']
    if 'product_sku' in data:
        item.product_sku = data['product_sku']
    if 'trade_value' in data:
        item.trade_value = data['trade_value']
    if 'market_value' in data:
        item.market_value = data['market_value']
    if 'notes' in data:
        item.notes = data['notes']

    # Recalculate batch totals if trade_value changed
    if 'trade_value' in data and data['trade_value'] != old_trade_value:
        batch.total_trade_value = sum(i.trade_value for i in batch.items)

    db.session.commit()

    return jsonify({
        'item': item.to_dict(),
        'batch': batch.to_dict()
    })


@trade_ins_bp.route('/items/<int:item_id>', methods=['DELETE'])
@require_shopify_auth
def delete_item(item_id):
    """
    Delete a trade-in item.

    Only allows deletion from pending/in_review batches.

    Returns:
        Success message and updated batch details
    """
    tenant_id = g.tenant_id
    item = TradeInItem.query.join(TradeInBatch).filter(
        TradeInItem.id == item_id,
        TradeInBatch.tenant_id == tenant_id
    ).first_or_404()

    batch = item.batch

    # Only allow deletion from pending/in_review batches
    if batch.status not in ('pending', 'in_review'):
        return jsonify({
            'error': f'Cannot delete items from a {batch.status} batch.'
        }), 400

    if item.listed_date or item.sold_date:
        return jsonify({
            'error': 'Cannot delete an item that has been listed or sold.'
        }), 400

    db.session.delete(item)

    # Update batch totals
    batch.total_items = batch.items.count() - 1  # -1 because delete not committed yet
    batch.total_trade_value = sum(i.trade_value for i in batch.items if i.id != item_id)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Item deleted successfully',
        'batch': batch.to_dict()
    })


@trade_ins_bp.route('/items/by-product/<shopify_product_id>', methods=['GET'])
@require_shopify_auth
def get_item_by_product(shopify_product_id):
    """Get trade-in item by Shopify product ID."""
    tenant_id = g.tenant_id
    item = TradeInItem.query.join(TradeInBatch).filter(
        TradeInItem.shopify_product_id == shopify_product_id,
        TradeInBatch.tenant_id == tenant_id
    ).first_or_404()

    return jsonify(item.to_dict())


@trade_ins_bp.route('/<int:batch_id>/apply-thresholds', methods=['POST'])
@require_shopify_auth
def apply_auto_thresholds(batch_id):
    """
    Apply auto-approval thresholds to a batch.

    Checks the batch total against tenant settings and:
    - Auto-approves if under auto_approve_under threshold
    - Marks as in_review if over require_review_over threshold
    - Otherwise leaves as pending

    Call this after all items have been added to a batch.

    Returns:
        Action taken (auto_approved, flagged_for_review, pending, skipped)
    """
    tenant_id = g.tenant_id
    service = TradeInService(tenant_id)

    try:
        result = service.apply_auto_approval_thresholds(batch_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


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


@trade_ins_bp.route('/<int:batch_id>/status', methods=['PUT'])
@require_shopify_auth
def update_batch_status(batch_id):
    """
    Update trade-in batch status and sync to Shopify customer metafields.

    Valid statuses: pending, under_review, approved, rejected, completed, listed, cancelled

    Request body:
        status: string - New status value
        reason: string (optional) - Reason for status change (useful for rejections)

    Returns:
        Status update result with sync status
    """
    tenant_id = g.tenant_id
    staff_email = request.headers.get('X-Staff-Email', 'API')

    data = request.json or {}
    new_status = data.get('status')
    reason = data.get('reason')

    if not new_status:
        return jsonify({'error': 'status is required'}), 400

    service = TradeInService(tenant_id)

    try:
        result = service.update_status(
            batch_id=batch_id,
            new_status=new_status,
            reason=reason,
            updated_by=staff_email
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to update status: {str(e)}'}), 500


@trade_ins_bp.route('/member/<int:member_id>/summary', methods=['GET'])
@require_shopify_auth
def get_member_trade_in_summary(member_id):
    """
    Get trade-in summary for a member (for customer account display).

    Returns:
        Trade-in summary with recent batches and stats
    """
    tenant_id = g.tenant_id
    service = TradeInService(tenant_id)

    result = service.get_member_trade_in_summary(member_id)
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 404


@trade_ins_bp.route('/<int:batch_id>/timeline', methods=['GET'])
@require_shopify_auth
def get_batch_timeline(batch_id):
    """
    Get timeline/history of events for a trade-in batch.

    Returns a chronological list of events including:
    - Batch creation
    - Item additions
    - Status changes
    - Completion and bonus issuance

    Returns:
        Timeline of batch events
    """
    tenant_id = g.tenant_id
    batch = TradeInBatch.query.filter_by(id=batch_id, tenant_id=tenant_id).first_or_404()

    timeline = []

    # 1. Batch creation event
    timeline.append({
        'event_type': 'batch_created',
        'description': f'Trade-in batch {batch.batch_reference} created',
        'timestamp': batch.created_at.isoformat() if batch.created_at else None,
        'actor': batch.created_by or 'System',
        'details': {
            'category': batch.category,
            'is_member': batch.member_id is not None,
            'member_name': batch.member.name if batch.member_id and batch.member else batch.guest_name
        }
    })

    # 2. Item addition events (using item creation timestamps)
    items = batch.items.order_by(TradeInItem.created_at.asc()).all()
    for item in items:
        timeline.append({
            'event_type': 'item_added',
            'description': f'Item added: {item.product_title or "Unnamed item"}',
            'timestamp': item.created_at.isoformat() if item.created_at else None,
            'actor': batch.created_by or 'System',
            'details': {
                'item_id': item.id,
                'product_title': item.product_title,
                'trade_value': float(item.trade_value)
            }
        })

    # 3. Items listed events
    for item in items:
        if item.listed_date:
            timeline.append({
                'event_type': 'item_listed',
                'description': f'Item listed on Shopify: {item.product_title or "Unnamed item"}',
                'timestamp': item.listed_date.isoformat(),
                'actor': 'System',
                'details': {
                    'item_id': item.id,
                    'product_title': item.product_title,
                    'listing_price': float(item.listing_price) if item.listing_price else None,
                    'shopify_product_id': item.shopify_product_id
                }
            })

    # 4. Items sold events
    for item in items:
        if item.sold_date:
            timeline.append({
                'event_type': 'item_sold',
                'description': f'Item sold: {item.product_title or "Unnamed item"}',
                'timestamp': item.sold_date.isoformat(),
                'actor': 'System',
                'details': {
                    'item_id': item.id,
                    'product_title': item.product_title,
                    'sold_price': float(item.sold_price) if item.sold_price else None,
                    'days_to_sell': item.days_to_sell
                }
            })

    # 5. Batch completion event
    if batch.completed_at:
        timeline.append({
            'event_type': 'batch_completed',
            'description': f'Trade-in batch completed',
            'timestamp': batch.completed_at.isoformat(),
            'actor': batch.completed_by or 'System',
            'details': {
                'total_items': batch.total_items,
                'total_trade_value': float(batch.total_trade_value),
                'bonus_amount': float(batch.bonus_amount) if batch.bonus_amount else 0
            }
        })

    # 6. Status change to current (if not pending and not completed)
    if batch.status not in ['pending', 'completed'] and batch.updated_at != batch.created_at:
        timeline.append({
            'event_type': 'status_changed',
            'description': f'Status changed to {batch.status}',
            'timestamp': batch.updated_at.isoformat() if batch.updated_at else None,
            'actor': 'System',
            'details': {
                'new_status': batch.status
            }
        })

    # Sort timeline by timestamp (oldest first)
    timeline.sort(key=lambda x: x['timestamp'] or '')

    return jsonify({
        'batch_id': batch.id,
        'batch_reference': batch.batch_reference,
        'current_status': batch.status,
        'timeline': timeline,
        'total_events': len(timeline)
    })
