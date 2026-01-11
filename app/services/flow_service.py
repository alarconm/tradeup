"""
Shopify Flow Integration Service.

Sends trigger events to Shopify Flow and handles Flow action requests.
Flow allows merchants to create automated workflows based on app events.

TRIGGERS (TradeUp → Flow):
----------------------------
Member Events:
- member_enrolled: New member joins the loyalty program
- tier_upgraded: Member moves to a higher tier
- tier_downgraded: Member moves to a lower tier

Points Events:
- points_earned: Customer earns points (purchase, referral, etc.)
- points_redeemed: Customer redeems points for rewards
- reward_unlocked: Customer has enough points for a reward

Trade-In Events:
- trade_in_completed: Trade-in batch is finalized
- credit_issued: Store credit added to account

ACTIONS (Flow → TradeUp):
----------------------------
- award_bonus_points: Give bonus points to a customer
- add_credit: Add store credit to a customer
- change_tier: Change a member's tier
- get_member: Retrieve member information
- send_tier_upgrade_email: Trigger tier upgrade notification
- create_reward_reminder: Schedule reward reminder

Flow Integration Architecture:
-----------------------------
1. Triggers are sent via Shopify's flowTriggerReceive GraphQL mutation
2. Triggers are registered in shopify.app.toml
3. Actions are HTTP endpoints that Flow calls
4. All operations are idempotent with proper error handling
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List
from flask import current_app
import hashlib
import json

from ..extensions import db


class FlowService:
    """
    Service for Shopify Flow integration.

    Provides methods for:
    1. Sending trigger events to Shopify Flow
    2. Handling incoming action requests from Flow
    3. Managing idempotency for reliable delivery

    Usage:
        from app.services.flow_service import FlowService
        from app.services.shopify_client import ShopifyClient

        client = ShopifyClient(tenant_id)
        flow = FlowService(tenant_id, client)

        # Send a trigger
        flow.trigger_points_earned(member, 100, 'purchase', 'order_123', 1500)

        # Handle an action (called from route)
        result = flow.action_award_bonus_points(customer_email, 50, 'Birthday bonus')
    """

    def __init__(self, tenant_id: int, shopify_client=None):
        self.tenant_id = tenant_id
        self.shopify_client = shopify_client
        self._sent_triggers = set()  # Track sent triggers for dedup

    # ==================== Flow Triggers ====================
    # These methods send events to Shopify Flow

    def trigger_member_enrolled(
        self,
        member_id: int,
        member_number: str,
        email: str,
        tier_name: str,
        shopify_customer_id: str = None
    ) -> Dict[str, Any]:
        """
        Trigger Flow when a new member enrolls.

        This allows merchants to create workflows like:
        - Send welcome email
        - Add customer tag
        - Create loyalty notification
        """
        payload = {
            'trigger': 'member_enrolled',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'member_id': member_id,
                'member_number': member_number,
                'email': email,
                'tier_name': tier_name,
                'shopify_customer_id': shopify_customer_id
            }
        }

        return self._send_flow_trigger('member-enrolled', payload)

    def trigger_tier_changed(
        self,
        member_id: int,
        member_number: str,
        email: str,
        old_tier: str,
        new_tier: str,
        change_type: str,  # 'upgrade' or 'downgrade'
        source: str,  # 'subscription', 'purchase', 'staff', etc.
        shopify_customer_id: str = None
    ) -> Dict[str, Any]:
        """
        Trigger Flow when a member's tier changes.

        This allows merchants to create workflows like:
        - Send tier upgrade congratulations
        - Update customer tags
        - Send downgrade warning/win-back offers
        """
        payload = {
            'trigger': 'tier_changed',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'member_id': member_id,
                'member_number': member_number,
                'email': email,
                'old_tier': old_tier,
                'new_tier': new_tier,
                'change_type': change_type,
                'source': source,
                'shopify_customer_id': shopify_customer_id
            }
        }

        return self._send_flow_trigger('tier-changed', payload)

    def trigger_trade_in_completed(
        self,
        member_id: int,
        member_number: str,
        email: str,
        batch_reference: str,
        trade_value: float,
        bonus_amount: float,
        item_count: int,
        category: str,
        shopify_customer_id: str = None
    ) -> Dict[str, Any]:
        """
        Trigger Flow when a trade-in is completed.

        This allows merchants to create workflows like:
        - Send thank you email with credit summary
        - Update customer lifetime value
        - Trigger re-engagement campaigns
        """
        payload = {
            'trigger': 'trade_in_completed',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'member_id': member_id,
                'member_number': member_number,
                'email': email,
                'batch_reference': batch_reference,
                'trade_value': trade_value,
                'bonus_amount': bonus_amount,
                'total_credit': trade_value + bonus_amount,
                'item_count': item_count,
                'category': category,
                'shopify_customer_id': shopify_customer_id
            }
        }

        return self._send_flow_trigger('trade-in-completed', payload)

    def trigger_credit_issued(
        self,
        member_id: int,
        member_number: str,
        email: str,
        amount: float,
        event_type: str,  # 'trade_in', 'referral', 'promotion', etc.
        description: str,
        new_balance: float,
        shopify_customer_id: str = None
    ) -> Dict[str, Any]:
        """
        Trigger Flow when store credit is issued.

        This allows merchants to create workflows like:
        - Send credit notification
        - Trigger spend reminder after X days
        - Update marketing segments
        """
        payload = {
            'trigger': 'credit_issued',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'member_id': member_id,
                'member_number': member_number,
                'email': email,
                'amount': amount,
                'event_type': event_type,
                'description': description,
                'new_balance': new_balance,
                'shopify_customer_id': shopify_customer_id
            }
        }

        return self._send_flow_trigger('credit-issued', payload)

    # ==================== Points Triggers ====================

    def trigger_points_earned(
        self,
        member_id: int,
        member_number: str,
        email: str,
        points_earned: int,
        source: str,
        source_id: str = None,
        new_balance: int = 0,
        tier_name: str = None,
        order_id: str = None,
        shopify_customer_id: str = None
    ) -> Dict[str, Any]:
        """
        Trigger Flow when a customer earns points.

        This allows merchants to create workflows like:
        - Send points earned notification
        - Trigger bonus points on milestone achievements
        - Update customer tags based on points
        - Check for reward eligibility

        Args:
            member_id: Internal member ID
            member_number: Member number (e.g., TU1001)
            email: Member email address
            points_earned: Number of points earned
            source: Source of points (purchase, referral, signup, trade_in, bonus)
            source_id: Reference ID (order ID, referral ID, etc.)
            new_balance: New total points balance
            tier_name: Member's current tier
            order_id: Shopify order GID (if from purchase)
            shopify_customer_id: Shopify customer GID

        Returns:
            Dict with trigger result
        """
        payload = {
            'trigger': 'points_earned',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'member_id': member_id,
                'member_number': member_number,
                'email': email,
                'points_earned': points_earned,
                'source': source,
                'source_id': source_id,
                'new_balance': new_balance,
                'tier_name': tier_name,
                'order_id': order_id,
                'shopify_customer_id': shopify_customer_id
            }
        }

        return self._send_flow_trigger('points-earned', payload)

    def trigger_points_redeemed(
        self,
        member_id: int,
        member_number: str,
        email: str,
        points_redeemed: int,
        reward_type: str,
        reward_value: float = None,
        reward_name: str = None,
        new_balance: int = 0,
        shopify_customer_id: str = None
    ) -> Dict[str, Any]:
        """
        Trigger Flow when a customer redeems points.

        This allows merchants to create workflows like:
        - Send redemption confirmation
        - Trigger win-back campaigns if balance is low
        - Update customer segments
        - Apply discount automatically

        Args:
            member_id: Internal member ID
            member_number: Member number
            email: Member email address
            points_redeemed: Number of points redeemed
            reward_type: Type of reward (store_credit, discount_code, product, custom)
            reward_value: Value of the reward (e.g., $10)
            reward_name: Name of the reward
            new_balance: New total points balance
            shopify_customer_id: Shopify customer GID

        Returns:
            Dict with trigger result
        """
        payload = {
            'trigger': 'points_redeemed',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'member_id': member_id,
                'member_number': member_number,
                'email': email,
                'points_redeemed': points_redeemed,
                'reward_type': reward_type,
                'reward_value': reward_value,
                'reward_name': reward_name,
                'new_balance': new_balance,
                'shopify_customer_id': shopify_customer_id
            }
        }

        return self._send_flow_trigger('points-redeemed', payload)

    def trigger_tier_upgraded(
        self,
        member_id: int,
        member_number: str,
        email: str,
        old_tier: str,
        new_tier: str,
        old_tier_bonus: float,
        new_tier_bonus: float,
        source: str = 'activity',
        shopify_customer_id: str = None
    ) -> Dict[str, Any]:
        """
        Trigger Flow when a customer is upgraded to a higher tier.

        This allows merchants to create workflows like:
        - Send congratulations email
        - Apply welcome discount for new tier
        - Add customer tag for new tier
        - Trigger celebration notification

        Args:
            member_id: Internal member ID
            member_number: Member number
            email: Member email address
            old_tier: Previous tier name
            new_tier: New tier name
            old_tier_bonus: Previous tier bonus rate
            new_tier_bonus: New tier bonus rate
            source: What triggered the upgrade (activity, purchase, subscription, staff)
            shopify_customer_id: Shopify customer GID

        Returns:
            Dict with trigger result
        """
        payload = {
            'trigger': 'tier_upgraded',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'member_id': member_id,
                'member_number': member_number,
                'email': email,
                'old_tier': old_tier,
                'new_tier': new_tier,
                'old_tier_bonus_percent': old_tier_bonus * 100,
                'new_tier_bonus_percent': new_tier_bonus * 100,
                'source': source,
                'change_type': 'upgrade',
                'shopify_customer_id': shopify_customer_id
            }
        }

        return self._send_flow_trigger('tier-upgraded', payload)

    def trigger_tier_downgraded(
        self,
        member_id: int,
        member_number: str,
        email: str,
        old_tier: str,
        new_tier: str,
        old_tier_bonus: float,
        new_tier_bonus: float,
        reason: str = 'inactivity',
        shopify_customer_id: str = None
    ) -> Dict[str, Any]:
        """
        Trigger Flow when a customer is downgraded to a lower tier.

        This allows merchants to create workflows like:
        - Send win-back offer
        - Trigger re-engagement campaign
        - Notify customer of tier change
        - Create retention task for staff

        Args:
            member_id: Internal member ID
            member_number: Member number
            email: Member email address
            old_tier: Previous tier name
            new_tier: New tier name (or None if removed)
            old_tier_bonus: Previous tier bonus rate
            new_tier_bonus: New tier bonus rate
            reason: Why downgraded (inactivity, subscription_cancelled, refund, expired)
            shopify_customer_id: Shopify customer GID

        Returns:
            Dict with trigger result
        """
        payload = {
            'trigger': 'tier_downgraded',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'member_id': member_id,
                'member_number': member_number,
                'email': email,
                'old_tier': old_tier,
                'new_tier': new_tier or 'None',
                'old_tier_bonus_percent': old_tier_bonus * 100,
                'new_tier_bonus_percent': new_tier_bonus * 100 if new_tier_bonus else 0,
                'reason': reason,
                'change_type': 'downgrade',
                'shopify_customer_id': shopify_customer_id
            }
        }

        return self._send_flow_trigger('tier-downgraded', payload)

    def trigger_reward_unlocked(
        self,
        member_id: int,
        member_number: str,
        email: str,
        reward_id: int,
        reward_name: str,
        points_required: int,
        reward_value: float,
        current_balance: int,
        shopify_customer_id: str = None
    ) -> Dict[str, Any]:
        """
        Trigger Flow when a customer has enough points to unlock a reward.

        This allows merchants to create workflows like:
        - Send reward available notification
        - Create urgency with limited-time bonus
        - Update customer segment for retargeting
        - Trigger personalized recommendation

        Args:
            member_id: Internal member ID
            member_number: Member number
            email: Member email address
            reward_id: Reward configuration ID
            reward_name: Name of the unlocked reward
            points_required: Points needed for this reward
            reward_value: Dollar value of the reward
            current_balance: Customer's current points balance
            shopify_customer_id: Shopify customer GID

        Returns:
            Dict with trigger result
        """
        payload = {
            'trigger': 'reward_unlocked',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'member_id': member_id,
                'member_number': member_number,
                'email': email,
                'reward_id': reward_id,
                'reward_name': reward_name,
                'points_required': points_required,
                'reward_value': reward_value,
                'current_balance': current_balance,
                'points_surplus': current_balance - points_required,
                'shopify_customer_id': shopify_customer_id
            }
        }

        return self._send_flow_trigger('reward-unlocked', payload)

    def check_and_trigger_reward_unlocks(
        self,
        member_id: int,
        new_balance: int
    ) -> List[Dict[str, Any]]:
        """
        Check if member has unlocked any new rewards and trigger events.

        Called after points are earned to check if new rewards are available.

        Args:
            member_id: Member ID to check
            new_balance: Member's new points balance

        Returns:
            List of trigger results for each unlocked reward
        """
        from ..models import Member
        from ..models.loyalty_points import Reward

        member = Member.query.filter_by(
            id=member_id,
            tenant_id=self.tenant_id
        ).first()

        if not member:
            return []

        # Get all available rewards the member can now afford
        rewards = Reward.query.filter(
            Reward.tenant_id == self.tenant_id,
            Reward.is_active == True,
            Reward.points_cost <= new_balance
        ).all()

        results = []
        for reward in rewards:
            if reward.is_available():
                result = self.trigger_reward_unlocked(
                    member_id=member.id,
                    member_number=member.member_number,
                    email=member.email,
                    reward_id=reward.id,
                    reward_name=reward.name,
                    points_required=reward.points_cost,
                    reward_value=float(reward.value or 0),
                    current_balance=new_balance,
                    shopify_customer_id=member.shopify_customer_id
                )
                results.append(result)

        return results

    def _send_flow_trigger(self, trigger_name: str, payload: Dict) -> Dict[str, Any]:
        """
        Send a trigger event to Shopify Flow.

        Note: Shopify Flow triggers are sent via the flowTriggerReceive mutation.
        The trigger must be registered in shopify.app.toml.
        """
        if not self.shopify_client:
            return {
                'success': False,
                'error': 'Shopify client not configured'
            }

        mutation = """
        mutation flowTriggerReceive($handle: String!, $payload: JSON!) {
            flowTriggerReceive(handle: $handle, payload: $payload) {
                userErrors {
                    field
                    message
                }
            }
        }
        """

        try:
            # The handle format is typically "app-slug/trigger-name"
            # For custom apps, use the trigger URI path
            handle = f"tradeup/{trigger_name}"

            result = self.shopify_client._execute_query(mutation, {
                'handle': handle,
                'payload': payload
            })

            errors = result.get('flowTriggerReceive', {}).get('userErrors', [])
            if errors:
                return {
                    'success': False,
                    'errors': errors,
                    'trigger': trigger_name
                }

            return {
                'success': True,
                'trigger': trigger_name,
                'payload': payload
            }

        except Exception as e:
            # Log but don't fail - Flow triggers are non-critical
            current_app.logger.warning(f"Flow trigger '{trigger_name}' failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'trigger': trigger_name
            }

    # ==================== Flow Actions ====================
    # These methods handle incoming action requests from Flow

    def action_add_credit(
        self,
        customer_email: str,
        amount: float,
        reason: str = 'Flow automation'
    ) -> Dict[str, Any]:
        """
        Flow action: Add store credit to a customer.

        Args:
            customer_email: Customer's email address
            amount: Credit amount to add
            reason: Description for the credit

        Returns:
            Dict with result and new balance
        """
        from ..models import Member
        from .store_credit_service import store_credit_service
        from ..models.promotions import CreditEventType

        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if not member:
            return {
                'success': False,
                'error': f'Member not found: {customer_email}'
            }

        try:
            entry = store_credit_service.add_credit(
                member_id=member.id,
                amount=Decimal(str(amount)),
                event_type=CreditEventType.PROMO.value,
                description=f"Flow: {reason}",
                source_type='flow_action',
                created_by='shopify_flow',
                sync_to_shopify=True
            )

            # Get updated balance
            balance = store_credit_service.get_balance(member.id)

            return {
                'success': True,
                'member_id': member.id,
                'member_number': member.member_number,
                'amount_added': float(amount),
                'new_balance': float(balance),
                'credit_entry_id': entry.id if entry else None
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def action_change_tier(
        self,
        customer_email: str,
        new_tier_name: str,
        reason: str = 'Flow automation'
    ) -> Dict[str, Any]:
        """
        Flow action: Change a member's tier.

        Args:
            customer_email: Customer's email address
            new_tier_name: Name of the new tier
            reason: Reason for the change

        Returns:
            Dict with result
        """
        from ..models import Member
        from ..models.promotions import TierConfiguration
        from .tier_service import TierService

        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if not member:
            return {
                'success': False,
                'error': f'Member not found: {customer_email}'
            }

        # Find the tier
        tier = TierConfiguration.query.filter_by(
            tenant_id=self.tenant_id,
            name=new_tier_name
        ).first()

        if not tier:
            # Try case-insensitive
            tier = TierConfiguration.query.filter(
                TierConfiguration.tenant_id == self.tenant_id,
                TierConfiguration.name.ilike(new_tier_name)
            ).first()

        if not tier:
            return {
                'success': False,
                'error': f'Tier not found: {new_tier_name}'
            }

        try:
            tier_svc = TierService(self.tenant_id)
            result = tier_svc.assign_tier(
                member_id=member.id,
                tier_id=tier.id,
                source='api',  # Flow is an API source
                assigned_by='shopify_flow',
                notes=f"Flow: {reason}"
            )

            return {
                'success': result.get('success', False),
                'member_id': member.id,
                'member_number': member.member_number,
                'old_tier': result.get('old_tier'),
                'new_tier': result.get('new_tier'),
                'change_type': result.get('change_type')
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def action_get_member(self, customer_email: str) -> Dict[str, Any]:
        """
        Flow action: Get member information.

        Args:
            customer_email: Customer's email address

        Returns:
            Dict with member data
        """
        from ..models import Member
        from .store_credit_service import store_credit_service

        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if not member:
            return {
                'success': False,
                'error': f'Member not found: {customer_email}',
                'is_member': False
            }

        # Get credit balance
        try:
            balance = store_credit_service.get_balance(member.id)
        except Exception:
            balance = 0

        return {
            'success': True,
            'is_member': True,
            'member': {
                'id': member.id,
                'member_number': member.member_number,
                'email': member.email,
                'name': member.name,
                'tier': member.tier.name if member.tier else None,
                'status': member.status,
                'credit_balance': float(balance),
                'points_balance': member.points_balance or 0,
                'total_trade_ins': member.total_trade_ins or 0,
                'total_trade_value': float(member.total_trade_value or 0),
                'total_bonus_earned': float(member.total_bonus_earned or 0),
                'membership_start_date': member.membership_start_date.isoformat() if member.membership_start_date else None,
                'shopify_customer_id': member.shopify_customer_id
            }
        }

    # ==================== Points Actions ====================

    def action_award_bonus_points(
        self,
        customer_email: str,
        points: int,
        reason: str = 'Shopify Flow bonus',
        idempotency_key: str = None
    ) -> Dict[str, Any]:
        """
        Flow action: Award bonus points to a customer.

        This is an idempotent operation - the same idempotency_key will not
        award points twice.

        Args:
            customer_email: Customer's email address
            points: Number of points to award
            reason: Description for the points award
            idempotency_key: Unique key to prevent duplicate awards

        Returns:
            Dict with result:
                success: Whether points were awarded
                member_id: Member's internal ID
                member_number: Member number (TU1001)
                points_awarded: Number of points awarded
                new_balance: New points balance
                was_duplicate: True if this was a duplicate request
        """
        from ..models import Member
        from .points_service import PointsService

        # Validate input
        if not customer_email:
            return {
                'success': False,
                'error': 'customer_email is required'
            }

        if not points or points <= 0:
            return {
                'success': False,
                'error': 'points must be a positive integer'
            }

        # Find member
        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if not member:
            return {
                'success': False,
                'error': f'Member not found: {customer_email}'
            }

        # Check idempotency
        if idempotency_key:
            cache_key = f"flow_points_{self.tenant_id}_{idempotency_key}"
            if cache_key in self._sent_triggers:
                return {
                    'success': True,
                    'member_id': member.id,
                    'member_number': member.member_number,
                    'points_awarded': points,
                    'new_balance': member.points_balance or 0,
                    'was_duplicate': True
                }
            self._sent_triggers.add(cache_key)

        try:
            points_svc = PointsService(self.tenant_id, self.shopify_client)

            result = points_svc.earn_points(
                member_id=member.id,
                amount=points,
                source_type='bonus',
                source_id=idempotency_key or f'flow_{datetime.utcnow().isoformat()}',
                description=f"Flow: {reason}",
                apply_multipliers=False,  # Bonus points don't get multipliers
                created_by='shopify_flow'
            )

            if result.get('success'):
                return {
                    'success': True,
                    'member_id': member.id,
                    'member_number': member.member_number,
                    'points_awarded': points,
                    'new_balance': result.get('new_balance', 0),
                    'transaction_id': result.get('transaction_id'),
                    'was_duplicate': False
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Failed to award points')
                }

        except Exception as e:
            current_app.logger.error(f"Flow action_award_bonus_points failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def action_send_tier_upgrade_email(
        self,
        customer_email: str,
        old_tier: str = None,
        new_tier: str = None
    ) -> Dict[str, Any]:
        """
        Flow action: Send tier upgrade notification email.

        Triggers the notification service to send a tier upgrade email
        to the customer.

        Args:
            customer_email: Customer's email address
            old_tier: Previous tier name (optional, will use current if not provided)
            new_tier: New tier name (optional, will use current if not provided)

        Returns:
            Dict with result:
                success: Whether email was sent
                member_id: Member's internal ID
                email_sent: True if email was successfully queued
        """
        from ..models import Member
        from .notification_service import notification_service

        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if not member:
            return {
                'success': False,
                'error': f'Member not found: {customer_email}'
            }

        # Determine tier names
        current_tier_name = member.tier.name if member.tier else 'Standard'
        actual_new_tier = new_tier or current_tier_name
        actual_old_tier = old_tier or 'Standard'

        # Get bonus rate for email
        new_bonus_rate = float(member.tier.bonus_rate) if member.tier else 0

        try:
            result = notification_service.send_tier_upgrade(
                tenant_id=self.tenant_id,
                member_id=member.id,
                old_tier_name=actual_old_tier,
                new_tier_name=actual_new_tier,
                new_bonus_rate=new_bonus_rate
            )

            return {
                'success': result.get('success', False),
                'member_id': member.id,
                'member_number': member.member_number,
                'email_sent': result.get('success', False),
                'old_tier': actual_old_tier,
                'new_tier': actual_new_tier,
                'skipped': result.get('skipped', False),
                'skip_reason': result.get('reason') if result.get('skipped') else None
            }

        except Exception as e:
            current_app.logger.error(f"Flow action_send_tier_upgrade_email failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def action_create_reward_reminder(
        self,
        customer_email: str,
        reward_name: str = None,
        points_needed: int = None,
        custom_message: str = None
    ) -> Dict[str, Any]:
        """
        Flow action: Create/send a reward reminder to a customer.

        Sends a notification to the customer about available rewards
        or rewards they're close to earning.

        Args:
            customer_email: Customer's email address
            reward_name: Name of the reward to highlight (optional)
            points_needed: Points needed to reach next reward (optional)
            custom_message: Custom message for the reminder (optional)

        Returns:
            Dict with result:
                success: Whether reminder was created
                member_id: Member's internal ID
                reminder_type: Type of reminder sent
                available_rewards: List of rewards member can redeem
        """
        from ..models import Member
        from ..models.loyalty_points import Reward
        from .notification_service import notification_service

        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if not member:
            return {
                'success': False,
                'error': f'Member not found: {customer_email}'
            }

        # Get member's points balance
        current_balance = member.points_balance or 0

        # Find available rewards
        available_rewards = Reward.query.filter(
            Reward.tenant_id == self.tenant_id,
            Reward.is_active == True,
            Reward.points_cost <= current_balance
        ).order_by(Reward.points_cost.desc()).all()

        # Find next reward they're working toward
        next_reward = Reward.query.filter(
            Reward.tenant_id == self.tenant_id,
            Reward.is_active == True,
            Reward.points_cost > current_balance
        ).order_by(Reward.points_cost.asc()).first()

        # Build reminder data
        reminder_type = 'available' if available_rewards else 'progress'
        featured_reward = reward_name

        if not featured_reward:
            if available_rewards:
                featured_reward = available_rewards[0].name
            elif next_reward:
                featured_reward = next_reward.name

        # Calculate points needed
        if points_needed is None and next_reward:
            points_needed = next_reward.points_cost - current_balance

        # Build email content
        member_name = member.name or member.email.split('@')[0]

        if available_rewards:
            subject = f"You have {len(available_rewards)} reward{'s' if len(available_rewards) > 1 else ''} waiting!"
            text_content = f"""Hi {member_name},

