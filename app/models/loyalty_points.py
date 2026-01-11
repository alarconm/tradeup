"""
Points-based Loyalty System models for TradeUp.

This module implements a comprehensive points loyalty system where:
- Members EARN points through purchases, trade-ins, referrals, etc.
- Members REDEEM points for store credit, discounts, or products
- Shopify store credit remains the REDEMPTION currency (points convert to credit)

The system supports:
- Flexible earning rules (per dollar, multipliers, bonuses)
- Rewards catalog (different redemption options)
- Full transaction history for auditing
- Points expiration
- Tier-based earning multipliers
"""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from ..extensions import db


# ==================== Enums ====================

class PointsTransactionType(str, Enum):
    """Types of points transactions."""
    EARN = 'earn'           # Points earned (positive)
    REDEEM = 'redeem'       # Points redeemed for reward (negative)
    EXPIRE = 'expire'       # Points expired (negative)
    ADJUST = 'adjust'       # Manual adjustment (+/-)
    BONUS = 'bonus'         # Bonus points (positive)
    REVERSE = 'reverse'     # Reversal of prior transaction (+/-)


class PointsEarnSource(str, Enum):
    """Sources of earned points."""
    PURCHASE = 'purchase'           # Shopify order
    TRADE_IN = 'trade_in'          # Trade-in completion
    REFERRAL = 'referral'          # Referral bonus
    SIGNUP = 'signup'              # New member signup
    BIRTHDAY = 'birthday'          # Birthday bonus
    REVIEW = 'review'              # Product review
    SOCIAL_SHARE = 'social_share'  # Social media share
    MANUAL = 'manual'              # Admin adjustment
    PROMOTION = 'promotion'        # Promotional bonus
    TIER_BONUS = 'tier_bonus'      # Tier upgrade bonus
    CHALLENGE = 'challenge'        # Challenge/achievement completion


class EarningRuleType(str, Enum):
    """Types of earning rules."""
    BASE_RATE = 'base_rate'         # Base points per dollar
    MULTIPLIER = 'multiplier'       # Multiply base earnings (2x, 3x)
    BONUS_POINTS = 'bonus_points'   # Flat bonus points
    PERCENTAGE = 'percentage'       # Percentage of order value as points


class RewardType(str, Enum):
    """Types of redeemable rewards."""
    STORE_CREDIT = 'store_credit'   # Convert to Shopify store credit
    DISCOUNT_CODE = 'discount_code' # Generate discount code
    FREE_PRODUCT = 'free_product'   # Specific product
    FREE_SHIPPING = 'free_shipping' # Free shipping voucher
    EXCLUSIVE_ACCESS = 'exclusive_access'  # Early access, exclusive events


class RewardRedemptionStatus(str, Enum):
    """Status of a reward redemption."""
    PENDING = 'pending'       # Being processed
    COMPLETED = 'completed'   # Successfully redeemed
    FAILED = 'failed'         # Failed to process
    CANCELLED = 'cancelled'   # Cancelled by user/admin
    EXPIRED = 'expired'       # Reward voucher expired


# ==================== Models ====================

