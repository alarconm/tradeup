"""
Referral Program models.
Tracks referrals between members and program configuration.
"""
from datetime import datetime
from decimal import Decimal
from ..extensions import db


class ReferralProgram(db.Model):
    """
    Referral program configuration for a tenant.
    Each tenant can have one active referral program.
    """
    __tablename__ = 'referral_programs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, unique=True)

    # Rewards configuration
    referrer_reward_amount = db.Column(db.Numeric(10, 2), default=10.00)  # $10 for referrer
    referee_reward_amount = db.Column(db.Numeric(10, 2), default=5.00)   # $5 for new member

    # When to grant rewards
    grant_on = db.Column(db.String(20), default='signup')  # 'signup', 'first_purchase', 'first_trade_in'

    # Limits
    monthly_referral_limit = db.Column(db.Integer, default=50)  # Max referrals per member per month

    # Credit expiration
    credit_expiration_days = db.Column(db.Integer)  # null = no expiration

    # Status
    is_active = db.Column(db.Boolean, default=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    referrals = db.relationship('Referral', backref='program', lazy='dynamic')

    def __repr__(self):
        return f'<ReferralProgram tenant={self.tenant_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'referrer_reward_amount': float(self.referrer_reward_amount),
            'referee_reward_amount': float(self.referee_reward_amount),
            'grant_on': self.grant_on,
            'monthly_referral_limit': self.monthly_referral_limit,
            'credit_expiration_days': self.credit_expiration_days,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Referral(db.Model):
    """
    Individual referral record.
    Tracks who referred whom and reward status.
    """
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('referral_programs.id'), nullable=False)

    # Referrer (existing member who made the referral)
    referrer_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)

    # Referee (new member who was referred)
    referee_id = db.Column(db.Integer, db.ForeignKey('members.id'))
    referee_email = db.Column(db.String(255))  # Email before they sign up

    # Referral code used
    referral_code = db.Column(db.String(50), nullable=False)

    # Status tracking
    status = db.Column(db.String(20), default='pending')  # pending, completed, expired, cancelled

    # Reward tracking
    referrer_reward_issued = db.Column(db.Boolean, default=False)
    referee_reward_issued = db.Column(db.Boolean, default=False)
    referrer_reward_amount = db.Column(db.Numeric(10, 2))
    referee_reward_amount = db.Column(db.Numeric(10, 2))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    reward_issued_at = db.Column(db.DateTime)

    # Relationships
    referrer = db.relationship('Member', foreign_keys=[referrer_id], backref='referrals_made')
    referee = db.relationship('Member', foreign_keys=[referee_id], backref='referral_received')

    def __repr__(self):
        return f'<Referral {self.referral_code} by member={self.referrer_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'program_id': self.program_id,
            'referrer_id': self.referrer_id,
            'referee_id': self.referee_id,
            'referee_email': self.referee_email,
            'referral_code': self.referral_code,
            'status': self.status,
            'referrer_reward_issued': self.referrer_reward_issued,
            'referee_reward_issued': self.referee_reward_issued,
            'referrer_reward_amount': float(self.referrer_reward_amount) if self.referrer_reward_amount else None,
            'referee_reward_amount': float(self.referee_reward_amount) if self.referee_reward_amount else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'reward_issued_at': self.reward_issued_at.isoformat() if self.reward_issued_at else None,
        }
