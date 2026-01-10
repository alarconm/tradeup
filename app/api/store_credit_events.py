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

    try:
        result = service.preview_event(
            start_datetime=data['start_datetime'],
            end_datetime=data['end_datetime'],
            sources=data['sources'],
            credit_percent=data.get('credit_percent', 10),
            include_authorized=data.get('include_authorized', True)
        )
        return jsonify(result)

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

    # Generate job_id if not provided
    job_id = data.get('job_id')
    if not job_id:
        job_id = f"event-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

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
            delay_ms=data.get('delay_ms', 1000)
        )
        return jsonify(result)

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
    service = get_service_for_tenant()
    if not service:
        return jsonify({'error': 'Shopify not configured for this shop'}), 500

    start = request.args.get('start_datetime')
    end = request.args.get('end_datetime')

    if not start or not end:
        return jsonify({'error': 'start_datetime and end_datetime are required'}), 400

    try:
        # Fetch orders with no source filter to see all sources
        orders = service.fetch_orders(start, end, [], include_authorized=True)

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
