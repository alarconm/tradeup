"""
Partner Integration API endpoints.
Manage partner configurations and sync operations.
"""
from flask import Blueprint, request, jsonify, g
from ..extensions import db
from ..models import PartnerIntegration, PartnerSyncLog
from ..services.partner_sync_service import PartnerSyncService
from ..middleware.shop_auth import require_shop_auth

partners_bp = Blueprint('partners', __name__)


# ==================== Partner Integration CRUD ====================

@partners_bp.route('', methods=['GET'])
@require_shop_auth
def list_integrations():
    """List all partner integrations for the tenant."""
    tenant_id = g.tenant_id

    integrations = PartnerIntegration.query.filter_by(
        tenant_id=tenant_id
    ).order_by(PartnerIntegration.created_at.desc()).all()

    return jsonify({
        'integrations': [i.to_dict() for i in integrations]
    })


@partners_bp.route('/<int:integration_id>', methods=['GET'])
@require_shop_auth
def get_integration(integration_id):
    """Get partner integration details."""
    integration = PartnerIntegration.query.get_or_404(integration_id)
    return jsonify(integration.to_dict())


@partners_bp.route('', methods=['POST'])
@require_shop_auth
def create_integration():
    """Create a new partner integration."""
    tenant_id = g.tenant_id
    data = request.json

    # Generate slug from name if not provided
    slug = data.get('slug') or data['name'].lower().replace(' ', '-').replace('_', '-')

    # Check for duplicate slug
    existing = PartnerIntegration.query.filter_by(
        tenant_id=tenant_id,
        slug=slug
    ).first()

    if existing:
        return jsonify({'error': f'Integration with slug "{slug}" already exists'}), 400

    integration = PartnerIntegration(
        tenant_id=tenant_id,
        name=data['name'],
        slug=slug,
        partner_type=data.get('partner_type', 'wordpress'),
        api_url=data.get('api_url'),
        api_token=data.get('api_token'),
        webhook_secret=data.get('webhook_secret'),
        enabled=data.get('enabled', True),
        sync_trade_ins=data.get('sync_trade_ins', True),
        sync_bonuses=data.get('sync_bonuses', True),
        sync_members=data.get('sync_members', False),
        field_mapping=data.get('field_mapping', {})
    )

    db.session.add(integration)
    db.session.commit()

    return jsonify(integration.to_dict()), 201


@partners_bp.route('/<int:integration_id>', methods=['PUT'])
@require_shop_auth
def update_integration(integration_id):
    """Update a partner integration."""
    integration = PartnerIntegration.query.get_or_404(integration_id)
    data = request.json

    # Update allowed fields
    if 'name' in data:
        integration.name = data['name']
    if 'api_url' in data:
        integration.api_url = data['api_url']
    if 'api_token' in data:
        integration.api_token = data['api_token']
    if 'webhook_secret' in data:
        integration.webhook_secret = data['webhook_secret']
    if 'enabled' in data:
        integration.enabled = data['enabled']
    if 'sync_trade_ins' in data:
        integration.sync_trade_ins = data['sync_trade_ins']
    if 'sync_bonuses' in data:
        integration.sync_bonuses = data['sync_bonuses']
    if 'sync_members' in data:
        integration.sync_members = data['sync_members']
    if 'field_mapping' in data:
        integration.field_mapping = data['field_mapping']

    db.session.commit()
    return jsonify(integration.to_dict())


@partners_bp.route('/<int:integration_id>', methods=['DELETE'])
@require_shop_auth
def delete_integration(integration_id):
    """Delete a partner integration."""
    integration = PartnerIntegration.query.get_or_404(integration_id)

    db.session.delete(integration)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Integration deleted'})


# ==================== Sync Operations ====================

@partners_bp.route('/<int:integration_id>/test', methods=['POST'])
@require_shop_auth
def test_integration(integration_id):
    """Test connectivity to a partner integration."""
    integration = PartnerIntegration.query.get_or_404(integration_id)
    tenant_id = g.tenant_id

    service = PartnerSyncService(tenant_id)

    # Send a test ping
    test_payload = {
        'type': 'test',
        'message': 'TradeUp connectivity test',
        'timestamp': __import__('datetime').datetime.utcnow().isoformat()
    }

    endpoint = f"{integration.api_url}/tradeup/test"

    result = service._send_to_partner(integration, endpoint, test_payload)

    return jsonify({
        'success': result.get('success', False),
        'status_code': result.get('status_code'),
        'error': result.get('error'),
        'response': result.get('body')
    })


@partners_bp.route('/sync-logs', methods=['GET'])
@require_shop_auth
def list_sync_logs():
    """List sync logs with filters."""
    tenant_id = g.tenant_id

    integration_id = request.args.get('integration_id', type=int)
    sync_type = request.args.get('type')
    status = request.args.get('status')
    limit = request.args.get('limit', 50, type=int)

    service = PartnerSyncService(tenant_id)
    logs = service.get_sync_logs(
        integration_id=integration_id,
        sync_type=sync_type,
        status=status,
        limit=limit
    )

    return jsonify({
        'logs': [log.to_dict() for log in logs]
    })


@partners_bp.route('/retry-failed', methods=['POST'])
@require_shop_auth
def retry_failed_syncs():
    """Retry all failed syncs."""
    tenant_id = g.tenant_id
    data = request.json or {}

    integration_id = data.get('integration_id')

    service = PartnerSyncService(tenant_id)
    results = service.retry_failed_syncs(integration_id=integration_id)

    return jsonify({
        'success': True,
        'results': results,
        'retried_count': len(results)
    })


# ==================== ORB Sports Cards Preset ====================

@partners_bp.route('/presets/orb-sports-cards', methods=['POST'])
@require_shop_auth
def create_orb_integration():
    """
    Create an ORB Sports Cards integration with default settings.

    This is a convenience endpoint that sets up the integration
    with the correct API URL and field mappings for ORB.
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    # Check if ORB integration already exists
    existing = PartnerIntegration.query.filter_by(
        tenant_id=tenant_id,
        slug='orb-sports-cards'
    ).first()

    if existing:
        return jsonify({
            'error': 'ORB Sports Cards integration already exists',
            'integration': existing.to_dict()
        }), 400

    # Create ORB integration with defaults
    integration = PartnerIntegration(
        tenant_id=tenant_id,
        name='ORB Sports Cards',
        slug='orb-sports-cards',
        partner_type='wordpress',
        api_url=data.get('api_url', 'https://orbsportscards.com/wp-json/mykd/v1'),
        api_token=data.get('api_token'),
        webhook_secret=data.get('webhook_secret'),
        enabled=True,
        sync_trade_ins=True,
        sync_bonuses=True,
        sync_members=False,
        field_mapping={
            'category': 'category',
            'total_trade_value': 'amount',
            'batch_reference': 'description'
        }
    )

    db.session.add(integration)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'ORB Sports Cards integration created',
        'integration': integration.to_dict()
    }), 201
