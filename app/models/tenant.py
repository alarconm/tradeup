"""
Tenant model for multi-tenant SaaS.
"""
from datetime import datetime
from ..extensions import db


class Tenant(db.Model):
    """
    Card shop tenant using the Quick Flip platform.
    Global table - shared across all tenants.
    """
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(255), nullable=False)
    shop_slug = db.Column(db.String(100), unique=True, nullable=False)

    # Shopify integration
    shopify_domain = db.Column(db.String(255))
    shopify_access_token = db.Column(db.Text)  # Encrypted in production
    webhook_secret = db.Column(db.String(100))

    # Subscription info
    subscription_tier = db.Column(db.String(20), default='basic')  # basic, pro, enterprise
    subscription_status = db.Column(db.String(20), default='trial')  # trial, active, cancelled
    trial_ends_at = db.Column(db.DateTime)
    monthly_price = db.Column(db.Numeric(10, 2))

    # Settings (JSON for flexibility)
    settings = db.Column(db.JSON, default=dict)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    api_keys = db.relationship('APIKey', backref='tenant', lazy='dynamic')
    membership_tiers = db.relationship('MembershipTier', backref='tenant', lazy='dynamic')
    members = db.relationship('Member', backref='tenant', lazy='dynamic')

    def __repr__(self):
        return f'<Tenant {self.shop_slug}>'

    def to_dict(self):
        return {
            'id': self.id,
            'shop_name': self.shop_name,
            'shop_slug': self.shop_slug,
            'shopify_domain': self.shopify_domain,
            'subscription_tier': self.subscription_tier,
            'subscription_status': self.subscription_status,
            'is_active': self.is_active
        }


class APIKey(db.Model):
    """
    API keys for tenant authentication.
    """
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    key_hash = db.Column(db.String(255), nullable=False)  # bcrypt hash
    key_prefix = db.Column(db.String(10), nullable=False)  # First 8 chars for lookup
    name = db.Column(db.String(100))  # 'Employee Dashboard Key'

    permissions = db.Column(db.JSON, default=['read'])  # ['read', 'write', 'admin']

    last_used_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<APIKey {self.key_prefix}...>'

    def to_dict(self):
        return {
            'id': self.id,
            'key_prefix': self.key_prefix,
            'name': self.name,
            'permissions': self.permissions,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'is_active': self.is_active
        }
