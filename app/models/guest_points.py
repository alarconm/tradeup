"""
Guest Points Model

Stores points earned by non-member customers that can be claimed
when they create an account.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from ..extensions import db


class GuestPoints(db.Model):
    """
    Points earned by guest customers (not yet members).

    These points are stored by email and can be claimed when the
    guest creates a membership account.
    """
    __tablename__ = 'guest_points'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    # Guest identification
    email = db.Column(db.String(255), nullable=False)
    shopify_customer_id = db.Column(db.String(50))  # If available

    # Points info
    points = db.Column(db.Integer, nullable=False)
    source_type = db.Column(db.String(50), nullable=False)  # purchase, referral, etc.
    source_id = db.Column(db.String(100))  # Order ID, etc.
    description = db.Column(db.String(500))

    # Order details (for purchases)
    order_number = db.Column(db.String(50))
    order_total = db.Column(db.Numeric(10, 2))

    # Status
    status = db.Column(db.String(20), default='pending')  # pending, claimed, expired
    claimed_by_member_id = db.Column(db.Integer, db.ForeignKey('members.id'))
    claimed_at = db.Column(db.DateTime)

    # Expiration
    expires_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        db.Index('ix_guest_points_tenant_email', 'tenant_id', 'email'),
        db.Index('ix_guest_points_tenant_status', 'tenant_id', 'status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'points': self.points,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'description': self.description,
            'order_number': self.order_number,
            'order_total': float(self.order_total) if self.order_total else None,
            'status': self.status,
            'claimed_by_member_id': self.claimed_by_member_id,
            'claimed_at': self.claimed_at.isoformat() if self.claimed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def create_guest_points(
        cls,
        tenant_id: int,
        email: str,
        points: int,
        source_type: str,
        source_id: str = None,
        description: str = None,
        order_number: str = None,
        order_total: Decimal = None,
        shopify_customer_id: str = None,
        expiry_days: int = 90
    ):
        """Create a new guest points entry."""
        entry = cls(
            tenant_id=tenant_id,
            email=email.lower(),
            points=points,
            source_type=source_type,
            source_id=source_id,
            description=description,
            order_number=order_number,
            order_total=order_total,
            shopify_customer_id=shopify_customer_id,
            status='pending',
            expires_at=datetime.utcnow() + timedelta(days=expiry_days) if expiry_days else None,
        )
        db.session.add(entry)
        db.session.commit()
        return entry

    @classmethod
    def get_pending_points_for_email(cls, tenant_id: int, email: str):
        """Get all pending points for an email."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            email=email.lower(),
            status='pending'
        ).filter(
            (cls.expires_at.is_(None)) | (cls.expires_at > datetime.utcnow())
        ).all()

    @classmethod
    def get_total_pending_points(cls, tenant_id: int, email: str) -> int:
        """Get total pending points for an email."""
        entries = cls.get_pending_points_for_email(tenant_id, email)
        return sum(e.points for e in entries)

    @classmethod
    def claim_points_for_member(cls, tenant_id: int, email: str, member_id: int) -> tuple:
        """
        Claim all pending points for a member.
        Returns tuple of (total_claimed, entries_claimed).
        """
        entries = cls.get_pending_points_for_email(tenant_id, email)
        total_claimed = 0
        claimed_count = 0

        for entry in entries:
            entry.status = 'claimed'
            entry.claimed_by_member_id = member_id
            entry.claimed_at = datetime.utcnow()
            total_claimed += entry.points
            claimed_count += 1

        if claimed_count > 0:
            db.session.commit()

        return total_claimed, claimed_count
