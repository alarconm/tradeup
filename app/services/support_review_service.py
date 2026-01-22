"""
Support Review Service for TradeUp.

Handles post-support review email prompts. When a support ticket is resolved
with a satisfied customer, sends a friendly follow-up email asking for an
app review.

Story: RC-008 - Add post-support review prompt
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from app.extensions import db
from app.models.support_ticket import SupportTicket, TicketStatus, TicketSatisfaction
from app.models.tenant import Tenant
from app.models.member import Member

logger = logging.getLogger(__name__)


# Configuration
REVIEW_EMAIL_DELAY_HOURS = 24  # Wait 24 hours after resolution before sending
MIN_TICKET_AGE_HOURS = 1  # Ticket must exist for at least 1 hour to avoid spam


class SupportReviewService:
    """
    Service for managing post-support review email prompts.

    Workflow:
    1. Ticket is created/updated from helpdesk webhook (Gorgias, Zendesk)
    2. When ticket is marked resolved with satisfied/neutral rating
    3. Wait 24 hours to ensure resolution sticks
    4. Send friendly review email if eligible
    5. Track email opens and clicks

    Usage:
        service = SupportReviewService(tenant_id)

        # When ticket is resolved
        service.on_ticket_resolved(
            external_ticket_id='12345',
            customer_email='customer@example.com',
            satisfaction='satisfied'
        )

        # Process pending review emails (run as scheduled job)
        service.process_pending_review_emails()

        # Track email interactions
        service.track_email_opened(tracking_id)
        service.track_email_clicked(tracking_id)
    """

    def __init__(self, tenant_id: int):
        """
        Initialize the SupportReviewService.

        Args:
            tenant_id: The tenant ID to manage support reviews for
        """
        self.tenant_id = tenant_id
        self._tenant = None

    @property
    def tenant(self) -> Optional[Tenant]:
        """Lazy load the tenant."""
        if self._tenant is None:
            self._tenant = Tenant.query.get(self.tenant_id)
        return self._tenant

    def on_ticket_resolved(
        self,
        external_ticket_id: str,
        customer_email: str,
        satisfaction: str = 'not_rated',
        customer_name: Optional[str] = None,
        subject: Optional[str] = None,
        external_source: str = 'gorgias'
    ) -> Dict[str, Any]:
        """
        Handle a support ticket being marked as resolved.

        This is the main entry point when a helpdesk webhook notifies
        us of a ticket resolution.

        Args:
            external_ticket_id: External ticket reference
            customer_email: Customer's email address
            satisfaction: Customer satisfaction rating
            customer_name: Optional customer name
            subject: Optional ticket subject
            external_source: Source system (gorgias, zendesk, etc.)

        Returns:
            Dict with processing result
        """
        try:
            # Map satisfaction string to enum
            satisfaction_enum = self._map_satisfaction(satisfaction)

            # Find or create the ticket
            ticket = SupportTicket.find_or_create(
                tenant_id=self.tenant_id,
                external_ticket_id=external_ticket_id,
                customer_email=customer_email,
                external_source=external_source,
                customer_name=customer_name,
                subject=subject
            )

            # Try to link to member if exists
            if not ticket.member_id:
                member = Member.query.filter_by(
                    tenant_id=self.tenant_id,
                    email=customer_email
                ).first()
                if member:
                    ticket.member_id = member.id

            # Mark as resolved
            ticket.mark_resolved(satisfaction_enum)
            db.session.commit()

            logger.info(
                f"Ticket {external_ticket_id} marked resolved for tenant {self.tenant_id}. "
                f"Satisfaction: {satisfaction_enum.value}. "
                f"Eligible for review email: {ticket.is_eligible_for_review_email()}"
            )

            return {
                'success': True,
                'ticket_id': ticket.id,
                'external_ticket_id': external_ticket_id,
                'eligible_for_review_email': ticket.is_eligible_for_review_email(),
                'satisfaction': satisfaction_enum.value
            }

        except Exception as e:
            logger.error(f"Error handling ticket resolution: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }

    def _map_satisfaction(self, satisfaction: str) -> TicketSatisfaction:
        """Map satisfaction string to enum."""
        mapping = {
            'satisfied': TicketSatisfaction.SATISFIED,
            'happy': TicketSatisfaction.SATISFIED,
            'positive': TicketSatisfaction.SATISFIED,
            'neutral': TicketSatisfaction.NEUTRAL,
            'dissatisfied': TicketSatisfaction.DISSATISFIED,
            'unhappy': TicketSatisfaction.DISSATISFIED,
            'negative': TicketSatisfaction.DISSATISFIED,
            'not_rated': TicketSatisfaction.NOT_RATED,
        }
        return mapping.get(satisfaction.lower(), TicketSatisfaction.NOT_RATED)

    def process_pending_review_emails(self) -> Dict[str, Any]:
        """
        Process and send pending post-support review emails.

        This should be run as a scheduled job (e.g., hourly).

        Returns:
            Dict with processing results
        """
        try:
            # Get tickets eligible for review emails
            cutoff = datetime.utcnow() - timedelta(hours=REVIEW_EMAIL_DELAY_HOURS)

            eligible_tickets = SupportTicket.query.filter(
                SupportTicket.tenant_id == self.tenant_id,
                SupportTicket.status == TicketStatus.RESOLVED.value,
                SupportTicket.satisfaction.in_([
                    TicketSatisfaction.SATISFIED.value,
                    TicketSatisfaction.NEUTRAL.value,
                    TicketSatisfaction.NOT_RATED.value
                ]),
                SupportTicket.review_email_sent_at.is_(None),
                SupportTicket.resolved_at <= cutoff
            ).limit(50).all()

            sent_count = 0
            failed_count = 0
            failed_tickets = []

            for ticket in eligible_tickets:
                result = self._send_review_email(ticket)
                if result.get('success'):
                    sent_count += 1
                else:
                    failed_count += 1
                    failed_tickets.append(ticket.external_ticket_id)

            logger.info(
                f"Processed review emails for tenant {self.tenant_id}: "
                f"{sent_count} sent, {failed_count} failed"
            )

            return {
                'success': True,
                'sent_count': sent_count,
                'failed_count': failed_count,
                'failed_tickets': failed_tickets[:10]  # Limit for response size
            }

        except Exception as e:
            logger.error(f"Error processing pending review emails: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _send_review_email(self, ticket: SupportTicket) -> Dict[str, Any]:
        """
        Send a post-support review email for a ticket.

        Args:
            ticket: SupportTicket to send email for

        Returns:
            Dict with send result
        """
        try:
            from app.services.notification_service import NotificationService

            notification_service = NotificationService()

            # Generate tracking ID for this email
            tracking_id = str(uuid.uuid4())

            # Get tenant settings for from name
            shop_name = self.tenant.shop_name if self.tenant else 'TradeUp'

            # Build email content
            customer_name = ticket.customer_name or ticket.customer_email.split('@')[0]

            subject = f"Thanks for reaching out, {customer_name}!"

            text_content = f"""Hi {customer_name},

