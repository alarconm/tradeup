"""
Customer lifecycle webhook handlers.
Handles customer creation, updates, and deletion for TradeUp rewards.
"""
import hmac
import hashlib
import base64
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import Tenant, Member


customer_lifecycle_bp = Blueprint('customer_lifecycle', __name__)


def verify_shopify_webhook(data: bytes, hmac_header: str, secret: str) -> bool:
    """Verify Shopify webhook HMAC signature."""
    if not secret or not hmac_header:
        return False
    computed_hmac = base64.b64encode(
        hmac.new(secret.encode('utf-8'), data, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(computed_hmac, hmac_header)


def get_tenant_from_domain(shop_domain: str) -> Tenant:
    """Get tenant from Shopify shop domain."""
    return Tenant.query.filter_by(shopify_domain=shop_domain).first()


@customer_lifecycle_bp.route('/customers/create', methods=['POST'])
def handle_customer_created():
    """
    Handle CUSTOMERS_CREATE webhook.

    Auto-enrolls new customers in the rewards program at the default tier.
    Triggered when a new customer account is created in Shopify.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        current_app.logger.warning(f'Unknown shop: {shop_domain}')
        return jsonify({'error': 'Unknown shop'}), 404

    # Verify webhook in production
    if current_app.config.get('ENV') != 'development':
        hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
        if not verify_shopify_webhook(request.data, hmac_header, tenant.webhook_secret):
            return jsonify({'error': 'Invalid signature'}), 401

    try:
        customer_data = request.json
        shopify_customer_id = str(customer_data.get('id'))
        email = customer_data.get('email', '')
        first_name = customer_data.get('first_name', '')
        last_name = customer_data.get('last_name', '')
        phone = customer_data.get('phone', '')

        # Check if member already exists
        existing = Member.query.filter_by(
            tenant_id=tenant.id,
            shopify_customer_id=shopify_customer_id
        ).first()

        if existing:
            return jsonify({
                'success': True,
                'message': 'Member already exists',
                'member_id': existing.id
            })

        # Also check by email
        existing_email = Member.query.filter_by(
            tenant_id=tenant.id,
            email=email
        ).first()

        if existing_email:
            # Link Shopify ID to existing member
            existing_email.shopify_customer_id = shopify_customer_id
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Linked Shopify ID to existing member',
                'member_id': existing_email.id
            })

        # Create new member with default tier
        from ..models import MembershipTier
        default_tier = MembershipTier.query.filter_by(
            tenant_id=tenant.id,
            is_default=True
        ).first()

        # Generate member number
        member_count = Member.query.filter_by(tenant_id=tenant.id).count()
        member_number = f"TU{member_count + 1:04d}"

        new_member = Member(
            tenant_id=tenant.id,
            member_number=member_number,
            shopify_customer_id=shopify_customer_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            tier_id=default_tier.id if default_tier else None,
            store_credit_balance=0,
            points_balance=0,
            lifetime_points=0,
            status='active',
            enrolled_at=datetime.utcnow(),
            enrolled_source='shopify_webhook'
        )

        db.session.add(new_member)
        db.session.commit()

        current_app.logger.info(f'Auto-enrolled new member: {member_number} ({email})')

        return jsonify({
            'success': True,
            'member_id': new_member.id,
            'member_number': member_number,
            'tier': default_tier.name if default_tier else None
        })

    except Exception as e:
        current_app.logger.error(f'Error processing customer create webhook: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@customer_lifecycle_bp.route('/customers/update', methods=['POST'])
def handle_customer_updated():
    """
    Handle CUSTOMERS_UPDATE webhook.

    Syncs customer data changes (email, name, phone) to member records.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    # Verify webhook in production
    if current_app.config.get('ENV') != 'development':
        hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
        if not verify_shopify_webhook(request.data, hmac_header, tenant.webhook_secret):
            return jsonify({'error': 'Invalid signature'}), 401

    try:
        customer_data = request.json
        shopify_customer_id = str(customer_data.get('id'))

        member = Member.query.filter_by(
            tenant_id=tenant.id,
            shopify_customer_id=shopify_customer_id
        ).first()

        if not member:
            # Customer not enrolled in rewards
            return jsonify({
                'success': True,
                'message': 'Customer not enrolled in rewards'
            })

        # Update member info
        member.email = customer_data.get('email', member.email)
        member.first_name = customer_data.get('first_name', member.first_name)
        member.last_name = customer_data.get('last_name', member.last_name)
        member.phone = customer_data.get('phone', member.phone)
        member.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'member_id': member.id,
            'updated_fields': ['email', 'first_name', 'last_name', 'phone']
        })

    except Exception as e:
        current_app.logger.error(f'Error processing customer update webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500


@customer_lifecycle_bp.route('/customers/delete', methods=['POST'])
def handle_customer_deleted():
    """
    Handle CUSTOMERS_DELETE webhook.

    Marks member as inactive but retains data for reporting.
    Actual data deletion happens via GDPR redact webhooks.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    try:
        customer_data = request.json
        shopify_customer_id = str(customer_data.get('id'))

        member = Member.query.filter_by(
            tenant_id=tenant.id,
            shopify_customer_id=shopify_customer_id
        ).first()

        if member:
            member.status = 'deleted'
            member.deleted_at = datetime.utcnow()
            db.session.commit()

            return jsonify({
                'success': True,
                'member_id': member.id,
                'action': 'marked_deleted'
            })

        return jsonify({
            'success': True,
            'message': 'Customer not found in rewards'
        })

    except Exception as e:
        current_app.logger.error(f'Error processing customer delete webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500
