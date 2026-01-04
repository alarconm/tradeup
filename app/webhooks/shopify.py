"""
Shopify webhook handlers.
Processes order/paid and product/create webhooks.
"""
import hmac
import hashlib
import base64
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import Tenant, TradeInItem, Member
from ..services.trade_in_service import TradeInService
from ..services.bonus_processor import BonusProcessor

webhooks_bp = Blueprint('webhooks', __name__)


def verify_shopify_webhook(data: bytes, hmac_header: str, secret: str) -> bool:
    """
    Verify Shopify webhook HMAC signature.

    Args:
        data: Raw request body
        hmac_header: X-Shopify-Hmac-SHA256 header
        secret: Webhook secret

    Returns:
        True if valid, False otherwise
    """
    if not secret or not hmac_header:
        return False

    computed_hmac = base64.b64encode(
        hmac.new(
            secret.encode('utf-8'),
            data,
            hashlib.sha256
        ).digest()
    ).decode()

    return hmac.compare_digest(computed_hmac, hmac_header)


def get_tenant_from_request() -> Tenant:
    """Get tenant from webhook request headers or path."""
    # Try X-Tenant-Slug header first
    tenant_slug = request.headers.get('X-Tenant-Slug')

    # Try path parameter
    if not tenant_slug:
        tenant_slug = request.view_args.get('tenant_slug')

    # Default to ORB for MVP
    if not tenant_slug:
        tenant_slug = 'orb-sports-cards'

    tenant = Tenant.query.filter_by(shop_slug=tenant_slug).first()
    return tenant


@webhooks_bp.route('/shopify/<tenant_slug>/order-paid', methods=['POST'])
def handle_order_paid(tenant_slug):
    """
    Handle Shopify orders/paid webhook.
    Detects quick flip sales and triggers bonus calculation.

    Flow:
    1. Verify webhook signature
    2. Extract line items from order
    3. Match products to trade-in items by Shopify product ID
    4. Calculate days to sell and bonus eligibility
    5. Queue bonus processing
    """
    tenant = Tenant.query.filter_by(shop_slug=tenant_slug).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Verify webhook (skip in development)
    if current_app.config.get('ENV') != 'development':
        hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
        if not verify_shopify_webhook(request.data, hmac_header, tenant.webhook_secret):
            return jsonify({'error': 'Invalid signature'}), 401

    try:
        order_data = request.json
        order_id = order_data.get('id')
        line_items = order_data.get('line_items', [])

        current_app.logger.info(f'Processing order {order_id} for {tenant_slug}')

        processed_items = []
        bonus_eligible = []

        for line_item in line_items:
            product_id = str(line_item.get('product_id'))
            variant_id = str(line_item.get('variant_id'))
            price = Decimal(str(line_item.get('price', 0)))

            # Find matching trade-in item
            trade_in_item = TradeInItem.query.filter_by(
                shopify_product_id=product_id
            ).first()

            if not trade_in_item:
                # Try variant ID
                trade_in_item = TradeInItem.query.filter(
                    TradeInItem.shopify_product_id.like(f'%{variant_id}%')
                ).first()

            if not trade_in_item:
                continue

            # Verify this belongs to the tenant
            member = trade_in_item.batch.member
            if member.tenant_id != tenant.id:
                continue

            # Record the sale
            trade_in_item.sold_date = datetime.utcnow()
            trade_in_item.sold_price = price
            trade_in_item.shopify_order_id = str(order_id)

            # Calculate days to sell
            if trade_in_item.listed_date:
                trade_in_item.days_to_sell = trade_in_item.calculate_days_to_sell()

                # Check bonus eligibility
                if member.tier:
                    quick_flip_days = member.tier.quick_flip_days
                    if trade_in_item.days_to_sell <= quick_flip_days:
                        trade_in_item.eligible_for_bonus = True
                        bonus_eligible.append({
                            'item_id': trade_in_item.id,
                            'product_title': trade_in_item.product_title,
                            'days_to_sell': trade_in_item.days_to_sell,
                            'sold_price': float(price)
                        })

            processed_items.append(trade_in_item.id)

        db.session.commit()

        # Process bonuses if any eligible
        if bonus_eligible:
            processor = BonusProcessor(tenant.id)
            # Process immediately or queue for background job
            # For MVP, process immediately
            processor.process_pending_bonuses(created_by='webhook')

        return jsonify({
            'success': True,
            'order_id': order_id,
            'processed_items': len(processed_items),
            'bonus_eligible': len(bonus_eligible)
        })

    except Exception as e:
        current_app.logger.error(f'Error processing order webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/shopify/<tenant_slug>/product-created', methods=['POST'])