We hope we were able to help with your recent question. Your satisfaction means the world to us!

If you have a moment, we'd really appreciate it if you could share your experience with TradeUp on the Shopify App Store. Your feedback helps other merchants discover our app and helps us continue improving.

[Leave a Review]

It only takes a minute, and every review makes a difference.

Thank you for being part of our community!

Warm regards,
The {shop_name} Team

P.S. No pressure at all - we're just grateful you gave us the chance to help!

---
You're receiving this email because you recently contacted our support team.
"""

            # App store review URL (update with actual app listing URL)
            review_url = f"https://apps.shopify.com/tradeup-by-cardflow-labs/reviews?utm_source=support_email&tracking_id={tracking_id}"

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f6f6f7;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: white; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">

            <h1 style="margin: 0 0 16px 0; font-size: 24px; color: #202223;">
                Thanks for reaching out!
            </h1>

            <p style="color: #6d7175; font-size: 16px; line-height: 1.6;">
                Hi {customer_name},
            </p>

            <p style="color: #6d7175; font-size: 16px; line-height: 1.6;">
                We hope we were able to help with your recent question. Your satisfaction means the world to us!
            </p>

            <p style="color: #6d7175; font-size: 16px; line-height: 1.6;">
                If you have a moment, we'd really appreciate it if you could share your experience with TradeUp on the Shopify App Store. Your feedback helps other merchants discover our app and helps us continue improving.
            </p>

            <div style="text-align: center; margin: 32px 0;">
                <a href="{review_url}"
                   style="display: inline-block; background: #5c6ac4; color: white; text-decoration: none; padding: 14px 28px; border-radius: 6px; font-weight: 500; font-size: 16px;">
                    Leave a Review
                </a>
            </div>

            <p style="color: #8c9196; font-size: 14px; line-height: 1.6; text-align: center;">
                It only takes a minute, and every review makes a difference.
            </p>

            <hr style="border: none; border-top: 1px solid #e1e3e5; margin: 32px 0;">

            <p style="color: #6d7175; font-size: 16px; line-height: 1.6;">
                Thank you for being part of our community!
            </p>

            <p style="color: #6d7175; font-size: 16px; line-height: 1.6; margin-bottom: 0;">
                Warm regards,<br>
                The {shop_name} Team
            </p>

            <p style="color: #8c9196; font-size: 13px; font-style: italic; margin-top: 24px;">
                P.S. No pressure at all - we're just grateful you gave us the chance to help!
            </p>
        </div>

        <p style="text-align: center; color: #8c9196; font-size: 12px; margin-top: 16px;">
            You're receiving this email because you recently contacted our support team.
        </p>
    </div>
    <img src="https://app.cardflowlabs.com/api/support-review/track/open/{tracking_id}" width="1" height="1" style="display:none;" alt="">
</body>
</html>
"""

            # Get settings
            settings = notification_service._get_tenant_settings(self.tenant_id)

            # Send the email
            result = notification_service._send_email(
                to_email=ticket.customer_email,
                to_name=customer_name,
                subject=subject,
                text_content=text_content,
                html_content=html_content,
                from_email=settings.get('from_email', notification_service.default_from_email),
                from_name=settings.get('from_name', shop_name)
            )

            if result.get('success'):
                ticket.mark_review_email_sent(tracking_id)
                db.session.commit()

                logger.info(
                    f"Sent post-support review email for ticket {ticket.external_ticket_id} "
                    f"to {ticket.customer_email}"
                )

            return result

        except Exception as e:
            logger.error(f"Error sending review email for ticket {ticket.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def track_email_opened(self, tracking_id: str) -> Dict[str, Any]:
        """
        Record that a review email was opened.

        Args:
            tracking_id: Email tracking ID

        Returns:
            Dict with tracking result
        """
        ticket = SupportTicket.find_by_tracking_id(tracking_id)

        if not ticket:
            return {
                'success': False,
                'error': 'Tracking ID not found'
            }

        ticket.record_email_opened()
        db.session.commit()

        logger.debug(f"Recorded email open for ticket {ticket.external_ticket_id}")

        return {
            'success': True,
            'ticket_id': ticket.id
        }

    def track_email_clicked(self, tracking_id: str) -> Dict[str, Any]:
        """
        Record that a review email link was clicked.

        Args:
            tracking_id: Email tracking ID

        Returns:
            Dict with tracking result
        """
        ticket = SupportTicket.find_by_tracking_id(tracking_id)

        if not ticket:
            return {
                'success': False,
                'error': 'Tracking ID not found'
            }

        ticket.record_email_clicked()
        db.session.commit()

        logger.debug(f"Recorded email click for ticket {ticket.external_ticket_id}")

        return {
            'success': True,
            'ticket_id': ticket.id
        }

    def get_review_email_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get statistics for post-support review emails.

        Args:
            days: Number of days to look back (0 for all time)

        Returns:
            Dict with email statistics
        """
        query = SupportTicket.query.filter(
            SupportTicket.tenant_id == self.tenant_id,
            SupportTicket.review_email_sent_at.isnot(None)
        )

        if days > 0:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(SupportTicket.review_email_sent_at >= cutoff)

        tickets = query.all()

        total_sent = len(tickets)
        total_opened = sum(1 for t in tickets if t.review_email_opened_at)
        total_clicked = sum(1 for t in tickets if t.review_email_clicked_at)

        open_rate = (total_opened / total_sent * 100) if total_sent > 0 else 0
        click_rate = (total_clicked / total_sent * 100) if total_sent > 0 else 0
        click_to_open_rate = (total_clicked / total_opened * 100) if total_opened > 0 else 0

        return {
            'period_days': days if days > 0 else 'all_time',
            'total_sent': total_sent,
            'total_opened': total_opened,
            'total_clicked': total_clicked,
            'open_rate': round(open_rate, 1),
            'click_rate': round(click_rate, 1),
            'click_to_open_rate': round(click_to_open_rate, 1),
            'summary': (
                f"{total_sent} emails sent, "
                f"{total_opened} opened ({round(open_rate, 1)}%), "
                f"{total_clicked} clicked ({round(click_rate, 1)}%)"
            )
        }

    def get_ticket_status(self, external_ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a support ticket.

        Args:
            external_ticket_id: External ticket reference

        Returns:
            Dict with ticket status or None if not found
        """
        ticket = SupportTicket.query.filter_by(
            tenant_id=self.tenant_id,
            external_ticket_id=external_ticket_id
        ).first()

        if not ticket:
            return None

        return ticket.to_dict()


def get_support_review_service(tenant_id: int) -> SupportReviewService:
    """Get SupportReviewService for a tenant."""
    return SupportReviewService(tenant_id)
