"""
Gamification Service

Handles badges, achievements, streaks, and milestones.
Automatically awards badges based on member activity.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import func

from app import db
from app.models.gamification import Badge, MemberBadge, MemberStreak, Milestone, MemberMilestone
from app.models.member import Member
from app.models.trade_in import TradeInBatch
from app.models.loyalty_points import PointsLedger


class GamificationService:
    """Service for gamification features."""

    # Default badge definitions for new tenants
    DEFAULT_BADGES = [
        {
            'name': 'First Purchase',
            'description': 'Made your first purchase',
            'icon': 'cart',
            'criteria_type': 'first_purchase',
            'criteria_value': 1,
            'points_reward': 50,
        },
        {
            'name': 'Trade-In Rookie',
            'description': 'Completed your first trade-in',
            'icon': 'exchange',
            'criteria_type': 'trade_in_count',
            'criteria_value': 1,
            'points_reward': 100,
        },
        {
            'name': 'Trade-In Pro',
            'description': 'Completed 10 trade-ins',
            'icon': 'star',
            'criteria_type': 'trade_in_count',
            'criteria_value': 10,
            'points_reward': 500,
        },
        {
            'name': 'Trade-In Master',
            'description': 'Completed 50 trade-ins',
            'icon': 'trophy',
            'criteria_type': 'trade_in_count',
            'criteria_value': 50,
            'points_reward': 2000,
        },
        {
            'name': 'Referral Champion',
            'description': 'Referred 5 friends who made purchases',
            'icon': 'users',
            'criteria_type': 'referral_count',
            'criteria_value': 5,
            'points_reward': 1000,
        },
        {
            'name': 'Points Collector',
            'description': 'Earned 1,000 total points',
            'icon': 'coins',
            'criteria_type': 'points_earned',
            'criteria_value': 1000,
            'points_reward': 100,
        },
        {
            'name': 'Points Master',
            'description': 'Earned 10,000 total points',
            'icon': 'gem',
            'criteria_type': 'points_earned',
            'criteria_value': 10000,
            'points_reward': 500,
        },
        {
            'name': '1 Year Member',
            'description': 'Been a loyal member for 1 year',
            'icon': 'calendar',
            'criteria_type': 'member_anniversary',
            'criteria_value': 365,
            'points_reward': 1000,
        },
        {
            'name': '2 Year Member',
            'description': 'Been a loyal member for 2 years',
            'icon': 'calendar',
            'color': '#C0C0C0',
            'criteria_type': 'member_anniversary',
            'criteria_value': 730,
            'points_reward': 2000,
        },
        {
            'name': '5 Year Member',
            'description': 'A truly loyal customer - 5 years!',
            'icon': 'heart',
            'color': '#FFD700',
            'criteria_type': 'member_anniversary',
            'criteria_value': 1825,
            'points_reward': 5000,
        },
        {
            'name': 'Weekly Warrior',
            'description': 'Maintained a 7-day activity streak',
            'icon': 'flame',
            'criteria_type': 'streak_days',
            'criteria_value': 7,
            'points_reward': 200,
        },
        {
            'name': 'Monthly Maven',
            'description': 'Maintained a 30-day activity streak',
            'icon': 'fire',
            'criteria_type': 'streak_days',
            'criteria_value': 30,
            'points_reward': 1000,
        },
        {
            'name': 'Silver Status',
            'description': 'Reached Silver tier',
            'icon': 'medal',
            'color': '#C0C0C0',
            'criteria_type': 'tier_reached',
            'criteria_value': 2,
            'points_reward': 200,
        },
        {
            'name': 'Gold Status',
            'description': 'Reached Gold tier',
            'icon': 'medal',
            'color': '#FFD700',
            'criteria_type': 'tier_reached',
            'criteria_value': 3,
            'points_reward': 500,
        },
        {
            'name': 'Big Spender',
            'description': 'Spent $500 lifetime',
            'icon': 'wallet',
            'criteria_type': 'total_spent',
            'criteria_value': 500,
            'points_reward': 250,
        },
        {
            'name': 'VIP Collector',
            'description': 'Spent $2,000 lifetime',
            'icon': 'crown',
            'criteria_type': 'total_spent',
            'criteria_value': 2000,
            'points_reward': 1000,
        },
    ]

    DEFAULT_MILESTONES = [
        {
            'name': '100 Points Club',
            'description': 'Welcome to the club!',
            'milestone_type': 'points_earned',
            'threshold': 100,
            'points_reward': 10,
            'celebration_message': '🎉 You earned 100 points! Keep collecting!',
        },
        {
            'name': '500 Points Club',
            'description': 'You\'re on a roll!',
            'milestone_type': 'points_earned',
            'threshold': 500,
            'points_reward': 50,
            'celebration_message': '🌟 500 points! You\'re a star collector!',
        },
        {
            'name': '1000 Points Club',
            'description': 'Legendary status!',
            'milestone_type': 'points_earned',
            'threshold': 1000,
            'points_reward': 100,
            'celebration_message': '🏆 1,000 points! You\'re legendary!',
        },
        {
            'name': '5 Trade-Ins',
            'description': 'Regular trader',
            'milestone_type': 'trade_ins_completed',
            'threshold': 5,
            'points_reward': 100,
            'celebration_message': '📦 5 trade-ins completed! You\'re a regular!',
        },
        {
            'name': '25 Trade-Ins',
            'description': 'Trade-in expert',
            'milestone_type': 'trade_ins_completed',
            'threshold': 25,
            'points_reward': 500,
            'celebration_message': '🎯 25 trade-ins! You\'re an expert trader!',
        },
    ]

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def initialize_defaults(self) -> Dict[str, Any]:
        """Create default badges and milestones for a new tenant."""
        badges_created = 0
        milestones_created = 0

        # Create default badges
        for badge_data in self.DEFAULT_BADGES:
            existing = Badge.query.filter_by(
                tenant_id=self.tenant_id,
                name=badge_data['name']
            ).first()

            if not existing:
                badge = Badge(
                    tenant_id=self.tenant_id,
                    **badge_data
                )
                db.session.add(badge)
                badges_created += 1

        # Create default milestones
        for milestone_data in self.DEFAULT_MILESTONES:
            existing = Milestone.query.filter_by(
                tenant_id=self.tenant_id,
                name=milestone_data['name']
            ).first()

            if not existing:
                milestone = Milestone(
                    tenant_id=self.tenant_id,
                    **milestone_data
                )
                db.session.add(milestone)
                milestones_created += 1

        db.session.commit()

        return {
            'badges_created': badges_created,
            'milestones_created': milestones_created,
        }

    # Badge Management
    def get_badges(self, include_inactive: bool = False) -> List[Badge]:
        """Get all badges for tenant."""
        query = Badge.query.filter_by(tenant_id=self.tenant_id)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        return query.order_by(Badge.display_order).all()

    def get_badge(self, badge_id: int) -> Optional[Badge]:
        """Get a specific badge."""
        return Badge.query.filter_by(
            id=badge_id,
            tenant_id=self.tenant_id
        ).first()

    def create_badge(self, data: Dict[str, Any]) -> Badge:
        """Create a new badge."""
        badge = Badge(
            tenant_id=self.tenant_id,
            name=data['name'],
            description=data.get('description', ''),
            icon=data.get('icon', 'trophy'),
            color=data.get('color', '#e85d27'),
            criteria_type=data['criteria_type'],
            criteria_value=data.get('criteria_value', 1),
            points_reward=data.get('points_reward', 0),
            credit_reward=data.get('credit_reward', 0),
            is_active=data.get('is_active', True),
            is_secret=data.get('is_secret', False),
            display_order=data.get('display_order', 0),
        )
        db.session.add(badge)
        db.session.commit()
        return badge

    def update_badge(self, badge_id: int, data: Dict[str, Any]) -> Optional[Badge]:
        """Update a badge."""
        badge = self.get_badge(badge_id)
        if not badge:
            return None

        for key, value in data.items():
            if hasattr(badge, key):
                setattr(badge, key, value)

        db.session.commit()
        return badge

    def delete_badge(self, badge_id: int) -> bool:
        """Delete a badge."""
        badge = self.get_badge(badge_id)
        if not badge:
            return False

        db.session.delete(badge)
        db.session.commit()
        return True

    # Member Badge Operations
    def get_member_badges(self, member_id: int) -> List[MemberBadge]:
        """Get all badges earned by a member."""
        return MemberBadge.query.filter_by(member_id=member_id).all()

    def award_badge(self, member_id: int, badge_id: int) -> Optional[MemberBadge]:
        """Manually award a badge to a member."""
        # Check if already earned
        existing = MemberBadge.query.filter_by(
            member_id=member_id,
            badge_id=badge_id
        ).first()

        if existing:
            return existing

        badge = self.get_badge(badge_id)
        if not badge:
            return None

        member_badge = MemberBadge(
            member_id=member_id,
            badge_id=badge_id,
            progress=badge.criteria_value,
            progress_max=badge.criteria_value,
        )
        db.session.add(member_badge)

        # Award rewards
        self._award_badge_rewards(member_id, badge)

        db.session.commit()
        return member_badge

    def _award_badge_rewards(self, member_id: int, badge: Badge):
        """Award points/credit for earning a badge."""
        member = Member.query.get(member_id)
        if not member:
            return

        # Award points
        if badge.points_reward > 0:
            points = PointsLedger(
                tenant_id=self.tenant_id,
                member_id=member_id,
                points=badge.points_reward,
                transaction_type='earn',
                source='badge_earned',
                description=f'Earned badge: {badge.name}',
            )
            db.session.add(points)
            member.points_balance = (member.points_balance or 0) + badge.points_reward

        # Award credit
        if badge.credit_reward and badge.credit_reward > 0:
            member.credit_balance = (member.credit_balance or Decimal('0')) + badge.credit_reward

    def check_and_award_badges(self, member_id: int) -> List[MemberBadge]:
        """Check all badge criteria and award any earned badges."""
        awarded = []
        member = Member.query.get(member_id)
        if not member:
            return awarded

        badges = self.get_badges()
        member_stats = self._get_member_stats(member)

        for badge in badges:
            # Skip if already earned
            existing = MemberBadge.query.filter_by(
                member_id=member_id,
                badge_id=badge.id
            ).first()

            if existing:
                continue

            # Check criteria
            if self._check_badge_criteria(badge, member_stats):
                member_badge = MemberBadge(
                    member_id=member_id,
                    badge_id=badge.id,
                    progress=badge.criteria_value,
                    progress_max=badge.criteria_value,
                )
                db.session.add(member_badge)
                self._award_badge_rewards(member_id, badge)
                awarded.append(member_badge)

        if awarded:
            db.session.commit()

        return awarded

    def _get_member_stats(self, member: Member) -> Dict[str, Any]:
        """Get member statistics for badge checking."""
        # Trade-in count
        trade_in_count = TradeInBatch.query.filter_by(
            member_id=member.id,
            status='completed'
        ).count()

        # Total points earned (all time)
        total_points = db.session.query(func.sum(PointsLedger.points)).filter(
            PointsLedger.member_id == member.id,
            PointsLedger.points > 0
        ).scalar() or 0

        # Member age in days
        member_days = (datetime.utcnow() - member.created_at).days if member.created_at else 0

        # Get streak
        streak = MemberStreak.query.filter_by(member_id=member.id).first()
        current_streak = streak.current_streak if streak else 0

        # Referral count (if referral tracking exists)
        referral_count = getattr(member, 'referral_count', 0) or 0

        # Tier level
        tier_level = getattr(member, 'tier_level', 1) or 1

        # Total spent
        total_spent = float(member.total_spent or 0)

        return {
            'trade_in_count': trade_in_count,
            'total_points': total_points,
            'member_days': member_days,
            'current_streak': current_streak,
            'referral_count': referral_count,
            'tier_level': tier_level,
            'total_spent': total_spent,
            'has_purchase': (member.total_spent or 0) > 0,
        }

    def _check_badge_criteria(self, badge: Badge, stats: Dict[str, Any]) -> bool:
        """Check if member meets badge criteria."""
        criteria_type = badge.criteria_type
        criteria_value = badge.criteria_value

        if criteria_type == 'first_purchase':
            return stats['has_purchase']

        elif criteria_type == 'trade_in_count':
            return stats['trade_in_count'] >= criteria_value

        elif criteria_type == 'points_earned':
            return stats['total_points'] >= criteria_value

        elif criteria_type == 'referral_count':
            return stats['referral_count'] >= criteria_value

        elif criteria_type == 'tier_reached':
            return stats['tier_level'] >= criteria_value

        elif criteria_type == 'streak_days':
            return stats['current_streak'] >= criteria_value

        elif criteria_type == 'member_anniversary':
            return stats['member_days'] >= criteria_value

        elif criteria_type == 'total_spent':
            return stats['total_spent'] >= criteria_value

        return False

    # Streak Management
    def get_member_streak(self, member_id: int) -> Optional[MemberStreak]:
        """Get member's current streak."""
        return MemberStreak.query.filter_by(member_id=member_id).first()

    def update_streak(self, member_id: int) -> MemberStreak:
        """Update member's streak based on activity."""
        streak = MemberStreak.query.filter_by(member_id=member_id).first()
        today = date.today()

        if not streak:
            streak = MemberStreak(
                member_id=member_id,
                current_streak=1,
                longest_streak=1,
                last_activity_date=today,
            )
            db.session.add(streak)
        else:
            if streak.last_activity_date:
                days_since = (today - streak.last_activity_date).days

                if days_since == 0:
                    # Already active today
                    pass
                elif days_since == 1:
                    # Consecutive day - extend streak
                    streak.current_streak += 1
                    if streak.current_streak > streak.longest_streak:
                        streak.longest_streak = streak.current_streak
                else:
                    # Streak broken - reset
                    streak.current_streak = 1

            streak.last_activity_date = today

        db.session.commit()

        # Check for streak badges
        self.check_and_award_badges(member_id)

        return streak

    # Milestone Management
    def get_milestones(self, include_inactive: bool = False) -> List[Milestone]:
        """Get all milestones for tenant."""
        query = Milestone.query.filter_by(tenant_id=self.tenant_id)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        return query.order_by(Milestone.threshold).all()

    def check_milestones(self, member_id: int) -> List[MemberMilestone]:
        """Check and award any milestones achieved."""
        achieved = []
        member = Member.query.get(member_id)
        if not member:
            return achieved

        milestones = self.get_milestones()
        stats = self._get_member_stats(member)

        for milestone in milestones:
            # Skip if already achieved
            existing = MemberMilestone.query.filter_by(
                member_id=member_id,
                milestone_id=milestone.id
            ).first()

            if existing:
                continue

            # Check threshold
            value = self._get_milestone_value(milestone.milestone_type, stats)
            if value >= milestone.threshold:
                member_milestone = MemberMilestone(
                    member_id=member_id,
                    milestone_id=milestone.id,
                )
                db.session.add(member_milestone)

                # Award rewards
                if milestone.points_reward > 0:
                    points = PointsLedger(
                        tenant_id=self.tenant_id,
                        member_id=member_id,
                        points=milestone.points_reward,
                        transaction_type='earn',
                        source='milestone_reached',
                        description=f'Milestone: {milestone.name}',
                    )
                    db.session.add(points)
                    member.points_balance = (member.points_balance or 0) + milestone.points_reward

                if milestone.credit_reward and milestone.credit_reward > 0:
                    member.credit_balance = (member.credit_balance or Decimal('0')) + milestone.credit_reward

                # Award badge if configured
                if milestone.badge_id:
                    self.award_badge(member_id, milestone.badge_id)

                achieved.append(member_milestone)

        if achieved:
            db.session.commit()

        return achieved

    def _get_milestone_value(self, milestone_type: str, stats: Dict[str, Any]) -> int:
        """Get the current value for a milestone type."""
        mapping = {
            'points_earned': 'total_points',
            'trade_ins_completed': 'trade_in_count',
            'referrals_made': 'referral_count',
            'total_spent': 'total_spent',
            'member_days': 'member_days',
        }
        key = mapping.get(milestone_type, milestone_type)
        return stats.get(key, 0)

    # Progress Tracking
    def get_member_progress(self, member_id: int) -> Dict[str, Any]:
        """Get member's progress toward all badges and milestones."""
        member = Member.query.get(member_id)
        if not member:
            return {}

        stats = self._get_member_stats(member)
        earned_badges = {mb.badge_id for mb in self.get_member_badges(member_id)}
        achieved_milestones = {mm.milestone_id for mm in MemberMilestone.query.filter_by(member_id=member_id).all()}

        # Badge progress
        badges_progress = []
        for badge in self.get_badges():
            current = self._get_badge_progress_value(badge.criteria_type, stats)
            badges_progress.append({
                'badge': badge.to_dict(),
                'earned': badge.id in earned_badges,
                'progress': min(current, badge.criteria_value),
                'progress_max': badge.criteria_value,
                'percentage': min(100, int((current / badge.criteria_value) * 100)) if badge.criteria_value > 0 else 0,
            })

        # Milestone progress
        milestones_progress = []
        for milestone in self.get_milestones():
            current = self._get_milestone_value(milestone.milestone_type, stats)
            milestones_progress.append({
                'milestone': milestone.to_dict(),
                'achieved': milestone.id in achieved_milestones,
                'progress': min(current, milestone.threshold),
                'progress_max': milestone.threshold,
                'percentage': min(100, int((current / milestone.threshold) * 100)) if milestone.threshold > 0 else 0,
            })

        # Streak info
        streak = self.get_member_streak(member_id)

        return {
            'badges': badges_progress,
            'milestones': milestones_progress,
            'streak': streak.to_dict() if streak else None,
            'stats': stats,
        }

    def _get_badge_progress_value(self, criteria_type: str, stats: Dict[str, Any]) -> int:
        """Get current progress value for a badge criteria type."""
        mapping = {
            'first_purchase': 1 if stats['has_purchase'] else 0,
            'trade_in_count': stats['trade_in_count'],
            'points_earned': stats['total_points'],
            'referral_count': stats['referral_count'],
            'tier_reached': stats['tier_level'],
            'streak_days': stats['current_streak'],
            'member_anniversary': stats['member_days'],
            'total_spent': int(stats['total_spent']),
        }
        return mapping.get(criteria_type, 0)

    # Notifications
    def get_unnotified_achievements(self, member_id: int) -> Dict[str, Any]:
        """Get achievements that haven't been shown to the member yet."""
        badges = MemberBadge.query.filter_by(
            member_id=member_id,
            notified=False
        ).all()

        milestones = MemberMilestone.query.filter_by(
            member_id=member_id,
            notified=False
        ).all()

        return {
            'badges': [mb.to_dict() for mb in badges],
            'milestones': [mm.to_dict() for mm in milestones],
        }

    def mark_achievements_notified(self, member_id: int):
        """Mark all achievements as notified."""
        MemberBadge.query.filter_by(
            member_id=member_id,
            notified=False
        ).update({'notified': True})

        MemberMilestone.query.filter_by(
            member_id=member_id,
            notified=False
        ).update({'notified': True})

        db.session.commit()

    # Anniversary Badge Integration
    def award_anniversary_badge(self, member_id: int, anniversary_year: int) -> Optional[MemberBadge]:
        """
        Award the appropriate anniversary badge based on membership years.

        This method is called by AnniversaryService when issuing anniversary rewards.
        It awards the corresponding milestone badge (1 Year, 2 Year, or 5 Year Member).

        Args:
            member_id: ID of the member to award badge to
            anniversary_year: The anniversary year (1, 2, 3, 4, 5, etc.)

        Returns:
            MemberBadge if a badge was awarded, None if no matching badge or already earned
        """
        # Map anniversary years to days for criteria matching
        # 1 year = 365 days, 2 years = 730 days, 5 years = 1825 days
        anniversary_days_map = {
            1: 365,
            2: 730,
            5: 1825,
        }

        # Only award badges for milestone years (1, 2, 5)
        if anniversary_year not in anniversary_days_map:
            return None

        target_days = anniversary_days_map[anniversary_year]

        # Find the anniversary badge with matching criteria
        badge = Badge.query.filter_by(
            tenant_id=self.tenant_id,
            criteria_type='member_anniversary',
            criteria_value=target_days,
            is_active=True
        ).first()

        if not badge:
            return None

        # Check if already earned
        existing = MemberBadge.query.filter_by(
            member_id=member_id,
            badge_id=badge.id
        ).first()

        if existing:
            return existing

        # Award the badge
        member_badge = MemberBadge(
            member_id=member_id,
            badge_id=badge.id,
            progress=badge.criteria_value,
            progress_max=badge.criteria_value,
        )
        db.session.add(member_badge)

        # Award badge rewards (points/credit)
        self._award_badge_rewards(member_id, badge)

        db.session.commit()
        return member_badge

    def get_anniversary_badges(self) -> List[Badge]:
        """
        Get all anniversary badges for this tenant.

        Returns:
            List of Badge objects with criteria_type='member_anniversary'
        """
        return Badge.query.filter_by(
            tenant_id=self.tenant_id,
            criteria_type='member_anniversary',
            is_active=True
        ).order_by(Badge.criteria_value).all()