class PointsBalance(db.Model):
    """
    Current points balance for a member.

    This is a cached/denormalized balance for fast lookups.
    The authoritative balance comes from summing PointsTransaction records.

    Design notes:
    - One row per member (unique constraint on member_id)
    - Updated on every points transaction
    - Includes lifetime stats for quick dashboard display
    """
    __tablename__ = 'points_balances'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, unique=True)

    # Current balances
    available_points = db.Column(db.Integer, default=0, nullable=False)
    pending_points = db.Column(db.Integer, default=0)  # From pending orders/trade-ins
    expiring_points = db.Column(db.Integer, default=0)  # Points expiring within 30 days
    expiring_date = db.Column(db.DateTime)  # When next points expire

    # Lifetime statistics
    lifetime_earned = db.Column(db.Integer, default=0)
    lifetime_redeemed = db.Column(db.Integer, default=0)
    lifetime_expired = db.Column(db.Integer, default=0)

    # Breakdown by source
    earned_from_purchases = db.Column(db.Integer, default=0)
    earned_from_trade_ins = db.Column(db.Integer, default=0)
    earned_from_referrals = db.Column(db.Integer, default=0)
    earned_from_promotions = db.Column(db.Integer, default=0)
    earned_from_other = db.Column(db.Integer, default=0)

    # Redemption stats
    total_redemptions = db.Column(db.Integer, default=0)  # Number of redemptions
    total_credit_redeemed = db.Column(db.Numeric(12, 2), default=Decimal('0'))  # Store credit value

    # Activity tracking
    last_earn_at = db.Column(db.DateTime)
    last_redeem_at = db.Column(db.DateTime)
    last_transaction_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='points_balances')
    member = db.relationship('Member', backref='points_balance_record', uselist=False)

    # Indexes for common queries
    __table_args__ = (
        db.Index('ix_points_balances_tenant_member', 'tenant_id', 'member_id'),
        db.Index('ix_points_balances_available', 'available_points'),
    )

    def __repr__(self):
        return f'<PointsBalance member={self.member_id} pts={self.available_points}>'

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            'member_id': self.member_id,
            'available_points': self.available_points,
            'pending_points': self.pending_points or 0,
            'expiring_points': self.expiring_points or 0,
            'expiring_date': self.expiring_date.isoformat() if self.expiring_date else None,
            # Lifetime stats
            'lifetime_earned': self.lifetime_earned,
            'lifetime_redeemed': self.lifetime_redeemed,
            'lifetime_expired': self.lifetime_expired or 0,
            # Breakdown
            'earned_from_purchases': self.earned_from_purchases or 0,
            'earned_from_trade_ins': self.earned_from_trade_ins or 0,
            'earned_from_referrals': self.earned_from_referrals or 0,
            'earned_from_promotions': self.earned_from_promotions or 0,
            # Redemption stats
            'total_redemptions': self.total_redemptions or 0,
            'total_credit_redeemed': float(self.total_credit_redeemed or 0),
            # Activity
            'last_earn_at': self.last_earn_at.isoformat() if self.last_earn_at else None,
            'last_redeem_at': self.last_redeem_at.isoformat() if self.last_redeem_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def recalculate_from_transactions(self):
        """
        Recalculate balance from transaction history.
        Use this for data integrity checks or fixes.
        """
        from sqlalchemy import func

        # Get sum of all points for this member
        result = db.session.query(
            func.sum(PointsLedger.points)
        ).filter(
            PointsLedger.member_id == self.member_id,
            PointsLedger.reversed_at.is_(None)
        ).scalar()

        self.available_points = result or 0
        self.updated_at = datetime.utcnow()


class PointsLedger(db.Model):
    """
    Points transaction ledger - the authoritative record of all points changes.

    Every earn, redeem, expire, and adjustment is recorded here.
    This is the audit trail for points activity.

    Design notes:
    - Immutable once created (reversals create new entries)
    - Points can be positive (earn) or negative (redeem/expire)
    - Links back to source (order, trade-in, etc.)
    - Supports expiration tracking
    """
    __tablename__ = 'points_ledger'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)

    # Transaction details
    points = db.Column(db.Integer, nullable=False)  # + for earn, - for redeem/expire
    balance_after = db.Column(db.Integer)  # Running balance after this transaction
    transaction_type = db.Column(db.String(30), nullable=False)  # PointsTransactionType

    # Source tracking
    source = db.Column(db.String(50))  # PointsEarnSource
    source_id = db.Column(db.String(100))  # Shopify order ID, trade-in ID, etc.
    source_type = db.Column(db.String(50))  # shopify_order, trade_in_batch, etc.

    # Earning rule reference (if points earned via rule)
    earning_rule_id = db.Column(db.Integer, db.ForeignKey('earning_rules.id'))

    # Redemption reference (if points redeemed)
    reward_redemption_id = db.Column(db.Integer, db.ForeignKey('reward_redemptions.id'))

    # Description for UI display
    description = db.Column(db.String(500))
    short_description = db.Column(db.String(100))  # For compact displays

    # Expiration tracking
    expires_at = db.Column(db.DateTime)  # When these points expire (null = never)
    expired_points_processed = db.Column(db.Boolean, default=False)

    # Reversal tracking
    related_transaction_id = db.Column(db.Integer, db.ForeignKey('points_ledger.id'))
    reversed_at = db.Column(db.DateTime)
    reversed_reason = db.Column(db.String(200))

    # Metadata
    created_by = db.Column(db.String(100))  # user email or 'system'
    ip_address = db.Column(db.String(45))  # For fraud detection
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='points_ledger_entries')
    member = db.relationship('Member', backref='points_ledger_entries')
    earning_rule = db.relationship('EarningRule', backref='ledger_entries')
    reward_redemption = db.relationship('RewardRedemption', backref='points_deduction')
    related_transaction = db.relationship('PointsLedger', remote_side=[id])

    # Indexes for common queries
    __table_args__ = (
        db.Index('ix_points_ledger_member_created', 'member_id', 'created_at'),
        db.Index('ix_points_ledger_tenant_created', 'tenant_id', 'created_at'),
        db.Index('ix_points_ledger_source', 'source_type', 'source_id'),
        db.Index('ix_points_ledger_expires', 'expires_at', 'expired_points_processed'),
        db.Index('ix_points_ledger_type', 'transaction_type'),
    )

    def __repr__(self):
        return f'<PointsLedger {self.id}: {self.points:+d} pts for member {self.member_id}>'

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            'id': self.id,
            'member_id': self.member_id,
            'points': self.points,
            'balance_after': self.balance_after,
            'transaction_type': self.transaction_type,
            'source': self.source,
            'source_id': self.source_id,
            'source_type': self.source_type,
            'description': self.description,
            'short_description': self.short_description,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_reversed': self.reversed_at is not None,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def to_dict_detailed(self) -> Dict[str, Any]:
        """Detailed serialization including references."""
        data = self.to_dict()
        data.update({
            'earning_rule_id': self.earning_rule_id,
            'reward_redemption_id': self.reward_redemption_id,
            'related_transaction_id': self.related_transaction_id,
            'reversed_at': self.reversed_at.isoformat() if self.reversed_at else None,
            'reversed_reason': self.reversed_reason,
        })
        return data


