"""
Store Credit Service for TradeUp.

ARCHITECTURE: Shopify is the SINGLE SOURCE OF TRUTH for store credit balances.

This service:
- Issues credit to Shopify FIRST (fails if Shopify fails)
- Maintains a ledger (StoreCreditLedger) as an audit trail of what TradeUp issued
- Tracks stats (total_earned, trade_in_earned, etc.) for analytics
- Does NOT maintain local balance - always fetches from Shopify

Handles:
- Credit issuance (trade-ins, cashback, promotions)
- Debit operations (manual deductions)
- Promotion application
- Bulk operations
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from flask import current_app

from ..extensions import db
from ..models.member import Member
from ..models.promotions import (
    Promotion,
    StoreCreditLedger,
    MemberCreditBalance,
    BulkCreditOperation,
    TierConfiguration,
    CreditEventType,
    TIER_CASHBACK,
)
from .shopify_client import ShopifyClient


class StoreCreditService:
    """
    Centralized store credit management.

    Shopify native store credit is the source of truth for balances.
    TradeUp maintains a ledger for audit trail and stats for analytics.
    """

    def get_member_stats(self, member_id: int) -> MemberCreditBalance:
        """
        Get or create member's credit stats record (for tracking what TradeUp issued).

        NOTE: This does NOT contain the real balance. Use get_shopify_balance() for that.
        """
        stats = MemberCreditBalance.query.filter_by(member_id=member_id).first()
        if not stats:
            stats = MemberCreditBalance(member_id=member_id)
            db.session.add(stats)
            db.session.commit()
        return stats

    def get_shopify_balance(self, member: Member) -> Dict[str, Any]:
        """
        Get the real store credit balance from Shopify (source of truth).

        Args:
            member: Member with shopify_customer_id

        Returns:
            Dict with balance, currency, account_id
        """
        if not member.shopify_customer_id:
            return {'balance': 0, 'currency': 'USD', 'account_id': None}

        try:
            shopify_client = ShopifyClient(member.tenant_id)
            return shopify_client.get_store_credit_balance(member.shopify_customer_id)
        except Exception as e:
            current_app.logger.error(f"Error fetching Shopify balance for member {member.id}: {e}")
            return {'balance': 0, 'currency': 'USD', 'account_id': None, 'error': str(e)}

    def get_member_balance(self, member_id: int) -> MemberCreditBalance:
        """
        Get member's credit stats (legacy method for compatibility).

        NOTE: The total_balance/available_balance fields are deprecated.
        Use get_shopify_balance() for the real balance from Shopify.
        """
        return self.get_member_stats(member_id)

    def add_credit(
        self,
        member_id: int,
        amount: Decimal,
        event_type: str,
        description: str,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        source_reference: Optional[str] = None,
        promotion_id: Optional[int] = None,
        channel: Optional[str] = None,
        created_by: str = 'system',
        sync_to_shopify: bool = True,
        expires_at: Optional[datetime] = None,
    ) -> StoreCreditLedger:
        """
        Add credit to member's store credit account.

        SHOPIFY-FIRST: Writes to Shopify first. If Shopify fails, operation fails.
        Only creates ledger entry after Shopify succeeds.
        """
        member = Member.query.get(member_id)
        if not member:
            raise ValueError(f"Member {member_id} not found")

        # Get promotion name if applicable
        promotion_name = None
        if promotion_id:
            promotion = Promotion.query.get(promotion_id)
            if promotion:
                promotion_name = promotion.name

        shopify_result = None
        new_balance = Decimal('0')

        # STEP 1: Write to Shopify FIRST (source of truth)
        if sync_to_shopify:
            if not member.shopify_customer_id:
                raise ValueError(
                    f"Member {member_id} has no Shopify customer ID - cannot issue store credit. "
                    f"The member must be linked to a Shopify customer account first."
                )

            try:
                shopify_client = ShopifyClient(member.tenant_id)
                shopify_result = shopify_client.add_store_credit(
                    customer_id=member.shopify_customer_id,
                    amount=float(amount),
                    note=description
                )

                if not shopify_result.get('success'):
                    raise ValueError("Shopify store credit operation failed")

                new_balance = Decimal(str(shopify_result.get('new_balance', 0)))
                current_app.logger.info(
                    f"Added ${amount} to Shopify for member {member.id}. "
                    f"New balance: ${new_balance:.2f}"
                )

            except Exception as e:
                current_app.logger.error(f"Shopify credit failed for member {member.id}: {e}")
                raise ValueError(f"Failed to add store credit: {e}")
        else:
            # sync_to_shopify=False is only for internal testing/migration
            current_app.logger.warning(
                f"Member {member_id} credit NOT synced to Shopify (sync_to_shopify=False)"
            )

        # STEP 2: Create ledger entry (audit trail) AFTER Shopify succeeds
        entry = StoreCreditLedger(
            member_id=member_id,
            event_type=event_type,
            amount=amount,
            balance_after=new_balance,
            description=description,
            source_type=source_type,
            source_id=source_id,
            source_reference=source_reference,
            promotion_id=promotion_id,
            promotion_name=promotion_name,
            channel=channel,
            created_by=created_by,
            expires_at=expires_at,
            synced_to_shopify=shopify_result is not None,
            shopify_credit_id=shopify_result.get('transaction_id') if shopify_result else None,
        )
        db.session.add(entry)

        # STEP 3: Update stats (what TradeUp has issued - for analytics)
        stats = self.get_member_stats(member_id)
        stats.total_earned = Decimal(str(stats.total_earned or 0)) + amount
        stats.last_credit_at = datetime.utcnow()

        # Update category-specific stats
        if event_type == CreditEventType.TRADE_IN.value:
            stats.trade_in_earned = Decimal(str(stats.trade_in_earned or 0)) + amount
        elif event_type == CreditEventType.PURCHASE_CASHBACK.value:
            stats.cashback_earned = Decimal(str(stats.cashback_earned or 0)) + amount
        elif event_type == CreditEventType.PROMOTION_BONUS.value:
            stats.promo_bonus_earned = Decimal(str(stats.promo_bonus_earned or 0)) + amount

        # Update member's running total for display in members list
        member.total_bonus_earned = Decimal(str(member.total_bonus_earned or 0)) + amount

        db.session.commit()

        # STEP 4: Trigger Shopify Flow event for credit issued
        if member.shopify_customer_id:
            try:
                from .flow_service import FlowService
                shopify_client = ShopifyClient(member.tenant_id)
                flow_svc = FlowService(member.tenant_id, shopify_client)
                flow_svc.trigger_credit_issued(
                    member_id=member.id,
                    member_number=member.member_number,
                    email=member.email,
                    amount=float(amount),
                    event_type=event_type,
                    description=description,
                    new_balance=float(new_balance),
                    shopify_customer_id=member.shopify_customer_id
                )
            except Exception as flow_err:
                # Flow triggers are non-critical
                current_app.logger.warning(f"Flow trigger error (non-blocking): {flow_err}")

        return entry

    def deduct_credit(
        self,
        member_id: int,
        amount: Decimal,
        description: str,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        created_by: str = 'system',
        sync_to_shopify: bool = True,
    ) -> StoreCreditLedger:
        """
        Deduct credit from member's store credit account (redemption).

        SHOPIFY-FIRST: Checks Shopify balance and debits Shopify first.
        Only creates ledger entry after Shopify succeeds.
        """
        member = Member.query.get(member_id)
        if not member:
            raise ValueError(f"Member {member_id} not found")

        shopify_result = None
        new_balance = Decimal('0')

        # STEP 1: Debit from Shopify FIRST (source of truth)
        if sync_to_shopify:
            if not member.shopify_customer_id:
                raise ValueError(
                    f"Member {member_id} has no Shopify customer ID - cannot deduct store credit. "
                    f"The member must be linked to a Shopify customer account first."
                )

            try:
                shopify_client = ShopifyClient(member.tenant_id)

                # Shopify's debit method already checks balance
                shopify_result = shopify_client.debit_store_credit(
                    customer_id=member.shopify_customer_id,
                    amount=float(amount),
                    note=description,
                )

                if not shopify_result.get('success'):
                    raise ValueError("Shopify store credit debit failed")

                new_balance = Decimal(str(shopify_result.get('new_balance', 0)))
                current_app.logger.info(
                    f"Debited ${amount} from Shopify for member {member.id}. "
                    f"New balance: ${new_balance:.2f}"
                )

            except Exception as e:
                current_app.logger.error(f"Shopify debit failed for member {member.id}: {e}")
                raise ValueError(f"Failed to deduct store credit: {e}")
        else:
            # sync_to_shopify=False is only for internal testing/migration
            current_app.logger.warning(
                f"Member {member_id} debit NOT synced to Shopify (sync_to_shopify=False)"
            )

        # STEP 2: Create ledger entry (audit trail) AFTER Shopify succeeds
        entry = StoreCreditLedger(
            member_id=member_id,
            event_type=CreditEventType.REDEMPTION.value,
            amount=-amount,  # Negative for deduction
            balance_after=new_balance,
            description=description,
            source_type=source_type,
            source_id=source_id,
            created_by=created_by,
            synced_to_shopify=shopify_result is not None,
            shopify_credit_id=shopify_result.get('transaction_id') if shopify_result else None,
        )
        db.session.add(entry)

        # STEP 3: Update stats
        stats = self.get_member_stats(member_id)
        stats.total_spent = Decimal(str(stats.total_spent or 0)) + amount
        stats.last_redemption_at = datetime.utcnow()

        db.session.commit()

        return entry

    def process_purchase_cashback(
        self,
        member_id: int,
        order_total: Decimal,
        order_id: str,
        order_name: str,
        channel: str = 'online',
        collection_ids: Optional[List[str]] = None,
        product_tags: Optional[List[str]] = None,
    ) -> Optional[StoreCreditLedger]:
        """
        Process cashback for a purchase.

        Calculates tier-based cashback plus any active promotions.
        Supports collection/tag filtering for category-specific bonuses.
        """
        member = Member.query.get(member_id)
        if not member or member.status != 'active':
            return None

        # Get cashback percentage from member's tier (MembershipTier model)
        if member.tier and member.tier.purchase_cashback_pct:
            base_cashback_pct = Decimal(str(member.tier.purchase_cashback_pct)) / 100
        else:
            # Fallback to legacy config or default
            tier_name = member.tier.name if member.tier else None
            tier_config = TierConfiguration.query.filter_by(tier_name=tier_name).first()
            if tier_config and tier_config.purchase_cashback_pct:
                base_cashback_pct = Decimal(str(tier_config.purchase_cashback_pct)) / 100
            else:
                base_cashback_pct = TIER_CASHBACK.get(tier_name, Decimal('0'))

        # Calculate base cashback
        base_cashback = order_total * base_cashback_pct

        # Check for active purchase cashback promotions
        promo_bonus = Decimal('0')
        applied_promo = None

        tier_name = member.tier.name if member.tier else None
        active_promos = self.get_active_promotions(
            promo_type='purchase_cashback',
            channel=channel,
            tier=tier_name,
        )

        for promo in active_promos:
            if promo.min_value and order_total < Decimal(str(promo.min_value)):
                continue

            # Check collection/tag restrictions if specified on promotion
            if collection_ids is not None and hasattr(promo, 'applies_to_collection'):
                if not any(promo.applies_to_collection(cid) for cid in collection_ids):
                    continue

            if product_tags is not None and hasattr(promo, 'applies_to_product_tag'):
                if not any(promo.applies_to_product_tag(tag) for tag in product_tags):
                    continue

            bonus = promo.calculate_bonus(order_total)
            if bonus > promo_bonus:
                promo_bonus = bonus
                applied_promo = promo

        total_cashback = base_cashback + promo_bonus

        if total_cashback <= 0:
            return None

        # Create credit entry
        description_parts = [f"{float(base_cashback_pct * 100):.0f}% cashback on order {order_name}"]
        if applied_promo:
            description_parts.append(f" + {applied_promo.name} bonus")

        entry = self.add_credit(
            member_id=member_id,
            amount=total_cashback,
            event_type=CreditEventType.PURCHASE_CASHBACK.value,
            description=' '.join(description_parts),
            source_type='order',
            source_id=order_id,
            source_reference=order_name,
            promotion_id=applied_promo.id if applied_promo else None,
            channel=channel,
        )

        # Increment promo usage
        if applied_promo:
            applied_promo.current_uses += 1
            db.session.commit()

        return entry

    def calculate_trade_in_bonus(
        self,
        member: Member,
        base_payout: Decimal,
        item_count: int,
        category_ids: List[int],
        channel: str = 'in_store',
    ) -> Tuple[Decimal, List[Dict[str, Any]]]:
        """
        Calculate total trade-in bonus from tier and promotions.

        Returns (bonus_amount, applied_promotions_list)
        """
        bonuses = []
        total_bonus = Decimal('0')
        tier_name = member.tier.name if member.tier else None

        # 1. Tier bonus - first try MembershipTier.bonus_rate, then TierConfiguration
        if member.tier and member.tier.bonus_rate:
            tier_bonus = base_payout * Decimal(str(member.tier.bonus_rate))
            total_bonus += tier_bonus
            bonuses.append({
                'source': 'tier',
                'name': f'{tier_name} Tier Bonus',
                'percent': float(member.tier.bonus_rate * 100),
                'amount': float(tier_bonus),
            })
        else:
            # Fallback to TierConfiguration
            tier_config = TierConfiguration.query.filter_by(tier_name=tier_name).first()
            if tier_config and tier_config.trade_in_bonus_pct:
                tier_bonus = base_payout * (Decimal(str(tier_config.trade_in_bonus_pct)) / 100)
                total_bonus += tier_bonus
                bonuses.append({
                    'source': 'tier',
                    'name': f'{tier_name} Tier Bonus',
                    'percent': float(tier_config.trade_in_bonus_pct),
                    'amount': float(tier_bonus),
                })

        # 2. Active promotions
        active_promos = self.get_active_promotions(
            promo_type='trade_in_bonus',
            channel=channel,
            tier=tier_name,
        )

        for promo in active_promos:
            # Check category restriction
            if promo.category_ids:
                import json
                allowed_cats = json.loads(promo.category_ids)
                if not any(cat_id in allowed_cats for cat_id in category_ids):
                    continue

            # Check minimum requirements
            if promo.min_items and item_count < promo.min_items:
                continue
            if promo.min_value and base_payout < Decimal(str(promo.min_value)):
                continue

            bonus = promo.calculate_bonus(base_payout)
            total_bonus += bonus
            bonuses.append({
                'source': 'promotion',
                'name': promo.name,
                'percent': float(promo.bonus_percent or 0),
                'amount': float(bonus),
                'promotion_id': promo.id,
            })

        return total_bonus, bonuses

    def get_active_promotions(
        self,
        promo_type: Optional[str] = None,
        channel: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> List[Promotion]:
        """
        Get currently active promotions with optional filters.
        """
        query = Promotion.query.filter(Promotion.active == True)

        if promo_type:
            query = query.filter(Promotion.promo_type == promo_type)

        now = datetime.utcnow()
        query = query.filter(
            Promotion.starts_at <= now,
            Promotion.ends_at >= now,
        )

        promos = query.order_by(Promotion.priority.desc()).all()

        # Filter by runtime conditions
        active = []
        for promo in promos:
            if not promo.is_active_now():
                continue
            if channel and not promo.applies_to_channel(channel):
                continue
            if tier and not promo.applies_to_tier(tier):
                continue
            active.append(promo)

        return active

    def execute_bulk_credit(
        self,
        operation_id: int,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a bulk credit operation.

        Returns summary of credits applied.
        """
        operation = BulkCreditOperation.query.get(operation_id)
        if not operation:
            raise ValueError("Operation not found")

        if operation.status != 'pending':
            raise ValueError(f"Operation already {operation.status}")

        # Build member query
        query = Member.query.filter(Member.status == 'active')

        if operation.tier_filter:
            tiers = operation.tier_filter.split(',')
            query = query.filter(Member.tier.in_(tiers))

        members = query.all()

        if dry_run:
            return {
                'member_count': len(members),
                'total_amount': float(Decimal(str(operation.amount_per_member)) * len(members)),
                'members': [{'id': m.id, 'email': m.email, 'tier': m.tier} for m in members[:10]],
            }

        # Execute
        operation.status = 'processing'
        operation.member_count = len(members)
        db.session.commit()

        try:
            total = Decimal('0')
            for member in members:
                self.add_credit(
                    member_id=member.id,
                    amount=Decimal(str(operation.amount_per_member)),
                    event_type=CreditEventType.BULK_CREDIT.value,
                    description=operation.description or operation.name,
                    source_type='bulk_operation',
                    source_id=str(operation.id),
                    created_by=operation.created_by,
                )
                total += Decimal(str(operation.amount_per_member))

            operation.total_amount = total
            operation.status = 'completed'
            operation.completed_at = datetime.utcnow()
            db.session.commit()

            return {
                'status': 'completed',
                'member_count': len(members),
                'total_amount': float(total),
            }

        except Exception as e:
            operation.status = 'failed'
            operation.error_message = str(e)[:500]
            db.session.commit()
            raise

    def get_member_credit_history(
        self,
        member_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get member's credit transaction history.

        Returns:
            - balance: Current balance from Shopify (source of truth)
            - stats: What TradeUp has issued (total_earned, trade_in_earned, etc.)
            - transactions: Ledger entries (audit trail)
        """
        member = Member.query.get(member_id)
        if not member:
            raise ValueError(f"Member {member_id} not found")

        query = StoreCreditLedger.query.filter_by(member_id=member_id)

        total = query.count()
        entries = query.order_by(
            StoreCreditLedger.created_at.desc()
        ).limit(limit).offset(offset).all()

        # Get stats (what TradeUp issued)
        stats = self.get_member_stats(member_id)

        # Get real balance from Shopify (source of truth)
        shopify_balance = self.get_shopify_balance(member)

        return {
            'balance': {
                'current_balance': shopify_balance.get('balance', 0),
                'currency': shopify_balance.get('currency', 'USD'),
                'account_id': shopify_balance.get('account_id'),
                # Stats from what TradeUp issued
                'total_earned': float(stats.total_earned or 0),
                'total_spent': float(stats.total_spent or 0),
                'trade_in_earned': float(stats.trade_in_earned or 0),
                'cashback_earned': float(stats.cashback_earned or 0),
                'promo_bonus_earned': float(stats.promo_bonus_earned or 0),
                'last_credit_at': stats.last_credit_at.isoformat() if stats.last_credit_at else None,
                'last_redemption_at': stats.last_redemption_at.isoformat() if stats.last_redemption_at else None,
            },
            'transactions': [e.to_dict() for e in entries],
            'total': total,
            'limit': limit,
            'offset': offset,
        }


    def issue_guest_store_credit(
        self,
        tenant_id: int,
        shopify_customer_id: str,
        customer_email: Optional[str],
        customer_name: Optional[str],
        amount: Decimal,
        description: str,
        promotion_id: Optional[int] = None,
        promotion_name: Optional[str] = None,
        order_id: Optional[str] = None,
        order_number: Optional[str] = None,
        order_total: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Issue store credit to a non-member via Shopify API.

        Used when promotions target 'all_customers' and a non-member
        makes a qualifying purchase. Credit goes directly to their
        Shopify account and is tracked in guest_credit_events.

        Args:
            tenant_id: Tenant ID
            shopify_customer_id: Shopify customer GID or numeric ID
            customer_email: Customer email for audit trail
            customer_name: Customer name for audit trail
            amount: Amount to credit
            description: Credit description (shown to customer)
            promotion_id: Optional promotion ID for tracking
            promotion_name: Optional promotion name for tracking
            order_id: Optional order ID that triggered this credit
            order_number: Optional order number for display
            order_total: Optional order total for audit

        Returns:
            Dict with success status, new_balance, transaction_id
        """
        from ..models.promotions import GuestCreditEvent

        # Issue credit to Shopify first
        try:
            shopify_client = ShopifyClient(tenant_id)
            shopify_result = shopify_client.add_store_credit(
                customer_id=shopify_customer_id,
                amount=float(amount),
                note=description
            )

            if not shopify_result.get('success'):
                current_app.logger.error(
                    f"Failed to issue guest credit to {shopify_customer_id}: {shopify_result}"
                )
                return {
                    'success': False,
                    'error': 'Shopify store credit operation failed'
                }

            new_balance = shopify_result.get('new_balance', 0)

        except Exception as e:
            current_app.logger.error(
                f"Error issuing guest store credit to {shopify_customer_id}: {e}"
            )
            return {
                'success': False,
                'error': str(e)
            }

        # Create audit trail record
        try:
            guest_event = GuestCreditEvent(
                tenant_id=tenant_id,
                shopify_customer_id=shopify_customer_id,
                customer_email=customer_email,
                customer_name=customer_name,
                amount=amount,
                description=description,
                promotion_id=promotion_id,
                promotion_name=promotion_name,
                order_id=order_id,
                order_number=order_number,
                order_total=order_total,
                synced_to_shopify=True,
                shopify_credit_id=shopify_result.get('transaction_id'),
            )
            db.session.add(guest_event)
            db.session.commit()

            current_app.logger.info(
                f"Issued ${amount} guest credit to {customer_email or shopify_customer_id} "
                f"(promotion: {promotion_name}, order: {order_number})"
            )

        except Exception as e:
            # Credit was issued, but audit trail failed - log and continue
            current_app.logger.error(
                f"Failed to create guest credit audit trail: {e}"
            )
            db.session.rollback()

        return {
            'success': True,
            'new_balance': new_balance,
            'transaction_id': shopify_result.get('transaction_id'),
            'amount': float(amount),
            'customer_email': customer_email,
        }

    def get_active_promotions_for_audience(
        self,
        tenant_id: int,
        audience: str,
        channel: Optional[str] = None,
        promo_type: Optional[str] = None,
    ) -> List[Promotion]:
        """
        Get active promotions filtered by audience type.

        Args:
            tenant_id: Tenant ID to filter by
            audience: 'members_only' or 'all_customers'
            channel: Optional channel filter ('pos', 'online', 'all')
            promo_type: Optional promotion type filter

        Returns:
            List of active promotions matching the criteria
        """
        from sqlalchemy import or_
        now = datetime.utcnow()

        # Build audience filter - handle NULL values for backwards compatibility
        # NULL or 'members_only' should both be treated as members_only
        if audience == 'members_only':
            audience_filter = or_(
                Promotion.audience == 'members_only',
                Promotion.audience.is_(None)
            )
        else:
            audience_filter = Promotion.audience == audience

        query = Promotion.query.filter(
            Promotion.tenant_id == tenant_id,
            Promotion.active == True,
            Promotion.starts_at <= now,
            Promotion.ends_at >= now,
            audience_filter,
        )

        if promo_type:
            query = query.filter(Promotion.promo_type == promo_type)

        promos = query.order_by(Promotion.priority.desc()).all()

        # Filter by runtime conditions (daily time windows, active days, etc.)
        active = []
        for promo in promos:
            if not promo.is_active_now():
                continue
            if channel and not promo.applies_to_channel(channel):
                continue
            active.append(promo)

        return active


# Singleton instance
store_credit_service = StoreCreditService()
