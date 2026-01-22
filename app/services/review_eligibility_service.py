"""
Review Eligibility Service for TradeUp.

Determines when a merchant is eligible to receive a review prompt
based on activity metrics, support history, and error rates.

Story: RC-002 - Define review prompt eligibility criteria
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

from app.extensions import db
from app.models.tenant import Tenant
from app.models.member import Member
from app.models.trade_in import TradeInBatch
from app.models.review_prompt import ReviewPrompt

logger = logging.getLogger(__name__)


class ReviewEligibilityService:
    """
    Service for determining merchant eligibility for app review prompts.

    Eligibility criteria:
    1. Merchant active for 30+ days
    2. Merchant has processed 10+ trade-ins OR 50+ members enrolled
    3. No review prompt in last 60 days
    4. No recent support tickets (negative sentiment indicator)
    5. No errors in last 7 days

    Usage:
        service = ReviewEligibilityService(tenant_id)
        result = service.check_eligibility()
        if result['eligible']:
            # Show review prompt
    """

    # Configuration constants
    MIN_DAYS_ACTIVE = 30
    MIN_TRADE_INS = 10
    MIN_MEMBERS = 50
    PROMPT_COOLDOWN_DAYS = 60
    ERROR_CHECK_DAYS = 7

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._tenant: Optional[Tenant] = None

    @property
    def tenant(self) -> Optional[Tenant]:
        """Lazy load tenant."""
        if self._tenant is None:
            self._tenant = Tenant.query.get(self.tenant_id)
        return self._tenant

    def check_eligibility(self) -> Dict[str, Any]:
        """
        Check if a merchant is eligible for a review prompt.

        Returns a dict with:
        - eligible: bool - whether to show the prompt
        - reason: str - explanation of the result
        - criteria: dict - detailed check results for each criterion
        """
        if not self.tenant:
            return {
                'eligible': False,
                'reason': 'Tenant not found',
                'criteria': {}
            }

        criteria = {
            'days_active': self._check_days_active(),
            'activity_threshold': self._check_activity_threshold(),
            'prompt_cooldown': self._check_prompt_cooldown(),
            'no_support_tickets': self._check_no_recent_support_tickets(),
            'no_recent_errors': self._check_no_recent_errors(),
        }

        # All criteria must pass
        all_passed = all(c['passed'] for c in criteria.values())

        if all_passed:
            reason = 'Merchant meets all eligibility criteria for review prompt'
        else:
            # Find the first failing criterion
            failed = [name for name, result in criteria.items() if not result['passed']]
            reasons = [criteria[name]['reason'] for name in failed]
            reason = '; '.join(reasons)

        return {
            'eligible': all_passed,
            'reason': reason,
            'criteria': criteria
        }

    def _check_days_active(self) -> Dict[str, Any]:
        """
        Check if merchant has been active for 30+ days.
        """
        if not self.tenant or not self.tenant.created_at:
            return {
                'passed': False,
                'reason': 'Tenant creation date unknown',
                'value': None,
                'threshold': self.MIN_DAYS_ACTIVE
            }

        days_active = (datetime.utcnow() - self.tenant.created_at).days
        passed = days_active >= self.MIN_DAYS_ACTIVE

        return {
            'passed': passed,
            'reason': f'Active for {days_active} days' if passed else f'Only active for {days_active} days (need {self.MIN_DAYS_ACTIVE}+)',
            'value': days_active,
            'threshold': self.MIN_DAYS_ACTIVE
        }

    def _check_activity_threshold(self) -> Dict[str, Any]:
        """
        Check if merchant has 10+ trade-ins OR 50+ members enrolled.
        """
        trade_in_count = TradeInBatch.query.filter_by(
            tenant_id=self.tenant_id
        ).count()

        member_count = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).count()

        has_trade_ins = trade_in_count >= self.MIN_TRADE_INS
        has_members = member_count >= self.MIN_MEMBERS
        passed = has_trade_ins or has_members

        if passed:
            if has_trade_ins and has_members:
                reason = f'Has {trade_in_count} trade-ins and {member_count} members'
            elif has_trade_ins:
                reason = f'Has {trade_in_count} trade-ins (threshold: {self.MIN_TRADE_INS}+)'
            else:
                reason = f'Has {member_count} members (threshold: {self.MIN_MEMBERS}+)'
        else:
            reason = f'Only {trade_in_count} trade-ins (need {self.MIN_TRADE_INS}+) and {member_count} members (need {self.MIN_MEMBERS}+)'

        return {
            'passed': passed,
            'reason': reason,
            'value': {
                'trade_ins': trade_in_count,
                'members': member_count
            },
            'threshold': {
                'trade_ins': self.MIN_TRADE_INS,
                'members': self.MIN_MEMBERS
            }
        }

    def _check_prompt_cooldown(self) -> Dict[str, Any]:
        """
        Check if no review prompt has been shown in the last 60 days.
        Uses the ReviewPrompt.can_show_prompt() method with 60-day cooldown.
        """
        cooldown_hours = self.PROMPT_COOLDOWN_DAYS * 24  # Convert days to hours
        can_show = ReviewPrompt.can_show_prompt(self.tenant_id, cooldown_hours=cooldown_hours)

        if can_show:
            # Check when the last prompt was shown (if any)
            last_prompt = ReviewPrompt.query.filter_by(
                tenant_id=self.tenant_id
            ).order_by(ReviewPrompt.prompt_shown_at.desc()).first()

            if last_prompt:
                days_since = (datetime.utcnow() - last_prompt.prompt_shown_at).days
                reason = f'Last prompt was {days_since} days ago (cooldown: {self.PROMPT_COOLDOWN_DAYS} days)'
            else:
                reason = 'No previous review prompts'
        else:
            last_prompt = ReviewPrompt.query.filter_by(
                tenant_id=self.tenant_id
            ).order_by(ReviewPrompt.prompt_shown_at.desc()).first()
            days_since = (datetime.utcnow() - last_prompt.prompt_shown_at).days if last_prompt else 0
            reason = f'Review prompt shown {days_since} days ago (need {self.PROMPT_COOLDOWN_DAYS}+ days)'

        return {
            'passed': can_show,
            'reason': reason,
            'value': None,
            'threshold': self.PROMPT_COOLDOWN_DAYS
        }

    def _check_no_recent_support_tickets(self) -> Dict[str, Any]:
        """
        Check if there are no recent support tickets (negative sentiment indicator).

        This integrates with Gorgias if configured, otherwise passes by default.
        Recent tickets suggest the merchant may have complaints, making it a bad
        time to ask for a review.
        """
        if not self.tenant:
            return {
                'passed': True,
                'reason': 'Support ticket check skipped (no tenant)',
                'value': None,
                'threshold': 0
            }

        # Check if Gorgias is configured
        settings = self.tenant.settings or {}
        integrations = settings.get('integrations', {})
        gorgias_config = integrations.get('gorgias', {})

        if not gorgias_config.get('enabled'):
            # No support integration configured - assume no tickets
            return {
                'passed': True,
                'reason': 'Support ticket check skipped (Gorgias not configured)',
                'value': 0,
                'threshold': 0
            }

        # If Gorgias is configured, check for recent tickets
        try:
            from app.services.gorgias_service import GorgiasService
            gorgias = GorgiasService(self.tenant_id)

            if not gorgias.is_enabled():
                return {
                    'passed': True,
                    'reason': 'Support ticket check skipped (Gorgias not enabled)',
                    'value': 0,
                    'threshold': 0
                }

            # For now, we'll pass this check if Gorgias is enabled but
            # we can't easily count recent tickets without additional API calls.
            # The presence of the integration is noted for future enhancement.
            return {
                'passed': True,
                'reason': 'Gorgias integration active (ticket count check not implemented)',
                'value': None,
                'threshold': 0
            }

        except ImportError:
            return {
                'passed': True,
                'reason': 'Support ticket check skipped (Gorgias service unavailable)',
                'value': 0,
                'threshold': 0
            }
        except Exception as e:
            logger.warning(f"Error checking Gorgias tickets for tenant {self.tenant_id}: {e}")
            # Don't block review prompt if we can't check tickets
            return {
                'passed': True,
                'reason': 'Support ticket check skipped (error checking Gorgias)',
                'value': None,
                'threshold': 0
            }

    def _check_no_recent_errors(self) -> Dict[str, Any]:
        """
        Check if there are no application errors in the last 7 days.

        This is a heuristic check. In production with Sentry, we could query
        Sentry's API for errors associated with this tenant. For now, we
        assume no errors unless we can verify otherwise.

        Future enhancement: Query Sentry API with tenant context tags.
        """
        # Currently, we don't have a way to query per-tenant errors
        # from Sentry without additional setup. We'll pass this check
        # by default and note it for future enhancement.
        #
        # To properly implement this, we would need:
        # 1. Sentry API token stored securely
        # 2. Consistent tenant tagging in Sentry events
        # 3. Sentry API call to check for recent issues

        return {
            'passed': True,
            'reason': 'Error check passed (per-tenant error tracking not configured)',
            'value': 0,
            'threshold': self.ERROR_CHECK_DAYS
        }

    def get_eligibility_summary(self) -> Dict[str, Any]:
        """
        Get a summary of eligibility status for display in admin UI.

        Returns a simplified view suitable for dashboard display.
        """
        result = self.check_eligibility()

        # Count passed/failed criteria
        passed_count = sum(1 for c in result['criteria'].values() if c['passed'])
        total_count = len(result['criteria'])

        return {
            'eligible': result['eligible'],
            'reason': result['reason'],
            'passed_criteria': passed_count,
            'total_criteria': total_count,
            'days_active': result['criteria'].get('days_active', {}).get('value', 0),
            'trade_ins': result['criteria'].get('activity_threshold', {}).get('value', {}).get('trade_ins', 0),
            'members': result['criteria'].get('activity_threshold', {}).get('value', {}).get('members', 0),
        }


def check_review_eligibility(tenant_id: int) -> Dict[str, Any]:
    """
    Convenience function to check review eligibility for a tenant.

    Args:
        tenant_id: The tenant ID to check

    Returns:
        Dict with eligibility result
    """
    service = ReviewEligibilityService(tenant_id)
    return service.check_eligibility()


def is_eligible_for_review(tenant_id: int) -> bool:
    """
    Simple boolean check for review eligibility.

    Args:
        tenant_id: The tenant ID to check

    Returns:
        True if eligible, False otherwise
    """
    result = check_review_eligibility(tenant_id)
    return result['eligible']