class EarningRule(db.Model):
    """
    Configurable rules for earning points.

    Supports:
    - Base rate (X points per $1 spent)
    - Multipliers (2x points on category, 3x during promotion)
    - Bonus points (flat bonus for specific actions)
    - Tier-based modifiers

    Design notes:
    - Rules can be combined (stacking)
    - Priority determines application order
    - Supports time-based activation (promotions)
    - Can target specific products/collections/vendors
    """
    __tablename__ = 'earning_rules'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    # Rule identification
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True)  # Internal reference code
    description = db.Column(db.String(500))

    # Rule type and value
    rule_type = db.Column(db.String(30), nullable=False, default='base_rate')  # EarningRuleType
    points_per_dollar = db.Column(db.Integer)  # For base_rate: points earned per $1
    multiplier = db.Column(db.Numeric(4, 2))  # For multiplier: 1.5, 2.0, etc.
    bonus_points = db.Column(db.Integer)  # For bonus_points: flat points awarded
    percentage = db.Column(db.Numeric(5, 2))  # For percentage: % of order as points

    # Trigger conditions
    trigger_source = db.Column(db.String(50))  # purchase, trade_in, referral, etc.
    min_order_value = db.Column(db.Numeric(10, 2))  # Minimum order to qualify
    max_order_value = db.Column(db.Numeric(10, 2))  # Maximum order for points cap

    # Time window (for promotional rules)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)

    # Product filters (JSON arrays)
    collection_ids = db.Column(db.Text)  # JSON: ["gid://shopify/Collection/123", ...]
    vendor_filter = db.Column(db.Text)   # JSON: ["Pokemon", "Magic", ...]
    product_type_filter = db.Column(db.Text)  # JSON: ["Sealed Product", "Singles"]
    product_tags_filter = db.Column(db.Text)  # JSON: ["preorder", "exclusive"]
    excluded_product_ids = db.Column(db.Text)  # JSON: Products that don't earn points

    # Member restrictions
    tier_restriction = db.Column(db.Text)  # JSON: ["GOLD", "PLATINUM"] or null for all
    new_member_only = db.Column(db.Boolean, default=False)  # Only first purchase
    member_join_days = db.Column(db.Integer)  # Apply to members joined within X days

    # Stacking rules
    stackable = db.Column(db.Boolean, default=True)  # Can combine with other rules
    priority = db.Column(db.Integer, default=0)  # Higher = applied first
    exclusive_group = db.Column(db.String(50))  # Rules in same group don't stack

    # Limits
    max_points_per_order = db.Column(db.Integer)  # Cap points per transaction
    max_uses_total = db.Column(db.Integer)  # Total uses across all members
    max_uses_per_member = db.Column(db.Integer)  # Uses per member
    current_uses = db.Column(db.Integer, default=0)

    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_base_rule = db.Column(db.Boolean, default=False)  # Default earning rule

    # Metadata
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='earning_rules')

    # Indexes
    __table_args__ = (
        db.Index('ix_earning_rules_tenant_active', 'tenant_id', 'is_active'),
        db.Index('ix_earning_rules_time_window', 'starts_at', 'ends_at'),
        db.Index('ix_earning_rules_trigger', 'trigger_source'),
    )

    def __repr__(self):
        return f'<EarningRule {self.name}>'

    def is_active_now(self) -> bool:
        """Check if rule is currently active."""
        if not self.is_active:
            return False

        now = datetime.utcnow()

        # Check time window if set
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False

        # Check usage limits
        if self.max_uses_total and self.current_uses >= self.max_uses_total:
            return False

        return True

    def applies_to_tier(self, tier_name: str) -> bool:
        """Check if rule applies to a member tier."""
        if not self.tier_restriction:
            return True  # No restriction = all tiers

        import json
        try:
            allowed = json.loads(self.tier_restriction)
            return tier_name.upper() in [t.upper() for t in allowed]
        except (json.JSONDecodeError, TypeError):
            return True

    def applies_to_product(self, product: Dict[str, Any]) -> bool:
        """
        Check if rule applies to a product.

        Product dict should have: collection_ids, vendor, product_type, tags, id
        """
        import json

        # Check excluded products
        if self.excluded_product_ids:
            try:
                excluded = json.loads(self.excluded_product_ids)
                if product.get('id') in excluded:
                    return False
            except (json.JSONDecodeError, TypeError):
                pass

        # Check collection filter
        if self.collection_ids:
            try:
                allowed = json.loads(self.collection_ids)
                product_collections = product.get('collection_ids', [])
                if not any(c in allowed for c in product_collections):
                    return False
            except (json.JSONDecodeError, TypeError):
                pass

        # Check vendor filter
        if self.vendor_filter:
            try:
                allowed = json.loads(self.vendor_filter)
                vendor = product.get('vendor', '')
                if vendor.lower() not in [v.lower() for v in allowed]:
                    return False
            except (json.JSONDecodeError, TypeError):
                pass

        # Check product type filter
        if self.product_type_filter:
            try:
                allowed = json.loads(self.product_type_filter)
                ptype = product.get('product_type', '')
                if ptype.lower() not in [t.lower() for t in allowed]:
                    return False
            except (json.JSONDecodeError, TypeError):
                pass

        # Check tags filter
        if self.product_tags_filter:
            try:
                required = json.loads(self.product_tags_filter)
                tags = product.get('tags', [])
                tags_lower = [t.lower() for t in tags]
                if not any(tag.lower() in tags_lower for tag in required):
                    return False
            except (json.JSONDecodeError, TypeError):
                pass

        return True

    def calculate_points(self, amount: Decimal, base_points: int = 0) -> int:
        """
        Calculate points for a given order amount.

        Args:
            amount: Order/transaction amount in dollars
            base_points: Points from base rule (for multiplier calculations)

        Returns:
            Points to award
        """
        # Check minimum order value
        if self.min_order_value and amount < self.min_order_value:
            return 0

        # Cap order value if specified
        effective_amount = amount
        if self.max_order_value and amount > self.max_order_value:
            effective_amount = self.max_order_value

        points = 0

        if self.rule_type == EarningRuleType.BASE_RATE.value:
            points = int(effective_amount * (self.points_per_dollar or 0))

        elif self.rule_type == EarningRuleType.MULTIPLIER.value:
            # Multiply the base points
            multiplier = float(self.multiplier or 1)
            points = int(base_points * (multiplier - 1))  # Additional points from multiplier

        elif self.rule_type == EarningRuleType.BONUS_POINTS.value:
            points = self.bonus_points or 0

        elif self.rule_type == EarningRuleType.PERCENTAGE.value:
            pct = float(self.percentage or 0) / 100
            points = int(float(effective_amount) * pct)

        # Apply max points cap
        if self.max_points_per_order and points > self.max_points_per_order:
            points = self.max_points_per_order

        return points

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        import json

        def safe_json_loads(value):
            if not value:
                return None
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None

        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'rule_type': self.rule_type,
            'points_per_dollar': self.points_per_dollar,
            'multiplier': float(self.multiplier) if self.multiplier else None,
            'bonus_points': self.bonus_points,
            'percentage': float(self.percentage) if self.percentage else None,
            'trigger_source': self.trigger_source,
            'min_order_value': float(self.min_order_value) if self.min_order_value else None,
            'max_order_value': float(self.max_order_value) if self.max_order_value else None,
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'ends_at': self.ends_at.isoformat() if self.ends_at else None,
            # Filters
            'collection_ids': safe_json_loads(self.collection_ids),
            'vendor_filter': safe_json_loads(self.vendor_filter),
            'product_type_filter': safe_json_loads(self.product_type_filter),
            'product_tags_filter': safe_json_loads(self.product_tags_filter),
            'tier_restriction': safe_json_loads(self.tier_restriction),
            # Rules
            'stackable': self.stackable,
            'priority': self.priority,
            'max_points_per_order': self.max_points_per_order,
            'max_uses_total': self.max_uses_total,
            'max_uses_per_member': self.max_uses_per_member,
            'current_uses': self.current_uses or 0,
            'is_active': self.is_active,
            'is_base_rule': self.is_base_rule,
            'is_active_now': self.is_active_now(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Reward(db.Model):
    """
    Redeemable rewards catalog.

    Members can redeem points for:
    - Store credit (converted to Shopify native store credit)
    - Discount codes
    - Free products
    - Free shipping
    - Exclusive access

    Design notes:
    - Each reward has a point cost
    - Can set availability windows (limited time rewards)
    - Can restrict to specific tiers
    - Can limit total redemptions
    """
    __tablename__ = 'rewards'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    # Reward identification
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True)  # Internal reference
    description = db.Column(db.String(1000))
    short_description = db.Column(db.String(200))  # For compact displays
    terms = db.Column(db.Text)  # Terms and conditions

    # Reward type and value
    reward_type = db.Column(db.String(30), nullable=False)  # RewardType
    points_cost = db.Column(db.Integer, nullable=False)  # Points required to redeem

    # Value details (depends on type)
    credit_value = db.Column(db.Numeric(10, 2))  # For store_credit: dollar value
    discount_percent = db.Column(db.Numeric(5, 2))  # For discount: percentage
    discount_amount = db.Column(db.Numeric(10, 2))  # For discount: fixed amount
    product_id = db.Column(db.String(100))  # For free_product: Shopify product ID
    product_variant_id = db.Column(db.String(100))  # For free_product: specific variant

    # Display
    image_url = db.Column(db.String(500))
    badge_text = db.Column(db.String(50))  # "Popular", "Limited", etc.
    display_order = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50))  # For grouping in UI

    # Availability
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    available_quantity = db.Column(db.Integer)  # Total available (null = unlimited)
    redeemed_quantity = db.Column(db.Integer, default=0)

    # Member restrictions
    tier_restriction = db.Column(db.Text)  # JSON: ["GOLD", "PLATINUM"] or null
    max_redemptions_per_member = db.Column(db.Integer)  # Per member limit
    min_member_days = db.Column(db.Integer)  # Member for at least X days

    # Validity after redemption
    voucher_valid_days = db.Column(db.Integer, default=30)  # Days voucher is valid

    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)

    # Metadata
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='rewards')
    redemptions = db.relationship('RewardRedemption', backref='reward', lazy='dynamic')

    # Indexes
    __table_args__ = (
        db.Index('ix_rewards_tenant_active', 'tenant_id', 'is_active'),
        db.Index('ix_rewards_type', 'reward_type'),
        db.Index('ix_rewards_display', 'display_order', 'is_featured'),
    )

    def __repr__(self):
        return f'<Reward {self.name}: {self.points_cost} pts>'

    def is_available(self) -> bool:
        """Check if reward is currently available."""
        if not self.is_active:
            return False

        now = datetime.utcnow()

        # Check time window
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False

        # Check quantity
        if self.available_quantity is not None:
            if self.redeemed_quantity >= self.available_quantity:
                return False

        return True

    def remaining_quantity(self) -> Optional[int]:
        """Get remaining quantity available."""
        if self.available_quantity is None:
            return None
        return max(0, self.available_quantity - (self.redeemed_quantity or 0))

    def applies_to_tier(self, tier_name: str) -> bool:
        """Check if reward is available for a tier."""
        if not self.tier_restriction:
            return True

        import json
        try:
            allowed = json.loads(self.tier_restriction)
            return tier_name.upper() in [t.upper() for t in allowed]
        except (json.JSONDecodeError, TypeError):
            return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        import json

        def safe_json_loads(value):
            if not value:
                return None
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None

        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'short_description': self.short_description,
            'terms': self.terms,
            'reward_type': self.reward_type,
            'points_cost': self.points_cost,
            # Values
            'credit_value': float(self.credit_value) if self.credit_value else None,
            'discount_percent': float(self.discount_percent) if self.discount_percent else None,
            'discount_amount': float(self.discount_amount) if self.discount_amount else None,
            'product_id': self.product_id,
            # Display
            'image_url': self.image_url,
            'badge_text': self.badge_text,
            'display_order': self.display_order,
            'category': self.category,
            # Availability
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'ends_at': self.ends_at.isoformat() if self.ends_at else None,
            'available_quantity': self.available_quantity,
            'redeemed_quantity': self.redeemed_quantity or 0,
            'remaining_quantity': self.remaining_quantity(),
            # Restrictions
            'tier_restriction': safe_json_loads(self.tier_restriction),
            'max_redemptions_per_member': self.max_redemptions_per_member,
            'voucher_valid_days': self.voucher_valid_days,
            # Status
            'is_active': self.is_active,
            'is_featured': self.is_featured,
            'is_available': self.is_available(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class RewardRedemption(db.Model):
    """
    Track reward redemptions.

    Each redemption:
    - Deducts points from member
    - Creates the reward (store credit, discount code, etc.)
    - Tracks fulfillment status
    - Stores voucher/code details

    Design notes:
    - Links to PointsLedger for the points deduction
    - Tracks Shopify sync status for store credit
    - Stores generated codes/vouchers
    """
    __tablename__ = 'reward_redemptions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    reward_id = db.Column(db.Integer, db.ForeignKey('rewards.id'), nullable=False)

    # Redemption reference
    redemption_code = db.Column(db.String(50), unique=True, nullable=False)  # RD-YYYYMMDD-XXXXX

    # Points spent
    points_spent = db.Column(db.Integer, nullable=False)

    # Status
    status = db.Column(db.String(30), default='pending')  # RewardRedemptionStatus

    # Reward details (snapshot at redemption time)
    reward_type = db.Column(db.String(30), nullable=False)
    reward_name = db.Column(db.String(100), nullable=False)
    reward_value = db.Column(db.Numeric(10, 2))  # Dollar value if applicable

    # Generated voucher/code
    voucher_code = db.Column(db.String(50))  # Generated discount code
    voucher_expires_at = db.Column(db.DateTime)

    # Shopify sync (for store credit)
    shopify_credit_id = db.Column(db.String(100))  # Store credit ID
    shopify_discount_id = db.Column(db.String(100))  # Price rule/discount ID
    synced_to_shopify = db.Column(db.Boolean, default=False)
    sync_error = db.Column(db.String(500))

    # Usage tracking
    used_at = db.Column(db.DateTime)  # When voucher was used
    used_order_id = db.Column(db.String(100))  # Shopify order where used

    # Metadata
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(100))  # 'member' or staff email
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    cancelled_reason = db.Column(db.String(200))

    # Relationships
    tenant = db.relationship('Tenant', backref='reward_redemptions')
    member = db.relationship('Member', backref='reward_redemptions')

    # Indexes
    __table_args__ = (
        db.Index('ix_redemptions_member_created', 'member_id', 'created_at'),
        db.Index('ix_redemptions_tenant_status', 'tenant_id', 'status'),
        db.Index('ix_redemptions_voucher', 'voucher_code'),
        db.Index('ix_redemptions_code', 'redemption_code'),
    )

    def __repr__(self):
        return f'<RewardRedemption {self.redemption_code}: {self.points_spent} pts>'

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            'id': self.id,
            'member_id': self.member_id,
            'reward_id': self.reward_id,
            'redemption_code': self.redemption_code,
            'points_spent': self.points_spent,
            'status': self.status,
            'reward_type': self.reward_type,
            'reward_name': self.reward_name,
            'reward_value': float(self.reward_value) if self.reward_value else None,
            'voucher_code': self.voucher_code,
            'voucher_expires_at': self.voucher_expires_at.isoformat() if self.voucher_expires_at else None,
            'synced_to_shopify': self.synced_to_shopify,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    def to_dict_detailed(self) -> Dict[str, Any]:
        """Detailed serialization including Shopify sync info."""
        data = self.to_dict()
        data.update({
            'shopify_credit_id': self.shopify_credit_id,
            'shopify_discount_id': self.shopify_discount_id,
            'sync_error': self.sync_error,
            'used_order_id': self.used_order_id,
            'notes': self.notes,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'cancelled_reason': self.cancelled_reason,
        })
        return data

    @staticmethod
    def generate_redemption_code() -> str:
        """Generate unique redemption reference code."""
        import secrets
        today = datetime.utcnow().strftime('%Y%m%d')
        random_suffix = secrets.token_hex(4).upper()
        return f'RD-{today}-{random_suffix}'

    @staticmethod
    def generate_voucher_code(prefix: str = 'TU') -> str:
        """Generate unique voucher/discount code."""
        import secrets
        import string
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(secrets.choice(chars) for _ in range(8))
        return f'{prefix}-{random_part}'


