"""
Cardflow Labs - Shopify Billing API Service

TradeUp membership payments via Shopify Billing API.
Replaces Stripe integration for Shopify App Store compliance.

Cardflow Labs: Built by card shop owners. For card shop owners.
https://cardflowlabs.com

Shopify Billing API docs:
https://shopify.dev/docs/apps/launch/billing
"""
import os
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from flask import current_app
from ..extensions import db
from ..models import Member, MembershipTier, Tenant
from .email_service import email_service


class ShopifyBillingService:
    """
    Service for handling Shopify Billing API operations.

    Shopify Billing uses GraphQL mutations to:
    - Create app subscriptions
    - Handle upgrades/downgrades
    - Cancel subscriptions
    - Track billing status
    """

    GRAPHQL_API_VERSION = '2025-01'

    def __init__(self, shop_domain: str, access_token: str):
        """
        Initialize billing service for a specific shop.

        Args:
            shop_domain: Shopify store domain (e.g., 'store.myshopify.com')
            access_token: Shopify Admin API access token
        """
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.graphql_url = f"https://{shop_domain}/admin/api/{self.GRAPHQL_API_VERSION}/graphql.json"
        self.headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }

    def _execute_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute a GraphQL query/mutation."""
        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        response = requests.post(
            self.graphql_url,
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()

        if 'errors' in result:
            raise Exception(f"GraphQL errors: {result['errors']}")

        return result.get('data', {})

    # ==================== Subscription Management ====================

    def create_subscription(
        self,
        plan_name: str,
        price: float,
        return_url: str,
        trial_days: int = 7,
        interval: str = 'EVERY_30_DAYS'
    ) -> Dict[str, Any]:
        """
        Create an app subscription for the merchant.

        Args:
            plan_name: Name of the plan (e.g., 'Gold Tier')
            price: Monthly price in USD
            return_url: URL to redirect after approval/decline
            trial_days: Number of trial days (default 7)
            interval: EVERY_30_DAYS or ANNUAL

        Returns:
            Dict with confirmation_url and subscription details
        """
        mutation = """
        mutation appSubscriptionCreate($name: String!, $lineItems: [AppSubscriptionLineItemInput!]!, $returnUrl: URL!, $trialDays: Int) {
            appSubscriptionCreate(
                name: $name
                returnUrl: $returnUrl
                trialDays: $trialDays
                lineItems: $lineItems
                test: %s
            ) {
                appSubscription {
                    id
                    name
                    status
                    trialDays
                    currentPeriodEnd
                    lineItems {
                        id
                        plan {
                            pricingDetails {
                                ... on AppRecurringPricing {
                                    price {
                                        amount
                                        currencyCode
                                    }
                                    interval
                                }
                            }
                        }
                    }
                }
                confirmationUrl
                userErrors {
                    field
                    message
                }
            }
        }
        """ % ('true' if os.getenv('SHOPIFY_BILLING_TEST', 'true').lower() == 'true' else 'false')

        variables = {
            'name': plan_name,
            'returnUrl': return_url,
            'trialDays': trial_days,
            'lineItems': [{
                'plan': {
                    'appRecurringPricingDetails': {
                        'price': {
                            'amount': price,
                            'currencyCode': 'USD'
                        },
                        'interval': interval
                    }
                }
            }]
        }

        result = self._execute_graphql(mutation, variables)
        data = result.get('appSubscriptionCreate', {})

        if data.get('userErrors'):
            raise Exception(f"Subscription creation failed: {data['userErrors']}")

        return {
            'subscription': data.get('appSubscription'),
            'confirmation_url': data.get('confirmationUrl'),
            'requires_approval': True
        }

    def get_active_subscriptions(self) -> List[Dict]:
        """
        Get all active subscriptions for the current app installation.

        Returns:
            List of active subscription objects
        """
        query = """
        query {
            currentAppInstallation {
                activeSubscriptions {
                    id
                    name
                    status
                    trialDays
                    currentPeriodEnd
                    createdAt
                    lineItems {
                        id
                        plan {
                            pricingDetails {
                                ... on AppRecurringPricing {
                                    price {
                                        amount
                                        currencyCode
                                    }
                                    interval
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        result = self._execute_graphql(query)
        return result.get('currentAppInstallation', {}).get('activeSubscriptions', [])

    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel an active subscription.

        Args:
            subscription_id: Shopify subscription GID

        Returns:
            Cancelled subscription details
        """
        mutation = """
        mutation appSubscriptionCancel($id: ID!) {
            appSubscriptionCancel(id: $id) {
                appSubscription {
                    id
                    status
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {'id': subscription_id}
        result = self._execute_graphql(mutation, variables)
        data = result.get('appSubscriptionCancel', {})

        if data.get('userErrors'):
            raise Exception(f"Cancellation failed: {data['userErrors']}")

        return data.get('appSubscription')

    def upgrade_subscription(
        self,
        current_subscription_id: str,
        new_plan_name: str,
        new_price: float,
        return_url: str,
        prorate: bool = True
    ) -> Dict[str, Any]:
        """
        Upgrade/downgrade to a different plan.

        Shopify handles proration automatically when replacing subscriptions.

        Args:
            current_subscription_id: Current subscription GID to replace
            new_plan_name: Name of new plan
            new_price: New monthly price
            return_url: Redirect URL after approval
            prorate: Whether to prorate (Shopify default behavior)

        Returns:
            New subscription details with confirmation URL
        """
        # Cancel current subscription
        self.cancel_subscription(current_subscription_id)

        # Create new subscription (Shopify handles proration)
        return self.create_subscription(
            plan_name=new_plan_name,
            price=new_price,
            return_url=return_url,
            trial_days=0  # No trial on upgrade
        )

    # ==================== One-Time Charges ====================

    def create_one_time_charge(
        self,
        name: str,
        price: float,
        return_url: str
    ) -> Dict[str, Any]:
        """
        Create a one-time app purchase (for add-ons, setup fees, etc.).

        Args:
            name: Charge description
            price: Price in USD
            return_url: Redirect URL after approval

        Returns:
            Charge details with confirmation URL
        """
        mutation = """
        mutation appPurchaseOneTimeCreate($name: String!, $price: MoneyInput!, $returnUrl: URL!) {
            appPurchaseOneTimeCreate(
                name: $name
                price: $price
                returnUrl: $returnUrl
                test: %s
            ) {
                appPurchaseOneTime {
                    id
                    name
                    status
                    price {
                        amount
                        currencyCode
                    }
                }
                confirmationUrl
                userErrors {
                    field
                    message
                }
            }
        }
        """ % ('true' if os.getenv('SHOPIFY_BILLING_TEST', 'true').lower() == 'true' else 'false')

        variables = {
            'name': name,
            'price': {
                'amount': price,
                'currencyCode': 'USD'
            },
            'returnUrl': return_url
        }

        result = self._execute_graphql(mutation, variables)
        data = result.get('appPurchaseOneTimeCreate', {})

        if data.get('userErrors'):
            raise Exception(f"One-time charge failed: {data['userErrors']}")

        return {
            'purchase': data.get('appPurchaseOneTime'),
            'confirmation_url': data.get('confirmationUrl')
        }

    # ==================== Usage-Based Billing ====================

    def create_usage_subscription(
        self,
        plan_name: str,
        base_price: float,
        capped_amount: float,
        usage_terms: str,
        return_url: str,
        trial_days: int = 7
    ) -> Dict[str, Any]:
        """
        Create a subscription with usage-based pricing.

        Args:
            plan_name: Plan name
            base_price: Base recurring price
            capped_amount: Maximum usage charge per period
            usage_terms: Description of usage unit (e.g., 'per 100 members')
            return_url: Redirect URL
            trial_days: Trial period

        Returns:
            Subscription with usage component
        """
        mutation = """
        mutation appSubscriptionCreate($name: String!, $lineItems: [AppSubscriptionLineItemInput!]!, $returnUrl: URL!, $trialDays: Int) {
            appSubscriptionCreate(
                name: $name
                returnUrl: $returnUrl
                trialDays: $trialDays
                lineItems: $lineItems
                test: %s
            ) {
                appSubscription {
                    id
                    name
                    status
                }
                confirmationUrl
                userErrors {
                    field
                    message
                }
            }
        }
        """ % ('true' if os.getenv('SHOPIFY_BILLING_TEST', 'true').lower() == 'true' else 'false')

        variables = {
            'name': plan_name,
            'returnUrl': return_url,
            'trialDays': trial_days,
            'lineItems': [
                # Base recurring charge
                {
                    'plan': {
                        'appRecurringPricingDetails': {
                            'price': {'amount': base_price, 'currencyCode': 'USD'},
                            'interval': 'EVERY_30_DAYS'
                        }
                    }
                },
                # Usage-based charge
                {
                    'plan': {
                        'appUsagePricingDetails': {
                            'cappedAmount': {'amount': capped_amount, 'currencyCode': 'USD'},
                            'terms': usage_terms
                        }
                    }
                }
            ]
        }

        result = self._execute_graphql(mutation, variables)
        data = result.get('appSubscriptionCreate', {})

        if data.get('userErrors'):
            raise Exception(f"Usage subscription failed: {data['userErrors']}")

        return {
            'subscription': data.get('appSubscription'),
            'confirmation_url': data.get('confirmationUrl')
        }

    def record_usage(
        self,
        subscription_line_item_id: str,
        amount: float,
        description: str
    ) -> Dict[str, Any]:
        """
        Record usage for usage-based billing.

        Args:
            subscription_line_item_id: The usage line item GID
            amount: Usage amount in USD
            description: Description of the usage

        Returns:
            Usage record details
        """
        mutation = """
        mutation appUsageRecordCreate($subscriptionLineItemId: ID!, $price: MoneyInput!, $description: String!) {
            appUsageRecordCreate(
                subscriptionLineItemId: $subscriptionLineItemId
                price: $price
                description: $description
            ) {
                appUsageRecord {
                    id
                    createdAt
                    price {
                        amount
                        currencyCode
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {
            'subscriptionLineItemId': subscription_line_item_id,
            'price': {'amount': amount, 'currencyCode': 'USD'},
            'description': description
        }

        result = self._execute_graphql(mutation, variables)
        data = result.get('appUsageRecordCreate', {})

        if data.get('userErrors'):
            raise Exception(f"Usage record failed: {data['userErrors']}")

        return data.get('appUsageRecord')


# ==================== Webhook Handler ====================

class ShopifyBillingWebhookHandler:
    """
    Handler for Shopify billing webhook events.

    Required webhooks:
    - APP_SUBSCRIPTIONS_UPDATE
    - APP_PURCHASES_ONE_TIME_UPDATE
    - APP_SUBSCRIPTIONS_APPROACHING_CAPPED_AMOUNT
    """

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def handle_subscription_update(self, payload: Dict) -> Dict[str, Any]:
        """
        Handle APP_SUBSCRIPTIONS_UPDATE webhook.

        Triggered when subscription status changes (activated, cancelled, etc.)
        """
        subscription_id = payload.get('app_subscription', {}).get('admin_graphql_api_id')
        status = payload.get('app_subscription', {}).get('status')
        plan_name = payload.get('app_subscription', {}).get('name', 'TradeUp')

        # Find tenant by subscription ID
        tenant = Tenant.query.filter_by(
            shopify_subscription_id=subscription_id
        ).first()

        if not tenant:
            return {'handled': False, 'error': 'Tenant not found'}

        # Update tenant subscription status
        old_status = tenant.subscription_status
        tenant.subscription_status = status.lower() if status else 'unknown'

        if status == 'ACTIVE':
            tenant.subscription_active = True
        elif status in ['CANCELLED', 'DECLINED', 'EXPIRED']:
            tenant.subscription_active = False

        db.session.commit()

        # Send merchant notification email
        merchant_email = tenant.email
        merchant_name = tenant.shop_name or 'Merchant'

        if merchant_email:
            if status == 'ACTIVE' and old_status != 'active':
                # Subscription activated
                trial_days = payload.get('app_subscription', {}).get('trialDays')
                email_service.send_template_email(
                    template_key='billing_subscription_activated',
                    tenant_id=tenant.id,
                    to_email=merchant_email,
                    to_name=merchant_name,
                    data={
                        'merchant_name': merchant_name,
                        'plan_name': plan_name,
                        'trial_days': trial_days if trial_days and trial_days > 0 else None,
                    },
                )
            elif status in ['CANCELLED', 'DECLINED', 'EXPIRED']:
                # Subscription cancelled
                current_period_end = payload.get('app_subscription', {}).get('currentPeriodEnd', 'immediately')
                email_service.send_template_email(
                    template_key='billing_subscription_cancelled',
                    tenant_id=tenant.id,
                    to_email=merchant_email,
                    to_name=merchant_name,
                    data={
                        'merchant_name': merchant_name,
                        'plan_name': plan_name,
                        'access_until': current_period_end,
                    },
                )

        return {
            'handled': True,
            'tenant_id': tenant.id,
            'new_status': status,
            'notification_sent': bool(merchant_email)
        }

    def handle_one_time_purchase_update(self, payload: Dict) -> Dict[str, Any]:
        """
        Handle APP_PURCHASES_ONE_TIME_UPDATE webhook.

        Triggered when one-time purchase status changes.
        """
        purchase_id = payload.get('app_purchase_one_time', {}).get('admin_graphql_api_id')
        status = payload.get('app_purchase_one_time', {}).get('status')

        # Log the purchase update
        current_app.logger.info(f"[Shopify Billing] One-time purchase {purchase_id}: {status}")

        return {
            'handled': True,
            'purchase_id': purchase_id,
            'status': status
        }

    def handle_approaching_capped_amount(self, payload: Dict) -> Dict[str, Any]:
        """
        Handle APP_SUBSCRIPTIONS_APPROACHING_CAPPED_AMOUNT webhook.

        Triggered when usage reaches 90% of capped amount.
        """
        subscription_id = payload.get('app_subscription', {}).get('admin_graphql_api_id')
        balance_used = payload.get('app_subscription', {}).get('balance_used')

        # Find tenant by subscription ID
        tenant = Tenant.query.filter_by(
            shopify_subscription_id=subscription_id
        ).first()

        notification_sent = False

        if tenant and tenant.email:
            # Get capped amount from subscription line items
            line_items = payload.get('app_subscription', {}).get('lineItems', [])
            capped_amount = None
            for item in line_items:
                pricing = item.get('plan', {}).get('pricingDetails', {})
                if 'cappedAmount' in pricing:
                    capped_amount = pricing['cappedAmount'].get('amount')
                    break

            merchant_name = tenant.shop_name or 'Merchant'

            email_service.send_template_email(
                template_key='billing_usage_warning',
                tenant_id=tenant.id,
                to_email=tenant.email,
                to_name=merchant_name,
                data={
                    'merchant_name': merchant_name,
                    'balance_used': f"${balance_used}" if balance_used else 'N/A',
                    'capped_amount': f"${capped_amount}" if capped_amount else 'your plan limit',
                },
            )
            notification_sent = True

        return {
            'handled': True,
            'subscription_id': subscription_id,
            'balance_used': balance_used,
            'notification_sent': notification_sent
        }


# ==================== Plan Configuration ====================

# Cardflow Labs Pricing Strategy
# Based on competitive research:
# - Undercut Furloop ($69) significantly at $19 entry
# - Free tier for adoption and reviews
# - Clear value progression to justify upgrades
#
# Brand: "Built by card shop owners. For card shop owners."

TRADEUP_PLANS = {
    'free': {
        'name': 'TradeUp Free',
        'display_name': 'Free',
        'price': 0,
        'max_members': 50,
        'max_tiers': 2,
        'features': [
            'Up to 50 members',
            '2 membership tiers',
            'Basic trade-in tracking',
            'Member portal (Cardflow Labs branded)'
        ],
        'limitations': ['Cardflow Labs branding on portal', 'Community support only'],
        'cta': 'Get Started Free'
    },
    'starter': {
        'name': 'TradeUp Starter',
        'display_name': 'Starter',
        'price': 19,
        'annual_price': 190,  # 17% savings
        'max_members': 200,
        'max_tiers': 3,
        'features': [
            'Up to 200 members',
            '3 membership tiers',
            'Remove Cardflow Labs branding',
            'Email notifications',
            'Basic analytics',
            'Email support'
        ],
        'popular': False,
        'cta': 'Start Free Trial'
    },
    'growth': {
        'name': 'TradeUp Growth',
        'display_name': 'Growth',
        'price': 49,
        'annual_price': 490,  # 17% savings
        'max_members': 1000,
        'max_tiers': 5,
        'features': [
            'Up to 1,000 members',
            '5 membership tiers',
            'Shopify POS integration',
            'Advanced analytics dashboard',
            'Custom tier colors/icons',
            'Member import (CSV)',
            'Priority email support'
        ],
        'popular': True,  # Best value - highlighted
        'cta': 'Start Free Trial',
        'badge': 'Most Popular'
    },
    'pro': {
        'name': 'TradeUp Pro',
        'display_name': 'Pro',
        'price': 99,
        'annual_price': 990,  # 17% savings
        'max_members': None,  # Unlimited
        'max_tiers': None,  # Unlimited
        'features': [
            'Unlimited members',
            'Unlimited tiers',
            'Tier cashback tracking',
            'API access',
            'White-label options',
            'Multi-location support',
            'Dedicated support',
            'Custom integrations'
        ],
        'popular': False,
        'cta': 'Start Free Trial',
        'badge': 'Full Power'
    }
}

# Usage-based add-ons (can be added to any paid plan)
TRADEUP_ADDONS = {
    'extra_members': {
        'name': 'Extra Members',
        'price_per_unit': 0.10,  # Per member over limit
        'description': 'Add members beyond your plan limit'
    }
}


def get_plan_config(plan_key: str) -> Optional[Dict]:
    """Get plan configuration by key."""
    return TRADEUP_PLANS.get(plan_key)


def get_all_plans() -> Dict[str, Dict]:
    """Get all available plans."""
    return TRADEUP_PLANS
