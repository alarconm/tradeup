"""
Points transaction model for TradeUp rewards.
"""
from datetime import datetime
from ..extensions import db


class PointsTransaction(db.Model):
    """
    Tracks all points earned, redeemed, and adjusted.

    Used for:
    - Order points earnings
    - Referral bonuses
    - Points redemptions
    - Admin adjustments
    - Reversals
    """
    __tablename__ = 'points_transactions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)

    # Transaction details
    points = db.Column(db.Integer, nullable=False)  # Positive for earn, negative for spend/adjust
    transaction_type = db.Column(db.String(50), nullable=False)  # earn, redeem, adjustment, expire

    # Source tracking
    source = db.Column(db.String(50))  # order, referral, admin, promotion, order_cancelled
    reference_id = db.Column(db.String(100))  # Shopify order ID, etc.
    reference_type = db.Column(db.String(50))  # shopify_order, referral, etc.
    description = db.Column(db.String(500))

    # For reversals
    related_transaction_id = db.Column(db.Integer, db.ForeignKey('points_transactions.id'))
    reversed_at = db.Column(db.DateTime)
    reversed_reason = db.Column(db.String(200))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='points_transactions')
    member = db.relationship('Member', backref='points_transactions')
    related_transaction = db.relationship('PointsTransaction', remote_side=[id])

    def __repr__(self):
        return f'<PointsTransaction {self.id}: {self.points} pts for member {self.member_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'points': self.points,
            'transaction_type': self.transaction_type,
            'source': self.source,
            'reference_id': self.reference_id,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class StoreCreditTransaction(db.Model):
    """
    Tracks store credit balance changes.

    Used for:
    - Trade-in credits
    - Quick Flip bonuses
    - Manual credits
    - Redemptions at checkout
    """
    __tablename__ = 'store_credit_transactions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)

    # Transaction details
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # Positive for credit, negative for debit
    balance_after = db.Column(db.Numeric(10, 2))  # Balance after this transaction
    transaction_type = db.Column(db.String(50), nullable=False)  # credit, debit, adjustment

    # Source tracking
    source = db.Column(db.String(50))  # trade_in, quick_flip_bonus, admin, checkout
    reference_id = db.Column(db.String(100))
    reference_type = db.Column(db.String(50))
    description = db.Column(db.String(500))

    # For reversals
    related_transaction_id = db.Column(db.Integer, db.ForeignKey('store_credit_transactions.id'))
    reversed_at = db.Column(db.DateTime)
    reversed_reason = db.Column(db.String(200))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))  # user_id or 'system'

    # Relationships
    tenant = db.relationship('Tenant', backref='store_credit_transactions')
    member = db.relationship('Member', backref='store_credit_transactions')
    related_transaction = db.relationship('StoreCreditTransaction', remote_side=[id])

    def __repr__(self):
        return f'<StoreCreditTransaction {self.id}: ${self.amount} for member {self.member_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'amount': float(self.amount),
            'balance_after': float(self.balance_after) if self.balance_after else None,
            'transaction_type': self.transaction_type,
            'source': self.source,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