# ==================== Points Program Configuration ====================

class PointsProgramConfig(db.Model):
    """
    Points program configuration per tenant.

    Stores global settings for the points program:
    - Points currency name/display
    - Default expiration policy
    - Conversion rates
    - Program-wide settings
    """
    __tablename__ = 'points_program_configs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, unique=True)

    # Program branding
    program_name = db.Column(db.String(100), default='Rewards')  # "TradeUp Points", "Star Rewards"
    points_name = db.Column(db.String(50), default='points')  # "points", "stars", "coins"
    points_name_singular = db.Column(db.String(50), default='point')
    currency_symbol = db.Column(db.String(10))  # Optional: "★", "⬡", etc.

    # Default earning rate
    default_points_per_dollar = db.Column(db.Integer, default=1)

    # Points to credit conversion
    points_to_credit_rate = db.Column(db.Numeric(8, 4), default=Decimal('0.01'))  # 100 pts = $1

    # Expiration policy
    points_expire = db.Column(db.Boolean, default=True)
    expiration_days = db.Column(db.Integer, default=365)  # Days until points expire
    expiration_warning_days = db.Column(db.Integer, default=30)  # Warn X days before

    # Minimum thresholds
    min_points_to_redeem = db.Column(db.Integer, default=100)
    min_credit_redemption = db.Column(db.Numeric(10, 2), default=Decimal('1.00'))

    # Program features
    allow_partial_redemption = db.Column(db.Boolean, default=True)
    show_points_on_products = db.Column(db.Boolean, default=True)
    show_progress_to_next_reward = db.Column(db.Boolean, default=True)

    # Tier multipliers (JSON: {"SILVER": 1.0, "GOLD": 1.5, "PLATINUM": 2.0})
    tier_multipliers = db.Column(db.Text)

    # Status
    is_active = db.Column(db.Boolean, default=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='points_program_config', uselist=False)

    def __repr__(self):
        return f'<PointsProgramConfig tenant={self.tenant_id}>'

    def get_tier_multiplier(self, tier_name: str) -> float:
        """Get earning multiplier for a tier."""
        if not self.tier_multipliers:
            return 1.0

        import json
        try:
            multipliers = json.loads(self.tier_multipliers)
            return float(multipliers.get(tier_name.upper(), 1.0))
        except (json.JSONDecodeError, TypeError):
            return 1.0

    def points_to_credit(self, points: int) -> Decimal:
        """Convert points to store credit value."""
        rate = self.points_to_credit_rate or Decimal('0.01')
        return Decimal(points) * rate

    def credit_to_points(self, credit: Decimal) -> int:
        """Convert store credit value to points."""
        rate = self.points_to_credit_rate or Decimal('0.01')
        if rate == 0:
            return 0
        return int(credit / rate)

    def format_points(self, points: int) -> str:
        """Format points for display."""
        symbol = self.currency_symbol or ''
        name = self.points_name if points != 1 else self.points_name_singular
        if symbol:
            return f'{symbol}{points:,}'
        return f'{points:,} {name}'

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        import json

        def safe_json_loads(value):
            if not value:
                return None
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None

        return {
            'tenant_id': self.tenant_id,
            'program_name': self.program_name,
            'points_name': self.points_name,
            'points_name_singular': self.points_name_singular,
            'currency_symbol': self.currency_symbol,
            'default_points_per_dollar': self.default_points_per_dollar,
            'points_to_credit_rate': float(self.points_to_credit_rate or 0.01),
            'points_expire': self.points_expire,
            'expiration_days': self.expiration_days,
            'expiration_warning_days': self.expiration_warning_days,
            'min_points_to_redeem': self.min_points_to_redeem,
            'min_credit_redemption': float(self.min_credit_redemption or 1),
            'allow_partial_redemption': self.allow_partial_redemption,
            'show_points_on_products': self.show_points_on_products,
            'show_progress_to_next_reward': self.show_progress_to_next_reward,
            'tier_multipliers': safe_json_loads(self.tier_multipliers),
            'is_active': self.is_active,
        }


