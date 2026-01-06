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
