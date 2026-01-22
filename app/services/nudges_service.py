"""
Nudges & Reminders Service

Automated notifications to engage members:
- Points expiring soon
- Tier upgrade proximity
- Re-engagement after inactivity
- Special offers based on behavior
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from app import db
from app.models.member import Member
from app.models.loyalty_points import PointsLedger, PointsBalance
from app.models.nudge_config import NudgeConfig, NudgeType


class NudgesService:
    """Service for managing member nudges and reminders."""

    def __init__(self, tenant_id: int, settings: Optional[Dict] = None):
        self.tenant_id = tenant_id
        self.settings = settings or {}

    def get_nudge_settings(self) -> Dict[str, Any]:
        """
        Get nudge settings for the tenant.

        First checks NudgeConfig database records, then falls back to tenant settings JSON.
        """
        # Try to get settings from NudgeConfig database records
        configs = NudgeConfig.get_all_for_tenant(self.tenant_id)

        if configs:
            # Build settings from database configs
            settings = {
                'enabled': any(c.is_enabled for c in configs),
                'configs': {c.nudge_type: c.to_dict() for c in configs},
            }

            # Extract specific config options for backwards compatibility
            for config in configs:
                if config.nudge_type == NudgeType.POINTS_EXPIRING.value:
                    settings['points_expiry_days'] = config.config_options.get('threshold_days', [30, 7, 1])
                elif config.nudge_type == NudgeType.TIER_PROGRESS.value:
                    settings['tier_upgrade_threshold'] = config.config_options.get('threshold_percent', 0.9)
                elif config.nudge_type == NudgeType.INACTIVE_REMINDER.value:
                    settings['inactive_days'] = config.config_options.get('inactive_days', 30)
                elif config.nudge_type == NudgeType.TRADE_IN_REMINDER.value:
                    settings['trade_in_reminder_days'] = config.config_options.get('min_days_since_last', 60)

            # Add defaults for any missing keys
            settings.setdefault('points_expiry_days', [30, 7, 1])
            settings.setdefault('tier_upgrade_threshold', 0.9)
            settings.setdefault('inactive_days', 30)
            settings.setdefault('welcome_reminder_days', 3)
            settings.setdefault('points_milestones', [100, 500, 1000, 5000])
            settings.setdefault('email_enabled', True)
            settings.setdefault('max_nudges_per_day', 1)

            return settings

        # Fall back to tenant settings JSON (legacy)
        nudge_settings = self.settings.get('nudges', {})
        return {
            'enabled': nudge_settings.get('enabled', True),
            'points_expiry_days': nudge_settings.get('points_expiry_days', [30, 7, 1]),
            'tier_upgrade_threshold': nudge_settings.get('tier_upgrade_threshold', 0.9),  # 90% to next tier
            'inactive_days': nudge_settings.get('inactive_days', 30),
            'welcome_reminder_days': nudge_settings.get('welcome_reminder_days', 3),
            'points_milestones': nudge_settings.get('points_milestones', [100, 500, 1000, 5000]),
            'email_enabled': nudge_settings.get('email_enabled', True),
            'max_nudges_per_day': nudge_settings.get('max_nudges_per_day', 1),
        }

    def get_nudge_config(self, nudge_type: str) -> Optional[NudgeConfig]:
        """Get a specific nudge configuration by type."""
        return NudgeConfig.get_by_type(self.tenant_id, nudge_type)

    def get_all_nudge_configs(self) -> List[NudgeConfig]:
        """Get all nudge configurations for the tenant."""
        return NudgeConfig.get_all_for_tenant(self.tenant_id)

    def is_nudge_enabled(self, nudge_type: str) -> bool:
        """Check if a specific nudge type is enabled."""
        config = self.get_nudge_config(nudge_type)
        if config:
            return config.is_enabled
        # Fall back to legacy settings
        return self.settings.get('nudges', {}).get('enabled', True)

    def get_members_with_expiring_points(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Get members with points expiring within N days."""
        expiry_date = datetime.utcnow() + timedelta(days=days_ahead)

        # Find points ledger entries expiring soon
        expiring_entries = PointsLedger.query.filter(
            PointsLedger.tenant_id == self.tenant_id,
            PointsLedger.expires_at.isnot(None),
            PointsLedger.expires_at <= expiry_date,
            PointsLedger.expires_at > datetime.utcnow(),
            PointsLedger.expired == False,
            PointsLedger.remaining_points > 0
        ).all()

        # Group by member
        member_points = {}
        for entry in expiring_entries:
            if entry.member_id not in member_points:
                member_points[entry.member_id] = {
                    'total_expiring': 0,
                    'earliest_expiry': None,
                    'entries': []
                }

            member_points[entry.member_id]['total_expiring'] += entry.remaining_points or entry.points
            member_points[entry.member_id]['entries'].append(entry)

            entry_expiry = entry.expires_at
            if member_points[entry.member_id]['earliest_expiry'] is None or entry_expiry < member_points[entry.member_id]['earliest_expiry']:
                member_points[entry.member_id]['earliest_expiry'] = entry_expiry

        # Build result list
        results = []
        for member_id, data in member_points.items():
            member = Member.query.get(member_id)
            if member and member.status == 'active':
                days_until = (data['earliest_expiry'] - datetime.utcnow()).days
                results.append({
                    'member': member.to_dict(),
                    'expiring_points': data['total_expiring'],
                    'earliest_expiry': data['earliest_expiry'].isoformat(),
                    'days_until_expiry': days_until,
                    'nudge_type': NudgeType.POINTS_EXPIRING.value,
                })

        # Sort by days until expiry (most urgent first)
        results.sort(key=lambda x: x['days_until_expiry'])
        return results

    def get_members_near_tier_upgrade(self, threshold: float = 0.9) -> List[Dict[str, Any]]:
        """
        Get members who are close to upgrading to the next tier.
        threshold = 0.9 means within 90% of required points/spend.
        """
        from app.models.member import MembershipTier

        # Get all tiers ordered by some criteria (e.g., bonus_rate or monthly_price)
        tiers = MembershipTier.query.filter_by(
            tenant_id=self.tenant_id,
            is_active=True
        ).order_by(MembershipTier.monthly_price.asc()).all()

        if len(tiers) < 2:
            return []  # Need at least 2 tiers for upgrades

        # Create tier progression map
        tier_progression = {}
        for i, tier in enumerate(tiers[:-1]):
            tier_progression[tier.id] = tiers[i + 1]

        results = []
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        for member in members:
            if not member.tier_id or member.tier_id not in tier_progression:
                continue

            next_tier = tier_progression[member.tier_id]

            # Check if member is near upgrade based on lifetime points
            # This is simplified - could be based on spend, trade-ins, etc.
            current_points = member.lifetime_points_earned or 0

            # Define tier thresholds based on tier benefits
            # In a real implementation, this would be configurable per tier
            tier_point_thresholds = {
                'silver': 0,
                'gold': 1000,
                'platinum': 5000,
            }

            next_tier_name = next_tier.name.lower()
            if next_tier_name in tier_point_thresholds:
                required_points = tier_point_thresholds[next_tier_name]
                if required_points > 0:
                    progress = current_points / required_points
                    if progress >= threshold and progress < 1.0:
                        points_needed = required_points - current_points
                        results.append({
                            'member': member.to_dict(),
                            'current_tier': member.tier.to_dict() if member.tier else None,
                            'next_tier': next_tier.to_dict(),
                            'progress_percent': round(progress * 100, 1),
                            'points_needed': points_needed,
                            'nudge_type': NudgeType.TIER_UPGRADE_NEAR.value,
                        })

        # Sort by progress (highest first)
        results.sort(key=lambda x: x['progress_percent'], reverse=True)
        return results

    def get_inactive_members(self, days_inactive: int = 30) -> List[Dict[str, Any]]:
        """Get members who haven't been active for N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

        # Find members with no recent activity
        inactive_members = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.status == 'active',
            Member.updated_at < cutoff_date
        ).all()

        results = []
        for member in inactive_members:
            days_since_activity = (datetime.utcnow() - (member.updated_at or member.created_at)).days
            results.append({
                'member': member.to_dict(),
                'days_inactive': days_since_activity,
                'last_activity': member.updated_at.isoformat() if member.updated_at else None,
                'nudge_type': NudgeType.INACTIVE_MEMBER.value,
            })

        # Sort by days inactive (longest first)
        results.sort(key=lambda x: x['days_inactive'], reverse=True)
        return results

    def get_members_at_points_milestone(self) -> List[Dict[str, Any]]:
        """Get members who recently crossed a points milestone."""
        settings = self.get_nudge_settings()
        milestones = settings['points_milestones']

        results = []
        members = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.status == 'active',
            Member.lifetime_points_earned > 0
        ).all()

        for member in members:
            points = member.lifetime_points_earned or 0
            for milestone in milestones:
                # Check if member just crossed this milestone (within last update)
                if points >= milestone and points < milestone * 1.1:  # Within 10% above milestone
                    results.append({
                        'member': member.to_dict(),
                        'milestone': milestone,
                        'current_points': points,
                        'nudge_type': NudgeType.POINTS_MILESTONE.value,
                    })
                    break  # Only count highest applicable milestone

        return results

    def get_all_pending_nudges(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all pending nudges grouped by type."""
        settings = self.get_nudge_settings()

        if not settings['enabled']:
            return {'error': 'Nudges are disabled', 'nudges': {}}

        nudges = {
            'points_expiring': self.get_members_with_expiring_points(days_ahead=30),
            'tier_upgrade_near': self.get_members_near_tier_upgrade(
                threshold=settings['tier_upgrade_threshold']
            ),
            'inactive_members': self.get_inactive_members(
                days_inactive=settings['inactive_days']
            ),
            'points_milestones': self.get_members_at_points_milestone(),
        }

        return {
            'success': True,
            'nudges': nudges,
            'total_count': sum(len(n) for n in nudges.values()),
        }

    def get_nudge_stats(self) -> Dict[str, Any]:
        """Get statistics about pending nudges."""
        nudges = self.get_all_pending_nudges()

        if 'error' in nudges:
            return nudges

        return {
            'success': True,
            'stats': {
                'points_expiring': len(nudges['nudges'].get('points_expiring', [])),
                'tier_upgrade_near': len(nudges['nudges'].get('tier_upgrade_near', [])),
                'inactive_members': len(nudges['nudges'].get('inactive_members', [])),
                'points_milestones': len(nudges['nudges'].get('points_milestones', [])),
                'total': nudges.get('total_count', 0),
            },
        }

    def get_nudges_for_member(self, member_id: int) -> List[Dict[str, Any]]:
        """Get all applicable nudges for a specific member."""
        member = Member.query.filter_by(
            id=member_id,
            tenant_id=self.tenant_id
        ).first()

        if not member:
            return []

        nudges = []

        # Check points expiring
        expiring = self.get_members_with_expiring_points(days_ahead=30)
        for n in expiring:
            if n['member']['id'] == member_id:
                nudges.append(n)

        # Check tier upgrade proximity
        tier_near = self.get_members_near_tier_upgrade()
        for n in tier_near:
            if n['member']['id'] == member_id:
                nudges.append(n)

        # Check inactivity
        inactive = self.get_inactive_members()
        for n in inactive:
            if n['member']['id'] == member_id:
                nudges.append(n)

        return nudges
