"""
Member and MembershipTier models.
"""
from datetime import datetime
from decimal import Decimal
from ..extensions import db


class MembershipTier(db.Model):
    """
    Membership tier configuration.
    Each tenant can have custom tiers.
    """
    __tablename__ = 'membership_tiers'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    name = db.Column(db.String(50), nullable=False)  # 'Silver', 'Gold', 'Platinum'
    monthly_price = db.Column(db.Numeric(10, 2), nullable=False)
    yearly_price = db.Column(db.Numeric(10, 2))  # Optional yearly pricing

    # Shopify selling plan integration (for subscription products)
    shopify_selling_plan_id = db.Column(db.String(100))  # gid://shopify/SellingPlan/xxx

    # Trade-in bonus configuration
    # bonus_rate: Percentage of trade-in value given as bonus credit
    # e.g., 0.05 = 5% bonus, 0.10 = 10% bonus
    bonus_rate = db.Column(db.Numeric(5, 4), nullable=False)  # 0.05, 0.10, 0.15

    # Purchase cashback percentage (e.g., 1%, 2%, 3%)
    purchase_cashback_pct = db.Column(db.Numeric(5, 2), default=0)

    # Monthly store credit reward
    monthly_credit_amount = db.Column(db.Numeric(10, 2), default=0)

    # Credit expiration in days (null = no expiration)
    credit_expiration_days = db.Column(db.Integer)

    # Other benefits (JSON for flexibility)
    benefits = db.Column(db.JSON, default=dict)
    # Example: {"discount_percent": 10, "free_shipping_threshold": 50}

    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    members = db.relationship('Member', backref='tier', lazy='dynamic')

    def __repr__(self):
        return f'<MembershipTier {self.name}>'

    def to_dict(self):
        # Default tier colors based on name
        tier_colors = {
            'silver': '#9CA3AF',
            'gold': '#F59E0B',
            'platinum': '#6366F1',
            'bronze': '#CD7F32',
            'diamond': '#3B82F6',
        }
        default_color = tier_colors.get((self.name or '').lower(), '#6B7280')

        return {
            'id': self.id,
            'name': self.name,
            'color': default_color,  # Frontend-compatible color field
            'monthly_price': float(self.monthly_price),
            'yearly_price': float(self.yearly_price) if self.yearly_price else None,
            'bonus_rate': float(self.bonus_rate),
            'purchase_cashback_pct': float(self.purchase_cashback_pct or 0),
            'monthly_credit_amount': float(self.monthly_credit_amount or 0),
            'credit_expiration_days': self.credit_expiration_days,
            'benefits': self.benefits,
            'is_active': self.is_active,
            'display_order': self.display_order,
            'shopify_selling_plan_id': self.shopify_selling_plan_id,
            'active': self.is_active  # Alias for frontend compatibility
        }


