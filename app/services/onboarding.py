"""
Cardflow Labs - TradeUp Onboarding Service

Provides pre-built tier templates and simplified setup flow
to maximize trial-to-paid conversion.

Target: Complete setup in under 5 minutes.

Cardflow Labs: Built by card shop owners. For card shop owners.
https://cardflowlabs.com
"""
from typing import Dict, List, Optional
from ..extensions import db
from ..models import MembershipTier, Tenant, seed_nudge_configs


# Pre-built tier templates for different business types
TIER_TEMPLATES = {
    'classic': {
        'name': 'Classic (Bronze/Silver/Gold)',
        'description': 'Traditional 3-tier structure. Great for most card shops.',
        'tiers': [
            {
                'name': 'Bronze',
                'slug': 'bronze',
                'trade_in_rate': 50,
                'monthly_fee': 0,
                'color': '#cd7f32',
                'icon': '🥉',
                'benefits': ['50% of market value on trade-ins', 'Member-only deals'],
                'is_default': True
            },
            {
                'name': 'Silver',
                'slug': 'silver',
                'trade_in_rate': 60,
                'monthly_fee': 0,
                'color': '#c0c0c0',
                'icon': '🥈',
                'benefits': ['60% of market value on trade-ins', 'Early access to new arrivals'],
                'min_spend_requirement': 500
            },
            {
                'name': 'Gold',
                'slug': 'gold',
                'trade_in_rate': 70,
                'monthly_fee': 0,
                'color': '#ffd700',
                'icon': '🥇',
                'benefits': ['70% of market value on trade-ins', 'VIP event access', 'Free shipping'],
                'min_spend_requirement': 1500
            }
        ]
    },
    'premium': {
        'name': 'Premium (Silver/Gold/Platinum)',
        'description': 'Higher-end tiers for established shops with serious collectors.',
        'tiers': [
            {
                'name': 'Silver',
                'slug': 'silver',
                'trade_in_rate': 55,
                'monthly_fee': 0,
                'color': '#c0c0c0',
                'icon': '🥈',
                'benefits': ['55% of market value on trade-ins'],
                'is_default': True
            },
            {
                'name': 'Gold',
                'slug': 'gold',
                'trade_in_rate': 65,
                'monthly_fee': 4.99,
                'color': '#ffd700',
                'icon': '🥇',
                'benefits': ['65% of market value', '10% off store purchases'],
                'min_spend_requirement': 1000
            },
            {
                'name': 'Platinum',
                'slug': 'platinum',
                'trade_in_rate': 75,
                'monthly_fee': 9.99,
                'color': '#e5e4e2',
                'icon': '💎',
                'benefits': ['75% of market value', '15% off store purchases', 'Free grading submission'],
                'min_spend_requirement': 3000
            }
        ]
    },
    'simple': {
        'name': 'Simple (Member/VIP)',
        'description': 'Just two tiers. Perfect for smaller shops.',
        'tiers': [
            {
                'name': 'Member',
                'slug': 'member',
                'trade_in_rate': 55,
                'monthly_fee': 0,
                'color': '#4a90d9',
                'icon': '⭐',
                'benefits': ['55% of market value on trade-ins', 'Member pricing'],
                'is_default': True
            },
            {
                'name': 'VIP',
                'slug': 'vip',
                'trade_in_rate': 70,
                'monthly_fee': 0,
                'color': '#9b59b6',
                'icon': '👑',
                'benefits': ['70% of market value', 'VIP-only events', 'Priority service'],
                'min_spend_requirement': 1000
            }
        ]
    },
    'gamestore': {
        'name': 'Game Store (Collector/Champion/Legend)',
        'description': 'Gaming-themed tiers for TCG and hobby game shops.',
        'tiers': [
            {
                'name': 'Collector',
                'slug': 'collector',
                'trade_in_rate': 50,
                'monthly_fee': 0,
                'color': '#3498db',
                'icon': '📦',
                'benefits': ['50% trade-in value', 'Tournament entry discounts'],
                'is_default': True
            },
            {
                'name': 'Champion',
                'slug': 'champion',
                'trade_in_rate': 62,
                'monthly_fee': 0,
                'color': '#e74c3c',
                'icon': '🏆',
                'benefits': ['62% trade-in value', 'Free tournament entry (1/month)'],
                'min_spend_requirement': 750
            },
            {
                'name': 'Legend',
                'slug': 'legend',
                'trade_in_rate': 75,
                'monthly_fee': 0,
                'color': '#f39c12',
                'icon': '🌟',
                'benefits': ['75% trade-in value', 'Free tournaments', 'Exclusive product access'],
                'min_spend_requirement': 2000
            }
        ]
    },
    'sports': {
        'name': 'Sports Card (Rookie/All-Star/MVP)',
        'description': 'Sports-themed tiers for sports card shops.',
        'tiers': [
            {
                'name': 'Rookie',
                'slug': 'rookie',
                'trade_in_rate': 50,
                'monthly_fee': 0,
                'color': '#27ae60',
                'icon': '🏃',
                'benefits': ['50% trade-in value', 'New release notifications'],
                'is_default': True
            },
            {
                'name': 'All-Star',
                'slug': 'all-star',
                'trade_in_rate': 62,
                'monthly_fee': 0,
                'color': '#3498db',
                'icon': '⚾',
                'benefits': ['62% trade-in value', 'Break priority', 'Exclusive box access'],
                'min_spend_requirement': 1000
            },
            {
                'name': 'MVP',
                'slug': 'mvp',
                'trade_in_rate': 75,
                'monthly_fee': 0,
                'color': '#9b59b6',
                'icon': '🏆',
                'benefits': ['75% trade-in value', 'Free grading (1/month)', 'MVP-only events'],
                'min_spend_requirement': 2500
            }
        ]
    }
}


