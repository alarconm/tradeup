"""
Review Prompt API Endpoints

API endpoints for checking eligibility and recording review prompt responses.

Story: RC-005 - Add API endpoint for review prompt
Story: RC-006 - Implement prompt timing logic
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from app.services.review_prompt_service import ReviewPromptService

review_prompt_bp = Blueprint('review_prompt', __name__)


def get_service() -> ReviewPromptService:
    """Get review prompt service for current tenant."""
    return ReviewPromptService(g.tenant.id)


@review_prompt_bp.route('/check', methods=['GET'])
@require_shopify_auth
def check_review_prompt():
    """
    Check if a review prompt should be shown to the merchant.

    Returns eligibility status and timing context about why or why not
    the prompt should be shown.

    Query params (all optional):
        context: Current page context ('dashboard', 'trade_in_approved',
                 'member_enrolled', 'onboarding'). Defaults to 'dashboard'.
        timezone_offset: User's timezone offset from UTC in hours (e.g., -5 for EST).
                         Used for optimal timing calculation.
        has_error: Set to 'true' if an error just occurred. Prompt will not show.

    Response:
        {
            "should_show": true/false,
            "timing_context": {
                "can_show": true/false,
                "blocking_reasons": [...],
                "session_count": 5,
                "min_sessions_required": 5,
                "is_in_onboarding": false,
                "is_optimal_time": true,
                ...
            },
            "eligibility": {
                "eligible": true/false,
                "criteria": {...}
            }
        }
    """
    service = get_service()

    # RC-006: Get timing parameters from query string
    context = request.args.get('context', 'dashboard')
    timezone_offset = request.args.get('timezone_offset', type=int)
    has_error = request.args.get('has_error', 'false').lower() == 'true'

    # Check with timing logic
    should_show = service.should_show_prompt(
        context=context,
        timezone_offset_hours=timezone_offset,
        has_recent_error=has_error
    )

    # Get detailed timing context for frontend
    timing_context = service.get_timing_context(
        timezone_offset_hours=timezone_offset,
        context=context,
        has_recent_error=has_error
    )

    # Get basic eligibility for backwards compatibility
    eligibility = service.get_eligibility_details()

    return jsonify({
        'should_show': should_show,
        'timing_context': timing_context,
        'eligibility': eligibility,
    })


@review_prompt_bp.route('/shown', methods=['POST'])
@require_shopify_auth
def record_prompt_shown():
    """
    Record that a review prompt was shown to the merchant.

    Creates a new ReviewPrompt record with the current timestamp.
    Should be called when the prompt modal is displayed.

    Response:
        {
            "success": true/false,
            "prompt_id": 123
        }
    """
    service = get_service()
    prompt_id = service.record_prompt_shown()

    if prompt_id is None:
        return jsonify({
            'success': False,
            'error': 'Failed to record prompt shown',
        }), 500

    return jsonify({
        'success': True,
        'prompt_id': prompt_id,
    })


@review_prompt_bp.route('/response', methods=['POST'])
@require_shopify_auth
def record_prompt_response():
    """
    Record the merchant's response to a review prompt.

    Request body:
        {
            "prompt_id": 123,
            "response": "clicked" | "dismissed" | "reminded_later"
        }

    Response:
        {
            "success": true/false,
            "prompt_id": 123,
            "response": "clicked",
            "responded_at": "2026-01-21T12:00:00"
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided',
        }), 400

    prompt_id = data.get('prompt_id')
    response = data.get('response')

    if not prompt_id:
        return jsonify({
            'success': False,
            'error': 'prompt_id is required',
        }), 400

    if not response:
        return jsonify({
            'success': False,
            'error': 'response is required',
        }), 400

    service = get_service()
    result = service.record_prompt_response(prompt_id, response)

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@review_prompt_bp.route('/history', methods=['GET'])
@require_shopify_auth
def get_prompt_history():
    """
    Get the review prompt history for the current tenant.

    Query params:
        limit: Maximum number of records to return (default 10)

    Response:
        {
            "success": true,
            "prompts": [...]
        }
    """
    limit = request.args.get('limit', 10, type=int)

    service = get_service()
    prompts = service.get_prompt_history(limit=limit)

    return jsonify({
        'success': True,
        'prompts': prompts,
    })


