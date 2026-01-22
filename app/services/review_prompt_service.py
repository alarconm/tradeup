"""
Review Prompt Service for TradeUp.

Manages the lifecycle of in-app review prompts: determining eligibility,
recording when prompts are shown, and tracking merchant responses.

Story: RC-003 - Create review prompt service
Story: RC-006 - Implement prompt timing logic
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

from app.extensions import db
from app.models.review_prompt import ReviewPrompt, ReviewPromptResponse
from app.services.review_eligibility_service import ReviewEligibilityService

logger = logging.getLogger(__name__)


# Timing constants for optimal prompt display
MIN_SESSIONS_FOR_PROMPT = 5  # Show after 5+ successful sessions
OPTIMAL_HOURS_START = 9  # Don't show before 9am local time
OPTIMAL_HOURS_END = 17  # Don't show after 5pm local time
SESSION_TRACKING_DAYS = 30  # Track sessions within last 30 days


class ReviewPromptService:
    """
    Service for managing review prompt lifecycle.

    Integrates eligibility checking (ReviewEligibilityService) with
    prompt tracking (ReviewPrompt model) to provide a complete
    review collection workflow.

    Story RC-006 adds timing logic:
    - Don't show after error messages
    - Don't show during onboarding
    - Show after successful actions (trade-in approved, member enrolled)
    - Show on dashboard after 5+ successful sessions
    - Respect user's time zone for optimal timing

    Usage:
        service = ReviewPromptService(tenant_id)

        # Check if we should show a prompt
        if service.should_show_prompt():
            # Show the review prompt to the merchant
            prompt_id = service.record_prompt_shown()

            # Later, when they respond
            service.record_prompt_response(prompt_id, 'clicked')

        # View prompt history
        history = service.get_prompt_history()
    """

    def __init__(self, tenant_id: int):
        """
        Initialize the ReviewPromptService.

        Args:
            tenant_id: The tenant ID to manage prompts for
        """
        self.tenant_id = tenant_id
        self._eligibility_service: Optional[ReviewEligibilityService] = None
        self._tenant = None

    @property
    def tenant(self):
        """Lazy load the tenant."""
        if self._tenant is None:
            from app.models.tenant import Tenant
            self._tenant = Tenant.query.get(self.tenant_id)
        return self._tenant

    @property
    def eligibility_service(self) -> ReviewEligibilityService:
        """Lazy load the eligibility service."""
        if self._eligibility_service is None:
            self._eligibility_service = ReviewEligibilityService(self.tenant_id)
        return self._eligibility_service

    def should_show_prompt(
        self,
        context: Optional[str] = None,
        timezone_offset_hours: Optional[int] = None,
        has_recent_error: bool = False
    ) -> bool:
        """
        Determine if a review prompt should be shown to this tenant.

        This combines eligibility criteria (activity metrics, support tickets, errors)
        with prompt cooldown logic and timing considerations.

        Args:
            context: The current context where the prompt would be shown.
                     Valid values: 'dashboard', 'trade_in_approved', 'member_enrolled',
                     'onboarding', 'error'. Defaults to 'dashboard'.
            timezone_offset_hours: User's timezone offset from UTC (e.g., -5 for EST).
                                   Used to determine if it's an optimal time to show prompt.
            has_recent_error: If True, indicates an error just occurred and prompt
                              should not be shown.

        Returns:
            True if a review prompt should be shown, False otherwise
        """
        # RC-006: Don't show after error messages
        if has_recent_error:
            logger.debug(f"Skipping review prompt for tenant {self.tenant_id}: recent error")
            return False

        # RC-006: Don't show during onboarding
        if context == 'onboarding' or self._is_in_onboarding():
            logger.debug(f"Skipping review prompt for tenant {self.tenant_id}: in onboarding")
            return False

        # Check basic eligibility (30+ days, activity thresholds, cooldown, etc.)
        eligibility_result = self.eligibility_service.check_eligibility()
        if not eligibility_result['eligible']:
            return False

        # RC-006: Show on dashboard only after 5+ successful sessions
        if context == 'dashboard' or context is None:
            if not self._has_sufficient_sessions():
                logger.debug(
                    f"Skipping review prompt for tenant {self.tenant_id}: "
                    f"insufficient sessions"
                )
                return False

        # RC-006: Respect user's timezone for optimal timing
        if not self._is_optimal_time(timezone_offset_hours):
            logger.debug(
                f"Skipping review prompt for tenant {self.tenant_id}: "
                f"not optimal time (offset={timezone_offset_hours})"
            )
            return False

        return True

    def _is_in_onboarding(self) -> bool:
        """
        Check if the tenant is still in onboarding.

        Returns:
            True if onboarding is not complete, False otherwise
        """
        if not self.tenant:
            return True  # Assume onboarding if tenant not found

        settings = self.tenant.settings or {}
        return not settings.get('onboarding_complete', False)

    def _has_sufficient_sessions(self) -> bool:
        """
        Check if tenant has had at least MIN_SESSIONS_FOR_PROMPT successful sessions.

        A "session" is tracked by recording successful actions. We count sessions
        where positive actions occurred (trade-ins completed, members enrolled, etc.)

        Returns:
            True if tenant has enough successful sessions, False otherwise
        """
        session_count = self.get_successful_session_count()
        return session_count >= MIN_SESSIONS_FOR_PROMPT

    def _is_optimal_time(self, timezone_offset_hours: Optional[int] = None) -> bool:
        """
        Check if the current time is within optimal hours for showing a prompt.

        Optimal times are business hours (9am-5pm) in the user's local timezone.
        If no timezone is provided, always returns True (don't block the prompt).

        Args:
            timezone_offset_hours: User's timezone offset from UTC (e.g., -5 for EST)

        Returns:
            True if it's an optimal time, False otherwise
        """
        if timezone_offset_hours is None:
            # If we don't know the timezone, don't block the prompt
            return True

        # Calculate local hour
        utc_now = datetime.utcnow()
        local_time = utc_now + timedelta(hours=timezone_offset_hours)
        local_hour = local_time.hour

        # Check if within optimal hours (9am-5pm)
        return OPTIMAL_HOURS_START <= local_hour < OPTIMAL_HOURS_END

    def get_successful_session_count(self) -> int:
        """
        Get the count of successful sessions for this tenant in the last 30 days.

        A session is considered successful if it includes positive actions like:
        - Trade-in batches completed
        - Members enrolled
        - Store credit issued

        This counts distinct dates with activity, not total actions.

        Returns:
            Number of days with successful activity in the tracking period
        """
        from app.models.trade_in import TradeInBatch
        from app.models.member import Member

        cutoff_date = datetime.utcnow() - timedelta(days=SESSION_TRACKING_DAYS)

        # Count distinct days with completed trade-ins
        trade_in_dates = db.session.query(
            db.func.date(TradeInBatch.updated_at)
        ).filter(
            TradeInBatch.tenant_id == self.tenant_id,
            TradeInBatch.status == 'complete',
            TradeInBatch.updated_at >= cutoff_date
        ).distinct().count()

        # Count distinct days with new member enrollments
        member_dates = db.session.query(
            db.func.date(Member.created_at)
        ).filter(
            Member.tenant_id == self.tenant_id,
            Member.status == 'active',
            Member.created_at >= cutoff_date
        ).distinct().count()

        # Return the higher count as a proxy for successful sessions
        # Each day with activity counts as a "session"
        return max(trade_in_dates, member_dates)

    def record_successful_action(self, action_type: str) -> None:
        """
        Record a successful action for session tracking purposes.

        This can be called after successful operations to track merchant engagement.
        The actual session counting is done by get_successful_session_count() which
        queries the database for completed actions.

        Args:
            action_type: Type of action ('trade_in_approved', 'member_enrolled',
                        'credit_issued', etc.)
        """
        # For now, we rely on the existing data models to track sessions.
        # The get_successful_session_count() method queries TradeInBatch and Member
        # tables to determine session count.
        #
        # This method is provided as a hook for future enhancements where we might
        # want to track additional session-related data.
        logger.debug(
            f"Successful action recorded for tenant {self.tenant_id}: {action_type}"
        )

    def get_timing_context(
        self,
        timezone_offset_hours: Optional[int] = None,
        context: Optional[str] = None,
        has_recent_error: bool = False
    ) -> Dict[str, Any]:
        """
        Get detailed timing context for debugging and frontend display.

        Returns information about why a prompt can or cannot be shown at this time.

        Args:
            timezone_offset_hours: User's timezone offset from UTC
            context: Current context ('dashboard', 'trade_in_approved', etc.)
            has_recent_error: Whether a recent error occurred

        Returns:
            Dict with timing details
        """
        eligibility = self.eligibility_service.check_eligibility()
        session_count = self.get_successful_session_count()
        is_in_onboarding = self._is_in_onboarding()
        is_optimal_time = self._is_optimal_time(timezone_offset_hours)

        # Determine blocking reasons
        blocking_reasons = []
        if has_recent_error:
            blocking_reasons.append('Recent error occurred')
        if is_in_onboarding:
            blocking_reasons.append('Still in onboarding')
        if not eligibility['eligible']:
            blocking_reasons.append(eligibility.get('reason', 'Eligibility check failed'))
        if context == 'dashboard' and session_count < MIN_SESSIONS_FOR_PROMPT:
            blocking_reasons.append(
                f'Insufficient sessions ({session_count}/{MIN_SESSIONS_FOR_PROMPT})'
            )
        if not is_optimal_time:
            blocking_reasons.append('Not optimal time of day')

        return {
            'can_show': len(blocking_reasons) == 0,
            'blocking_reasons': blocking_reasons,
            'context': context or 'dashboard',
            'session_count': session_count,
            'min_sessions_required': MIN_SESSIONS_FOR_PROMPT,
            'is_in_onboarding': is_in_onboarding,
            'is_optimal_time': is_optimal_time,
            'timezone_offset_hours': timezone_offset_hours,
            'optimal_hours': f'{OPTIMAL_HOURS_START}:00 - {OPTIMAL_HOURS_END}:00',
            'eligibility': eligibility
        }

    def get_eligibility_details(self) -> Dict[str, Any]:
        """
        Get detailed eligibility information for debugging or display.

        Returns:
            Dict with full eligibility criteria breakdown
        """
        return self.eligibility_service.check_eligibility()

    def record_prompt_shown(self) -> Optional[int]:
        """
        Record that a review prompt was shown to the merchant.

        Creates a new ReviewPrompt record with the current timestamp.
        Should only be called after should_show_prompt() returns True.

        Returns:
            The ID of the created prompt record, or None if creation failed
        """
        try:
            # Verify we should show the prompt (extra safety check)
            if not self.should_show_prompt():
                logger.warning(
                    f"record_prompt_shown called when not eligible for tenant {self.tenant_id}"
                )
                # Still allow recording if explicitly called
                # This prevents data loss if UI is out of sync

            prompt = ReviewPrompt.create_prompt(self.tenant_id)
            db.session.commit()

            logger.info(f"Recorded review prompt shown for tenant {self.tenant_id}, prompt_id={prompt.id}")
            return prompt.id

        except Exception as e:
            logger.error(f"Failed to record prompt shown for tenant {self.tenant_id}: {e}")
            db.session.rollback()
            return None

    def record_prompt_response(
        self,
        prompt_id: int,
        response: str
    ) -> Dict[str, Any]:
        """
        Record a merchant's response to a review prompt.

        Args:
            prompt_id: The ID of the prompt being responded to
            response: One of 'dismissed', 'clicked', 'reminded_later'

        Returns:
            Dict with success status and details
        """
        # Validate response value
        valid_responses = [r.value for r in ReviewPromptResponse]
        if response not in valid_responses:
            return {
                'success': False,
                'error': f"Invalid response. Must be one of: {', '.join(valid_responses)}"
            }

        try:
            prompt = ReviewPrompt.query.filter_by(
                id=prompt_id,
                tenant_id=self.tenant_id
            ).first()

            if not prompt:
                return {
                    'success': False,
                    'error': f"Prompt {prompt_id} not found for tenant {self.tenant_id}"
                }

            # Check if already responded
            if prompt.response:
                return {
                    'success': False,
                    'error': f"Prompt already has response: {prompt.response}",
                    'existing_response': prompt.response
                }

            # Record the response
            prompt.record_response(ReviewPromptResponse(response))
            db.session.commit()

            logger.info(
                f"Recorded review prompt response for tenant {self.tenant_id}: "
                f"prompt_id={prompt_id}, response={response}"
            )

            return {
                'success': True,
                'prompt_id': prompt_id,
                'response': response,
                'responded_at': prompt.responded_at.isoformat() if prompt.responded_at else None
            }

        except Exception as e:
            logger.error(
                f"Failed to record prompt response for tenant {self.tenant_id}, "
                f"prompt_id={prompt_id}: {e}"
            )
            db.session.rollback()
            return {
                'success': False,
                'error': 'Failed to record response'
            }

    def get_prompt_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the review prompt history for this tenant.

        Args:
            limit: Maximum number of records to return (default 10)

        Returns:
            List of prompt records as dicts, most recent first
        """
        prompts = ReviewPrompt.get_prompt_history(self.tenant_id, limit=limit)
        return [prompt.to_dict() for prompt in prompts]

    def get_last_prompt(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent review prompt for this tenant.

        Returns:
            Dict of the last prompt, or None if no prompts exist
        """
        history = self.get_prompt_history(limit=1)
        return history[0] if history else None

    def get_prompt_stats(self) -> Dict[str, Any]:
        """
        Get statistics about review prompts for this tenant.

        Returns:
            Dict with prompt statistics
        """
        all_prompts = ReviewPrompt.query.filter_by(tenant_id=self.tenant_id).all()

        total_prompts = len(all_prompts)
        total_responses = sum(1 for p in all_prompts if p.response)
        responses_by_type = {}

        for prompt in all_prompts:
            if prompt.response:
                responses_by_type[prompt.response] = responses_by_type.get(prompt.response, 0) + 1

        last_prompt = self.get_last_prompt()
        eligibility = self.eligibility_service.get_eligibility_summary()

        return {
            'total_prompts_shown': total_prompts,
            'total_responses': total_responses,
            'response_rate': round(total_responses / total_prompts * 100, 1) if total_prompts > 0 else 0,
            'responses_by_type': responses_by_type,
            'clicked_count': responses_by_type.get('clicked', 0),
            'dismissed_count': responses_by_type.get('dismissed', 0),
            'reminded_later_count': responses_by_type.get('reminded_later', 0),
            'last_prompt': last_prompt,
            'currently_eligible': eligibility['eligible'],
            'eligibility_summary': eligibility
        }


def should_show_review_prompt(tenant_id: int) -> bool:
    """
    Convenience function to check if a review prompt should be shown.

    Args:
        tenant_id: The tenant ID to check

    Returns:
        True if a prompt should be shown, False otherwise
    """
    service = ReviewPromptService(tenant_id)
    return service.should_show_prompt()


def record_review_prompt_shown(tenant_id: int) -> Optional[int]:
    """
    Convenience function to record a prompt being shown.

    Args:
        tenant_id: The tenant ID

    Returns:
        The prompt ID, or None if creation failed
    """
    service = ReviewPromptService(tenant_id)
    return service.record_prompt_shown()


def record_review_prompt_response(tenant_id: int, prompt_id: int, response: str) -> Dict[str, Any]:
    """
    Convenience function to record a prompt response.

    Args:
        tenant_id: The tenant ID
        prompt_id: The prompt ID
        response: The response type

    Returns:
        Dict with success status
    """
    service = ReviewPromptService(tenant_id)
    return service.record_prompt_response(prompt_id, response)


def get_aggregate_review_metrics(
    days: int = 30,
    tenant_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get aggregate review prompt metrics across all tenants (or a specific tenant).

    Story: RC-007 - Track review conversion metrics

    This provides metrics for:
    - Total prompt impressions
    - Rate Now (clicked) count and rate
    - Dismiss count and rate
    - Remind Later count and rate
    - Conversion funnel breakdown

    Args:
        days: Number of days to look back (default 30, 0 for all time)
        tenant_id: Optional tenant ID to filter by (None for all tenants)

    Returns:
        Dict with aggregate metrics
    """
    from sqlalchemy import func
    from datetime import timedelta

    # Build base query
    query = db.session.query(ReviewPrompt)

    if tenant_id is not None:
        query = query.filter(ReviewPrompt.tenant_id == tenant_id)

    if days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(ReviewPrompt.prompt_shown_at >= cutoff)

    all_prompts = query.all()

    # Calculate metrics
    total_impressions = len(all_prompts)
    prompts_with_response = [p for p in all_prompts if p.response]
    total_responses = len(prompts_with_response)

    # Count by response type
    clicked_count = sum(1 for p in all_prompts if p.response == 'clicked')
    dismissed_count = sum(1 for p in all_prompts if p.response == 'dismissed')
    reminded_later_count = sum(1 for p in all_prompts if p.response == 'reminded_later')
    no_response_count = total_impressions - total_responses

    # Calculate rates (as percentages)
    def rate(count: int) -> float:
        if total_impressions == 0:
            return 0.0
        return round((count / total_impressions) * 100, 1)

    # Get daily breakdown for trend analysis
    daily_breakdown = {}
    for prompt in all_prompts:
        date_key = prompt.prompt_shown_at.strftime('%Y-%m-%d')
        if date_key not in daily_breakdown:
            daily_breakdown[date_key] = {
                'impressions': 0,
                'clicked': 0,
                'dismissed': 0,
                'reminded_later': 0
            }
        daily_breakdown[date_key]['impressions'] += 1
        if prompt.response == 'clicked':
            daily_breakdown[date_key]['clicked'] += 1
        elif prompt.response == 'dismissed':
            daily_breakdown[date_key]['dismissed'] += 1
        elif prompt.response == 'reminded_later':
            daily_breakdown[date_key]['reminded_later'] += 1

    # Sort daily breakdown by date
    sorted_daily = sorted(daily_breakdown.items(), key=lambda x: x[0])
    daily_trend = [
        {
            'date': date,
            **metrics
        }
        for date, metrics in sorted_daily
    ]

    # Get unique tenant count
    unique_tenants = len(set(p.tenant_id for p in all_prompts))

    return {
        'period_days': days if days > 0 else 'all_time',
        'tenant_id': tenant_id,

        # Core metrics (RC-007 acceptance criteria)
        'total_impressions': total_impressions,
        'clicked_count': clicked_count,
        'dismissed_count': dismissed_count,
        'reminded_later_count': reminded_later_count,
        'no_response_count': no_response_count,

        # Rates
        'click_rate': rate(clicked_count),
        'dismiss_rate': rate(dismissed_count),
        'remind_later_rate': rate(reminded_later_count),
        'response_rate': rate(total_responses),

        # Conversion funnel
        'funnel': {
            'impressions': total_impressions,
            'engaged': total_responses,
            'converted': clicked_count,
            'engagement_rate': rate(total_responses),
            'conversion_rate': rate(clicked_count)
        },

        # Context
        'unique_tenants': unique_tenants,
        'daily_trend': daily_trend[-30:],  # Last 30 days of trends
        'summary': (
            f"{total_impressions} prompts shown, "
            f"{clicked_count} clicked ({rate(clicked_count)}%), "
            f"{dismissed_count} dismissed ({rate(dismissed_count)}%)"
        )
    }
