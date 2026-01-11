"""
Analytics API endpoints for TradeUp.

Provides comprehensive analytics and reporting data for the dashboard.
Includes overview, points, tiers, rewards, referrals, cohort analysis,
and Web Pixel endpoint for storefront event tracking.
"""
import logging
import csv
import io
from flask import Blueprint, request, jsonify, g, Response
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, and_, or_, extract, case, distinct
from ..extensions import db
from ..models.member import Member, MembershipTier
from ..models.trade_in import TradeInBatch, TradeInItem
from ..models.promotions import StoreCreditLedger
from ..models.tenant import Tenant
from ..models.referral import Referral, ReferralProgram
from ..models.tier_history import TierChangeLog
from ..models.loyalty_points import (
    PointsBalance, PointsLedger, EarningRule,
    Reward, RewardRedemption, PointsTransactionType, PointsEarnSource
)
from ..middleware.shopify_auth import require_shopify_auth

logger = logging.getLogger(__name__)

analytics_bp = Blueprint('analytics', __name__)


def get_date_range(period: str) -> tuple:
    """Calculate start/end dates and previous period for comparison."""
    end_date = datetime.utcnow()
    if period == 'all':
        start_date = datetime(2000, 1, 1)
        previous_start = datetime(1999, 1, 1)
    else:
        days = int(period)
        start_date = end_date - timedelta(days=days)
        previous_start = start_date - timedelta(days=days)
    return start_date, end_date, previous_start


def calculate_change(current: float, previous: float) -> dict:
    """Calculate percentage change and trend direction."""
    if previous > 0:
        change_pct = ((current - previous) / previous) * 100
    else:
        change_pct = 100 if current > 0 else 0

    return {
        'current': current,
        'previous': previous,
        'change_pct': round(change_pct, 1),
        'trend': 'up' if change_pct > 0 else 'down' if change_pct < 0 else 'flat'
    }


# ==================== OVERVIEW ENDPOINT ====================

