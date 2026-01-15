"""
Third-Party Integration API endpoints for TradeUp.

Provides connection management for:
- Gorgias (customer service)
- Judge.me (product reviews)
- Recharge (subscriptions)
"""

from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm.attributes import flag_modified
from ...middleware.shopify_auth import require_shopify_auth
from ...services.gorgias_service import get_gorgias_service
from ...services.judgeme_service import get_judgeme_service
from ...services.recharge_service import get_recharge_service
from ...extensions import db

thirdparty_bp = Blueprint('thirdparty', __name__)


# ==================== GORGIAS ENDPOINTS ====================

@thirdparty_bp.route('/gorgias/status', methods=['GET'])
@require_shopify_auth
def get_gorgias_status():
    """Get Gorgias integration status."""
    try:
        service = get_gorgias_service(g.tenant_id)

        status = {'enabled': False, 'connected': False}

        if service.is_enabled():
            status['enabled'] = True
            connection = service.test_connection()
            status['connected'] = connection.get('success', False)
            if connection.get('success'):
                status['account'] = connection.get('account')

        return jsonify({
            'success': True,
            **status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/gorgias/connect', methods=['POST'])
@require_shopify_auth
def connect_gorgias():
    """
    Connect Gorgias integration.

    Request body:
    {
        "api_key": "base64_encoded_key",
        "domain": "mystore.gorgias.com"
    }
    """
    try:
        data = request.get_json()
        api_key = data.get('api_key')
        domain = data.get('domain')

        if not api_key or not domain:
            return jsonify({'error': 'API key and domain are required'}), 400

        # Test connection
        from ...services.gorgias_service import GorgiasService
        test_service = GorgiasService(g.tenant_id)
        test_service._api_key = api_key
        test_service._domain = domain

        connection = test_service.test_connection()

        if not connection.get('success'):
            return jsonify({
                'error': 'Invalid credentials',
                'details': connection.get('error')
            }), 400

        # Save settings
        tenant = g.tenant
        if tenant.settings is None:
            tenant.settings = {}

        if 'integrations' not in tenant.settings:
            tenant.settings['integrations'] = {}

        tenant.settings['integrations']['gorgias'] = {
            'enabled': True,
            'api_key': api_key,
            'domain': domain,
            'auto_enrich_tickets': data.get('auto_enrich_tickets', True),
            'add_tier_tags': data.get('add_tier_tags', True),
            'connected_at': __import__('datetime').datetime.utcnow().isoformat()
        }

        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Gorgias connected successfully',
            'account': connection.get('account')
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/gorgias/disconnect', methods=['POST'])
@require_shopify_auth
def disconnect_gorgias():
    """Disconnect Gorgias integration."""
    try:
        tenant = g.tenant

        if tenant.settings and 'integrations' in tenant.settings:
            tenant.settings['integrations']['gorgias'] = {'enabled': False}
            flag_modified(tenant, 'settings')
            db.session.commit()

        return jsonify({'success': True, 'message': 'Gorgias disconnected'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/gorgias/widget', methods=['GET'])
@require_shopify_auth
def get_gorgias_widget_data():
    """
    Get widget data for a customer.

    Query params:
    - email: Customer email address
    """
    try:
        email = request.args.get('email')
        if not email:
            return jsonify({'error': 'Email is required'}), 400

        service = get_gorgias_service(g.tenant_id)
        widget_data = service.get_widget_data(email)

        return jsonify({
            'success': True,
            'data': widget_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== JUDGE.ME ENDPOINTS ====================

@thirdparty_bp.route('/judgeme/status', methods=['GET'])
@require_shopify_auth
def get_judgeme_status():
    """Get Judge.me integration status."""
    try:
        service = get_judgeme_service(g.tenant_id)

        status = {'enabled': False, 'connected': False}

        if service.is_enabled():
            status['enabled'] = True
            connection = service.test_connection()
            status['connected'] = connection.get('success', False)

        # Include points config
        status['points_config'] = service.get_points_config()

        return jsonify({
            'success': True,
            **status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/judgeme/connect', methods=['POST'])
@require_shopify_auth
def connect_judgeme():
    """
    Connect Judge.me integration.

    Request body:
    {
        "api_token": "xxx",
        "points_per_review": 50,
        "points_per_photo_review": 100,
        "points_per_video_review": 200,
        "max_reviews_per_day": 3
    }
    """
    try:
        data = request.get_json()
        api_token = data.get('api_token')

        if not api_token:
            return jsonify({'error': 'API token is required'}), 400

        # Test connection
        from ...services.judgeme_service import JudgeMeService
        test_service = JudgeMeService(g.tenant_id)
        test_service._api_token = api_token

        connection = test_service.test_connection()

        if not connection.get('success'):
            return jsonify({
                'error': 'Invalid API token',
                'details': connection.get('error')
            }), 400

        # Save settings
        tenant = g.tenant
        if tenant.settings is None:
            tenant.settings = {}

        if 'integrations' not in tenant.settings:
            tenant.settings['integrations'] = {}

        tenant.settings['integrations']['judgeme'] = {
            'enabled': True,
            'api_token': api_token,
            'shop_domain': tenant.shop_domain,
            'points_per_review': data.get('points_per_review', 50),
            'points_per_photo_review': data.get('points_per_photo_review', 100),
            'points_per_video_review': data.get('points_per_video_review', 200),
            'max_reviews_per_day': data.get('max_reviews_per_day', 3),
            'connected_at': __import__('datetime').datetime.utcnow().isoformat()
        }

        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Judge.me connected successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/judgeme/disconnect', methods=['POST'])
@require_shopify_auth
def disconnect_judgeme():
    """Disconnect Judge.me integration."""
    try:
        tenant = g.tenant

        if tenant.settings and 'integrations' in tenant.settings:
            tenant.settings['integrations']['judgeme'] = {'enabled': False}
            flag_modified(tenant, 'settings')
            db.session.commit()

        return jsonify({'success': True, 'message': 'Judge.me disconnected'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/judgeme/settings', methods=['PUT'])
@require_shopify_auth
def update_judgeme_settings():
    """Update Judge.me points configuration."""
    try:
        data = request.get_json()
        tenant = g.tenant

        if not tenant.settings or 'integrations' not in tenant.settings:
            return jsonify({'error': 'Judge.me not connected'}), 400

        judgeme = tenant.settings['integrations'].get('judgeme', {})
        if not judgeme.get('enabled'):
            return jsonify({'error': 'Judge.me not enabled'}), 400

        # Update points settings
        if 'points_per_review' in data:
            judgeme['points_per_review'] = data['points_per_review']
        if 'points_per_photo_review' in data:
            judgeme['points_per_photo_review'] = data['points_per_photo_review']
        if 'points_per_video_review' in data:
            judgeme['points_per_video_review'] = data['points_per_video_review']
        if 'max_reviews_per_day' in data:
            judgeme['max_reviews_per_day'] = data['max_reviews_per_day']

        tenant.settings['integrations']['judgeme'] = judgeme
        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'settings': judgeme
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/judgeme/stats', methods=['GET'])
@require_shopify_auth
def get_judgeme_stats():
    """Get Judge.me review points statistics."""
    try:
        service = get_judgeme_service(g.tenant_id)
        stats = service.get_review_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== RECHARGE ENDPOINTS ====================

@thirdparty_bp.route('/recharge/status', methods=['GET'])
@require_shopify_auth
def get_recharge_status():
    """Get Recharge integration status."""
    try:
        service = get_recharge_service(g.tenant_id)

        status = {'enabled': False, 'connected': False}

        if service.is_enabled():
            status['enabled'] = True
            connection = service.test_connection()
            status['connected'] = connection.get('success', False)
            if connection.get('success'):
                status['store'] = connection.get('store')

        return jsonify({
            'success': True,
            **status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/recharge/connect', methods=['POST'])
@require_shopify_auth
def connect_recharge():
    """
    Connect Recharge integration.

    Request body:
    {
        "api_key": "xxx",
        "award_points_on_subscription": true,
        "points_per_dollar": 1,
        "count_towards_tier": true
    }
    """
    try:
        data = request.get_json()
        api_key = data.get('api_key')

        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        # Test connection
        from ...services.recharge_service import RechargeService
        test_service = RechargeService(g.tenant_id)
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

        tenant.settings['integrations']['recharge'] = {
            'enabled': True,
            'api_key': api_key,
            'award_points_on_subscription': data.get('award_points_on_subscription', True),
            'points_per_dollar': data.get('points_per_dollar', 1),
            'count_towards_tier': data.get('count_towards_tier', True),
            'connected_at': __import__('datetime').datetime.utcnow().isoformat()
        }

        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Recharge connected successfully',
            'store': connection.get('store')
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/recharge/disconnect', methods=['POST'])
@require_shopify_auth
def disconnect_recharge():
    """Disconnect Recharge integration."""
    try:
        tenant = g.tenant

        if tenant.settings and 'integrations' in tenant.settings:
            tenant.settings['integrations']['recharge'] = {'enabled': False}
            flag_modified(tenant, 'settings')
            db.session.commit()

        return jsonify({'success': True, 'message': 'Recharge disconnected'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/recharge/settings', methods=['PUT'])
@require_shopify_auth
def update_recharge_settings():
    """Update Recharge integration settings."""
    try:
        data = request.get_json()
        tenant = g.tenant

        if not tenant.settings or 'integrations' not in tenant.settings:
            return jsonify({'error': 'Recharge not connected'}), 400

        recharge = tenant.settings['integrations'].get('recharge', {})
        if not recharge.get('enabled'):
            return jsonify({'error': 'Recharge not enabled'}), 400

        # Update settings
        if 'award_points_on_subscription' in data:
            recharge['award_points_on_subscription'] = data['award_points_on_subscription']
        if 'points_per_dollar' in data:
            recharge['points_per_dollar'] = data['points_per_dollar']
        if 'count_towards_tier' in data:
            recharge['count_towards_tier'] = data['count_towards_tier']

        tenant.settings['integrations']['recharge'] = recharge
        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': True,
            'settings': recharge
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@thirdparty_bp.route('/recharge/subscriptions', methods=['GET'])
@require_shopify_auth
def get_customer_subscriptions():
    """
    Get subscriptions for a customer.

    Query params:
    - email: Customer email address
    """
    try:
        email = request.args.get('email')
        if not email:
            return jsonify({'error': 'Email is required'}), 400

        service = get_recharge_service(g.tenant_id)

        if not service.is_enabled():
            return jsonify({'error': 'Recharge not enabled'}), 400

        result = service.get_customer_subscriptions(email)

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ALL INTEGRATIONS STATUS ====================

@thirdparty_bp.route('/status', methods=['GET'])
@require_shopify_auth
def get_all_integrations_status():
    """Get status of all third-party integrations."""
    try:
        gorgias = get_gorgias_service(g.tenant_id)
        judgeme = get_judgeme_service(g.tenant_id)
        recharge = get_recharge_service(g.tenant_id)

        from ...services.klaviyo_service import get_klaviyo_service
        from ...services.sms_service import get_sms_service

        klaviyo = get_klaviyo_service(g.tenant_id)
        sms = get_sms_service(g.tenant_id)

        return jsonify({
            'success': True,
            'integrations': {
                'klaviyo': {
                    'enabled': klaviyo.is_enabled(),
                    'type': 'email_marketing'
                },
                'postscript': {
                    'enabled': sms.postscript.is_enabled(),
                    'type': 'sms_marketing'
                },
                'attentive': {
                    'enabled': sms.attentive.is_enabled(),
                    'type': 'sms_marketing'
                },
                'gorgias': {
                    'enabled': gorgias.is_enabled(),
                    'type': 'customer_service'
                },
                'judgeme': {
                    'enabled': judgeme.is_enabled(),
                    'type': 'reviews'
                },
                'recharge': {
                    'enabled': recharge.is_enabled(),
                    'type': 'subscriptions'
                }
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
