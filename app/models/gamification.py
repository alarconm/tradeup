"""
Gamification Models

Badges, achievements, streaks, and milestones for loyalty engagement.
"""

from datetime import datetime
from app import db


class Badge(db.Model):
    """Badge/achievement definition."""

    __tablename__ = 'badges'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    # Badge info
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    icon = db.Column(db.String(50), default='trophy')  # Icon name from Polaris
    color = db.Column(db.String(20), default='#e85d27')  # Badge color

    # Criteria
    criteria_type = db.Column(db.String(50), nullable=False)
    # Types: first_purchase, trade_in_count, points_earned, referral_count,
    #        tier_reached, streak_days, total_spent, member_anniversary
    criteria_value = db.Column(db.Integer, default=1)  # e.g., 10 trade-ins

    # Rewards
    points_reward = db.Column(db.Integer, default=0)
    credit_reward = db.Column(db.Numeric(10, 2), default=0)

    # Display
    is_active = db.Column(db.Boolean, default=True)
    is_secret = db.Column(db.Boolean, default=False)  # Hidden until earned
    display_order = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('badges', lazy='dynamic'))
    member_badges = db.relationship('MemberBadge', backref='badge', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'color': self.color,
            'criteria_type': self.criteria_type,
            'criteria_value': self.criteria_value,
            'points_reward': self.points_reward,
            'credit_reward': float(self.credit_reward) if self.credit_reward else 0,
            'is_active': self.is_active,
            'is_secret': self.is_secret,
            'display_order': self.display_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MemberBadge(db.Model):
    """Badge earned by a member."""

    __tablename__ = 'member_badges'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badges.id'), nullable=False)

    # When earned
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Progress tracking (for progressive badges)
    progress = db.Column(db.Integer, default=0)
    progress_max = db.Column(db.Integer, default=0)

    # Notification status
    notified = db.Column(db.Boolean, default=False)

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('member_id', 'badge_id', name='unique_member_badge'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'badge_id': self.badge_id,
            'badge': self.badge.to_dict() if self.badge else None,
            'earned_at': self.earned_at.isoformat() if self.earned_at else None,
            'progress': self.progress,
            'progress_max': self.progress_max,
        }


class MemberStreak(db.Model):
    """Activity streak tracking for members."""

    __tablename__ = 'member_streaks'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, unique=True)

    # Current streak
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)

    # Tracking
    last_activity_date = db.Column(db.Date)
    streak_type = db.Column(db.String(50), default='daily')  # daily, weekly, monthly

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'current_streak': self.current_streak,
            'longest_streak': self.longest_streak,
            'last_activity_date': self.last_activity_date.isoformat() if self.last_activity_date else None,
            'streak_type': self.streak_type,
        }


class Milestone(db.Model):
    """Milestone celebrations (100 points, 1000 points, etc.)."""

    __tablename__ = 'milestones'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    # Milestone definition
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    milestone_type = db.Column(db.String(50), nullable=False)
    # Types: points_earned, trade_ins_completed, referrals_made, total_spent, member_days
    threshold = db.Column(db.Integer, nullable=False)

    # Rewards
    points_reward = db.Column(db.Integer, default=0)
    credit_reward = db.Column(db.Numeric(10, 2), default=0)
    badge_id = db.Column(db.Integer, db.ForeignKey('badges.id'), nullable=True)

    # Display
    celebration_message = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('milestones', lazy='dynamic'))
    badge = db.relationship('Badge', backref='milestone')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'milestone_type': self.milestone_type,
            'threshold': self.threshold,
            'points_reward': self.points_reward,
            'credit_reward': float(self.credit_reward) if self.credit_reward else 0,
            'badge_id': self.badge_id,
            'celebration_message': self.celebration_message,
            'is_active': self.is_active,
        }


class MemberMilestone(db.Model):
    """Milestones achieved by members."""

    __tablename__ = 'member_milestones'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestones.id'), nullable=False)

    achieved_at = db.Column(db.DateTime, default=datetime.utcnow)
    notified = db.Column(db.Boolean, default=False)

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('member_id', 'milestone_id', name='unique_member_milestone'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'milestone_id': self.milestone_id,
            'achieved_at': self.achieved_at.isoformat() if self.achieved_at else None,
        }