@review_prompt_bp.route('/stats', methods=['GET'])
@require_shopify_auth
def get_prompt_stats():
    """
    Get review prompt statistics for the current tenant.

    Response:
        {
            "success": true,
            "stats": {
                "total_prompts_shown": 5,
                "total_responses": 3,
                "response_rate": 60.0,
                "clicked_count": 1,
                "dismissed_count": 1,
                "reminded_later_count": 1,
                ...
            }
        }
    """
    service = get_service()
    stats = service.get_prompt_stats()

    return jsonify({
        'success': True,
        'stats': stats,
    })


@review_prompt_bp.route('/session-count', methods=['GET'])
@require_shopify_auth
def get_session_count():
    """
    Get the successful session count for the current tenant.

    This is used by the frontend to determine if enough sessions have
    occurred to warrant showing a review prompt on the dashboard.

    Response:
        {
            "success": true,
            "session_count": 5,
            "min_sessions_required": 5,
            "has_sufficient_sessions": true
        }
    """
    from app.services.review_prompt_service import MIN_SESSIONS_FOR_PROMPT

    service = get_service()
    session_count = service.get_successful_session_count()

    return jsonify({
        'success': True,
        'session_count': session_count,
        'min_sessions_required': MIN_SESSIONS_FOR_PROMPT,
        'has_sufficient_sessions': session_count >= MIN_SESSIONS_FOR_PROMPT,
    })


@review_prompt_bp.route('/action', methods=['POST'])
@require_shopify_auth
def record_successful_action():
    """
    Record a successful action for session tracking.

    This endpoint is called after successful operations to track merchant
    engagement and determine when to show review prompts.

    Request body:
        {
            "action_type": "trade_in_approved" | "member_enrolled" | "credit_issued"
        }

    Response:
        {
            "success": true,
            "action_type": "trade_in_approved"
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided',
        }), 400

    action_type = data.get('action_type')
    if not action_type:
        return jsonify({
            'success': False,
            'error': 'action_type is required',
        }), 400

    valid_actions = ['trade_in_approved', 'member_enrolled', 'credit_issued']
    if action_type not in valid_actions:
        return jsonify({
            'success': False,
            'error': f'Invalid action_type. Must be one of: {", ".join(valid_actions)}',
        }), 400

    service = get_service()
    service.record_successful_action(action_type)

    return jsonify({
        'success': True,
        'action_type': action_type,
    })


@review_prompt_bp.route('/metrics', methods=['GET'])
@require_shopify_auth
def get_review_metrics():
    """
    Get aggregate review prompt conversion metrics.

    Story: RC-007 - Track review conversion metrics

    Provides metrics for tracking how many prompts convert to actual reviews:
    - Total prompt impressions
    - Rate Now (clicked) count and rate
    - Dismiss count and rate
    - Remind Later count and rate
    - Conversion funnel breakdown

    Query params:
        days: Number of days to look back (default 30, 0 for all time)
        scope: 'tenant' for current tenant only, 'all' for aggregate (default 'tenant')

    Response:
        {
            "success": true,
            "metrics": {
                "total_impressions": 100,
                "clicked_count": 15,
                "click_rate": 15.0,
                "dismissed_count": 45,
                "dismiss_rate": 45.0,
                "reminded_later_count": 20,
                "remind_later_rate": 20.0,
                "no_response_count": 20,
                "response_rate": 80.0,
                "funnel": {...},
                "daily_trend": [...],
                "summary": "100 prompts shown, 15 clicked (15.0%), 45 dismissed (45.0%)"
            }
        }
    """
    from app.services.review_prompt_service import get_aggregate_review_metrics

    days = request.args.get('days', 30, type=int)
    scope = request.args.get('scope', 'tenant')

    # Determine tenant filtering
    tenant_id = None
    if scope == 'tenant':
        tenant_id = g.tenant.id

    metrics = get_aggregate_review_metrics(days=days, tenant_id=tenant_id)

    return jsonify({
        'success': True,
        'metrics': metrics,
    })