Great news! You have {current_balance} points and can redeem:

"""
            for reward in available_rewards[:3]:  # Top 3 rewards
                text_content += f"- {reward.name} ({reward.points_cost} points)\n"

            text_content += f"""
Don't let your points go to waste - redeem them today!

Your TradeUp Team
"""
        else:
            subject = f"You're {points_needed} points away from {featured_reward}!"
            text_content = f"""Hi {member_name},

You currently have {current_balance} points.

You're only {points_needed} points away from "{featured_reward}"!

Keep earning points to unlock this reward.

Your TradeUp Team
"""

        if custom_message:
            text_content = custom_message

        try:
            # Send the reminder email
            result = notification_service.send_custom_email(
                tenant_id=self.tenant_id,
                to_email=member.email,
                to_name=member.name,
                subject=subject,
                text_content=text_content,
                html_content=None  # Will use text content as HTML
            )

            return {
                'success': result.get('success', False),
                'member_id': member.id,
                'member_number': member.member_number,
                'reminder_type': reminder_type,
                'current_balance': current_balance,
                'points_needed': points_needed,
                'available_rewards': [
                    {'name': r.name, 'points_cost': r.points_cost}
                    for r in available_rewards[:5]
                ],
                'next_reward': {
                    'name': next_reward.name,
                    'points_cost': next_reward.points_cost
                } if next_reward else None,
                'email_sent': result.get('success', False),
                'skipped': result.get('skipped', False)
            }

        except Exception as e:
            current_app.logger.error(f"Flow action_create_reward_reminder failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def action_get_points_balance(
        self,
        customer_email: str
    ) -> Dict[str, Any]:
        """
        Flow action: Get customer's points balance and tier info.

        Useful for Flow conditions and branching logic.

        Args:
            customer_email: Customer's email address

        Returns:
            Dict with points data:
                success: Whether lookup succeeded
                points_balance: Current points balance
                tier: Current tier name
                tier_bonus_percent: Tier bonus rate as percentage
                available_rewards_count: Number of rewards they can redeem
        """
        from ..models import Member
        from ..models.loyalty_points import Reward

        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if not member:
            return {
                'success': False,
                'error': f'Member not found: {customer_email}',
                'is_member': False
            }

        current_balance = member.points_balance or 0

        # Count available rewards
        available_count = Reward.query.filter(
            Reward.tenant_id == self.tenant_id,
            Reward.is_active == True,
            Reward.points_cost <= current_balance
        ).count()

        # Get next reward threshold
        next_reward = Reward.query.filter(
            Reward.tenant_id == self.tenant_id,
            Reward.is_active == True,
            Reward.points_cost > current_balance
        ).order_by(Reward.points_cost.asc()).first()

        tier_name = member.tier.name if member.tier else None
        tier_bonus = float(member.tier.bonus_rate * 100) if member.tier else 0

        return {
            'success': True,
            'is_member': True,
            'member_id': member.id,
            'member_number': member.member_number,
            'email': member.email,
            'points_balance': current_balance,
            'lifetime_points_earned': member.lifetime_points_earned or 0,
            'lifetime_points_spent': member.lifetime_points_spent or 0,
            'tier': tier_name,
            'tier_bonus_percent': tier_bonus,
            'available_rewards_count': available_count,
            'next_reward': {
                'name': next_reward.name,
                'points_cost': next_reward.points_cost,
                'points_needed': next_reward.points_cost - current_balance
            } if next_reward else None,
            'shopify_customer_id': member.shopify_customer_id
        }
