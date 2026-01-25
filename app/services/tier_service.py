"""
Tier Management Service.

Comprehensive service for managing membership tier assignments.
Handles all tier operations with proper validation, auditing, and conflict resolution.

Tier Assignment Priority (highest to lowest):
1. Staff override (always takes precedence)
2. Active subscription
3. One-time purchase
4. Promotional
5. Activity-earned

When conflicts occur, higher priority sources win unless explicitly overridden.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from flask import current_app
from ..extensions import db
from ..models import Member, MembershipTier, Tenant
from ..models.tier_history import TierChangeLog, TierEligibilityRule, TierPromotion, MemberPromoUsage
from ..models.trade_in import TradeInBatch


# Source priority (higher number = higher priority)
SOURCE_PRIORITY = {
    'promo': 10,
    'earned': 20,
    'purchase': 30,
    'subscription': 40,
    'staff': 100,  # Staff can always override
    'system': 50,  # System operations (refunds, expirations)
    'api': 35,     # External API assignments
}


class TierService:
    """
    Central service for all tier management operations.

    Usage:
        service = TierService(tenant_id)
        result = service.assign_tier(member_id, tier_id, source='staff', ...)
    """

    def __init__(self, tenant_id: int, shopify_client=None):
        self.tenant_id = tenant_id
        self.tenant = Tenant.query.get(tenant_id)
        # Create ShopifyClient if not provided (needed for metafield sync and Flow triggers)
        if shopify_client:
            self.shopify_client = shopify_client
        else:
            try:
                from .shopify_client import ShopifyClient
                self.shopify_client = ShopifyClient(tenant_id)
            except Exception:
                self.shopify_client = None

    # ==================== Core Tier Assignment ====================

    def assign_tier(
        self,
        member_id: int,
        tier_id: int,
        source_type: str,
        source_reference: str,
        reason: str = None,
        expires_at: datetime = None,
        created_by: str = None,
        force: bool = False,
        metadata: dict = None
    ) -> Dict[str, Any]:
        """
        Assign a tier to a member with full validation and auditing.

        Args:
            member_id: Member to assign tier to
            tier_id: Tier to assign
            source_type: 'staff', 'purchase', 'subscription', 'earned', 'promo'
            source_reference: Reference ID (e.g., 'staff:email', 'order:123')
            reason: Human-readable reason for the change
            expires_at: When this tier assignment expires (optional)
            created_by: Who made this change
            force: Override priority checks
            metadata: Additional structured data

        Returns:
            Dict with success status and details
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        tier = MembershipTier.query.filter_by(id=tier_id, tenant_id=self.tenant_id, is_active=True).first()
        if not tier:
            return {'success': False, 'error': 'Tier not found or inactive'}

        # Check priority unless forced
        if not force and member.tier_id:
            current_priority = self._get_source_priority(member.tier_assigned_by)
            new_priority = SOURCE_PRIORITY.get(source_type, 0)

            if new_priority < current_priority:
                return {
                    'success': False,
                    'error': f'Cannot override {self._get_source_type(member.tier_assigned_by)} assignment with {source_type}',
                    'current_source': member.tier_assigned_by,
                    'requires_force': True
                }

        # Determine change type
        change_type = self._determine_change_type(member, tier, source_type)

        # Store previous tier info
        previous_tier_id = member.tier_id
        previous_tier_name = member.tier.name if member.tier else None

        # Apply the tier change
        member.tier_id = tier_id
        member.tier_assigned_by = f'{source_type}:{source_reference}'
        member.tier_assigned_at = datetime.utcnow()
        member.tier_expires_at = expires_at

        # If member was inactive, activate them
        if member.status in ['pending', 'expired']:
            member.status = 'active'

        # Create audit log
        log = TierChangeLog(
            tenant_id=self.tenant_id,
            member_id=member_id,
            previous_tier_id=previous_tier_id,
            new_tier_id=tier_id,
            previous_tier_name=previous_tier_name,
            new_tier_name=tier.name,
            change_type=change_type,
            source_type=source_type,
            source_reference=source_reference,
            reason=reason,
            expires_at=expires_at,
            created_by=created_by,
            extra_data=metadata or {}
        )
        db.session.add(log)

        try:
            db.session.commit()
            current_app.logger.info(
                f'Tier assigned: {member.member_number} -> {tier.name} ({source_type}:{source_reference})'
            )

            # Sync member metafields to Shopify (non-blocking)
            try:
                from .membership_service import MembershipService
                membership_svc = MembershipService(self.tenant_id, self.shopify_client)
                membership_svc.sync_member_metafields_to_shopify(member)
            except Exception as sync_err:
                current_app.logger.warning(f'Metafield sync failed: {sync_err}')

            # Trigger Shopify Flow events for tier change
            if previous_tier_name != tier.name:  # Only if tier actually changed
                try:
                    from .flow_service import FlowService
                    flow_svc = FlowService(self.tenant_id, self.shopify_client)

                    # Get bonus rates for the Flow payload
                    old_bonus = 0
                    if previous_tier_id:
                        old_tier = MembershipTier.query.get(previous_tier_id)
                        old_bonus = float(old_tier.bonus_rate) if old_tier else 0
                    new_bonus = float(tier.bonus_rate)

                    # Send the general tier_changed trigger
                    flow_svc.trigger_tier_changed(
                        member_id=member.id,
                        member_number=member.member_number,
                        email=member.email,
                        old_tier=previous_tier_name or 'None',
                        new_tier=tier.name,
                        change_type=change_type,
                        source=source_type,
                        shopify_customer_id=member.shopify_customer_id
                    )

                    # Send the more specific trigger based on change type
                    if change_type == 'upgrade':
                        flow_svc.trigger_tier_upgraded(
                            member_id=member.id,
                            member_number=member.member_number,
                            email=member.email,
                            old_tier=previous_tier_name or 'None',
                            new_tier=tier.name,
                            old_tier_bonus=old_bonus,
                            new_tier_bonus=new_bonus,
                            source=source_type,
                            shopify_customer_id=member.shopify_customer_id
                        )
                    elif change_type == 'downgrade':
                        flow_svc.trigger_tier_downgraded(
                            member_id=member.id,
                            member_number=member.member_number,
                            email=member.email,
                            old_tier=previous_tier_name or 'None',
                            new_tier=tier.name,
                            old_tier_bonus=old_bonus,
                            new_tier_bonus=new_bonus,
                            reason=source_type,
                            shopify_customer_id=member.shopify_customer_id
                        )

                except Exception as flow_err:
                    current_app.logger.warning(f'Flow trigger failed: {flow_err}')

            return {
                'success': True,
                'member_id': member_id,
                'member_number': member.member_number,
                'tier_id': tier_id,
                'tier_name': tier.name,
                'previous_tier': previous_tier_name,
                'change_type': change_type,
                'expires_at': expires_at.isoformat() if expires_at else None,
                'log_id': log.id
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Tier assignment failed: {str(e)}')
            return {'success': False, 'error': str(e)}

    def remove_tier(
        self,
        member_id: int,
        source_type: str,
        source_reference: str,
        reason: str = None,
        created_by: str = None
    ) -> Dict[str, Any]:
        """
        Remove tier from a member.

        Args:
            member_id: Member to remove tier from
            source_type: Why tier is being removed
            source_reference: Reference for audit
            reason: Human-readable reason
            created_by: Who made this change

        Returns:
            Dict with success status
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        if not member.tier_id:
            return {'success': True, 'message': 'Member has no tier'}

        # Store previous tier info
        previous_tier_id = member.tier_id
        previous_tier_name = member.tier.name if member.tier else None

        # Determine change type
        change_type = 'removed'
        if source_type == 'subscription':
            change_type = 'subscription_cancelled'
        elif source_type == 'system' and 'expired' in (reason or '').lower():
            change_type = 'expired'
        elif source_type == 'system' and 'refund' in (reason or '').lower():
            change_type = 'refunded'

        # Remove tier
        member.tier_id = None
        member.tier_assigned_by = None
        member.tier_assigned_at = None
        member.tier_expires_at = None
        member.subscription_status = 'none'

        # Create audit log
        log = TierChangeLog(
            tenant_id=self.tenant_id,
            member_id=member_id,
            previous_tier_id=previous_tier_id,
            new_tier_id=None,
            previous_tier_name=previous_tier_name,
            new_tier_name=None,
            change_type=change_type,
            source_type=source_type,
            source_reference=source_reference,
            reason=reason,
            created_by=created_by
        )
        db.session.add(log)

        try:
            db.session.commit()
            current_app.logger.info(
                f'Tier removed: {member.member_number} (was {previous_tier_name}) - {reason}'
            )
            return {
                'success': True,
                'member_id': member_id,
                'previous_tier': previous_tier_name,
                'change_type': change_type
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    # ==================== Bulk Operations ====================

    def bulk_assign_tier(
        self,
        member_ids: List[int],
        tier_id: int,
        source_type: str,
        source_reference: str,
        reason: str = None,
        expires_at: datetime = None,
        created_by: str = None
    ) -> Dict[str, Any]:
        """
        Assign tier to multiple members at once.

        Returns:
            Dict with success count and any failures
        """
        results = {
            'success_count': 0,
            'failure_count': 0,
            'failures': []
        }

        for member_id in member_ids:
            result = self.assign_tier(
                member_id=member_id,
                tier_id=tier_id,
                source_type=source_type,
                source_reference=source_reference,
                reason=reason,
                expires_at=expires_at,
                created_by=created_by
            )

            if result.get('success'):
                results['success_count'] += 1
            else:
                results['failure_count'] += 1
                results['failures'].append({
                    'member_id': member_id,
                    'error': result.get('error')
                })

        return results

    # ==================== Staff Assignment ====================

    def staff_assign_tier(
        self,
        member_id: int,
        tier_id: int,
        staff_email: str,
        reason: str = None,
        duration_days: int = None,
        notes: str = None
    ) -> Dict[str, Any]:
        """
        Staff manually assigns a tier to a member.

        This is the highest priority assignment and overrides all others.

        Args:
            member_id: Member to assign
            tier_id: Tier to assign (or None to remove)
            staff_email: Email of staff making the change
            reason: Why this assignment was made
            duration_days: How long the tier lasts (None = permanent)
            notes: Additional notes

        Returns:
            Dict with result
        """
        expires_at = None
        if duration_days:
            expires_at = datetime.utcnow() + timedelta(days=duration_days)

        if tier_id is None:
            return self.remove_tier(
                member_id=member_id,
                source_type='staff',
                source_reference=staff_email,
                reason=reason or 'Removed by staff',
                created_by=staff_email
            )

        return self.assign_tier(
            member_id=member_id,
            tier_id=tier_id,
            source_type='staff',
            source_reference=staff_email,
            reason=reason or 'Assigned by staff',
            expires_at=expires_at,
            created_by=staff_email,
            force=True,  # Staff can always override
            metadata={'notes': notes} if notes else None
        )

    # ==================== Purchase-Based Assignment ====================

    def process_purchase(
        self,
        member_id: int,
        order_id: str,
        tier_id: int,
        order_total: Decimal = None,
        product_sku: str = None,
        is_subscription: bool = False
    ) -> Dict[str, Any]:
        """
        Process a tier purchase from an order.

        Args:
            member_id: Member who purchased
            order_id: Shopify order ID
            tier_id: Tier they purchased
            order_total: Order total (for audit)
            product_sku: SKU of membership product
            is_subscription: Whether this is a subscription purchase

        Returns:
            Dict with result
        """
        source_type = 'subscription' if is_subscription else 'purchase'

        return self.assign_tier(
            member_id=member_id,
            tier_id=tier_id,
            source_type=source_type,
            source_reference=f'order_{order_id}',
            reason=f'Purchased via order #{order_id}',
            created_by='system:order_webhook',
            metadata={
                'order_id': order_id,
                'order_total': float(order_total) if order_total else None,
                'product_sku': product_sku,
                'is_subscription': is_subscription
            }
        )

    def process_refund(
        self,
        member_id: int,
        order_id: str,
        reason: str = None
    ) -> Dict[str, Any]:
        """
        Handle a refund for a tier purchase.

        If the member's current tier came from this order, remove it.

        Args:
            member_id: Member who was refunded
            order_id: Order that was refunded
            reason: Refund reason

        Returns:
            Dict with result
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        # Check if current tier is from this order
        current_source = member.tier_assigned_by or ''
        if f'order_{order_id}' not in current_source:
            return {
                'success': True,
                'message': 'Current tier not from this order, no change needed'
            }

        return self.remove_tier(
            member_id=member_id,
            source_type='system',
            source_reference=f'refund_order_{order_id}',
            reason=reason or f'Refunded order #{order_id}',
            created_by='system:refund_webhook'
        )

    # ==================== Subscription-Based Assignment ====================

    def process_subscription_started(
        self,
        member_id: int,
        contract_id: str,
        tier_id: int,
        selling_plan_id: str = None
    ) -> Dict[str, Any]:
        """
        Handle a new subscription contract.

        Args:
            member_id: Member who subscribed
            contract_id: Shopify subscription contract GID
            tier_id: Tier associated with this subscription
            selling_plan_id: Shopify selling plan ID

        Returns:
            Dict with result
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        result = self.assign_tier(
            member_id=member_id,
            tier_id=tier_id,
            source_type='subscription',
            source_reference=contract_id,
            reason='Subscription started',
            created_by='system:subscription_webhook',
            metadata={
                'contract_id': contract_id,
                'selling_plan_id': selling_plan_id
            }
        )

        if result.get('success'):
            # Update subscription-specific fields
            member.shopify_subscription_contract_id = contract_id
            member.subscription_status = 'active'
            db.session.commit()

        return result

    def process_subscription_cancelled(
        self,
        member_id: int,
        contract_id: str,
        reason: str = None,
        immediate: bool = True
    ) -> Dict[str, Any]:
        """
        Handle subscription cancellation.

        Args:
            member_id: Member whose subscription was cancelled
            contract_id: Subscription contract ID
            reason: Cancellation reason
            immediate: If True, remove tier now. If False, let it expire naturally.

        Returns:
            Dict with result
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        # Update subscription status
        member.subscription_status = 'cancelled'
        member.shopify_subscription_contract_id = None

        if immediate:
            # Check if current tier is from this subscription
            current_source = member.tier_assigned_by or ''
            if contract_id in current_source or current_source.startswith('subscription:'):
                result = self.remove_tier(
                    member_id=member_id,
                    source_type='subscription',
                    source_reference=f'cancelled_{contract_id}',
                    reason=reason or 'Subscription cancelled',
                    created_by='system:subscription_webhook'
                )
                return result

        db.session.commit()
        return {
            'success': True,
            'message': 'Subscription marked as cancelled',
            'tier_retained': True
        }

    def process_subscription_billing_failed(
        self,
        member_id: int,
        contract_id: str,
        attempt_count: int = 1
    ) -> Dict[str, Any]:
        """
        Handle failed subscription billing.

        Args:
            member_id: Member with failed billing
            contract_id: Subscription contract ID
            attempt_count: Number of failed attempts

        Returns:
            Dict with result
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        member.subscription_status = 'past_due'

        # Log the billing failure
        log = TierChangeLog(
            tenant_id=self.tenant_id,
            member_id=member_id,
            previous_tier_id=member.tier_id,
            new_tier_id=member.tier_id,  # Tier not changed yet
            previous_tier_name=member.tier.name if member.tier else None,
            new_tier_name=member.tier.name if member.tier else None,
            change_type='billing_failed',
            source_type='subscription',
            source_reference=contract_id,
            reason=f'Billing failed (attempt {attempt_count})',
            created_by='system:billing_webhook',
            extra_data={'attempt_count': attempt_count}
        )
        db.session.add(log)
        db.session.commit()

        # Could implement grace period logic here
        # e.g., after 3 failed attempts, pause or remove tier

        return {
            'success': True,
            'status': 'past_due',
            'attempt_count': attempt_count
        }

    # ==================== Promotional Assignment ====================

    def apply_promotion(
        self,
        member_id: int,
        promotion_id: int = None,
        promo_code: str = None
    ) -> Dict[str, Any]:
        """
        Apply a promotional tier to a member.

        Args:
            member_id: Member to apply promo to
            promotion_id: Promotion ID (or use promo_code)
            promo_code: Promo code to look up

        Returns:
            Dict with result
        """
        # Find the promotion
        if promo_code:
            promotion = TierPromotion.query.filter_by(
                tenant_id=self.tenant_id,
                code=promo_code.upper(),
                is_active=True
            ).first()
        else:
            promotion = TierPromotion.query.filter_by(
                id=promotion_id,
                tenant_id=self.tenant_id,
                is_active=True
            ).first()

        if not promotion:
            return {'success': False, 'error': 'Promotion not found'}

        if not promotion.is_currently_active:
            return {'success': False, 'error': 'Promotion is not currently active'}

        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        # Check if member already used this promo
        existing_usage = MemberPromoUsage.query.filter_by(
            member_id=member_id,
            promotion_id=promotion.id
        ).first()

        if existing_usage:
            return {'success': False, 'error': 'Member has already used this promotion'}

        # Check usage limits
        if promotion.max_uses and promotion.current_uses >= promotion.max_uses:
            return {'success': False, 'error': 'Promotion has reached maximum uses'}

        # Check targeting
        if not self._check_promo_eligibility(member, promotion):
            return {'success': False, 'error': 'Member not eligible for this promotion'}

        # Check if upgrade only
        if promotion.upgrade_only and member.tier:
            promo_tier = promotion.tier
            if member.tier.bonus_rate >= promo_tier.bonus_rate:
                return {
                    'success': False,
                    'error': 'Current tier is equal or better than promotional tier'
                }

        # Calculate expiration
        if promotion.grant_duration_days:
            expires_at = datetime.utcnow() + timedelta(days=promotion.grant_duration_days)
        else:
            expires_at = promotion.ends_at

        # Store previous tier for potential revert
        previous_tier_id = member.tier_id

        # Record usage
        usage = MemberPromoUsage(
            tenant_id=self.tenant_id,
            member_id=member_id,
            promotion_id=promotion.id,
            previous_tier_id=previous_tier_id,
            expires_at=expires_at,
            status='active'
        )
        db.session.add(usage)

        # Increment usage counter
        promotion.current_uses = (promotion.current_uses or 0) + 1

        # Assign the tier
        result = self.assign_tier(
            member_id=member_id,
            tier_id=promotion.tier_id,
            source_type='promo',
            source_reference=f'{promotion.id}:{promotion.code or promotion.name}',
            reason=f'Promotion: {promotion.name}',
            expires_at=expires_at,
            created_by='system:promotion',
            metadata={
                'promotion_id': promotion.id,
                'promotion_name': promotion.name,
                'promo_code': promotion.code,
                'previous_tier_id': previous_tier_id
            }
        )

        if not result.get('success'):
            db.session.rollback()
            return result

        return {
            **result,
            'promotion_name': promotion.name,
            'promo_code': promotion.code
        }

    def expire_promotion(
        self,
        member_id: int,
        promotion_id: int
    ) -> Dict[str, Any]:
        """
        Expire a promotional tier and revert to previous tier.

        Args:
            member_id: Member whose promo is expiring
            promotion_id: Promotion that's expiring

        Returns:
            Dict with result
        """
        usage = MemberPromoUsage.query.filter_by(
            member_id=member_id,
            promotion_id=promotion_id,
            status='active'
        ).first()

        if not usage:
            return {'success': True, 'message': 'No active promo usage found'}

        promotion = usage.promotion

        # Mark usage as expired
        usage.status = 'expired'
        usage.reverted_at = datetime.utcnow()

        member = Member.query.get(member_id)

        # Check if current tier is from this promo
        if member.tier_assigned_by and f'{promotion_id}:' in member.tier_assigned_by:
            # Revert to previous tier if configured
            if promotion.revert_on_expire and usage.previous_tier_id:
                return self.assign_tier(
                    member_id=member_id,
                    tier_id=usage.previous_tier_id,
                    source_type='system',
                    source_reference=f'promo_expired_{promotion_id}',
                    reason=f'Reverted after promotion "{promotion.name}" expired',
                    created_by='system:promo_expiry'
                )
            else:
                return self.remove_tier(
                    member_id=member_id,
                    source_type='system',
                    source_reference=f'promo_expired_{promotion_id}',
                    reason=f'Promotion "{promotion.name}" expired',
                    created_by='system:promo_expiry'
                )

        db.session.commit()
        return {'success': True, 'message': 'Promo usage marked as expired'}

    # ==================== Activity-Based (Earned) Assignment ====================

    def check_earned_tier_eligibility(
        self,
        member_id: int,
        apply_if_eligible: bool = False
    ) -> Dict[str, Any]:
        """
        Check if a member qualifies for an earned tier based on activity.

        Args:
            member_id: Member to check
            apply_if_eligible: If True, automatically assign the tier

        Returns:
            Dict with eligibility results
        """
        member = Member.query.filter_by(id=member_id, tenant_id=self.tenant_id).first()
        if not member:
            return {'success': False, 'error': 'Member not found'}

        # Get active eligibility rules ordered by tier (highest first)
        rules = TierEligibilityRule.query.filter_by(
            tenant_id=self.tenant_id,
            is_active=True,
            rule_type='qualification'
        ).order_by(TierEligibilityRule.priority.desc()).all()

        if not rules:
            return {
                'success': True,
                'eligible_for': None,
                'message': 'No eligibility rules configured'
            }

        # Get member stats
        stats = self._get_member_stats(member, max_days=365)

        eligible_tier = None
        eligible_rule = None
        all_results = []

        for rule in rules:
            is_eligible = self._evaluate_rule(rule, stats)
            all_results.append({
                'rule_id': rule.id,
                'rule_name': rule.name,
                'tier_id': rule.tier_id,
                'metric': rule.metric,
                'threshold': float(rule.threshold_value),
                'current_value': stats.get(rule.metric, 0),
                'is_eligible': is_eligible
            })

            if is_eligible and (not eligible_tier or rule.priority > eligible_rule.priority):
                eligible_tier = rule.tier
                eligible_rule = rule

        result = {
            'success': True,
            'member_id': member_id,
            'current_tier': member.tier.name if member.tier else None,
            'eligible_for': eligible_tier.name if eligible_tier else None,
            'eligible_tier_id': eligible_tier.id if eligible_tier else None,
            'rule_evaluations': all_results,
            'stats': stats
        }

        # Apply if requested
        if apply_if_eligible:
            if eligible_tier:
                # Check if this is different from current tier
                if not member.tier or eligible_tier.id != member.tier_id:
                    # Determine if upgrade or downgrade
                    current_bonus = member.tier.bonus_rate if member.tier else 0
                    new_bonus = eligible_tier.bonus_rate

                    change_type = 'upgraded' if new_bonus > current_bonus else 'downgraded'

                    assign_result = self.assign_tier(
                        member_id=member_id,
                        tier_id=eligible_tier.id,
                        source_type='earned',
                        source_reference=f'rule_{eligible_rule.id}:{eligible_rule.name}',
                        reason=f'{change_type.capitalize()} via: {eligible_rule.name}',
                        created_by='system:eligibility_check',
                        metadata={
                            'rule_id': eligible_rule.id,
                            'metric': eligible_rule.metric,
                            'value_achieved': stats.get(eligible_rule.metric),
                            'change_type': change_type
                        }
                    )
                    result['tier_assigned'] = assign_result.get('success', False)
                    result['change_type'] = change_type
            elif member.tier and member.tier_assigned_by == 'earned':
                # Member has earned tier but no longer qualifies - check for downgrade rules
                downgrade_rules = TierEligibilityRule.query.filter_by(
                    tenant_id=self.tenant_id,
                    is_active=True,
                    rule_type='downgrade'
                ).all()

                if downgrade_rules:
                    # Apply downgrade to lowest tier or remove
                    lowest_tier = MembershipTier.query.filter_by(
                        tenant_id=self.tenant_id,
                        is_active=True
                    ).order_by(MembershipTier.bonus_rate.asc()).first()

                    if lowest_tier and lowest_tier.id != member.tier_id:
                        assign_result = self.assign_tier(
                            member_id=member_id,
                            tier_id=lowest_tier.id,
                            source_type='earned',
                            source_reference='downgrade:no_longer_eligible',
                            reason='No longer meets tier requirements',
                            created_by='system:eligibility_check',
                            metadata={'change_type': 'downgraded'}
                        )
                        result['tier_assigned'] = assign_result.get('success', False)
                        result['change_type'] = 'downgraded'
                        result['downgrade_reason'] = 'No longer meets tier requirements'

        return result

    def process_activity_batch(
        self,
        member_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Check all members (or specified list) for earned tier eligibility.

        This should be run periodically (e.g., daily cron job).

        Args:
            member_ids: Specific members to check (None = all active members)

        Returns:
            Dict with processing results
        """
        if member_ids:
            members = Member.query.filter(
                Member.id.in_(member_ids),
                Member.tenant_id == self.tenant_id
            ).all()
        else:
            members = Member.query.filter_by(
                tenant_id=self.tenant_id,
                status='active'
            ).all()

        results = {
            'checked': 0,
            'upgraded': 0,
            'downgraded': 0,
            'unchanged': 0,
            'errors': 0
        }

        for member in members:
            try:
                result = self.check_earned_tier_eligibility(
                    member_id=member.id,
                    apply_if_eligible=True
                )
                results['checked'] += 1

                if result.get('tier_assigned'):
                    eligible_tier_id = result.get('eligible_tier_id')
                    if member.tier and eligible_tier_id:
                        eligible_tier = MembershipTier.query.get(eligible_tier_id)
                        if eligible_tier.bonus_rate > member.tier.bonus_rate:
                            results['upgraded'] += 1
                        else:
                            results['downgraded'] += 1
                    else:
                        results['upgraded'] += 1
                else:
                    results['unchanged'] += 1

            except Exception as e:
                current_app.logger.error(f'Error checking eligibility for member {member.id}: {e}')
                results['errors'] += 1

        return results

    # ==================== Expiration Processing ====================

    def process_expired_tiers(self) -> Dict[str, Any]:
        """
        Process all expired tiers.

        Should be run periodically (e.g., hourly cron job).

        Returns:
            Dict with processing results
        """
        now = datetime.utcnow()

        # Find members with expired tiers
        expired_members = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.tier_expires_at.isnot(None),
            Member.tier_expires_at <= now,
            Member.tier_id.isnot(None)
        ).all()

        results = {
            'processed': 0,
            'removed': 0,
            'reverted': 0,
            'errors': 0
        }

        for member in expired_members:
            try:
                results['processed'] += 1

                # Check if this was a promo that needs reverting
                if member.tier_assigned_by and member.tier_assigned_by.startswith('promo:'):
                    promo_id = int(member.tier_assigned_by.split(':')[1].split(':')[0])
                    result = self.expire_promotion(member.id, promo_id)
                    if result.get('success'):
                        results['reverted'] += 1
                else:
                    # Just remove the tier
                    result = self.remove_tier(
                        member_id=member.id,
                        source_type='system',
                        source_reference='expiration',
                        reason='Tier assignment expired',
                        created_by='system:expiry_cron'
                    )
                    if result.get('success'):
                        results['removed'] += 1

            except Exception as e:
                current_app.logger.error(f'Error processing expiration for member {member.id}: {e}')
                results['errors'] += 1

        # Also process expired promo usages
        expired_promos = MemberPromoUsage.query.filter(
            MemberPromoUsage.tenant_id == self.tenant_id,
            MemberPromoUsage.status == 'active',
            MemberPromoUsage.expires_at <= now
        ).all()

        for usage in expired_promos:
            try:
                result = self.expire_promotion(usage.member_id, usage.promotion_id)
                if result.get('success'):
                    results['reverted'] += 1
            except Exception as e:
                current_app.logger.error(f'Error expiring promo usage {usage.id}: {e}')
                results['errors'] += 1

        return results

    # ==================== History & Audit ====================

    def get_tier_history(
        self,
        member_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get tier change history for a member.

        Args:
            member_id: Member to get history for
            limit: Max records to return
            offset: Pagination offset

        Returns:
            Dict with history records
        """
        query = TierChangeLog.query.filter_by(
            tenant_id=self.tenant_id,
            member_id=member_id
        ).order_by(TierChangeLog.created_at.desc())

        total = query.count()
        logs = query.limit(limit).offset(offset).all()

        return {
            'success': True,
            'history': [log.to_dict() for log in logs],
            'total': total,
            'limit': limit,
            'offset': offset
        }

    # ==================== Helper Methods ====================

    def _get_source_priority(self, source_ref: str) -> int:
        """Extract priority from a source reference string."""
        if not source_ref:
            return 0
        source_type = source_ref.split(':')[0] if ':' in source_ref else source_ref
        return SOURCE_PRIORITY.get(source_type, 0)

    def _get_source_type(self, source_ref: str) -> str:
        """Extract source type from a source reference string."""
        if not source_ref:
            return 'unknown'
        return source_ref.split(':')[0] if ':' in source_ref else source_ref

    def _determine_change_type(
        self,
        member: Member,
        new_tier: MembershipTier,
        source_type: str
    ) -> str:
        """Determine the type of tier change."""
        if not member.tier_id:
            if source_type == 'subscription':
                return 'subscription_started'
            elif source_type == 'purchase':
                return 'purchase'
            elif source_type == 'promo':
                return 'promo_applied'
            elif source_type == 'earned':
                return 'earned'
            return 'assigned'

        current_tier = member.tier
        if new_tier.bonus_rate > current_tier.bonus_rate:
            return 'upgraded'
        elif new_tier.bonus_rate < current_tier.bonus_rate:
            return 'downgraded'
        return 'changed'  # Same level, different tier

    def _check_promo_eligibility(
        self,
        member: Member,
        promotion: TierPromotion
    ) -> bool:
        """Check if member is eligible for a promotion."""
        if promotion.target_type == 'all':
            return True

        if promotion.target_type == 'new_members':
            # Member joined in last 30 days
            if member.membership_start_date:
                days_since_join = (datetime.utcnow().date() - member.membership_start_date).days
                return days_since_join <= 30
            return True

        if promotion.target_type == 'tier_specific':
            if promotion.target_tiers and member.tier_id:
                return member.tier_id in promotion.target_tiers
            return not promotion.target_tiers  # If no tiers specified, allow all

        if promotion.target_type == 'tagged':
            # Check if member has any of the required tags
            # Tags are stored in Shopify and synced to member.tags (JSON field)
            if not promotion.target_tags:
                return True  # No tags required, allow all
            member_tags = getattr(member, 'tags', None) or []
            if isinstance(member_tags, str):
                member_tags = [t.strip() for t in member_tags.split(',') if t.strip()]
            # Check if any member tag matches the required tags (case-insensitive)
            member_tags_lower = [t.lower() for t in member_tags]
            for required_tag in promotion.target_tags:
                if required_tag.lower() in member_tags_lower:
                    return True
            return False

        if promotion.target_type == 'manual':
            # Manual targeting uses a list of specific member IDs
            # Stored in promotion.target_member_ids (JSON field)
            target_member_ids = getattr(promotion, 'target_member_ids', None) or []
            if not target_member_ids:
                return True  # No specific members, allow all
            return member.id in target_member_ids

        return True

    def _get_member_stats(self, member: Member, max_days: int = None) -> Dict[str, Any]:
        """Get member activity stats for eligibility checking."""
        stats = {
            'total_spend': float(member.total_trade_value or 0),
            'trade_in_count': member.total_trade_ins or 0,
            'trade_in_value': float(member.total_trade_value or 0),
            'bonus_earned': float(member.total_bonus_earned or 0),
            'points_earned': getattr(member, 'lifetime_points', 0) or 0,
            'membership_duration': 0
        }

        if member.membership_start_date:
            stats['membership_duration'] = (
                datetime.utcnow().date() - member.membership_start_date
            ).days

        # Calculate time-windowed stats if max_days is specified
        if max_days:
            cutoff_date = datetime.utcnow() - timedelta(days=max_days)

            # Query trade-ins within the time window
            windowed_batches = TradeInBatch.query.filter(
                TradeInBatch.member_id == member.id,
                TradeInBatch.created_at >= cutoff_date,
                TradeInBatch.status == 'completed'
            ).all()

            # Calculate windowed stats
            windowed_trade_count = len(windowed_batches)
            windowed_trade_value = sum(
                float(batch.total_trade_value or 0)
                for batch in windowed_batches
            )
            windowed_bonus = sum(
                float(batch.bonus_amount or 0)
                for batch in windowed_batches
            )

            # Override stats with windowed values
            stats['trade_in_count'] = windowed_trade_count
            stats['trade_in_value'] = windowed_trade_value
            stats['total_spend'] = windowed_trade_value
            stats['bonus_earned'] = max(0, windowed_bonus)

        return stats

    def _evaluate_rule(self, rule: TierEligibilityRule, stats: Dict) -> bool:
        """Evaluate a single eligibility rule against member stats."""
        current_value = Decimal(str(stats.get(rule.metric, 0)))
        threshold = rule.threshold_value

        if rule.threshold_operator == '>=':
            return current_value >= threshold
        elif rule.threshold_operator == '>':
            return current_value > threshold
        elif rule.threshold_operator == '<=':
            return current_value <= threshold
        elif rule.threshold_operator == '<':
            return current_value < threshold
        elif rule.threshold_operator == '==':
            return current_value == threshold
        elif rule.threshold_operator == 'between':
            return threshold <= current_value <= (rule.threshold_max or threshold)

        return False

    # ==================== Shopify Discount Management ====================

    def sync_tier_discounts_to_shopify(self, shopify_client) -> Dict[str, Any]:
        """
        Sync all tier discount codes to Shopify.

        Creates discount codes for each tier that has a store_discount_pct > 0.
        The discount codes are:
        - TRADEUP-BRONZE (10% off)
        - TRADEUP-SILVER (15% off)
        - TRADEUP-GOLD (20% off)

        Members can use their tier's discount code at checkout.
        Validation happens via customer tags (tradeup-bronze, etc.)

        Args:
            shopify_client: ShopifyClient instance

        Returns:
            Dict with sync results
        """
        from ..models.promotions import TierConfiguration

        tiers = TierConfiguration.query.filter_by(
            tenant_id=self.tenant_id,
            is_active=True
        ).order_by(TierConfiguration.rank).all()

        results = {
            'created': [],
            'updated': [],
            'skipped': [],
            'errors': []
        }

        for tier in tiers:
            discount_pct = float(tier.store_discount_pct or 0)

            if discount_pct <= 0:
                results['skipped'].append({
                    'tier': tier.name,
                    'reason': 'No store discount configured'
                })
                continue

            customer_tag = f'tradeup-{tier.name.lower()}'

            try:
                result = shopify_client.create_tier_discount_code(
                    tier_name=tier.name,
                    percentage=discount_pct,
                    customer_tag=customer_tag
                )

                if result.get('success'):
                    results['created'].append({
                        'tier': tier.name,
                        'code': result.get('code'),
                        'percentage': discount_pct,
                        'discount_id': result.get('discount_id')
                    })
                else:
                    # Might already exist
                    errors = result.get('errors', [])
                    if any('taken' in str(e).lower() for e in errors):
                        results['updated'].append({
                            'tier': tier.name,
                            'code': f'TRADEUP-{tier.name.upper()}',
                            'percentage': discount_pct,
                            'note': 'Code already exists'
                        })
                    else:
                        results['errors'].append({
                            'tier': tier.name,
                            'error': result.get('errors') or result.get('error')
                        })
            except Exception as e:
                results['errors'].append({
                    'tier': tier.name,
                    'error': str(e)
                })

        return {
            'success': len(results['errors']) == 0,
            'summary': {
                'created': len(results['created']),
                'updated': len(results['updated']),
                'skipped': len(results['skipped']),
                'errors': len(results['errors'])
            },
            'details': results
        }

    def get_tier_discount_codes(self) -> List[Dict[str, Any]]:
        """
        Get all tier discount codes configuration.

        Returns:
            List of tier discount code info
        """
        from ..models.promotions import TierConfiguration

        tiers = TierConfiguration.query.filter_by(
            tenant_id=self.tenant_id,
            is_active=True
        ).order_by(TierConfiguration.rank).all()

        codes = []
        for tier in tiers:
            discount_pct = float(tier.store_discount_pct or 0)
            if discount_pct > 0:
                codes.append({
                    'tier_id': tier.id,
                    'tier_name': tier.name,
                    'code': f'TRADEUP-{tier.name.upper()}',
                    'percentage': discount_pct,
                    'customer_tag': f'tradeup-{tier.name.lower()}',
                    'description': f'{int(discount_pct)}% off for {tier.name} members'
                })

        return codes
