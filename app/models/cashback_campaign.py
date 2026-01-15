"""
Cashback Campaign Model for TradeUp.

Supports promotional cashback periods where customers earn
a percentage of their purchase as store credit.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from ..extensions import db


class CashbackCampaign(db.Model):
    """
    Cashback campaign configuration.

    Merchants can create time-limited campaigns where customers
    earn a percentage of their purchase as store credit.
    """
    __tablename__ = 'cashback_campaigns'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    # Campaign identity
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    internal_notes = db.Column(db.Text)  # For merchant reference

    # Cashback configuration
    cashback_rate = db.Column(db.Numeric(5, 2), nullable=False)  # e.g., 5.00 for 5%
    min_purchase = db.Column(db.Numeric(10, 2))  # Minimum order value
    max_cashback = db.Column(db.Numeric(10, 2))  # Cap per order
    max_total_cashback = db.Column(db.Numeric(12, 2))  # Total campaign budget

    # Timing
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)

    # Targeting
    applies_to = db.Column(db.String(100), default='all')  # 'all', 'tier:gold', 'product:123', 'collection:456'
    applies_to_new_customers = db.Column(db.Boolean, default=True)
    applies_to_existing_customers = db.Column(db.Boolean, default=True)
    tier_restriction = db.Column(db.Text)  # JSON: ["GOLD", "PLATINUM"] or null for all

    # Product restrictions (JSON)
    included_products = db.Column(db.Text)  # JSON array of product IDs
    excluded_products = db.Column(db.Text)  # JSON array of product IDs
    included_collections = db.Column(db.Text)  # JSON array of collection IDs
    excluded_collections = db.Column(db.Text)  # JSON array of collection IDs

    # Stacking rules
    stackable_with_discounts = db.Column(db.Boolean, default=True)
    stackable_with_promotions = db.Column(db.Boolean, default=True)

    # Limits
    max_uses_total = db.Column(db.Integer)  # Total redemptions allowed
    max_uses_per_customer = db.Column(db.Integer, default=1)  # Per customer limit
    current_uses = db.Column(db.Integer, default=0)
    total_cashback_issued = db.Column(db.Numeric(12, 2), default=Decimal('0'))

    # Status
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, active, paused, ended, cancelled

    # Metadata
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    activated_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)

    # Relationships
    tenant = db.relationship('Tenant', backref='cashback_campaigns')

    # Indexes
    __table_args__ = (
        db.Index('ix_cashback_tenant_status', 'tenant_id', 'status'),
        db.Index('ix_cashback_dates', 'start_date', 'end_date'),
    )

    def __repr__(self):
        return f'<CashbackCampaign {self.name}: {self.cashback_rate}%>'

    def is_active(self) -> bool:
        """Check if campaign is currently active."""
        if self.status not in ['active', 'scheduled']:
            return False

        now = datetime.utcnow()
        return self.start_date <= now <= self.end_date

    def is_within_budget(self, amount: Decimal) -> bool:
        """Check if campaign has budget for cashback amount."""
        if not self.max_total_cashback:
            return True

        issued = self.total_cashback_issued or Decimal('0')
        return (issued + amount) <= self.max_total_cashback

    def calculate_cashback(self, order_total: Decimal) -> Decimal:
        """
        Calculate cashback amount for an order.

        Args:
            order_total: Order subtotal

        Returns:
            Cashback amount (may be 0 if order doesn't qualify)
        """
        if not self.is_active():
            return Decimal('0')

        # Check minimum purchase
        if self.min_purchase and order_total < self.min_purchase:
            return Decimal('0')

        # Calculate base cashback
        rate = self.cashback_rate / Decimal('100')
        cashback = order_total * rate

        # Apply per-order cap
        if self.max_cashback and cashback > self.max_cashback:
            cashback = self.max_cashback

        # Check remaining budget
        if self.max_total_cashback:
            remaining = self.max_total_cashback - (self.total_cashback_issued or Decimal('0'))
            if cashback > remaining:
                cashback = max(Decimal('0'), remaining)

        return cashback.quantize(Decimal('0.01'))

    def applies_to_tier(self, tier_name: Optional[str]) -> bool:
        """Check if campaign applies to a tier."""
        if not self.tier_restriction:
            return True

        if not tier_name:
            return False

        import json
        try:
            allowed = json.loads(self.tier_restriction)
            return tier_name.upper() in [t.upper() for t in allowed]
        except (json.JSONDecodeError, TypeError):
            return True

    def applies_to_product(self, product_id: str) -> bool:
        """Check if campaign applies to a product."""
        import json

        # Check exclusions first
        if self.excluded_products:
            try:
                excluded = json.loads(self.excluded_products)
                if product_id in excluded:
                    return False
            except (json.JSONDecodeError, TypeError):
                pass

        # Check inclusions
        if self.included_products:
            try:
                included = json.loads(self.included_products)
                return product_id in included
            except (json.JSONDecodeError, TypeError):
                return True

        return True  # No restrictions

    def check_customer_eligibility(
        self,
        customer_id: str,
        is_new: bool,
        tier_name: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Check if a customer is eligible for this campaign.

        Returns:
            Tuple of (is_eligible, reason)
        """
        if not self.is_active():
            return False, 'Campaign is not active'

        if is_new and not self.applies_to_new_customers:
            return False, 'Campaign does not apply to new customers'

        if not is_new and not self.applies_to_existing_customers:
            return False, 'Campaign does not apply to existing customers'

        if not self.applies_to_tier(tier_name):
            return False, f'Campaign does not apply to {tier_name} tier'

        # Check usage limits
        if self.max_uses_total and self.current_uses >= self.max_uses_total:
            return False, 'Campaign usage limit reached'

        return True, 'Eligible'

    def record_usage(self, cashback_amount: Decimal):
        """Record a cashback redemption."""
        self.current_uses = (self.current_uses or 0) + 1
        self.total_cashback_issued = (self.total_cashback_issued or Decimal('0')) + cashback_amount

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
            'description': self.description,
            'cashback_rate': float(self.cashback_rate),
            'min_purchase': float(self.min_purchase) if self.min_purchase else None,
            'max_cashback': float(self.max_cashback) if self.max_cashback else None,
            'max_total_cashback': float(self.max_total_cashback) if self.max_total_cashback else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'applies_to': self.applies_to,
            'tier_restriction': safe_json_loads(self.tier_restriction),
            'stackable_with_discounts': self.stackable_with_discounts,
            'stackable_with_promotions': self.stackable_with_promotions,
            'max_uses_total': self.max_uses_total,
            'max_uses_per_customer': self.max_uses_per_customer,
            'current_uses': self.current_uses or 0,
            'total_cashback_issued': float(self.total_cashback_issued or 0),
            'status': self.status,
            'is_active': self.is_active(),
            'budget_remaining': float(
                (self.max_total_cashback or Decimal('0')) - (self.total_cashback_issued or Decimal('0'))
            ) if self.max_total_cashback else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_dict_admin(self) -> Dict[str, Any]:
        """Full serialization including admin fields."""
        data = self.to_dict()
        import json

        def safe_json_loads(value):
            if not value:
                return None
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None

        data.update({
            'internal_notes': self.internal_notes,
            'included_products': safe_json_loads(self.included_products),
            'excluded_products': safe_json_loads(self.excluded_products),
            'included_collections': safe_json_loads(self.included_collections),
            'excluded_collections': safe_json_loads(self.excluded_collections),
            'applies_to_new_customers': self.applies_to_new_customers,
            'applies_to_existing_customers': self.applies_to_existing_customers,
            'created_by': self.created_by,
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
        })
        return data


class CashbackRedemption(db.Model):
    """
    Track individual cashback redemptions.

    Records each time a customer earns cashback from a campaign.
    """
    __tablename__ = 'cashback_redemptions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('cashback_campaigns.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'))

    # Order details
    shopify_order_id = db.Column(db.String(100), nullable=False)
    order_number = db.Column(db.String(50))
    order_total = db.Column(db.Numeric(10, 2), nullable=False)

    # Cashback details
    cashback_rate = db.Column(db.Numeric(5, 2), nullable=False)  # Rate at time of redemption
    cashback_amount = db.Column(db.Numeric(10, 2), nullable=False)

    # Customer info (snapshot)
    customer_email = db.Column(db.String(255))
    customer_tier = db.Column(db.String(50))

    # Fulfillment
    credit_issued = db.Column(db.Boolean, default=False)
    credit_entry_id = db.Column(db.Integer)  # Link to StoreCreditLedger
    issued_at = db.Column(db.DateTime)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='cashback_redemptions')
    campaign = db.relationship('CashbackCampaign', backref='redemptions')
    member = db.relationship('Member', backref='cashback_redemptions')

    # Indexes
    __table_args__ = (
        db.Index('ix_cashback_redemption_order', 'shopify_order_id'),
        db.Index('ix_cashback_redemption_campaign', 'campaign_id'),
        db.Index('ix_cashback_redemption_member', 'member_id'),
    )

    def __repr__(self):
        return f'<CashbackRedemption order={self.order_number}: ${self.cashback_amount}>'

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'member_id': self.member_id,
            'shopify_order_id': self.shopify_order_id,
            'order_number': self.order_number,
            'order_total': float(self.order_total),
            'cashback_rate': float(self.cashback_rate),
            'cashback_amount': float(self.cashback_amount),
            'customer_email': self.customer_email,
            'customer_tier': self.customer_tier,
            'credit_issued': self.credit_issued,
            'issued_at': self.issued_at.isoformat() if self.issued_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
