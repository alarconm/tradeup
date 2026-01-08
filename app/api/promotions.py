"""
Promotions and Store Credit API for TradeUp.

Endpoints for:
- Promotion management (CRUD)
- Store credit operations
- Bulk credit operations
- Tier configuration
- Purchase cashback processing
"""

from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, request, jsonify, current_app, g
import sqlalchemy as sa
from sqlalchemy import func, and_, or_

from ..extensions import db
from ..middleware.shop_auth import require_shop_auth
from ..models.member import Member
from ..models.promotions import (
    Promotion,
    StoreCreditLedger,
    MemberCreditBalance,
    BulkCreditOperation,
    TierConfiguration,
    CreditEventType,
    seed_tier_configurations,
)
from ..services.store_credit_service import store_credit_service


promotions_bp = Blueprint('promotions', __name__)


# ==================== Health Check ====================

@promotions_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check that doesn't hit the database."""
    return jsonify({
        'status': 'ok',
        'module': 'promotions',
        'message': 'Promotions API is loaded'
    }), 200


@promotions_bp.route('/init-db', methods=['POST'])
def init_database():
    """Initialize promotions database tables (for debugging)."""
    results = {}
    try:
        # First, try to add missing columns if table exists
        try:
            db.session.execute(sa.text(
                "ALTER TABLE tier_configurations ADD COLUMN IF NOT EXISTS icon VARCHAR(50) DEFAULT 'star'"
            ))
            db.session.commit()
            results['add_icon_column'] = 'success or already exists'
        except Exception as e:
            db.session.rollback()
            results['add_icon_column'] = f'skipped: {e}'

        # Try to create tables (won't override existing)
        db.create_all()
        results['create_all'] = 'success'

        # Check if tier_configurations table exists and count rows
        try:
            count_before = TierConfiguration.query.count()
            results['tier_count_before'] = count_before
        except Exception as e:
            results['tier_count_before'] = f'error: {e}'
            count_before = -1

        # Seed tier configurations
        seed_tier_configurations()

        # Check count after seeding
        try:
            count_after = TierConfiguration.query.count()
            results['tier_count_after'] = count_after
        except Exception as e:
            results['tier_count_after'] = f'error: {e}'

        return jsonify({
            'status': 'success',
            'message': 'Database tables created and seeded',
            'details': results
        }), 200
    except Exception as e:
        results['error'] = str(e)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'details': results
        }), 500


# ==================== Promotions CRUD ====================

@promotions_bp.route('/promotions', methods=['GET'])
@require_shop_auth
def list_promotions():
    """
    List promotions with filtering.

    Query params:
        active_only: Only show active promotions
        type: Filter by promo_type
        current: Only promotions active right now
    """
    try:
        query = Promotion.query

        if request.args.get('active_only', '').lower() == 'true':
            query = query.filter(Promotion.active == True)

        promo_type = request.args.get('type')
        if promo_type:
            query = query.filter(Promotion.promo_type == promo_type)

        if request.args.get('current', '').lower() == 'true':
            now = datetime.utcnow()
            query = query.filter(
                and_(
                    Promotion.active == True,
                    Promotion.starts_at <= now,
                    Promotion.ends_at >= now,
                )
            )

        promotions = query.order_by(Promotion.starts_at.desc()).all()

        # Filter by runtime conditions for current promotions
        if request.args.get('current', '').lower() == 'true':
            promotions = [p for p in promotions if p.is_active_now()]

        return jsonify({
            'promotions': [p.to_dict() for p in promotions],
            'total': len(promotions),
        }), 200
    except Exception as e:
        # Table may not exist yet - return empty with hint
        current_app.logger.warning(f"[Promotions] list_promotions error: {e}")
        return jsonify({
            'promotions': [],
            'total': 0,
            'error': 'Could not fetch promotions - database may need migration',
            'hint': 'POST to /api/promotions/init-db to initialize tables'
        }), 200