@analytics_bp.route('/overview', methods=['GET'])
@require_shopify_auth
def get_overview_analytics():
    """
    Dashboard summary with key metrics.

    Query params:
        period: '7', '30', '90', '365', 'all' (default: '30')

    Returns:
        - Total members, active members (30 days)
        - Points issued (today/week/month/all-time)
        - Points redeemed
        - Rewards claimed
        - Revenue influenced by loyalty program
        - Member retention rate
    """
    tenant_id = g.tenant_id
    period = request.args.get('period', '30')
    start_date, end_date, previous_start = get_date_range(period)

    try:
        # ====== MEMBER METRICS ======
        total_members = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id
        ).scalar() or 0

        active_members = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.status == 'active'
        ).scalar() or 0

        # Members active in last 30 days (had any activity)
        thirty_days_ago = end_date - timedelta(days=30)
        recently_active = db.session.query(func.count(distinct(Member.id))).filter(
            Member.tenant_id == tenant_id,
            or_(
                Member.updated_at >= thirty_days_ago,
                Member.id.in_(
                    db.session.query(PointsLedger.member_id).filter(
                        PointsLedger.tenant_id == tenant_id,
                        PointsLedger.created_at >= thirty_days_ago
                    )
                )
            )
        ).scalar() or 0

        new_members_current = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.created_at >= start_date
        ).scalar() or 0

        new_members_previous = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.created_at >= previous_start,
            Member.created_at < start_date
        ).scalar() or 0

        member_growth = calculate_change(new_members_current, new_members_previous)

        # Retention rate (active / total)
        retention_rate = (active_members / total_members * 100) if total_members > 0 else 0

        # ====== POINTS METRICS ======
        # Points issued today
        today_start = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        points_today = db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.transaction_type == 'earn',
            PointsLedger.created_at >= today_start
        ).scalar() or 0

        # Points issued this week
        week_start = end_date - timedelta(days=end_date.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        points_week = db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.transaction_type == 'earn',
            PointsLedger.created_at >= week_start
        ).scalar() or 0

        # Points issued this month
        month_start = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        points_month = db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.transaction_type == 'earn',
            PointsLedger.created_at >= month_start
        ).scalar() or 0

        # Points issued all time
        points_all_time = db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.transaction_type == 'earn'
        ).scalar() or 0

        # Points redeemed (current period)
        points_redeemed_current = abs(db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.transaction_type == 'redeem',
            PointsLedger.created_at >= start_date
        ).scalar() or 0)

        points_redeemed_previous = abs(db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.transaction_type == 'redeem',
            PointsLedger.created_at >= previous_start,
            PointsLedger.created_at < start_date
        ).scalar() or 0)

        # ====== REWARDS METRICS ======
        rewards_claimed_current = db.session.query(func.count(RewardRedemption.id)).join(
            Member
        ).filter(
            Member.tenant_id == tenant_id,
            RewardRedemption.status == 'completed',
            RewardRedemption.created_at >= start_date
        ).scalar() or 0

        rewards_claimed_previous = db.session.query(func.count(RewardRedemption.id)).join(
            Member
        ).filter(
            Member.tenant_id == tenant_id,
            RewardRedemption.status == 'completed',
            RewardRedemption.created_at >= previous_start,
            RewardRedemption.created_at < start_date
        ).scalar() or 0

        # Total reward value claimed
        reward_value_claimed = db.session.query(
            func.coalesce(func.sum(RewardRedemption.reward_value), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            RewardRedemption.status == 'completed',
            RewardRedemption.created_at >= start_date
        ).scalar() or 0

        # ====== STORE CREDIT METRICS ======
        credit_issued_current = db.session.query(
            func.coalesce(func.sum(StoreCreditLedger.amount), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            StoreCreditLedger.amount > 0,
            StoreCreditLedger.created_at >= start_date
        ).scalar() or 0

        credit_issued_previous = db.session.query(
            func.coalesce(func.sum(StoreCreditLedger.amount), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            StoreCreditLedger.amount > 0,
            StoreCreditLedger.created_at >= previous_start,
            StoreCreditLedger.created_at < start_date
        ).scalar() or 0

        # ====== TRADE-IN METRICS ======
        trade_ins_current = db.session.query(func.count(TradeInBatch.id)).join(Member).filter(
            Member.tenant_id == tenant_id,
            TradeInBatch.created_at >= start_date
        ).scalar() or 0

        trade_in_value_current = db.session.query(
            func.coalesce(func.sum(TradeInBatch.total_trade_value), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            TradeInBatch.created_at >= start_date
        ).scalar() or 0

        # ====== REFERRAL METRICS ======
        referrals_current = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.referred_by_id.isnot(None),
            Member.created_at >= start_date
        ).scalar() or 0

        # ====== REVENUE INFLUENCED ======
        # Estimate: reward value + store credit issued (represents loyalty-driven purchases)
        revenue_influenced = float(reward_value_claimed) + float(credit_issued_current)

        return jsonify({
            'period': period,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'members': {
                'total': total_members,
                'active': active_members,
                'recently_active': recently_active,
                'new_this_period': new_members_current,
                'growth': member_growth,
                'retention_rate': round(retention_rate, 1)
            },
            'points': {
                'issued_today': int(points_today),
                'issued_week': int(points_week),
                'issued_month': int(points_month),
                'issued_all_time': int(points_all_time),
                'redeemed_this_period': int(points_redeemed_current),
                'redeemed_change': calculate_change(points_redeemed_current, points_redeemed_previous)
            },
            'rewards': {
                'claimed_this_period': rewards_claimed_current,
                'claimed_change': calculate_change(rewards_claimed_current, rewards_claimed_previous),
                'value_claimed': float(reward_value_claimed)
            },
            'store_credit': {
                'issued_this_period': float(credit_issued_current),
                'issued_change': calculate_change(float(credit_issued_current), float(credit_issued_previous))
            },
            'trade_ins': {
                'count_this_period': trade_ins_current,
                'value_this_period': float(trade_in_value_current)
            },
            'referrals': {
                'count_this_period': referrals_current
            },
            'revenue_influenced': {
                'total': revenue_influenced,
                'breakdown': {
                    'rewards_redeemed': float(reward_value_claimed),
                    'store_credit_used': float(credit_issued_current)
                }
            }
        })

    except Exception as e:
        logger.error(f"Overview analytics error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== POINTS METRICS ENDPOINT ====================

@analytics_bp.route('/points', methods=['GET'])
@require_shopify_auth
def get_points_analytics():
    """
    Points-specific metrics.

    Returns:
        - Points earned by source (purchases, referrals, bonuses)
        - Points redemption rate
        - Average points per member
        - Points velocity (earn rate over time)
    """
    tenant_id = g.tenant_id
    period = request.args.get('period', '30')
    start_date, end_date, previous_start = get_date_range(period)

    try:
        # Points earned by source
        source_breakdown = db.session.query(
            PointsLedger.source,
            func.coalesce(func.sum(PointsLedger.points), 0).label('total_points'),
            func.count(PointsLedger.id).label('transaction_count')
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.transaction_type == 'earn',
            PointsLedger.created_at >= start_date
        ).group_by(PointsLedger.source).all()

        by_source = {}
        total_earned = 0
        for source, points, count in source_breakdown:
            source_name = source or 'other'
            by_source[source_name] = {
                'points': int(points),
                'transactions': count
            }
            total_earned += int(points)

        # Total points redeemed
        total_redeemed = abs(db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.transaction_type == 'redeem',
            PointsLedger.created_at >= start_date
        ).scalar() or 0)

        # Redemption rate
        redemption_rate = (total_redeemed / total_earned * 100) if total_earned > 0 else 0

        # Average points per member
        member_count = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id
        ).scalar() or 1

        avg_points_per_member = total_earned / member_count if member_count > 0 else 0

        # Points velocity (daily earn rate over period)
        days_in_period = (end_date - start_date).days or 1
        daily_velocity = total_earned / days_in_period

        # Points velocity trend (compare to previous period)
        prev_earned = db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.transaction_type == 'earn',
            PointsLedger.created_at >= previous_start,
            PointsLedger.created_at < start_date
        ).scalar() or 0

        prev_velocity = int(prev_earned) / days_in_period if days_in_period > 0 else 0

        # Daily breakdown for chart (last 30 days max)
        chart_days = min(30, days_in_period)
        chart_start = end_date - timedelta(days=chart_days)

        daily_points = db.session.query(
            func.date(PointsLedger.created_at).label('date'),
            func.coalesce(func.sum(case(
                (PointsLedger.transaction_type == 'earn', PointsLedger.points),
                else_=0
            )), 0).label('earned'),
            func.coalesce(func.sum(case(
                (PointsLedger.transaction_type == 'redeem', func.abs(PointsLedger.points)),
                else_=0
            )), 0).label('redeemed')
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            PointsLedger.created_at >= chart_start
        ).group_by(func.date(PointsLedger.created_at)).order_by('date').all()

        velocity_chart = []
        for row in daily_points:
            velocity_chart.append({
                'date': row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date),
                'earned': int(row.earned),
                'redeemed': int(row.redeemed)
            })

        # Top earning sources pie chart data
        source_chart = [
            {'source': source, 'points': data['points'], 'transactions': data['transactions']}
            for source, data in by_source.items()
        ]
        source_chart.sort(key=lambda x: x['points'], reverse=True)

        return jsonify({
            'period': period,
            'by_source': by_source,
            'summary': {
                'total_earned': total_earned,
                'total_redeemed': int(total_redeemed),
                'net_points': total_earned - int(total_redeemed),
                'redemption_rate': round(redemption_rate, 1),
                'avg_per_member': round(avg_points_per_member, 0)
            },
            'velocity': {
                'daily_average': round(daily_velocity, 0),
                'previous_daily_average': round(prev_velocity, 0),
                'change': calculate_change(daily_velocity, prev_velocity)
            },
            'charts': {
                'velocity': velocity_chart,
                'by_source': source_chart
            }
        })

    except Exception as e:
        logger.error(f"Points analytics error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== TIER ANALYTICS ENDPOINT ====================

@analytics_bp.route('/tiers', methods=['GET'])
@require_shopify_auth
def get_tier_analytics():
    """
    Tier distribution and movement analytics.

    Returns:
        - Members per tier
        - Tier movement (upgrades/downgrades)
        - Revenue by tier (approximated by trade-in/credit activity)
    """
    tenant_id = g.tenant_id
    period = request.args.get('period', '30')
    start_date, end_date, previous_start = get_date_range(period)

    try:
        # Get all active tiers
        tiers = MembershipTier.query.filter(
            MembershipTier.tenant_id == tenant_id,
            MembershipTier.is_active == True
        ).order_by(MembershipTier.display_order).all()

        # Tier distribution
        distribution = []
        total_members = 0
        for tier in tiers:
            member_count = db.session.query(func.count(Member.id)).filter(
                Member.tenant_id == tenant_id,
                Member.tier_id == tier.id
            ).scalar() or 0

            # Revenue for tier (trade-in value + store credit issued)
            tier_credit = db.session.query(
                func.coalesce(func.sum(StoreCreditLedger.amount), 0)
            ).join(Member).filter(
                Member.tenant_id == tenant_id,
                Member.tier_id == tier.id,
                StoreCreditLedger.amount > 0,
                StoreCreditLedger.created_at >= start_date
            ).scalar() or 0

            tier_trade_value = db.session.query(
                func.coalesce(func.sum(TradeInBatch.total_trade_value), 0)
            ).join(Member).filter(
                Member.tenant_id == tenant_id,
                Member.tier_id == tier.id,
                TradeInBatch.created_at >= start_date
            ).scalar() or 0

            # Average points per member in tier
            tier_points = db.session.query(
                func.coalesce(func.avg(Member.points_balance), 0)
            ).filter(
                Member.tenant_id == tenant_id,
                Member.tier_id == tier.id
            ).scalar() or 0

            total_members += member_count

            distribution.append({
                'tier_id': tier.id,
                'tier_name': tier.name,
                'color': tier.to_dict().get('color', '#6B7280'),
                'member_count': member_count,
                'avg_points': round(float(tier_points), 0),
                'revenue': float(tier_credit) + float(tier_trade_value),
                'trade_value': float(tier_trade_value),
                'credit_issued': float(tier_credit)
            })

        # Add percentages
        for tier_data in distribution:
            tier_data['percentage'] = round(
                (tier_data['member_count'] / total_members * 100) if total_members > 0 else 0, 1
            )

        # Tier movements (upgrades and downgrades)
        upgrades = db.session.query(func.count(TierChangeLog.id)).filter(
            TierChangeLog.tenant_id == tenant_id,
            TierChangeLog.change_type == 'upgraded',
            TierChangeLog.created_at >= start_date
        ).scalar() or 0

        downgrades = db.session.query(func.count(TierChangeLog.id)).filter(
            TierChangeLog.tenant_id == tenant_id,
            TierChangeLog.change_type == 'downgraded',
            TierChangeLog.created_at >= start_date
        ).scalar() or 0

        # Recent tier changes (for activity feed)
        recent_changes = TierChangeLog.query.filter(
            TierChangeLog.tenant_id == tenant_id,
            TierChangeLog.created_at >= start_date
        ).order_by(TierChangeLog.created_at.desc()).limit(20).all()

        movement_history = []
        for change in recent_changes:
            movement_history.append({
                'member_id': change.member_id,
                'previous_tier': change.previous_tier_name,
                'new_tier': change.new_tier_name,
                'change_type': change.change_type,
                'reason': change.reason,
                'created_at': change.created_at.isoformat()
            })

        return jsonify({
            'period': period,
            'distribution': distribution,
            'total_members': total_members,
            'movement': {
                'upgrades': upgrades,
                'downgrades': downgrades,
                'net_movement': upgrades - downgrades
            },
            'recent_changes': movement_history
        })

    except Exception as e:
        logger.error(f"Tier analytics error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== REWARDS ANALYTICS ENDPOINT ====================

@analytics_bp.route('/rewards', methods=['GET'])
@require_shopify_auth
def get_rewards_analytics():
    """
    Reward performance analytics.

    Returns:
        - Most popular rewards
        - Redemption by reward type
        - Reward ROI (cost vs revenue generated)
    """
    tenant_id = g.tenant_id
    period = request.args.get('period', '30')
    start_date, end_date, previous_start = get_date_range(period)

    try:
        # Get all rewards for tenant
        rewards = Reward.query.filter(
            Reward.tenant_id == tenant_id
        ).all()

        reward_stats = []
        total_redemptions = 0
        total_points_spent = 0
        total_value_given = 0

        for reward in rewards:
            # Redemption count for this period
            redemptions = db.session.query(func.count(RewardRedemption.id)).filter(
                RewardRedemption.reward_id == reward.id,
                RewardRedemption.status == 'completed',
                RewardRedemption.created_at >= start_date
            ).scalar() or 0

            # Total points spent on this reward
            points_spent = db.session.query(
                func.coalesce(func.sum(RewardRedemption.points_spent), 0)
            ).filter(
                RewardRedemption.reward_id == reward.id,
                RewardRedemption.status == 'completed',
                RewardRedemption.created_at >= start_date
            ).scalar() or 0

            # Total value given
            value_given = db.session.query(
                func.coalesce(func.sum(RewardRedemption.reward_value), 0)
            ).filter(
                RewardRedemption.reward_id == reward.id,
                RewardRedemption.status == 'completed',
                RewardRedemption.created_at >= start_date
            ).scalar() or 0

            total_redemptions += redemptions
            total_points_spent += int(points_spent)
            total_value_given += float(value_given)

            # Calculate points-to-value efficiency
            points_per_dollar = int(points_spent) / float(value_given) if float(value_given) > 0 else 0

            reward_stats.append({
                'reward_id': reward.id,
                'name': reward.name,
                'reward_type': reward.reward_type,
                'points_cost': reward.points_cost,
                'credit_value': float(reward.credit_value) if reward.credit_value else None,
                'redemptions': redemptions,
                'points_spent': int(points_spent),
                'value_given': float(value_given),
                'points_per_dollar': round(points_per_dollar, 1),
                'is_active': reward.is_active,
                'remaining_quantity': reward.remaining_quantity()
            })

        # Sort by popularity (redemptions)
        reward_stats.sort(key=lambda x: x['redemptions'], reverse=True)

        # Breakdown by reward type
        type_breakdown = {}
        for stat in reward_stats:
            rtype = stat['reward_type']
            if rtype not in type_breakdown:
                type_breakdown[rtype] = {
                    'redemptions': 0,
                    'points_spent': 0,
                    'value_given': 0,
                    'rewards_count': 0
                }
            type_breakdown[rtype]['redemptions'] += stat['redemptions']
            type_breakdown[rtype]['points_spent'] += stat['points_spent']
            type_breakdown[rtype]['value_given'] += stat['value_given']
            type_breakdown[rtype]['rewards_count'] += 1

        # Daily redemption trend
        daily_redemptions = db.session.query(
            func.date(RewardRedemption.created_at).label('date'),
            func.count(RewardRedemption.id).label('count'),
            func.coalesce(func.sum(RewardRedemption.points_spent), 0).label('points'),
            func.coalesce(func.sum(RewardRedemption.reward_value), 0).label('value')
        ).join(Member).filter(
            Member.tenant_id == tenant_id,
            RewardRedemption.status == 'completed',
            RewardRedemption.created_at >= start_date
        ).group_by(func.date(RewardRedemption.created_at)).order_by('date').all()

        redemption_trend = []
        for row in daily_redemptions:
            redemption_trend.append({
                'date': row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date),
                'redemptions': row.count,
                'points': int(row.points),
                'value': float(row.value)
            })

        return jsonify({
            'period': period,
            'summary': {
                'total_redemptions': total_redemptions,
                'total_points_spent': total_points_spent,
                'total_value_given': total_value_given,
                'avg_points_per_redemption': round(total_points_spent / total_redemptions, 0) if total_redemptions > 0 else 0,
                'avg_value_per_redemption': round(total_value_given / total_redemptions, 2) if total_redemptions > 0 else 0
            },
            'top_rewards': reward_stats[:10],
            'all_rewards': reward_stats,
            'by_type': type_breakdown,
            'trend': redemption_trend
        })

    except Exception as e:
        logger.error(f"Rewards analytics error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== REFERRALS ANALYTICS ENDPOINT ====================

@analytics_bp.route('/referrals', methods=['GET'])
@require_shopify_auth
def get_referral_analytics():
    """
    Referral program metrics.

    Returns:
        - Total referrals
        - Conversion rate
        - Revenue from referrals
        - Top referrers
    """
    tenant_id = g.tenant_id
    period = request.args.get('period', '30')
    start_date, end_date, previous_start = get_date_range(period)

    try:
        # Get referral program config
        program = ReferralProgram.query.filter_by(tenant_id=tenant_id).first()

        # Total referrals created this period
        total_referrals = db.session.query(func.count(Referral.id)).join(
            ReferralProgram
        ).filter(
            ReferralProgram.tenant_id == tenant_id,
            Referral.created_at >= start_date
        ).scalar() or 0

        # Completed referrals (converted)
        completed_referrals = db.session.query(func.count(Referral.id)).join(
            ReferralProgram
        ).filter(
            ReferralProgram.tenant_id == tenant_id,
            Referral.status == 'completed',
            Referral.created_at >= start_date
        ).scalar() or 0

        # Conversion rate
        conversion_rate = (completed_referrals / total_referrals * 100) if total_referrals > 0 else 0

        # Total rewards paid
        referrer_rewards = db.session.query(
            func.coalesce(func.sum(Referral.referrer_reward_amount), 0)
        ).join(ReferralProgram).filter(
            ReferralProgram.tenant_id == tenant_id,
            Referral.referrer_reward_issued == True,
            Referral.created_at >= start_date
        ).scalar() or 0

        referee_rewards = db.session.query(
            func.coalesce(func.sum(Referral.referee_reward_amount), 0)
        ).join(ReferralProgram).filter(
            ReferralProgram.tenant_id == tenant_id,
            Referral.referee_reward_issued == True,
            Referral.created_at >= start_date
        ).scalar() or 0

        total_rewards_paid = float(referrer_rewards) + float(referee_rewards)

        # Revenue from referred members (trade-in + credit activity)
        referred_member_ids = db.session.query(Member.id).filter(
            Member.tenant_id == tenant_id,
            Member.referred_by_id.isnot(None),
            Member.created_at >= start_date
        ).all()
        referred_ids = [m.id for m in referred_member_ids]

        revenue_from_referrals = 0
        if referred_ids:
            referred_activity = db.session.query(
                func.coalesce(func.sum(TradeInBatch.total_trade_value), 0)
            ).filter(
                TradeInBatch.member_id.in_(referred_ids)
            ).scalar() or 0
            revenue_from_referrals = float(referred_activity)

        # Top referrers
        top_referrers = db.session.query(
            Member.id,
            Member.member_number,
            Member.name,
            Member.referral_code,
            Member.referral_count,
            Member.referral_earnings
        ).filter(
            Member.tenant_id == tenant_id,
            Member.referral_count > 0
        ).order_by(Member.referral_count.desc()).limit(10).all()

        referrer_list = []
        for r in top_referrers:
            referrer_list.append({
                'member_id': r.id,
                'member_number': r.member_number,
                'name': r.name or r.member_number,
                'referral_code': r.referral_code,
                'referral_count': r.referral_count or 0,
                'earnings': float(r.referral_earnings or 0)
            })

        # Monthly trend
        monthly_referrals = db.session.query(
            extract('month', Referral.created_at).label('month'),
            extract('year', Referral.created_at).label('year'),
            func.count(Referral.id).label('total'),
            func.sum(case((Referral.status == 'completed', 1), else_=0)).label('completed')
        ).join(ReferralProgram).filter(
            ReferralProgram.tenant_id == tenant_id,
            Referral.created_at >= start_date
        ).group_by(
            extract('year', Referral.created_at),
            extract('month', Referral.created_at)
        ).order_by('year', 'month').all()

        trend = []
        for row in monthly_referrals:
            trend.append({
                'month': f"{int(row.year)}-{int(row.month):02d}",
                'total': row.total,
                'completed': int(row.completed) if row.completed else 0
            })

        return jsonify({
            'period': period,
            'program': program.to_dict() if program else None,
            'summary': {
                'total_referrals': total_referrals,
                'completed_referrals': completed_referrals,
                'pending_referrals': total_referrals - completed_referrals,
                'conversion_rate': round(conversion_rate, 1),
                'total_rewards_paid': total_rewards_paid,
                'referrer_rewards': float(referrer_rewards),
                'referee_rewards': float(referee_rewards),
                'revenue_from_referrals': revenue_from_referrals
            },
            'roi': {
                'cost': total_rewards_paid,
                'revenue': revenue_from_referrals,
                'ratio': round(revenue_from_referrals / total_rewards_paid, 2) if total_rewards_paid > 0 else 0
            },
            'top_referrers': referrer_list,
            'trend': trend
        })

    except Exception as e:
        logger.error(f"Referral analytics error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== COHORT ANALYTICS ENDPOINT ====================

@analytics_bp.route('/cohorts', methods=['GET'])
@require_shopify_auth
def get_cohort_analytics():
    """
    Cohort analysis for member retention and LTV.

    Returns:
        - Member signup cohorts
        - Retention by signup month
        - LTV by cohort
    """
    tenant_id = g.tenant_id
    months_back = int(request.args.get('months', '6'))

    try:
        cohorts = []
        end_date = datetime.utcnow()

        for i in range(months_back):
            # Calculate month boundaries
            month_end = end_date.replace(day=1) - timedelta(days=1)
            for _ in range(i):
                month_end = month_end.replace(day=1) - timedelta(days=1)
            month_start = month_end.replace(day=1)
            next_month = (month_start + timedelta(days=32)).replace(day=1)

            # Members who signed up this month
            cohort_members = Member.query.filter(
                Member.tenant_id == tenant_id,
                Member.created_at >= month_start,
                Member.created_at < next_month
            ).all()

            cohort_member_ids = [m.id for m in cohort_members]
            cohort_size = len(cohort_member_ids)

            if cohort_size == 0:
                cohorts.append({
                    'cohort_month': month_start.strftime('%Y-%m'),
                    'cohort_label': month_start.strftime('%b %Y'),
                    'size': 0,
                    'retention_rates': {},
                    'ltv': 0,
                    'avg_points': 0,
                    'avg_trade_ins': 0
                })
                continue

            # Calculate retention for each subsequent month
            retention_rates = {}
            for m in range(1, min(months_back - i, 7)):  # Up to 6 months retention
                retention_date = (month_start + timedelta(days=32 * m)).replace(day=1)

                # Members still active (any activity after this date)
                retained = db.session.query(func.count(distinct(Member.id))).filter(
                    Member.id.in_(cohort_member_ids),
                    Member.status == 'active',
                    or_(
                        Member.updated_at >= retention_date,
                        Member.id.in_(
                            db.session.query(PointsLedger.member_id).filter(
                                PointsLedger.member_id.in_(cohort_member_ids),
                                PointsLedger.created_at >= retention_date
                            )
                        ),
                        Member.id.in_(
                            db.session.query(TradeInBatch.member_id).filter(
                                TradeInBatch.member_id.in_(cohort_member_ids),
                                TradeInBatch.created_at >= retention_date
                            )
                        )
                    )
                ).scalar() or 0

                retention_rates[f'month_{m}'] = round(retained / cohort_size * 100, 1)

            # LTV for cohort (total credit + trade-in value)
            cohort_ltv = 0
            if cohort_member_ids:
                credit_value = db.session.query(
                    func.coalesce(func.sum(StoreCreditLedger.amount), 0)
                ).filter(
                    StoreCreditLedger.member_id.in_(cohort_member_ids),
                    StoreCreditLedger.amount > 0
                ).scalar() or 0

                trade_value = db.session.query(
                    func.coalesce(func.sum(TradeInBatch.total_trade_value), 0)
                ).filter(
                    TradeInBatch.member_id.in_(cohort_member_ids)
                ).scalar() or 0

                cohort_ltv = float(credit_value) + float(trade_value)

            # Average stats for cohort
            avg_points = db.session.query(
                func.coalesce(func.avg(Member.lifetime_points_earned), 0)
            ).filter(
                Member.id.in_(cohort_member_ids)
            ).scalar() or 0

            avg_trade_ins = db.session.query(
                func.coalesce(func.avg(Member.total_trade_ins), 0)
            ).filter(
                Member.id.in_(cohort_member_ids)
            ).scalar() or 0

            cohorts.append({
                'cohort_month': month_start.strftime('%Y-%m'),
                'cohort_label': month_start.strftime('%b %Y'),
                'size': cohort_size,
                'retention_rates': retention_rates,
                'ltv': round(cohort_ltv, 2),
                'ltv_per_member': round(cohort_ltv / cohort_size, 2) if cohort_size > 0 else 0,
                'avg_points': round(float(avg_points), 0),
                'avg_trade_ins': round(float(avg_trade_ins), 1)
            })

        # Reverse so oldest cohort is first
        cohorts.reverse()

        # Calculate overall metrics
        total_members = sum(c['size'] for c in cohorts)
        avg_ltv = sum(c['ltv_per_member'] * c['size'] for c in cohorts) / total_members if total_members > 0 else 0

        return jsonify({
            'months_analyzed': months_back,
            'cohorts': cohorts,
            'summary': {
                'total_members_analyzed': total_members,
                'average_ltv_per_member': round(avg_ltv, 2),
                'best_cohort': max(cohorts, key=lambda x: x['ltv_per_member'])['cohort_label'] if cohorts else None
            }
        })

    except Exception as e:
        logger.error(f"Cohort analytics error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== LEGACY DASHBOARD ENDPOINT ====================

@analytics_bp.route('/dashboard', methods=['GET'])
@require_shopify_auth
def get_dashboard_analytics():
    """
    Get comprehensive analytics for the dashboard.
    Legacy endpoint - maintained for backwards compatibility.

    Query params:
        period: '7', '30', '90', '365', 'all' (default: '30')
    """
    tenant_id = g.tenant_id
    period = request.args.get('period', '30')

    # Calculate date range
    end_date = datetime.utcnow()
    if period == 'all':
        start_date = datetime(2000, 1, 1)
    else:
        days = int(period)
        start_date = end_date - timedelta(days=days)

    # Previous period for comparison
    previous_start = start_date - timedelta(days=(end_date - start_date).days)

    try:
        # Get member statistics
        total_members = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id
        ).scalar() or 0

        active_members = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.status == 'active'
        ).scalar() or 0

        new_members_this_period = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.created_at >= start_date
        ).scalar() or 0

        new_members_previous = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.created_at >= previous_start,
            Member.created_at < start_date
        ).scalar() or 0

        # Calculate growth percentage
        if new_members_previous > 0:
            member_growth_pct = ((new_members_this_period - new_members_previous) / new_members_previous) * 100
        else:
            member_growth_pct = 100 if new_members_this_period > 0 else 0

        # Get trade-in statistics (join through Member for tenant filtering)
        total_trade_ins = db.session.query(func.count(TradeInBatch.id)).join(
            Member, Member.id == TradeInBatch.member_id
        ).filter(
            Member.tenant_id == tenant_id
        ).scalar() or 0

        trade_ins_this_period = db.session.query(func.count(TradeInBatch.id)).join(
            Member, Member.id == TradeInBatch.member_id
        ).filter(
            Member.tenant_id == tenant_id,
            TradeInBatch.created_at >= start_date
        ).scalar() or 0

        trade_in_value_this_period = db.session.query(
            func.coalesce(func.sum(TradeInBatch.total_trade_value), 0)
        ).join(
            Member, Member.id == TradeInBatch.member_id
        ).filter(
            Member.tenant_id == tenant_id,
            TradeInBatch.created_at >= start_date
        ).scalar() or 0

        # Get store credit statistics (join through Member for tenant filtering)
        total_credit_issued = db.session.query(
            func.coalesce(func.sum(StoreCreditLedger.amount), 0)
        ).join(
            Member, Member.id == StoreCreditLedger.member_id
        ).filter(
            Member.tenant_id == tenant_id,
            StoreCreditLedger.amount > 0
        ).scalar() or 0

        credit_this_period = db.session.query(
            func.coalesce(func.sum(StoreCreditLedger.amount), 0)
        ).join(
            Member, Member.id == StoreCreditLedger.member_id
        ).filter(
            Member.tenant_id == tenant_id,
            StoreCreditLedger.amount > 0,
            StoreCreditLedger.created_at >= start_date
        ).scalar() or 0

        # Get referral statistics
        total_referrals = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.referred_by_id.isnot(None)
        ).scalar() or 0

        referrals_this_period = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.referred_by_id.isnot(None),
            Member.created_at >= start_date
        ).scalar() or 0

        # Get tier distribution
        tier_distribution = []
        tiers_with_counts = db.session.query(
            MembershipTier.name,
            func.count(Member.id).label('count')
        ).outerjoin(
            Member, and_(
                Member.tier_id == MembershipTier.id,
                Member.tenant_id == tenant_id
            )
        ).filter(
            MembershipTier.tenant_id == tenant_id,
            MembershipTier.is_active == True
        ).group_by(MembershipTier.id, MembershipTier.name).all()

        for tier_name, count in tiers_with_counts:
            percentage = (count / total_members * 100) if total_members > 0 else 0
            tier_distribution.append({
                'tier_name': tier_name,
                'member_count': count,
                'percentage': round(percentage, 1),
                'color': '#5C6AC4'  # Shopify purple
            })

        # Get top members by trade-in activity
        top_members = db.session.query(
            Member.id,
            Member.member_number,
            func.coalesce(Member.name, '').label('member_name'),
            func.count(TradeInBatch.id).label('trade_in_count'),
            func.coalesce(func.sum(TradeInBatch.total_trade_value), 0).label('total_credit')
        ).outerjoin(
            TradeInBatch, TradeInBatch.member_id == Member.id
        ).filter(
            Member.tenant_id == tenant_id
        ).group_by(
            Member.id, Member.member_number, Member.name
        ).order_by(
            func.count(TradeInBatch.id).desc()
        ).limit(10).all()

        top_members_list = []
        for m in top_members:
            # Count referrals for this member
            referral_count = db.session.query(func.count(Member.id)).filter(
                Member.referred_by_id == m.id
            ).scalar() or 0

            top_members_list.append({
                'id': m.id,
                'member_number': m.member_number,
                'name': m.member_name or m.member_number,
                'total_trade_ins': m.trade_in_count,
                'total_credit_earned': float(m.total_credit),
                'referral_count': referral_count
            })

        # Get category performance (top categories by trade-in count)
        category_performance = db.session.query(
            TradeInBatch.category,
            func.count(TradeInItem.id).label('item_count'),
            func.coalesce(func.sum(TradeInItem.trade_value), 0).label('total_value')
        ).join(
            TradeInItem, TradeInItem.batch_id == TradeInBatch.id
        ).join(
            Member, Member.id == TradeInBatch.member_id
        ).filter(
            Member.tenant_id == tenant_id,
            TradeInBatch.category.isnot(None)
        ).group_by(
            TradeInBatch.category
        ).order_by(
            func.count(TradeInItem.id).desc()
        ).limit(5).all()

        category_list = []
        for cat in category_performance:
            avg_value = float(cat.total_value) / cat.item_count if cat.item_count > 0 else 0
            category_list.append({
                'category_name': cat.category or 'Uncategorized',
                'trade_in_count': cat.item_count,
                'total_value': float(cat.total_value),
                'avg_value': avg_value
            })

        # Calculate monthly trends (last 6 months)
        monthly_trends = []
        for i in range(5, -1, -1):
            # Calculate month start/end
            month_end = datetime.utcnow().replace(day=1) - timedelta(days=1)
            for _ in range(i):
                month_end = month_end.replace(day=1) - timedelta(days=1)
            month_start = month_end.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

            # Count members added this month
            members_added = db.session.query(func.count(Member.id)).filter(
                Member.tenant_id == tenant_id,
                Member.created_at >= month_start,
                Member.created_at <= month_end
            ).scalar() or 0

            # Count trade-ins this month
            trade_ins_count = db.session.query(func.count(TradeInBatch.id)).join(
                Member, Member.id == TradeInBatch.member_id
            ).filter(
                Member.tenant_id == tenant_id,
                TradeInBatch.created_at >= month_start,
                TradeInBatch.created_at <= month_end
            ).scalar() or 0

            # Sum credit issued this month
            credit_issued = db.session.query(
                func.coalesce(func.sum(StoreCreditLedger.amount), 0)
            ).join(
                Member, Member.id == StoreCreditLedger.member_id
            ).filter(
                Member.tenant_id == tenant_id,
                StoreCreditLedger.amount > 0,
                StoreCreditLedger.created_at >= month_start,
                StoreCreditLedger.created_at <= month_end
            ).scalar() or 0

            monthly_trends.append({
                'month': month_start.strftime('%b %Y'),
                'month_start': month_start.isoformat(),
                'new_members': members_added,
                'trade_ins': trade_ins_count,
                'credit_issued': float(credit_issued)
            })

        return jsonify({
            'overview': {
                'total_members': total_members,
                'active_members': active_members,
                'new_members_this_month': new_members_this_period,
                'member_growth_pct': round(member_growth_pct, 1),
                'total_trade_ins': total_trade_ins,
                'trade_ins_this_month': trade_ins_this_period,
                'trade_in_value_this_month': float(trade_in_value_this_period),
                'total_store_credit_issued': float(total_credit_issued),
                'store_credit_this_month': float(credit_this_period),
                'total_referrals': total_referrals,
                'referrals_this_month': referrals_this_period
            },
            'tier_distribution': tier_distribution,
            'top_members': top_members_list,
            'category_performance': category_list,
            'monthly_trends': monthly_trends
        })

    except Exception as e:
        logger.error(f"Dashboard analytics error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== EXPORT ENDPOINT ====================

@analytics_bp.route('/export', methods=['GET'])
@require_shopify_auth
def export_analytics():
    """
    Export analytics data as CSV.

    Query params:
        type: 'members', 'trade_ins', 'credits', 'points', 'rewards', 'summary'
        period: '7', '30', '90', '365', 'all'
    """
    tenant_id = g.tenant_id
    export_type = request.args.get('type', 'summary')
    period = request.args.get('period', '30')

    # Calculate date range
    end_date = datetime.utcnow()
    if period == 'all':
        start_date = datetime(2000, 1, 1)
    else:
        days = int(period)
        start_date = end_date - timedelta(days=days)

    try:
        output = io.StringIO()
        writer = csv.writer(output)

        if export_type == 'members':
            writer.writerow(['Member Number', 'Name', 'Email', 'Tier', 'Status', 'Points Balance', 'Trade-Ins', 'Total Credit', 'Joined'])
            members = Member.query.filter(
                Member.tenant_id == tenant_id,
                Member.created_at >= start_date
            ).all()
            for m in members:
                tier_name = m.tier.name if m.tier else 'None'
                writer.writerow([
                    m.member_number,
                    m.name or m.email,
                    m.email,
                    tier_name,
                    m.status,
                    m.points_balance or 0,
                    m.total_trade_ins or 0,
                    float(m.total_bonus_earned or 0),
                    m.created_at.strftime('%Y-%m-%d') if m.created_at else ''
                ])
            filename = f'members_export_{datetime.utcnow().strftime("%Y%m%d")}.csv'

        elif export_type == 'trade_ins':
            writer.writerow(['Reference', 'Member', 'Category', 'Items', 'Trade Value', 'Status', 'Created'])
            batches = TradeInBatch.query.join(
                Member, Member.id == TradeInBatch.member_id
            ).filter(
                Member.tenant_id == tenant_id,
                TradeInBatch.created_at >= start_date
            ).order_by(TradeInBatch.created_at.desc()).all()
            for b in batches:
                member_name = b.member.member_number if b.member else 'Unknown'
                writer.writerow([
                    b.batch_reference,
                    member_name,
                    b.category or 'General',
                    b.total_items or 0,
                    float(b.total_trade_value or 0),
                    b.status,
                    b.created_at.strftime('%Y-%m-%d %H:%M') if b.created_at else ''
                ])
            filename = f'trade_ins_export_{datetime.utcnow().strftime("%Y%m%d")}.csv'

        elif export_type == 'credits':
            writer.writerow(['Date', 'Member', 'Amount', 'Type', 'Description', 'Balance After'])
            ledger = StoreCreditLedger.query.join(
                Member, Member.id == StoreCreditLedger.member_id
            ).filter(
                Member.tenant_id == tenant_id,
                StoreCreditLedger.created_at >= start_date
            ).order_by(StoreCreditLedger.created_at.desc()).all()
            for entry in ledger:
                member_num = entry.member.member_number if entry.member else 'Unknown'
                writer.writerow([
                    entry.created_at.strftime('%Y-%m-%d %H:%M') if entry.created_at else '',
                    member_num,
                    float(entry.amount),
                    entry.source_type or 'manual',
                    entry.description or '',
                    float(entry.balance_after or 0)
                ])
            filename = f'credits_export_{datetime.utcnow().strftime("%Y%m%d")}.csv'

        elif export_type == 'points':
            writer.writerow(['Date', 'Member', 'Points', 'Type', 'Source', 'Description', 'Balance After'])
            ledger = PointsLedger.query.join(
                Member, Member.id == PointsLedger.member_id
            ).filter(
                Member.tenant_id == tenant_id,
                PointsLedger.created_at >= start_date
            ).order_by(PointsLedger.created_at.desc()).all()
            for entry in ledger:
                member_num = entry.member.member_number if entry.member else 'Unknown'
                writer.writerow([
                    entry.created_at.strftime('%Y-%m-%d %H:%M') if entry.created_at else '',
                    member_num,
                    entry.points,
                    entry.transaction_type,
                    entry.source or '',
                    entry.description or '',
                    entry.balance_after or 0
                ])
            filename = f'points_export_{datetime.utcnow().strftime("%Y%m%d")}.csv'

        elif export_type == 'rewards':
            writer.writerow(['Date', 'Member', 'Reward', 'Type', 'Points Spent', 'Value', 'Status'])
            redemptions = RewardRedemption.query.join(
                Member, Member.id == RewardRedemption.member_id
            ).filter(
                Member.tenant_id == tenant_id,
                RewardRedemption.created_at >= start_date
            ).order_by(RewardRedemption.created_at.desc()).all()
            for r in redemptions:
                member_num = r.member.member_number if r.member else 'Unknown'
                writer.writerow([
                    r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
                    member_num,
                    r.reward_name,
                    r.reward_type,
                    r.points_spent,
                    float(r.reward_value or 0),
                    r.status
                ])
            filename = f'rewards_export_{datetime.utcnow().strftime("%Y%m%d")}.csv'

        else:  # summary
            writer.writerow(['Metric', 'Value'])

            total_members = db.session.query(func.count(Member.id)).filter(
                Member.tenant_id == tenant_id
            ).scalar() or 0
            writer.writerow(['Total Members', total_members])

            active_members = db.session.query(func.count(Member.id)).filter(
                Member.tenant_id == tenant_id,
                Member.status == 'active'
            ).scalar() or 0
            writer.writerow(['Active Members', active_members])

            total_trade_ins = db.session.query(func.count(TradeInBatch.id)).join(
                Member, Member.id == TradeInBatch.member_id
            ).filter(
                Member.tenant_id == tenant_id
            ).scalar() or 0
            writer.writerow(['Total Trade-Ins', total_trade_ins])

            total_credit = db.session.query(
                func.coalesce(func.sum(StoreCreditLedger.amount), 0)
            ).join(
                Member, Member.id == StoreCreditLedger.member_id
            ).filter(
                Member.tenant_id == tenant_id,
                StoreCreditLedger.amount > 0
            ).scalar() or 0
            writer.writerow(['Total Credit Issued', f'${float(total_credit):.2f}'])

            total_points = db.session.query(
                func.coalesce(func.sum(PointsLedger.points), 0)
            ).join(Member).filter(
                Member.tenant_id == tenant_id,
                PointsLedger.transaction_type == 'earn'
            ).scalar() or 0
            writer.writerow(['Total Points Issued', int(total_points)])

            total_redemptions = db.session.query(func.count(RewardRedemption.id)).join(
                Member
            ).filter(
                Member.tenant_id == tenant_id,
                RewardRedemption.status == 'completed'
            ).scalar() or 0
            writer.writerow(['Total Reward Redemptions', total_redemptions])

            writer.writerow(['Export Date', datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')])
            writer.writerow(['Period', f'Last {period} days' if period != 'all' else 'All time'])

            filename = f'summary_export_{datetime.utcnow().strftime("%Y%m%d")}.csv'

        # Return CSV response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )

    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# WEB PIXEL ENDPOINT
# Receives events from the TradeUp Web Pixel extension
# ============================================================

# Valid event types from the pixel
VALID_PIXEL_EVENTS = {
    'tradeup_points_earned',
    'tradeup_checkout_started',
    'tradeup_reward_viewed',
    'tradeup_reward_redeemed',
    'tradeup_tier_displayed',
    'tradeup_referral_shared',
    'tradeup_member_enrolled',
    'tradeup_trade_in_product_viewed',
    'tradeup_cart_add',
}


@analytics_bp.route('/pixel', methods=['POST', 'OPTIONS'])
def receive_pixel_event():
    """
    Receive analytics events from the TradeUp Web Pixel.

    This endpoint is intentionally lightweight and fast.
    It accepts events via POST (JSON or sendBeacon blob) and
    logs them for later processing.

    No authentication required - events come from storefront.
    Rate limiting and validation prevent abuse.
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'ok': True})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '86400'
        return response, 200

    try:
        # Parse event data (handles both JSON and sendBeacon blobs)
        if request.is_json:
            data = request.get_json(silent=True) or {}
        else:
            # sendBeacon sends as text/plain blob
            try:
                import json
                data = json.loads(request.data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                data = {}

        if not data:
            return _pixel_response({'error': 'No data'}, 400)

        # Validate event type
        event_type = data.get('event', '')
        if event_type not in VALID_PIXEL_EVENTS:
            logger.warning(f"Invalid pixel event type: {event_type}")
            return _pixel_response({'error': 'Invalid event'}, 400)

        # Validate shop domain
        shop = data.get('shop', '')
        if not shop or not shop.endswith('.myshopify.com'):
            logger.warning(f"Invalid shop domain in pixel event: {shop}")
            return _pixel_response({'error': 'Invalid shop'}, 400)

        # Look up tenant
        tenant = Tenant.query.filter_by(shop_domain=shop).first()
        if not tenant:
            # Shop not found - could be new install, log but don't error
            logger.info(f"Pixel event from unknown shop: {shop}")
            return _pixel_response({'ok': True, 'processed': False})

        # Log the event for processing
        _process_pixel_event(tenant.id, event_type, data)

        return _pixel_response({'ok': True, 'processed': True})

    except Exception as e:
        logger.error(f"Pixel event error: {str(e)}")
        # Always return 200 to prevent retries - analytics should never break
        return _pixel_response({'ok': True, 'error': 'internal'})


def _pixel_response(data, status=200):
    """Helper to create CORS-enabled response for pixel endpoint."""
    response = jsonify(data)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-store'
    return response, status


def _process_pixel_event(tenant_id, event_type, data):
    """
    Process a pixel event.

    Currently logs to database/file. In production, consider:
    - Writing to Redis for real-time dashboards
    - Queuing to SQS/RabbitMQ for batch processing
    - Streaming to analytics warehouse (BigQuery, Redshift)
    """
    logger.info(f"Pixel event [{tenant_id}] {event_type}: {data.get('customer_id', 'anon')}")

    # Extract key metrics for aggregate tracking
    if event_type == 'tradeup_points_earned':
        _track_points_earned(tenant_id, data)
    elif event_type == 'tradeup_reward_redeemed':
        _track_reward_redeemed(tenant_id, data)
    elif event_type == 'tradeup_referral_shared':
        _track_referral_shared(tenant_id, data)


def _track_points_earned(tenant_id, data):
    """Track points earned event for ROI measurement."""
    try:
        order_value = float(data.get('order_value', 0))
        points_earned = int(data.get('points_earned', 0))
        member_id = data.get('member_id')

        if member_id:
            member = Member.query.filter_by(
                tenant_id=tenant_id,
                shopify_customer_id=data.get('customer_id')
            ).first()

            if member:
                logger.debug(f"Points earned tracked for member {member.id}: {points_earned}")

        logger.info(
            f"PIXEL_POINTS_EARNED tenant={tenant_id} "
            f"order_value={order_value} points={points_earned} "
            f"is_member={bool(member_id)}"
        )
    except Exception as e:
        logger.error(f"Error tracking points earned: {e}")


def _track_reward_redeemed(tenant_id, data):
    """Track reward redemption for conversion measurement."""
    try:
        reward_id = data.get('reward_id')
        points_spent = int(data.get('points_spent', 0))
        reward_value = float(data.get('reward_value', 0))

        logger.info(
            f"PIXEL_REWARD_REDEEMED tenant={tenant_id} "
            f"reward_id={reward_id} points_spent={points_spent} "
            f"value={reward_value}"
        )
    except Exception as e:
        logger.error(f"Error tracking reward redeemed: {e}")


def _track_referral_shared(tenant_id, data):
    """Track referral shares for viral coefficient measurement."""
    try:
        share_method = data.get('share_method', 'unknown')
        referral_code = data.get('referral_code')

        logger.info(
            f"PIXEL_REFERRAL_SHARED tenant={tenant_id} "
            f"method={share_method} code={referral_code}"
        )
    except Exception as e:
        logger.error(f"Error tracking referral shared: {e}")
