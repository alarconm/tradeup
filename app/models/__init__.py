"""
Database models for TradeUp platform.
Store credit, rewards, and membership management for Shopify.
"""
from .tenant import Tenant, APIKey
from .member import MembershipTier, Member
from .trade_in import TradeInBatch, TradeInItem
from .bonus import BonusTransaction
from .points import PointsTransaction, StoreCreditTransaction
from .partner_integration import PartnerIntegration, PartnerSyncLog
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

__all__ = [
    'Tenant',
    'APIKey',
    'MembershipTier',
    'Member',
    'TradeInBatch',
    'TradeInItem',
    'BonusTransaction',
    'PointsTransaction',
    'StoreCreditTransaction',
    'PartnerIntegration',
    'PartnerSyncLog',
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
]
