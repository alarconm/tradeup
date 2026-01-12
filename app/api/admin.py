"""
Admin API routes for TradeUp platform.
Handles admin dashboard, Shopify lookups, and store credit events.

Authentication:
- Uses Shopify session tokens (JWT) for embedded app requests
- Falls back to shop query param or X-Tenant-ID header for dev/backwards compat
"""
from flask import Blueprint, request, jsonify, g
from functools import wraps

from ..extensions import db
from ..models.member import Member, MembershipTier
from ..services.shopify_client import ShopifyClient
from ..services.store_credit_events import StoreCreditEventService
from ..middleware.shopify_auth import require_shopify_auth

admin_bp = Blueprint('admin', __name__)


def require_tenant(f):
    """
    Legacy decorator for tenant context.
    DEPRECATED: Use @require_shopify_auth instead.

    Kept for backwards compatibility - will check both new and old methods.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First try the new auth method (shop domain based)
        from ..middleware.shopify_auth import get_shop_from_request
        from ..models import Tenant

        shop = get_shop_from_request()
        if shop:
            tenant = Tenant.query.filter_by(shopify_domain=shop).first()
            if tenant:
                g.tenant_id = tenant.id
                g.tenant = tenant
                g.shop = shop
                return f(*args, **kwargs)

        # Fallback to X-Tenant-ID header
        tenant_id = request.headers.get('X-Tenant-ID')
        if tenant_id:
            try:
                g.tenant_id = int(tenant_id)
                return f(*args, **kwargs)
            except (ValueError, TypeError):
                pass

        return jsonify({'error': 'Tenant ID required'}), 400

    return decorated_function


# ================== Dashboard ==================

@admin_bp.route('/dashboard', methods=['GET'])
@require_tenant
def get_dashboard_stats():
    """Get admin dashboard statistics."""
    from sqlalchemy import func
    from datetime import datetime, timedelta

    tenant_id = g.tenant_id
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Total members
    total_members = Member.query.filter_by(tenant_id=tenant_id).count()

    # Active members
    active_members = Member.query.filter_by(
        tenant_id=tenant_id,
        status='active'
    ).count()

    # Members this month
    members_this_month = Member.query.filter(
        Member.tenant_id == tenant_id,
        Member.created_at >= month_start
    ).count()

    # Members by tier
    tier_counts = db.session.query(
        MembershipTier.name,
        func.count(Member.id)
    ).outerjoin(Member, Member.tier_id == MembershipTier.id).filter(
        MembershipTier.tenant_id == tenant_id
    ).group_by(MembershipTier.name).all()

    members_by_tier = {name: count for name, count in tier_counts}

    # Recent members
    recent_members = Member.query.filter_by(
        tenant_id=tenant_id
    ).order_by(Member.created_at.desc()).limit(5).all()

    # Recent activity (simplified for now)
    recent_activity = []
    for member in recent_members:
        recent_activity.append({
            'id': str(member.id),
            'type': 'member_joined',
            'description': f'{member.name or member.email} joined',
            'timestamp': member.created_at.isoformat(),
            'meta': {'member_id': member.id}
        })

    return jsonify({
        'total_members': total_members,
        'active_members': active_members,
        'members_this_month': members_this_month,
        'total_events_this_month': 0,  # TODO: Track events
        'total_credited_this_month': 0,  # TODO: Track credits
        'members_by_tier': members_by_tier,
        'recent_activity': recent_activity
    })


# ================== Shopify Lookups ==================

@admin_bp.route('/shopify/customer', methods=['GET'])
@require_tenant
def lookup_shopify_customer():
    """Lookup a Shopify customer by email."""
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400

    try:
        client = ShopifyClient(g.tenant_id)
        customer = client.get_customer_by_email(email)

        if not customer:
            return jsonify({'customer': None})

        # Get store credit balance
        store_credit = client.get_store_credit_balance(customer['id'])

        return jsonify({
            'customer': {
                'id': customer['id'],
                'email': customer.get('email'),
                'firstName': customer.get('firstName', ''),
                'lastName': customer.get('lastName', ''),
                'phone': customer.get('phone'),
                'tags': customer.get('tags', []),
                'ordersCount': customer.get('numberOfOrders', 0),
                'totalSpent': float(customer.get('amountSpent', {}).get('amount', 0)),
                'storeCreditBalance': float(store_credit.get('balance', {}).get('amount', 0)) if store_credit else 0,
                'currency': customer.get('amountSpent', {}).get('currencyCode', 'USD'),
                'createdAt': customer.get('createdAt')
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/shopify/customers/search', methods=['GET'])
@require_tenant
def search_shopify_customers():
    """
    Search Shopify customers by name, email, phone, or ORB#.

    Query params:
        q: Search query (required, min 2 chars)
        limit: Max results (default 10, max 25)

    Searches intelligently:
        - If query contains @, searches by email
        - If query is mostly digits, searches by phone
        - If query starts with ORB or #ORB, searches by tag
        - Otherwise searches by name
    """
    query = request.args.get('q', '').strip()
    limit = min(request.args.get('limit', 10, type=int), 25)

    if len(query) < 2:
        return jsonify({'customers': [], 'query': query})

    try:
        client = ShopifyClient(g.tenant_id)
        customers = client.search_customers(query, limit=limit)

        # Format customers for frontend
        results = []
        for c in customers:
            results.append({
                'id': c.get('id'),
                'gid': c.get('gid'),
                'email': c.get('email'),
                'firstName': c.get('firstName', ''),
                'lastName': c.get('lastName', ''),
                'displayName': c.get('displayName') or c.get('name', ''),
                'phone': c.get('phone'),
                'tags': c.get('tags', []),
                'orbNumber': c.get('orb_number'),
                'ordersCount': c.get('numberOfOrders', 0),
                'totalSpent': c.get('amountSpent', 0),
                'storeCreditBalance': c.get('storeCredit', 0),
                'createdAt': c.get('createdAt')
            })

        return jsonify({
            'customers': results,
            'query': query,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/shopify/collections', methods=['GET'])
@require_tenant
def get_collections():
    """Get all Shopify collections."""
    try:
        client = ShopifyClient(g.tenant_id)
        collections = client.get_collections()

        return jsonify({
            'collections': [
                {
                    'id': col['id'],
                    'title': col['title'],
                    'handle': col.get('handle', ''),
                    'productsCount': col.get('productsCount', 0)
                }
                for col in collections
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/shopify/product-tags', methods=['GET'])
@require_tenant
def get_product_tags():
    """Get all unique product tags from Shopify."""
    try:
        client = ShopifyClient(g.tenant_id)
        tags = client.get_product_tags()

        return jsonify({'tags': sorted(tags)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/shopify/customer-tags', methods=['GET'])
@require_tenant
def get_customer_tags():
    """Get all unique customer tags from Shopify."""
    try:
        client = ShopifyClient(g.tenant_id)
        tags = client.get_customer_tags()

        return jsonify({'tags': sorted(tags)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ================== Store Credit Events ==================

@admin_bp.route('/events', methods=['GET'])
@require_tenant
def list_events():
    """List store credit events."""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 15, type=int)
    status = request.args.get('status')

    try:
        service = StoreCreditEventService(g.tenant_id)
        result = service.list_events(page=page, limit=limit, status=status)

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/events/preview', methods=['POST'])
@require_tenant
def preview_event():
    """Preview store credit event impact."""
    data = request.get_json()

    credit_amount = data.get('credit_amount')
    filters = data.get('filters', {})

    if not credit_amount or credit_amount <= 0:
        return jsonify({'error': 'Valid credit amount required'}), 400

    try:
        service = StoreCreditEventService(g.tenant_id)
        preview = service.preview_event(
            credit_amount=credit_amount,
            filters=filters
        )

        return jsonify(preview)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/events/run', methods=['POST'])
@require_tenant
def run_event():
    """Run a store credit event."""
    data = request.get_json()

    name = data.get('name')
    description = data.get('description', '')
    credit_amount = data.get('credit_amount')
    filters = data.get('filters', {})

    if not name:
        return jsonify({'error': 'Event name required'}), 400
    if not credit_amount or credit_amount <= 0:
        return jsonify({'error': 'Valid credit amount required'}), 400

    try:
        service = StoreCreditEventService(g.tenant_id)
        result = service.run_event(
            name=name,
            description=description,
            credit_amount=credit_amount,
            filters=filters
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/events/<event_id>', methods=['GET'])
@require_tenant
def get_event(event_id):
    """Get details of a specific event."""
    try:
        service = StoreCreditEventService(g.tenant_id)
        event = service.get_event(event_id)

        if not event:
            return jsonify({'error': 'Event not found'}), 404

        return jsonify({'event': event})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ================== Schema Fix (Emergency) ==================

@admin_bp.route('/fix-schema', methods=['POST'])
def fix_schema():
    """
    Emergency endpoint to add missing database columns.
    This runs raw SQL to add columns that migrations missed.

    Call with: POST /api/admin/fix-schema?key=tradeup-schema-fix-2026
    """
    # Simple security key check
    key = request.args.get('key')
    if key != 'tradeup-schema-fix-2026':
        return jsonify({'error': 'Invalid key'}), 403

    from sqlalchemy import text

    columns_to_add = [
        # Members - Shopify subscription columns
        ("members", "shopify_subscription_contract_id", "VARCHAR(100)"),
        ("members", "subscription_status", "VARCHAR(20) DEFAULT 'none'"),
        ("members", "tier_assigned_by", "VARCHAR(100)"),
        ("members", "tier_assigned_at", "TIMESTAMP"),
        ("members", "tier_expires_at", "TIMESTAMP"),
        ("members", "shopify_customer_gid", "VARCHAR(100)"),
        ("members", "partner_customer_id", "VARCHAR(100)"),
        # Members - Referral program columns
        ("members", "referral_code", "VARCHAR(20)"),
        ("members", "referred_by_id", "INTEGER"),
        ("members", "referral_count", "INTEGER DEFAULT 0"),
        ("members", "referral_earnings", "NUMERIC(12,2) DEFAULT 0"),
        # Membership tiers
        ("membership_tiers", "shopify_selling_plan_id", "VARCHAR(100)"),
        ("membership_tiers", "yearly_price", "NUMERIC(10,2)"),
        ("membership_tiers", "purchase_cashback_pct", "NUMERIC(5,2) DEFAULT 0"),
        ("membership_tiers", "monthly_credit_amount", "NUMERIC(10,2) DEFAULT 0"),
        ("membership_tiers", "credit_expiration_days", "INTEGER"),
        # Trade-in batches - missing columns from model
        ("trade_in_batches", "category", "VARCHAR(50) DEFAULT 'other'"),
        ("trade_in_batches", "completed_at", "TIMESTAMP"),
        ("trade_in_batches", "completed_by", "VARCHAR(100)"),
        ("trade_in_batches", "bonus_amount", "NUMERIC(10,2) DEFAULT 0"),
        # Trade-in batches - guest/non-member trade-in support
        ("trade_in_batches", "guest_name", "VARCHAR(200)"),
        ("trade_in_batches", "guest_email", "VARCHAR(200)"),
        ("trade_in_batches", "guest_phone", "VARCHAR(50)"),
        # Trade-in batches - tenant isolation (CRITICAL SECURITY)
        ("trade_in_batches", "tenant_id", "INTEGER REFERENCES tenants(id)"),
        # Promotions - tenant isolation (CRITICAL SECURITY)
        ("promotions", "tenant_id", "INTEGER REFERENCES tenants(id)"),
        # Bulk credit operations - tenant isolation (CRITICAL SECURITY)
        ("bulk_credit_operations", "tenant_id", "INTEGER REFERENCES tenants(id)"),
        # Tier configurations - promotion system columns
        ("tier_configurations", "yearly_price", "NUMERIC(6,2)"),
        ("tier_configurations", "trade_in_bonus_pct", "NUMERIC(5,2) DEFAULT 0"),
        ("tier_configurations", "purchase_cashback_pct", "NUMERIC(5,2) DEFAULT 0"),
        ("tier_configurations", "store_discount_pct", "NUMERIC(5,2) DEFAULT 0"),
        ("tier_configurations", "color", "VARCHAR(20) DEFAULT 'slate'"),
        ("tier_configurations", "icon", "VARCHAR(50) DEFAULT 'star'"),
        ("tier_configurations", "badge_text", "VARCHAR(50)"),
        ("tier_configurations", "features", "TEXT"),
        # Member credit balances - missing columns
        ("member_credit_balances", "total_expired", "NUMERIC(10,2) DEFAULT 0"),
        # Members - Points loyalty system columns
        ("members", "points_balance", "INTEGER DEFAULT 0"),
        ("members", "lifetime_points_earned", "INTEGER DEFAULT 0"),
        ("members", "lifetime_points_spent", "INTEGER DEFAULT 0"),
    ]

    results = []

    try:
        for table, column, col_type in columns_to_add:
            # Check if column exists
            check_sql = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = :table_name AND column_name = :column_name
                )
            """)
            result = db.session.execute(check_sql, {'table_name': table, 'column_name': column})
            exists = result.scalar()

            if not exists:
                # Add the column
                alter_sql = text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}')
                db.session.execute(alter_sql)
                results.append({'table': table, 'column': column, 'action': 'added'})
            else:
                results.append({'table': table, 'column': column, 'action': 'exists'})

        # Special case: Make trade_in_batches.member_id nullable for non-member trade-ins
        try:
            alter_nullable_sql = text('ALTER TABLE trade_in_batches ALTER COLUMN member_id DROP NOT NULL')
            db.session.execute(alter_nullable_sql)
            results.append({'table': 'trade_in_batches', 'column': 'member_id', 'action': 'made_nullable'})
        except Exception:
            # Column might already be nullable, that's fine
            results.append({'table': 'trade_in_batches', 'column': 'member_id', 'action': 'already_nullable_or_error'})

        # Backfill tenant_id for existing trade-in batches (from their member)
        try:
            backfill_sql = text('''
                UPDATE trade_in_batches
                SET tenant_id = m.tenant_id
                FROM members m
                WHERE trade_in_batches.member_id = m.id
                AND trade_in_batches.tenant_id IS NULL
            ''')
            result = db.session.execute(backfill_sql)
            results.append({'table': 'trade_in_batches', 'column': 'tenant_id', 'action': f'backfilled_{result.rowcount}_rows'})
        except Exception as e:
            results.append({'table': 'trade_in_batches', 'column': 'tenant_id', 'action': f'backfill_error: {str(e)}'})

        # Add index on tenant_id for trade_in_batches
        try:
            index_sql = text('CREATE INDEX IF NOT EXISTS ix_trade_in_batches_tenant_id ON trade_in_batches (tenant_id)')
            db.session.execute(index_sql)
            results.append({'table': 'trade_in_batches', 'index': 'ix_trade_in_batches_tenant_id', 'action': 'created'})
        except Exception:
            results.append({'table': 'trade_in_batches', 'index': 'ix_trade_in_batches_tenant_id', 'action': 'exists_or_error'})

        # Add index on tenant_id for promotions
        try:
            index_sql = text('CREATE INDEX IF NOT EXISTS ix_promotions_tenant_id ON promotions (tenant_id)')
            db.session.execute(index_sql)
            results.append({'table': 'promotions', 'index': 'ix_promotions_tenant_id', 'action': 'created'})
        except Exception:
            results.append({'table': 'promotions', 'index': 'ix_promotions_tenant_id', 'action': 'exists_or_error'})

        # Add index on tenant_id for bulk_credit_operations
        try:
            index_sql = text('CREATE INDEX IF NOT EXISTS ix_bulk_credit_operations_tenant_id ON bulk_credit_operations (tenant_id)')
            db.session.execute(index_sql)
            results.append({'table': 'bulk_credit_operations', 'index': 'ix_bulk_credit_operations_tenant_id', 'action': 'created'})
        except Exception:
            results.append({'table': 'bulk_credit_operations', 'index': 'ix_bulk_credit_operations_tenant_id', 'action': 'exists_or_error'})

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Schema fix completed',
            'results': results
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Shopify Metafields Sync ==================

