"""
Order lifecycle webhook handlers.
Handles order events for TradeUp rewards and points.
"""
import hmac
import hashlib
import base64
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import Tenant, Member


order_lifecycle_bp = Blueprint('order_lifecycle', __name__)


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


@order_lifecycle_bp.route('/orders/create', methods=['POST'])
def handle_order_created():
    """
    Handle ORDERS_CREATE webhook.

    Awards points to members when they place orders.
    Points are calculated based on order subtotal and tenant settings.
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
        order_data = request.json
        order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number')
        customer_data = order_data.get('customer', {})
        shopify_customer_id = str(customer_data.get('id', '')) if customer_data else None
        subtotal = Decimal(str(order_data.get('subtotal_price', 0)))

        if not shopify_customer_id:
            # Guest checkout - no points
            return jsonify({
                'success': True,
                'message': 'Guest checkout - no points awarded'
            })

        # Find member
        member = Member.query.filter_by(
            tenant_id=tenant.id,
            shopify_customer_id=shopify_customer_id
        ).first()

        if not member:
            return jsonify({
                'success': True,
                'message': 'Customer not enrolled in rewards'
            })

        if member.status != 'active':
            return jsonify({
                'success': True,
                'message': 'Member account not active'
            })

        # Calculate points based on subtotal
        # Default: 1 point per dollar spent
        points_per_dollar = tenant.settings.get('points_per_dollar', 1) if hasattr(tenant, 'settings') else 1
        points_earned = int(subtotal * points_per_dollar)

        # Apply tier multiplier if applicable
        if member.tier and hasattr(member.tier, 'points_multiplier'):
            points_earned = int(points_earned * member.tier.points_multiplier)

        if points_earned > 0:
            # Record points transaction
            from ..models import PointsTransaction
            transaction = PointsTransaction(
                tenant_id=tenant.id,
                member_id=member.id,
                points=points_earned,
                transaction_type='earn',
                source='order',
                reference_id=order_id,
                reference_type='shopify_order',
                description=f'Points from order #{order_number}',
                created_at=datetime.utcnow()
            )
            db.session.add(transaction)

            # Update member balances
            member.points_balance = (member.points_balance or 0) + points_earned
            member.lifetime_points = (member.lifetime_points or 0) + points_earned
            member.last_activity_at = datetime.utcnow()

            db.session.commit()

            current_app.logger.info(
                f'Awarded {points_earned} points to {member.member_number} for order #{order_number}'
            )

            return jsonify({
                'success': True,
                'member_id': member.id,
                'points_earned': points_earned,
                'new_balance': member.points_balance,
                'order_id': order_id
            })

        return jsonify({
            'success': True,
            'message': 'No points earned (order subtotal too low)',
            'order_id': order_id
        })

    except Exception as e:
        current_app.logger.error(f'Error processing order create webhook: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@order_lifecycle_bp.route('/orders/cancelled', methods=['POST'])
def handle_order_cancelled():
    """
    Handle ORDERS_CANCELLED webhook.

    Reverses points awarded for cancelled orders.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    try:
        order_data = request.json
        order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number')

        # Find original points transaction
        from ..models import PointsTransaction
        original_transaction = PointsTransaction.query.filter_by(
            tenant_id=tenant.id,
            reference_id=order_id,
            transaction_type='earn'
        ).first()

        if not original_transaction:
            return jsonify({
                'success': True,
                'message': 'No points to reverse'
            })

        member = original_transaction.member

        # Create reversal transaction
        reversal = PointsTransaction(
            tenant_id=tenant.id,
            member_id=member.id,
            points=-original_transaction.points,
            transaction_type='adjustment',
            source='order_cancelled',
            reference_id=order_id,
            reference_type='shopify_order',
            description=f'Points reversed - order #{order_number} cancelled',
            related_transaction_id=original_transaction.id,
            created_at=datetime.utcnow()
        )
        db.session.add(reversal)

        # Update member balance (don't reduce lifetime)
        member.points_balance = max(0, (member.points_balance or 0) - original_transaction.points)

        # Mark original as reversed
        original_transaction.reversed_at = datetime.utcnow()
        original_transaction.reversed_reason = 'order_cancelled'

        db.session.commit()

        return jsonify({
            'success': True,
            'points_reversed': original_transaction.points,
            'new_balance': member.points_balance,
            'order_id': order_id
        })

    except Exception as e:
        current_app.logger.error(f'Error processing order cancelled webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500


@order_lifecycle_bp.route('/orders/fulfilled', methods=['POST'])
def handle_order_fulfilled():
    """
    Handle ORDERS_FULFILLED webhook.

    Optional: Some rewards programs only award points after fulfillment.
    This is a placeholder for that workflow if enabled.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    # Check if tenant requires fulfillment for points
    award_on_fulfillment = tenant.settings.get('award_points_on_fulfillment', False) if hasattr(tenant, 'settings') else False

    if not award_on_fulfillment:
        return jsonify({
            'success': True,
            'message': 'Points awarded at order creation, not fulfillment'
        })

    # If tenant requires fulfillment, process points here
    # (Similar logic to orders/create)
    try:
        order_data = request.json
        order_id = str(order_data.get('id'))

        # Implementation would be similar to orders/create
        # For now, just acknowledge
        return jsonify({
            'success': True,
            'message': 'Fulfillment tracked',
            'order_id': order_id
        })

    except Exception as e:
        current_app.logger.error(f'Error processing order fulfilled webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500
