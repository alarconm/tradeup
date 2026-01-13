"""
App lifecycle webhook handlers.
Handles app installation, uninstallation, and shop events.
"""
import hmac
import hashlib
import base64
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import Tenant


app_lifecycle_bp = Blueprint('app_lifecycle', __name__)


def verify_shopify_webhook(data: bytes, hmac_header: str, secret: str) -> bool:
    """Verify Shopify webhook HMAC signature."""
    if not secret or not hmac_header:
        return False
    computed_hmac = base64.b64encode(
        hmac.new(secret.encode('utf-8'), data, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(computed_hmac, hmac_header)


@app_lifecycle_bp.route('/app/uninstalled', methods=['POST'])
def handle_app_uninstalled():
    """
    Handle APP_UNINSTALLED webhook.

    Required by Shopify for all apps.
    Cleans up tenant data and marks tenant as inactive.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')

    current_app.logger.info(f'App uninstalled by {shop_domain}')

    try:
        tenant = Tenant.query.filter_by(shopify_domain=shop_domain).first()

        if not tenant:
            return jsonify({'success': True, 'message': 'Tenant not found'})

        # Verify webhook signature
        if current_app.config.get('ENV') != 'development':
            hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
            # For uninstall, we might use SHOPIFY_API_SECRET as webhook_secret could be cleared
            secret = tenant.webhook_secret or current_app.config.get('SHOPIFY_API_SECRET')
            if not verify_shopify_webhook(request.data, hmac_header, secret):
                return jsonify({'error': 'Invalid signature'}), 401

        # Mark tenant as inactive
        tenant.status = 'uninstalled'
        tenant.uninstalled_at = datetime.utcnow()

        # Clear sensitive data (access tokens)
        tenant.shopify_access_token = None
        tenant.webhook_secret = None

        # Keep member data for potential re-install
        # but mark subscription as cancelled
        if hasattr(tenant, 'subscription_status'):
            tenant.subscription_status = 'cancelled'

        db.session.commit()

        current_app.logger.info(f'Tenant {shop_domain} marked as uninstalled')

        return jsonify({
            'success': True,
            'shop': shop_domain,
            'action': 'marked_uninstalled'
        })

    except Exception as e:
        current_app.logger.error(f'Error processing app uninstalled webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app_lifecycle_bp.route('/shop/update', methods=['POST'])
def handle_shop_updated():
    """
    Handle SHOP_UPDATE webhook.

    Updates tenant info when shop details change
    (e.g., shop name, domain, currency, timezone).
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')

    try:
        shop_data = request.json
        new_domain = shop_data.get('myshopify_domain', shop_domain)

        tenant = Tenant.query.filter_by(shopify_domain=shop_domain).first()

        if not tenant:
            # Try finding by new domain
            tenant = Tenant.query.filter_by(shopify_domain=new_domain).first()

        if not tenant:
            return jsonify({'success': True, 'message': 'Tenant not found'})

        # Verify webhook signature
        if current_app.config.get('ENV') != 'development':
            hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
            secret = tenant.webhook_secret or current_app.config.get('SHOPIFY_API_SECRET')
            if not verify_shopify_webhook(request.data, hmac_header, secret):
                return jsonify({'error': 'Invalid signature'}), 401

        # Update tenant info
        tenant.shop_name = shop_data.get('name', tenant.shop_name)
        tenant.shopify_domain = new_domain
        tenant.updated_at = datetime.utcnow()

        # Store currency and timezone in settings (JSON field)
        current_settings = tenant.settings or {}
        general_settings = current_settings.get('general', {})

        if 'currency' in shop_data:
            general_settings['currency'] = shop_data['currency']
        if 'iana_timezone' in shop_data:
            general_settings['timezone'] = shop_data['iana_timezone']

        current_settings['general'] = general_settings
        tenant.settings = current_settings

        db.session.commit()

        return jsonify({
            'success': True,
            'shop': new_domain,
            'updated_fields': ['shop_name', 'domain', 'currency', 'timezone']
        })

    except Exception as e:
        current_app.logger.error(f'Error processing shop update webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app_lifecycle_bp.route('/shop/redact', methods=['POST'])
def handle_shop_redact():
    """
    Handle SHOP_REDACT webhook.

    GDPR mandatory webhook.
    Called 48 hours after app uninstall to request full data deletion.
    Must delete all shop data permanently.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')

    current_app.logger.info(f'Shop redact request for {shop_domain}')

    # Verify webhook signature using API secret (tenant webhook_secret may be cleared after uninstall)
    if current_app.config.get('ENV') != 'development':
        hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
        secret = current_app.config.get('SHOPIFY_API_SECRET')
        if not verify_shopify_webhook(request.data, hmac_header, secret):
            return jsonify({'error': 'Invalid signature'}), 401

    try:
        tenant = Tenant.query.filter_by(shopify_domain=shop_domain).first()

        if not tenant:
            return jsonify({'success': True, 'message': 'No data to redact'})

        # Delete all tenant data
        from ..models import Member, TradeInBatch, TradeInItem, PointsTransaction, StoreCreditLedger

        tenant_id = tenant.id

        # Delete in order to respect foreign keys
        PointsTransaction.query.filter_by(tenant_id=tenant_id).delete()
        StoreCreditLedger.query.filter_by(tenant_id=tenant_id).delete()
        TradeInItem.query.filter(
            TradeInItem.batch_id.in_(
                db.session.query(TradeInBatch.id).filter_by(tenant_id=tenant_id)
            )
        ).delete(synchronize_session=False)
        TradeInBatch.query.filter_by(tenant_id=tenant_id).delete()
        Member.query.filter_by(tenant_id=tenant_id).delete()

        # Finally delete tenant
        db.session.delete(tenant)
        db.session.commit()

        current_app.logger.info(f'All data for {shop_domain} permanently deleted')

        return jsonify({
            'success': True,
            'shop': shop_domain,
            'action': 'data_permanently_deleted'
        })

    except Exception as e:
        current_app.logger.error(f'Error processing shop redact webhook: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app_lifecycle_bp.route('/customers/redact', methods=['POST'])
def handle_customer_redact():
    """
    Handle CUSTOMERS_REDACT webhook.

    GDPR mandatory webhook.
    Called when a customer requests data deletion.
    Must delete all customer data permanently.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')

    try:
        payload = request.json
        customer_data = payload.get('customer', {})
        shopify_customer_id = str(customer_data.get('id', ''))
        orders_to_redact = payload.get('orders_to_redact', [])

        tenant = Tenant.query.filter_by(shopify_domain=shop_domain).first()

        if not tenant:
            return jsonify({'success': True, 'message': 'Tenant not found'})

        # Verify webhook signature
        if current_app.config.get('ENV') != 'development':
            hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
            secret = tenant.webhook_secret or current_app.config.get('SHOPIFY_API_SECRET')
            if not verify_shopify_webhook(request.data, hmac_header, secret):
                return jsonify({'error': 'Invalid signature'}), 401

        from ..models import Member

        member = Member.query.filter_by(
            tenant_id=tenant.id,
            shopify_customer_id=shopify_customer_id
        ).first()

        if not member:
            return jsonify({
                'success': True,
                'message': 'Customer not found in rewards'
            })

        # Anonymize member data (keep for reporting but remove PII)
        member.email = f'redacted-{member.id}@redacted.invalid'
        member.first_name = 'REDACTED'
        member.last_name = 'REDACTED'
        member.phone = None
        member.shopify_customer_id = None
        member.status = 'redacted'
        member.redacted_at = datetime.utcnow()

        # Keep transaction history but anonymize references
        from ..models import PointsTransaction, StoreCreditLedger

        PointsTransaction.query.filter_by(member_id=member.id).update({
            'description': 'REDACTED'
        })
        StoreCreditLedger.query.filter_by(member_id=member.id).update({
            'description': 'REDACTED'
        })

        db.session.commit()

        current_app.logger.info(f'Customer {shopify_customer_id} data redacted for {shop_domain}')

        return jsonify({
            'success': True,
            'action': 'customer_data_redacted'
        })

    except Exception as e:
        current_app.logger.error(f'Error processing customer redact webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app_lifecycle_bp.route('/customers/data_request', methods=['POST'])
def handle_customer_data_request():
    """
    Handle CUSTOMERS_DATA_REQUEST webhook.

    GDPR mandatory webhook.
    Called when a customer requests their data.
    Must provide all stored data about the customer.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')

    try:
        payload = request.json
        customer_data = payload.get('customer', {})
        shopify_customer_id = str(customer_data.get('id', ''))
        data_request = payload.get('data_request', {})
        request_id = data_request.get('id')

        tenant = Tenant.query.filter_by(shopify_domain=shop_domain).first()

        if not tenant:
            return jsonify({
                'success': True,
                'message': 'No data stored for this shop'
            })

        # Verify webhook signature
        if current_app.config.get('ENV') != 'development':
            hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
            secret = tenant.webhook_secret or current_app.config.get('SHOPIFY_API_SECRET')
            if not verify_shopify_webhook(request.data, hmac_header, secret):
                return jsonify({'error': 'Invalid signature'}), 401

        from ..models import Member, PointsTransaction, StoreCreditLedger, TradeInBatch, TradeInItem

        member = Member.query.filter_by(
            tenant_id=tenant.id,
            shopify_customer_id=shopify_customer_id
        ).first()

        if not member:
            return jsonify({
                'success': True,
                'customer_data': None,
                'message': 'Customer not found in rewards program'
            })

        # Compile all customer data
        points_history = PointsTransaction.query.filter_by(member_id=member.id).all()
        credit_history = StoreCreditLedger.query.filter_by(member_id=member.id).all()
        trade_batches = TradeInBatch.query.filter_by(member_id=member.id).all()

        customer_export = {
            'member_info': {
                'member_number': member.member_number,
                'email': member.email,
                'name': member.name,
                'phone': member.phone,
                'tier': member.tier.name if member.tier else None,
                'total_trade_value': float(member.total_trade_value or 0),
                'total_trade_ins': member.total_trade_ins or 0,
                'created_at': member.created_at.isoformat() if member.created_at else None
            },
            'points_transactions': [
                {
                    'date': t.created_at.isoformat(),
                    'points': t.points,
                    'type': t.transaction_type,
                    'description': t.description
                } for t in points_history
            ],
            'credit_transactions': [
                {
                    'date': t.created_at.isoformat(),
                    'amount': float(t.amount),
                    'event_type': t.event_type,
                    'description': t.description
                } for t in credit_history
            ],
            'trade_in_batches': [
                {
                    'batch_reference': b.batch_reference,
                    'status': b.status,
                    'total_value': float(b.total_trade_value) if b.total_trade_value else 0,
                    'created_at': b.created_at.isoformat()
                } for b in trade_batches
            ]
        }

        # Note: In production, you'd send this data via email or store for pickup
        # For now, we log that the request was processed
        current_app.logger.info(
            f'Data request {request_id} processed for customer {shopify_customer_id}'
        )

        return jsonify({
            'success': True,
            'request_id': request_id,
            'data_compiled': True,
            'message': 'Customer data compiled and ready for export'
        })

    except Exception as e:
        current_app.logger.error(f'Error processing customer data request: {str(e)}')
        return jsonify({'error': str(e)}), 500
