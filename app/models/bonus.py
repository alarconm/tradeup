"""
Bonus transaction model for audit trail.
"""
from datetime import datetime
from ..extensions import db


class BonusTransaction(db.Model):
    """
    Record of Quick Flip bonus issued to a member.
    Provides audit trail for all bonus credits.
    """
    __tablename__ = 'bonus_transactions'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    trade_in_item_id = db.Column(db.Integer, db.ForeignKey('trade_in_items.id'))

    # Transaction details
    bonus_amount = db.Column(db.Numeric(10, 2), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'credit', 'adjustment', 'reversal'

    # Shopify store credit reference
    store_credit_txn_id = db.Column(db.String(100))

    # Context
    notes = db.Column(db.Text)
    reason = db.Column(db.String(255))  # 'Quick Flip bonus - sold in 3 days'

    # Calculation details (for audit)
    sale_price = db.Column(db.Numeric(10, 2))
    trade_value = db.Column(db.Numeric(10, 2))
    profit = db.Column(db.Numeric(10, 2))
    bonus_rate = db.Column(db.Numeric(5, 4))
    days_to_sell = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))  # System or employee

    # Relationships
    trade_in_item = db.relationship('TradeInItem', backref='bonus_transaction')

    def __repr__(self):
        return f'<BonusTransaction ${self.bonus_amount} for Member {self.member_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'member_number': self.member.member_number if self.member else None,
            'trade_in_item_id': self.trade_in_item_id,
            'bonus_amount': float(self.bonus_amount),
            'transaction_type': self.transaction_type,
            'store_credit_txn_id': self.store_credit_txn_id,
            'notes': self.notes,
            'reason': self.reason,
            'calculation': {
                'sale_price': float(self.sale_price) if self.sale_price else None,
                'trade_value': float(self.trade_value) if self.trade_value else None,
                'profit': float(self.profit) if self.profit else None,
                'bonus_rate': float(self.bonus_rate) if self.bonus_rate else None,
                'days_to_sell': self.days_to_sell
            },
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by
        }
