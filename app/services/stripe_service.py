"""
Stripe integration service for membership payments.
Handles customer creation, subscriptions, checkout sessions, and webhooks.
"""
import os
import stripe
from datetime import datetime
from typing import Optional
from ..extensions import db
from ..models import Member, MembershipTier, Tenant


class StripeService:
    """Service for handling Stripe billing operations."""

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.tenant = Tenant.query.get(tenant_id)

        # Initialize Stripe with tenant's key or global key
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

    def create_customer(self, email: str, name: str, member_id: int) -> str:
        """
        Create a Stripe customer for a member.

        Args:
            email: Customer email
            name: Customer name
            member_id: Internal member ID

        Returns:
            Stripe customer ID (cus_xxxxx)
        """
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={
                'member_id': str(member_id),
                'tenant_id': str(self.tenant_id),
                'tenant_slug': self.tenant.slug if self.tenant else 'unknown'
            }
        )
        return customer.id

    def create_checkout_session(
        self,
        tier_id: int,
        member_id: int,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None,
        stripe_customer_id: Optional[str] = None
    ) -> dict:
        """
        Create a Stripe Checkout session for subscription signup.

        Args:
            tier_id: MembershipTier ID
            member_id: Member ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment cancelled
            customer_email: Pre-fill email if no customer yet
            stripe_customer_id: Existing Stripe customer ID

        Returns:
            Dict with session_id and url
        """
        tier = MembershipTier.query.get(tier_id)
        if not tier or not tier.stripe_price_id:
            raise ValueError(f"Tier {tier_id} not configured with Stripe price")

        session_params = {
            'mode': 'subscription',
            'payment_method_types': ['card'],
            'line_items': [{
                'price': tier.stripe_price_id,
                'quantity': 1
            }],
            'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': cancel_url,
            'metadata': {
                'member_id': str(member_id),
                'tier_id': str(tier_id),
                'tenant_id': str(self.tenant_id)
            },
            'subscription_data': {
                'metadata': {
                    'member_id': str(member_id),
                    'tier_id': str(tier_id),
                    'tenant_id': str(self.tenant_id)
                }
            }
        }

        if stripe_customer_id:
            session_params['customer'] = stripe_customer_id
        elif customer_email:
            session_params['customer_email'] = customer_email

        session = stripe.checkout.Session.create(**session_params)

        return {
            'session_id': session.id,
            'url': session.url
        }

    def create_billing_portal_session(
        self,
        stripe_customer_id: str,
        return_url: str
    ) -> dict:
        """
        Create a Stripe billing portal session for subscription management.

        Args:
            stripe_customer_id: Stripe customer ID
            return_url: URL to return to after portal session

        Returns:
            Dict with url
        """
        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url
        )

        return {'url': session.url}

    def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True
    ) -> dict:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True, cancel at end of billing period

        Returns:
            Updated subscription data
        """
        if at_period_end:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
        else:
            subscription = stripe.Subscription.cancel(subscription_id)

        return {
            'status': subscription.status,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'current_period_end': datetime.fromtimestamp(subscription.current_period_end)
        }

    def reactivate_subscription(self, subscription_id: str) -> dict:
        """
        Reactivate a subscription that was set to cancel at period end.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Updated subscription data
        """
        subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False
        )

        return {
            'status': subscription.status,
            'cancel_at_period_end': subscription.cancel_at_period_end
        }

    def change_subscription_tier(
        self,
        subscription_id: str,
        new_tier_id: int
    ) -> dict:
        """
        Change subscription to a different tier.

        Args:
            subscription_id: Stripe subscription ID
            new_tier_id: New MembershipTier ID

        Returns:
            Updated subscription data
        """
        new_tier = MembershipTier.query.get(new_tier_id)
        if not new_tier or not new_tier.stripe_price_id:
            raise ValueError(f"Tier {new_tier_id} not configured with Stripe price")

        # Get current subscription to find the item to update
        subscription = stripe.Subscription.retrieve(subscription_id)
        current_item = subscription['items']['data'][0]

        # Update the subscription with new price
        updated = stripe.Subscription.modify(
            subscription_id,
            items=[{
                'id': current_item.id,
                'price': new_tier.stripe_price_id
            }],
            proration_behavior='create_prorations'  # Prorate the change
        )

        return {
            'status': updated.status,
            'new_tier_id': new_tier_id,
            'current_period_end': datetime.fromtimestamp(updated.current_period_end)
        }

    def get_subscription(self, subscription_id: str) -> dict:
        """Get subscription details from Stripe."""
        subscription = stripe.Subscription.retrieve(subscription_id)

        return {
            'id': subscription.id,
            'status': subscription.status,
            'current_period_start': datetime.fromtimestamp(subscription.current_period_start),
            'current_period_end': datetime.fromtimestamp(subscription.current_period_end),
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'price_id': subscription['items']['data'][0].price.id
        }

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str, webhook_secret: str):
        """
        Construct and verify a Stripe webhook event.

        Args:
            payload: Raw request body
            sig_header: Stripe-Signature header
            webhook_secret: Webhook signing secret

        Returns:
            Verified Stripe event object

        Raises:
            stripe.error.SignatureVerificationError: If signature invalid
        """
        return stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )


class StripeWebhookHandler:
    """Handler for processing Stripe webhook events."""

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def handle_event(self, event: stripe.Event) -> dict:
        """
        Route and handle a Stripe webhook event.

        Args:
            event: Verified Stripe event

        Returns:
            Result dict with handled status
        """
        event_type = event['type']
        data = event['data']['object']

        handlers = {
            'checkout.session.completed': self._handle_checkout_completed,
            'invoice.paid': self._handle_invoice_paid,
            'invoice.payment_failed': self._handle_payment_failed,
            'customer.subscription.updated': self._handle_subscription_updated,
            'customer.subscription.deleted': self._handle_subscription_deleted,
        }

        handler = handlers.get(event_type)
        if handler:
            return handler(data)

        return {'handled': False, 'event_type': event_type}

    def _handle_checkout_completed(self, session) -> dict:
        """Handle successful checkout session."""
        member_id = session['metadata'].get('member_id')
        if not member_id:
            return {'handled': False, 'error': 'No member_id in metadata'}

        member = Member.query.get(int(member_id))
        if not member:
            return {'handled': False, 'error': f'Member {member_id} not found'}

        # Update member with Stripe IDs
        member.stripe_customer_id = session.get('customer')
        member.stripe_subscription_id = session.get('subscription')
        member.payment_status = 'active'
        member.status = 'active'
        member.membership_start_date = datetime.utcnow().date()

        # Get subscription details for period info
        if member.stripe_subscription_id:
            subscription = stripe.Subscription.retrieve(member.stripe_subscription_id)
            member.current_period_start = datetime.fromtimestamp(subscription.current_period_start)
            member.current_period_end = datetime.fromtimestamp(subscription.current_period_end)

        db.session.commit()

        return {
            'handled': True,
            'member_id': member_id,
            'action': 'activated_membership'
        }

    def _handle_invoice_paid(self, invoice) -> dict:
        """Handle successful invoice payment (subscription renewal)."""
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return {'handled': False, 'error': 'No subscription in invoice'}

        member = Member.query.filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if not member:
            return {'handled': False, 'error': f'No member for subscription {subscription_id}'}

        # Update payment status and period
        member.payment_status = 'active'
        member.status = 'active'

        # Get updated subscription details
        subscription = stripe.Subscription.retrieve(subscription_id)
        member.current_period_start = datetime.fromtimestamp(subscription.current_period_start)
        member.current_period_end = datetime.fromtimestamp(subscription.current_period_end)

        db.session.commit()

        return {
            'handled': True,
            'member_id': member.id,
            'action': 'renewed_membership'
        }

    def _handle_payment_failed(self, invoice) -> dict:
        """Handle failed payment."""
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return {'handled': False, 'error': 'No subscription in invoice'}

        member = Member.query.filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if not member:
            return {'handled': False, 'error': f'No member for subscription {subscription_id}'}

        member.payment_status = 'past_due'
        db.session.commit()

        # TODO: Send warning email to member

        return {
            'handled': True,
            'member_id': member.id,
            'action': 'marked_past_due'
        }

    def _handle_subscription_updated(self, subscription) -> dict:
        """Handle subscription update (tier change, etc)."""
        subscription_id = subscription['id']

        member = Member.query.filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if not member:
            return {'handled': False, 'error': f'No member for subscription {subscription_id}'}

        # Update status
        member.payment_status = subscription['status']
        member.cancel_at_period_end = subscription.get('cancel_at_period_end', False)
        member.current_period_start = datetime.fromtimestamp(subscription['current_period_start'])
        member.current_period_end = datetime.fromtimestamp(subscription['current_period_end'])

        # Check if tier changed
        new_price_id = subscription['items']['data'][0]['price']['id']
        new_tier = MembershipTier.query.filter_by(
            tenant_id=self.tenant_id,
            stripe_price_id=new_price_id
        ).first()

        if new_tier and new_tier.id != member.tier_id:
            member.tier_id = new_tier.id

        db.session.commit()

        return {
            'handled': True,
            'member_id': member.id,
            'action': 'subscription_updated',
            'new_tier_id': new_tier.id if new_tier else None
        }

    def _handle_subscription_deleted(self, subscription) -> dict:
        """Handle subscription cancellation."""
        subscription_id = subscription['id']

        member = Member.query.filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if not member:
            return {'handled': False, 'error': f'No member for subscription {subscription_id}'}

        member.payment_status = 'cancelled'
        member.status = 'cancelled'
        member.membership_end_date = datetime.utcnow().date()
        member.stripe_subscription_id = None  # Clear since it's no longer valid

        db.session.commit()

        return {
            'handled': True,
            'member_id': member.id,
            'action': 'cancelled_membership'
        }
