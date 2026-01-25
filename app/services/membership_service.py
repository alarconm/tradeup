"""
Membership service for managing members and tiers.
"""
import os
from datetime import date
from typing import Optional, Dict, Any, List
from flask import current_app
from sqlalchemy.orm import joinedload
from ..extensions import db
from ..models import Member, MembershipTier
from .shopify_client import ShopifyClient


def get_shopify_client() -> Optional[ShopifyClient]:
    """Create Shopify client from environment."""
    shop_domain = os.getenv('SHOPIFY_DOMAIN')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    if not shop_domain or not access_token:
        return None
    return ShopifyClient(shop_domain, access_token)


class MembershipService:
    """Service for membership operations."""

    # Tag prefixes for Shopify
    TIER_TAG_PREFIX = 'tu-tier-'
    MEMBER_TAG_PREFIX = 'tu-member-'

    def __init__(self, tenant_id: int, shopify_client: Optional[ShopifyClient] = None):
        self.tenant_id = tenant_id
        self.shopify_client = shopify_client or get_shopify_client()

    def enroll_shopify_customer(
        self,
        shopify_customer_id: str,
        tier_id: Optional[int] = None,
        partner_customer_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Member:
        """
        Enroll an existing Shopify customer as a TradeUp member.
        Pulls name/email/phone from Shopify - no manual input.

        Args:
            shopify_customer_id: Shopify customer ID (numeric, NOT gid)
            tier_id: Membership tier ID (optional, defaults to lowest tier)
            partner_customer_id: Partner ID like ORB# (optional)
            notes: Internal notes

        Returns:
            Created Member object

        Raises:
            ValueError: If customer already enrolled or not found in Shopify
        """
        # Check if already enrolled
        existing = Member.query.filter_by(
            tenant_id=self.tenant_id,
            shopify_customer_id=shopify_customer_id
        ).first()

        if existing:
            raise ValueError(f'Customer {shopify_customer_id} is already a member ({existing.member_number})')

        # Get customer info from Shopify (by ID, not search)
        if not self.shopify_client:
            raise ValueError('Shopify not configured')

        customer = self.shopify_client.get_customer_by_id(shopify_customer_id)
        if not customer:
            raise ValueError(f'Shopify customer {shopify_customer_id} not found')

        # Check for duplicate email
        existing_email = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer['email']
        ).first()

        if existing_email:
            raise ValueError(f"Customer email {customer['email']} already enrolled as {existing_email.member_number}")

        # Use default tier if not specified
        if not tier_id:
            default_tier = self.get_default_tier()
            tier_id = default_tier.id if default_tier else None

        # Extract ORB# from tags if not provided
        if not partner_customer_id and customer.get('orb_number'):
            partner_customer_id = customer['orb_number']

        # Generate member number
        member_number = Member.generate_member_number(self.tenant_id)

        member = Member(
            tenant_id=self.tenant_id,
            member_number=member_number,
            shopify_customer_id=customer['id'],
            shopify_customer_gid=customer['gid'],
            partner_customer_id=partner_customer_id,
            email=customer['email'],
            name=customer['name'],
            phone=customer.get('phone'),
            tier_id=tier_id,
            status='active',
            membership_start_date=date.today(),
            notes=notes
        )

        db.session.add(member)
        db.session.commit()

        # Sync tier tags to Shopify
        self.sync_member_tags(member)

        # Sync member data to Shopify customer metafields
        self.sync_member_metafields_to_shopify(member)

        # Trigger Shopify Flow event
        try:
            from .flow_service import FlowService
            flow_svc = FlowService(self.tenant_id, self.shopify_client)
            flow_svc.trigger_member_enrolled(
                member_id=member.id,
                member_number=member.member_number,
                email=member.email,
                tier_name=member.tier.name if member.tier else 'Bronze',
                shopify_customer_id=member.shopify_customer_id
            )
        except Exception as e:
            # Flow triggers are non-critical - log and continue
            current_app.logger.warning(f"Flow trigger error (non-blocking): {e}")

        return member

    def search_shopify_customers(self, query: str) -> List[Dict[str, Any]]:
        """
        Search Shopify customers and check enrollment status.

        Optimized to batch check enrollment status with a single query
        instead of N+1 queries.

        Args:
            query: Search query (name, email, phone, or ORB#)

        Returns:
            List of customers with is_member flag
        """
        if not self.shopify_client:
            raise ValueError('Shopify not configured')

        customers = self.shopify_client.search_customers(query, limit=20)

        if not customers:
            return []

        # Batch check enrollment status with a single query (optimized from N+1)
        customer_ids = [c['id'] for c in customers]
        existing_members = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.shopify_customer_id.in_(customer_ids)
        ).options(
            joinedload(Member.tier)  # Eager load tier to avoid N+1 on tier name
        ).all()

        # Build lookup dictionary for O(1) access
        member_lookup = {m.shopify_customer_id: m for m in existing_members}

        # Enrich customer data with membership info
        for customer in customers:
            existing = member_lookup.get(customer['id'])
            customer['is_member'] = existing is not None
            if existing:
                customer['member_id'] = existing.id
                customer['member_number'] = existing.member_number
                customer['member_tier'] = existing.tier.name if existing.tier else None

        return customers

    def create_member(
        self,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        tier_id: Optional[int] = None,
        shopify_customer_id: Optional[str] = None,
        shopify_customer_gid: Optional[str] = None,
        partner_customer_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Member:
        """
        Create a new member. REQUIRES Shopify customer ID.

        For easier enrollment, use enroll_shopify_customer() instead.

        Args:
            email: Member email address
            name: Member name
            phone: Member phone number
            tier_id: Membership tier ID
            shopify_customer_id: Shopify customer ID (REQUIRED)
            shopify_customer_gid: Full GID format (optional)
            partner_customer_id: Partner ID like ORB# (optional)
            notes: Internal notes

        Returns:
            Created Member object

        Raises:
            ValueError: If shopify_customer_id not provided or duplicate
        """
        # Shopify customer ID is REQUIRED
        if not shopify_customer_id:
            raise ValueError('Shopify customer ID is required. Use the customer search to find and enroll customers.')

        # Check for duplicate Shopify customer
        existing_shopify = Member.query.filter_by(
            tenant_id=self.tenant_id,
            shopify_customer_id=shopify_customer_id
        ).first()

        if existing_shopify:
            raise ValueError(f'Shopify customer {shopify_customer_id} is already enrolled as {existing_shopify.member_number}')

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
            shopify_customer_gid=shopify_customer_gid,
            partner_customer_id=partner_customer_id,
            status='active',
            membership_start_date=date.today(),
            notes=notes
        )

        db.session.add(member)
        db.session.commit()

        return member

    def get_member_by_number(self, member_number: str) -> Optional[Member]:
        """Get member by member number."""
        # Normalize member number - support both TU and legacy QF prefixes
        upper_num = member_number.upper()
        if not upper_num.startswith('TU') and not upper_num.startswith('QF'):
            member_number = f'TU{member_number}'
        else:
            member_number = upper_num

        return Member.query.filter_by(
            tenant_id=self.tenant_id,
            member_number=member_number
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
                'monthly_price': 0.00,  # Free tier
                'bonus_rate': 0.05,  # 5% trade-in bonus
                'benefits': {'discount_percent': 5},
                'display_order': 1
            },
            {
                'name': 'Gold',
                'monthly_price': 0.00,
                'bonus_rate': 0.10,  # 10% trade-in bonus
                'benefits': {'discount_percent': 10, 'free_shipping_threshold': 50},
                'display_order': 2
            },
            {
                'name': 'Platinum',
                'monthly_price': 0.00,
                'bonus_rate': 0.15,  # 15% trade-in bonus
                'benefits': {'discount_percent': 15, 'free_shipping': True},
                'display_order': 3
            }
        ]

        for tier_data in default_tiers:
            tier = MembershipTier(tenant_id=self.tenant_id, **tier_data)
            db.session.add(tier)

        db.session.commit()

    # ==================== Shopify Sync Methods ====================

    def link_shopify_customer(self, member: Member) -> Dict[str, Any]:
        """
        Link a member to their Shopify customer account by email.
        Also syncs their tier tag to the Shopify customer.

        Args:
            member: Member to link

        Returns:
            Dict with linking result
        """
        if not self.shopify_client:
            return {'success': False, 'error': 'Shopify not configured'}

        if member.shopify_customer_id:
            return {
                'success': True,
                'already_linked': True,
                'customer_id': member.shopify_customer_id
            }

        # Find customer by email
        customer = self.shopify_client.get_customer_by_email(member.email)
        if not customer:
            return {
                'success': False,
                'error': f'No Shopify customer found with email {member.email}'
            }

        # Link the customer
        member.shopify_customer_id = customer['id']
        db.session.commit()

        # Sync tier tags
        self.sync_member_tags(member)

        return {
            'success': True,
            'customer_id': customer['id'],
            'customer_name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        }

    def sync_member_tags(self, member: Member) -> Dict[str, Any]:
        """
        Sync member's tier tags to Shopify customer.
        Adds member number tag and tier-specific tag.

        Args:
            member: Member to sync

        Returns:
            Dict with sync result
        """
        if not self.shopify_client:
            return {'success': False, 'error': 'Shopify not configured'}

        if not member.shopify_customer_id:
            return {'success': False, 'error': 'Member not linked to Shopify'}

        tags_to_add = []

        # Add member number tag (e.g., tu-member-1001)
        # Remove TU or legacy QF prefix to get numeric portion
        member_num = member.member_number.upper().replace('TU', '').replace('QF', '')
        member_tag = f'{self.MEMBER_TAG_PREFIX}{member_num}'
        tags_to_add.append(member_tag)

        # Add tier tag if member has a tier (e.g., tu-tier-gold)
        if member.tier:
            tier_tag = f'{self.TIER_TAG_PREFIX}{member.tier.name.lower()}'
            tags_to_add.append(tier_tag)

        # Add tags to Shopify
        try:
            for tag in tags_to_add:
                self.shopify_client.add_customer_tag(member.shopify_customer_id, tag)

            return {
                'success': True,
                'tags_added': tags_to_add
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def sync_member_metafields_to_shopify(self, member: Member) -> Dict[str, Any]:
        """
        Sync member data to Shopify customer metafields.

        Creates/updates these metafields in the 'tradeup' namespace:
        - member_number: TradeUp member ID
        - tier: Current tier name
        - credit_balance: Store credit balance
        - trade_in_count: Total trade-ins
        - total_bonus_earned: Total bonus credits
        - status: active/paused/cancelled
        - joined_date: Membership start date

        Args:
            member: Member to sync

        Returns:
            Dict with sync result
        """
        if not self.shopify_client:
            return {'success': False, 'error': 'Shopify not configured'}

        if not member.shopify_customer_id:
            return {'success': False, 'error': 'Member not linked to Shopify'}

        try:
            # Get store credit balance from Shopify
            credit_balance = 0
            try:
                credit_result = self.shopify_client.get_store_credit_balance(
                    member.shopify_customer_id
                )
                if credit_result:
                    credit_balance = float(credit_result.get('balance', {}).get('amount', 0))
            except Exception:
                pass  # If credit fetch fails, use 0

            # Calculate trade-in stats
            from ..models.trade_in import TradeInBatch
            trade_in_count = TradeInBatch.query.filter_by(
                tenant_id=self.tenant_id,
                member_id=member.id
            ).count()

            # Calculate total bonus earned (sum of tier bonus on completed trade-ins)
            total_bonus = 0
            completed_batches = TradeInBatch.query.filter_by(
                tenant_id=self.tenant_id,
                member_id=member.id,
                status='completed'
            ).all()
            for batch in completed_batches:
                if batch.tier_bonus_amount:
                    total_bonus += float(batch.tier_bonus_amount)

            # Get loyalty mode settings from tenant
            from ..models.tenant import Tenant
            from ..utils.settings_defaults import get_settings_with_defaults
            tenant = Tenant.query.get(self.tenant_id)
            settings = get_settings_with_defaults(tenant.settings if tenant else {})
            loyalty_settings = settings.get('loyalty', {})
            loyalty_mode = loyalty_settings.get('mode', 'store_credit')

            # Get points balance for points mode
            points_balance = 0
            if loyalty_mode == 'points':
                from ..models.points import PointsTransaction
                from sqlalchemy import func
                points_result = db.session.query(
                    func.coalesce(func.sum(PointsTransaction.points), 0)
                ).filter(
                    PointsTransaction.member_id == member.id,
                    PointsTransaction.tenant_id == self.tenant_id
                ).scalar()
                points_balance = int(points_result) if points_result else 0

            # Get tier-specific earning info
            tier_cashback_pct = 0
            tier_earning_multiplier = 1.0
            if member.tier:
                # purchase_cashback_pct is the % back on purchases (e.g., 2 = 2%)
                tier_cashback_pct = float(member.tier.purchase_cashback_pct or 0)
                # For points mode, use bonus_rate as multiplier (e.g., 0.10 = 10% = 1.1x)
                # Convert bonus_rate to multiplier: 1.0 + bonus_rate
                tier_earning_multiplier = 1.0 + float(member.tier.bonus_rate or 0)

            # Sync to Shopify
            result = self.shopify_client.sync_member_metafields(
                customer_id=member.shopify_customer_id,
                member_number=member.member_number,
                tier_name=member.tier.name if member.tier else None,
                credit_balance=credit_balance,
                trade_in_count=trade_in_count,
                total_bonus_earned=total_bonus,
                joined_date=member.membership_start_date.isoformat() if member.membership_start_date else None,
                status=member.status or 'active',
                # New loyalty mode fields
                loyalty_mode=loyalty_mode,
                points_balance=points_balance,
                store_credit_balance=credit_balance,  # Same as credit_balance
                tier_cashback_pct=tier_cashback_pct,
                tier_earning_multiplier=tier_earning_multiplier
            )

            return result

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def remove_tier_tag(self, member: Member, tier_name: str) -> bool:
        """
        Remove a tier tag from Shopify customer.

        Args:
            member: Member whose tag to remove
            tier_name: Name of tier to remove

        Returns:
            True if successful
        """
        if not self.shopify_client or not member.shopify_customer_id:
            return False

        tag_to_remove = f'{self.TIER_TAG_PREFIX}{tier_name.lower()}'

        # We need to remove the tag via Shopify API
        # First get current tags, then update without this tag
        try:
            customer = self.shopify_client.get_customer_by_email(member.email)
            if customer:
                current_tags = customer.get('tags', [])
                new_tags = [t for t in current_tags if t != tag_to_remove]

                # Update customer with new tags
                mutation = """
                mutation customerUpdate($input: CustomerInput!) {
                    customerUpdate(input: $input) {
                        customer { id tags }
                        userErrors { field message }
                    }
                }
                """
                variables = {
                    'input': {
                        'id': member.shopify_customer_id,
                        'tags': new_tags
                    }
                }
                self.shopify_client._execute_query(mutation, variables)
                return True
        except Exception:
            pass
        return False

    def update_tier_with_sync(self, member_id: int, tier_id: int) -> Member:
        """
        Update member's tier and sync to Shopify.
        Removes old tier tag and adds new tier tag.

        Args:
            member_id: Member ID
            tier_id: New tier ID

        Returns:
            Updated member
        """
        member = Member.query.get(member_id)
        if not member or member.tenant_id != self.tenant_id:
            raise ValueError('Member not found')

        old_tier = member.tier
        new_tier = MembershipTier.query.get(tier_id)
        if not new_tier or new_tier.tenant_id != self.tenant_id:
            raise ValueError('Tier not found')

        # Update tier
        member.tier_id = tier_id
        db.session.commit()

        # Sync to Shopify
        if member.shopify_customer_id and self.shopify_client:
            # Remove old tier tag
            if old_tier:
                self.remove_tier_tag(member, old_tier.name)

            # Add new tier tag
            self.sync_member_tags(member)

        return member

    def sync_all_members(self) -> Dict[str, Any]:
        """
        Sync all active members to Shopify.
        Useful for initial sync or re-sync.

        Returns:
            Dict with sync results
        """
        if not self.shopify_client:
            return {'success': False, 'error': 'Shopify not configured'}

        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        results = {
            'total': len(members),
            'linked': 0,
            'synced': 0,
            'failed': 0,
            'errors': []
        }

        for member in members:
            try:
                # Link if not already linked
                if not member.shopify_customer_id:
                    link_result = self.link_shopify_customer(member)
                    if link_result.get('success'):
                        results['linked'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'member': member.member_number,
                            'error': link_result.get('error')
                        })
                        continue

                # Sync tags
                sync_result = self.sync_member_tags(member)
                if sync_result.get('success'):
                    results['synced'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'member': member.member_number,
                        'error': sync_result.get('error')
                    })

            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'member': member.member_number,
                    'error': str(e)
                })

        return results

    def get_shopify_customer_info(self, member: Member) -> Optional[Dict[str, Any]]:
        """
        Get Shopify customer info for a member.

        Args:
            member: Member to get info for

        Returns:
            Customer info or None
        """
        if not self.shopify_client or not member.shopify_customer_id:
            return None

        try:
            customer = self.shopify_client.get_customer_by_email(member.email)
            if customer:
                balance = self.shopify_client.get_store_credit_balance(customer['id'])
                return {
                    'id': customer['id'],
                    'name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                    'email': customer.get('email'),
                    'tags': customer.get('tags', []),
                    'store_credit_balance': balance['balance'],
                    'store_credit_currency': balance['currency']
                }
        except Exception:
            pass
        return None