@admin_bp.route('/fix-credits', methods=['POST'])
def fix_credits():
    """
    Fix member credits_issued totals by recalculating from ledger entries.

    This fixes the bug where member.total_bonus_earned wasn't being updated
    when credits were issued.

    Call with: POST /api/admin/fix-credits?key=tradeup-schema-fix-2026
    """
    from sqlalchemy import func
    from decimal import Decimal
    from ..models.promotions import StoreCreditLedger

    # Simple security key check
    key = request.args.get('key')
    if key != 'tradeup-schema-fix-2026':
        return jsonify({'error': 'Invalid key'}), 403

    try:
        # Get all members with their actual credit totals from ledger
        credit_totals = db.session.query(
            StoreCreditLedger.member_id,
            func.sum(StoreCreditLedger.amount).label('total_credits')
        ).filter(
            StoreCreditLedger.amount > 0  # Only positive amounts (credits issued)
        ).group_by(StoreCreditLedger.member_id).all()

        updated = []
        for member_id, total_credits in credit_totals:
            member = Member.query.get(member_id)
            if member:
                old_value = float(member.total_bonus_earned or 0)
                new_value = float(total_credits or 0)

                if old_value != new_value:
                    member.total_bonus_earned = Decimal(str(total_credits or 0))
                    updated.append({
                        'member_id': member_id,
                        'member_number': member.member_number,
                        'old_value': old_value,
                        'new_value': new_value
                    })

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Fixed {len(updated)} members',
            'updated': updated
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/create-points-tables', methods=['POST'])
def create_points_tables():
    """
    Create the points loyalty system tables.

    Call with: POST /api/admin/create-points-tables?key=tradeup-schema-fix-2026
    """
    key = request.args.get('key')
    if key != 'tradeup-schema-fix-2026':
        return jsonify({'error': 'Invalid key'}), 403

    try:
        # Import all the points models to register them with SQLAlchemy
        from ..models.loyalty_points import (
            PointsBalance,
            PointsLedger,
            EarningRule,
            Reward,
            RewardRedemption,
            PointsProgramConfig,
        )

        # Create all tables that don't exist yet
        db.create_all()

        return jsonify({
            'success': True,
            'message': 'Points system tables created successfully',
            'tables': [
                'points_balances',
                'points_ledger',
                'earning_rules',
                'rewards',
                'reward_redemptions',
                'points_program_configs'
            ]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/create-trade-ledger-table', methods=['POST'])
def create_trade_ledger_table():
    """
    Create the trade_in_ledger table for simplified trade-in tracking.

    Call with: POST /api/admin/create-trade-ledger-table?key=tradeup-schema-fix-2026
    """
    key = request.args.get('key')
    if key != 'tradeup-schema-fix-2026':
        return jsonify({'error': 'Invalid key'}), 403

    try:
        # Import the trade ledger model to register with SQLAlchemy
        from ..models.trade_ledger import TradeInLedger

        # Create all tables that don't exist yet
        db.create_all()

        return jsonify({
            'success': True,
            'message': 'Trade ledger table created successfully',
            'tables': ['trade_in_ledger']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/members/<int:member_id>/sync-metafields', methods=['POST'])
@require_tenant
def sync_member_metafields(member_id):
    """
    Sync a single member's data to Shopify customer metafields.

    This updates the customer's metafields in Shopify Admin with:
    - tradeup.member_number
    - tradeup.tier
    - tradeup.credit_balance
    - tradeup.trade_in_count
    - tradeup.total_bonus_earned
    - tradeup.status
    - tradeup.joined_date
    """
    member = Member.query.get(member_id)
    if not member or member.tenant_id != g.tenant_id:
        return jsonify({'error': 'Member not found'}), 404

    if not member.shopify_customer_id:
        return jsonify({'error': 'Member has no linked Shopify customer'}), 400

    try:
        from ..services.membership_service import MembershipService
        client = ShopifyClient(g.tenant_id)
        membership_svc = MembershipService(g.tenant_id, client)
        result = membership_svc.sync_member_metafields_to_shopify(member)

        return jsonify({
            'success': True,
            'member_id': member_id,
            'member_number': member.member_number,
            'shopify_customer_id': member.shopify_customer_id,
            'metafields_synced': result.get('metafields_set', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/members/sync-metafields', methods=['POST'])
@require_tenant
def sync_all_member_metafields():
    """
    Bulk sync all members' metafields to Shopify.

    Use this to backfill metafields for existing members.
    Only syncs members that have a linked Shopify customer.

    Request body (optional):
        limit: Max members to sync (default 100, max 500)
        offset: Skip first N members (for pagination)
    """
    data = request.get_json() or {}
    limit = min(data.get('limit', 100), 500)
    offset = data.get('offset', 0)

    # Get members with Shopify customer IDs
    members = Member.query.filter(
        Member.tenant_id == g.tenant_id,
        Member.shopify_customer_id.isnot(None),
        Member.status == 'active'
    ).order_by(Member.id).offset(offset).limit(limit).all()

    if not members:
        return jsonify({
            'success': True,
            'message': 'No members to sync',
            'synced': 0,
            'failed': 0
        })

    try:
        from ..services.membership_service import MembershipService
        client = ShopifyClient(g.tenant_id)
        membership_svc = MembershipService(g.tenant_id, client)

        results = {
            'synced': [],
            'failed': []
        }

        for member in members:
            try:
                membership_svc.sync_member_metafields_to_shopify(member)
                results['synced'].append({
                    'member_id': member.id,
                    'member_number': member.member_number
                })
            except Exception as e:
                results['failed'].append({
                    'member_id': member.id,
                    'member_number': member.member_number,
                    'error': str(e)
                })

        # Get total count for pagination info
        total_count = Member.query.filter(
            Member.tenant_id == g.tenant_id,
            Member.shopify_customer_id.isnot(None),
            Member.status == 'active'
        ).count()

        return jsonify({
            'success': True,
            'synced_count': len(results['synced']),
            'failed_count': len(results['failed']),
            'total_members': total_count,
            'offset': offset,
            'limit': limit,
            'has_more': offset + limit < total_count,
            'synced': results['synced'],
            'failed': results['failed']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/members/<int:member_id>/metafields', methods=['GET'])
@require_tenant
def get_member_metafields(member_id):
    """
    Get metafields for a member from Shopify.

    Returns the current metafield values stored on the Shopify customer.
    """
    member = Member.query.get(member_id)
    if not member or member.tenant_id != g.tenant_id:
        return jsonify({'error': 'Member not found'}), 404

    if not member.shopify_customer_id:
        return jsonify({'error': 'Member has no linked Shopify customer'}), 400

    try:
        client = ShopifyClient(g.tenant_id)
        metafields = client.get_customer_metafields(
            member.shopify_customer_id,
            namespace='tradeup'
        )

        return jsonify({
            'member_id': member_id,
            'member_number': member.member_number,
            'shopify_customer_id': member.shopify_customer_id,
            'metafields': metafields
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ================== Tier Discounts ==================

@admin_bp.route('/discounts/tier-codes', methods=['GET'])
@require_tenant
def get_tier_discount_codes():
    """
    Get all tier discount codes configuration.

    Returns the discount codes that should be created for each tier.
    """
    try:
        from ..services.tier_service import TierService
        tier_svc = TierService(g.tenant_id)
        codes = tier_svc.get_tier_discount_codes()

        return jsonify({
            'success': True,
            'codes': codes,
            'count': len(codes)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/discounts/sync-tiers', methods=['POST'])
@require_tenant
def sync_tier_discounts():
    """
    Sync all tier discount codes to Shopify.

    Creates discount codes like TRADEUP-GOLD, TRADEUP-SILVER, etc.
    for each tier that has a store discount configured.
    """
    try:
        from ..services.tier_service import TierService
        client = ShopifyClient(g.tenant_id)
        tier_svc = TierService(g.tenant_id)

        result = tier_svc.sync_tier_discounts_to_shopify(client)

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/discounts/shopify', methods=['GET'])
@require_tenant
def list_shopify_discounts():
    """
    List all automatic discounts from Shopify.
    """
    try:
        client = ShopifyClient(g.tenant_id)
        result = client.list_automatic_discounts()

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/discounts/create', methods=['POST'])
@require_tenant
def create_discount():
    """
    Create a new discount code in Shopify.

    Request body:
        tier_name: Name of tier (e.g., "Gold")
        percentage: Discount percentage (e.g., 20)
        customer_tag: Required customer tag (e.g., "tradeup-gold")
    """
    data = request.get_json()

    tier_name = data.get('tier_name')
    percentage = data.get('percentage')
    customer_tag = data.get('customer_tag')

    if not all([tier_name, percentage]):
        return jsonify({'error': 'tier_name and percentage required'}), 400

    try:
        client = ShopifyClient(g.tenant_id)
        result = client.create_tier_discount_code(
            tier_name=tier_name,
            percentage=float(percentage),
            customer_tag=customer_tag or f'tradeup-{tier_name.lower()}'
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/discounts/<discount_id>', methods=['DELETE'])
@require_tenant
def delete_discount(discount_id):
    """Delete a discount by ID."""
    try:
        client = ShopifyClient(g.tenant_id)
        result = client.delete_discount(discount_id)

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
