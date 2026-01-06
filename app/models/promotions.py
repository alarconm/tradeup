"""
Promotions and Store Credit Events for TradeUp.

World-class promotion system supporting:
- Time-based promotions (holiday weekends, flash sales)
- Category-specific bonuses (sports night, Pokemon day)
- Channel-specific (in-store only, online, all)
- Member tier bonuses (purchase cashback)
- Bulk credit operations
- Full audit trail
"""

from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from ..extensions import db


# ==================== Enums ====================

class PromotionType(str, Enum):
    """Types of promotions."""
    TRADE_IN_BONUS = 'trade_in_bonus'       # Extra % on trade-ins
    PURCHASE_CASHBACK = 'purchase_cashback'  # % back on purchases
    FLAT_BONUS = 'flat_bonus'               # Flat $ bonus on trade-ins
    MULTIPLIER = 'multiplier'               # Multiply base credit (2x, 1.5x)


class PromotionChannel(str, Enum):
    """Where the promotion applies."""
    ALL = 'all'
    IN_STORE = 'in_store'
    ONLINE = 'online'


class CreditEventType(str, Enum):
    """Types of store credit events."""
    TRADE_IN = 'trade_in'              # From trade-up
    PURCHASE_CASHBACK = 'purchase'     # % back on purchase
    PROMOTION_BONUS = 'promotion'      # From a promotion
    MANUAL_ADJUSTMENT = 'adjustment'   # Manual add/deduct
    BULK_CREDIT = 'bulk'              # Bulk operation
    REFERRAL = 'referral'             # Referral bonus
    REDEMPTION = 'redemption'         # Used credit (negative)
    EXPIRATION = 'expiration'         # Expired credit (negative)


# ==================== Tier Cashback Configuration ====================

# Default tier cashback percentages on purchases
TIER_CASHBACK = {
    'SILVER': Decimal('0.01'),    # 1% back
    'GOLD': Decimal('0.02'),      # 2% back
    'PLATINUM': Decimal('0.03'),  # 3% back
}


# ==================== Models ====================

