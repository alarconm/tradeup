"""
Support Review API Endpoints

API endpoints for post-support review email prompts.
Handles ticket resolution webhooks, email tracking, and statistics.

Story: RC-008 - Add post-support review prompt
"""

from flask import Blueprint, request, jsonify, g, redirect
from ..middleware.shopify_auth import require_shopify_auth
from app.services.support_review_service import SupportReviewService

support_review_bp = Blueprint('support_review', __name__)


def get_service() -> SupportReviewService:
    """Get support review service for current tenant."""
    return SupportReviewService(g.tenant.id)


@support_review_bp.route('/ticket/resolved', methods=['POST'])
@require_shopify_auth
def on_ticket_resolved():
    """
    Handle a support ticket being marked as resolved.

    This endpoint is called by helpdesk webhook integrations (Gorgias, Zendesk)
    when a support ticket is marked as resolved.

    Request body:
        {
            "external_ticket_id": "12345",
            "customer_email": "customer@example.com",
            "customer_name": "John Doe",  // optional
            "subject": "Help with trade-in",  // optional
            "satisfaction": "satisfied",  // satisfied, neutral, dissatisfied, not_rated
            "external_source": "gorgias"  // optional, defaults to gorgias
        }

    Response:
        {
            "success": true,
            "ticket_id": 123,
            "external_ticket_id": "12345",
            "eligible_for_review_email": true,
            "satisfaction": "satisfied"
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided',
        }), 400

    external_ticket_id = data.get('external_ticket_id')
    customer_email = data.get('customer_email')

    if not external_ticket_id:
        return jsonify({
            'success': False,
            'error': 'external_ticket_id is required',
        }), 400

    if not customer_email:
        return jsonify({
            'success': False,
            'error': 'customer_email is required',
        }), 400

    service = get_service()
    result = service.on_ticket_resolved(
        external_ticket_id=external_ticket_id,
        customer_email=customer_email,
        satisfaction=data.get('satisfaction', 'not_rated'),
        customer_name=data.get('customer_name'),
        subject=data.get('subject'),
        external_source=data.get('external_source', 'gorgias')
    )

    if not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)


@support_review_bp.route('/process-pending', methods=['POST'])
@require_shopify_auth
def process_pending_emails():
    """
    Process and send pending post-support review emails.

    This endpoint can be called manually or by a scheduled job to process
    tickets that are eligible for review emails.

    Response:
        {
            "success": true,
            "sent_count": 5,
            "failed_count": 0,
            "failed_tickets": []
        }
    """
    service = get_service()
    result = service.process_pending_review_emails()

    if not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)


@support_review_bp.route('/track/open/<tracking_id>', methods=['GET'])
def track_email_opened(tracking_id: str):
    """
    Track email open (via tracking pixel).

    This endpoint serves a 1x1 transparent pixel and records the email open.
    Called when the email client loads the tracking pixel image.

    Returns a 1x1 transparent GIF image.
    """
    from app.models.support_ticket import SupportTicket
    from app.extensions import db

    try:
        ticket = SupportTicket.find_by_tracking_id(tracking_id)
        if ticket:
            ticket.record_email_opened()
            db.session.commit()
    except Exception:
        pass  # Don't fail on tracking - fire and forget

    # Return 1x1 transparent GIF
    gif = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'

    from flask import Response
    return Response(gif, mimetype='image/gif')


@support_review_bp.route('/track/click/<tracking_id>', methods=['GET'])
def track_email_clicked(tracking_id: str):
    """
    Track email link click and redirect to app store.

    This endpoint records the click and redirects to the Shopify App Store
    review page.
    """
    from app.models.support_ticket import SupportTicket
    from app.extensions import db

    try:
        ticket = SupportTicket.find_by_tracking_id(tracking_id)
        if ticket:
            ticket.record_email_clicked()
            db.session.commit()
    except Exception:
        pass  # Don't fail on tracking - fire and forget

    # Redirect to app store review page
    review_url = "https://apps.shopify.com/tradeup-by-cardflow-labs/reviews"
    return redirect(review_url)


@support_review_bp.route('/stats', methods=['GET'])
@require_shopify_auth
def get_stats():
    """
    Get post-support review email statistics.

    Query params:
        days: Number of days to look back (default 30, 0 for all time)

    Response:
        {
            "success": true,
            "stats": {
                "period_days": 30,
                "total_sent": 50,
                "total_opened": 35,
                "total_clicked": 10,
                "open_rate": 70.0,
                "click_rate": 20.0,
                "click_to_open_rate": 28.6,
                "summary": "50 emails sent, 35 opened (70.0%), 10 clicked (20.0%)"
            }
        }
    """
    days = request.args.get('days', 30, type=int)

    service = get_service()
    stats = service.get_review_email_stats(days=days)

    return jsonify({
        'success': True,
        'stats': stats,
    })


@support_review_bp.route('/ticket/<external_ticket_id>', methods=['GET'])
@require_shopify_auth
def get_ticket_status(external_ticket_id: str):
    """
    Get the status of a support ticket.

    Response:
        {
            "success": true,
            "ticket": {
                "id": 123,
                "external_ticket_id": "12345",
                "status": "resolved",
                "satisfaction": "satisfied",
                "review_email_sent_at": "2026-01-21T10:00:00",
                ...
            }
        }
    """
    service = get_service()
    ticket = service.get_ticket_status(external_ticket_id)

    if not ticket:
        return jsonify({
            'success': False,
            'error': 'Ticket not found',
        }), 404

    return jsonify({
        'success': True,
        'ticket': ticket,
    })


# Gorgias webhook handler
@support_review_bp.route('/webhook/gorgias', methods=['POST'])
def gorgias_webhook():
    """
    Handle incoming Gorgias webhook events.

    Gorgias sends webhooks when tickets are updated. We listen for
    ticket.resolved events to trigger post-support review emails.

    This endpoint does not require Shopify auth as it's called by Gorgias.
    It uses the shop domain from the webhook payload to identify the tenant.
    """
    from app.models.tenant import Tenant

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data'}), 400

    # Get event type
    event_type = data.get('event')
    if event_type != 'ticket.updated':
        # We only care about ticket updates
        return jsonify({'success': True, 'message': 'Event ignored'})

    ticket_data = data.get('ticket', {})

    # Check if ticket is resolved
    status = ticket_data.get('status')
    if status != 'closed':
        return jsonify({'success': True, 'message': 'Ticket not closed'})

    # Get shop domain from integration settings or ticket data
    integration_id = data.get('integration_id')
    if not integration_id:
        return jsonify({'success': False, 'error': 'Missing integration_id'}), 400

    # Look up tenant by Gorgias integration ID
    tenant = Tenant.query.filter(
        Tenant.settings['integrations']['gorgias']['integration_id'].astext == str(integration_id)
    ).first()

    if not tenant:
        # Try to find by domain if available
        shop_domain = ticket_data.get('customer', {}).get('data', {}).get('shopify_domain')
        if shop_domain:
            tenant = Tenant.query.filter_by(shop_domain=shop_domain).first()

    if not tenant:
        return jsonify({'success': False, 'error': 'Tenant not found'}), 404

    # Extract customer info
    customer = ticket_data.get('customer', {})
    customer_email = customer.get('email')

    if not customer_email:
        return jsonify({'success': False, 'error': 'No customer email'}), 400

    # Get satisfaction score if available
    satisfaction = 'not_rated'
    if ticket_data.get('satisfaction_survey'):
        score = ticket_data['satisfaction_survey'].get('score')
        if score:
            if score >= 4:
                satisfaction = 'satisfied'
            elif score >= 3:
                satisfaction = 'neutral'
            else:
                satisfaction = 'dissatisfied'

    # Process the resolved ticket
    service = SupportReviewService(tenant.id)
    result = service.on_ticket_resolved(
        external_ticket_id=str(ticket_data.get('id')),
        customer_email=customer_email,
        satisfaction=satisfaction,
        customer_name=customer.get('name'),
        subject=ticket_data.get('subject'),
        external_source='gorgias'
    )

    return jsonify(result)
