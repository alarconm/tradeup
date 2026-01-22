"""
Email Notification API for TradeUp.

Provides endpoints for managing email templates and sending notifications.
"""
from flask import Blueprint, request, jsonify
from ..services.email_service import email_service
from ..middleware.shopify_auth import require_shopify_auth
from ..models.tenant import Tenant

email_bp = Blueprint('email', __name__)


@email_bp.route('/templates', methods=['GET'])
@require_shopify_auth
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
@require_shopify_auth
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


@email_bp.route('/templates/<template_id>', methods=['PUT'])
@require_shopify_auth
def update_template(template_id):
    """
    Update/customize an email template.

    Request body:
    {
        "name": "Custom Welcome",
        "subject": "Welcome to {{program_name}}!",
        "body": "Hi {{member_name}}, ..."
    }
    """
    tenant_id = request.tenant_id
    data = request.get_json()

    if not data.get('subject') or not data.get('body'):
        return jsonify({'error': 'subject and body are required'}), 400

    result = email_service.save_custom_template(
        template_key=template_id,
        tenant_id=tenant_id,
        name=data.get('name', template_id),
        subject=data['subject'],
        body=data['body'],
        category=data.get('category')
    )

    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400


@email_bp.route('/templates/<template_id>/reset', methods=['POST'])
@require_shopify_auth
def reset_template(template_id):
    """Reset a customized template back to the default."""
    tenant_id = request.tenant_id

    result = email_service.reset_template_to_default(template_id, tenant_id)

    if result.get('success'):
        # Return the default template
        default_template = email_service.DEFAULT_TEMPLATES.get(template_id)
        if default_template:
            return jsonify({
                'success': True,
                'message': result.get('message'),
                'template': {
                    'id': template_id,
                    **default_template,
                    'is_custom': False,
                }
            })
        return jsonify(result)
    else:
        return jsonify(result), 400


@email_bp.route('/preview', methods=['POST'])
@require_shopify_auth
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
        'shop_url': custom_data.get('shop_url', f'https://{tenant.shop_domain}' if tenant else 'https://example.com'),
        'tier_name': custom_data.get('tier_name', 'Gold'),
        'tier_benefits': custom_data.get('tier_benefits', '• 5% trade-in bonus\n• $10 monthly credit\n• Priority processing'),
        'trade_in_id': custom_data.get('trade_in_id', '12345'),
        'item_count': custom_data.get('item_count', '3'),
        'estimated_value': custom_data.get('estimated_value', '$45.00'),
        'credit_amount': custom_data.get('credit_amount', '$50.00'),
        'tier_bonus': custom_data.get('tier_bonus', '5'),
        'total_credit': custom_data.get('total_credit', '$52.50'),
        'status': custom_data.get('status', 'Under Review'),
        'reason': custom_data.get('reason', 'Items require additional verification'),
        'old_tier': custom_data.get('old_tier', 'Silver'),
        'new_tier': custom_data.get('new_tier', 'Gold'),
        'amount': custom_data.get('amount', '$25.00'),
        'current_balance': custom_data.get('current_balance', '750'),
        'expiration_date': custom_data.get('expiration_date', 'March 31, 2026'),
        'reward_amount': custom_data.get('reward_amount', '$10.00'),
        'referred_name': custom_data.get('referred_name', 'Jane Smith'),
        'referred_reward': custom_data.get('referred_reward', '$5.00'),
        'referral_code': custom_data.get('referral_code', 'JOHN2025'),
        # Nudge-specific sample data
        'expiring_points': custom_data.get('expiring_points', '500'),
        'days_until': custom_data.get('days_until', '7'),
        'days_until_critical': custom_data.get('days_until_critical', True if custom_data.get('days_until', 7) <= 7 else False),
        'rewards_available': custom_data.get('rewards_available', True),
        'rewards_list': custom_data.get('rewards_list', ''),
        'current_tier': custom_data.get('current_tier', 'Silver'),
        'next_tier': custom_data.get('next_tier', 'Gold'),
        'progress_percent': custom_data.get('progress_percent', '92'),
        'current_points': custom_data.get('current_points', '920'),
        'points_needed': custom_data.get('points_needed', '80'),
        'next_tier_threshold': custom_data.get('next_tier_threshold', '1000'),
        'next_tier_benefits': custom_data.get('next_tier_benefits', '<li>10% bonus on trade-ins</li><li>$15 monthly credit</li><li>Priority processing</li>'),
        'days_inactive': custom_data.get('days_inactive', '45'),
        'points_balance': custom_data.get('points_balance', '750'),
        'incentive_text': custom_data.get('incentive_text', '50 bonus points'),
        'missed_opportunities': custom_data.get('missed_opportunities', ''),
        'days_since_last': custom_data.get('days_since_last', '90'),
        'has_tier_bonus': custom_data.get('has_tier_bonus', True),
        'credit_rates': custom_data.get('credit_rates', ''),
    }

    # Merge custom data
    sample_data.update(custom_data)

    rendered = email_service.render_template(template, sample_data)

    # Check if HTML template exists for this template type
    html_body = email_service.render_html_template(template_id, tenant_id, sample_data)
    if not html_body:
        html_body = email_service._markdown_to_html(rendered['body'])

    return jsonify({
        'template_id': template_id,
        'template_name': template['name'],
        'subject': rendered['subject'],
        'body': rendered['body'],
        'html_body': html_body,
        'has_html_template': template_id in email_service.HTML_TEMPLATE_FILES,
    })


