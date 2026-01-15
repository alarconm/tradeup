"""
Guest Points Service

Manages points for non-member (guest) customers.
Points can be earned on purchases and claimed when they create an account.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List

from app import db
from app.models.guest_points import GuestPoints
from app.models.member import Member


class GuestPointsService:
    """Service for managing guest checkout points."""

    def __init__(self, tenant_id: int, settings: Optional[Dict] = None):
        self.tenant_id = tenant_id
        self.settings = settings or {}

    def get_guest_points_settings(self) -> Dict[str, Any]:
        """Get guest points settings for the tenant."""
        guest_settings = self.settings.get('guest_points', {})
        return {
            'enabled': guest_settings.get('enabled', False),
            'points_per_dollar': guest_settings.get('points_per_dollar', 1),
            'expiry_days': guest_settings.get('expiry_days', 90),
            'min_order_value': guest_settings.get('min_order_value', 0),
            'welcome_message': guest_settings.get('welcome_message',
                'You earned {points} points! Create an account to claim them.'),
        }

    def is_guest_points_enabled(self) -> bool:
        """Check if guest points are enabled."""
        return self.get_guest_points_settings()['enabled']

    def award_guest_points(
        self,
        email: str,
        points: int,
        source_type: str,
        source_id: str = None,
        description: str = None,
        order_number: str = None,
        order_total: Decimal = None,
        shopify_customer_id: str = None,
    ) -> Dict[str, Any]:
        """
        Award points to a guest customer.

        Args:
            email: Customer email
            points: Number of points to award
            source_type: Source of points (purchase, referral, etc.)
            source_id: Reference ID (order ID, etc.)
            description: Human-readable description
            order_number: Shopify order number
            order_total: Order total amount
            shopify_customer_id: Shopify customer ID if available

        Returns:
            Dict with the created entry and summary
        """
        if not self.is_guest_points_enabled():
            return {'success': False, 'error': 'Guest points not enabled'}

        if points <= 0:
            return {'success': False, 'error': 'Points must be positive'}

        settings = self.get_guest_points_settings()

        # Check if customer is already a member
        existing_member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=email.lower()
        ).first()

        if existing_member:
            return {
                'success': False,
                'error': 'Customer is already a member',
                'member_id': existing_member.id
            }

        # Create guest points entry
        entry = GuestPoints.create_guest_points(
            tenant_id=self.tenant_id,
            email=email,
            points=points,
            source_type=source_type,
            source_id=source_id,
            description=description,
            order_number=order_number,
            order_total=order_total,
            shopify_customer_id=shopify_customer_id,
            expiry_days=settings['expiry_days'],
        )

        # Get total pending points for this email
        total_pending = GuestPoints.get_total_pending_points(self.tenant_id, email)

        return {
            'success': True,
            'entry': entry.to_dict(),
            'total_pending': total_pending,
            'message': settings['welcome_message'].format(points=points),
        }

    def calculate_guest_points_for_order(
        self,
        order_total: Decimal,
        order_id: str = None,
    ) -> Dict[str, Any]:
        """
        Calculate how many points a guest would earn for an order.

        Args:
            order_total: Order subtotal (before shipping/tax)
            order_id: Shopify order ID (for deduplication)

        Returns:
            Dict with calculated points breakdown
        """
        settings = self.get_guest_points_settings()

        if not settings['enabled']:
            return {'success': False, 'points': 0, 'error': 'Guest points not enabled'}

        # Check minimum order value
        if order_total < settings['min_order_value']:
            return {
                'success': False,
                'points': 0,
                'error': f'Order must be at least ${settings["min_order_value"]}'
            }

        # Calculate points
        points = int(float(order_total) * settings['points_per_dollar'])

        return {
            'success': True,
            'points': points,
            'order_total': float(order_total),
            'points_per_dollar': settings['points_per_dollar'],
        }

    def get_pending_points(self, email: str) -> Dict[str, Any]:
        """Get all pending points for an email."""
        entries = GuestPoints.get_pending_points_for_email(self.tenant_id, email)
        total = sum(e.points for e in entries)

        return {
            'success': True,
            'email': email,
            'total_points': total,
            'entries': [e.to_dict() for e in entries],
        }

    def claim_points(self, email: str, member_id: int) -> Dict[str, Any]:
        """
        Claim all pending points for a member.

        Called when a guest creates an account.

        Args:
            email: Customer email
            member_id: New member ID

        Returns:
            Dict with claimed points info
        """
        # Verify member exists and belongs to tenant
        member = Member.query.filter_by(
            id=member_id,
            tenant_id=self.tenant_id
        ).first()

        if not member:
            return {'success': False, 'error': 'Member not found'}

        # Claim all pending points
        total_claimed, entries_claimed = GuestPoints.claim_points_for_member(
            self.tenant_id, email, member_id
        )

        if total_claimed == 0:
            return {
                'success': True,
                'claimed': 0,
                'message': 'No pending points to claim',
            }

        # Add points to member's balance
        member.points_balance = (member.points_balance or 0) + total_claimed
        member.lifetime_points_earned = (member.lifetime_points_earned or 0) + total_claimed
        db.session.commit()

        return {
            'success': True,
            'claimed': total_claimed,
            'entries_claimed': entries_claimed,
            'new_balance': member.points_balance,
            'message': f'Successfully claimed {total_claimed} points!',
        }

    def get_guest_points_stats(self) -> Dict[str, Any]:
        """Get statistics about guest points."""
        pending_count = GuestPoints.query.filter_by(
            tenant_id=self.tenant_id,
            status='pending'
        ).count()

        claimed_count = GuestPoints.query.filter_by(
            tenant_id=self.tenant_id,
            status='claimed'
        ).count()

        expired_count = GuestPoints.query.filter_by(
            tenant_id=self.tenant_id,
            status='expired'
        ).count()

        # Sum pending points
        pending_total = db.session.query(
            db.func.sum(GuestPoints.points)
        ).filter_by(
            tenant_id=self.tenant_id,
            status='pending'
        ).scalar() or 0

        # Unique guest emails with pending points
        unique_guests = db.session.query(
            db.func.count(db.func.distinct(GuestPoints.email))
        ).filter_by(
            tenant_id=self.tenant_id,
            status='pending'
        ).scalar() or 0

        return {
            'success': True,
            'stats': {
                'pending_entries': pending_count,
                'pending_total_points': pending_total,
                'unique_guests': unique_guests,
                'claimed_entries': claimed_count,
                'expired_entries': expired_count,
            },
        }

    def expire_old_points(self) -> Dict[str, Any]:
        """
        Expire guest points that have passed their expiration date.
        Called by scheduled task.
        """
        expired_entries = GuestPoints.query.filter(
            GuestPoints.tenant_id == self.tenant_id,
            GuestPoints.status == 'pending',
            GuestPoints.expires_at.isnot(None),
            GuestPoints.expires_at < datetime.utcnow()
        ).all()

        expired_count = 0
        expired_points = 0

        for entry in expired_entries:
            entry.status = 'expired'
            expired_count += 1
            expired_points += entry.points

        if expired_count > 0:
            db.session.commit()

        return {
            'success': True,
            'expired_count': expired_count,
            'expired_points': expired_points,
        }
