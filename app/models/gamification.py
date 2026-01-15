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
