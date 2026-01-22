"""
Tests for ReviewPromptService.

Story: RC-003 - Create review prompt service
"""
import pytest
from datetime import datetime, timedelta

from app.extensions import db
from app.models.review_prompt import ReviewPrompt, ReviewPromptResponse
from app.services.review_prompt_service import (
    ReviewPromptService,
    should_show_review_prompt,
    record_review_prompt_shown,
    record_review_prompt_response
)


class TestReviewPromptService:
    """Tests for ReviewPromptService class."""

    def test_service_initialization(self, app, sample_tenant):
        """Test service initializes with tenant_id."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)
            assert service.tenant_id == sample_tenant.id

    def test_should_show_prompt_new_tenant(self, app, sample_tenant):
        """Test should_show_prompt returns False for new tenant (< 30 days)."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)
            # New tenant doesn't meet the 30-day requirement
            result = service.should_show_prompt()
            assert result is False

    def test_should_show_prompt_eligible_tenant(self, app, sample_tenant):
        """Test should_show_prompt returns True for eligible tenant."""
        from app.models import TradeInBatch, Tenant
        with app.app_context():
            # Make tenant 30+ days old
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.created_at = datetime.utcnow() - timedelta(days=35)

            # Add 10+ trade-ins to meet activity threshold
            for i in range(12):
                batch = TradeInBatch(
                    tenant_id=sample_tenant.id,
                    batch_reference=f'TB-TEST-{i}',
                    status='completed',
                    total_items=1,
                    total_trade_value=100
                )
                db.session.add(batch)
            db.session.commit()

            service = ReviewPromptService(sample_tenant.id)
            result = service.should_show_prompt()
            assert result is True

    def test_get_eligibility_details(self, app, sample_tenant):
        """Test get_eligibility_details returns detailed criteria."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)
            details = service.get_eligibility_details()

            assert 'eligible' in details
            assert 'reason' in details
            assert 'criteria' in details
            assert 'days_active' in details['criteria']
            assert 'activity_threshold' in details['criteria']

    def test_record_prompt_shown(self, app, sample_tenant):
        """Test recording a prompt being shown."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)
            prompt_id = service.record_prompt_shown()

            assert prompt_id is not None
            prompt = ReviewPrompt.query.get(prompt_id)
            assert prompt is not None
            assert prompt.tenant_id == sample_tenant.id
            assert prompt.prompt_shown_at is not None
            assert prompt.response is None

    def test_record_prompt_response_clicked(self, app, sample_tenant):
        """Test recording 'clicked' response."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)
            prompt_id = service.record_prompt_shown()

            result = service.record_prompt_response(prompt_id, 'clicked')

            assert result['success'] is True
            assert result['response'] == 'clicked'

            prompt = ReviewPrompt.query.get(prompt_id)
            assert prompt.response == 'clicked'
            assert prompt.responded_at is not None

    def test_record_prompt_response_dismissed(self, app, sample_tenant):
        """Test recording 'dismissed' response."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)
            prompt_id = service.record_prompt_shown()

            result = service.record_prompt_response(prompt_id, 'dismissed')

            assert result['success'] is True
            assert result['response'] == 'dismissed'

    def test_record_prompt_response_reminded_later(self, app, sample_tenant):
        """Test recording 'reminded_later' response."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)
            prompt_id = service.record_prompt_shown()

            result = service.record_prompt_response(prompt_id, 'reminded_later')

            assert result['success'] is True
            assert result['response'] == 'reminded_later'

    def test_record_prompt_response_invalid(self, app, sample_tenant):
        """Test recording invalid response fails."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)
            prompt_id = service.record_prompt_shown()

            result = service.record_prompt_response(prompt_id, 'invalid_response')

            assert result['success'] is False
            assert 'Invalid response' in result['error']

    def test_record_prompt_response_not_found(self, app, sample_tenant):
        """Test recording response for non-existent prompt fails."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)

            result = service.record_prompt_response(99999, 'clicked')

            assert result['success'] is False
            assert 'not found' in result['error']

    def test_record_prompt_response_already_responded(self, app, sample_tenant):
        """Test recording response twice fails."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)
            prompt_id = service.record_prompt_shown()

            # First response
            service.record_prompt_response(prompt_id, 'clicked')

            # Second response should fail
            result = service.record_prompt_response(prompt_id, 'dismissed')

            assert result['success'] is False
            assert 'already has response' in result['error']

    def test_get_prompt_history(self, app, sample_tenant):
        """Test getting prompt history."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)

            # Create multiple prompts
            prompt_ids = []
            for i in range(3):
                prompt_id = service.record_prompt_shown()
                prompt_ids.append(prompt_id)

            history = service.get_prompt_history(limit=10)

            assert len(history) == 3
            # Most recent first
            assert history[0]['id'] == prompt_ids[2]

    def test_get_prompt_history_limit(self, app, sample_tenant):
        """Test prompt history respects limit."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)

            # Create 5 prompts
            for i in range(5):
                service.record_prompt_shown()

            history = service.get_prompt_history(limit=2)

            assert len(history) == 2

    def test_get_last_prompt(self, app, sample_tenant):
        """Test getting the last prompt."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)

            # No prompts yet
            assert service.get_last_prompt() is None

            # Create a prompt
            prompt_id = service.record_prompt_shown()

            last_prompt = service.get_last_prompt()
            assert last_prompt is not None
            assert last_prompt['id'] == prompt_id

    def test_get_prompt_stats(self, app, sample_tenant):
        """Test getting prompt statistics."""
        with app.app_context():
            service = ReviewPromptService(sample_tenant.id)

            # Create prompts with different responses
            prompt1 = service.record_prompt_shown()
            service.record_prompt_response(prompt1, 'clicked')

            prompt2 = service.record_prompt_shown()
            service.record_prompt_response(prompt2, 'dismissed')

            prompt3 = service.record_prompt_shown()
            # No response yet

            stats = service.get_prompt_stats()

            assert stats['total_prompts_shown'] == 3
            assert stats['total_responses'] == 2
            assert stats['clicked_count'] == 1
            assert stats['dismissed_count'] == 1
            assert stats['reminded_later_count'] == 0
            assert stats['response_rate'] == round(2/3 * 100, 1)


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_should_show_review_prompt(self, app, sample_tenant):
        """Test should_show_review_prompt convenience function."""
        with app.app_context():
            result = should_show_review_prompt(sample_tenant.id)
            assert isinstance(result, bool)

    def test_record_review_prompt_shown(self, app, sample_tenant):
        """Test record_review_prompt_shown convenience function."""
        with app.app_context():
            prompt_id = record_review_prompt_shown(sample_tenant.id)
            assert prompt_id is not None

    def test_record_review_prompt_response(self, app, sample_tenant):
        """Test record_review_prompt_response convenience function."""
        with app.app_context():
            prompt_id = record_review_prompt_shown(sample_tenant.id)
            result = record_review_prompt_response(sample_tenant.id, prompt_id, 'clicked')
            assert result['success'] is True


class TestPromptCooldown:
    """Tests for prompt cooldown behavior."""

    def test_cooldown_prevents_immediate_prompt(self, app, sample_tenant):
        """Test that showing a prompt prevents showing another immediately."""
        from app.models import Tenant, TradeInBatch
        with app.app_context():
            # Make tenant eligible
            tenant = Tenant.query.get(sample_tenant.id)
            tenant.created_at = datetime.utcnow() - timedelta(days=35)

            for i in range(12):
                batch = TradeInBatch(
                    tenant_id=sample_tenant.id,
                    batch_reference=f'TB-COOL-{i}',
                    status='completed',
                    total_items=1,
                    total_trade_value=100
                )
                db.session.add(batch)
            db.session.commit()

            service = ReviewPromptService(sample_tenant.id)

            # First check - should be eligible
            assert service.should_show_prompt() is True

            # Record a prompt
            service.record_prompt_shown()

            # Now should not be eligible (cooldown active)
            assert service.should_show_prompt() is False
