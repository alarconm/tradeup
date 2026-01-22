"""
Widget Configuration Model

Database model to store widget configurations per tenant for the Widget Builder system.
Supports multiple widget types with customizable position, styling, and content options.
"""

from datetime import datetime
from enum import Enum
from ..extensions import db


class WidgetType(str, Enum):
    """Types of widgets available in the system."""
    POINTS_BALANCE = 'points_balance'  # Floating points balance display
    TIER_BADGE = 'tier_badge'  # Tier status badge
    REWARDS_LAUNCHER = 'rewards_launcher'  # Button to open rewards panel
    REFERRAL_PROMPT = 'referral_prompt'  # Referral sharing prompt


# Default configurations for each widget type
DEFAULT_WIDGET_CONFIGS = {
    WidgetType.POINTS_BALANCE: {
        'position': {
            'type': 'fixed',
            'location': 'bottom-right',
            'offset_x': 20,
            'offset_y': 20,
        },
        'styling': {
            'background_color': '#000000',
            'text_color': '#ffffff',
            'accent_color': '#e85d27',
            'border_radius': 12,
            'font_size': 14,
            'shadow': True,
        },
        'content': {
            'show_icon': True,
            'show_label': True,
            'label_text': 'Your Points',
            'show_tier_indicator': True,
        },
        'behavior': {
            'click_action': 'open_rewards',
            'animate_on_update': True,
            'show_on_mobile': True,
        },
    },
    WidgetType.TIER_BADGE: {
        'position': {
            'type': 'inline',
            'selector': '.customer-info',
            'placement': 'after',
        },
        'styling': {
            'background_color': 'transparent',
            'text_color': '#333333',
            'badge_style': 'pill',  # pill, square, rounded
            'font_size': 12,
        },
        'content': {
            'show_tier_name': True,
            'show_tier_icon': True,
            'show_progress_bar': False,
        },
        'behavior': {
            'click_action': 'show_tier_benefits',
            'show_on_mobile': True,
        },
    },
    WidgetType.REWARDS_LAUNCHER: {
        'position': {
            'type': 'fixed',
            'location': 'bottom-left',
            'offset_x': 20,
            'offset_y': 20,
        },
        'styling': {
            'background_color': '#e85d27',
            'text_color': '#ffffff',
            'icon_color': '#ffffff',
            'border_radius': 50,
            'size': 56,  # Button size in pixels
            'shadow': True,
        },
        'content': {
            'icon': 'gift',
            'tooltip_text': 'View Rewards',
            'show_notification_badge': True,
        },
        'behavior': {
            'click_action': 'open_panel',
            'panel_position': 'right',
            'show_on_mobile': True,
        },
    },
    WidgetType.REFERRAL_PROMPT: {
        'position': {
            'type': 'fixed',
            'location': 'top-center',
            'offset_y': 20,
        },
        'styling': {
            'background_color': '#ffffff',
            'text_color': '#333333',
            'accent_color': '#e85d27',
            'border_radius': 8,
            'font_size': 14,
            'shadow': True,
        },
        'content': {
            'title': 'Share & Earn!',
            'description': 'Refer a friend and you both get rewarded',
            'cta_text': 'Get Your Link',
            'show_reward_amount': True,
        },
        'behavior': {
            'trigger': 'scroll',  # scroll, delay, exit_intent
            'trigger_value': 50,  # 50% scroll, 5s delay, etc.
            'show_once_per_session': True,
            'dismissible': True,
            'show_on_mobile': True,
        },
    },
}


