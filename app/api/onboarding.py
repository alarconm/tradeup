"""
TradeUp Onboarding API endpoints.

Provides simplified setup flow to maximize trial-to-paid conversion.
Target: Complete setup in under 5 minutes.
"""
from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import Tenant, MembershipTier

onboarding_bp = Blueprint('onboarding', __name__)


def get_tenant_from_request():
    """Get tenant from request headers."""
    shop = (request.headers.get('X-Shop-Domain') or
            request.headers.get('X-Shopify-Shop-Domain') or
            request.args.get('shop'))
    if not shop:
        return None
    # Normalize shop domain
    shop = shop.replace('https://', '').replace('http://', '').rstrip('/')
    return Tenant.query.filter_by(shopify_domain=shop).first()


@onboarding_bp.route('/status', methods=['GET'])
def get_onboarding_status():
    """
    Get current onboarding status.

    Returns:
        - setup_complete: Boolean indicating if setup is complete
        - current_step: Current step in onboarding (1-4)
        - steps: List of step statuses
    """
    tenant = get_tenant_from_request()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    from ..services.onboarding import OnboardingService
    service = OnboardingService(tenant.id)

    # Check each onboarding step
    status = service.get_onboarding_status()

    # Build detailed steps
    has_tiers = status.get('has_tiers', False)
    onboarding_complete = status.get('onboarding_complete', False)
    store_credit_enabled = status.get('store_credit_enabled', False)

    steps = [
        {
            'id': 1,
            'name': 'App Installed',
            'description': 'TradeUp is installed and connected to your store',
            'status': 'complete',  # Always complete if we got here
            'action': None
        },
        {
            'id': 2,
            'name': 'Store Credit Enabled',
            'description': 'Shopify native store credit is set up',
            'status': 'complete' if store_credit_enabled else 'pending',
            'action': 'check_store_credit' if not store_credit_enabled else None
        },
        {
            'id': 3,
            'name': 'Tiers Configured',
            'description': 'Membership tiers are set up for your store',
            'status': 'complete' if has_tiers else 'pending',
            'action': 'setup_tiers' if not has_tiers else None
        },
        {
            'id': 4,
            'name': 'Ready to Go',
            'description': 'Your loyalty program is live and accepting members',
            'status': 'complete' if onboarding_complete else 'pending',
            'action': 'go_live' if store_credit_enabled and has_tiers and not onboarding_complete else None
        }
    ]

    # Determine current step
    current_step = 1
    for step in steps:
        if step['status'] != 'complete':
            current_step = step['id']
            break
        current_step = step['id'] + 1

    return jsonify({
        'setup_complete': onboarding_complete,
        'current_step': min(current_step, 4),
        'steps': steps,
        'subscription_plan': status.get('subscription_plan', 'free'),
        'subscription_active': status.get('subscription_active', False)
    })


@onboarding_bp.route('/store-credit-check', methods=['GET'])
def check_store_credit():
    """
    Check if Shopify native store credit is enabled.

    Returns:
        - enabled: Boolean
        - status: 'ready', 'not_enabled', or 'error'
        - message: User-friendly message
        - instructions: List of steps to enable (if not enabled)
        - settings_url: Direct link to Shopify payment settings
    """
    from sqlalchemy.orm.attributes import flag_modified

    tenant = get_tenant_from_request()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    from ..services.onboarding import OnboardingService
    service = OnboardingService(tenant.id)

    result = service.check_store_credit_enabled()

    # Save store credit status in tenant settings so we can track progress
    if tenant.settings is None:
        tenant.settings = {}
    tenant.settings['store_credit_enabled'] = result.get('enabled', False)
    flag_modified(tenant, 'settings')
    db.session.commit()

    return jsonify(result)


@onboarding_bp.route('/templates', methods=['GET'])
def get_templates():
    """
    Get available tier templates.

    Templates are pre-configured tier sets for different business types.
    """
    tenant = get_tenant_from_request()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    from ..services.onboarding import OnboardingService
    service = OnboardingService(tenant.id)

    templates = service.get_available_templates()
    return jsonify({
        'templates': templates,
        'subscription_plan': tenant.subscription_plan,
        'can_upgrade': tenant.subscription_plan == 'free'
    })


@onboarding_bp.route('/templates/<template_key>/preview', methods=['GET'])
def preview_template(template_key: str):
    """
    Preview a tier template before applying.

    Shows what the tier structure will look like.
    """
    from ..services.onboarding import get_template_preview

    preview = get_template_preview(template_key)
    if not preview:
        return jsonify({'error': 'Template not found'}), 404

    return jsonify(preview)


@onboarding_bp.route('/templates/<template_key>/apply', methods=['POST'])
def apply_template(template_key: str):
    """
    Apply a tier template to the tenant.

    This will:
    1. Delete any existing tiers
    2. Create tiers from the template
    3. Mark onboarding as complete
    """
    tenant = get_tenant_from_request()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    from ..services.onboarding import OnboardingService
    service = OnboardingService(tenant.id)

    try:
        result = service.apply_template(template_key)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to apply template: {str(e)}'}), 500


@onboarding_bp.route('/complete', methods=['POST'])
def complete_onboarding():
    """
    Mark onboarding as complete.

    Called when merchant finishes setup (even if they skipped templates).
    """
    from sqlalchemy.orm.attributes import flag_modified

    tenant = get_tenant_from_request()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Update tenant settings
    if tenant.settings is None:
        tenant.settings = {}
    tenant.settings['onboarding_complete'] = True

    # Explicitly mark the JSON column as modified
    flag_modified(tenant, 'settings')
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Onboarding complete! Your loyalty program is now live.'
    })


@onboarding_bp.route('/skip', methods=['POST'])
def skip_onboarding():
    """
    Skip onboarding wizard.

    Allows experienced users to configure manually.
    """
    from sqlalchemy.orm.attributes import flag_modified

    tenant = get_tenant_from_request()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Mark as skipped but not complete
    if tenant.settings is None:
        tenant.settings = {}
    tenant.settings['onboarding_skipped'] = True

    # Explicitly mark the JSON column as modified
    flag_modified(tenant, 'settings')
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Onboarding skipped. You can configure everything manually in Settings.'
    })