# ==================== Default Configuration ====================

DEFAULT_EARNING_RULES = [
    {
        'name': 'Base Earning Rate',
        'code': 'base_rate',
        'description': 'Earn 1 point for every $1 spent',
        'rule_type': 'base_rate',
        'points_per_dollar': 1,
        'trigger_source': 'purchase',
        'is_base_rule': True,
        'is_active': True,
        'priority': 0,
    },
    {
        'name': 'Trade-In Points',
        'code': 'trade_in_base',
        'description': 'Earn 2 points per $1 of trade-in value',
        'rule_type': 'base_rate',
        'points_per_dollar': 2,
        'trigger_source': 'trade_in',
        'is_base_rule': True,
        'is_active': True,
        'priority': 0,
    },
]

DEFAULT_REWARDS = [
    {
        'name': '$5 Store Credit',
        'code': 'credit_5',
        'description': 'Redeem for $5 in store credit',
        'short_description': '$5 off your next purchase',
        'reward_type': 'store_credit',
        'points_cost': 500,
        'credit_value': Decimal('5.00'),
        'is_active': True,
        'is_featured': False,
        'display_order': 1,
    },
    {
        'name': '$10 Store Credit',
        'code': 'credit_10',
        'description': 'Redeem for $10 in store credit',
        'short_description': '$10 off your next purchase',
        'reward_type': 'store_credit',
        'points_cost': 1000,
        'credit_value': Decimal('10.00'),
        'is_active': True,
        'is_featured': True,
        'badge_text': 'Popular',
        'display_order': 2,
    },
    {
        'name': '$25 Store Credit',
        'code': 'credit_25',
        'description': 'Redeem for $25 in store credit',
        'short_description': '$25 off your next purchase',
        'reward_type': 'store_credit',
        'points_cost': 2500,
        'credit_value': Decimal('25.00'),
        'is_active': True,
        'is_featured': False,
        'display_order': 3,
    },
    {
        'name': 'Free Shipping',
        'code': 'free_shipping',
        'description': 'Get free shipping on your next order',
        'short_description': 'Free shipping voucher',
        'reward_type': 'free_shipping',
        'points_cost': 250,
        'is_active': True,
        'is_featured': False,
        'display_order': 4,
    },
]


