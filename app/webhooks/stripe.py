"""
Stripe webhook endpoint.
Handles payment events from Stripe.
"""
import os
from flask import Blueprint, request, jsonify
from ..services.stripe_service import StripeService, StripeWebhookHandler
from ..models import Tenant

stripe_webhook_bp = Blueprint('stripe_webhook', __name__)


@stripe_webhook_bp.route('', methods=['POST'])
def handle_stripe_webhook():
    """
    Handle incoming Stripe webhook events.

    Stripe sends events for:
    - checkout.session.completed (new subscription)
    - invoice.paid (renewal)
    - invoice.payment_failed
    - customer.subscription.updated (tier change, etc)
    - customer.subscription.deleted (cancellation)
    """
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    if not webhook_secret:
        return jsonify({'error': 'Webhook secret not configured'}), 500

    if not sig_header:
        return jsonify({'error': 'Missing Stripe-Signature header'}), 400

    # Verify and construct the event
    try:
        event = StripeService.construct_webhook_event(
            payload, sig_header, webhook_secret
        )
    except Exception as e:
        return jsonify({'error': f'Webhook signature verification failed: {str(e)}'}), 400

    # Extract tenant_id from event metadata
    event_data = event['data']['object']
    metadata = event_data.get('metadata', {})

    # Try to get tenant_id from different locations
    tenant_id = None

    # Check in direct metadata
    if 'tenant_id' in metadata:
        tenant_id = int(metadata['tenant_id'])

    # Check in subscription metadata (for invoice events)
    elif 'subscription' in event_data:
        try:
            import stripe
            stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
            subscription = stripe.Subscription.retrieve(event_data['subscription'])
            tenant_id = int(subscription.metadata.get('tenant_id', 1))
        except Exception:
            tenant_id = 1  # Default to tenant 1

    # Default fallback
    if not tenant_id:
        tenant_id = 1

    # Process the webhook
    handler = StripeWebhookHandler(tenant_id)
    result = handler.handle_event(event)

    # Log the result
    print(f"[Stripe Webhook] {event['type']}: {result}")

    return jsonify(result)


@stripe_webhook_bp.route('/test', methods=['GET'])
def test_webhook():
    """Test endpoint to verify webhook route is accessible."""
    return jsonify({
        'status': 'ok',
        'message': 'Stripe webhook endpoint is accessible',
        'webhook_secret_configured': bool(os.getenv('STRIPE_WEBHOOK_SECRET'))
    })