class Member(db.Model):
    """
    Member of the TradeUp program.
    MUST be linked to a Shopify customer - no standalone members.
    """
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    tier_id = db.Column(db.Integer, db.ForeignKey('membership_tiers.id'))

    # Member identification - Shopify customer is REQUIRED
    member_number = db.Column(db.String(20), nullable=False)  # TU1001, TU1002, etc.
    shopify_customer_id = db.Column(db.String(50), nullable=False)  # Numeric ID (required)
    shopify_customer_gid = db.Column(db.String(100))  # Full GID: gid://shopify/Customer/123

    # Partner integration fields (e.g., ORB# from ORB Sports Cards)
    partner_customer_id = db.Column(db.String(50))  # e.g., "ORB1050"

    # Shopify subscription integration (for paid membership products)
    shopify_subscription_contract_id = db.Column(db.String(100))  # gid://shopify/SubscriptionContract/xxx
    subscription_status = db.Column(db.String(20), default='none')  # none, active, paused, cancelled

    # Tier assignment tracking (tiers can be staff-assigned OR earned)
    tier_assigned_by = db.Column(db.String(100))  # 'staff:email@example.com', 'system:purchase', 'system:activity'
    tier_assigned_at = db.Column(db.DateTime)
    tier_expires_at = db.Column(db.DateTime)  # NULL = never expires

    # Contact info (synced from Shopify customer)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255))
    phone = db.Column(db.String(50))

    # Membership status
    status = db.Column(db.String(20), default='pending')  # pending, active, paused, cancelled, expired
    membership_start_date = db.Column(db.Date)
    membership_end_date = db.Column(db.Date)  # NULL = ongoing

    # Running totals
    total_bonus_earned = db.Column(db.Numeric(12, 2), default=Decimal('0'))
    total_trade_ins = db.Column(db.Integer, default=0)
    total_trade_value = db.Column(db.Numeric(12, 2), default=Decimal('0'))

    # Referral program
    referral_code = db.Column(db.String(20), unique=True)  # Unique code for sharing
    referred_by_id = db.Column(db.Integer, db.ForeignKey('members.id'))  # Who referred this member
    referral_count = db.Column(db.Integer, default=0)  # How many people they've referred
    referral_earnings = db.Column(db.Numeric(12, 2), default=Decimal('0'))  # Total credit earned from referrals

    # Metadata
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    trade_in_batches = db.relationship('TradeInBatch', backref='member', lazy='dynamic')
    referred_by = db.relationship('Member', remote_side='Member.id', backref='referrals', foreign_keys=[referred_by_id])

    # Unique constraint per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'member_number', name='uq_tenant_member_number'),
        db.UniqueConstraint('tenant_id', 'email', name='uq_tenant_email'),
        db.UniqueConstraint('tenant_id', 'shopify_customer_id', name='uq_tenant_shopify_customer'),
    )

    def __repr__(self):
        return f'<Member {self.member_number}>'

    def to_dict(self, include_stats=False, include_subscription=False, include_referrals=False):
        # Split name into first/last for frontend compatibility
        name_parts = (self.name or '').split(' ', 1) if self.name else ['', '']
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        data = {
            'id': self.id,
            'member_number': self.member_number,
            'shopify_customer_id': self.shopify_customer_id,
            'shopify_customer_gid': self.shopify_customer_gid,
            'partner_customer_id': self.partner_customer_id,
            'email': self.email,
            'name': self.name,
            # Frontend-compatible name fields
            'first_name': first_name,
            'last_name': last_name,
            'phone': self.phone,
            'tier': self.tier.to_dict() if self.tier else None,
            'status': self.status,
            'membership_start_date': self.membership_start_date.isoformat() if self.membership_start_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            # Frontend-compatible stats fields at root level
            'trade_in_count': self.total_trade_ins or 0,
            'total_trade_in_value': float(self.total_trade_value or 0),
            'total_credits_issued': float(self.total_bonus_earned or 0),
            'last_trade_in_at': None  # TODO: Calculate from trade_in_batches if needed
        }

        if include_stats:
            data['stats'] = {
                'total_bonus_earned': float(self.total_bonus_earned or 0),
                'total_trade_ins': self.total_trade_ins or 0,
                'total_trade_value': float(self.total_trade_value or 0)
            }

        if include_subscription:
            data['subscription'] = {
                'shopify_subscription_contract_id': self.shopify_subscription_contract_id,
                'subscription_status': self.subscription_status,
                'tier_assigned_by': self.tier_assigned_by,
                'tier_assigned_at': self.tier_assigned_at.isoformat() if self.tier_assigned_at else None,
                'tier_expires_at': self.tier_expires_at.isoformat() if self.tier_expires_at else None
            }

        if include_referrals:
            data['referral'] = {
                'referral_code': self.referral_code,
                'referral_count': self.referral_count or 0,
                'referral_earnings': float(self.referral_earnings or 0),
                'referred_by': self.referred_by.member_number if self.referred_by else None
            }

        return data

    @staticmethod
    def generate_member_number(tenant_id: int) -> str:
        """Generate next member number for tenant."""
        last_member = Member.query.filter_by(tenant_id=tenant_id).order_by(
            Member.id.desc()
        ).first()

        if last_member:
            # Extract number from TU1001 -> 1001 (also handles legacy QF prefix)
            try:
                num_str = last_member.member_number.replace('TU', '').replace('QF', '')
                last_num = int(num_str)
                next_num = last_num + 1
            except (ValueError, AttributeError):
                next_num = 1001
        else:
            next_num = 1001

        return f'TU{next_num}'

    @staticmethod
    def generate_referral_code() -> str:
        """Generate a unique referral code."""
        import secrets
        import string
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(8))
            existing = Member.query.filter_by(referral_code=code).first()
            if not existing:
                return code

    def ensure_referral_code(self):
        """Ensure member has a referral code, generate if missing."""
        if not self.referral_code:
            self.referral_code = Member.generate_referral_code()
        return self.referral_code