def handle_product_created(tenant_slug):
    """
    Handle Shopify products/create webhook.
    Captures listing date and updates trade-in items.

    This webhook is triggered when items are listed in Shopify.
    We look for the member tag (QF####) to link back to the trade-in item.
    """
    tenant = Tenant.query.filter_by(shop_slug=tenant_slug).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Verify webhook (skip in development)
    if current_app.config.get('ENV') != 'development':
        hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
        if not verify_shopify_webhook(request.data, hmac_header, tenant.webhook_secret):
            return jsonify({'error': 'Invalid signature'}), 401

    try:
        product_data = request.json
        product_id = str(product_data.get('id'))
        title = product_data.get('title', '')
        tags = product_data.get('tags', '')

        current_app.logger.info(f'Product created: {product_id} - {title}')

        # Parse tags to find member number (QF####)
        member_number = None
        tag_list = [t.strip() for t in tags.split(',')]
        for tag in tag_list:
            if tag.upper().startswith('QF'):
                member_number = tag.upper()
                break

        if not member_number:
            # No member tag, not a quick flip item
            return jsonify({'success': True, 'message': 'No member tag found'})

        # Find the member
        member = Member.query.filter_by(
            tenant_id=tenant.id,
            member_number=member_number
        ).first()

        if not member:
            current_app.logger.warning(f'Member not found: {member_number}')
            return jsonify({'success': True, 'message': f'Member {member_number} not found'})

        # Get the most recent pending batch for this member
        # (Items are typically listed in batch order)
        from ..models import TradeInBatch, TradeInItem

        # Find unlisted items in member's batches
        unlisted_item = (
            TradeInItem.query
            .join(TradeInBatch)
            .filter(
                TradeInBatch.member_id == member.id,
                TradeInItem.listed_date.is_(None)
            )
            .order_by(TradeInItem.created_at)
            .first()
        )

        if unlisted_item:
            # Get price from first variant
            variants = product_data.get('variants', [])
            listing_price = Decimal(variants[0].get('price', 0)) if variants else None

            unlisted_item.shopify_product_id = product_id
            unlisted_item.product_title = title
            unlisted_item.listing_price = listing_price
            unlisted_item.listed_date = datetime.utcnow()

            # Update batch status if all items listed
            batch = unlisted_item.batch
            remaining = TradeInItem.query.filter_by(
                batch_id=batch.id,
                listed_date=None
            ).count()

            if remaining == 0:
                batch.status = 'listed'

            db.session.commit()

            return jsonify({
                'success': True,
                'linked_item_id': unlisted_item.id,
                'member_number': member_number
            })

        return jsonify({
            'success': True,
            'message': f'No unlisted items for member {member_number}'
        })

    except Exception as e:
        current_app.logger.error(f'Error processing product webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/shopify/<tenant_slug>/order-refunded', methods=['POST'])
def handle_order_refunded(tenant_slug):
    """
    Handle Shopify refunds/create webhook.
    Reverses bonuses for refunded items.
    """
    tenant = Tenant.query.filter_by(shop_slug=tenant_slug).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    try:
        refund_data = request.json
        order_id = str(refund_data.get('order_id'))

        # Find trade-in items linked to this order
        items = TradeInItem.query.filter_by(shopify_order_id=order_id).all()

        reversed_count = 0
        processor = BonusProcessor(tenant.id)

        for item in items:
            if item.bonus_status == 'issued':
                # Find the bonus transaction
                from ..models import BonusTransaction
                transaction = BonusTransaction.query.filter_by(
                    trade_in_item_id=item.id,
                    transaction_type='credit'
                ).first()

                if transaction:
                    processor.reverse_bonus(
                        transaction_id=transaction.id,
                        reason='Order refunded',
                        created_by='webhook'
                    )
                    reversed_count += 1

        return jsonify({
            'success': True,
            'order_id': order_id,
            'bonuses_reversed': reversed_count
        })

    except Exception as e:
        current_app.logger.error(f'Error processing refund webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500
