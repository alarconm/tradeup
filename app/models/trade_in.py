"""
Trade-in batch and item models.
"""
from datetime import datetime
from decimal import Decimal
from ..extensions import db


class TradeInBatch(db.Model):
    """
    A batch of items traded in by a member.
    All items in a batch should be listed together.
    """
    __tablename__ = 'trade_in_batches'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)  # Required for tenant isolation
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)  # Nullable for non-member trade-ins

    # Guest info for non-member trade-ins
    guest_name = db.Column(db.String(200))
    guest_email = db.Column(db.String(200))
    guest_phone = db.Column(db.String(50))

    # Batch identification
    batch_reference = db.Column(db.String(50), unique=True, nullable=False)  # TI-20260104-001
    trade_in_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Totals
    total_items = db.Column(db.Integer, default=0)
    total_trade_value = db.Column(db.Numeric(12, 2), default=Decimal('0'))

    # Status tracking
    status = db.Column(db.String(20), default='pending')  # pending, listed, completed, cancelled

    # Category (matches ORB categories: sports, pokemon, magic, riftbound, tcg_other, other)
    category = db.Column(db.String(50), default='other')

    # Completion and bonus
    completed_at = db.Column(db.DateTime)
    completed_by = db.Column(db.String(100))
    bonus_amount = db.Column(db.Numeric(10, 2), default=Decimal('0'))  # Tier bonus issued

    # Metadata
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(100))  # Employee who processed the trade-in
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items = db.relationship('TradeInItem', backref='batch', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<TradeInBatch {self.batch_reference}>'

    def to_dict(self, include_items=False):
        # Handle member vs guest info
        is_member = self.member_id is not None and self.member is not None
        customer_name = self.member.name if is_member else self.guest_name
        customer_tier = self.member.tier.name if is_member and self.member.tier else None

        data = {
            'id': self.id,
            'member_id': self.member_id,
            'is_member': is_member,
            'member_number': self.member.member_number if is_member else None,
            'member_name': customer_name,
            'member_tier': customer_tier,
            'guest_name': self.guest_name,
            'guest_email': self.guest_email,
            'guest_phone': self.guest_phone,
            'batch_reference': self.batch_reference,
            'trade_in_date': self.trade_in_date.isoformat(),
            'total_items': self.total_items,
            'total_trade_value': float(self.total_trade_value),
            'bonus_amount': float(self.bonus_amount) if self.bonus_amount else 0,
            'status': self.status,
            'category': self.category,
            'notes': self.notes,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'completed_by': self.completed_by
        }

        if include_items:
            data['items'] = [item.to_dict() for item in self.items]

        return data

    @staticmethod
    def generate_batch_reference(tenant_id: int) -> str:
        """Generate batch reference: TI-YYYYMMDD-###"""
        today = datetime.utcnow().strftime('%Y%m%d')
        prefix = f'TI-{today}-'

        # Find last batch with this prefix
        last_batch = TradeInBatch.query.filter(
            TradeInBatch.batch_reference.like(f'{prefix}%')
        ).order_by(TradeInBatch.id.desc()).first()

        if last_batch:
            try:
                last_num = int(last_batch.batch_reference.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1

        return f'{prefix}{next_num:03d}'


class TradeInItem(db.Model):
    """
    Individual item within a trade-in batch.
    Tracks the item through listing and sale.
    """
    __tablename__ = 'trade_in_items'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('trade_in_batches.id'), nullable=False)

    # Shopify product linkage
    shopify_product_id = db.Column(db.String(50))
    product_title = db.Column(db.String(500))
    product_sku = db.Column(db.String(100))

    # Trade-in values
    trade_value = db.Column(db.Numeric(10, 2), nullable=False)  # What shop paid for item
    market_value = db.Column(db.Numeric(10, 2))  # TCGPlayer market price at trade-in

    # Listing info
    listing_price = db.Column(db.Numeric(10, 2))
    listed_date = db.Column(db.DateTime)

    # Sale info (optional - for inventory tracking)
    sold_date = db.Column(db.DateTime)
    sold_price = db.Column(db.Numeric(10, 2))
    shopify_order_id = db.Column(db.String(50))
    days_to_sell = db.Column(db.Integer)  # Calculated when sold (for analytics)

    # Metadata
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<TradeInItem {self.id} - {self.product_title}>'

    def to_dict(self):
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'shopify_product_id': self.shopify_product_id,
            'product_title': self.product_title,
            'product_sku': self.product_sku,
            'trade_value': float(self.trade_value),
            'market_value': float(self.market_value) if self.market_value else None,
            'listing_price': float(self.listing_price) if self.listing_price else None,
            'listed_date': self.listed_date.isoformat() if self.listed_date else None,
            'sold_date': self.sold_date.isoformat() if self.sold_date else None,
            'sold_price': float(self.sold_price) if self.sold_price else None,
            'days_to_sell': self.days_to_sell
        }

    def calculate_days_to_sell(self) -> int | None:
        """Calculate days between listing and sale."""
        if not self.listed_date or not self.sold_date:
            return None
        delta = self.sold_date - self.listed_date
        return delta.days

    def calculate_profit(self) -> Decimal | None:
        """Calculate profit from sale."""
        if not self.sold_price or not self.trade_value:
            return None
        return self.sold_price - self.trade_value
