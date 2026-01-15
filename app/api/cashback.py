"""
Cashback Campaign API endpoints for TradeUp.

Provides CRUD operations for cashback campaigns and
retrieval of redemption statistics.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from ..services.cashback_service import get_cashback_service

cashback_bp = Blueprint('cashback', __name__)


@cashback_bp.route('/campaigns', methods=['GET'])
@require_shopify_auth
def list_campaigns():
    """
    List all cashback campaigns.

    Query params:
    - status: Filter by status (draft, scheduled, active, paused, ended, cancelled)
    - include_stats: Include redemption statistics (default: false)
    """
    try:
        status = request.args.get('status')
        include_stats = request.args.get('include_stats', 'false').lower() == 'true'

        service = get_cashback_service(g.tenant_id)
        campaigns = service.get_campaigns(status=status, include_stats=include_stats)

        return jsonify({
            'success': True,
            'campaigns': campaigns,
            'total': len(campaigns)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cashback_bp.route('/campaigns', methods=['POST'])
@require_shopify_auth
def create_campaign():
    """
    Create a new cashback campaign.

    Request body:
    {
        "name": "Holiday Cashback",
        "description": "10% cashback on all orders",
        "cashback_rate": 10.0,
        "min_purchase": 50.00,
        "max_cashback": 100.00,
        "max_total_cashback": 5000.00,
        "start_date": "2026-01-15T00:00:00Z",
        "end_date": "2026-01-31T23:59:59Z",
        "applies_to": "all",
        "tier_restriction": ["GOLD", "PLATINUM"],
        "max_uses_per_customer": 1
    }
    """
    try:
        data = request.get_json()

        # Validate required fields
        required = ['name', 'cashback_rate', 'start_date', 'end_date']
        for field in required:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400

        service = get_cashback_service(g.tenant_id)
        result = service.create_campaign(data, created_by=g.shop_domain)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cashback_bp.route('/campaigns/<int:campaign_id>', methods=['GET'])
@require_shopify_auth
def get_campaign(campaign_id: int):
    """Get a single cashback campaign."""
    try:
        service = get_cashback_service(g.tenant_id)
        campaign = service.get_campaign(campaign_id)

        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404

        return jsonify({
            'success': True,
            'campaign': campaign
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cashback_bp.route('/campaigns/<int:campaign_id>', methods=['PUT'])
@require_shopify_auth
def update_campaign(campaign_id: int):
    """Update a cashback campaign."""
    try:
        data = request.get_json()

        service = get_cashback_service(g.tenant_id)
        result = service.update_campaign(campaign_id, data)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cashback_bp.route('/campaigns/<int:campaign_id>', methods=['DELETE'])
@require_shopify_auth
def delete_campaign(campaign_id: int):
    """Delete a draft cashback campaign."""
    try:
        service = get_cashback_service(g.tenant_id)
        result = service.delete_campaign(campaign_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cashback_bp.route('/campaigns/<int:campaign_id>/activate', methods=['POST'])
@require_shopify_auth
def activate_campaign(campaign_id: int):
    """Activate a cashback campaign."""
    try:
        service = get_cashback_service(g.tenant_id)
        result = service.activate_campaign(campaign_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cashback_bp.route('/campaigns/<int:campaign_id>/pause', methods=['POST'])
@require_shopify_auth
def pause_campaign(campaign_id: int):
    """Pause an active cashback campaign."""
    try:
        service = get_cashback_service(g.tenant_id)
        result = service.pause_campaign(campaign_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cashback_bp.route('/campaigns/<int:campaign_id>/end', methods=['POST'])
@require_shopify_auth
def end_campaign(campaign_id: int):
    """End a cashback campaign."""
    try:
        service = get_cashback_service(g.tenant_id)
        result = service.end_campaign(campaign_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cashback_bp.route('/campaigns/<int:campaign_id>/stats', methods=['GET'])
@require_shopify_auth
def get_campaign_stats(campaign_id: int):
    """Get redemption statistics for a campaign."""
    try:
        service = get_cashback_service(g.tenant_id)
        campaign = service.get_campaign(campaign_id)

        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404

        stats = service._get_campaign_stats(campaign_id)

        return jsonify({
            'success': True,
            'campaign_id': campaign_id,
            'campaign_name': campaign.get('name'),
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cashback_bp.route('/active', methods=['GET'])
@require_shopify_auth
def get_active_campaigns():
    """Get currently active cashback campaigns."""
    try:
        service = get_cashback_service(g.tenant_id)
        campaigns = service.get_active_campaigns()

        return jsonify({
            'success': True,
            'campaigns': [c.to_dict() for c in campaigns],
            'total': len(campaigns)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
