"""
Trade-In Ledger Model - Simplified trade-in tracking.

A simple ledger for recording trade-in transactions without complex
item tracking or workflow states. Just records what was traded and
how it was paid (cash vs store credit).
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from ..extensions import db


class TradeInLedger(db.Model):
    """
    Simple trade-in ledger entry.

    Records a single trade-in transaction with optional categorization.
    Supports both members and guests. Tracks cash vs credit payment split.
    """
    __tablename__ = 'trade_in_ledger'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)

    # Customer - either a member or guest info
    member_id = Column(Integer, ForeignKey('members.id'), nullable=True, index=True)
    guest_name = Column(String(200), nullable=True)
    guest_email = Column(String(200), nullable=True)
    guest_phone = Column(String(50), nullable=True)

    # Trade details
    reference = Column(String(50), unique=True, nullable=False)  # TI-YYYYMMDD-###
    trade_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_value = Column(Numeric(12, 2), default=0, nullable=False)  # Total trade-in value
    cash_amount = Column(Numeric(12, 2), default=0, nullable=False)  # Amount paid in cash
    credit_amount = Column(Numeric(12, 2), default=0, nullable=False)  # Amount as store credit

    # Optional categorization
    category = Column(String(100), nullable=True)  # Manual category name
    collection_id = Column(String(100), nullable=True)  # Shopify collection GID
    collection_name = Column(String(200), nullable=True)  # Cached collection name
    notes = Column(Text, nullable=True)

    # Audit
    created_by = Column(String(100), nullable=True)  # Employee who processed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship('Tenant', backref='trade_ledger_entries')
    member = relationship('Member', backref='trade_ledger_entries')

    # Indexes for common queries
    __table_args__ = (
        Index('ix_trade_ledger_tenant_date', 'tenant_id', 'trade_date'),
        Index('ix_trade_ledger_tenant_category', 'tenant_id', 'category'),
    )

    @staticmethod
    def generate_reference(tenant_id: int) -> str:
        """
        Generate a unique reference number for a trade-in entry.
        Format: TI-YYYYMMDD-### (e.g., TI-20260111-001)
        """
        today = datetime.utcnow().strftime('%Y%m%d')
        prefix = f'TI-{today}-'

        # Find highest number for today
        last_entry = (
            TradeInLedger.query
            .filter(
                TradeInLedger.tenant_id == tenant_id,
                TradeInLedger.reference.like(f'{prefix}%')
            )
            .order_by(TradeInLedger.reference.desc())
            .first()
        )

        if last_entry:
            try:
                last_num = int(last_entry.reference.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1

        return f'{prefix}{next_num:03d}'

    def to_dict(self) -> dict:
        """Serialize ledger entry to dictionary."""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'member_id': self.member_id,
            'member_name': self.member.name if self.member else None,
            'member_email': self.member.email if self.member else None,
            'guest_name': self.guest_name,
            'guest_email': self.guest_email,
            'guest_phone': self.guest_phone,
            'customer_name': self.member.name if self.member else self.guest_name,
            'customer_email': self.member.email if self.member else self.guest_email,
            'reference': self.reference,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'total_value': float(self.total_value or 0),
            'cash_amount': float(self.cash_amount or 0),
            'credit_amount': float(self.credit_amount or 0),
            'category': self.category,
            'collection_id': self.collection_id,
            'collection_name': self.collection_name,
            'notes': self.notes,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<TradeInLedger {self.reference}>'
