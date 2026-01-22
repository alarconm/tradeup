"""
Loyalty Page Builder Models

Database model to store page builder configurations per tenant.
Supports draft and published versions.
"""

from datetime import datetime
from app import db


class LoyaltyPage(db.Model):
    """
    Loyalty landing page configuration for a tenant.

    Stores page builder settings including sections, styles, and content.
    Supports draft editing with separate publication workflow.
    """

    __tablename__ = 'loyalty_pages'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Page configuration stored as JSON
    # Structure: {
    #   'template': 'minimal',
    #   'sections': [...],
    #   'colors': {...},
    #   'custom_css': '',
    #   'meta': {'title': '', 'description': ''}
    # }
    page_config = db.Column(db.JSON, nullable=False, default=dict)

    # Draft configuration (edits before publishing)
    # If null, page_config is used as draft
    draft_config = db.Column(db.JSON, nullable=True)

    # Publication status
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    published_at = db.Column(db.DateTime, nullable=True)

    # Version tracking
    version = db.Column(db.Integer, default=1, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('loyalty_pages', lazy='dynamic'))

    # Ensure one page per tenant (can expand to multiple pages later)
    __table_args__ = (
        db.UniqueConstraint('tenant_id', name='unique_tenant_loyalty_page'),
    )

    def __repr__(self):
        return f'<LoyaltyPage {self.id} tenant={self.tenant_id} published={self.is_published}>'

    def to_dict(self):
        """Return dictionary representation of the page."""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'page_config': self.page_config,
            'draft_config': self.draft_config,
            'is_published': self.is_published,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_published_config(self):
        """Get the published page configuration."""
        if not self.is_published:
            return None
        return self.page_config

    def get_draft_config(self):
        """
        Get the draft configuration.
        Returns draft_config if exists, otherwise page_config.
        """
        return self.draft_config if self.draft_config is not None else self.page_config

    def update_draft(self, config):
        """
        Update the draft configuration.

        Args:
            config: Dictionary with page configuration
        """
        self.draft_config = config
        self.updated_at = datetime.utcnow()

    def publish(self):
        """
        Publish the current draft.
        Moves draft_config to page_config and updates publication status.
        """
        if self.draft_config is not None:
            self.page_config = self.draft_config
            self.draft_config = None

        self.is_published = True
        self.published_at = datetime.utcnow()
        self.version += 1
        self.updated_at = datetime.utcnow()

    def unpublish(self):
        """
        Unpublish the page.
        Keeps the configuration but marks as unpublished.
        """
        self.is_published = False
        self.updated_at = datetime.utcnow()

    def discard_draft(self):
        """
        Discard the current draft and revert to published version.
        """
        self.draft_config = None
        self.updated_at = datetime.utcnow()

    def has_unsaved_changes(self):
        """Check if there are unpublished changes in draft."""
        return self.draft_config is not None

    @classmethod
    def get_or_create(cls, tenant_id, default_config=None):
        """
        Get existing page or create a new one for the tenant.

        Args:
            tenant_id: The tenant ID
            default_config: Default configuration if creating new

        Returns:
            LoyaltyPage instance
        """
        page = cls.query.filter_by(tenant_id=tenant_id).first()

        if not page:
            page = cls(
                tenant_id=tenant_id,
                page_config=default_config or {},
                is_published=False,
            )
            db.session.add(page)
            db.session.flush()

        return page


# Default page configuration structure
DEFAULT_PAGE_CONFIG = {
    'template': 'minimal',
    'sections': [
        {
            'id': 'hero',
            'type': 'hero',
            'enabled': True,
            'order': 0,
            'settings': {
                'title': 'Join Our Rewards Program',
                'subtitle': 'Earn points on every purchase and unlock exclusive rewards',
                'cta_text': 'Join Now',
                'cta_link': '/account/register',
                'background_type': 'gradient',
                'background_color': '#e85d27',
                'text_color': '#ffffff',
            }
        },
        {
            'id': 'how_it_works',
            'type': 'how_it_works',
            'enabled': True,
            'order': 1,
            'settings': {
                'title': 'How It Works',
                'steps': [
                    {'icon': 'star', 'title': 'Sign Up', 'description': 'Create your free account'},
                    {'icon': 'shopping-cart', 'title': 'Shop & Earn', 'description': 'Earn points on every purchase'},
                    {'icon': 'gift', 'title': 'Redeem', 'description': 'Use points for rewards and discounts'},
                ]
            }
        },
        {
            'id': 'tiers',
            'type': 'tier_comparison',
            'enabled': True,
            'order': 2,
            'settings': {
                'title': 'Membership Tiers',
                'show_benefits': True,
                'show_prices': True,
                'highlight_tier': None,
            }
        },
        {
            'id': 'rewards',
            'type': 'rewards_catalog',
            'enabled': True,
            'order': 3,
            'settings': {
                'title': 'Available Rewards',
                'show_points_cost': True,
                'max_items': 6,
            }
        },
        {
            'id': 'earning_rules',
            'type': 'earning_rules',
            'enabled': True,
            'order': 4,
            'settings': {
                'title': 'Ways to Earn',
                'show_points_values': True,
            }
        },
        {
            'id': 'faq',
            'type': 'faq',
            'enabled': False,
            'order': 5,
            'settings': {
                'title': 'Frequently Asked Questions',
                'items': [
                    {'question': 'How do I earn points?', 'answer': 'Earn points on every purchase. The more you shop, the more you earn!'},
                    {'question': 'How do I redeem rewards?', 'answer': 'Use your points at checkout or in your account dashboard.'},
                    {'question': 'Do points expire?', 'answer': 'Points expire after 12 months of account inactivity.'},
                ]
            }
        },
        {
            'id': 'referrals',
            'type': 'referral_banner',
            'enabled': True,
            'order': 6,
            'settings': {
                'title': 'Refer Friends & Earn',
                'description': 'Give $10, Get $10 for every friend you refer',
                'show_code_input': True,
            }
        },
    ],
    'colors': {
        'primary': '#000000',
        'secondary': '#666666',
        'accent': '#e85d27',
        'background': '#ffffff',
    },
    'custom_css': '',
    'meta': {
        'title': 'Rewards Program',
        'description': 'Join our rewards program and earn points on every purchase',
    },
}