class MemberActivity(db.Model):
    """
    General activity log for member events.

    Tracks various member activities including:
    - Anniversary rewards
    - Birthday rewards
    - Badge achievements
    - Milestone completions
    - Tier changes
    - Special promotions
    """

    __tablename__ = 'member_activities'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)

    # Activity type and details
    activity_type = db.Column(db.String(50), nullable=False, index=True)
    # Types: anniversary_reward, birthday_reward, badge_earned, milestone_achieved,
    #        tier_changed, points_earned, credit_issued, referral_completed

    # Activity-specific data
    activity_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    description = db.Column(db.String(500))

    # For anniversary rewards specifically
    anniversary_year = db.Column(db.Integer)  # 1, 2, 3, etc.

    # Reward details (applicable to reward activities)
    reward_type = db.Column(db.String(30))  # points, credit, discount_code
    reward_amount = db.Column(db.Numeric(10, 2))  # Amount of points/credit/discount
    reward_reference = db.Column(db.String(100))  # Reference ID for the reward (ledger entry, transaction, etc.)

    # Related entities
    related_badge_id = db.Column(db.Integer, db.ForeignKey('badges.id'))
    related_milestone_id = db.Column(db.Integer, db.ForeignKey('milestones.id'))
    related_tier_id = db.Column(db.Integer, db.ForeignKey('membership_tiers.id'))

    # Extra data
    activity_data = db.Column(db.JSON, default=dict)  # Additional activity-specific data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('member_activities', lazy='dynamic'))
    member = db.relationship('Member', backref=db.backref('activities', lazy='dynamic'))
    badge = db.relationship('Badge', backref='activity_logs')
    milestone = db.relationship('Milestone', backref='activity_logs')

    # Indexes for common queries
    __table_args__ = (
        db.Index('ix_member_activity_type', 'member_id', 'activity_type'),
        db.Index('ix_member_activity_date', 'member_id', 'activity_date'),
        db.Index('ix_tenant_activity_type', 'tenant_id', 'activity_type'),
    )

    def __repr__(self):
        return f'<MemberActivity {self.id}: {self.activity_type} for member {self.member_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'activity_type': self.activity_type,
            'activity_date': self.activity_date.isoformat() if self.activity_date else None,
            'description': self.description,
            'anniversary_year': self.anniversary_year,
            'reward_type': self.reward_type,
            'reward_amount': float(self.reward_amount) if self.reward_amount else None,
            'reward_reference': self.reward_reference,
            'related_badge_id': self.related_badge_id,
            'related_milestone_id': self.related_milestone_id,
            'related_tier_id': self.related_tier_id,
            'activity_data': self.activity_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def log_anniversary_reward(
        cls,
        tenant_id: int,
        member_id: int,
        anniversary_year: int,
        reward_type: str,
        reward_amount: float,
        reward_reference: str = None,
        description: str = None,
        badge_id: int = None
    ):
        """
        Log an anniversary reward activity.

        Args:
            tenant_id: Tenant ID
            member_id: Member ID
            anniversary_year: Which anniversary year (1, 2, 3, etc.)
            reward_type: Type of reward (points, credit, discount_code)
            reward_amount: Amount of the reward
            reward_reference: Reference ID for the reward transaction
            description: Optional description override
            badge_id: Optional badge ID if a badge was also awarded

        Returns:
            MemberActivity: The created activity record
        """
        from decimal import Decimal

        if not description:
            ordinal = cls._ordinal(anniversary_year)
            description = f"{ordinal} Anniversary Reward: {reward_type} ({reward_amount})"

        activity = cls(
            tenant_id=tenant_id,
            member_id=member_id,
            activity_type='anniversary_reward',
            description=description,
            anniversary_year=anniversary_year,
            reward_type=reward_type,
            reward_amount=Decimal(str(reward_amount)),
            reward_reference=reward_reference,
            related_badge_id=badge_id,
            activity_data={
                'anniversary_year': anniversary_year,
                'reward_type': reward_type,
                'reward_amount': reward_amount,
            }
        )
        db.session.add(activity)
        return activity

    @classmethod
    def get_member_anniversary_history(cls, member_id: int, limit: int = 50):
        """
        Get anniversary reward history for a member.

        Args:
            member_id: Member ID
            limit: Maximum number of records to return

        Returns:
            List of MemberActivity records for anniversary rewards
        """
        return cls.query.filter(
            cls.member_id == member_id,
            cls.activity_type == 'anniversary_reward'
        ).order_by(cls.activity_date.desc()).limit(limit).all()

    @classmethod
    def get_member_activity_history(cls, member_id: int, activity_type: str = None, limit: int = 100):
        """
        Get activity history for a member.

        Args:
            member_id: Member ID
            activity_type: Optional filter by activity type
            limit: Maximum number of records to return

        Returns:
            List of MemberActivity records
        """
        query = cls.query.filter(cls.member_id == member_id)
        if activity_type:
            query = query.filter(cls.activity_type == activity_type)
        return query.order_by(cls.activity_date.desc()).limit(limit).all()

    @staticmethod
    def _ordinal(n: int) -> str:
        """Convert number to ordinal (1st, 2nd, 3rd, etc.)."""
        if 11 <= (n % 100) <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f"{n}{suffix}"
