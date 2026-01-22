"""
Review prompt tracking model for in-app review collection.
"""
from datetime import datetime
from enum import Enum
from ..extensions import db


class ReviewPromptResponse(str, Enum):
    """Possible responses to a review prompt."""
    DISMISSED = 'dismissed'
    CLICKED = 'clicked'
    REMINDED_LATER = 'reminded_later'


class ReviewPrompt(db.Model):
    """
    Tracks when review prompts are shown to merchants and their responses.
    Used to manage in-app review collection for App Store visibility.
    """
    __tablename__ = 'review_prompts'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)

    # When the prompt was shown
    prompt_shown_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # How the merchant responded
    response = db.Column(db.String(20), nullable=True)  # dismissed, clicked, reminded_later
    responded_at = db.Column(db.DateTime, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    tenant = db.relationship('Tenant', backref=db.backref('review_prompts', lazy='dynamic'))

    def __repr__(self):
        return f'<ReviewPrompt tenant={self.tenant_id} response={self.response}>'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'prompt_shown_at': self.prompt_shown_at.isoformat() if self.prompt_shown_at else None,
            'response': self.response,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def record_response(self, response: ReviewPromptResponse):
        """Record a merchant's response to the prompt."""
        self.response = response.value
        self.responded_at = datetime.utcnow()

    @classmethod
    def can_show_prompt(cls, tenant_id: int, cooldown_hours: int = 168) -> bool:
        """
        Check if a review prompt can be shown to this tenant.
        Prevents duplicate prompts within the cooldown period (default: 7 days).

        Args:
            tenant_id: The tenant to check
            cooldown_hours: Hours to wait between prompts (default 168 = 7 days)

        Returns:
            True if a prompt can be shown, False otherwise
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=cooldown_hours)

        # Check for any recent prompts
        recent_prompt = cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.prompt_shown_at >= cutoff
        ).first()

        return recent_prompt is None

    @classmethod
    def get_prompt_history(cls, tenant_id: int, limit: int = 10):
        """
        Get the review prompt history for a tenant.

        Args:
            tenant_id: The tenant to get history for
            limit: Maximum number of records to return

        Returns:
            List of ReviewPrompt records, most recent first
        """
        return cls.query.filter(
            cls.tenant_id == tenant_id
        ).order_by(cls.prompt_shown_at.desc()).limit(limit).all()

    @classmethod
    def create_prompt(cls, tenant_id: int) -> 'ReviewPrompt':
        """
        Create a new review prompt record for a tenant.
        This should only be called after checking can_show_prompt().

        Args:
            tenant_id: The tenant to create a prompt for

        Returns:
            The newly created ReviewPrompt
        """
        prompt = cls(
            tenant_id=tenant_id,
            prompt_shown_at=datetime.utcnow()
        )
        db.session.add(prompt)
        return prompt