class OnboardingService:
    """
    Handles the simplified onboarding flow.

    Goal: Shop owner goes from install to live in under 5 minutes.

    Flow:
    1. OAuth (automatic)
    2. Store credit check (automatic)
    3. Choose template (30 seconds)
    4. Preview (30 seconds)
    5. Go live (click)
    """

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.tenant = Tenant.query.get(tenant_id)

    def check_store_credit_enabled(self) -> Dict:
        """
        Check if Shopify native store credit is enabled for this store.

        Returns status and instructions if not enabled.
        """
        from .shopify_client import ShopifyClient

        try:
            client = ShopifyClient(self.tenant_id)

            # Try to query shop capabilities to check store credit
            # We'll use a simple query to check if store credit APIs are accessible
            query = """
            query checkStoreCreditCapability {
                shop {
                    id
                    name
                    currencyCode
                    features {
                        storefront
                    }
                }
            }
            """
            result = client._execute_query(query)
            shop_data = result.get('shop', {})

            # Try to check if we can access store credit accounts
            # If this fails, store credit is not enabled
            try:
                # Query for any customer's store credit to see if API is accessible
                test_query = """
                query testStoreCreditAccess {
                    customers(first: 1) {
                        edges {
                            node {
                                id
                                storeCreditAccounts(first: 1) {
                                    edges {
                                        node {
                                            id
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                """
                client._execute_query(test_query)
                store_credit_accessible = True
            except Exception as e:
                error_msg = str(e).lower()
                if 'access' in error_msg or 'scope' in error_msg or 'permission' in error_msg:
                    store_credit_accessible = False
                else:
                    # Other error - assume it's accessible but had different issue
                    store_credit_accessible = True

            if store_credit_accessible:
                return {
                    'enabled': True,
                    'status': 'ready',
                    'message': 'Store credit is enabled and ready to use!',
                    'shop_name': shop_data.get('name'),
                    'currency': shop_data.get('currencyCode', 'USD')
                }
            else:
                return {
                    'enabled': False,
                    'status': 'not_enabled',
                    'message': 'Store credit needs to be enabled in your Shopify settings.',
                    'instructions': [
                        'Go to Shopify Admin → Settings → Payments',
                        'Scroll down to "Store credit"',
                        'Click "Activate" to enable store credit',
                        'Return here and refresh to verify'
                    ],
                    'settings_url': f"https://{self.tenant.shopify_domain}/admin/settings/payments"
                }

        except Exception as e:
            return {
                'enabled': False,
                'status': 'error',
                'message': f'Could not check store credit status: {str(e)}',
                'instructions': [
                    'Ensure the app has proper permissions',
                    'Try reinstalling the app if the issue persists'
                ]
            }

    def get_available_templates(self) -> List[Dict]:
        """
        Get list of available tier templates.

        Returns templates appropriate for the tenant's plan.
        """
        plan = self.tenant.subscription_plan or 'free'
        max_tiers = self._get_max_tiers(plan)

        available = []
        for key, template in TIER_TEMPLATES.items():
            tier_count = len(template['tiers'])
            if tier_count <= max_tiers:
                available.append({
                    'key': key,
                    'name': template['name'],
                    'description': template['description'],
                    'tier_count': tier_count,
                    'tiers': template['tiers']
                })

        return available

    def apply_template(self, template_key: str) -> Dict:
        """
        Apply a tier template to the tenant.

        Creates all tiers from the template.

        Args:
            template_key: Key of template to apply (e.g., 'classic')

        Returns:
            Created tiers
        """
        if template_key not in TIER_TEMPLATES:
            raise ValueError(f"Unknown template: {template_key}")

        template = TIER_TEMPLATES[template_key]

        # Delete existing tiers (if any)
        MembershipTier.query.filter_by(tenant_id=self.tenant_id).delete()

        # Create tiers from template
        # Map template fields to MembershipTier model fields
        created_tiers = []
        for idx, tier_data in enumerate(template['tiers']):
            # Convert trade_in_rate (e.g., 50 for 50%) to bonus_rate (0.50)
            trade_in_rate = tier_data.get('trade_in_rate', 50)
            bonus_rate = trade_in_rate / 100.0

            # Store additional template data in benefits JSON
            benefits = {
                'description_list': tier_data.get('benefits', []),
                'trade_in_rate': trade_in_rate,
                'color': tier_data.get('color', '#e85d27'),
                'icon': tier_data.get('icon', '⭐'),
                'is_default': tier_data.get('is_default', False),
            }

            # Add min_spend_requirement if specified
            if tier_data.get('min_spend_requirement'):
                benefits['min_spend_requirement'] = tier_data['min_spend_requirement']

            tier = MembershipTier(
                tenant_id=self.tenant_id,
                name=tier_data['name'],
                monthly_price=tier_data.get('monthly_fee', 0),
                bonus_rate=bonus_rate,
                benefits=benefits,
                display_order=idx,
                is_active=True
            )
            db.session.add(tier)
            created_tiers.append(tier)

        # Mark onboarding as complete
        from sqlalchemy.orm.attributes import flag_modified

        if self.tenant.settings is None:
            self.tenant.settings = {}
        self.tenant.settings['onboarding_complete'] = True
        self.tenant.settings['template_used'] = template_key

        # Explicitly mark the JSON column as modified
        flag_modified(self.tenant, 'settings')
        db.session.commit()

        # Seed default nudge configurations for the tenant
        seed_nudge_configs(self.tenant_id)

        return {
            'success': True,
            'template': template_key,
            'tiers_created': len(created_tiers),
            'tiers': [t.to_dict() for t in created_tiers]
        }

    def get_onboarding_status(self) -> Dict:
        """
        Get the current onboarding status for the tenant.
        """
        settings = self.tenant.settings or {}
        tier_count = MembershipTier.query.filter_by(tenant_id=self.tenant_id).count()

        return {
            'onboarding_complete': settings.get('onboarding_complete', False),
            'store_credit_enabled': settings.get('store_credit_enabled', False),
            'template_used': settings.get('template_used'),
            'has_tiers': tier_count > 0,
            'tier_count': tier_count,
            'subscription_active': self.tenant.subscription_active,
            'subscription_plan': self.tenant.subscription_plan
        }

    def _get_max_tiers(self, plan: str) -> int:
        """Get max tiers allowed for a plan."""
        from .shopify_billing import TRADEUP_PLANS

        plan_config = TRADEUP_PLANS.get(plan, TRADEUP_PLANS['free'])
        max_tiers = plan_config.get('max_tiers')

        return max_tiers if max_tiers else 999  # None = unlimited


def get_template_preview(template_key: str) -> Optional[Dict]:
    """
    Get a preview of a tier template.

    Used to show merchants what they'll get before applying.
    """
    if template_key not in TIER_TEMPLATES:
        return None

    template = TIER_TEMPLATES[template_key]
    return {
        'key': template_key,
        'name': template['name'],
        'description': template['description'],
        'tiers': template['tiers']
    }


def calculate_member_rate(tier_trade_in_rate: float, market_value: float) -> float:
    """
    Calculate what a member receives for a trade-in.

    Args:
        tier_trade_in_rate: The tier's trade-in rate (e.g., 65 for 65%)
        market_value: TCGPlayer market value of items

    Returns:
        Store credit amount
    """
    return round(market_value * (tier_trade_in_rate / 100), 2)
