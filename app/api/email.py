"""
Email Notification API for TradeUp.

Provides endpoints for managing email templates and sending notifications.
"""
from flask import Blueprint, request, jsonify
from ..services.email_service import email_service
from ..middleware.shop_auth import require_shop_auth
from ..models.tenant import Tenant

email_bp = Blueprint('email', __name__)


@email_bp.route('/templates', methods=['GET'])
@require_shop_auth
def get_templates():
    """Get all available email templates for the tenant."""
    tenant_id = request.tenant_id

    templates = email_service.get_all_templates(tenant_id)

    # Group by category
    categorized = {}
    for template in templates:
        category = template['category']
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(template)

    return jsonify({
        'templates': templates,
        'by_category': categorized,
        'categories': list(categorized.keys()),
    })


@email_bp.route('/templates/<template_id>', methods=['GET'])
@require_shop_auth
def get_template(template_id):
    """Get a specific email template."""
    tenant_id = request.tenant_id

    template = email_service.get_template(template_id, tenant_id)
    if not template:
        return jsonify({'error': f'Template not found: {template_id}'}), 404

    return jsonify({
        'id': template_id,
        **template,
    })


@email_bp.route('/preview', methods=['POST'])
@require_shop_auth
def preview_template():
    """
    Preview a rendered template with sample data.

    Request body:
    {
        "template_id": "welcome",
        "data": { ... }  // Optional custom data, otherwise uses sample
    }
    """
    tenant_id = request.tenant_id
    data = request.get_json()

    template_id = data.get('template_id')
    custom_data = data.get('data', {})

    template = email_service.get_template(template_id, tenant_id)
    if not template:
        return jsonify({'error': f'Template not found: {template_id}'}), 404

    # Get tenant info for sample data
    tenant = Tenant.query.get(tenant_id)

    # Sample data for preview
    sample_data = {
        'member_name': custom_data.get('member_name', 'John Doe'),
        'member_number': custom_data.get('member_number', 'TU00010001'),
        'program_name': custom_data.get('program_name', tenant.program_name if tenant else 'TradeUp Rewards'),
        'shop_name': custom_data.get('shop_name', tenant.shop_name if tenant else 'Your Store'),
        'tier_name': custom_data.get('tier_name', 'Gold'),
        'tier_benefits': custom_data.get('tier_benefits', '• 5% trade-in bonus\n• $10 monthly credit\n• Priority processing'),
        'trade_in_id': custom_data.get('trade_in_id', '12345'),
        'item_count': custom_data.get('item_count', '3'),
        'estimated_value': custom_data.get('estimated_value', '$45.00'),
        'credit_amount': custom_data.get('credit_amount', '$50.00'),
        'tier_bonus': custom_data.get('tier_bonus', '$2.50'),
        'total_credit': custom_data.get('total_credit', '$52.50'),
        'status': custom_data.get('status', 'Under Review'),
        'reason': custom_data.get('reason', 'Items require additional verification'),
        'old_tier': custom_data.get('old_tier', 'Silver'),
        'new_tier': custom_data.get('new_tier', 'Gold'),
        'amount': custom_data.get('amount', '$25.00'),
        'current_balance': custom_data.get('current_balance', '$75.00'),
        'expiration_date': custom_data.get('expiration_date', 'March 31, 2026'),
        'reward_amount': custom_data.get('reward_amount', '$10.00'),
        'referred_name': custom_data.get('referred_name', 'Jane Smith'),
        'referred_reward': custom_data.get('referred_reward', '$5.00'),
        'referral_code': custom_data.get('referral_code', 'JOHN2025'),
    }

    # Merge custom data
    sample_data.update(custom_data)

    rendered = email_service.render_template(template, sample_data)

    return jsonify({
        'template_id': template_id,
        'template_name': template['name'],
        'subject': rendered['subject'],
        'body': rendered['body'],
        'html_body': email_service._markdown_to_html(rendered['body']),
    })


@email_bp.route('/send-test', methods=['POST'])
@require_shop_auth
def send_test_email():
    """
    Send a test email to verify configuration.

    Request body:
    {
        "template_id": "welcome",
        "to_email": "test@example.com",
        "to_name": "Test User",
        "data": { ... }  // Optional custom data
    }
    """
    tenant_id = request.tenant_id
    data = request.get_json()

    template_id = data.get('template_id')
    to_email = data.get('to_email')
    to_name = data.get('to_name', 'Test User')
    custom_data = data.get('data', {})

    if not template_id:
        return jsonify({'error': 'template_id is required'}), 400
    if not to_email:
        return jsonify({'error': 'to_email is required'}), 400

    # Get tenant info
    tenant = Tenant.query.get(tenant_id)

    # Build data context
    email_data = {
        'member_name': to_name,
        'member_number': 'TU00010001',
        'program_name': tenant.program_name if tenant else 'TradeUp Rewards',
        'shop_name': tenant.shop_name if tenant else 'Your Store',
        'tier_name': 'Gold',
        'tier_benefits': '• 5% trade-in bonus\n• $10 monthly credit\n• Priority processing',
        'trade_in_id': '12345',
        'item_count': '3',
        'estimated_value': '$45.00',
        'credit_amount': '$50.00',
        'tier_bonus': '$2.50',
        'total_credit': '$52.50',
        'status': 'Under Review',
        'reason': 'Items require additional verification',
        'old_tier': 'Silver',
        'new_tier': 'Gold',
        'amount': '$25.00',
        'current_balance': '$75.00',
        'expiration_date': 'March 31, 2026',
        'reward_amount': '$10.00',
        'referred_name': 'Jane Smith',
        'referred_reward': '$5.00',
        'referral_code': 'TESTCODE',
    }
    email_data.update(custom_data)

    # Get tenant from email if available
    from_email = None
    from_name = None
    if tenant:
        from_name = tenant.shop_name

    result = email_service.send_template_email(
        template_key=template_id,
        tenant_id=tenant_id,
        to_email=to_email,
        to_name=to_name,
        data=email_data,
        from_email=from_email,
        from_name=from_name,
    )

    if result.get('success'):
        return jsonify({
            'success': True,
            'message': f'Test email sent to {to_email}',
        })
    else:
        return jsonify({
            'success': False,
            'error': result.get('error', 'Unknown error'),
        }), 500


@email_bp.route('/settings', methods=['GET'])
@require_shop_auth
def get_email_settings():
    """Get email notification settings for the tenant."""
    tenant_id = request.tenant_id

    # Default settings - TODO: Store in database
    settings = {
        'enabled': True,
        'from_name': 'TradeUp Rewards',
        'from_email': 'noreply@tradeup.io',
        'triggers': {
            'welcome': True,
            'trade_in_received': True,
            'trade_in_approved': True,
            'trade_in_rejected': True,
            'tier_upgrade': True,
            'tier_downgrade': True,
            'credit_issued': True,
            'credit_expiring': True,
            'monthly_credit': True,
            'referral_success': True,
        },
    }

    return jsonify(settings)


@email_bp.route('/settings', methods=['PUT'])
@require_shop_auth
def update_email_settings():
    """Update email notification settings."""
    tenant_id = request.tenant_id
    data = request.get_json()

    # TODO: Store in database
    # For now, just return success
    return jsonify({
        'success': True,
        'message': 'Email settings updated',
    })
