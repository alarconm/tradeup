"""
Klaviyo Integration API endpoints for TradeUp.

Provides connection management, sync operations, and
configuration for Klaviyo email marketing integration.
"""
from datetime import datetime

from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm.attributes import flag_modified
from ...middleware.shopify_auth import require_shopify_auth
from ...services.klaviyo_service import get_klaviyo_service
from ...extensions import db

klaviyo_bp = Blueprint('klaviyo', __name__)


@klaviyo_bp.route('/status', methods=['GET'])
@require_shopify_auth
def get_status():
    """
    Get Klaviyo integration status.

    Returns connection status and configuration.
    """
    try:
        service = get_klaviyo_service(g.tenant_id)

        # Test connection if enabled
        if service.is_enabled():
            connection = service.test_connection()
        else:
            connection = {'connected': False}

        return jsonify({
            'success': True,
            'enabled': service.is_enabled(),
            'connected': connection.get('success', False),
            'account': connection.get('account') if connection.get('success') else None,
            'settings': {
                'list_id': service.settings.get('list_id'),
                'sync_on_events': service.settings.get('sync_on_events', [])
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@klaviyo_bp.route('/connect', methods=['POST'])
@require_shopify_auth
def connect():
    """
    Connect Klaviyo integration.

    Request body:
    {
        "api_key": "pk_xxx...",
        "list_id": "ABC123",
        "sync_on_events": ["member_enrolled", "tier_upgraded", "trade_in_completed"]
    }
    """
    try:
        data = request.get_json()
        api_key = data.get('api_key')

        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        # Validate API key by testing connection
        from ...services.klaviyo_service import KlaviyoService
        test_service = KlaviyoService(g.tenant_id)
        test_service._api_key = api_key
        test_service._settings = {'enabled': True}

        connection = test_service.test_connection()

        if not connection.get('success'):
            return jsonify({
                'error': 'Invalid API key',
                'details': connection.get('error')
            }), 400

        # Save settings
        tenant = g.tenant
        if tenant.settings is None:
            tenant.settings = {}

        if 'integrations' not in tenant.settings:
            tenant.settings['integrations'] = {}

        tenant.settings['integrations']['klaviyo'] = {
            'enabled': True,
            'api_key': api_key,
            'list_id': data.get('list_id'),
            'sync_on_events': data.get('sync_on_events', [
                'member_enrolled',
                'tier_upgraded',
                'trade_in_completed',
                'credit_issued',
                'points_earned'
            ]),
            'connected_at': datetime.utcnow().isoformat()
        }

        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Klaviyo connected successfully',
            'account': connection.get('account')
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@klaviyo_bp.route('/disconnect', methods=['POST'])
@require_shopify_auth
def disconnect():
    """Disconnect Klaviyo integration."""
    try:
        tenant = g.tenant

        if tenant.settings and 'integrations' in tenant.settings:
            tenant.settings['integrations']['klaviyo'] = {
                'enabled': False
            }
            flag_modified(tenant, 'settings')
            db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Klaviyo disconnected'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@klaviyo_bp.route('/settings', methods=['PUT'])
@require_shopify_auth
def update_settings():
    """
    Update Klaviyo settings.

    Request body:
    {
        "list_id": "ABC123",
        "sync_on_events": ["member_enrolled", "tier_upgraded"]
    }
    """
    try:
        data = request.get_json()
        tenant = g.tenant

        if not tenant.settings or 'integrations' not in tenant.settings:
            return jsonify({'error': 'Klaviyo not connected'}), 400

        klaviyo = tenant.settings['integrations'].get('klaviyo', {})
        if not klaviyo.get('enabled'):
            return jsonify({'error': 'Klaviyo not enabled'}), 400

        # Update settings
        if 'list_id' in data:
            klaviyo['list_id'] = data['list_id']
        if 'sync_on_events' in data:
            klaviyo['sync_on_events'] = data['sync_on_events']

        tenant.settings['integrations']['klaviyo'] = klaviyo
        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'settings': klaviyo
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@klaviyo_bp.route('/lists', methods=['GET'])
@require_shopify_auth
def get_lists():
    """Get available Klaviyo lists."""
    try:
        service = get_klaviyo_service(g.tenant_id)

        if not service.is_enabled():
            return jsonify({'error': 'Klaviyo not enabled'}), 400

        result = service.get_lists()

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@klaviyo_bp.route('/sync-members', methods=['POST'])
@require_shopify_auth
def sync_members():
    """
    Sync all members to Klaviyo.

    This is a bulk operation that may take time for large member lists.
    """
    try:
        service = get_klaviyo_service(g.tenant_id)

        if not service.is_enabled():
            return jsonify({'error': 'Klaviyo not enabled'}), 400

        result = service.sync_all_members()

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@klaviyo_bp.route('/sync-member/<int:member_id>', methods=['POST'])
@require_shopify_auth
def sync_member(member_id: int):
    """Sync a single member to Klaviyo."""
    try:
        from ...models.member import Member

        service = get_klaviyo_service(g.tenant_id)

        if not service.is_enabled():
            return jsonify({'error': 'Klaviyo not enabled'}), 400

        member = Member.query.filter_by(
            id=member_id,
            tenant_id=g.tenant_id
        ).first()

        if not member:
            return jsonify({'error': 'Member not found'}), 404

        result = service.upsert_profile(member)

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@klaviyo_bp.route('/test-event', methods=['POST'])
@require_shopify_auth
def test_event():
    """
    Send a test event to Klaviyo.

    Request body:
    {
        "event_type": "member_enrolled",
        "email": "test@example.com"
    }
    """
    try:
        data = request.get_json()
        event_type = data.get('event_type', 'test_event')
        email = data.get('email')

        if not email:
            return jsonify({'error': 'Email is required'}), 400

        service = get_klaviyo_service(g.tenant_id)

        if not service.is_enabled():
            return jsonify({'error': 'Klaviyo not enabled'}), 400

        result = service.track_event(
            event_name=f'tradeup_{event_type}',
            email=email,
            properties={
                'test': True,
                'source': 'test_endpoint',
                'tenant_id': g.tenant_id
            }
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