class Promotion(db.Model):
    """
    Promotion configuration for store credit bonuses.

    Supports:
    - Trade-in bonuses (extra % during event)
    - Purchase cashback (extra % back during event)
    - Time windows (start/end dates, specific hours)
    - Category restrictions (only sports, only Pokemon, etc.)
    - Channel restrictions (in-store only, online, all)
    - Stacking rules (can combine with other promos)
    """
    __tablename__ = 'promotions'

    id = db.Column(db.Integer, primary_key=True)

    # Basic info
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    code = db.Column(db.String(50), unique=True, index=True)  # Optional promo code

    # Promotion type and value
    promo_type = db.Column(db.String(30), nullable=False, default='trade_in_bonus')
    bonus_percent = db.Column(db.Numeric(5, 2), default=0)  # e.g., 10 for 10%
    bonus_flat = db.Column(db.Numeric(10, 2), default=0)    # e.g., 5.00 for $5
    multiplier = db.Column(db.Numeric(4, 2), default=1.0)   # e.g., 2.0 for 2x

    # Time window
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)

    # Daily time window (optional - for "6-9pm" style promos)
    daily_start_time = db.Column(db.Time)  # e.g., 18:00
    daily_end_time = db.Column(db.Time)    # e.g., 21:00
    active_days = db.Column(db.String(20))  # e.g., "0,1,2,3,4" for Mon-Fri (0=Mon)

    # Channel restriction
    channel = db.Column(db.String(20), default='all')  # all, in_store, online

    # Category restrictions (JSON array of category IDs, empty = all)
    category_ids = db.Column(db.Text)  # JSON: [1, 2, 3] or null for all

    # Tier restrictions (JSON array, empty = all tiers)
    tier_restriction = db.Column(db.Text)  # JSON: ["GOLD", "PLATINUM"] or null

    # Minimum requirements
    min_items = db.Column(db.Integer, default=0)      # Min items in trade-in
    min_value = db.Column(db.Numeric(10, 2), default=0)  # Min order/trade value

    # Stacking rules
    stackable = db.Column(db.Boolean, default=True)  # Can combine with other promos
    priority = db.Column(db.Integer, default=0)      # Higher = applied first

    # Limits
    max_uses = db.Column(db.Integer)         # Total uses allowed (null = unlimited)
    max_uses_per_member = db.Column(db.Integer)  # Per member (null = unlimited)
    current_uses = db.Column(db.Integer, default=0)

    # Status
    active = db.Column(db.Boolean, default=True)

    # Metadata
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_active_now(self) -> bool:
        """Check if promotion is currently active."""
        if not self.active:
            return False

        now = datetime.utcnow()

        # Check date range
        if now < self.starts_at or now > self.ends_at:
            return False

        # Check daily time window if set
        if self.daily_start_time and self.daily_end_time:
            current_time = now.time()
            if not (self.daily_start_time <= current_time <= self.daily_end_time):
                return False

        # Check active days if set
        if self.active_days:
            active_day_list = [int(d) for d in self.active_days.split(',')]
            if now.weekday() not in active_day_list:
                return False

        # Check max uses
        if self.max_uses and self.current_uses >= self.max_uses:
            return False

        return True

    def applies_to_category(self, category_id: int) -> bool:
        """Check if promotion applies to a specific category."""
        if not self.category_ids:
            return True  # No restriction = all categories

        import json
        try:
            allowed = json.loads(self.category_ids)
            return category_id in allowed
        except (json.JSONDecodeError, TypeError):
            return True

    def applies_to_tier(self, tier: str) -> bool:
        """Check if promotion applies to a member tier."""
        if not self.tier_restriction:
            return True  # No restriction = all tiers

        import json
        try:
            allowed = json.loads(self.tier_restriction)
            return tier in allowed
        except (json.JSONDecodeError, TypeError):
            return True

    def applies_to_channel(self, channel: str) -> bool:
        """Check if promotion applies to the channel."""
        if self.channel == 'all':
            return True
        return self.channel == channel

    def calculate_bonus(self, base_amount: Decimal) -> Decimal:
        """Calculate bonus amount based on promotion type."""
        if self.promo_type == PromotionType.TRADE_IN_BONUS.value:
            return base_amount * (Decimal(str(self.bonus_percent)) / 100)
        elif self.promo_type == PromotionType.PURCHASE_CASHBACK.value:
            return base_amount * (Decimal(str(self.bonus_percent)) / 100)
        elif self.promo_type == PromotionType.FLAT_BONUS.value:
            return Decimal(str(self.bonus_flat))
        elif self.promo_type == PromotionType.MULTIPLIER.value:
            return base_amount * (Decimal(str(self.multiplier)) - 1)
        return Decimal('0')

    def to_dict(self) -> Dict[str, Any]:
        """Serialize promotion to dictionary."""
        import json
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'code': self.code,
            'promo_type': self.promo_type,
            'bonus_percent': float(self.bonus_percent or 0),
            'bonus_flat': float(self.bonus_flat or 0),
            'multiplier': float(self.multiplier or 1),
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'ends_at': self.ends_at.isoformat() if self.ends_at else None,
            'daily_start_time': self.daily_start_time.strftime('%H:%M') if self.daily_start_time else None,
            'daily_end_time': self.daily_end_time.strftime('%H:%M') if self.daily_end_time else None,
            'active_days': self.active_days,
            'channel': self.channel,
            'category_ids': json.loads(self.category_ids) if self.category_ids else None,
            'tier_restriction': json.loads(self.tier_restriction) if self.tier_restriction else None,
            'min_items': self.min_items,
            'min_value': float(self.min_value or 0),
            'stackable': self.stackable,
            'priority': self.priority,
            'max_uses': self.max_uses,
            'max_uses_per_member': self.max_uses_per_member,
            'current_uses': self.current_uses,
            'active': self.active,
            'is_active_now': self.is_active_now(),
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class StoreCreditLedger(db.Model):
    """
    Store credit ledger - tracks all credit transactions.

    Each transaction records:
    - Amount (positive = credit, negative = debit)
    - Running balance
    - Source (trade-in, purchase, promotion, etc.)
    - Full audit trail
    """
    __tablename__ = 'store_credit_ledger'

    id = db.Column(db.Integer, primary_key=True)

    # Member
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)

    # Transaction details
    event_type = db.Column(db.String(30), nullable=False)  # CreditEventType
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # + credit, - debit
    balance_after = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.String(500))

    # Source tracking
    source_type = db.Column(db.String(50))  # tradein, order, promotion, manual
    source_id = db.Column(db.String(100))   # TradeIn ID, Order ID, Promotion ID
    source_reference = db.Column(db.String(100))  # TU-20240101-0001, #ORB1234

    # Promotion tracking
    promotion_id = db.Column(db.Integer, db.ForeignKey('promotions.id'))
    promotion_name = db.Column(db.String(100))

    # Shopify sync
    synced_to_shopify = db.Column(db.Boolean, default=False)
    shopify_credit_id = db.Column(db.String(100))  # Native store credit ID
    sync_error = db.Column(db.String(500))

    # Metadata
    channel = db.Column(db.String(20))  # in_store, online
    created_by = db.Column(db.String(100))  # Staff email or 'system'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Expiration (optional)
    expires_at = db.Column(db.DateTime)

    # Relationships
    member = db.relationship('Member', backref='credit_ledger')
    promotion = db.relationship('Promotion', backref='ledger_entries')

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ledger entry to dictionary."""
        return {
            'id': self.id,
            'member_id': self.member_id,
            'event_type': self.event_type,
            'amount': float(self.amount),
            'balance_after': float(self.balance_after),
            'description': self.description,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'source_reference': self.source_reference,
            'promotion_id': self.promotion_id,
            'promotion_name': self.promotion_name,
            'channel': self.channel,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'synced_to_shopify': self.synced_to_shopify,
        }


class MemberCreditBalance(db.Model):
    """
    Cached credit balance for quick lookups.

    Updated by triggers/application on each ledger entry.
    """
    __tablename__ = 'member_credit_balances'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), unique=True, nullable=False)

    # Balances
    total_balance = db.Column(db.Numeric(10, 2), default=0)
    available_balance = db.Column(db.Numeric(10, 2), default=0)  # Excludes pending
    pending_balance = db.Column(db.Numeric(10, 2), default=0)    # From pending trade-ins

    # Lifetime stats
    total_earned = db.Column(db.Numeric(10, 2), default=0)
    total_spent = db.Column(db.Numeric(10, 2), default=0)
    total_expired = db.Column(db.Numeric(10, 2), default=0)

    # Purchase cashback stats
    cashback_earned = db.Column(db.Numeric(10, 2), default=0)
    trade_in_earned = db.Column(db.Numeric(10, 2), default=0)
    promo_bonus_earned = db.Column(db.Numeric(10, 2), default=0)

    # Last activity
    last_credit_at = db.Column(db.DateTime)
    last_redemption_at = db.Column(db.DateTime)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    member = db.relationship('Member', backref='credit_balance_record', uselist=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize balance to dictionary."""
        return {
            'member_id': self.member_id,
            'total_balance': float(self.total_balance or 0),
            'available_balance': float(self.available_balance or 0),
            'pending_balance': float(self.pending_balance or 0),
            'total_earned': float(self.total_earned or 0),
            'total_spent': float(self.total_spent or 0),
            'cashback_earned': float(self.cashback_earned or 0),
            'trade_in_earned': float(self.trade_in_earned or 0),
            'promo_bonus_earned': float(self.promo_bonus_earned or 0),
            'last_credit_at': self.last_credit_at.isoformat() if self.last_credit_at else None,
            'last_redemption_at': self.last_redemption_at.isoformat() if self.last_redemption_at else None,
        }