@promotions_bp.route('/promotions', methods=['POST'])
@require_shop_auth
def create_promotion():
    """
    Create a new promotion.

    Request body:
        name: Promotion name (required)
        description: Description
        promo_type: trade_in_bonus, purchase_cashback, flat_bonus, multiplier
        bonus_percent: Percentage bonus (for % types)
        bonus_flat: Flat dollar amount (for flat_bonus)
        multiplier: Multiplier value (for multiplier type)
        starts_at: Start datetime ISO format (required)
        ends_at: End datetime ISO format (required)
        daily_start_time: Daily start time HH:MM (optional)
        daily_end_time: Daily end time HH:MM (optional)
        active_days: Comma-separated day numbers 0-6 (0=Monday)
        channel: all, in_store, online
        category_ids: Array of category IDs (optional)
        tier_restriction: Array of tier names (optional)
        min_items: Minimum items required
        min_value: Minimum value required
        stackable: Can combine with other promos
        max_uses: Total usage limit
        max_uses_per_member: Per-member limit
    """
    data = request.get_json()

    # Validate required fields
    if not data.get('name'):
        return jsonify({'error': 'name is required'}), 400
    if not data.get('starts_at'):
        return jsonify({'error': 'starts_at is required'}), 400
    if not data.get('ends_at'):
        return jsonify({'error': 'ends_at is required'}), 400

    try:
        starts_at = datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00'))
        ends_at = datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00'))
    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {e}'}), 400

    # Parse time windows
    daily_start = None
    daily_end = None
    if data.get('daily_start_time'):
        try:
            h, m = map(int, data['daily_start_time'].split(':'))
            from datetime import time
            daily_start = time(h, m)
        except ValueError:
            return jsonify({'error': 'Invalid daily_start_time format'}), 400

    if data.get('daily_end_time'):
        try:
            h, m = map(int, data['daily_end_time'].split(':'))
            from datetime import time
            daily_end = time(h, m)
        except ValueError:
            return jsonify({'error': 'Invalid daily_end_time format'}), 400

    # Serialize arrays to JSON
    import json

    def to_json_or_none(value):
        """Convert to JSON string or None."""
        return json.dumps(value) if value else None

    # Product filters
    collection_ids = to_json_or_none(data.get('collection_ids'))
    vendor_filter = to_json_or_none(data.get('vendor_filter'))
    product_type_filter = to_json_or_none(data.get('product_type_filter'))
    product_tags_filter = to_json_or_none(data.get('product_tags_filter'))
    category_ids = to_json_or_none(data.get('category_ids'))  # Legacy

    # Member restrictions
    tier_restriction = to_json_or_none(data.get('tier_restriction'))

    promotion = Promotion(
        name=data['name'],
        description=data.get('description'),
        code=data.get('code'),
        promo_type=data.get('promo_type', 'trade_in_bonus'),
        bonus_percent=data.get('bonus_percent', 0),
        bonus_flat=data.get('bonus_flat', 0),
        multiplier=data.get('multiplier', 1),
        starts_at=starts_at,
        ends_at=ends_at,
        daily_start_time=daily_start,
        daily_end_time=daily_end,
        active_days=data.get('active_days'),
        channel=data.get('channel', 'all'),
        # Product filters
        collection_ids=collection_ids,
        vendor_filter=vendor_filter,
        product_type_filter=product_type_filter,
        product_tags_filter=product_tags_filter,
        category_ids=category_ids,  # Legacy
        # Member restrictions
        tier_restriction=tier_restriction,
        min_items=data.get('min_items', 0),
        min_value=data.get('min_value', 0),
        stackable=data.get('stackable', True),
        priority=data.get('priority', 0),
        max_uses=data.get('max_uses'),
        max_uses_per_member=data.get('max_uses_per_member'),
        active=data.get('active', True),
        created_by=data.get('created_by', 'admin'),
    )

    db.session.add(promotion)
    db.session.commit()

    return jsonify(promotion.to_dict()), 201


@promotions_bp.route('/promotions/<int:promo_id>', methods=['GET'])
@require_shop_auth
def get_promotion(promo_id: int):
    """Get a single promotion."""
    promotion = Promotion.query.get_or_404(promo_id)
    return jsonify(promotion.to_dict()), 200


