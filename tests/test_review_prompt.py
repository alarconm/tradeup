"""
Tests for ReviewPrompt model.
"""
import pytest
from datetime import datetime, timedelta
from app.models import ReviewPrompt, ReviewPromptResponse
from app.extensions import db


class TestReviewPromptModel:
    """Test ReviewPrompt model functionality."""

    def test_create_review_prompt(self, app, sample_tenant):
        """Test creating a review prompt record."""
        with app.app_context():
            prompt = ReviewPrompt(
                tenant_id=sample_tenant.id,
                prompt_shown_at=datetime.utcnow()
            )
            db.session.add(prompt)
            db.session.commit()

            assert prompt.id is not None
            assert prompt.tenant_id == sample_tenant.id
            assert prompt.prompt_shown_at is not None
            assert prompt.response is None
            assert prompt.responded_at is None

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_record_response_dismissed(self, app, sample_tenant):
        """Test recording a dismissed response."""
        with app.app_context():
            prompt = ReviewPrompt(
                tenant_id=sample_tenant.id,
                prompt_shown_at=datetime.utcnow()
            )
            db.session.add(prompt)
            db.session.commit()

            prompt.record_response(ReviewPromptResponse.DISMISSED)
            db.session.commit()

            assert prompt.response == 'dismissed'
            assert prompt.responded_at is not None

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_record_response_clicked(self, app, sample_tenant):
        """Test recording a clicked response."""
        with app.app_context():
            prompt = ReviewPrompt(
                tenant_id=sample_tenant.id,
                prompt_shown_at=datetime.utcnow()
            )
            db.session.add(prompt)
            db.session.commit()

            prompt.record_response(ReviewPromptResponse.CLICKED)
            db.session.commit()

            assert prompt.response == 'clicked'
            assert prompt.responded_at is not None

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_record_response_reminded_later(self, app, sample_tenant):
        """Test recording a reminded_later response."""
        with app.app_context():
            prompt = ReviewPrompt(
                tenant_id=sample_tenant.id,
                prompt_shown_at=datetime.utcnow()
            )
            db.session.add(prompt)
            db.session.commit()

            prompt.record_response(ReviewPromptResponse.REMINDED_LATER)
            db.session.commit()

            assert prompt.response == 'reminded_later'
            assert prompt.responded_at is not None

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_can_show_prompt_no_history(self, app, sample_tenant):
        """Test can_show_prompt returns True when no prompts exist."""
        with app.app_context():
            assert ReviewPrompt.can_show_prompt(sample_tenant.id) is True

    def test_can_show_prompt_within_cooldown(self, app, sample_tenant):
        """Test can_show_prompt returns False within cooldown period."""
        with app.app_context():
            # Create a recent prompt
            prompt = ReviewPrompt(
                tenant_id=sample_tenant.id,
                prompt_shown_at=datetime.utcnow()
            )
            db.session.add(prompt)
            db.session.commit()

            # Should not allow another prompt within 7 days
            assert ReviewPrompt.can_show_prompt(sample_tenant.id) is False

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_can_show_prompt_after_cooldown(self, app, sample_tenant):
        """Test can_show_prompt returns True after cooldown period."""
        with app.app_context():
            # Create an old prompt (8 days ago)
            prompt = ReviewPrompt(
                tenant_id=sample_tenant.id,
                prompt_shown_at=datetime.utcnow() - timedelta(days=8)
            )
            db.session.add(prompt)
            db.session.commit()

            # Should allow another prompt after 7 days
            assert ReviewPrompt.can_show_prompt(sample_tenant.id) is True

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_can_show_prompt_custom_cooldown(self, app, sample_tenant):
        """Test can_show_prompt with custom cooldown period."""
        with app.app_context():
            # Create a prompt 2 days ago
            prompt = ReviewPrompt(
                tenant_id=sample_tenant.id,
                prompt_shown_at=datetime.utcnow() - timedelta(days=2)
            )
            db.session.add(prompt)
            db.session.commit()

            # Should not allow with 72-hour cooldown
            assert ReviewPrompt.can_show_prompt(sample_tenant.id, cooldown_hours=72) is False

            # Should allow with 24-hour cooldown
            assert ReviewPrompt.can_show_prompt(sample_tenant.id, cooldown_hours=24) is True

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_get_prompt_history(self, app, sample_tenant):
        """Test getting prompt history for a tenant."""
        with app.app_context():
            # Create multiple prompts
            prompts = []
            for i in range(3):
                prompt = ReviewPrompt(
                    tenant_id=sample_tenant.id,
                    prompt_shown_at=datetime.utcnow() - timedelta(days=i * 10)
                )
                db.session.add(prompt)
                prompts.append(prompt)
            db.session.commit()

            # Get history
            history = ReviewPrompt.get_prompt_history(sample_tenant.id)
            assert len(history) == 3
            # Should be ordered by prompt_shown_at desc (most recent first)
            assert history[0].prompt_shown_at > history[1].prompt_shown_at

            # Cleanup
            for prompt in prompts:
                db.session.delete(prompt)
            db.session.commit()

    def test_get_prompt_history_with_limit(self, app, sample_tenant):
        """Test getting prompt history with a limit."""
        with app.app_context():
            # Create multiple prompts
            prompts = []
            for i in range(5):
                prompt = ReviewPrompt(
                    tenant_id=sample_tenant.id,
                    prompt_shown_at=datetime.utcnow() - timedelta(days=i * 10)
                )
                db.session.add(prompt)
                prompts.append(prompt)
            db.session.commit()

            # Get limited history
            history = ReviewPrompt.get_prompt_history(sample_tenant.id, limit=3)
            assert len(history) == 3

            # Cleanup
            for prompt in prompts:
                db.session.delete(prompt)
            db.session.commit()

    def test_create_prompt_method(self, app, sample_tenant):
        """Test the create_prompt class method."""
        with app.app_context():
            prompt = ReviewPrompt.create_prompt(sample_tenant.id)
            db.session.commit()

            assert prompt.id is not None
            assert prompt.tenant_id == sample_tenant.id
            assert prompt.prompt_shown_at is not None
            assert prompt.response is None

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_to_dict(self, app, sample_tenant):
        """Test to_dict serialization."""
        with app.app_context():
            prompt = ReviewPrompt(
                tenant_id=sample_tenant.id,
                prompt_shown_at=datetime.utcnow()
            )
            db.session.add(prompt)
            db.session.commit()

            data = prompt.to_dict()
            assert 'id' in data
            assert 'tenant_id' in data
            assert 'prompt_shown_at' in data
            assert 'response' in data
            assert 'responded_at' in data
            assert 'created_at' in data

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_tenant_relationship(self, app, sample_tenant):
        """Test the tenant relationship."""
        with app.app_context():
            prompt = ReviewPrompt(
                tenant_id=sample_tenant.id,
                prompt_shown_at=datetime.utcnow()
            )
            db.session.add(prompt)
            db.session.commit()

            # Access tenant through relationship
            assert prompt.tenant is not None
            assert prompt.tenant.id == sample_tenant.id

            # Cleanup
            db.session.delete(prompt)
            db.session.commit()

    def test_prevent_duplicate_prompts(self, app, sample_tenant):
        """Test that duplicate prompts are prevented within cooldown."""
        with app.app_context():
            # First prompt should be allowed
            assert ReviewPrompt.can_show_prompt(sample_tenant.id) is True

            # Create the first prompt
            prompt1 = ReviewPrompt.create_prompt(sample_tenant.id)
            db.session.commit()

            # Second prompt should be prevented
            assert ReviewPrompt.can_show_prompt(sample_tenant.id) is False

            # Cleanup
            db.session.delete(prompt1)
            db.session.commit()
