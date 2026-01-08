"""
CLI Commands for TradeUp.

Provides Flask CLI commands for scheduled tasks and administration.

Usage:
    flask tiers process-expirations    # Process expired tier assignments
    flask tiers check-eligibility      # Check activity-based eligibility
    flask tiers stats --tenant-id 1    # Show tier statistics

    flask scheduled monthly-credits --tenant-id 1     # Distribute monthly credits
    flask scheduled expire-credits --tenant-id 1      # Expire old credits
    flask scheduled expiration-warnings --tenant-id 1 # Preview expiring credits
    flask scheduled referral-stats --tenant-id 1      # Referral program stats
"""
from .tiers import init_app as init_tier_commands
from .scheduled import init_app as init_scheduled_commands


def init_app(app):
    """Register all CLI commands with the Flask app."""
    init_tier_commands(app)
    init_scheduled_commands(app)
