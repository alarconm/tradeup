"""
SMS Integration API endpoints for TradeUp.

Provides connection management and sync operations for
Postscript and Attentive SMS marketing integrations.
"""

from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm.attributes import flag_modified
from ...middleware.shopify_auth import require_shopify_auth
from ...services.sms_service import (
    get_sms_service,
    get_postscript_service,
    get_attentive_service
)
from ...extensions import db

sms_bp = Blueprint('sms', __name__)


# ==================== UNIFIED SMS ENDPOINTS ====================

@sms_bp.route('/status', methods=['GET'])
@require_shopify_auth
def get_sms_status():
    """
    Get SMS integration status for all providers.

    Returns connection status for Postscript and Attentive.
    """
    try:
        sms_service = get_sms_service(g.tenant_id)

        postscript_status = {'enabled': False, 'connected': False}
        attentive_status = {'enabled': False, 'connected': False}

        # Check Postscript
        if sms_service.postscript.is_enabled():
            postscript_status['enabled'] = True
            connection = sms_service.postscript.test_connection()
            postscript_status['connected'] = connection.get('success', False)
            if connection.get('success'):
                postscript_status['shop'] = connection.get('shop')

        # Check Attentive
        if sms_service.attentive.is_enabled():
            attentive_status['enabled'] = True
            connection = sms_service.attentive.test_connection()
            attentive_status['connected'] = connection.get('success', False)
            if connection.get('success'):
                attentive_status['account'] = connection.get('account')

        return jsonify({
            'success': True,
            'enabled': sms_service.is_enabled(),
            'active_provider': sms_service.get_enabled_provider(),
            'providers': {
                'postscript': postscript_status,
                'attentive': attentive_status
            },
            'supported_events': sms_service.SUPPORTED_EVENTS
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@sms_bp.route('/sync-members', methods=['POST'])
@require_shopify_auth
def sync_all_members():
    """
    Sync all members to enabled SMS providers.

    This is a bulk operation that syncs members with phone numbers.
    """
    try:
        sms_service = get_sms_service(g.tenant_id)

        if not sms_service.is_enabled():
            return jsonify({'error': 'No SMS provider enabled'}), 400

        result = sms_service.sync_all_members()

        return jsonify({
            'success': True,
            'stats': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== POSTSCRIPT ENDPOINTS ====================

@sms_bp.route('/postscript/connect', methods=['POST'])
@require_shopify_auth
def connect_postscript():
    """
    Connect Postscript integration.

    Request body:
    {
        "api_key": "pk_xxx...",
        "shop_id": "shop_xxx",
        "sync_on_events": ["member_enrolled", "tier_upgraded"]
    }
    """
    try:
        data = request.get_json()
        api_key = data.get('api_key')

        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        # Test connection with provided key
        from ...services.sms_service import PostscriptService
        test_service = PostscriptService(g.tenant_id)
        test_service._api_key = api_key

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

        tenant.settings['integrations']['postscript'] = {
            'enabled': True,
            'api_key': api_key,
            'shop_id': data.get('shop_id'),
            'sync_on_events': data.get('sync_on_events', [
                'member_enrolled',
                'tier_upgraded',
                'trade_in_completed',
                'credit_issued'
            ]),
            'connected_at': __import__('datetime').datetime.utcnow().isoformat()
        }

        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Postscript connected successfully',
            'shop': connection.get('shop')
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@sms_bp.route('/postscript/disconnect', methods=['POST'])
@require_shopify_auth
def disconnect_postscript():
    """Disconnect Postscript integration."""
    try:
        tenant = g.tenant

        if tenant.settings and 'integrations' in tenant.settings:
            tenant.settings['integrations']['postscript'] = {
                'enabled': False
            }
            flag_modified(tenant, 'settings')
            db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Postscript disconnected'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@sms_bp.route('/postscript/settings', methods=['PUT'])
@require_shopify_auth
def update_postscript_settings():
    """
    Update Postscript settings.

    Request body:
    {
        "sync_on_events": ["member_enrolled", "tier_upgraded"]
    }
    """
    try:
        data = request.get_json()
        tenant = g.tenant

        if not tenant.settings or 'integrations' not in tenant.settings:
            return jsonify({'error': 'Postscript not connected'}), 400

        postscript = tenant.settings['integrations'].get('postscript', {})
        if not postscript.get('enabled'):
            return jsonify({'error': 'Postscript not enabled'}), 400

        # Update settings
        if 'sync_on_events' in data:
            postscript['sync_on_events'] = data['sync_on_events']

        tenant.settings['integrations']['postscript'] = postscript
        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'settings': postscript
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== ATTENTIVE ENDPOINTS ====================

@sms_bp.route('/attentive/connect', methods=['POST'])
@require_shopify_auth
def connect_attentive():
    """
    Connect Attentive integration.

    Request body:
    {
        "api_key": "attn_xxx...",
        "sync_on_events": ["member_enrolled", "tier_upgraded"]
    }
    """
    try:
        data = request.get_json()
        api_key = data.get('api_key')

        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        # Test connection with provided key
        from ...services.sms_service import AttentiveService
        test_service = AttentiveService(g.tenant_id)
        test_service._api_key = api_key

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

        tenant.settings['integrations']['attentive'] = {
            'enabled': True,
            'api_key': api_key,
            'sync_on_events': data.get('sync_on_events', [
                'member_enrolled',
                'tier_upgraded',
                'trade_in_completed',
                'credit_issued'
            ]),
            'connected_at': __import__('datetime').datetime.utcnow().isoformat()
        }

        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Attentive connected successfully',
            'account': connection.get('account')
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@sms_bp.route('/attentive/disconnect', methods=['POST'])
@require_shopify_auth
def disconnect_attentive():
    """Disconnect Attentive integration."""
    try:
        tenant = g.tenant

        if tenant.settings and 'integrations' in tenant.settings:
            tenant.settings['integrations']['attentive'] = {
                'enabled': False
            }
            flag_modified(tenant, 'settings')
            db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Attentive disconnected'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@sms_bp.route('/attentive/settings', methods=['PUT'])
@require_shopify_auth
def update_attentive_settings():
    """
    Update Attentive settings.

    Request body:
    {
        "sync_on_events": ["member_enrolled", "tier_upgraded"]
    }
    """
    try:
        data = request.get_json()
        tenant = g.tenant

        if not tenant.settings or 'integrations' not in tenant.settings:
            return jsonify({'error': 'Attentive not connected'}), 400

        attentive = tenant.settings['integrations'].get('attentive', {})
        if not attentive.get('enabled'):
            return jsonify({'error': 'Attentive not enabled'}), 400

        # Update settings
        if 'sync_on_events' in data:
            attentive['sync_on_events'] = data['sync_on_events']

        tenant.settings['integrations']['attentive'] = attentive
        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'settings': attentive
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@sms_bp.route('/test-event', methods=['POST'])
@require_shopify_auth
def test_sms_event():
    """
    Send a test event to enabled SMS providers.

    Request body:
    {
        "event_type": "member_enrolled",
        "phone": "+1234567890"
    }
    """
    try:
        data = request.get_json()
        event_type = data.get('event_type', 'test_event')
        phone = data.get('phone')

        if not phone:
            return jsonify({'error': 'Phone number is required'}), 400

        sms_service = get_sms_service(g.tenant_id)

        if not sms_service.is_enabled():
            return jsonify({'error': 'No SMS provider enabled'}), 400

        results = {}

        # Send to Postscript
        if sms_service.postscript.is_enabled():
            results['postscript'] = sms_service.postscript.track_event(
                event_type,
                phone,
                {
                    'test': True,
                    'source': 'test_endpoint',
                    'tenant_id': g.tenant_id
                }
            )

        # Send to Attentive
        if sms_service.attentive.is_enabled():
            results['attentive'] = sms_service.attentive.track_event(
                event_type,
                phone,
                {
                    'test': True,
                    'source': 'test_endpoint',
                    'tenant_id': g.tenant_id
                }
            )

        return jsonify({
            'success': any(r.get('success') for r in results.values()),
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
