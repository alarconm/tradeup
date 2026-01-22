"""
Nudges & Reminders Service

Automated notifications to engage members:
- Points expiring soon
- Tier upgrade proximity
- Re-engagement after inactivity
- Special offers based on behavior
"""

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from app import db
from app.models.member import Member
from app.models.loyalty_points import PointsLedger, PointsBalance
from app.models.nudge_config import NudgeConfig, NudgeType
from app.models.nudge_sent import NudgeSent

logger = logging.getLogger(__name__)


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

        # Add trade-in reminders only if trade-ins are enabled
        if self.is_trade_ins_enabled_for_tenant():
            trade_in_reminder_days = settings.get('trade_in_reminder_days', 60)
            nudges['trade_in_reminders'] = self.get_members_needing_trade_in_reminder(
                min_days_since_last=trade_in_reminder_days
            )

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

        stats = {
            'points_expiring': len(nudges['nudges'].get('points_expiring', [])),
            'tier_upgrade_near': len(nudges['nudges'].get('tier_upgrade_near', [])),
            'inactive_members': len(nudges['nudges'].get('inactive_members', [])),
            'points_milestones': len(nudges['nudges'].get('points_milestones', [])),
            'trade_in_reminders': len(nudges['nudges'].get('trade_in_reminders', [])),
            'total': nudges.get('total_count', 0),
        }

        return {
            'success': True,
            'stats': stats,
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

        # Check trade-in reminder (only if trade-ins enabled)
        if self.is_trade_ins_enabled_for_tenant():
            trade_in_reminders = self.get_members_needing_trade_in_reminder()
            for n in trade_in_reminders:
                if n['member']['id'] == member_id:
                    nudges.append(n)

        return nudges

    # ==================== Points Expiring Reminder Methods ====================

    def get_points_expiring_config(self) -> Dict[str, Any]:
        """
        Get configuration for points expiring nudges.

        Returns:
            Dict with: enabled, threshold_days (list), frequency_days (cooldown)
        """
        config = self.get_nudge_config(NudgeType.POINTS_EXPIRING.value)

        if config:
            return {
                'enabled': config.is_enabled,
                'threshold_days': config.config_options.get('threshold_days', [30, 7, 1]),
                'frequency_days': config.frequency_days,
                'message_template': config.message_template,
            }

        # Fall back to defaults
        settings = self.get_nudge_settings()
        return {
            'enabled': settings.get('enabled', True),
            'threshold_days': settings.get('points_expiry_days', [30, 7, 1]),
            'frequency_days': 7,  # Default cooldown: 7 days
            'message_template': None,
        }

    def should_send_points_expiring_reminder(
        self,
        member_id: int,
        cooldown_days: Optional[int] = None
    ) -> bool:
        """
        Check if a points expiring reminder should be sent to this member.

        Checks:
        1. Nudge type is enabled
        2. Member has points expiring within threshold days
        3. No reminder was sent within the cooldown period

        Args:
            member_id: The member ID
            cooldown_days: Override cooldown period (uses config default if not provided)

        Returns:
            True if reminder should be sent, False otherwise
        """
        config = self.get_points_expiring_config()

        # Check if nudge is enabled
        if not config['enabled']:
            return False

        # Use config cooldown if not overridden
        if cooldown_days is None:
            cooldown_days = config['frequency_days']

        # Check if recently sent
        if NudgeSent.was_recently_sent(
            tenant_id=self.tenant_id,
            member_id=member_id,
            nudge_type=NudgeType.POINTS_EXPIRING.value,
            cooldown_days=cooldown_days
        ):
            return False

        # Check if member has expiring points within any threshold
        threshold_days = config['threshold_days']
        max_threshold = max(threshold_days) if threshold_days else 30

        expiring_members = self.get_members_with_expiring_points(days_ahead=max_threshold)
        for data in expiring_members:
            if data['member']['id'] == member_id:
                return True

        return False

    def send_points_expiring_reminder(
        self,
        member_id: int,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Send a points expiring reminder to a specific member.

        Args:
            member_id: The member to send reminder to
            force: Skip cooldown check if True

        Returns:
            Dict with success status and details
        """
        from app.models.tenant import Tenant
        from app.services.email_service import email_service

        member = Member.query.filter_by(
            id=member_id,
            tenant_id=self.tenant_id
        ).first()

        if not member:
            return {'success': False, 'error': 'Member not found'}

        if not member.email:
            return {'success': False, 'error': 'Member has no email address'}

        if member.status != 'active':
            return {'success': False, 'error': 'Member is not active'}

        # Check if we should send (unless forced)
        if not force:
            if not self.should_send_points_expiring_reminder(member_id):
                return {'success': False, 'error': 'Reminder not due (cooldown or no expiring points)'}

        # Get tenant info
        tenant = Tenant.query.get(self.tenant_id)
        if not tenant:
            return {'success': False, 'error': 'Tenant not found'}

        # Get expiring points data
        expiring_data = None
        config = self.get_points_expiring_config()
        max_threshold = max(config['threshold_days']) if config['threshold_days'] else 30

        for data in self.get_members_with_expiring_points(days_ahead=max_threshold):
            if data['member']['id'] == member_id:
                expiring_data = data
                break

        if not expiring_data:
            return {'success': False, 'error': 'No expiring points found for this member'}

        # Get member's current points balance
        points_balance = PointsBalance.query.filter_by(member_id=member_id).first()
        current_balance = points_balance.available_points if points_balance else member.points_balance or 0

        # Build email data
        email_data = {
            'member_name': member.name or member.email.split('@')[0],
            'expiring_points': expiring_data['expiring_points'],
            'expiration_date': datetime.fromisoformat(expiring_data['earliest_expiry']).strftime('%B %d, %Y'),
            'days_until': expiring_data['days_until_expiry'],
            'current_balance': current_balance,
            'shop_name': tenant.shop_name or tenant.shop_domain.split('.')[0].title(),
            'shop_url': f"https://{tenant.shop_domain}",
            'rewards_available': True,  # Could check for available rewards
            'rewards_list': '',  # Could list available rewards
        }

        # Send email
        result = email_service.send_template_email(
            template_key='points_expiring',
            tenant_id=self.tenant_id,
            to_email=member.email,
            to_name=member.name or '',
            data=email_data,
            from_name=email_data['shop_name'],
        )

        # Record the nudge sent
        if result.get('success'):
            NudgeSent.record_sent(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.POINTS_EXPIRING.value,
                context_data={
                    'expiring_points': expiring_data['expiring_points'],
                    'expiration_date': expiring_data['earliest_expiry'],
                    'days_until_expiry': expiring_data['days_until_expiry'],
                },
                delivery_method='email',
            )
            logger.info(f"Points expiring reminder sent to member {member_id} "
                       f"({expiring_data['expiring_points']} points expiring in "
                       f"{expiring_data['days_until_expiry']} days)")
        else:
            logger.warning(f"Failed to send points expiring reminder to member {member_id}: "
                          f"{result.get('error', 'Unknown error')}")

        return {
            'success': result.get('success', False),
            'member_id': member_id,
            'expiring_points': expiring_data['expiring_points'],
            'expiration_date': expiring_data['earliest_expiry'],
            'days_until_expiry': expiring_data['days_until_expiry'],
            'email_sent': result.get('success', False),
            'error': result.get('error'),
        }

    def process_points_expiring_reminders(
        self,
        days_threshold: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process and send points expiring reminders to all eligible members.

        Args:
            days_threshold: Only process members with points expiring within this many days.
                           Uses config threshold_days if not provided.

        Returns:
            Dict with count of reminders sent and any errors
        """
        config = self.get_points_expiring_config()

        if not config['enabled']:
            return {'success': False, 'error': 'Points expiring nudge is disabled'}

        # Use config threshold or provided value
        if days_threshold is None:
            # Use the smallest threshold from config (most urgent)
            days_threshold = min(config['threshold_days']) if config['threshold_days'] else 7

        # Get members with expiring points
        expiring_members = self.get_members_with_expiring_points(days_ahead=days_threshold)

        results = {
            'success': True,
            'total_eligible': len(expiring_members),
            'reminders_sent': 0,
            'skipped': 0,
            'errors': [],
        }

        for data in expiring_members:
            member_id = data['member']['id']

            # Check cooldown
            if NudgeSent.was_recently_sent(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.POINTS_EXPIRING.value,
                cooldown_days=config['frequency_days']
            ):
                results['skipped'] += 1
                continue

            # Send reminder
            result = self.send_points_expiring_reminder(member_id, force=True)

            if result.get('success'):
                results['reminders_sent'] += 1
            else:
                results['errors'].append({
                    'member_id': member_id,
                    'error': result.get('error'),
                })

        return results

    def get_points_expiring_nudge_history(
        self,
        member_id: Optional[int] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get history of points expiring nudges sent.

        Args:
            member_id: Filter to specific member (optional)
            days: Number of days to look back

        Returns:
            List of nudge sent records
        """
        if member_id:
            nudges = NudgeSent.get_member_nudge_history(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.POINTS_EXPIRING.value,
                limit=100
            )
        else:
            nudges = NudgeSent.get_recent_nudges_for_tenant(
                tenant_id=self.tenant_id,
                nudge_type=NudgeType.POINTS_EXPIRING.value,
                days=days,
                limit=100
            )

        return [n.to_dict() for n in nudges]

    # ==================== Tier Progress Reminder Methods ====================

    def get_tier_progress_config(self) -> Dict[str, Any]:
        """
        Get configuration for tier progress nudges.

        Returns:
            Dict with: enabled, threshold_percent (decimal), frequency_days (cooldown)
        """
        config = self.get_nudge_config(NudgeType.TIER_PROGRESS.value)

        if config:
            return {
                'enabled': config.is_enabled,
                'threshold_percent': config.config_options.get('threshold_percent', 0.9),
                'frequency_days': config.frequency_days,
                'message_template': config.message_template,
            }

        # Fall back to defaults
        settings = self.get_nudge_settings()
        return {
            'enabled': settings.get('enabled', True),
            'threshold_percent': settings.get('tier_upgrade_threshold', 0.9),
            'frequency_days': 14,  # Default cooldown: 14 days
            'message_template': None,
        }

    def get_members_near_tier_progress(
        self,
        threshold_percent: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Get members who are close to reaching the next tier.

        Args:
            threshold_percent: Minimum progress percentage (0.0-1.0) to include.
                             Default is 0.9 (90%), meaning members within 10% of next tier.

        Returns:
            List of dicts with member info, current tier, next tier, progress details
        """
        from app.models.member import MembershipTier

        config = self.get_tier_progress_config()
        if threshold_percent is None:
            threshold_percent = config['threshold_percent']

        # Get all tiers ordered by bonus_rate (as a proxy for tier level)
        tiers = MembershipTier.query.filter_by(
            tenant_id=self.tenant_id,
            is_active=True
        ).order_by(MembershipTier.bonus_rate.asc()).all()

        if len(tiers) < 2:
            return []  # Need at least 2 tiers for progression

        # Build tier progression map (current tier ID -> next tier)
        # Assumes tiers are ordered by bonus_rate from lowest to highest
        tier_progression = {}
        tier_thresholds = {}  # tier_id -> points threshold to reach this tier

        # Define tier thresholds based on display_order or bonus_rate
        # In production, these would be stored in tier configuration
        base_threshold = 500  # Points needed for first upgrade
        for i, tier in enumerate(tiers):
            if i == 0:
                tier_thresholds[tier.id] = 0  # Base tier requires no points
            else:
                # Each tier requires more points (can be customized per tenant)
                tier_thresholds[tier.id] = base_threshold * i

            if i < len(tiers) - 1:
                tier_progression[tier.id] = tiers[i + 1]

        # Get highest tier ID (members at this tier are already at the top)
        highest_tier_id = tiers[-1].id

        results = []
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        for member in members:
            # Skip members without a tier or at the highest tier
            if not member.tier_id:
                continue
            if member.tier_id == highest_tier_id:
                continue  # Already at highest tier, no progress to show
            if member.tier_id not in tier_progression:
                continue

            next_tier = tier_progression[member.tier_id]
            next_tier_threshold = tier_thresholds.get(next_tier.id, 0)

            if next_tier_threshold <= 0:
                continue

            # Calculate progress based on lifetime points earned
            current_points = member.lifetime_points_earned or 0
            current_tier_threshold = tier_thresholds.get(member.tier_id, 0)

            # Points needed within this tier range
            points_in_current_range = current_points - current_tier_threshold
            points_range = next_tier_threshold - current_tier_threshold

            if points_range <= 0:
                continue

            progress = min(1.0, max(0.0, points_in_current_range / points_range))

            # Only include members within the threshold (e.g., >= 90%)
            if progress >= threshold_percent and progress < 1.0:
                points_needed = next_tier_threshold - current_points

                # Get benefits of next tier
                next_tier_benefits = self._format_tier_benefits(next_tier)

                results.append({
                    'member': member.to_dict(),
                    'current_tier': member.tier.to_dict() if member.tier else None,
                    'next_tier': next_tier.to_dict(),
                    'progress_percent': round(progress * 100, 1),
                    'progress_decimal': round(progress, 4),
                    'current_points': current_points,
                    'points_needed': max(0, points_needed),
                    'next_tier_threshold': next_tier_threshold,
                    'next_tier_benefits': next_tier_benefits,
                    'nudge_type': NudgeType.TIER_PROGRESS.value,
                })

        # Sort by progress (highest first - closest to upgrade)
        results.sort(key=lambda x: x['progress_percent'], reverse=True)
        return results

    def _format_tier_benefits(self, tier) -> List[str]:
        """
        Format tier benefits as a list of human-readable strings.

        Args:
            tier: MembershipTier instance

        Returns:
            List of benefit descriptions
        """
        benefits = []

        # Bonus rate benefit
        if tier.bonus_rate and float(tier.bonus_rate) > 0:
            bonus_pct = round(float(tier.bonus_rate) * 100, 1)
            benefits.append(f"{bonus_pct}% bonus on trade-ins")

        # Monthly credit benefit
        if tier.monthly_credit_amount and float(tier.monthly_credit_amount) > 0:
            benefits.append(f"${float(tier.monthly_credit_amount):.2f} monthly store credit")

        # Purchase cashback benefit
        if tier.purchase_cashback_pct and float(tier.purchase_cashback_pct) > 0:
            benefits.append(f"{float(tier.purchase_cashback_pct)}% cashback on purchases")

        # JSON benefits field
        if tier.benefits:
            if tier.benefits.get('discount_percent'):
                benefits.append(f"{tier.benefits['discount_percent']}% member discount")
            if tier.benefits.get('free_shipping_threshold'):
                benefits.append(f"Free shipping on orders ${tier.benefits['free_shipping_threshold']}+")
            if tier.benefits.get('early_access'):
                benefits.append("Early access to new releases")
            if tier.benefits.get('exclusive_offers'):
                benefits.append("Exclusive member offers")

        return benefits

    def should_send_tier_progress_reminder(
        self,
        member_id: int,
        cooldown_days: Optional[int] = None
    ) -> bool:
        """
        Check if a tier progress reminder should be sent to this member.

        Checks:
        1. Nudge type is enabled
        2. Member is within threshold of next tier
        3. Member is not at the highest tier
        4. No reminder was sent within the cooldown period

        Args:
            member_id: The member ID
            cooldown_days: Override cooldown period (uses config default if not provided)

        Returns:
            True if reminder should be sent, False otherwise
        """
        config = self.get_tier_progress_config()

        # Check if nudge is enabled
        if not config['enabled']:
            return False

        # Use config cooldown if not overridden
        if cooldown_days is None:
            cooldown_days = config['frequency_days']

        # Check if recently sent
        if NudgeSent.was_recently_sent(
            tenant_id=self.tenant_id,
            member_id=member_id,
            nudge_type=NudgeType.TIER_PROGRESS.value,
            cooldown_days=cooldown_days
        ):
            return False

        # Check if member is near tier upgrade
        near_upgrade = self.get_members_near_tier_progress(
            threshold_percent=config['threshold_percent']
        )
        for data in near_upgrade:
            if data['member']['id'] == member_id:
                return True

        return False

    def send_tier_progress_reminder(
        self,
        member_id: int,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Send a tier progress reminder to a specific member.

        Args:
            member_id: The member to send reminder to
            force: Skip cooldown check if True

        Returns:
            Dict with success status and details
        """
        from app.models.tenant import Tenant
        from app.services.email_service import email_service

        member = Member.query.filter_by(
            id=member_id,
            tenant_id=self.tenant_id
        ).first()

        if not member:
            return {'success': False, 'error': 'Member not found'}

        if not member.email:
            return {'success': False, 'error': 'Member has no email address'}

        if member.status != 'active':
            return {'success': False, 'error': 'Member is not active'}

        # Check if we should send (unless forced)
        if not force:
            if not self.should_send_tier_progress_reminder(member_id):
                return {'success': False, 'error': 'Reminder not due (cooldown or not near tier upgrade)'}

        # Get tenant info
        tenant = Tenant.query.get(self.tenant_id)
        if not tenant:
            return {'success': False, 'error': 'Tenant not found'}

        # Get tier progress data for this member
        progress_data = None
        config = self.get_tier_progress_config()

        for data in self.get_members_near_tier_progress(threshold_percent=config['threshold_percent']):
            if data['member']['id'] == member_id:
                progress_data = data
                break

        if not progress_data:
            return {'success': False, 'error': 'Member is not near tier upgrade'}

        # Build email data
        benefits_list = '\n'.join([f"- {b}" for b in progress_data['next_tier_benefits']]) if progress_data['next_tier_benefits'] else ''

        email_data = {
            'member_name': member.name or member.email.split('@')[0],
            'current_tier': progress_data['current_tier']['name'] if progress_data['current_tier'] else 'Member',
            'next_tier': progress_data['next_tier']['name'],
            'progress_percent': progress_data['progress_percent'],
            'current_points': progress_data['current_points'],
            'points_needed': progress_data['points_needed'],
            'next_tier_threshold': progress_data['next_tier_threshold'],
            'next_tier_benefits': benefits_list,
            'shop_name': tenant.shop_name or tenant.shop_domain.split('.')[0].title(),
            'shop_url': f"https://{tenant.shop_domain}",
        }

        # Send email
        result = email_service.send_template_email(
            template_key='tier_progress',
            tenant_id=self.tenant_id,
            to_email=member.email,
            to_name=member.name or '',
            data=email_data,
            from_name=email_data['shop_name'],
        )

        # Record the nudge sent
        if result.get('success'):
            NudgeSent.record_sent(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.TIER_PROGRESS.value,
                context_data={
                    'current_tier': progress_data['current_tier']['name'] if progress_data['current_tier'] else None,
                    'next_tier': progress_data['next_tier']['name'],
                    'progress_percent': progress_data['progress_percent'],
                    'points_needed': progress_data['points_needed'],
                },
                delivery_method='email',
            )
            logger.info(f"Tier progress reminder sent to member {member_id} "
                       f"({progress_data['progress_percent']}% to {progress_data['next_tier']['name']})")
        else:
            logger.warning(f"Failed to send tier progress reminder to member {member_id}: "
                          f"{result.get('error', 'Unknown error')}")

        return {
            'success': result.get('success', False),
            'member_id': member_id,
            'current_tier': progress_data['current_tier']['name'] if progress_data['current_tier'] else None,
            'next_tier': progress_data['next_tier']['name'],
            'progress_percent': progress_data['progress_percent'],
            'points_needed': progress_data['points_needed'],
            'email_sent': result.get('success', False),
            'error': result.get('error'),
        }

    def process_tier_progress_reminders(
        self,
        threshold_percent: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Process and send tier progress reminders to all eligible members.

        Args:
            threshold_percent: Minimum progress to include (0.0-1.0).
                             Uses config threshold_percent if not provided.

        Returns:
            Dict with count of reminders sent and any errors
        """
        config = self.get_tier_progress_config()

        if not config['enabled']:
            return {'success': False, 'error': 'Tier progress nudge is disabled'}

        # Use config threshold or provided value
        if threshold_percent is None:
            threshold_percent = config['threshold_percent']

        # Get members near tier upgrade
        near_upgrade_members = self.get_members_near_tier_progress(
            threshold_percent=threshold_percent
        )

        results = {
            'success': True,
            'total_eligible': len(near_upgrade_members),
            'reminders_sent': 0,
            'skipped': 0,
            'errors': [],
        }

        for data in near_upgrade_members:
            member_id = data['member']['id']

            # Check cooldown
            if NudgeSent.was_recently_sent(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.TIER_PROGRESS.value,
                cooldown_days=config['frequency_days']
            ):
                results['skipped'] += 1
                continue

            # Send reminder
            result = self.send_tier_progress_reminder(member_id, force=True)

            if result.get('success'):
                results['reminders_sent'] += 1
            else:
                results['errors'].append({
                    'member_id': member_id,
                    'error': result.get('error'),
                })

        return results

    def get_tier_progress_nudge_history(
        self,
        member_id: Optional[int] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get history of tier progress nudges sent.

        Args:
            member_id: Filter to specific member (optional)
            days: Number of days to look back

        Returns:
            List of nudge sent records
        """
        if member_id:
            nudges = NudgeSent.get_member_nudge_history(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.TIER_PROGRESS.value,
                limit=100
            )
        else:
            nudges = NudgeSent.get_recent_nudges_for_tenant(
                tenant_id=self.tenant_id,
                nudge_type=NudgeType.TIER_PROGRESS.value,
                days=days,
                limit=100
            )

        return [n.to_dict() for n in nudges]

    def update_tier_progress_config(
        self,
        enabled: Optional[bool] = None,
        threshold_percent: Optional[float] = None,
        frequency_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update the tier progress nudge configuration.

        Args:
            enabled: Enable/disable the nudge
            threshold_percent: Minimum progress percentage to trigger (0.0-1.0)
            frequency_days: Cooldown days between reminders

        Returns:
            Dict with updated configuration
        """
        config = NudgeConfig.get_by_type(self.tenant_id, NudgeType.TIER_PROGRESS.value)

        if not config:
            return {'success': False, 'error': 'Tier progress nudge config not found'}

        if enabled is not None:
            config.is_enabled = enabled

        if frequency_days is not None:
            config.frequency_days = frequency_days

        if threshold_percent is not None:
            # Validate threshold is between 0 and 1
            if threshold_percent < 0 or threshold_percent > 1:
                return {'success': False, 'error': 'Threshold must be between 0.0 and 1.0'}
            if not config.config_options:
                config.config_options = {}
            config.config_options['threshold_percent'] = threshold_percent

        config.updated_at = datetime.utcnow()
        db.session.commit()

        return {
            'success': True,
            'config': config.to_dict(),
        }

    def update_points_expiring_config(
        self,
        enabled: Optional[bool] = None,
        threshold_days: Optional[List[int]] = None,
        frequency_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update the points expiring nudge configuration.

        Args:
            enabled: Enable/disable the nudge
            threshold_days: List of days before expiry to send reminders (e.g., [30, 7, 1])
            frequency_days: Cooldown days between reminders

        Returns:
            Dict with updated configuration
        """
        config = NudgeConfig.get_by_type(self.tenant_id, NudgeType.POINTS_EXPIRING.value)

        if not config:
            return {'success': False, 'error': 'Points expiring nudge config not found'}

        if enabled is not None:
            config.is_enabled = enabled

        if frequency_days is not None:
            config.frequency_days = frequency_days

        if threshold_days is not None:
            if not config.config_options:
                config.config_options = {}
            config.config_options['threshold_days'] = sorted(threshold_days, reverse=True)

        config.updated_at = datetime.utcnow()
        db.session.commit()

        return {
            'success': True,
            'config': config.to_dict(),
        }

    # ==================== Inactive Member Re-engagement Methods ====================

    def get_inactive_reengagement_config(self) -> Dict[str, Any]:
        """
        Get configuration for inactive member re-engagement nudges.

        Returns:
            Dict with: enabled, inactive_days (threshold), frequency_days (cooldown),
                      incentive_type, incentive_amount
        """
        config = self.get_nudge_config(NudgeType.INACTIVE_REMINDER.value)

        if config:
            return {
                'enabled': config.is_enabled,
                'inactive_days': config.config_options.get('inactive_days', 30),
                'frequency_days': config.frequency_days,
                'incentive_type': config.config_options.get('incentive_type', 'points'),
                'incentive_amount': config.config_options.get('incentive_amount', 50),
                'message_template': config.message_template,
            }

        # Fall back to defaults
        settings = self.get_nudge_settings()
        return {
            'enabled': settings.get('enabled', True),
            'inactive_days': settings.get('inactive_days', 30),
            'frequency_days': 30,  # Default cooldown: 30 days
            'incentive_type': 'points',  # points, credit, discount
            'incentive_amount': 50,  # 50 bonus points by default
            'message_template': None,
        }

    def get_inactive_members_for_reengagement(
        self,
        inactive_days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get members who have been inactive and are eligible for re-engagement.

        Args:
            inactive_days: Days of inactivity threshold (default: from config)

        Returns:
            List of dicts with member info, inactivity details, and current status
        """
        config = self.get_inactive_reengagement_config()
        if inactive_days is None:
            inactive_days = config['inactive_days']

        cutoff_date = datetime.utcnow() - timedelta(days=inactive_days)

        # Find members with no recent activity
        inactive_members = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.status == 'active',
            Member.updated_at < cutoff_date
        ).all()

        results = []
        for member in inactive_members:
            days_since_activity = (datetime.utcnow() - (member.updated_at or member.created_at)).days

            # Get member's current status summary
            points_balance = member.points_balance or 0
            tier_name = member.tier.name if member.tier else 'Member'
            tier_benefits = self._format_tier_benefits(member.tier) if member.tier else []

            # Calculate what they're missing
            missed_summary = self._calculate_missed_opportunities(member, days_since_activity)

            results.append({
                'member': member.to_dict(),
                'days_inactive': days_since_activity,
                'last_activity': member.updated_at.isoformat() if member.updated_at else None,
                'points_balance': points_balance,
                'tier_name': tier_name,
                'tier_benefits': tier_benefits,
                'missed_opportunities': missed_summary,
                'nudge_type': NudgeType.INACTIVE_MEMBER.value,
            })

        # Sort by days inactive (longest first)
        results.sort(key=lambda x: x['days_inactive'], reverse=True)
        return results

    def _calculate_missed_opportunities(
        self,
        member: Member,
        days_inactive: int
    ) -> Dict[str, Any]:
        """
        Calculate what opportunities a member has missed during their inactivity.

        Args:
            member: The inactive Member
            days_inactive: Number of days of inactivity

        Returns:
            Dict with summary of missed opportunities
        """
        missed = {
            'potential_points': 0,
            'potential_credit': 0,
            'summary_items': [],
        }

        # Estimate potential points based on average earning (simplified)
        # Assume 10 points per transaction, 2 transactions per month
        months_inactive = days_inactive / 30
        estimated_transactions = int(months_inactive * 2)
        estimated_points = estimated_transactions * 10
        if estimated_points > 0:
            missed['potential_points'] = estimated_points
            missed['summary_items'].append(f"~{estimated_points} points from purchases")

        # Check if tier has monthly credit
        if member.tier and member.tier.monthly_credit_amount:
            months_missed = int(months_inactive)
            credit_missed = float(member.tier.monthly_credit_amount) * months_missed
            if credit_missed > 0:
                missed['potential_credit'] = credit_missed
                missed['summary_items'].append(f"${credit_missed:.2f} in monthly tier credits")

        # Add generic missed items
        if days_inactive >= 60:
            missed['summary_items'].append("New product releases and exclusive deals")
        if days_inactive >= 90:
            missed['summary_items'].append("Seasonal promotions and sales")

        return missed

    def should_send_reengagement_email(
        self,
        member_id: int,
        cooldown_days: Optional[int] = None
    ) -> bool:
        """
        Check if a re-engagement email should be sent to this inactive member.

        Checks:
        1. Nudge type is enabled
        2. Member has been inactive for threshold days
        3. No re-engagement email was sent within the cooldown period

        Args:
            member_id: The member ID
            cooldown_days: Override cooldown period (uses config default if not provided)

        Returns:
            True if email should be sent, False otherwise
        """
        config = self.get_inactive_reengagement_config()

        # Check if nudge is enabled
        if not config['enabled']:
            return False

        # Use config cooldown if not overridden
        if cooldown_days is None:
            cooldown_days = config['frequency_days']

        # Check if recently sent
        if NudgeSent.was_recently_sent(
            tenant_id=self.tenant_id,
            member_id=member_id,
            nudge_type=NudgeType.INACTIVE_MEMBER.value,
            cooldown_days=cooldown_days
        ):
            return False

        # Check if member is inactive enough
        inactive_members = self.get_inactive_members_for_reengagement(
            inactive_days=config['inactive_days']
        )
        for data in inactive_members:
            if data['member']['id'] == member_id:
                return True

        return False

    def send_reengagement_email(
        self,
        member_id: int,
        force: bool = False,
        custom_incentive: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a re-engagement email to an inactive member.

        Args:
            member_id: The member to send the email to
            force: Skip cooldown check if True
            custom_incentive: Override default incentive (type, amount)

        Returns:
            Dict with success status and details
        """
        from app.models.tenant import Tenant
        from app.services.email_service import email_service

        member = Member.query.filter_by(
            id=member_id,
            tenant_id=self.tenant_id
        ).first()

        if not member:
            return {'success': False, 'error': 'Member not found'}

        if not member.email:
            return {'success': False, 'error': 'Member has no email address'}

        if member.status != 'active':
            return {'success': False, 'error': 'Member is not active'}

        # Check if we should send (unless forced)
        if not force:
            if not self.should_send_reengagement_email(member_id):
                return {'success': False, 'error': 'Re-engagement email not due (cooldown or not inactive enough)'}

        # Get tenant info
        tenant = Tenant.query.get(self.tenant_id)
        if not tenant:
            return {'success': False, 'error': 'Tenant not found'}

        # Get inactivity data
        inactivity_data = None
        config = self.get_inactive_reengagement_config()

        for data in self.get_inactive_members_for_reengagement(inactive_days=config['inactive_days']):
            if data['member']['id'] == member_id:
                inactivity_data = data
                break

        if not inactivity_data:
            return {'success': False, 'error': 'Member is not inactive enough for re-engagement'}

        # Determine incentive
        incentive = custom_incentive or {
            'type': config['incentive_type'],
            'amount': config['incentive_amount'],
        }

        # Format incentive for email
        if incentive['type'] == 'points':
            incentive_text = f"{incentive['amount']} bonus points"
        elif incentive['type'] == 'credit':
            incentive_text = f"${incentive['amount']:.2f} store credit"
        elif incentive['type'] == 'discount':
            incentive_text = f"{incentive['amount']}% off your next purchase"
        else:
            incentive_text = "a special reward"

        # Format missed opportunities
        missed_items = inactivity_data.get('missed_opportunities', {}).get('summary_items', [])
        missed_text = '\n'.join([f"- {item}" for item in missed_items]) if missed_items else ''

        # Build email data
        email_data = {
            'member_name': member.name or member.email.split('@')[0],
            'days_inactive': inactivity_data['days_inactive'],
            'points_balance': inactivity_data['points_balance'],
            'tier_name': inactivity_data['tier_name'],
            'incentive_text': incentive_text,
            'missed_opportunities': missed_text,
            'shop_name': tenant.shop_name or tenant.shop_domain.split('.')[0].title(),
            'shop_url': f"https://{tenant.shop_domain}",
        }

        # Send email
        result = email_service.send_template_email(
            template_key='inactive_reengagement',
            tenant_id=self.tenant_id,
            to_email=member.email,
            to_name=member.name or '',
            data=email_data,
            from_name=email_data['shop_name'],
        )

        # Record the nudge sent
        if result.get('success'):
            NudgeSent.record_sent(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.INACTIVE_MEMBER.value,
                context_data={
                    'days_inactive': inactivity_data['days_inactive'],
                    'points_balance': inactivity_data['points_balance'],
                    'tier_name': inactivity_data['tier_name'],
                    'incentive_type': incentive['type'],
                    'incentive_amount': incentive['amount'],
                },
                delivery_method='email',
            )
            logger.info(f"Re-engagement email sent to member {member_id} "
                       f"(inactive {inactivity_data['days_inactive']} days)")
        else:
            logger.warning(f"Failed to send re-engagement email to member {member_id}: "
                          f"{result.get('error', 'Unknown error')}")

        return {
            'success': result.get('success', False),
            'member_id': member_id,
            'days_inactive': inactivity_data['days_inactive'],
            'incentive': incentive,
            'email_sent': result.get('success', False),
            'error': result.get('error'),
        }

    def process_reengagement_emails(
        self,
        inactive_days: Optional[int] = None,
        max_emails: int = 50
    ) -> Dict[str, Any]:
        """
        Process and send re-engagement emails to all eligible inactive members.

        Args:
            inactive_days: Override inactivity threshold (uses config if not provided)
            max_emails: Maximum emails to send in one batch

        Returns:
            Dict with count of emails sent and any errors
        """
        config = self.get_inactive_reengagement_config()

        if not config['enabled']:
            return {'success': False, 'error': 'Inactive re-engagement nudge is disabled'}

        # Use config threshold or provided value
        if inactive_days is None:
            inactive_days = config['inactive_days']

        # Get inactive members
        inactive_members = self.get_inactive_members_for_reengagement(
            inactive_days=inactive_days
        )

        results = {
            'success': True,
            'total_eligible': len(inactive_members),
            'emails_sent': 0,
            'skipped': 0,
            'errors': [],
        }

        emails_sent = 0
        for data in inactive_members:
            if emails_sent >= max_emails:
                break

            member_id = data['member']['id']

            # Check cooldown
            if NudgeSent.was_recently_sent(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.INACTIVE_MEMBER.value,
                cooldown_days=config['frequency_days']
            ):
                results['skipped'] += 1
                continue

            # Send email
            result = self.send_reengagement_email(member_id, force=True)

            if result.get('success'):
                results['emails_sent'] += 1
                emails_sent += 1
            else:
                results['errors'].append({
                    'member_id': member_id,
                    'error': result.get('error'),
                })

        return results

    def get_reengagement_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get statistics about re-engagement nudge effectiveness.

        Tracks:
        - Total sent
        - Open rate
        - Click rate (response rate)
        - Members who became active after receiving email

        Args:
            days: Number of days to analyze

        Returns:
            Dict with re-engagement statistics
        """
        from sqlalchemy import func

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get all re-engagement nudges sent in the period
        nudges = NudgeSent.query.filter(
            NudgeSent.tenant_id == self.tenant_id,
            NudgeSent.nudge_type == NudgeType.INACTIVE_MEMBER.value,
            NudgeSent.sent_at >= cutoff
        ).all()

        total_sent = len(nudges)
        opened = sum(1 for n in nudges if n.opened_at)
        clicked = sum(1 for n in nudges if n.clicked_at)

        # Check how many members became active after receiving the email
        reactivated = 0
        for nudge in nudges:
            member = Member.query.get(nudge.member_id)
            if member and member.updated_at and nudge.sent_at:
                # Check if member had activity after the nudge was sent
                if member.updated_at > nudge.sent_at:
                    reactivated += 1

        return {
            'period_days': days,
            'total_sent': total_sent,
            'opened': opened,
            'clicked': clicked,
            'reactivated': reactivated,
            'open_rate': round(opened / total_sent * 100, 1) if total_sent > 0 else 0,
            'click_rate': round(clicked / total_sent * 100, 1) if total_sent > 0 else 0,
            'response_rate': round(reactivated / total_sent * 100, 1) if total_sent > 0 else 0,
        }

    def get_reengagement_history(
        self,
        member_id: Optional[int] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get history of re-engagement emails sent.

        Args:
            member_id: Filter to specific member (optional)
            days: Number of days to look back

        Returns:
            List of nudge sent records
        """
        if member_id:
            nudges = NudgeSent.get_member_nudge_history(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.INACTIVE_MEMBER.value,
                limit=100
            )
        else:
            nudges = NudgeSent.get_recent_nudges_for_tenant(
                tenant_id=self.tenant_id,
                nudge_type=NudgeType.INACTIVE_MEMBER.value,
                days=days,
                limit=100
            )

        return [n.to_dict() for n in nudges]

    def update_inactive_reengagement_config(
        self,
        enabled: Optional[bool] = None,
        inactive_days: Optional[int] = None,
        frequency_days: Optional[int] = None,
        incentive_type: Optional[str] = None,
        incentive_amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Update the inactive re-engagement nudge configuration.

        Args:
            enabled: Enable/disable the nudge
            inactive_days: Days of inactivity threshold
            frequency_days: Cooldown days between re-engagement emails
            incentive_type: Type of incentive (points, credit, discount)
            incentive_amount: Amount of incentive

        Returns:
            Dict with updated configuration
        """
        config = NudgeConfig.get_by_type(self.tenant_id, NudgeType.INACTIVE_REMINDER.value)

        if not config:
            return {'success': False, 'error': 'Inactive re-engagement nudge config not found'}

        if enabled is not None:
            config.is_enabled = enabled

        if frequency_days is not None:
            config.frequency_days = frequency_days

        # Update config_options
        if not config.config_options:
            config.config_options = {}

        if inactive_days is not None:
            config.config_options['inactive_days'] = inactive_days

        if incentive_type is not None:
            if incentive_type not in ['points', 'credit', 'discount']:
                return {'success': False, 'error': 'Invalid incentive type. Must be: points, credit, or discount'}
            config.config_options['incentive_type'] = incentive_type

        if incentive_amount is not None:
            if incentive_amount <= 0:
                return {'success': False, 'error': 'Incentive amount must be positive'}
            config.config_options['incentive_amount'] = incentive_amount

        config.updated_at = datetime.utcnow()
        db.session.commit()

        return {
            'success': True,
            'config': config.to_dict(),
        }

    def track_reengagement_response(
        self,
        member_id: int,
        action: str = 'clicked'
    ) -> Dict[str, Any]:
        """
        Track when an inactive member responds to a re-engagement email.

        Args:
            member_id: The member who responded
            action: The action taken ('opened', 'clicked')

        Returns:
            Dict with success status
        """
        # Find the most recent re-engagement nudge for this member
        nudge = NudgeSent.query.filter(
            NudgeSent.tenant_id == self.tenant_id,
            NudgeSent.member_id == member_id,
            NudgeSent.nudge_type == NudgeType.INACTIVE_MEMBER.value
        ).order_by(NudgeSent.sent_at.desc()).first()

        if not nudge:
            return {'success': False, 'error': 'No re-engagement email found for this member'}

        if action == 'opened':
            nudge.mark_opened()
        elif action == 'clicked':
            nudge.mark_clicked()
        else:
            return {'success': False, 'error': f'Invalid action: {action}'}

        return {
            'success': True,
            'nudge_id': nudge.id,
            'action': action,
            'tracked_at': datetime.utcnow().isoformat(),
        }

    # ==================== Trade-In Reminder Methods ====================

    def get_trade_in_reminder_config(self) -> Dict[str, Any]:
        """
        Get configuration for trade-in reminder nudges.

        Returns:
            Dict with: enabled, min_days_since_last (threshold), frequency_days (cooldown)
        """
        config = self.get_nudge_config(NudgeType.TRADE_IN_REMINDER.value)

        if config:
            return {
                'enabled': config.is_enabled,
                'min_days_since_last': config.config_options.get('min_days_since_last', 60),
                'frequency_days': config.frequency_days,
                'message_template': config.message_template,
            }

        # Fall back to defaults
        settings = self.get_nudge_settings()
        return {
            'enabled': settings.get('enabled', True),
            'min_days_since_last': settings.get('trade_in_reminder_days', 60),
            'frequency_days': 21,  # Default cooldown: 3 weeks
            'message_template': None,
        }

    def is_trade_ins_enabled_for_tenant(self) -> bool:
        """
        Check if trade-ins are enabled for the tenant.

        Returns:
            True if trade-ins are enabled, False otherwise
        """
        from app.models.tenant import Tenant
        from app.utils.settings_defaults import get_settings_with_defaults

        tenant = Tenant.query.get(self.tenant_id)
        if not tenant:
            return False

        settings = get_settings_with_defaults(tenant.settings or {})
        return settings.get('trade_ins', {}).get('enabled', True)

    def get_trade_in_rates_for_tenant(self) -> Dict[str, Any]:
        """
        Get current trade-in credit rates and bonuses for the tenant.

        Returns:
            Dict with credit rate info and any active bonuses
        """
        from app.models.member import MembershipTier

        rates = {
            'base_rate': '100%',  # Base trade-in value
            'tier_bonuses': [],
            'active_promotions': [],
        }

        # Get tier bonuses
        tiers = MembershipTier.query.filter_by(
            tenant_id=self.tenant_id,
            is_active=True
        ).order_by(MembershipTier.bonus_rate.asc()).all()

        for tier in tiers:
            if tier.bonus_rate and float(tier.bonus_rate) > 0:
                bonus_pct = round(float(tier.bonus_rate) * 100, 1)
                rates['tier_bonuses'].append({
                    'tier_name': tier.name,
                    'bonus_percent': bonus_pct,
                    'description': f"{tier.name} members: +{bonus_pct}% bonus on trade-ins",
                })

        return rates

    def get_members_needing_trade_in_reminder(
        self,
        min_days_since_last: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get members who haven't done a trade-in in a while and may benefit from a reminder.

        Identifies members who:
        1. Are active
        2. Have done at least one trade-in before (showing interest in the program)
        3. Haven't done a trade-in in min_days_since_last days (default: 60)

        Args:
            min_days_since_last: Minimum days since last trade-in to qualify (default: from config)

        Returns:
            List of dicts with member info and last trade-in details
        """
        from app.models.trade_in import TradeInBatch

        # Check if trade-ins are enabled for this tenant
        if not self.is_trade_ins_enabled_for_tenant():
            return []

        config = self.get_trade_in_reminder_config()
        if min_days_since_last is None:
            min_days_since_last = config['min_days_since_last']

        cutoff_date = datetime.utcnow() - timedelta(days=min_days_since_last)

        # Get all active members with their most recent trade-in
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        results = []
        for member in members:
            # Find this member's most recent trade-in
            last_trade_in = TradeInBatch.query.filter(
                TradeInBatch.tenant_id == self.tenant_id,
                TradeInBatch.member_id == member.id,
                TradeInBatch.status.in_(['completed', 'listed', 'pending'])
            ).order_by(TradeInBatch.trade_in_date.desc()).first()

            # Only include members who have done at least one trade-in
            if not last_trade_in:
                continue

            # Check if the last trade-in is old enough
            if last_trade_in.trade_in_date >= cutoff_date:
                continue  # Too recent, skip

            days_since_last = (datetime.utcnow() - last_trade_in.trade_in_date).days

            # Get trade-in stats for this member
            trade_in_count = TradeInBatch.query.filter(
                TradeInBatch.tenant_id == self.tenant_id,
                TradeInBatch.member_id == member.id,
                TradeInBatch.status == 'completed'
            ).count()

            total_value = db.session.query(
                db.func.sum(TradeInBatch.total_trade_value)
            ).filter(
                TradeInBatch.tenant_id == self.tenant_id,
                TradeInBatch.member_id == member.id,
                TradeInBatch.status == 'completed'
            ).scalar() or 0

            results.append({
                'member': member.to_dict(),
                'days_since_last_trade_in': days_since_last,
                'last_trade_in_date': last_trade_in.trade_in_date.isoformat(),
                'last_trade_in_value': float(last_trade_in.total_trade_value),
                'total_trade_ins': trade_in_count,
                'lifetime_trade_in_value': float(total_value),
                'tier_name': member.tier.name if member.tier else 'Member',
                'tier_bonus': float(member.tier.bonus_rate * 100) if member.tier and member.tier.bonus_rate else 0,
                'nudge_type': NudgeType.TRADE_IN_REMINDER.value,
            })

        # Sort by days since last trade-in (longest first)
        results.sort(key=lambda x: x['days_since_last_trade_in'], reverse=True)
        return results

    def should_send_trade_in_reminder(
        self,
        member_id: int,
        cooldown_days: Optional[int] = None
    ) -> bool:
        """
        Check if a trade-in reminder should be sent to this member.

        Checks:
        1. Trade-ins are enabled for the tenant
        2. Nudge type is enabled
        3. Member qualifies (hasn't traded in recently)
        4. No reminder was sent within the cooldown period

        Args:
            member_id: The member ID
            cooldown_days: Override cooldown period (uses config default if not provided)

        Returns:
            True if reminder should be sent, False otherwise
        """
        # Check if trade-ins are enabled
        if not self.is_trade_ins_enabled_for_tenant():
            return False

        config = self.get_trade_in_reminder_config()

        # Check if nudge is enabled
        if not config['enabled']:
            return False

        # Use config cooldown if not overridden
        if cooldown_days is None:
            cooldown_days = config['frequency_days']

        # Check if recently sent
        if NudgeSent.was_recently_sent(
            tenant_id=self.tenant_id,
            member_id=member_id,
            nudge_type=NudgeType.TRADE_IN_REMINDER.value,
            cooldown_days=cooldown_days
        ):
            return False

        # Check if member qualifies for reminder
        qualifying_members = self.get_members_needing_trade_in_reminder(
            min_days_since_last=config['min_days_since_last']
        )
        for data in qualifying_members:
            if data['member']['id'] == member_id:
                return True

        return False

    def send_trade_in_reminder(
        self,
        member_id: int,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Send a trade-in reminder to a specific member.

        Args:
            member_id: The member to send reminder to
            force: Skip cooldown check if True

        Returns:
            Dict with success status and details
        """
        from app.models.tenant import Tenant
        from app.services.email_service import email_service

        # Check if trade-ins are enabled
        if not self.is_trade_ins_enabled_for_tenant():
            return {'success': False, 'error': 'Trade-ins are not enabled for this store'}

        member = Member.query.filter_by(
            id=member_id,
            tenant_id=self.tenant_id
        ).first()

        if not member:
            return {'success': False, 'error': 'Member not found'}

        if not member.email:
            return {'success': False, 'error': 'Member has no email address'}

        if member.status != 'active':
            return {'success': False, 'error': 'Member is not active'}

        # Check if we should send (unless forced)
        if not force:
            if not self.should_send_trade_in_reminder(member_id):
                return {'success': False, 'error': 'Reminder not due (cooldown, no qualifying trade-in history, or trade-ins disabled)'}

        # Get tenant info
        tenant = Tenant.query.get(self.tenant_id)
        if not tenant:
            return {'success': False, 'error': 'Tenant not found'}

        # Get trade-in data for this member
        reminder_data = None
        config = self.get_trade_in_reminder_config()

        for data in self.get_members_needing_trade_in_reminder(min_days_since_last=config['min_days_since_last']):
            if data['member']['id'] == member_id:
                reminder_data = data
                break

        if not reminder_data and not force:
            return {'success': False, 'error': 'Member does not qualify for trade-in reminder'}

        # If forced but no data, create minimal data
        if not reminder_data:
            reminder_data = {
                'days_since_last_trade_in': 0,
                'tier_name': member.tier.name if member.tier else 'Member',
                'tier_bonus': float(member.tier.bonus_rate * 100) if member.tier and member.tier.bonus_rate else 0,
            }

        # Get current credit rates
        rates = self.get_trade_in_rates_for_tenant()

        # Build credit rates text
        rates_text = ''
        if rates['tier_bonuses']:
            rates_text = '\n'.join([f"- {b['description']}" for b in rates['tier_bonuses']])

        # Build email data
        email_data = {
            'member_name': member.name or member.email.split('@')[0],
            'days_since_last': reminder_data.get('days_since_last_trade_in', 0),
            'tier_name': reminder_data.get('tier_name', 'Member'),
            'tier_bonus': reminder_data.get('tier_bonus', 0),
            'credit_rates': rates_text,
            'has_tier_bonus': reminder_data.get('tier_bonus', 0) > 0,
            'shop_name': tenant.shop_name or tenant.shop_domain.split('.')[0].title(),
            'shop_url': f"https://{tenant.shop_domain}",
        }

        # Send email
        result = email_service.send_template_email(
            template_key='trade_in_reminder',
            tenant_id=self.tenant_id,
            to_email=member.email,
            to_name=member.name or '',
            data=email_data,
            from_name=email_data['shop_name'],
        )

        # Record the nudge sent
        if result.get('success'):
            NudgeSent.record_sent(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.TRADE_IN_REMINDER.value,
                context_data={
                    'days_since_last': reminder_data.get('days_since_last_trade_in', 0),
                    'tier_name': reminder_data.get('tier_name'),
                    'tier_bonus': reminder_data.get('tier_bonus', 0),
                },
                delivery_method='email',
            )
            logger.info(f"Trade-in reminder sent to member {member_id} "
                       f"(last trade-in {reminder_data.get('days_since_last_trade_in', 'N/A')} days ago)")
        else:
            logger.warning(f"Failed to send trade-in reminder to member {member_id}: "
                          f"{result.get('error', 'Unknown error')}")

        return {
            'success': result.get('success', False),
            'member_id': member_id,
            'days_since_last_trade_in': reminder_data.get('days_since_last_trade_in', 0),
            'tier_bonus': reminder_data.get('tier_bonus', 0),
            'email_sent': result.get('success', False),
            'error': result.get('error'),
        }

    def process_trade_in_reminders(
        self,
        min_days_since_last: Optional[int] = None,
        max_emails: int = 50
    ) -> Dict[str, Any]:
        """
        Process and send trade-in reminders to all eligible members.

        Args:
            min_days_since_last: Override days threshold (uses config if not provided)
            max_emails: Maximum emails to send in one batch

        Returns:
            Dict with count of reminders sent and any errors
        """
        # Check if trade-ins are enabled
        if not self.is_trade_ins_enabled_for_tenant():
            return {'success': False, 'error': 'Trade-ins are not enabled for this store'}

        config = self.get_trade_in_reminder_config()

        if not config['enabled']:
            return {'success': False, 'error': 'Trade-in reminder nudge is disabled'}

        # Use config threshold or provided value
        if min_days_since_last is None:
            min_days_since_last = config['min_days_since_last']

        # Get members needing reminder
        qualifying_members = self.get_members_needing_trade_in_reminder(
            min_days_since_last=min_days_since_last
        )

        results = {
            'success': True,
            'total_eligible': len(qualifying_members),
            'reminders_sent': 0,
            'skipped': 0,
            'errors': [],
        }

        emails_sent = 0
        for data in qualifying_members:
            if emails_sent >= max_emails:
                break

            member_id = data['member']['id']

            # Check cooldown
            if NudgeSent.was_recently_sent(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.TRADE_IN_REMINDER.value,
                cooldown_days=config['frequency_days']
            ):
                results['skipped'] += 1
                continue

            # Send reminder
            result = self.send_trade_in_reminder(member_id, force=True)

            if result.get('success'):
                results['reminders_sent'] += 1
                emails_sent += 1
            else:
                results['errors'].append({
                    'member_id': member_id,
                    'error': result.get('error'),
                })

        return results

    def get_trade_in_reminder_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get statistics about trade-in reminder effectiveness.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with reminder statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get all trade-in reminders sent in the period
        nudges = NudgeSent.query.filter(
            NudgeSent.tenant_id == self.tenant_id,
            NudgeSent.nudge_type == NudgeType.TRADE_IN_REMINDER.value,
            NudgeSent.sent_at >= cutoff
        ).all()

        total_sent = len(nudges)
        opened = sum(1 for n in nudges if n.opened_at)
        clicked = sum(1 for n in nudges if n.clicked_at)

        # Check how many members did a trade-in after receiving the reminder
        from app.models.trade_in import TradeInBatch

        responded = 0
        for nudge in nudges:
            # Check if member did a trade-in after the nudge was sent
            trade_in_after = TradeInBatch.query.filter(
                TradeInBatch.tenant_id == self.tenant_id,
                TradeInBatch.member_id == nudge.member_id,
                TradeInBatch.trade_in_date > nudge.sent_at
            ).first()

            if trade_in_after:
                responded += 1

        return {
            'period_days': days,
            'total_sent': total_sent,
            'opened': opened,
            'clicked': clicked,
            'trade_ins_after_reminder': responded,
            'open_rate': round(opened / total_sent * 100, 1) if total_sent > 0 else 0,
            'click_rate': round(clicked / total_sent * 100, 1) if total_sent > 0 else 0,
            'response_rate': round(responded / total_sent * 100, 1) if total_sent > 0 else 0,
        }

    def get_trade_in_reminder_history(
        self,
        member_id: Optional[int] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get history of trade-in reminders sent.

        Args:
            member_id: Filter to specific member (optional)
            days: Number of days to look back

        Returns:
            List of nudge sent records
        """
        if member_id:
            nudges = NudgeSent.get_member_nudge_history(
                tenant_id=self.tenant_id,
                member_id=member_id,
                nudge_type=NudgeType.TRADE_IN_REMINDER.value,
                limit=100
            )
        else:
            nudges = NudgeSent.get_recent_nudges_for_tenant(
                tenant_id=self.tenant_id,
                nudge_type=NudgeType.TRADE_IN_REMINDER.value,
                days=days,
                limit=100
            )

        return [n.to_dict() for n in nudges]

    def update_trade_in_reminder_config(
        self,
        enabled: Optional[bool] = None,
        min_days_since_last: Optional[int] = None,
        frequency_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update the trade-in reminder nudge configuration.

        Args:
            enabled: Enable/disable the nudge
            min_days_since_last: Days since last trade-in to trigger reminder
            frequency_days: Cooldown days between reminders

        Returns:
            Dict with updated configuration
        """
        config = NudgeConfig.get_by_type(self.tenant_id, NudgeType.TRADE_IN_REMINDER.value)

        if not config:
            return {'success': False, 'error': 'Trade-in reminder nudge config not found'}

        if enabled is not None:
            config.is_enabled = enabled

        if frequency_days is not None:
            config.frequency_days = frequency_days

        # Update config_options
        if not config.config_options:
            config.config_options = {}

        if min_days_since_last is not None:
            if min_days_since_last < 1:
                return {'success': False, 'error': 'min_days_since_last must be at least 1'}
            config.config_options['min_days_since_last'] = min_days_since_last

        config.updated_at = datetime.utcnow()
        db.session.commit()

        return {
            'success': True,
            'config': config.to_dict(),
        }

    # ==================== Nudge Effectiveness Tracking Methods ====================

    def get_effectiveness_metrics(
        self,
        nudge_type: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive effectiveness metrics for nudges.

        Args:
            nudge_type: Optional filter by nudge type
            days: Number of days to analyze

        Returns:
            Dict with open rate, click rate, conversion rate, and ROI metrics
        """
        return NudgeSent.get_effectiveness_metrics(
            tenant_id=self.tenant_id,
            nudge_type=nudge_type,
            days=days
        )

    def get_metrics_by_type(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get effectiveness metrics broken down by nudge type.

        Args:
            days: Number of days to analyze

        Returns:
            List of metrics dictionaries, one per nudge type
        """
        return NudgeSent.get_metrics_by_type(
            tenant_id=self.tenant_id,
            days=days
        )

    def get_daily_metrics(
        self,
        nudge_type: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get daily breakdown of nudge metrics for trending.

        Args:
            nudge_type: Optional filter by nudge type
            days: Number of days to include

        Returns:
            List of daily metrics dictionaries
        """
        return NudgeSent.get_daily_metrics(
            tenant_id=self.tenant_id,
            nudge_type=nudge_type,
            days=days
        )

    def track_open(self, tracking_id: str) -> Dict[str, Any]:
        """
        Track that a nudge email was opened.

        Args:
            tracking_id: The unique tracking ID from the email

        Returns:
            Dict with success status
        """
        nudge = NudgeSent.get_by_tracking_id(tracking_id)
        if not nudge:
            return {'success': False, 'error': 'Nudge not found'}

        if nudge.tenant_id != self.tenant_id:
            return {'success': False, 'error': 'Nudge not found'}

        if not nudge.opened_at:
            nudge.mark_opened()

        return {
            'success': True,
            'nudge_id': nudge.id,
            'opened_at': nudge.opened_at.isoformat() if nudge.opened_at else None,
        }

    def track_click(self, tracking_id: str) -> Dict[str, Any]:
        """
        Track that a link in a nudge email was clicked.

        Args:
            tracking_id: The unique tracking ID from the email

        Returns:
            Dict with success status
        """
        nudge = NudgeSent.get_by_tracking_id(tracking_id)
        if not nudge:
            return {'success': False, 'error': 'Nudge not found'}

        if nudge.tenant_id != self.tenant_id:
            return {'success': False, 'error': 'Nudge not found'}

        nudge.mark_clicked()

        return {
            'success': True,
            'nudge_id': nudge.id,
            'clicked_at': nudge.clicked_at.isoformat() if nudge.clicked_at else None,
        }

    def track_conversion(
        self,
        member_id: int,
        order_id: Optional[str] = None,
        order_total: Optional[float] = None,
        tracking_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Track that a member made a purchase after receiving a nudge.

        Args:
            member_id: The member ID who converted
            order_id: Shopify order ID (optional)
            order_total: Order total for ROI calculation (optional)
            tracking_id: Specific tracking ID to convert (optional)

        Returns:
            Dict with success status and conversion details
        """
        nudge = None

        if tracking_id:
            nudge = NudgeSent.get_by_tracking_id(tracking_id)
        else:
            # Find most recent nudge for this member within conversion window (7 days)
            conversion_window = datetime.utcnow() - timedelta(days=7)
            nudge = NudgeSent.query.filter(
                NudgeSent.tenant_id == self.tenant_id,
                NudgeSent.member_id == member_id,
                NudgeSent.sent_at >= conversion_window,
                NudgeSent.converted_at.is_(None)
            ).order_by(NudgeSent.sent_at.desc()).first()

        if not nudge:
            return {
                'success': False,
                'error': 'No recent nudge found for this member'
            }

        if nudge.tenant_id != self.tenant_id:
            return {'success': False, 'error': 'Nudge not found'}

        nudge.mark_converted(order_id=order_id, order_total=order_total)

        return {
            'success': True,
            'nudge_id': nudge.id,
            'nudge_type': nudge.nudge_type,
            'converted_at': nudge.converted_at.isoformat() if nudge.converted_at else None,
            'order_id': nudge.order_id,
            'order_total': float(nudge.order_total) if nudge.order_total else None,
        }

    def get_tracking_urls(self, tracking_id: str, base_url: str) -> Dict[str, str]:
        """
        Generate tracking URLs for a nudge email.

        Args:
            tracking_id: The unique tracking ID for this nudge
            base_url: The base URL for the tracking endpoints (e.g., https://app.cardflowlabs.com)

        Returns:
            Dict with tracking pixel URL and click tracking URL template
        """
        return {
            'open_pixel': f"{base_url}/api/nudges/track/open/{tracking_id}",
            'click_url_template': f"{base_url}/api/nudges/track/click/{tracking_id}?url={{url}}",
        }

    def get_roi_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get ROI summary for nudge campaigns.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with ROI calculations
        """
        metrics_by_type = self.get_metrics_by_type(days=days)

        total_revenue = sum(m['total_revenue'] for m in metrics_by_type)
        total_conversions = sum(m['converted'] for m in metrics_by_type)
        total_sent = sum(m['total_sent'] for m in metrics_by_type)

        # Estimate cost at $0.01 per email
        estimated_cost = total_sent * 0.01

        # Calculate ROI percentage
        roi_percentage = 0.0
        if estimated_cost > 0:
            roi_percentage = round((total_revenue - estimated_cost) / estimated_cost * 100, 2)

        return {
            'period_days': days,
            'total_nudges_sent': total_sent,
            'total_conversions': total_conversions,
            'total_revenue': round(total_revenue, 2),
            'estimated_cost': round(estimated_cost, 2),
            'roi_percentage': roi_percentage,
            'revenue_per_nudge': round(total_revenue / total_sent, 2) if total_sent > 0 else 0.0,
            'conversion_rate': round(total_conversions / total_sent * 100, 2) if total_sent > 0 else 0.0,
        }