def seed_points_program(tenant_id: int):
    """Seed default points program configuration for a tenant."""
    try:
        # Create program config if not exists
        existing_config = PointsProgramConfig.query.filter_by(tenant_id=tenant_id).first()
        if not existing_config:
            config = PointsProgramConfig(
                tenant_id=tenant_id,
                program_name='TradeUp Rewards',
                points_name='points',
                points_name_singular='point',
                default_points_per_dollar=1,
                points_to_credit_rate=Decimal('0.01'),
                points_expire=True,
                expiration_days=365,
                min_points_to_redeem=100,
            )
            db.session.add(config)

        # Create default earning rules
        for rule_data in DEFAULT_EARNING_RULES:
            existing = EarningRule.query.filter_by(
                tenant_id=tenant_id,
                code=rule_data['code']
            ).first()
            if not existing:
                rule = EarningRule(tenant_id=tenant_id, **rule_data)
                db.session.add(rule)

        # Create default rewards
        for reward_data in DEFAULT_REWARDS:
            existing = Reward.query.filter_by(
                tenant_id=tenant_id,
                code=reward_data['code']
            ).first()
            if not existing:
                reward = Reward(tenant_id=tenant_id, **reward_data)
                db.session.add(reward)

        db.session.commit()
        print(f"[LoyaltyPoints] Seeded points program for tenant {tenant_id}")

    except Exception as e:
        db.session.rollback()
        print(f"[LoyaltyPoints] Could not seed points program: {e}")
