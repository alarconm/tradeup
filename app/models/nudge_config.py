"""
NudgeConfig Model

Stores nudge configurations and settings per tenant for the Nudges & Reminders system.
Supports configurable nudge types with customizable frequency and message templates.
"""

from datetime import datetime
from enum import Enum
from ..extensions import db


class NudgeType(str, Enum):
    """Types of nudges/reminders available in the system."""
    POINTS_EXPIRING = 'points_expiring'
    TIER_PROGRESS = 'tier_progress'
    INACTIVE_REMINDER = 'inactive_reminder'
    TRADE_IN_REMINDER = 'trade_in_reminder'


# Default message templates for each nudge type
DEFAULT_NUDGE_TEMPLATES = {
    NudgeType.POINTS_EXPIRING: "Hi {member_name}, you have {expiring_points} points expiring in {days_until} days! Visit {shop_name} to redeem them before they expire.",
    NudgeType.TIER_PROGRESS: "Hi {member_name}, you're {progress_percent}% of the way to {next_tier}! Earn {points_needed} more points to unlock exclusive benefits.",
    NudgeType.INACTIVE_REMINDER: "Hi {member_name}, we miss you at {shop_name}! It's been {days_inactive} days since your last visit. Come back and check out what's new!",
    NudgeType.TRADE_IN_REMINDER: "Hi {member_name}, have items to trade in? {shop_name} is accepting trade-ins! Bring in your items and earn store credit.",
}

# Default frequency in days for each nudge type
DEFAULT_NUDGE_FREQUENCY = {
    NudgeType.POINTS_EXPIRING: 7,  # Weekly reminders
    NudgeType.TIER_PROGRESS: 14,   # Bi-weekly reminders
    NudgeType.INACTIVE_REMINDER: 30,  # Monthly reminders
    NudgeType.TRADE_IN_REMINDER: 21,  # Every 3 weeks
}


class NudgeConfig(db.Model):
    """
    Configuration for nudge/reminder messages per tenant.

    Each tenant can have multiple nudge configurations, one for each nudge type.
    """
    __tablename__ = 'nudge_configs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Nudge type (points_expiring, tier_progress, inactive_reminder, trade_in_reminder)
    nudge_type = db.Column(db.String(50), nullable=False, index=True)

    # Whether this nudge type is enabled
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)

    # Frequency of nudges in days (how often to send this nudge)
    frequency_days = db.Column(db.Integer, default=7, nullable=False)

    # Message template with placeholders like {member_name}, {shop_name}, etc.
    message_template = db.Column(db.Text, nullable=False)

    # Additional configuration options stored as JSON
    # For points_expiring: threshold_days (e.g., 30, 7, 1)
    # For tier_progress: threshold_percent (e.g., 0.9 for 90%)
    # For inactive_reminder: inactive_days (e.g., 30)
    # For trade_in_reminder: min_days_since_last (e.g., 60)
    config_options = db.Column(db.JSON, default=dict)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    tenant = db.relationship('Tenant', backref=db.backref('nudge_configs', lazy='dynamic'))

    # Unique constraint: one nudge type per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'nudge_type', name='unique_tenant_nudge_type'),
    )

    def __repr__(self):
        return f'<NudgeConfig {self.nudge_type} for tenant {self.tenant_id}>'

    def to_dict(self):
        """Serialize nudge config to dictionary."""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'nudge_type': self.nudge_type,
            'is_enabled': self.is_enabled,
            'frequency_days': self.frequency_days,
            'message_template': self.message_template,
            'config_options': self.config_options or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_by_type(cls, tenant_id: int, nudge_type: str) -> 'NudgeConfig':
        """Get nudge config by type for a tenant."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            nudge_type=nudge_type
        ).first()

    @classmethod
    def get_all_for_tenant(cls, tenant_id: int) -> list:
        """Get all nudge configs for a tenant."""
        return cls.query.filter_by(tenant_id=tenant_id).all()

    @classmethod
    def get_enabled_for_tenant(cls, tenant_id: int) -> list:
        """Get all enabled nudge configs for a tenant."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            is_enabled=True
        ).all()

    @classmethod
    def create_defaults_for_tenant(cls, tenant_id: int) -> list:
        """
        Create default nudge configurations for a new tenant.

        Creates one NudgeConfig for each NudgeType with default settings.
        Skips any that already exist.

        Args:
            tenant_id: The tenant ID to create configs for

        Returns:
            List of created NudgeConfig instances
        """
        created_configs = []

        for nudge_type in NudgeType:
            # Check if config already exists
            existing = cls.get_by_type(tenant_id, nudge_type.value)
            if existing:
                continue

            # Create new config with defaults
            config = cls(
                tenant_id=tenant_id,
                nudge_type=nudge_type.value,
                is_enabled=True,
                frequency_days=DEFAULT_NUDGE_FREQUENCY.get(nudge_type, 7),
                message_template=DEFAULT_NUDGE_TEMPLATES.get(nudge_type, ''),
                config_options=cls._get_default_options(nudge_type)
            )
            db.session.add(config)
            created_configs.append(config)

        if created_configs:
            db.session.commit()

        return created_configs

    @staticmethod
    def _get_default_options(nudge_type: NudgeType) -> dict:
        """Get default config options for a nudge type."""
        defaults = {
            NudgeType.POINTS_EXPIRING: {
                'threshold_days': [30, 7, 1],  # Send at 30, 7, and 1 day before expiry
            },
            NudgeType.TIER_PROGRESS: {
                'threshold_percent': 0.9,  # Notify when 90% to next tier
            },
            NudgeType.INACTIVE_REMINDER: {
                'inactive_days': 30,  # Consider inactive after 30 days
            },
            NudgeType.TRADE_IN_REMINDER: {
                'min_days_since_last': 60,  # Remind if no trade-in in 60 days
            },
        }
        return defaults.get(nudge_type, {})


def seed_nudge_configs(tenant_id: int):
    """
    Seed default nudge configurations for a tenant.

    This function should be called during tenant setup/onboarding.

    Args:
        tenant_id: The tenant ID to seed configs for

    Returns:
        List of created NudgeConfig instances
    """
    return NudgeConfig.create_defaults_for_tenant(tenant_id)
