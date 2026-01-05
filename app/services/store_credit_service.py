"""
Store Credit Service for Quick Flip.

Handles all store credit operations:
- Credit issuance (trade-ins, cashback, promotions)
- Shopify native store credit sync
- Balance tracking
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
from .shopify_client import shopify_client


class StoreCreditService:
    """
    Centralized store credit management.
    """

    def get_member_balance(self, member_id: int) -> MemberCreditBalance:
        """
        Get or create member's credit balance record.
        """
        balance = MemberCreditBalance.query.filter_by(member_id=member_id).first()
        if not balance:
            balance = MemberCreditBalance(member_id=member_id)
            db.session.add(balance)
            db.session.commit()
        return balance

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
        Add credit to member's balance.

        Creates ledger entry, updates balance, and syncs to Shopify.
        """
        member = Member.query.get(member_id)
        if not member:
            raise ValueError(f"Member {member_id} not found")

        balance = self.get_member_balance(member_id)

        # Calculate new balance
        new_balance = Decimal(str(balance.total_balance or 0)) + amount

        # Get promotion name if applicable
        promotion_name = None
        if promotion_id:
            promotion = Promotion.query.get(promotion_id)
            if promotion:
                promotion_name = promotion.name

        # Create ledger entry
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
        )
        db.session.add(entry)

        # Update balance
        balance.total_balance = new_balance
        balance.available_balance = new_balance
        balance.total_earned = Decimal(str(balance.total_earned or 0)) + amount
        balance.last_credit_at = datetime.utcnow()

        # Update category-specific stats
        if event_type == CreditEventType.TRADE_IN.value:
            balance.trade_in_earned = Decimal(str(balance.trade_in_earned or 0)) + amount
        elif event_type == CreditEventType.PURCHASE_CASHBACK.value:
            balance.cashback_earned = Decimal(str(balance.cashback_earned or 0)) + amount
        elif event_type == CreditEventType.PROMOTION_BONUS.value:
            balance.promo_bonus_earned = Decimal(str(balance.promo_bonus_earned or 0)) + amount

        db.session.commit()

        # Sync to Shopify
        if sync_to_shopify and member.shopify_customer_id:
            self._sync_credit_to_shopify(entry, member)

        return entry

    def deduct_credit(
        self,
        member_id: int,
        amount: Decimal,
        description: str,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        created_by: str = 'system',
    ) -> StoreCreditLedger:
        """
        Deduct credit from member's balance (redemption).
        """
        balance = self.get_member_balance(member_id)

        if Decimal(str(balance.available_balance or 0)) < amount:
            raise ValueError("Insufficient credit balance")

        new_balance = Decimal(str(balance.total_balance or 0)) - amount

        entry = StoreCreditLedger(
            member_id=member_id,
            event_type=CreditEventType.REDEMPTION.value,
            amount=-amount,  # Negative for deduction
            balance_after=new_balance,
            description=description,
            source_type=source_type,
            source_id=source_id,
            created_by=created_by,
        )
        db.session.add(entry)

        balance.total_balance = new_balance
        balance.available_balance = new_balance
        balance.total_spent = Decimal(str(balance.total_spent or 0)) + amount
        balance.last_redemption_at = datetime.utcnow()

        db.session.commit()

        return entry

    def _sync_credit_to_shopify(self, entry: StoreCreditLedger, member: Member) -> bool:
        """
        Sync credit entry to Shopify native store credit.

        Uses Shopify's Store Credit API if available, otherwise metafield.
        """
        try:
            # Try native store credit first
            result = shopify_client.issue_store_credit(
                customer_id=member.shopify_customer_id,
                amount=float(entry.amount),
                note=entry.description,
            )

            if result.get('success'):
                entry.synced_to_shopify = True
                entry.shopify_credit_id = result.get('credit_id')
                db.session.commit()
                return True
            else:
                # Fall back to metafield approach
                return self._sync_via_metafield(entry, member)

        except Exception as e:
            current_app.logger.error(f"Shopify sync error: {e}")
            entry.sync_error = str(e)[:500]
            db.session.commit()
            return False

    def _sync_via_metafield(self, entry: StoreCreditLedger, member: Member) -> bool:
        """
        Fall back to metafield-based store credit tracking.
        """
        try:
            balance = self.get_member_balance(entry.member_id)
            result = shopify_client.set_customer_metafield(
                customer_id=member.shopify_customer_id,
                namespace='quick_flip',
                key='store_credit',
                value=str(float(balance.total_balance)),
                type='number_decimal'
            )
            entry.synced_to_shopify = result
            db.session.commit()
            return result
        except Exception as e:
            current_app.logger.error(f"Metafield sync error: {e}")
            return False

    def process_purchase_cashback(
        self,
        member_id: int,
        order_total: Decimal,
        order_id: str,
        order_name: str,
        channel: str = 'online',
    ) -> Optional[StoreCreditLedger]:
        """
        Process cashback for a purchase.

        Calculates tier-based cashback plus any active promotions.
        """
        member = Member.query.get(member_id)
        if not member or member.status != 'active':
            return None

        # Get tier configuration
        tier_config = TierConfiguration.query.filter_by(tier_name=member.tier).first()
        if not tier_config:
            # Use default
            base_cashback_pct = TIER_CASHBACK.get(member.tier, Decimal('0'))
        else:
            base_cashback_pct = Decimal(str(tier_config.purchase_cashback_pct)) / 100

        # Calculate base cashback
        base_cashback = order_total * base_cashback_pct

        # Check for active purchase cashback promotions
        promo_bonus = Decimal('0')
        applied_promo = None

        active_promos = self.get_active_promotions(
            promo_type='purchase_cashback',
            channel=channel,
            tier=member.tier,
        )

        for promo in active_promos:
            if promo.min_value and order_total < Decimal(str(promo.min_value)):
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

        # 1. Tier bonus
        tier_config = TierConfiguration.query.filter_by(tier_name=member.tier).first()
        if tier_config and tier_config.trade_in_bonus_pct:
            tier_bonus = base_payout * (Decimal(str(tier_config.trade_in_bonus_pct)) / 100)
            total_bonus += tier_bonus
            bonuses.append({
                'source': 'tier',
                'name': f'{member.tier} Tier Bonus',
                'percent': float(tier_config.trade_in_bonus_pct),
                'amount': float(tier_bonus),
            })

        # 2. Active promotions
        active_promos = self.get_active_promotions(
            promo_type='trade_in_bonus',
            channel=channel,
            tier=member.tier,
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
        """
        query = StoreCreditLedger.query.filter_by(member_id=member_id)

        total = query.count()
        entries = query.order_by(
            StoreCreditLedger.created_at.desc()
        ).limit(limit).offset(offset).all()

        balance = self.get_member_balance(member_id)

        return {
            'balance': balance.to_dict(),
            'transactions': [e.to_dict() for e in entries],
            'total': total,
            'limit': limit,
            'offset': offset,
        }


# Singleton instance
store_credit_service = StoreCreditService()