@promotions_bp.route('/promotions/<int:promo_id>', methods=['PUT'])
@require_shop_auth
def update_promotion(promo_id: int):
    """Update a promotion."""
    promotion = Promotion.query.get_or_404(promo_id)
    data = request.get_json()

    # Update fields
    if 'name' in data:
        promotion.name = data['name']
    if 'description' in data:
        promotion.description = data['description']
    if 'code' in data:
        promotion.code = data['code']
    if 'promo_type' in data:
        promotion.promo_type = data['promo_type']
    if 'bonus_percent' in data:
        promotion.bonus_percent = data['bonus_percent']
    if 'bonus_flat' in data:
        promotion.bonus_flat = data['bonus_flat']
    if 'multiplier' in data:
        promotion.multiplier = data['multiplier']

    if 'starts_at' in data:
        promotion.starts_at = datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00'))
    if 'ends_at' in data:
        promotion.ends_at = datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00'))

    if 'daily_start_time' in data:
        if data['daily_start_time']:
            h, m = map(int, data['daily_start_time'].split(':'))
            from datetime import time
            promotion.daily_start_time = time(h, m)
        else:
            promotion.daily_start_time = None

    if 'daily_end_time' in data:
        if data['daily_end_time']:
            h, m = map(int, data['daily_end_time'].split(':'))
            from datetime import time
            promotion.daily_end_time = time(h, m)
        else:
            promotion.daily_end_time = None

    if 'active_days' in data:
        promotion.active_days = data['active_days']
    if 'channel' in data:
        promotion.channel = data['channel']

    import json

    def to_json_or_none(value):
        """Convert to JSON string or None."""
        return json.dumps(value) if value else None

    # Product filters
    if 'collection_ids' in data:
        promotion.collection_ids = to_json_or_none(data['collection_ids'])
    if 'vendor_filter' in data:
        promotion.vendor_filter = to_json_or_none(data['vendor_filter'])
    if 'product_type_filter' in data:
        promotion.product_type_filter = to_json_or_none(data['product_type_filter'])
    if 'product_tags_filter' in data:
        promotion.product_tags_filter = to_json_or_none(data['product_tags_filter'])
    if 'category_ids' in data:
        promotion.category_ids = to_json_or_none(data['category_ids'])

    # Member restrictions
    if 'tier_restriction' in data:
        promotion.tier_restriction = to_json_or_none(data['tier_restriction'])

    if 'min_items' in data:
        promotion.min_items = data['min_items']
    if 'min_value' in data:
        promotion.min_value = data['min_value']
    if 'stackable' in data:
        promotion.stackable = data['stackable']
    if 'priority' in data:
        promotion.priority = data['priority']
    if 'max_uses' in data:
        promotion.max_uses = data['max_uses']
    if 'max_uses_per_member' in data:
        promotion.max_uses_per_member = data['max_uses_per_member']
    if 'active' in data:
        promotion.active = data['active']

    db.session.commit()

    return jsonify(promotion.to_dict()), 200


@promotions_bp.route('/promotions/<int:promo_id>', methods=['DELETE'])
@require_shop_auth
def delete_promotion(promo_id: int):
    """Delete a promotion."""
    promotion = Promotion.query.get_or_404(promo_id)

    # Check if it has been used
    if promotion.current_uses > 0:
        # Soft delete instead
        promotion.active = False
        db.session.commit()
        return jsonify({'deactivated': True, 'reason': 'Promotion has been used'}), 200

    db.session.delete(promotion)
    db.session.commit()

    return jsonify({'deleted': True}), 200


# ==================== Quick Promotion Templates ====================

@promotions_bp.route('/promotions/templates', methods=['GET'])
@require_shop_auth
def get_promotion_templates():
    """Get common promotion templates for quick creation."""
    now = datetime.utcnow()

    templates = [
        {
            'name': 'Holiday Weekend Bonus',
            'description': '+10% store credit on all purchases this weekend',
            'promo_type': 'purchase_cashback',
            'bonus_percent': 10,
            'channel': 'all',
            'suggested_duration': '3 days',
        },
        {
            'name': 'Sports Card Night',
            'description': '+10% trade-in value on sports cards 6-9pm',
            'promo_type': 'trade_in_bonus',
            'bonus_percent': 10,
            'channel': 'in_store',
            'daily_start_time': '18:00',
            'daily_end_time': '21:00',
            'category_hint': 'sports',
            'suggested_duration': '1 day',
        },
        {
            'name': 'Pokemon Day',
            'description': '+15% trade-in value on all Pokemon cards',
            'promo_type': 'trade_in_bonus',
            'bonus_percent': 15,
            'channel': 'all',
            'category_hint': 'pokemon',
            'suggested_duration': '1 day',
        },
        {
            'name': 'New Member Bonus',
            'description': '+5% extra cashback for first week',
            'promo_type': 'purchase_cashback',
            'bonus_percent': 5,
            'channel': 'all',
            'suggested_duration': '7 days',
        },
        {
            'name': 'Flash Double Points',
            'description': '2x store credit on all trade-ins (2 hours only)',
            'promo_type': 'multiplier',
            'multiplier': 2.0,
            'channel': 'all',
            'suggested_duration': '2 hours',
        },
        {
            'name': 'Bulk Trade Bonus',
            'description': '+5% extra on trade-ins of 25+ items',
            'promo_type': 'trade_in_bonus',
            'bonus_percent': 5,
            'min_items': 25,
            'channel': 'all',
            'suggested_duration': '7 days',
        },
    ]

    return jsonify({'templates': templates}), 200


