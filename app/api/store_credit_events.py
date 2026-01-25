"""
Store Credit Events API endpoints.
For running promotional store credit events like Trade Night.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from ..services.store_credit_events import StoreCreditEventsService

store_credit_events_bp = Blueprint('store_credit_events', __name__)


def get_service_for_tenant():
    """Get store credit events service for the authenticated tenant."""
    tenant = getattr(g, 'tenant', None)
    if not tenant or not tenant.shopify_access_token:
        return None
    return StoreCreditEventsService(tenant.shopify_domain, tenant.shopify_access_token)


def validate_filter_lists(data: dict) -> tuple:
    """
    Validate collection_ids and product_tags filter parameters.

    Args:
        data: Request JSON data

    Returns:
        Tuple of (collection_ids, product_tags) or raises ValueError

    Raises:
        ValueError: If parameters are invalid
    """
    collection_ids = data.get('collection_ids')
    if collection_ids is not None:
        if not isinstance(collection_ids, list):
            raise ValueError('collection_ids must be a list')
        if not all(isinstance(cid, str) for cid in collection_ids):
            raise ValueError('collection_ids must contain only strings')
        # Validate Shopify GID format for collections
        for cid in collection_ids:
            if cid and not cid.startswith('gid://shopify/Collection/'):
                raise ValueError(f'Invalid collection ID format: {cid}')

    product_tags = data.get('product_tags')
    if product_tags is not None:
        if not isinstance(product_tags, list):
            raise ValueError('product_tags must be a list')
        if not all(isinstance(tag, str) for tag in product_tags):
            raise ValueError('product_tags must contain only strings')
        # Limit tag length to prevent abuse
        for tag in product_tags:
            if tag and len(tag) > 255:
                raise ValueError('product_tags values must be 255 characters or less')

    return collection_ids, product_tags


@store_credit_events_bp.route('/preview', methods=['POST'])
@require_shopify_auth
def preview_event():
    """
    Preview a store credit event.

    Request body:
        start_datetime: ISO datetime string (required)
        end_datetime: ISO datetime string (required)
        sources: List of sources like ['pos', 'web'] (required)
        credit_percent: Percentage to credit (default 10)
        include_authorized: Include authorized orders (default true)
        collection_ids: List of collection GIDs to filter by (optional)
        product_tags: List of product tags to filter by (optional)
        audience: 'all_customers' (default) or 'members_only' (optional)

    Returns:
        Preview with order counts, customer totals, top customers
    """
    service = get_service_for_tenant()
    if not service:
        return jsonify({'error': 'Shopify not configured for this shop'}), 500

    data = request.json
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['start_datetime', 'end_datetime', 'sources']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    # Validate filter parameters
    try:
        collection_ids, product_tags = validate_filter_lists(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # Validate audience parameter
    audience = data.get('audience', 'all_customers')
    if audience not in ('all_customers', 'members_only'):
        return jsonify({'error': 'audience must be "all_customers" or "members_only"'}), 400

    try:
        result = service.preview_event(
            start_datetime=data['start_datetime'],
            end_datetime=data['end_datetime'],
            sources=data['sources'],
            credit_percent=data.get('credit_percent', 10),
            include_authorized=data.get('include_authorized', True),
            collection_ids=collection_ids,
            product_tags=product_tags,
            audience=audience
        )
        return jsonify(result)

    except ValueError as e:
        # Datetime validation errors
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@store_credit_events_bp.route('/run', methods=['POST'])
@require_shopify_auth
def run_event():
    """
    Run a store credit event (apply credits).

    Request body:
        start_datetime: ISO datetime string (required)
        end_datetime: ISO datetime string (required)
        sources: List of sources like ['pos', 'web'] (required)
        credit_percent: Percentage to credit (default 10)
        include_authorized: Include authorized orders (default true)
        job_id: Unique job ID for idempotency (recommended)
        expires_at: Credit expiration datetime (optional)
        collection_ids: List of collection GIDs to filter by (optional)
        product_tags: List of product tags to filter by (optional)
        audience: 'all_customers' (default) or 'members_only' (optional)

    Returns:
        Event results with success/failure counts
    """
    service = get_service_for_tenant()
    if not service:
        return jsonify({'error': 'Shopify not configured for this shop'}), 500

    data = request.json
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['start_datetime', 'end_datetime', 'sources']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    # Validate filter parameters
    try:
        collection_ids, product_tags = validate_filter_lists(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # Generate job_id if not provided
    job_id = data.get('job_id')
    if not job_id:
        job_id = f"event-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    # Validate audience parameter
    audience = data.get('audience', 'all_customers')
    if audience not in ('all_customers', 'members_only'):
        return jsonify({'error': 'audience must be "all_customers" or "members_only"'}), 400

    try:
        result = service.run_event(
            start_datetime=data['start_datetime'],
            end_datetime=data['end_datetime'],
            sources=data['sources'],
            credit_percent=data.get('credit_percent', 10),
            include_authorized=data.get('include_authorized', True),
            job_id=job_id,
            expires_at=data.get('expires_at'),
            batch_size=data.get('batch_size', 5),
            delay_ms=data.get('delay_ms', 1000),
            collection_ids=collection_ids,
            product_tags=product_tags,
            audience=audience
        )
        return jsonify(result)

    except ValueError as e:
        # Datetime validation errors
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@store_credit_events_bp.route('/sources', methods=['GET'])
@require_shopify_auth
def list_sources():
    """
    List available order sources for a date range.

    Query params:
        start_datetime: ISO datetime string (required)
        end_datetime: ISO datetime string (required)

    Returns:
        List of sources with order counts
    """
    import logging
    logger = logging.getLogger(__name__)

    service = get_service_for_tenant()
    if not service:
        return jsonify({'error': 'Shopify not configured for this shop'}), 500

    start = request.args.get('start_datetime')
    end = request.args.get('end_datetime')

    logger.info(f"[StoreCreditEvents] /sources called with start={start}, end={end}")

    if not start or not end:
        return jsonify({'error': 'start_datetime and end_datetime are required'}), 400

    try:
        # Fetch orders with no source filter to see all sources
        logger.info(f"[StoreCreditEvents] Fetching orders from {start} to {end}")
        orders = service.fetch_orders(start, end, [], include_authorized=True)
        logger.info(f"[StoreCreditEvents] Found {len(orders)} orders")

        # Count by source
        by_source = {}
        for order in orders:
            source = order.source_name or 'unknown'
            by_source[source] = by_source.get(source, 0) + 1

        return jsonify({
            'start_datetime': start,
            'end_datetime': end,
            'total_orders': len(orders),
            'sources': [
                {'name': name, 'count': count}
                for name, count in sorted(by_source.items(), key=lambda x: -x[1])
            ]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@store_credit_events_bp.route('/manual-run', methods=['POST'])
def manual_run_event():
    """
    Manual endpoint to run bulk store credit event.
    Protected by secret key instead of Shopify auth for emergency use.

    Query params:
        key: Secret key for authorization

    Body (JSON):
        shop_domain: Shopify shop domain
        start_datetime: ISO UTC datetime (e.g., 2026-01-25T01:00:00Z)
        end_datetime: ISO UTC datetime (e.g., 2026-01-25T04:00:00Z)
        credit_percent: Percentage to credit (default 10)
        sources: List of sources (default all)
        dry_run: If true, only preview (default true)
    """
    import logging
    from ..models import Tenant
    logger = logging.getLogger(__name__)

    # Simple key-based auth for emergency use
    key = request.args.get('key')
    if key != 'tradeup-manual-event-2026':
        return jsonify({'error': 'Invalid key'}), 403

    data = request.json or {}
    shop_domain = data.get('shop_domain')

    if not shop_domain:
        return jsonify({'error': 'shop_domain is required'}), 400

    # Get tenant credentials
    tenant = Tenant.query.filter_by(shopify_domain=shop_domain).first()
    if not tenant or not tenant.shopify_access_token:
        return jsonify({'error': f'No tenant found for {shop_domain}'}), 404

    from ..services.store_credit_events import StoreCreditEventsService
    service = StoreCreditEventsService(tenant.shopify_domain, tenant.shopify_access_token)

    start = data.get('start_datetime')
    end = data.get('end_datetime')
    credit_percent = data.get('credit_percent', 10)
    sources = data.get('sources', [])
    dry_run = data.get('dry_run', True)

    logger.info(f"[ManualRun] shop={shop_domain}, start={start}, end={end}, dry_run={dry_run}")

    if not start or not end:
        return jsonify({'error': 'start_datetime and end_datetime are required'}), 400

    try:
        if dry_run:
            result = service.preview_event(
                start_datetime=start,
                end_datetime=end,
                sources=sources,
                credit_percent=credit_percent,
                include_authorized=True,
                audience='all_customers'
            )
            result['dry_run'] = True
            return jsonify(result)
        else:
            result = service.run_event(
                start_datetime=start,
                end_datetime=end,
                sources=sources,
                credit_percent=credit_percent,
                include_authorized=True,
                job_id=f"manual-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
                audience='all_customers'
            )
            return jsonify(result)

    except Exception as e:
        logger.error(f"[ManualRun] Error: {str(e)}")
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@store_credit_events_bp.route('/debug-orders', methods=['GET'])
@require_shopify_auth
def debug_orders():
    """
    Debug endpoint to test order fetching.
    Shows exactly what Shopify returns for a date range.
    """
    import logging
    logger = logging.getLogger(__name__)

    service = get_service_for_tenant()
    if not service:
        return jsonify({'error': 'Shopify not configured for this shop'}), 500

    start = request.args.get('start_datetime')
    end = request.args.get('end_datetime')

    logger.info(f"[DEBUG] Received start={start}, end={end}")

    if not start or not end:
        return jsonify({'error': 'start_datetime and end_datetime are required'}), 400

    try:
        orders = service.fetch_orders(start, end, [], include_authorized=True)

        return jsonify({
            'debug': True,
            'start_datetime_received': start,
            'end_datetime_received': end,
            'shop_domain': service.shop_domain,
            'total_orders': len(orders),
            'orders': [
                {
                    'id': o.id,
                    'order_number': o.order_number,
                    'created_at': o.created_at,
                    'source_name': o.source_name,
                    'total_price': float(o.total_price),
                    'customer_email': o.customer_email
                }
                for o in orders[:20]  # Limit to first 20 for debug
            ]
        })

    except Exception as e:
        logger.error(f"[DEBUG] Error: {str(e)}")
        return jsonify({'error': str(e), 'start': start, 'end': end}), 500


@store_credit_events_bp.route('/templates', methods=['GET'])
def list_templates():
    """
    List available event templates.

    Returns:
        Predefined event templates like Trade Night
    """
    templates = [
        {
            'id': 'trade-night',
            'name': 'Trade Night',
            'description': '10% store credit on all purchases during Trade Night hours',
            'default_sources': ['pos', 'web', 'shop'],
            'default_credit_percent': 10,
            'duration_hours': 3
        },
        {
            'id': 'grand-opening',
            'name': 'Grand Opening',
            'description': '15% store credit on opening day purchases',
            'default_sources': ['pos', 'web', 'shop'],
            'default_credit_percent': 15,
            'duration_hours': 24
        },
        {
            'id': 'holiday-promo',
            'name': 'Holiday Promotion',
            'description': '5% store credit on holiday purchases',
            'default_sources': ['pos', 'web', 'shop'],
            'default_credit_percent': 5,
            'duration_hours': 72
        }
    ]

    return jsonify({'templates': templates})
