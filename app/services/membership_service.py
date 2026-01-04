"""
Membership service for managing members and tiers.
"""
from datetime import date
from typing import Optional
from ..extensions import db
from ..models import Member, MembershipTier


class MembershipService:
    """Service for membership operations."""

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def create_member(
        self,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        tier_id: Optional[int] = None,
        shopify_customer_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Member:
        """
        Create a new member.

        Args:
            email: Member email address
            name: Member name
            phone: Member phone number
            tier_id: Membership tier ID
            shopify_customer_id: Shopify customer ID
            notes: Internal notes

        Returns:
            Created Member object

        Raises:
            ValueError: If email already exists for tenant
        """
        # Check for duplicate email
        existing = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=email
        ).first()

        if existing:
            raise ValueError(f'Member with email {email} already exists')

        # Generate member number
        member_number = Member.generate_member_number(self.tenant_id)

        member = Member(
            tenant_id=self.tenant_id,
            member_number=member_number,
            email=email,
            name=name,
            phone=phone,
            tier_id=tier_id,
            shopify_customer_id=shopify_customer_id,
            status='active',
            membership_start_date=date.today(),
            notes=notes
        )

        db.session.add(member)
        db.session.commit()

        return member

    def get_member_by_number(self, member_number: str) -> Optional[Member]:
        """Get member by member number."""
        # Normalize member number
        if not member_number.upper().startswith('QF'):
            member_number = f'QF{member_number}'

        return Member.query.filter_by(
            tenant_id=self.tenant_id,
            member_number=member_number.upper()
        ).first()

    def get_member_by_email(self, email: str) -> Optional[Member]:
        """Get member by email."""
        return Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=email
        ).first()

    def get_member_by_shopify_id(self, shopify_customer_id: str) -> Optional[Member]:
        """Get member by Shopify customer ID."""
        return Member.query.filter_by(
            tenant_id=self.tenant_id,
            shopify_customer_id=shopify_customer_id
        ).first()

    def update_tier(self, member_id: int, tier_id: int) -> Member:
        """Update member's tier."""
        member = Member.query.get(member_id)
        if not member or member.tenant_id != self.tenant_id:
            raise ValueError('Member not found')

        tier = MembershipTier.query.get(tier_id)
        if not tier or tier.tenant_id != self.tenant_id:
            raise ValueError('Tier not found')

        member.tier_id = tier_id
        db.session.commit()

        return member

    def cancel_membership(self, member_id: int, reason: Optional[str] = None) -> Member:
        """Cancel a membership."""
        member = Member.query.get(member_id)
        if not member or member.tenant_id != self.tenant_id:
            raise ValueError('Member not found')

        member.status = 'cancelled'
        member.membership_end_date = date.today()

        if reason:
            member.notes = f'{member.notes or ""}\nCancelled: {reason}'.strip()

        db.session.commit()

        return member

    def pause_membership(self, member_id: int) -> Member:
        """Pause a membership."""
        member = Member.query.get(member_id)
        if not member or member.tenant_id != self.tenant_id:
            raise ValueError('Member not found')

        member.status = 'paused'
        db.session.commit()

        return member

    def resume_membership(self, member_id: int) -> Member:
        """Resume a paused membership."""
        member = Member.query.get(member_id)
        if not member or member.tenant_id != self.tenant_id:
            raise ValueError('Member not found')

        if member.status != 'paused':
            raise ValueError('Member is not paused')

        member.status = 'active'
        db.session.commit()

        return member

    def get_default_tier(self) -> Optional[MembershipTier]:
        """Get the default (lowest) tier for tenant."""
        return MembershipTier.query.filter_by(
            tenant_id=self.tenant_id,
            is_active=True
        ).order_by(MembershipTier.display_order).first()

    def setup_default_tiers(self):
        """Set up default membership tiers for a new tenant."""
        default_tiers = [
            {
                'name': 'Silver',
                'monthly_price': 10.00,
                'bonus_rate': 0.10,
                'quick_flip_days': 7,
                'benefits': {'discount_percent': 5},
                'display_order': 1
            },
            {
                'name': 'Gold',
                'monthly_price': 25.00,
                'bonus_rate': 0.20,
                'quick_flip_days': 7,
                'benefits': {'discount_percent': 10, 'free_shipping_threshold': 50},
                'display_order': 2
            },
            {
                'name': 'Platinum',
                'monthly_price': 50.00,
                'bonus_rate': 0.30,
                'quick_flip_days': 7,
                'benefits': {'discount_percent': 15, 'free_shipping': True},
                'display_order': 3
            }
        ]

        for tier_data in default_tiers:
            tier = MembershipTier(tenant_id=self.tenant_id, **tier_data)
            db.session.add(tier)

        db.session.commit()
