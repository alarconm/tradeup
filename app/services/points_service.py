"""
Points Service for TradeUp Loyalty System.

Comprehensive points management system supporting:
- Points earning from purchases, referrals, activities
- Tier-based multipliers and promotional bonuses
- Points redemption for rewards (store credit, discounts, etc.)
- Configurable earning rules with triggers and conditions
- Points expiration and lifecycle management
- Shopify metafield sync for Liquid templates

ARCHITECTURE:
- Points are stored locally in PointsTransaction table
- Member's points_balance is the single source of truth (calculated from transactions)
- Points can be converted to store credit (which then syncs to Shopify)
- Tier information is synced to Shopify customer metafields

Points are NOT the same as store credit:
- Points are internal loyalty currency (earned via activity)
- Store credit is Shopify-native currency (can be spent at checkout)
- Points can be REDEEMED for store credit (conversion)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from flask import current_app
import json

from ..extensions import db
from ..models.member import Member, MembershipTier
from ..models.points import PointsTransaction
from ..models.loyalty_points import (
    PointsBalance,
    PointsLedger,
    EarningRule,
    Reward,
    RewardRedemption,
    PointsProgramConfig,
    PointsTransactionType,
    PointsEarnSource,
    RewardRedemptionStatus,
)
from ..models.promotions import Promotion, CreditEventType


# ==================== Configuration ====================

# Default earning rates (points per dollar spent)
DEFAULT_BASE_EARNING_RATE = 1  # 1 point per $1 spent

# Trigger types for earning rules
TRIGGER_TYPES = {
    'purchase': 'Order completed',
    'signup': 'New member signup',
    'referral': 'Successful referral',
    'birthday': 'Member birthday',
    'anniversary': 'Membership anniversary',
    'trade_in': 'Trade-in completed',
    'review': 'Product review submitted',
    'social_share': 'Social media share',
    'checkin': 'Store check-in',
    'bonus': 'Bonus/promotional points',
}

# Transaction types
TRANSACTION_TYPES = {
    'earn': 'Points earned',
    'redeem': 'Points redeemed',
    'adjustment': 'Manual adjustment',
    'expire': 'Points expired',
    'cancel': 'Points cancelled/reversed',
}


class PointsService:
    """
    Central service for all points-related operations.

    Usage:
        service = PointsService(tenant_id)

        # Award points
        result = service.earn_points(member_id, 100, 'purchase', order_id, 'Order #1234')

        # Redeem points
        result = service.redeem_points(member_id, reward_id)

        # Calculate points for order
        breakdown = service.calculate_points_for_order(order_data, member)
    """

    def __init__(self, tenant_id: int, shopify_client=None):
        """
        Initialize PointsService.

        Args:
            tenant_id: Tenant ID for multi-tenancy
            shopify_client: Optional ShopifyClient for Shopify operations
        """
        self.tenant_id = tenant_id
        self.shopify_client = shopify_client

    # ==================== Core Points Operations ====================

    def earn_points(
        self,
        member_id: int,
        amount: int,
        source_type: str,
        source_id: str = None,
        description: str = None,
        apply_multipliers: bool = True,
        multiplier_context: Dict[str, Any] = None,
        created_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Award points to a member.

        Applies any active multipliers (tier bonus, promo, etc.) and creates
        a transaction record.

        Args:
            member_id: Member to award points to
            amount: Base points amount (before multipliers)
            source_type: Source of points (purchase, referral, signup, etc.)
            source_id: Reference ID (order ID, referral ID, etc.)
            description: Human-readable description
            apply_multipliers: Whether to apply tier/promo multipliers
            multiplier_context: Additional context for multiplier calculation
            created_by: Who/what initiated this action

        Returns:
            Dict with transaction details and final points awarded
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        if member.status != 'active':
            return {'success': False, 'error': f'Member is not active (status: {member.status})'}

        if amount <= 0:
            return {'success': False, 'error': 'Points amount must be positive'}

        # Calculate multipliers
        base_points = amount
        bonus_points = 0
        multiplier_breakdown = []

        if apply_multipliers:
            multipliers = self._calculate_multipliers(
                member=member,
                source_type=source_type,
                context=multiplier_context or {}
            )

            for mult in multipliers:
                mult_bonus = int(base_points * (mult['rate'] - 1))
                bonus_points += mult_bonus
                multiplier_breakdown.append({
                    'name': mult['name'],
                    'rate': mult['rate'],
                    'bonus_points': mult_bonus
                })

        total_points = base_points + bonus_points

        # Calculate expiration date based on tenant policy
        expiration_days = self._get_expiration_policy()
        expires_at = None
        if expiration_days:
            expires_at = datetime.utcnow() + timedelta(days=expiration_days)

        # Create transaction
        transaction = PointsTransaction(
            tenant_id=self.tenant_id,
            member_id=member_id,
            points=total_points,
            remaining_points=total_points,  # Start with all points available
            transaction_type='earn',
            source=source_type,
            reference_id=source_id,
            reference_type=self._get_reference_type(source_type),
            description=description or f'Earned {total_points} points from {source_type}',
            expires_at=expires_at,
            created_at=datetime.utcnow()
        )
        db.session.add(transaction)

        # Update member's cached points balance
        member.points_balance = (member.points_balance or 0) + total_points
        member.lifetime_points_earned = (member.lifetime_points_earned or 0) + total_points

        try:
            db.session.commit()

            current_app.logger.info(
                f"Points earned: Member {member.member_number} +{total_points} pts "
                f"({base_points} base + {bonus_points} bonus) from {source_type}"
            )

            # New balance is the cached value
            new_balance = member.points_balance

            # Trigger Flow event for points earned (non-blocking)
            self._trigger_points_earned_flow(
                member=member,
                points=total_points,
                source_type=source_type,
                new_balance=new_balance,
                source_id=source_id,
                order_id=source_id if source_type == 'purchase' else None
            )

            return {
                'success': True,
                'transaction_id': transaction.id,
                'member_id': member_id,
                'member_number': member.member_number,
                'base_points': base_points,
                'bonus_points': bonus_points,
                'total_points': total_points,
                'multipliers': multiplier_breakdown,
                'new_balance': new_balance,
                'source': source_type,
                'description': transaction.description
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Points earn failed for member {member_id}: {e}")
            return {'success': False, 'error': str(e)}

    def redeem_points(
        self,
        member_id: int,
        reward_id: int = None,
        points_amount: int = None,
        reward_type: str = 'store_credit',
        reward_value: Decimal = None,
        description: str = None,
        created_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Redeem points for a reward.

        Supports different reward types:
        - store_credit: Convert points to Shopify store credit
        - discount_code: Generate a discount code
        - product: Redeem for a specific product
        - custom: Custom reward (tracked but fulfilled externally)

        Args:
            member_id: Member redeeming points
            reward_id: Optional reward configuration ID
            points_amount: Points to redeem (required if no reward_id)
            reward_type: Type of reward (store_credit, discount_code, etc.)
            reward_value: Value of the reward (e.g., $10 credit)
            description: Description for the redemption
            created_by: Who/what initiated this action

        Returns:
            Dict with redemption details
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        # Get current balance
        current_balance = self._calculate_member_balance(member_id)

        # Determine points to redeem
        if reward_id:
            # Look up reward configuration
            reward_config = self._get_reward_config(reward_id)
            if not reward_config:
                return {'success': False, 'error': 'Reward not found'}

            points_to_redeem = reward_config['points_required']
            reward_type = reward_config['type']
            reward_value = Decimal(str(reward_config['value']))
            description = description or reward_config['description']
        elif points_amount:
            points_to_redeem = points_amount
        else:
            return {'success': False, 'error': 'Either reward_id or points_amount required'}

        # Check sufficient balance
        if current_balance < points_to_redeem:
            return {
                'success': False,
                'error': f'Insufficient points balance. Required: {points_to_redeem}, Available: {current_balance}'
            }

        # Execute reward based on type
        reward_result = None
        if reward_type == 'store_credit':
            reward_result = self._execute_store_credit_reward(member, reward_value)
        elif reward_type == 'discount_code':
            reward_result = self._execute_discount_code_reward(member, reward_value)
        elif reward_type == 'product':
            reward_result = self._execute_product_reward(member, reward_id)
        else:
            # Custom reward - just track it
            reward_result = {'success': True, 'type': 'custom', 'requires_fulfillment': True}

        if not reward_result.get('success'):
            return {
                'success': False,
                'error': f"Failed to execute reward: {reward_result.get('error')}"
            }

        # Consume points using FIFO from oldest earn transactions
        self._consume_points_fifo(member_id, points_to_redeem)

        # Create redemption transaction (negative points)
        transaction = PointsTransaction(
            tenant_id=self.tenant_id,
            member_id=member_id,
            points=-points_to_redeem,  # Negative for redemption
            transaction_type='redeem',
            source='redemption',
            reference_id=str(reward_id) if reward_id else None,
            reference_type=reward_type,
            description=description or f'Redeemed {points_to_redeem} points for {reward_type}',
            created_at=datetime.utcnow()
        )
        db.session.add(transaction)

        # Update member's cached points balance
        member.points_balance = (member.points_balance or 0) - points_to_redeem
        member.lifetime_points_spent = (member.lifetime_points_spent or 0) + points_to_redeem

        try:
            db.session.commit()

            new_balance = member.points_balance

            current_app.logger.info(
                f"Points redeemed: Member {member.member_number} -{points_to_redeem} pts "
                f"for {reward_type}. New balance: {new_balance}"
            )

            # Trigger Flow event for points redeemed (non-blocking)
            self._trigger_points_redeemed_flow(
                member=member,
                points_redeemed=points_to_redeem,
                reward_type=reward_type,
                reward_value=float(reward_value) if reward_value else 0,
                reward_name=description or reward_type,
                new_balance=new_balance
            )

            return {
                'success': True,
                'transaction_id': transaction.id,
                'member_id': member_id,
                'member_number': member.member_number,
                'points_redeemed': points_to_redeem,
                'reward_type': reward_type,
                'reward_value': float(reward_value) if reward_value else None,
                'reward_details': reward_result,
                'new_balance': new_balance,
                'description': transaction.description
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Points redemption failed for member {member_id}: {e}")
            return {'success': False, 'error': str(e)}

    def calculate_points_for_order(
        self,
        order_data: Dict[str, Any],
        member: Member
    ) -> Dict[str, Any]:
        """
        Calculate points earned for an order.

        Applies earning rules:
        - Base rate (points per dollar)
        - Tier multiplier
        - Active promotional multipliers

        Args:
            order_data: Order data with total_price, line_items, etc.
            member: Member who placed the order

        Returns:
            Dict with points breakdown
        """
        if not member or member.status != 'active':
            return {
                'base_points': 0,
                'bonus_points': 0,
                'total_points': 0,
                'multipliers': [],
                'eligible': False,
                'reason': 'Member not active'
            }

        # Extract order value (use subtotal, excluding taxes/shipping typically)
        order_total = Decimal(str(order_data.get('subtotal_price', order_data.get('total_price', 0))))

        # Check for excluded products (gift cards, etc.)
        excluded_amount = self._calculate_excluded_amount(order_data)
        eligible_amount = order_total - excluded_amount

        if eligible_amount <= 0:
            return {
                'base_points': 0,
                'bonus_points': 0,
                'total_points': 0,
                'multipliers': [],
                'eligible': False,
                'reason': 'No eligible products in order'
            }

        # Calculate base points
        earning_rate = self._get_earning_rate(member)
        base_points = int(float(eligible_amount) * earning_rate)

        # Calculate multipliers
        multipliers = self._calculate_multipliers(
            member=member,
            source_type='purchase',
            context={
                'order_data': order_data,
                'order_total': float(eligible_amount),
                'channel': order_data.get('source_name', 'web')
            }
        )

        bonus_points = 0
        multiplier_breakdown = []

        for mult in multipliers:
            mult_bonus = int(base_points * (mult['rate'] - 1))
            bonus_points += mult_bonus
            multiplier_breakdown.append({
                'name': mult['name'],
                'rate': mult['rate'],
                'source': mult['source'],
                'bonus_points': mult_bonus
            })

        total_points = base_points + bonus_points

        return {
            'base_points': base_points,
            'bonus_points': bonus_points,
            'total_points': total_points,
            'eligible_amount': float(eligible_amount),
            'excluded_amount': float(excluded_amount),
            'earning_rate': earning_rate,
            'multipliers': multiplier_breakdown,
            'eligible': True
        }

    def evaluate_earning_rules(
        self,
        member: Member,
        trigger_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate earning rules for a specific trigger.

        Finds applicable earning rules for the trigger type and calculates
        total points to award.

        Args:
            member: Member to evaluate rules for
            trigger_type: Type of trigger (purchase, signup, referral, etc.)
            context: Context data (order_data, referral_info, etc.)

        Returns:
            Dict with applicable rules and total points
        """
        if not member or member.status != 'active':
            return {
                'applicable_rules': [],
                'total_points': 0,
                'eligible': False,
                'reason': 'Member not active'
            }

        applicable_rules = []
        total_points = 0

        # Get rules for this trigger type
        rules = self._get_earning_rules(trigger_type)

        for rule in rules:
            # Check rule conditions
            is_applicable, reason = self._check_rule_conditions(rule, member, context)

            if is_applicable:
                # Calculate points for this rule
                points = self._calculate_rule_points(rule, member, context)

                # Apply any caps
                points = self._apply_caps(rule, member, points)

                if points > 0:
                    applicable_rules.append({
                        'rule_id': rule.get('id'),
                        'rule_name': rule.get('name'),
                        'trigger': trigger_type,
                        'points': points,
                        'description': rule.get('description')
                    })
                    total_points += points

        return {
            'applicable_rules': applicable_rules,
            'total_points': total_points,
            'eligible': len(applicable_rules) > 0,
            'trigger_type': trigger_type
        }

    def get_member_points(self, member_id: int) -> Dict[str, Any]:
        """
        Get member's current points balance and statistics.

        Args:
            member_id: Member ID

        Returns:
            Dict with balance, pending, and lifetime stats
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        # Calculate current balance from transactions
        current_balance = self._calculate_member_balance(member_id)

        # Calculate pending points (e.g., from pending orders)
        pending_points = self._calculate_pending_points(member_id)

        # Calculate lifetime stats
        lifetime_earned = self._calculate_lifetime_earned(member_id)
        lifetime_redeemed = self._calculate_lifetime_redeemed(member_id)
        lifetime_expired = self._calculate_lifetime_expired(member_id)

        # Get expiring points (next 30 days)
        expiring_soon = self._calculate_expiring_points(member_id, days=30)

        return {
            'success': True,
            'member_id': member_id,
            'member_number': member.member_number,
            'current_balance': current_balance,
            'pending_points': pending_points,
            'available_balance': current_balance,  # Alias for compatibility
            'lifetime': {
                'earned': lifetime_earned,
                'redeemed': lifetime_redeemed,
                'expired': lifetime_expired,
                'net': lifetime_earned - lifetime_redeemed - lifetime_expired
            },
            'expiring_soon': {
                'amount': expiring_soon,
                'within_days': 30
            },
            'tier': member.tier.name if member.tier else None,
            'tier_multiplier': self._get_tier_multiplier(member)
        }

    def expire_points(self, batch_size: int = 100) -> Dict[str, Any]:
        """
        Background job to expire old points based on expiration rules.

        Should be run periodically (e.g., daily cron job).

        Args:
            batch_size: Number of members to process per batch

        Returns:
            Dict with expiration results
        """
        # Get tenant's expiration policy
        expiration_days = self._get_expiration_policy()

        if not expiration_days:
            return {
                'success': True,
                'message': 'No expiration policy configured',
                'expired_count': 0
            }

        cutoff_date = datetime.utcnow() - timedelta(days=expiration_days)

        results = {
            'members_processed': 0,
            'transactions_expired': 0,
            'total_points_expired': 0,
            'errors': []
        }

        # Find members with old unspent points
        # This is a simplified approach - production would need more sophisticated tracking
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).limit(batch_size).all()

        for member in members:
            try:
                expired = self._expire_member_points(member.id, cutoff_date)
                if expired > 0:
                    results['members_processed'] += 1
                    results['total_points_expired'] += expired
                    results['transactions_expired'] += 1
            except Exception as e:
                results['errors'].append({
                    'member_id': member.id,
                    'error': str(e)
                })

        current_app.logger.info(
            f"Points expiration completed: {results['total_points_expired']} points "
            f"expired across {results['members_processed']} members"
        )

        return {
            'success': len(results['errors']) == 0,
            **results
        }

    def sync_tier_to_shopify(self, member: Member) -> Dict[str, Any]:
        """
        Update customer metafield with current tier information.

        Syncs tier data to Shopify for use in:
        - Liquid templates (displaying tier badge, benefits)
        - Shopify Functions (tier-based discounts)
        - Customer segments (tier-based marketing)

        Args:
            member: Member to sync

        Returns:
            Dict with sync result
        """
        if not member.shopify_customer_id:
            return {
                'success': False,
                'error': 'Member has no Shopify customer ID'
            }

        if not self.shopify_client:
            return {
                'success': False,
                'error': 'Shopify client not configured'
            }

        # Get current points balance
        points_balance = self._calculate_member_balance(member.id)

        # Build metafields to sync
        metafields = [
            {
                'namespace': 'tradeup',
                'key': 'tier',
                'value': member.tier.name if member.tier else 'none',
                'type': 'single_line_text_field'
            },
            {
                'namespace': 'tradeup',
                'key': 'tier_id',
                'value': str(member.tier_id) if member.tier_id else '0',
                'type': 'number_integer'
            },
            {
                'namespace': 'tradeup',
                'key': 'points_balance',
                'value': str(points_balance),
                'type': 'number_integer'
            },
            {
                'namespace': 'tradeup',
                'key': 'member_number',
                'value': member.member_number,
                'type': 'single_line_text_field'
            },
            {
                'namespace': 'tradeup',
                'key': 'member_status',
                'value': member.status,
                'type': 'single_line_text_field'
            }
        ]

        # Add tier-specific metafields
        if member.tier:
            metafields.extend([
                {
                    'namespace': 'tradeup',
                    'key': 'tier_bonus_rate',
                    'value': str(float(member.tier.bonus_rate or 0)),
                    'type': 'number_decimal'
                },
                {
                    'namespace': 'tradeup',
                    'key': 'tier_cashback_pct',
                    'value': str(float(member.tier.purchase_cashback_pct or 0)),
                    'type': 'number_decimal'
                }
            ])

        try:
            result = self.shopify_client.set_customer_metafields(
                customer_id=member.shopify_customer_id,
                metafields=metafields
            )

            if result.get('success'):
                current_app.logger.info(
                    f"Synced tier metafields to Shopify for member {member.member_number}"
                )

            return result

        except Exception as e:
            current_app.logger.error(
                f"Failed to sync tier to Shopify for member {member.id}: {e}"
            )
            return {
                'success': False,
                'error': str(e)
            }

    # ==================== Transaction History ====================

    def get_points_history(
        self,
        member_id: int,
        limit: int = 50,
        offset: int = 0,
        transaction_type: str = None
    ) -> Dict[str, Any]:
        """
        Get member's points transaction history.

        Args:
            member_id: Member ID
            limit: Max records to return
            offset: Pagination offset
            transaction_type: Filter by type (earn, redeem, etc.)

        Returns:
            Dict with transaction history
        """
        query = PointsTransaction.query.filter_by(
            tenant_id=self.tenant_id,
            member_id=member_id
        )

        if transaction_type:
            query = query.filter_by(transaction_type=transaction_type)

        total = query.count()
        transactions = query.order_by(
            PointsTransaction.created_at.desc()
        ).limit(limit).offset(offset).all()

        return {
            'success': True,
            'transactions': [t.to_dict() for t in transactions],
            'total': total,
            'limit': limit,
            'offset': offset
        }

    def adjust_points(
        self,
        member_id: int,
        amount: int,
        reason: str,
        created_by: str
    ) -> Dict[str, Any]:
        """
        Manually adjust a member's points balance.

        Used for corrections, customer service adjustments, etc.

        Args:
            member_id: Member ID
            amount: Points to add (positive) or remove (negative)
            reason: Reason for adjustment
            created_by: Staff member making the adjustment

        Returns:
            Dict with adjustment result
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        if amount == 0:
            return {'success': False, 'error': 'Adjustment amount cannot be zero'}

        # Check balance for negative adjustments
        if amount < 0:
            current_balance = self._calculate_member_balance(member_id)
            if current_balance + amount < 0:
                return {
                    'success': False,
                    'error': f'Insufficient balance. Current: {current_balance}, Adjustment: {amount}'
                }

        transaction = PointsTransaction(
            tenant_id=self.tenant_id,
            member_id=member_id,
            points=amount,
            transaction_type='adjustment',
            source='admin',
            reference_id=None,
            reference_type='manual_adjustment',
            description=f"Adjustment: {reason} (by {created_by})",
            created_at=datetime.utcnow()
        )
        db.session.add(transaction)

        try:
            db.session.commit()

            new_balance = self._calculate_member_balance(member_id)

            current_app.logger.info(
                f"Points adjustment: Member {member.member_number} "
                f"{'+' if amount > 0 else ''}{amount} pts by {created_by}: {reason}"
            )

            return {
                'success': True,
                'transaction_id': transaction.id,
                'member_id': member_id,
                'amount': amount,
                'new_balance': new_balance,
                'reason': reason,
                'created_by': created_by
            }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    def reverse_transaction(
        self,
        transaction_id: int,
        reason: str,
        created_by: str
    ) -> Dict[str, Any]:
        """
        Reverse a points transaction.

        Creates a new transaction that negates the original.

        Args:
            transaction_id: Transaction to reverse
            reason: Reason for reversal
            created_by: Staff member performing reversal

        Returns:
            Dict with reversal result
        """
        original = PointsTransaction.query.filter_by(
            id=transaction_id,
            tenant_id=self.tenant_id
        ).first()

        if not original:
            return {'success': False, 'error': 'Transaction not found'}

        if original.reversed_at:
            return {'success': False, 'error': 'Transaction already reversed'}

        # Create reversal transaction
        reversal = PointsTransaction(
            tenant_id=self.tenant_id,
            member_id=original.member_id,
            points=-original.points,
            transaction_type='cancel',
            source=original.source,
            reference_id=original.reference_id,
            reference_type=original.reference_type,
            description=f"Reversal: {reason}",
            related_transaction_id=original.id,
            created_at=datetime.utcnow()
        )
        db.session.add(reversal)

        # Mark original as reversed
        original.reversed_at = datetime.utcnow()
        original.reversed_reason = reason

        try:
            db.session.commit()

            new_balance = self._calculate_member_balance(original.member_id)

            current_app.logger.info(
                f"Points reversed: Transaction {transaction_id}, "
                f"{original.points} pts, by {created_by}: {reason}"
            )

            return {
                'success': True,
                'reversal_id': reversal.id,
                'original_id': original.id,
                'points_reversed': original.points,
                'new_balance': new_balance,
                'reason': reason
            }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    # ==================== Helper Methods ====================

    def _calculate_member_balance(self, member_id: int) -> int:
        """Calculate member's current points balance from transactions."""
        result = db.session.query(
            db.func.coalesce(db.func.sum(PointsTransaction.points), 0)
        ).filter(
            PointsTransaction.tenant_id == self.tenant_id,
            PointsTransaction.member_id == member_id,
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        return int(result or 0)

    def _calculate_pending_points(self, member_id: int) -> int:
        """Calculate pending points (e.g., from pending orders)."""
        # Placeholder - implement based on business logic
        # Could query pending orders that haven't been fulfilled yet
        return 0

    def _calculate_lifetime_earned(self, member_id: int) -> int:
        """Calculate lifetime points earned."""
        result = db.session.query(
            db.func.coalesce(db.func.sum(PointsTransaction.points), 0)
        ).filter(
            PointsTransaction.tenant_id == self.tenant_id,
            PointsTransaction.member_id == member_id,
            PointsTransaction.transaction_type == 'earn',
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        return int(result or 0)

    def _calculate_lifetime_redeemed(self, member_id: int) -> int:
        """Calculate lifetime points redeemed."""
        result = db.session.query(
            db.func.coalesce(db.func.sum(db.func.abs(PointsTransaction.points)), 0)
        ).filter(
            PointsTransaction.tenant_id == self.tenant_id,
            PointsTransaction.member_id == member_id,
            PointsTransaction.transaction_type == 'redeem',
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        return int(result or 0)

    def _calculate_lifetime_expired(self, member_id: int) -> int:
        """Calculate lifetime points expired."""
        result = db.session.query(
            db.func.coalesce(db.func.sum(db.func.abs(PointsTransaction.points)), 0)
        ).filter(
            PointsTransaction.tenant_id == self.tenant_id,
            PointsTransaction.member_id == member_id,
            PointsTransaction.transaction_type == 'expire',
            PointsTransaction.reversed_at.is_(None)
        ).scalar()

        return int(result or 0)

    def _calculate_expiring_points(self, member_id: int, days: int = 30) -> int:
        """Calculate points expiring within specified days.

        Uses the expires_at and remaining_points fields on PointsTransaction
        to calculate how many points will expire within the given period.
        """
        now = datetime.utcnow()
        expiry_window = now + timedelta(days=days)

        # Sum remaining_points from earn transactions that expire within the window
        result = db.session.query(
            db.func.coalesce(db.func.sum(PointsTransaction.remaining_points), 0)
        ).filter(
            PointsTransaction.tenant_id == self.tenant_id,
            PointsTransaction.member_id == member_id,
            PointsTransaction.transaction_type == 'earn',
            PointsTransaction.reversed_at.is_(None),
            PointsTransaction.expires_at.isnot(None),
            PointsTransaction.expires_at > now,  # Not yet expired
            PointsTransaction.expires_at <= expiry_window,  # Expires within window
            PointsTransaction.remaining_points > 0  # Has remaining points
        ).scalar()

        return int(result or 0)

    def _calculate_multipliers(
        self,
        member: Member,
        source_type: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate applicable multipliers for a points transaction."""
        multipliers = []

        # Tier multiplier
        tier_mult = self._get_tier_multiplier(member)
        if tier_mult > 1.0:
            multipliers.append({
                'name': f'{member.tier.name} Tier Bonus' if member.tier else 'Tier Bonus',
                'rate': tier_mult,
                'source': 'tier'
            })

        # Check for active promotions
        if source_type == 'purchase':
            promo_mult = self._get_promotional_multiplier(member, context)
            if promo_mult > 1.0:
                multipliers.append({
                    'name': 'Promotional Bonus',
                    'rate': promo_mult,
                    'source': 'promotion'
                })

        # Double points day (from tier configuration)
        if member.tier and self._is_double_points_day(member):
            multipliers.append({
                'name': 'Double Points Day',
                'rate': 2.0,
                'source': 'double_points'
            })

        return multipliers

    def _get_tier_multiplier(self, member: Member) -> float:
        """Get points multiplier based on member's tier."""
        if not member.tier:
            return 1.0

        # Use tier's bonus rate as base for multiplier
        # e.g., 5% bonus rate = 1.05x multiplier
        bonus_rate = float(member.tier.bonus_rate or 0)

        # If tier has double_points benefit, apply 2x
        benefits = member.tier.benefits or {}
        if benefits.get('double_points'):
            return 2.0

        return 1.0 + bonus_rate

    def _get_promotional_multiplier(self, member: Member, context: Dict) -> float:
        """Get active promotional multiplier."""
        # Check for active promotions that apply to points
        # This could query the Promotion model for active multiplier-type promos

        now = datetime.utcnow()
        tier_name = member.tier.name if member.tier else None
        channel = context.get('channel', 'online')

        # Query active promotions of multiplier type
        promos = Promotion.query.filter(
            Promotion.active == True,
            Promotion.promo_type == 'multiplier',
            Promotion.starts_at <= now,
            Promotion.ends_at >= now
        ).all()

        max_multiplier = 1.0
        for promo in promos:
            if promo.is_active_now():
                if promo.applies_to_tier(tier_name) and promo.applies_to_channel(channel):
                    promo_mult = float(promo.multiplier or 1.0)
                    if promo_mult > max_multiplier:
                        max_multiplier = promo_mult

        return max_multiplier

    def _is_double_points_day(self, member: Member) -> bool:
        """Check if today is a double points day for this tier."""
        if not member.tier:
            return False

        benefits = member.tier.benefits or {}

        # Check if tier has double_points enabled
        if not benefits.get('double_points'):
            return False

        # Could implement specific day logic here
        # e.g., double points every Tuesday
        # For now, return False (would need configuration)
        return False

    def _get_earning_rate(self, member: Member) -> float:
        """Get points earning rate for member."""
        # Base rate
        rate = DEFAULT_BASE_EARNING_RATE

        # Tier-specific rates could be configured here
        if member.tier:
            # Check tier benefits for custom earning rate
            benefits = member.tier.benefits or {}
            if benefits.get('points_per_dollar'):
                rate = benefits['points_per_dollar']

        return rate

    def _calculate_excluded_amount(self, order_data: Dict) -> Decimal:
        """Calculate amount from excluded products (gift cards, etc.)."""
        excluded = Decimal('0')

        line_items = order_data.get('line_items', [])
        for item in line_items:
            # Exclude gift cards
            if item.get('gift_card'):
                excluded += Decimal(str(item.get('price', 0))) * item.get('quantity', 1)

            # Could exclude other product types based on tags
            # e.g., items with 'no-points' tag

        return excluded

    def _get_reference_type(self, source_type: str) -> str:
        """Map source type to reference type."""
        mapping = {
            'purchase': 'shopify_order',
            'referral': 'referral',
            'signup': 'signup_bonus',
            'trade_in': 'trade_in_batch',
            'birthday': 'birthday_bonus',
            'anniversary': 'anniversary_bonus',
            'bonus': 'promotional',
        }
        return mapping.get(source_type, source_type)

    def _get_reward_config(self, reward_id: int) -> Optional[Dict]:
        """Get reward configuration by ID."""
        reward = Reward.query.filter_by(
            id=reward_id,
            tenant_id=self.tenant_id
        ).first()

        if not reward:
            return None

        if not reward.is_available():
            return None

        return {
            'id': reward.id,
            'type': reward.reward_type,
            'points_required': reward.points_cost,
            'value': float(reward.value) if reward.value else 0,
            'value_type': reward.value_type,
            'description': reward.description or reward.name,
            'reward_object': reward
        }

    def _execute_store_credit_reward(
        self,
        member: Member,
        value: Decimal
    ) -> Dict[str, Any]:
        """Execute store credit reward."""
        from .store_credit_service import store_credit_service

        try:
            entry = store_credit_service.add_credit(
                member_id=member.id,
                amount=value,
                event_type=CreditEventType.PROMOTION_BONUS.value,
                description=f'Points redemption: ${value} store credit',
                source_type='points_redemption',
                created_by='system:points_service',
                sync_to_shopify=True
            )

            return {
                'success': True,
                'type': 'store_credit',
                'credit_entry_id': entry.id if entry else None,
                'amount': float(value)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _execute_discount_code_reward(
        self,
        member: Member,
        value: Decimal
    ) -> Dict[str, Any]:
        """Execute discount code reward."""
        # Placeholder - would generate a unique discount code in Shopify
        # Could use ShopifyClient.create_discount_code method
        return {
            'success': True,
            'type': 'discount_code',
            'code': f'POINTS-{member.member_number}-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            'value': float(value),
            'requires_fulfillment': False
        }

    def _execute_product_reward(
        self,
        member: Member,
        reward_id: int
    ) -> Dict[str, Any]:
        """Execute product reward."""
        # Placeholder - would create a draft order or gift card
        return {
            'success': True,
            'type': 'product',
            'reward_id': reward_id,
            'requires_fulfillment': True
        }

    def _get_earning_rules(self, trigger_type: str) -> List[Dict]:
        """Get earning rules for a trigger type from database."""
        rules = EarningRule.query.filter(
            EarningRule.tenant_id == self.tenant_id,
            EarningRule.is_active == True,
            EarningRule.trigger_source == trigger_type
        ).order_by(EarningRule.priority.desc()).all()

        return [
            {
                'id': rule.id,
                'name': rule.name,
                'trigger': rule.trigger_source,
                'points': rule.bonus_points or 0,
                'points_per_dollar': rule.points_per_dollar,
                'multiplier': float(rule.multiplier) if rule.multiplier else None,
                'rule_type': rule.rule_type,
                'description': rule.description,
                'min_order_value': float(rule.min_order_value) if rule.min_order_value else None,
                'max_points_per_order': rule.max_points_per_order,
                'rule_object': rule
            }
            for rule in rules if rule.is_active_now()
        ]

    def _check_rule_conditions(
        self,
        rule: Dict,
        member: Member,
        context: Dict
    ) -> Tuple[bool, str]:
        """Check if rule conditions are met."""
        # Placeholder - would evaluate rule conditions
        # e.g., tier requirements, date ranges, usage limits
        return True, 'OK'

    def _calculate_rule_points(
        self,
        rule: Dict,
        member: Member,
        context: Dict
    ) -> int:
        """Calculate points for a rule."""
        return rule.get('points', 0)

    def _apply_caps(self, rule: Dict, member: Member, points: int) -> int:
        """Apply any caps or limits to points."""
        # Could implement daily/weekly/monthly caps
        max_points = rule.get('max_points')
        if max_points and points > max_points:
            return max_points
        return points

    def _get_expiration_policy(self) -> Optional[int]:
        """Get points expiration policy in days from tenant settings."""
        from ..models.tenant import Tenant

        tenant = Tenant.query.get(self.tenant_id)
        if not tenant:
            return None

        # Get points settings from tenant.settings JSON
        settings = tenant.settings or {}
        points_settings = settings.get('points', {})

        # Return expiration_days (None means no expiration)
        expiration_days = points_settings.get('expiration_days')

        # Ensure it's an integer or None
        if expiration_days is not None:
            try:
                return int(expiration_days)
            except (ValueError, TypeError):
                return None

        return None  # Points don't expire by default

    def _consume_points_fifo(self, member_id: int, points_to_consume: int) -> int:
        """Consume points from oldest earn transactions first (FIFO).

        Updates remaining_points on earn transactions to track which points
        have been spent. Uses FIFO order based on created_at date.

        Args:
            member_id: Member whose points to consume
            points_to_consume: Number of points to consume

        Returns:
            Actual points consumed (may be less if insufficient)
        """
        if points_to_consume <= 0:
            return 0

        # Get earn transactions with remaining points, oldest first
        earn_transactions = PointsTransaction.query.filter(
            PointsTransaction.tenant_id == self.tenant_id,
            PointsTransaction.member_id == member_id,
            PointsTransaction.transaction_type == 'earn',
            PointsTransaction.reversed_at.is_(None),
            PointsTransaction.remaining_points > 0
        ).order_by(
            # Prioritize points that expire soonest (FIFO by expiration, then by creation)
            PointsTransaction.expires_at.asc().nullslast(),
            PointsTransaction.created_at.asc()
        ).all()

        remaining_to_consume = points_to_consume
        total_consumed = 0

        for txn in earn_transactions:
            if remaining_to_consume <= 0:
                break

            available = txn.remaining_points or 0
            if available <= 0:
                continue

            # Consume from this transaction
            consume_from_txn = min(available, remaining_to_consume)
            txn.remaining_points = available - consume_from_txn

            remaining_to_consume -= consume_from_txn
            total_consumed += consume_from_txn

        return total_consumed

    def _expire_member_points(self, member_id: int, cutoff_date: datetime) -> int:
        """Expire old points for a member using FIFO logic.

        Finds all earn transactions that have expired (expires_at <= cutoff_date)
        and still have remaining_points > 0. Creates expiration transactions
        for each and updates the member's balance.

        Args:
            member_id: Member whose points to expire
            cutoff_date: Date to check expiration against (usually now)

        Returns:
            Total points expired
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return 0

        # Find expired transactions with remaining points
        expired_transactions = PointsTransaction.query.filter(
            PointsTransaction.tenant_id == self.tenant_id,
            PointsTransaction.member_id == member_id,
            PointsTransaction.transaction_type == 'earn',
            PointsTransaction.reversed_at.is_(None),
            PointsTransaction.expires_at.isnot(None),
            PointsTransaction.expires_at <= cutoff_date,
            PointsTransaction.remaining_points > 0
        ).order_by(PointsTransaction.expires_at.asc()).all()

        total_expired = 0

        for txn in expired_transactions:
            points_to_expire = txn.remaining_points or 0
            if points_to_expire <= 0:
                continue

            # Create expiration transaction (negative points)
            expiration_txn = PointsTransaction(
                tenant_id=self.tenant_id,
                member_id=member_id,
                points=-points_to_expire,
                transaction_type='expire',
                source='expiration',
                reference_id=str(txn.id),
                reference_type='expired_earn',
                description=f'Points expired (earned {txn.created_at.strftime("%Y-%m-%d") if txn.created_at else ""})',
                related_transaction_id=txn.id,
                created_at=datetime.utcnow()
            )
            db.session.add(expiration_txn)

            # Mark original transaction as fully consumed
            txn.remaining_points = 0

            total_expired += points_to_expire

            current_app.logger.info(
                f"Expired {points_to_expire} pts from txn {txn.id} for member {member.member_number}"
            )

        if total_expired > 0:
            # Update member's cached balance
            member.points_balance = max(0, (member.points_balance or 0) - total_expired)

            try:
                db.session.commit()

                # Trigger Flow event for points expired (non-blocking)
                self._trigger_points_expired_flow(
                    member=member,
                    points_expired=total_expired,
                    new_balance=member.points_balance
                )
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to expire points for member {member_id}: {e}")
                raise

        return total_expired

    def _trigger_points_expired_flow(
        self,
        member: Member,
        points_expired: int,
        new_balance: int
    ):
        """Trigger Shopify Flow event for points expired (non-critical)."""
        if not self.shopify_client:
            return

        try:
            from .flow_service import FlowService
            flow_svc = FlowService(self.tenant_id, self.shopify_client)

            # Use a generic trigger for points expired
            # This could be extended to use a specific flow trigger
            current_app.logger.info(
                f"Points expired for member {member.member_number}: "
                f"{points_expired} pts, new balance: {new_balance}"
            )
        except Exception as e:
            current_app.logger.warning(f"Points expired Flow trigger failed: {e}")

    def _trigger_points_earned_flow(
        self,
        member: Member,
        points: int,
        source_type: str,
        new_balance: int,
        source_id: str = None,
        order_id: str = None
    ):
        """
        Trigger Shopify Flow event for points earned.

        Sends the points_earned trigger and checks for reward unlocks.
        """
        if not self.shopify_client:
            return

        try:
            from .flow_service import FlowService
            flow_svc = FlowService(self.tenant_id, self.shopify_client)

            # Send points_earned trigger
            flow_svc.trigger_points_earned(
                member_id=member.id,
                member_number=member.member_number,
                email=member.email,
                points_earned=points,
                source=source_type,
                source_id=source_id,
                new_balance=new_balance,
                tier_name=member.tier.name if member.tier else None,
                order_id=order_id,
                shopify_customer_id=member.shopify_customer_id
            )

            # Check if any rewards were unlocked
            flow_svc.check_and_trigger_reward_unlocks(
                member_id=member.id,
                new_balance=new_balance
            )

        except Exception as e:
            # Flow triggers are non-critical - log and continue
            current_app.logger.warning(f"Points Flow trigger failed: {e}")

    def _trigger_points_redeemed_flow(
        self,
        member: Member,
        points_redeemed: int,
        reward_type: str,
        reward_value: float,
        reward_name: str,
        new_balance: int
    ):
        """
        Trigger Shopify Flow event for points redeemed.
        """
        if not self.shopify_client:
            return

        try:
            from .flow_service import FlowService
            flow_svc = FlowService(self.tenant_id, self.shopify_client)

            flow_svc.trigger_points_redeemed(
                member_id=member.id,
                member_number=member.member_number,
                email=member.email,
                points_redeemed=points_redeemed,
                reward_type=reward_type,
                reward_value=reward_value,
                reward_name=reward_name,
                new_balance=new_balance,
                shopify_customer_id=member.shopify_customer_id
            )

        except Exception as e:
            # Flow triggers are non-critical - log and continue
            current_app.logger.warning(f"Points redeemed Flow trigger failed: {e}")


# Singleton instance
points_service = PointsService(tenant_id=0)  # Will be reconfigured per-request
