"""
Database models for TradeUp platform.
Store credit, rewards, and membership management for Shopify.
"""
from .tenant import Tenant, APIKey, BillingHistory
from .member import MembershipTier, Member
from .trade_in import TradeInBatch, TradeInItem
from .trade_ledger import TradeInLedger
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
from .loyalty_points import (
    # Enums
    PointsTransactionType,
    PointsEarnSource,
    EarningRuleType,
    RewardType,
    RewardRedemptionStatus,
    # Models
    PointsBalance,
    PointsLedger,
    EarningRule,
    Reward,
    RewardRedemption,
    PointsProgramConfig,
    # Seeders
    seed_points_program,
    DEFAULT_EARNING_RULES,
    DEFAULT_REWARDS,
)
from .cashback_campaign import CashbackCampaign, CashbackRedemption
from .gamification import Badge, MemberBadge, MemberStreak, Milestone, MemberMilestone
from .guest_points import GuestPoints

__all__ = [
    'Tenant',
    'APIKey',
    'BillingHistory',
    'MembershipTier',
    'Member',
    'TradeInBatch',
    'TradeInItem',
    'TradeInLedger',
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
    # Points-based Loyalty System
    'PointsTransactionType',
    'PointsEarnSource',
    'EarningRuleType',
    'RewardType',
    'RewardRedemptionStatus',
    'PointsBalance',
    'PointsLedger',
    'EarningRule',
    'Reward',
    'RewardRedemption',
    'PointsProgramConfig',
    'seed_points_program',
    'DEFAULT_EARNING_RULES',
    'DEFAULT_REWARDS',
    # Cashback Campaigns
    'CashbackCampaign',
    'CashbackRedemption',
    # Gamification
    'Badge',
    'MemberBadge',
    'MemberStreak',
    'Milestone',
    'MemberMilestone',
    # Guest Points
    'GuestPoints',
]