@email_bp.route('/send-test', methods=['POST'])
@require_shopify_auth
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
@require_shopify_auth
def get_email_settings():
    """Get email notification settings for the tenant from database."""
    from ..extensions import db

    tenant_id = request.tenant_id
    tenant = Tenant.query.get(tenant_id)

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Default settings
    default_settings = {
        'enabled': True,
        'from_name': tenant.shop_name or 'TradeUp Rewards',
        'from_email': 'noreply@tradeup.io',
        'reply_to': '',
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
            # Nudge email triggers
            'points_expiring': True,
            'tier_progress': True,
            'inactive_reengagement': True,
            'trade_in_reminder': True,
        },
    }

    # Get stored settings from tenant.settings JSON
    tenant_settings = tenant.settings or {}
    email_settings = tenant_settings.get('email', {})

    # Merge with defaults (stored settings override defaults)
    settings = {**default_settings}
    if email_settings:
        settings['enabled'] = email_settings.get('enabled', default_settings['enabled'])
        settings['from_name'] = email_settings.get('from_name', default_settings['from_name'])
        settings['from_email'] = email_settings.get('from_email', default_settings['from_email'])
        settings['reply_to'] = email_settings.get('reply_to', default_settings['reply_to'])
        # Merge triggers
        stored_triggers = email_settings.get('triggers', {})
        settings['triggers'] = {**default_settings['triggers'], **stored_triggers}

    return jsonify(settings)


@email_bp.route('/settings', methods=['PUT'])
@require_shopify_auth
def update_email_settings():
    """Update email notification settings and persist to database."""
    from ..extensions import db

    tenant_id = request.tenant_id
    data = request.get_json()

    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Initialize settings if not exists
    if tenant.settings is None:
        tenant.settings = {}

    # Update email settings in tenant.settings JSON
    email_settings = {
        'enabled': data.get('enabled', True),
        'from_name': data.get('from_name', tenant.shop_name or 'TradeUp Rewards'),
        'from_email': data.get('from_email', 'noreply@tradeup.io'),
        'reply_to': data.get('reply_to', ''),
        'triggers': data.get('triggers', {}),
    }

    # Store in tenant settings
    tenant.settings = {**tenant.settings, 'email': email_settings}
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Email settings updated',
        'settings': email_settings,
    })
