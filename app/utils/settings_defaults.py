"""
Default tenant settings.

Shared between settings API and tenant settings service to avoid circular imports.
"""

# Cashback method options
CASHBACK_METHODS = {
    'native_store_credit': 'Shopify Native Store Credit (recommended)',
    'discount_code': 'Unique Discount Codes',
    'gift_card': 'Shopify Gift Cards',
    'manual': 'Manual Fulfillment (track only)',
}


# Default settings structure
DEFAULT_SETTINGS = {
    'branding': {
        'app_name': 'TradeUp',
        'tagline': 'Trade-in Loyalty Program',
        'logo_url': None,
        'logo_dark_url': None,
        'colors': {
            'primary': '#e85d27',
            'primary_hover': '#d14d1a',
            'secondary': '#1e293b',
            'accent': '#3b82f6'
        },
        'style': 'glass'  # glass, solid, minimal
    },
    'features': {
        'points_enabled': False,
        'referrals_enabled': False,
        'self_signup_enabled': True,
        'advanced_features_enabled': False  # Show simplified nav by default
    },
    'auto_enrollment': {
        'enabled': True,  # Auto-enroll customers on first purchase
        'default_tier_id': None,  # Tier to assign (None = lowest tier)
        'min_order_value': 0,  # Minimum order value to trigger enrollment
        'excluded_tags': [],  # Customer tags to exclude (e.g., ['wholesale', 'staff'])
    },
    'cashback': {
        'method': 'native_store_credit',  # How rewards are delivered
        # Options: native_store_credit, discount_code, gift_card, manual
        'purchase_cashback_enabled': True,  # Award cashback on purchases
        'trade_in_credit_enabled': True,   # Award credit on trade-ins
        'same_transaction_bonus': True,    # Apply tier benefits to same order as membership purchase
        'rounding_mode': 'down',           # down, up, nearest - for cashback cents
        'min_cashback_amount': 0.01,       # Minimum amount to issue (avoid tiny credits)
    },
    'subscriptions': {
        'monthly_enabled': True,  # Offer monthly subscriptions
        'yearly_enabled': True,   # Offer yearly subscriptions (uses yearly_price from tier)
        'trial_days': 0,          # Free trial days (0 = no trial)
        'grace_period_days': 3,   # Days to retry failed payment before downgrade
    },
    'notifications': {
        'enabled': True,  # Master toggle for all notifications

        # Member notifications
        'welcome_email': True,  # Send welcome email on enrollment

        # Trade-in notifications (granular controls)
        'trade_in_updates': True,  # Legacy toggle (enables all trade-in emails)
        'trade_in_created': True,  # Trade-in received confirmation
        'trade_in_approved': True,  # Trade-in approved/completed
        'trade_in_rejected': True,  # Trade-in rejected notification

        # Tier notifications (granular controls)
        'tier_change': True,  # Legacy toggle (enables all tier emails)
        'tier_upgrade': True,  # Tier upgrade notification
        'tier_downgrade': True,  # Tier downgrade notification
        'tier_expiring': True,  # Tier about to expire warning

        # Credit notifications (granular controls)
        'credit_issued': True,  # Legacy toggle (enables all credit emails)
        'credit_added': True,  # Store credit added notification
        'credit_expiring': True,  # Credit expiration warning
        'monthly_credit': True,  # Monthly membership credit notification

        # Referral notifications
        'referral_success': True,  # Referral completed notification

        # Daily digest option
        'daily_digest': False,  # Combine daily notifications into one email

        # Sender configuration
        'from_name': None,  # Defaults to shop name
        'from_email': None,  # SendGrid verified sender
        'reply_to': None,  # Reply-to address (optional)
    },
    'contact': {
        'support_email': None,
        'support_phone': None
    },
    'trade_ins': {
        'enabled': True,
        'auto_approve_under': 50.00,  # Auto-approve trade-ins under this value
        'require_review_over': 500.00,  # Require manual review over this value
        'allow_guest_trade_ins': True,  # Allow non-member trade-ins
        'default_category': 'other',
        'require_photos': False,
    },
    'general': {
        'currency': 'USD',
        'timezone': 'America/Los_Angeles',
    },
    'milestones': {
        'enabled': True,  # Master toggle for milestone celebrations
        'point_milestones': [100, 500, 1000, 2500, 5000, 10000],  # Point thresholds to celebrate
        'trade_in_milestones': [5, 10, 25, 50, 100],  # Trade-in count thresholds
        'email_on_major_milestones': True,  # Send email for 1000+ points, 25+ trade-ins
        'major_point_threshold': 1000,  # Points threshold considered "major"
        'major_trade_in_threshold': 25,  # Trade-in threshold considered "major"
        'celebration_duration_ms': 5000,  # How long to show celebration (milliseconds)
    },
    'anniversary': {
        'enabled': False,  # Master toggle for anniversary rewards
        'reward_type': 'points',  # points, credit, or discount_code
        'reward_amount': 100,  # Amount of points/credit or discount percentage (default/base amount)
        'email_days_before': 0,  # 0 = on anniversary, 1, 3, or 7 days before
        'message': 'Happy Anniversary! Thank you for being a loyal member!',  # Customizable message
        'tiered_rewards_enabled': False,  # Enable different rewards per anniversary year
        'tiered_rewards': {  # Reward amounts by anniversary year (overrides reward_amount)
            # Example: '1': 5, '2': 10, '5': 25, '10': 50
            # Years not configured will use the default reward_amount
        },
    },
    'loyalty': {
        'mode': 'store_credit',  # 'store_credit' (default) or 'points'
        # Store Credit Mode: Customers earn cashback as Shopify store credit (auto-applies at checkout)
        # Points Mode: Customers earn points, redeem for store credit (same checkout experience)

        # Points earning configuration (used in points mode)
        'points_per_dollar': 10,  # Points earned per $1 spent (e.g., 10 = 10 pts per $1)
        'points_to_credit_value': 0.01,  # Dollar value of 1 point (e.g., 0.01 = 100 pts = $1)

        # Display customization
        'points_name': 'points',  # Display name (e.g., 'points', 'coins', 'stars')
        'points_name_singular': 'point',  # Singular form
        'points_currency_symbol': 'pts',  # Short symbol (e.g., 'pts', '★', '🪙')

        # Redemption options
        'min_redemption_points': 100,  # Minimum points to redeem (e.g., 100 = $1 minimum)
        'redemption_increments': 100,  # Redeem in increments of X points (e.g., 100, 500, 1000)

        # Points expiration (also available in 'points' section for backward compat)
        'points_expiration_days': None,  # Days until points expire (None = never expire)
    }
}


def get_settings_with_defaults(settings: dict) -> dict:
    """Merge tenant settings with defaults."""
    result = {}
    for key, default_value in DEFAULT_SETTINGS.items():
        if isinstance(default_value, dict):
            result[key] = {**default_value, **(settings.get(key) or {})}
        else:
            result[key] = settings.get(key, default_value)
    return result