class BulkCreditOperation(db.Model):
    """
    Track bulk credit operations for audit purposes.
    """
    __tablename__ = 'bulk_credit_operations'

    id = db.Column(db.Integer, primary_key=True)

    # Operation details
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    amount_per_member = db.Column(db.Numeric(10, 2), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2))
    member_count = db.Column(db.Integer)

    # Filters used
    tier_filter = db.Column(db.String(50))   # e.g., "GOLD,PLATINUM"
    status_filter = db.Column(db.String(50)) # e.g., "active"

    # Status
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed

    # Audit
    created_by = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.String(500))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'amount_per_member': float(self.amount_per_member),
            'total_amount': float(self.total_amount or 0),
            'member_count': self.member_count,
            'tier_filter': self.tier_filter,
            'status_filter': self.status_filter,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


# ==================== Tier Configuration ====================

class CashbackMethod(str, Enum):
    """How cashback rewards are delivered to customers."""
    NATIVE_STORE_CREDIT = 'native_store_credit'  # Shopify native store credit
    DISCOUNT_CODE = 'discount_code'              # Generate unique discount codes
    GIFT_CARD = 'gift_card'                      # Shopify gift cards
    MANUAL = 'manual'                            # Track only, manual fulfillment


class TierConfiguration(db.Model):
    """
    Configurable tier benefits.

    Allows customizing:
    - Monthly and yearly pricing options
    - Trade-in bonus percentage
    - Purchase cashback percentage
    - Other tier-specific benefits
    """
    __tablename__ = 'tier_configurations'

    id = db.Column(db.Integer, primary_key=True)
    tier_name = db.Column(db.String(20), unique=True, nullable=False)  # SILVER, GOLD, PLATINUM

    # Pricing - Monthly is required, yearly is optional (typically ~17% discount)
    monthly_price = db.Column(db.Numeric(6, 2), nullable=False)
    yearly_price = db.Column(db.Numeric(6, 2), nullable=True)  # If null, yearly not offered

    # Benefits
    trade_in_bonus_pct = db.Column(db.Numeric(5, 2), default=0)     # Extra % on trade-ins
    purchase_cashback_pct = db.Column(db.Numeric(5, 2), default=0)  # % back on purchases
    store_discount_pct = db.Column(db.Numeric(5, 2), default=0)     # % off purchases

    # Display
    display_order = db.Column(db.Integer, default=0)
    color = db.Column(db.String(20), default='slate')
    icon = db.Column(db.String(50), default='star')
    badge_text = db.Column(db.String(50))

    # Features (JSON array of feature strings)
    features = db.Column(db.Text)

    # Status
    active = db.Column(db.Boolean, default=True)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def yearly_savings(self) -> Optional[Decimal]:
        """Calculate yearly savings vs monthly billing."""
        if not self.yearly_price:
            return None
        annual_monthly = self.monthly_price * 12
        return annual_monthly - self.yearly_price

    @property
    def yearly_discount_pct(self) -> Optional[float]:
        """Calculate yearly discount percentage."""
        if not self.yearly_price:
            return None
        annual_monthly = float(self.monthly_price) * 12
        if annual_monthly == 0:
            return None
        return round((1 - float(self.yearly_price) / annual_monthly) * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        import json
        return {
            'id': self.id,
            'tier_name': self.tier_name,
            'monthly_price': float(self.monthly_price),
            'yearly_price': float(self.yearly_price) if self.yearly_price else None,
            'yearly_savings': float(self.yearly_savings) if self.yearly_savings else None,
            'yearly_discount_pct': self.yearly_discount_pct,
            'trade_in_bonus_pct': float(self.trade_in_bonus_pct or 0),
            'purchase_cashback_pct': float(self.purchase_cashback_pct or 0),
            'store_discount_pct': float(self.store_discount_pct or 0),
            'display_order': self.display_order,
            'color': self.color,
            'icon': self.icon,
            'badge_text': self.badge_text,
            'features': json.loads(self.features) if self.features else [],
            'active': self.active,
        }


# ==================== Default Data ====================

DEFAULT_TIER_CONFIGS = [
    {
        'tier_name': 'SILVER',
        'monthly_price': 9.99,
        'yearly_price': 99.99,  # ~17% savings ($19.89/yr)
        'trade_in_bonus_pct': 0,
        'purchase_cashback_pct': 1,
        'store_discount_pct': 10,
        'display_order': 1,
        'color': 'slate',
        'badge_text': 'Silver',
        'features': '["1% cashback on purchases", "10% store discount", "Early access to releases", "Member-only events"]',
    },
    {
        'tier_name': 'GOLD',
        'monthly_price': 19.99,
        'yearly_price': 199.99,  # ~17% savings ($39.89/yr)
        'trade_in_bonus_pct': 5,
        'purchase_cashback_pct': 2,
        'store_discount_pct': 15,
        'display_order': 2,
        'color': 'amber',
        'badge_text': 'Gold',
        'features': '["2% cashback on purchases", "15% store discount", "+5% trade-in bonus", "Priority grading", "Free shipping over $50"]',
    },
    {
        'tier_name': 'PLATINUM',
        'monthly_price': 29.99,
        'yearly_price': 299.99,  # ~17% savings ($59.89/yr)
        'trade_in_bonus_pct': 10,
        'purchase_cashback_pct': 3,
        'store_discount_pct': 20,
        'display_order': 3,
        'color': 'blue',
        'badge_text': 'Platinum',
        'features': '["3% cashback on purchases", "20% store discount", "+10% trade-in bonus", "VIP grading queue", "Free shipping all orders", "Exclusive box breaks"]',
    },
]


def seed_tier_configurations():
    """Seed default tier configurations if none exist."""
    try:
        if TierConfiguration.query.count() == 0:
            for config in DEFAULT_TIER_CONFIGS:
                tier = TierConfiguration(**config)
                db.session.add(tier)
            db.session.commit()
            print(f"[Promotions] Seeded {len(DEFAULT_TIER_CONFIGS)} tier configurations")
    except Exception as e:
        # Table may not exist yet - that's ok, will be created by migration
        db.session.rollback()
        print(f"[Promotions] Could not seed tier configurations: {e}")
