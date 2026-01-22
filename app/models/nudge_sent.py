"""
NudgeSent Model

Tracks sent nudges to prevent duplicate notifications to members.
Ensures members don't receive the same nudge type multiple times within a cooldown period.
"""

from datetime import datetime, timedelta
from typing import Optional, List
import uuid
from ..extensions import db


class NudgeSent(db.Model):
    """
    Tracks nudges sent to members for duplicate prevention.

    Each record represents a nudge that was sent to a member.
    Used to enforce cooldown periods between the same nudge type.
    """
    __tablename__ = 'nudges_sent'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)

    # Nudge identification
    nudge_type = db.Column(db.String(50), nullable=False, index=True)  # points_expiring, tier_progress, etc.

    # Context data (what triggered this nudge)
    context_data = db.Column(db.JSON, default=dict)  # e.g., {"expiring_points": 500, "expiration_date": "2026-02-01"}

    # Delivery tracking
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    delivery_method = db.Column(db.String(30), default='email')  # email, sms, push
    delivery_status = db.Column(db.String(30), default='sent')  # sent, delivered, failed, opened, clicked

    # Response tracking (if applicable)
    opened_at = db.Column(db.DateTime)
    clicked_at = db.Column(db.DateTime)
    converted_at = db.Column(db.DateTime)  # When member made a purchase after nudge

    # Conversion tracking
    order_id = db.Column(db.String(100))  # Shopify order ID if conversion occurred
    order_total = db.Column(db.Numeric(10, 2))  # Order total for ROI calculation
    tracking_id = db.Column(db.String(100), unique=True, index=True)  # Unique ID for tracking pixel/links

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('nudges_sent', lazy='dynamic'))
    member = db.relationship('Member', backref=db.backref('nudges_sent', lazy='dynamic'))

    # Indexes for common queries
    __table_args__ = (
        db.Index('ix_nudges_sent_member_type', 'member_id', 'nudge_type'),
        db.Index('ix_nudges_sent_tenant_type_date', 'tenant_id', 'nudge_type', 'sent_at'),
    )

    def __repr__(self):
        return f'<NudgeSent {self.nudge_type} to member {self.member_id} at {self.sent_at}>'

    def to_dict(self) -> dict:
        """Serialize nudge sent record to dictionary."""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'member_id': self.member_id,
            'nudge_type': self.nudge_type,
            'context_data': self.context_data or {},
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivery_method': self.delivery_method,
            'delivery_status': self.delivery_status,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
            'converted_at': self.converted_at.isoformat() if self.converted_at else None,
            'order_id': self.order_id,
            'order_total': float(self.order_total) if self.order_total else None,
            'tracking_id': self.tracking_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def was_recently_sent(
        cls,
        tenant_id: int,
        member_id: int,
        nudge_type: str,
        cooldown_days: int = 7
    ) -> bool:
        """
        Check if a nudge of this type was recently sent to this member.

        Args:
            tenant_id: The tenant ID
            member_id: The member ID
            nudge_type: The type of nudge (e.g., 'points_expiring')
            cooldown_days: Number of days before the same nudge can be sent again

        Returns:
            True if nudge was sent within cooldown period, False otherwise
        """
        cutoff = datetime.utcnow() - timedelta(days=cooldown_days)

        recent = cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.member_id == member_id,
            cls.nudge_type == nudge_type,
            cls.sent_at >= cutoff
        ).first()

        return recent is not None

    @classmethod
    def record_sent(
        cls,
        tenant_id: int,
        member_id: int,
        nudge_type: str,
        context_data: Optional[dict] = None,
        delivery_method: str = 'email'
    ) -> 'NudgeSent':
        """
        Record that a nudge was sent to a member.

        Args:
            tenant_id: The tenant ID
            member_id: The member ID
            nudge_type: The type of nudge sent
            context_data: Optional context data about what triggered the nudge
            delivery_method: How the nudge was delivered (email, sms, push)

        Returns:
            The created NudgeSent record
        """
        # Generate unique tracking ID for open/click/conversion tracking
        tracking_id = f"nudge_{tenant_id}_{member_id}_{nudge_type}_{uuid.uuid4().hex[:12]}"

        nudge_sent = cls(
            tenant_id=tenant_id,
            member_id=member_id,
            nudge_type=nudge_type,
            context_data=context_data or {},
            delivery_method=delivery_method,
            delivery_status='sent',
            sent_at=datetime.utcnow(),
            tracking_id=tracking_id,
        )
        db.session.add(nudge_sent)
        db.session.commit()
        return nudge_sent

    @classmethod
    def get_by_tracking_id(cls, tracking_id: str) -> Optional['NudgeSent']:
        """Get a nudge sent record by its tracking ID."""
        return cls.query.filter_by(tracking_id=tracking_id).first()

    @classmethod
    def get_member_nudge_history(
        cls,
        tenant_id: int,
        member_id: int,
        nudge_type: Optional[str] = None,
        limit: int = 50
    ) -> List['NudgeSent']:
        """
        Get nudge history for a member.

        Args:
            tenant_id: The tenant ID
            member_id: The member ID
            nudge_type: Optional filter by nudge type
            limit: Maximum number of records to return

        Returns:
            List of NudgeSent records
        """
        query = cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.member_id == member_id
        )

        if nudge_type:
            query = query.filter(cls.nudge_type == nudge_type)

        return query.order_by(cls.sent_at.desc()).limit(limit).all()

    @classmethod
    def get_recent_nudges_for_tenant(
        cls,
        tenant_id: int,
        nudge_type: Optional[str] = None,
        days: int = 7,
        limit: int = 100
    ) -> List['NudgeSent']:
        """
        Get recent nudges sent by a tenant.

        Args:
            tenant_id: The tenant ID
            nudge_type: Optional filter by nudge type
            days: Number of days to look back
            limit: Maximum number of records to return

        Returns:
            List of NudgeSent records
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        query = cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.sent_at >= cutoff
        )

        if nudge_type:
            query = query.filter(cls.nudge_type == nudge_type)

        return query.order_by(cls.sent_at.desc()).limit(limit).all()

    @classmethod
    def get_stats_for_tenant(
        cls,
        tenant_id: int,
        days: int = 30
    ) -> dict:
        """
        Get nudge statistics for a tenant.

        Args:
            tenant_id: The tenant ID
            days: Number of days to include in stats

        Returns:
            Dictionary with nudge statistics
        """
        from sqlalchemy import func

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Count by nudge type
        type_counts = db.session.query(
            cls.nudge_type,
            func.count(cls.id)
        ).filter(
            cls.tenant_id == tenant_id,
            cls.sent_at >= cutoff
        ).group_by(cls.nudge_type).all()

        # Count by delivery status
        status_counts = db.session.query(
            cls.delivery_status,
            func.count(cls.id)
        ).filter(
            cls.tenant_id == tenant_id,
            cls.sent_at >= cutoff
        ).group_by(cls.delivery_status).all()

        total = sum(count for _, count in type_counts)

        return {
            'total_sent': total,
            'by_type': {ntype: count for ntype, count in type_counts},
            'by_status': {status: count for status, count in status_counts},
            'period_days': days,
        }

    def mark_opened(self):
        """Mark this nudge as opened."""
        self.opened_at = datetime.utcnow()
        self.delivery_status = 'opened'
        db.session.commit()

    def mark_clicked(self):
        """Mark this nudge as clicked."""
        self.clicked_at = datetime.utcnow()
        self.delivery_status = 'clicked'
        if not self.opened_at:
            self.opened_at = datetime.utcnow()
        db.session.commit()

    def mark_converted(
        self,
        order_id: Optional[str] = None,
        order_total: Optional[float] = None
    ):
        """
        Mark this nudge as converted (member made a purchase).

        Args:
            order_id: Shopify order ID (optional)
            order_total: Order total for ROI calculation (optional)
        """
        self.converted_at = datetime.utcnow()
        self.delivery_status = 'converted'
        if order_id:
            self.order_id = order_id
        if order_total is not None:
            self.order_total = order_total
        if not self.opened_at:
            self.opened_at = datetime.utcnow()
        if not self.clicked_at:
            self.clicked_at = datetime.utcnow()
        db.session.commit()

    def mark_failed(self, error_message: Optional[str] = None):
        """Mark this nudge as failed to deliver."""
        self.delivery_status = 'failed'
        if error_message and self.context_data is None:
            self.context_data = {}
        if error_message:
            self.context_data['error'] = error_message
        db.session.commit()

    @classmethod
    def get_effectiveness_metrics(
        cls,
        tenant_id: int,
        nudge_type: Optional[str] = None,
        days: int = 30
    ) -> dict:
        """
        Get comprehensive effectiveness metrics for nudges.

        Args:
            tenant_id: The tenant ID
            nudge_type: Optional filter by nudge type
            days: Number of days to include in metrics

        Returns:
            Dictionary with open rate, click rate, conversion rate, and ROI metrics
        """
        from sqlalchemy import func
        from decimal import Decimal

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Base query
        query = cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.sent_at >= cutoff
        )

        if nudge_type:
            query = query.filter(cls.nudge_type == nudge_type)

        nudges = query.all()
        total_sent = len(nudges)

        if total_sent == 0:
            return {
                'period_days': days,
                'nudge_type': nudge_type,
                'total_sent': 0,
                'delivered': 0,
                'opened': 0,
                'clicked': 0,
                'converted': 0,
                'open_rate': 0.0,
                'click_rate': 0.0,
                'conversion_rate': 0.0,
                'click_to_open_rate': 0.0,
                'total_revenue': 0.0,
                'average_order_value': 0.0,
                'revenue_per_send': 0.0,
            }

        # Count by status
        delivered = sum(1 for n in nudges if n.delivery_status != 'failed')
        opened = sum(1 for n in nudges if n.opened_at)
        clicked = sum(1 for n in nudges if n.clicked_at)
        converted = sum(1 for n in nudges if n.converted_at)

        # Calculate revenue
        total_revenue = sum(
            float(n.order_total or 0)
            for n in nudges
            if n.converted_at and n.order_total
        )

        # Calculate rates
        open_rate = round(opened / delivered * 100, 2) if delivered > 0 else 0.0
        click_rate = round(clicked / delivered * 100, 2) if delivered > 0 else 0.0
        conversion_rate = round(converted / delivered * 100, 2) if delivered > 0 else 0.0
        click_to_open_rate = round(clicked / opened * 100, 2) if opened > 0 else 0.0
        avg_order_value = round(total_revenue / converted, 2) if converted > 0 else 0.0
        revenue_per_send = round(total_revenue / total_sent, 2) if total_sent > 0 else 0.0

        return {
            'period_days': days,
            'nudge_type': nudge_type,
            'total_sent': total_sent,
            'delivered': delivered,
            'opened': opened,
            'clicked': clicked,
            'converted': converted,
            'open_rate': open_rate,
            'click_rate': click_rate,
            'conversion_rate': conversion_rate,
            'click_to_open_rate': click_to_open_rate,
            'total_revenue': round(total_revenue, 2),
            'average_order_value': avg_order_value,
            'revenue_per_send': revenue_per_send,
        }

    @classmethod
    def get_metrics_by_type(
        cls,
        tenant_id: int,
        days: int = 30
    ) -> List[dict]:
        """
        Get effectiveness metrics broken down by nudge type.

        Args:
            tenant_id: The tenant ID
            days: Number of days to include in metrics

        Returns:
            List of metrics dictionaries, one per nudge type
        """
        from sqlalchemy import func

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get distinct nudge types
        types = db.session.query(
            cls.nudge_type
        ).filter(
            cls.tenant_id == tenant_id,
            cls.sent_at >= cutoff
        ).distinct().all()

        metrics = []
        for (nudge_type,) in types:
            type_metrics = cls.get_effectiveness_metrics(
                tenant_id=tenant_id,
                nudge_type=nudge_type,
                days=days
            )
            metrics.append(type_metrics)

        # Sort by total sent (descending)
        metrics.sort(key=lambda x: x['total_sent'], reverse=True)
        return metrics

    @classmethod
    def get_daily_metrics(
        cls,
        tenant_id: int,
        nudge_type: Optional[str] = None,
        days: int = 30
    ) -> List[dict]:
        """
        Get daily breakdown of nudge metrics for trending.

        Args:
            tenant_id: The tenant ID
            nudge_type: Optional filter by nudge type
            days: Number of days to include

        Returns:
            List of daily metrics dictionaries
        """
        from sqlalchemy import func, cast, Date

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Base query for daily aggregation
        query = db.session.query(
            func.date(cls.sent_at).label('date'),
            func.count(cls.id).label('sent'),
            func.sum(func.case((cls.opened_at.isnot(None), 1), else_=0)).label('opened'),
            func.sum(func.case((cls.clicked_at.isnot(None), 1), else_=0)).label('clicked'),
            func.sum(func.case((cls.converted_at.isnot(None), 1), else_=0)).label('converted'),
            func.sum(func.case((cls.order_total.isnot(None), cls.order_total), else_=0)).label('revenue'),
        ).filter(
            cls.tenant_id == tenant_id,
            cls.sent_at >= cutoff
        )

        if nudge_type:
            query = query.filter(cls.nudge_type == nudge_type)

        results = query.group_by(func.date(cls.sent_at)).order_by(func.date(cls.sent_at)).all()

        daily_metrics = []
        for row in results:
            sent = row.sent or 0
            opened = row.opened or 0
            clicked = row.clicked or 0
            converted = row.converted or 0
            revenue = float(row.revenue or 0)

            daily_metrics.append({
                'date': row.date.isoformat() if row.date else None,
                'sent': sent,
                'opened': opened,
                'clicked': clicked,
                'converted': converted,
                'revenue': round(revenue, 2),
                'open_rate': round(opened / sent * 100, 2) if sent > 0 else 0.0,
                'click_rate': round(clicked / sent * 100, 2) if sent > 0 else 0.0,
                'conversion_rate': round(converted / sent * 100, 2) if sent > 0 else 0.0,
            })

        return daily_metrics
