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

    # Quick Flip bonus configuration
    bonus_rate = db.Column(db.Numeric(5, 4), nullable=False)  # 0.10, 0.20, 0.30
    quick_flip_days = db.Column(db.Integer, default=7)

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
        return {
            'id': self.id,
            'name': self.name,
            'monthly_price': float(self.monthly_price),
            'bonus_rate': float(self.bonus_rate),
            'quick_flip_days': self.quick_flip_days,
            'benefits': self.benefits,
            'is_active': self.is_active
        }


class Member(db.Model):
    """
    Member of the Quick Flip program.
    Linked to Shopify customer.
    """
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    tier_id = db.Column(db.Integer, db.ForeignKey('membership_tiers.id'))

    # Member identification
    member_number = db.Column(db.String(20), nullable=False)  # QF1001, QF1002, etc.
    shopify_customer_id = db.Column(db.String(50))

    # Contact info
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255))
    phone = db.Column(db.String(50))

    # Membership status
    status = db.Column(db.String(20), default='active')  # active, paused, cancelled, expired
    membership_start_date = db.Column(db.Date)
    membership_end_date = db.Column(db.Date)  # NULL = ongoing

    # Running totals
    total_bonus_earned = db.Column(db.Numeric(12, 2), default=Decimal('0'))
    total_trade_ins = db.Column(db.Integer, default=0)
    total_trade_value = db.Column(db.Numeric(12, 2), default=Decimal('0'))

    # Metadata
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    trade_in_batches = db.relationship('TradeInBatch', backref='member', lazy='dynamic')
    bonus_transactions = db.relationship('BonusTransaction', backref='member', lazy='dynamic')

    # Unique constraint per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'member_number', name='uq_tenant_member_number'),
        db.UniqueConstraint('tenant_id', 'email', name='uq_tenant_email'),
    )

    def __repr__(self):
        return f'<Member {self.member_number}>'

    def to_dict(self, include_stats=False):
        data = {
            'id': self.id,
            'member_number': self.member_number,
            'shopify_customer_id': self.shopify_customer_id,
            'email': self.email,
            'name': self.name,
            'phone': self.phone,
            'tier': self.tier.to_dict() if self.tier else None,
            'status': self.status,
            'membership_start_date': self.membership_start_date.isoformat() if self.membership_start_date else None,
            'created_at': self.created_at.isoformat()
        }

        if include_stats:
            data['stats'] = {
                'total_bonus_earned': float(self.total_bonus_earned),
                'total_trade_ins': self.total_trade_ins,
                'total_trade_value': float(self.total_trade_value)
            }

        return data

    @staticmethod
    def generate_member_number(tenant_id: int) -> str:
        """Generate next member number for tenant."""
        last_member = Member.query.filter_by(tenant_id=tenant_id).order_by(
            Member.id.desc()
        ).first()

        if last_member:
            # Extract number from QF1001 -> 1001
            try:
                last_num = int(last_member.member_number.replace('QF', ''))
                next_num = last_num + 1
            except (ValueError, AttributeError):
                next_num = 1001
        else:
            next_num = 1001

        return f'QF{next_num}'