class Widget(db.Model):
    """
    Widget configuration for a tenant.

    Each tenant can have multiple widgets, one for each widget type.
    Stores position, styling, and content configuration as JSON.
    """
    __tablename__ = 'widgets'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Widget type (points_balance, tier_badge, rewards_launcher, referral_prompt)
    widget_type = db.Column(db.String(50), nullable=False, index=True)

    # JSON configuration storing position, styling, and content options
    # Structure: {
    #   'position': {'type': 'fixed', 'location': 'bottom-right', ...},
    #   'styling': {'background_color': '#000', ...},
    #   'content': {'show_icon': True, ...},
    #   'behavior': {'click_action': 'open_rewards', ...}
    # }
    config = db.Column(db.JSON, nullable=False, default=dict)

    # Whether this widget is enabled for display
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship
    tenant = db.relationship('Tenant', backref=db.backref('widgets', lazy='dynamic'))

    # Unique constraint: one widget type per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'widget_type', name='unique_tenant_widget_type'),
    )

    def __repr__(self):
        return f'<Widget {self.widget_type} for tenant {self.tenant_id} enabled={self.is_enabled}>'

    def to_dict(self):
        """Serialize widget config to dictionary."""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'widget_type': self.widget_type,
            'config': self.config or {},
            'is_enabled': self.is_enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_position(self):
        """Get widget position configuration."""
        return self.config.get('position', {})

    def get_styling(self):
        """Get widget styling configuration."""
        return self.config.get('styling', {})

    def get_content(self):
        """Get widget content configuration."""
        return self.config.get('content', {})

    def get_behavior(self):
        """Get widget behavior configuration."""
        return self.config.get('behavior', {})

    def update_config(self, new_config: dict):
        """
        Update widget configuration by merging with existing config.

        Args:
            new_config: Dictionary with updated configuration sections
        """
        current_config = self.config or {}
        for key in ['position', 'styling', 'content', 'behavior']:
            if key in new_config:
                current_config[key] = {**current_config.get(key, {}), **new_config[key]}
        self.config = current_config
        self.updated_at = datetime.utcnow()

    @classmethod
    def get_by_type(cls, tenant_id: int, widget_type: str) -> 'Widget':
        """Get widget config by type for a tenant."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            widget_type=widget_type
        ).first()

    @classmethod
    def get_all_for_tenant(cls, tenant_id: int) -> list:
        """Get all widget configs for a tenant."""
        return cls.query.filter_by(tenant_id=tenant_id).all()

    @classmethod
    def get_enabled_for_tenant(cls, tenant_id: int) -> list:
        """Get all enabled widget configs for a tenant."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            is_enabled=True
        ).all()

    @classmethod
    def create_defaults_for_tenant(cls, tenant_id: int) -> list:
        """
        Create default widget configurations for a new tenant.

        Creates one Widget for each WidgetType with default settings.
        Skips any that already exist.

        Args:
            tenant_id: The tenant ID to create configs for

        Returns:
            List of created Widget instances
        """
        created_widgets = []

        for widget_type in WidgetType:
            # Check if widget already exists
            existing = cls.get_by_type(tenant_id, widget_type.value)
            if existing:
                continue

            # Create new widget with defaults
            widget = cls(
                tenant_id=tenant_id,
                widget_type=widget_type.value,
                is_enabled=False,  # Start disabled by default
                config=DEFAULT_WIDGET_CONFIGS.get(widget_type, {})
            )
            db.session.add(widget)
            created_widgets.append(widget)

        if created_widgets:
            db.session.commit()

        return created_widgets

    @classmethod
    def get_or_create(cls, tenant_id: int, widget_type: str) -> 'Widget':
        """
        Get existing widget or create a new one with defaults.

        Args:
            tenant_id: The tenant ID
            widget_type: The widget type string

        Returns:
            Widget instance
        """
        widget = cls.get_by_type(tenant_id, widget_type)

        if not widget:
            # Get default config for this type
            try:
                wt = WidgetType(widget_type)
                default_config = DEFAULT_WIDGET_CONFIGS.get(wt, {})
            except ValueError:
                default_config = {}

            widget = cls(
                tenant_id=tenant_id,
                widget_type=widget_type,
                is_enabled=False,
                config=default_config
            )
            db.session.add(widget)
            db.session.flush()

        return widget


def seed_widgets(tenant_id: int) -> list:
    """
    Seed default widget configurations for a tenant.

    This function should be called during tenant setup/onboarding.

    Args:
        tenant_id: The tenant ID to seed widgets for

    Returns:
        List of created Widget instances
    """
    return Widget.create_defaults_for_tenant(tenant_id)
