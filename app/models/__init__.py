"""
Database models for TradeUp platform.
Store credit, rewards, and membership management for Shopify.
"""
from .tenant import Tenant, APIKey
from .member import MembershipTier, Member
from .trade_in import TradeInBatch, TradeInItem
from .points import PointsTransaction, StoreCreditTransaction
from .partner_integration import PartnerIntegration, PartnerSyncLog
from .tier_history import (
    TierChangeLog,
    TierEligibilityRule,
    TierPromotion,
    MemberPromoUsage,
)
from .promotions import (
    Promotion,
    StoreCreditLedger,
    MemberCreditBalance,
    BulkCreditOperation,
    TierConfiguration,
    PromotionType,
    PromotionChannel,
    CreditEventType,
    TIER_CASHBACK,
    seed_tier_configurations,
)
from .referral import Referral, ReferralProgram

__all__ = [
    'Tenant',
    'APIKey',
    'MembershipTier',
    'Member',
    'TradeInBatch',
    'TradeInItem',
    'PointsTransaction',
    'StoreCreditTransaction',
    'PartnerIntegration',
    'PartnerSyncLog',
    # Tier History & Eligibility
    'TierChangeLog',
    'TierEligibilityRule',
    'TierPromotion',
    'MemberPromoUsage',
    # Promotions & Store Credit
    'Promotion',
    'StoreCreditLedger',
    'MemberCreditBalance',
    'BulkCreditOperation',
    'TierConfiguration',
    'PromotionType',
    'PromotionChannel',
    'CreditEventType',
    'TIER_CASHBACK',
    'seed_tier_configurations',
    # Referrals
    'Referral',
    'ReferralProgram',
]