# ==================== Store Credit Operations ====================

@promotions_bp.route('/credit/balance/<int:member_id>', methods=['GET'])
@require_shop_auth
def get_member_balance(member_id: int):
    """Get member's store credit balance and history."""
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    result = store_credit_service.get_member_credit_history(
        member_id=member_id,
        limit=limit,
        offset=offset,
    )

    return jsonify(result), 200


@promotions_bp.route('/credit/add', methods=['POST'])
@require_shop_auth
def add_credit():
    """
    Manually add store credit to a member.

    Request body:
        member_id: Member ID (required)
        amount: Amount to add (required)
        description: Reason for credit (required)
        event_type: Type of credit event (default: adjustment)
    """
    data = request.get_json()

    if not data.get('member_id'):
        return jsonify({'error': 'member_id is required'}), 400
    if 'amount' not in data:
        return jsonify({'error': 'amount is required'}), 400
    if not data.get('description'):
        return jsonify({'error': 'description is required'}), 400

    try:
        entry = store_credit_service.add_credit(
            member_id=data['member_id'],
            amount=Decimal(str(data['amount'])),
            event_type=data.get('event_type', CreditEventType.MANUAL_ADJUSTMENT.value),
            description=data['description'],
            source_type='manual',
            created_by=data.get('created_by', 'admin'),
        )

        balance = store_credit_service.get_member_balance(data['member_id'])

        return jsonify({
            'entry': entry.to_dict(),
            'new_balance': float(balance.total_balance),
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@promotions_bp.route('/credit/deduct', methods=['POST'])
@require_shop_auth
def deduct_credit():
    """
    Deduct store credit from a member (redemption).

    Request body:
        member_id: Member ID (required)
        amount: Amount to deduct (required)
        description: Reason for deduction (required)
    """
    data = request.get_json()

    if not data.get('member_id'):
        return jsonify({'error': 'member_id is required'}), 400
    if 'amount' not in data:
        return jsonify({'error': 'amount is required'}), 400
    if not data.get('description'):
        return jsonify({'error': 'description is required'}), 400

    try:
        entry = store_credit_service.deduct_credit(
            member_id=data['member_id'],
            amount=Decimal(str(data['amount'])),
            description=data['description'],
            created_by=data.get('created_by', 'admin'),
        )

        balance = store_credit_service.get_member_balance(data['member_id'])

        return jsonify({
            'entry': entry.to_dict(),
            'new_balance': float(balance.total_balance),
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


# ==================== Bulk Operations ====================

@promotions_bp.route('/credit/bulk', methods=['POST'])
@require_shop_auth
def create_bulk_operation():
    """
    Create a bulk credit operation.

    Request body:
        name: Operation name (required)
        description: Description
        amount_per_member: Amount per member (required)
        tier_filter: Comma-separated tier names (optional)
        created_by: Admin email (required)
    """
    data = request.get_json()

    if not data.get('name'):
        return jsonify({'error': 'name is required'}), 400
    if 'amount_per_member' not in data:
        return jsonify({'error': 'amount_per_member is required'}), 400
    if not data.get('created_by'):
        return jsonify({'error': 'created_by is required'}), 400

    operation = BulkCreditOperation(
        name=data['name'],
        description=data.get('description'),
        amount_per_member=data['amount_per_member'],
        tier_filter=data.get('tier_filter'),
        status_filter=data.get('status_filter', 'active'),
        created_by=data['created_by'],
    )

    db.session.add(operation)
    db.session.commit()

    return jsonify(operation.to_dict()), 201


@promotions_bp.route('/credit/bulk/<int:op_id>/preview', methods=['GET'])
@require_shop_auth
def preview_bulk_operation(op_id: int):
    """Preview a bulk operation before execution."""
    try:
        result = store_credit_service.execute_bulk_credit(op_id, dry_run=True)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@promotions_bp.route('/credit/bulk/<int:op_id>/execute', methods=['POST'])
@require_shop_auth
def execute_bulk_operation(op_id: int):
    """Execute a bulk credit operation."""
    try:
        result = store_credit_service.execute_bulk_credit(op_id, dry_run=False)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.exception(f"Bulk operation failed: {e}")
        return jsonify({'error': str(e)}), 500


@promotions_bp.route('/credit/bulk', methods=['GET'])
@require_shop_auth
def list_bulk_operations():
    """List bulk credit operations."""
    operations = BulkCreditOperation.query.order_by(
        BulkCreditOperation.created_at.desc()
    ).limit(50).all()

    return jsonify({
        'operations': [op.to_dict() for op in operations],
        'total': len(operations),
    }), 200


# ==================== Tier Configuration ====================

@promotions_bp.route('/tiers', methods=['GET'])
@require_shop_auth
def list_tiers():
    """Get all tier configurations."""
    try:
        # Ensure defaults exist
        seed_tier_configurations()

        tiers = TierConfiguration.query.filter_by(active=True).order_by(
            TierConfiguration.display_order.asc()
        ).all()

        return jsonify({
            'tiers': [t.to_dict() for t in tiers],
        }), 200
    except Exception as e:
        # Table may not exist yet - return empty with migration hint
        print(f"[Promotions] Tiers endpoint error: {e}")
        return jsonify({
            'tiers': [],
            'error': 'Tier configurations not available - database may need migration',
            'error_detail': str(e),
            'hint': 'POST to /api/promotions/init-db to initialize tables'
        }), 200


@promotions_bp.route('/tiers/<int:tier_id>', methods=['PUT'])
@require_shop_auth
def update_tier(tier_id: int):
    """
    Update a tier configuration.

    Request body:
        monthly_price: Monthly subscription price
        yearly_price: Yearly subscription price (null to disable yearly)
        trade_in_bonus_pct: Trade-in bonus percentage
        purchase_cashback_pct: Purchase cashback percentage
        store_discount_pct: Store discount percentage
        color: Display color
        icon: Icon name
        badge_text: Badge display text
        features: Array of feature strings
    """
    tier = TierConfiguration.query.get_or_404(tier_id)
    data = request.get_json()

    # Pricing
    if 'monthly_price' in data:
        tier.monthly_price = data['monthly_price']
    if 'yearly_price' in data:
        # Allow null to disable yearly pricing
        tier.yearly_price = data['yearly_price'] if data['yearly_price'] else None

    # Benefits
    if 'trade_in_bonus_pct' in data:
        tier.trade_in_bonus_pct = data['trade_in_bonus_pct']
    if 'purchase_cashback_pct' in data:
        tier.purchase_cashback_pct = data['purchase_cashback_pct']
    if 'store_discount_pct' in data:
        tier.store_discount_pct = data['store_discount_pct']

    # Display
    if 'color' in data:
        tier.color = data['color']
    if 'icon' in data:
        tier.icon = data['icon']
    if 'badge_text' in data:
        tier.badge_text = data['badge_text']
    if 'features' in data:
        import json
        tier.features = json.dumps(data['features'])
    if 'active' in data:
        tier.active = data['active']

    db.session.commit()

    return jsonify(tier.to_dict()), 200


# ==================== Dashboard Stats ====================

@promotions_bp.route('/dashboard/stats', methods=['GET'])
@promotions_bp.route('/stats', methods=['GET'])
@require_shop_auth
def get_promotion_stats():
    """Get promotion and store credit statistics."""
    try:
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)

        # Active promotions
        try:
            active_promos = Promotion.query.filter(
                and_(
                    Promotion.active == True,
                    Promotion.starts_at <= now,
                    Promotion.ends_at >= now,
                )
            ).all()
            active_promos = [p for p in active_promos if p.is_active_now()]
        except Exception as e:
            current_app.logger.warning(f"Error fetching active promos: {e}")
            active_promos = []

        # Upcoming promotions (next 7 days)
        try:
            seven_days = now + timedelta(days=7)
            upcoming_promos = Promotion.query.filter(
                and_(
                    Promotion.active == True,
                    Promotion.starts_at > now,
                    Promotion.starts_at <= seven_days,
                )
            ).count()
        except Exception as e:
            current_app.logger.warning(f"Error fetching upcoming promos: {e}")
            upcoming_promos = 0

        # Credit issued in last 30 days
        try:
            credit_stats = db.session.query(
                func.sum(StoreCreditLedger.amount),
                func.count(StoreCreditLedger.id),
            ).filter(
                and_(
                    StoreCreditLedger.created_at >= thirty_days_ago,
                    StoreCreditLedger.amount > 0,
                )
            ).first()
        except Exception as e:
            current_app.logger.warning(f"Error fetching credit stats: {e}")
            credit_stats = (0, 0)

        # Credit by type in last 30 days
        try:
            credit_by_type = db.session.query(
                StoreCreditLedger.event_type,
                func.sum(StoreCreditLedger.amount),
                func.count(StoreCreditLedger.id),
            ).filter(
                and_(
                    StoreCreditLedger.created_at >= thirty_days_ago,
                    StoreCreditLedger.amount > 0,
                )
            ).group_by(StoreCreditLedger.event_type).all()
        except Exception as e:
            current_app.logger.warning(f"Error fetching credit by type: {e}")
            credit_by_type = []

        # Top members by credit earned (simplified - no join)
        try:
            top_earners = MemberCreditBalance.query.order_by(
                MemberCreditBalance.total_earned.desc()
            ).limit(5).all()
            top_earners_data = [
                {
                    'member_id': te.member_id,
                    'total_earned': float(te.total_earned or 0),
                }
                for te in top_earners
            ]
        except Exception as e:
            current_app.logger.warning(f"Error fetching top earners: {e}")
            top_earners_data = []

        return jsonify({
            'active_promotions': len(active_promos),
            'active_promo_list': [{'id': p.id, 'name': p.name, 'ends_at': p.ends_at.isoformat()} for p in active_promos],
            'upcoming_promotions': upcoming_promos,
            'credit_issued_30d': {
                'total': float(credit_stats[0] or 0),
                'transactions': credit_stats[1] or 0,
            },
            'credit_by_type': {
                row[0]: {'amount': float(row[1] or 0), 'count': row[2]}
                for row in credit_by_type
            },
            'top_earners': top_earners_data,
        }), 200
    except Exception as e:
        current_app.logger.error(f"Stats endpoint error: {e}")
        return jsonify({
            'error': 'Failed to fetch stats',
            'message': str(e),
        }), 500


# ==================== Product Filter Options ====================

@promotions_bp.route('/filter-options', methods=['GET'])
@require_shop_auth
def get_filter_options():
    """
    Get all product filter options from Shopify for promotion configuration.

    Returns:
        - collections: List of Shopify collections
        - vendors: List of unique product vendors
        - productTypes: List of unique product types
        - productTags: List of unique product tags
    """
    tenant_id = g.tenant_id

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(int(tenant_id))

        # Fetch all filter options
        options = client.get_promotion_filter_options()

        return jsonify({
            'collections': options['collections'],
            'vendors': options['vendors'],
            'productTypes': options['productTypes'],
            'productTags': options['productTags']
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.exception(f"Failed to fetch filter options: {e}")
        return jsonify({'error': f'Failed to fetch filter options: {e}'}), 500


@promotions_bp.route('/filter-options/collections', methods=['GET'])
@require_shop_auth
def get_collections():
    """Get just collections for the filter."""
    tenant_id = g.tenant_id

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(int(tenant_id))
        collections = client.get_collections()
        return jsonify({'collections': collections}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@promotions_bp.route('/filter-options/vendors', methods=['GET'])
@require_shop_auth
def get_vendors():
    """Get just vendors for the filter."""
    tenant_id = g.tenant_id

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(int(tenant_id))
        vendors = client.get_vendors()
        return jsonify({'vendors': vendors}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@promotions_bp.route('/filter-options/product-types', methods=['GET'])
@require_shop_auth
def get_product_types():
    """Get just product types for the filter."""
    tenant_id = g.tenant_id

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(int(tenant_id))
        product_types = client.get_product_types()
        return jsonify({'productTypes': product_types}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
