"""
Support Ticket tracking model for post-support review prompts.

Story: RC-008 - Add post-support review prompt
"""
from datetime import datetime
from enum import Enum
from ..extensions import db


class TicketStatus(str, Enum):
    """Possible statuses for a support ticket."""
    OPEN = 'open'
    PENDING = 'pending'
    RESOLVED = 'resolved'
    CLOSED = 'closed'


class TicketSatisfaction(str, Enum):
    """Customer satisfaction rating for resolved tickets."""
    SATISFIED = 'satisfied'
    NEUTRAL = 'neutral'
    DISSATISFIED = 'dissatisfied'
    NOT_RATED = 'not_rated'


class SupportTicket(db.Model):
    """
    Tracks support tickets for post-support review email prompts.

    This model stores references to support tickets (from Gorgias or other
    helpdesk integrations) and tracks when review emails are sent.

    Story: RC-008 - Add post-support review prompt
    """
    __tablename__ = 'support_tickets'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)

    # External ticket reference (from Gorgias, Zendesk, etc.)
    external_ticket_id = db.Column(db.String(100), nullable=False, index=True)
    external_source = db.Column(db.String(50), default='gorgias')  # gorgias, zendesk, etc.

    # Customer information
    customer_email = db.Column(db.String(255), nullable=False)
    customer_name = db.Column(db.String(255), nullable=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id', ondelete='SET NULL'), nullable=True)

    # Ticket details
    subject = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default=TicketStatus.OPEN.value)
    satisfaction = db.Column(db.String(20), default=TicketSatisfaction.NOT_RATED.value)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Review email tracking
    review_email_sent_at = db.Column(db.DateTime, nullable=True)
    review_email_opened_at = db.Column(db.DateTime, nullable=True)
    review_email_clicked_at = db.Column(db.DateTime, nullable=True)
    review_email_tracking_id = db.Column(db.String(64), nullable=True, unique=True)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('support_tickets', lazy='dynamic'))
    member = db.relationship('Member', backref=db.backref('support_tickets', lazy='dynamic'))

    def __repr__(self):
        return f'<SupportTicket {self.external_ticket_id} status={self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'external_ticket_id': self.external_ticket_id,
            'external_source': self.external_source,
            'customer_email': self.customer_email,
            'customer_name': self.customer_name,
            'member_id': self.member_id,
            'subject': self.subject,
            'status': self.status,
            'satisfaction': self.satisfaction,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'review_email_sent_at': self.review_email_sent_at.isoformat() if self.review_email_sent_at else None,
            'review_email_opened_at': self.review_email_opened_at.isoformat() if self.review_email_opened_at else None,
            'review_email_clicked_at': self.review_email_clicked_at.isoformat() if self.review_email_clicked_at else None,
        }

    def mark_resolved(self, satisfaction: TicketSatisfaction = TicketSatisfaction.NOT_RATED):
        """Mark the ticket as resolved with optional satisfaction rating."""
        self.status = TicketStatus.RESOLVED.value
        self.satisfaction = satisfaction.value
        self.resolved_at = datetime.utcnow()

    def is_eligible_for_review_email(self) -> bool:
        """
        Check if this ticket is eligible for a post-support review email.

        Criteria:
        - Ticket must be resolved
        - Customer must be satisfied or neutral (not dissatisfied)
        - Review email not already sent
        """
        if self.status != TicketStatus.RESOLVED.value:
            return False

        if self.satisfaction == TicketSatisfaction.DISSATISFIED.value:
            return False

        if self.review_email_sent_at is not None:
            return False

        return True

    def mark_review_email_sent(self, tracking_id: str):
        """Record that the review email was sent."""
        self.review_email_sent_at = datetime.utcnow()
        self.review_email_tracking_id = tracking_id

    def record_email_opened(self):
        """Record that the review email was opened."""
        if self.review_email_opened_at is None:
            self.review_email_opened_at = datetime.utcnow()

    def record_email_clicked(self):
        """Record that the review email link was clicked."""
        if self.review_email_clicked_at is None:
            self.review_email_clicked_at = datetime.utcnow()
            # Also record as opened if not already
            if self.review_email_opened_at is None:
                self.review_email_opened_at = datetime.utcnow()

    @classmethod
    def find_by_tracking_id(cls, tracking_id: str) -> 'SupportTicket':
        """Find a ticket by its review email tracking ID."""
        return cls.query.filter_by(review_email_tracking_id=tracking_id).first()

    @classmethod
    def find_or_create(
        cls,
        tenant_id: int,
        external_ticket_id: str,
        customer_email: str,
        external_source: str = 'gorgias',
        **kwargs
    ) -> 'SupportTicket':
        """
        Find existing ticket or create a new one.

        Args:
            tenant_id: Tenant ID
            external_ticket_id: External ticket reference
            customer_email: Customer's email
            external_source: Source system (gorgias, zendesk, etc.)
            **kwargs: Additional fields to set

        Returns:
            SupportTicket instance
        """
        ticket = cls.query.filter_by(
            tenant_id=tenant_id,
            external_ticket_id=external_ticket_id,
            external_source=external_source
        ).first()

        if ticket:
            # Update existing ticket
            for key, value in kwargs.items():
                if hasattr(ticket, key):
                    setattr(ticket, key, value)
        else:
            # Create new ticket
            ticket = cls(
                tenant_id=tenant_id,
                external_ticket_id=external_ticket_id,
                customer_email=customer_email,
                external_source=external_source,
                **kwargs
            )
            db.session.add(ticket)

        return ticket

    @classmethod
    def get_pending_review_emails(cls, tenant_id: int, limit: int = 50):
        """
        Get tickets eligible for review emails.

        Returns resolved/satisfied tickets that haven't received a review email.
        """
        return cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.status == TicketStatus.RESOLVED.value,
            cls.satisfaction.in_([
                TicketSatisfaction.SATISFIED.value,
                TicketSatisfaction.NEUTRAL.value,
                TicketSatisfaction.NOT_RATED.value
            ]),
            cls.review_email_sent_at.is_(None)
        ).limit(limit).all()
