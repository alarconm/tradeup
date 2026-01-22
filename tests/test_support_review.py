"""
Tests for Support Review Service (RC-008 - Post-support review prompt).

Tests the support ticket tracking and post-support review email workflow.
"""
import pytest
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models.tenant import Tenant
from app.models.member import Member, MembershipTier
from app.models.support_ticket import SupportTicket, TicketStatus, TicketSatisfaction
from app.services.support_review_service import SupportReviewService


@pytest.fixture
def app():
    """Create test application."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def tenant(app):
    """Create a test tenant."""
    with app.app_context():
        tenant = Tenant(
            shop_domain='test-shop.myshopify.com',
            shop_name='Test Shop',
            access_token='test-token',
            settings={'notifications': {'enabled': True}}
        )
        db.session.add(tenant)
        db.session.commit()
        yield tenant


@pytest.fixture
def member(app, tenant):
    """Create a test member."""
    with app.app_context():
        # Reload tenant in this context
        tenant = Tenant.query.get(tenant.id)

        tier = MembershipTier(
            tenant_id=tenant.id,
            name='Gold',
            bonus_rate=0.1
        )
        db.session.add(tier)
        db.session.commit()

        member = Member(
            tenant_id=tenant.id,
            email='customer@example.com',
            name='Test Customer',
            member_number='MEM001',
            tier_id=tier.id
        )
        db.session.add(member)
        db.session.commit()
        yield member


class TestSupportTicketModel:
    """Tests for the SupportTicket model."""

    def test_create_support_ticket(self, app, tenant):
        """Test creating a support ticket."""
        with app.app_context():
            tenant = Tenant.query.get(tenant.id)

            ticket = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='12345',
                external_source='gorgias',
                customer_email='customer@example.com',
                customer_name='Test Customer',
                subject='Help with trade-in'
            )
            db.session.add(ticket)
            db.session.commit()

            assert ticket.id is not None
            assert ticket.status == TicketStatus.OPEN.value
            assert ticket.satisfaction == TicketSatisfaction.NOT_RATED.value

    def test_mark_resolved(self, app, tenant):
        """Test marking a ticket as resolved."""
        with app.app_context():
            tenant = Tenant.query.get(tenant.id)

            ticket = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='12345',
                customer_email='customer@example.com'
            )
            db.session.add(ticket)
            db.session.commit()

            ticket.mark_resolved(TicketSatisfaction.SATISFIED)
            db.session.commit()

            assert ticket.status == TicketStatus.RESOLVED.value
            assert ticket.satisfaction == TicketSatisfaction.SATISFIED.value
            assert ticket.resolved_at is not None

    def test_eligibility_for_review_email_satisfied(self, app, tenant):
        """Test eligibility check for satisfied customer."""
        with app.app_context():
            tenant = Tenant.query.get(tenant.id)

            ticket = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='12345',
                customer_email='customer@example.com'
            )
            db.session.add(ticket)
            db.session.commit()

            # Not eligible when open
            assert ticket.is_eligible_for_review_email() is False

            # Eligible when resolved and satisfied
            ticket.mark_resolved(TicketSatisfaction.SATISFIED)
            db.session.commit()
            assert ticket.is_eligible_for_review_email() is True

    def test_eligibility_for_review_email_dissatisfied(self, app, tenant):
        """Test eligibility check for dissatisfied customer."""
        with app.app_context():
            tenant = Tenant.query.get(tenant.id)

            ticket = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='12345',
                customer_email='customer@example.com'
            )
            db.session.add(ticket)
            ticket.mark_resolved(TicketSatisfaction.DISSATISFIED)
            db.session.commit()

            # Not eligible when dissatisfied
            assert ticket.is_eligible_for_review_email() is False

    def test_eligibility_already_sent(self, app, tenant):
        """Test eligibility check when email already sent."""
        with app.app_context():
            tenant = Tenant.query.get(tenant.id)

            ticket = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='12345',
                customer_email='customer@example.com'
            )
            db.session.add(ticket)
            ticket.mark_resolved(TicketSatisfaction.SATISFIED)
            ticket.mark_review_email_sent('tracking-123')
            db.session.commit()

            # Not eligible when already sent
            assert ticket.is_eligible_for_review_email() is False

    def test_find_or_create_new(self, app, tenant):
        """Test find_or_create creates new ticket."""
        with app.app_context():
            tenant = Tenant.query.get(tenant.id)

            ticket = SupportTicket.find_or_create(
                tenant_id=tenant.id,
                external_ticket_id='new-ticket',
                customer_email='new@example.com',
                customer_name='New Customer'
            )
            db.session.commit()

            assert ticket.id is not None
            assert ticket.external_ticket_id == 'new-ticket'

    def test_find_or_create_existing(self, app, tenant):
        """Test find_or_create finds existing ticket."""
        with app.app_context():
            tenant = Tenant.query.get(tenant.id)

            # Create first ticket
            ticket1 = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='existing-ticket',
                customer_email='customer@example.com'
            )
            db.session.add(ticket1)
            db.session.commit()
            original_id = ticket1.id

            # Find existing ticket
            ticket2 = SupportTicket.find_or_create(
                tenant_id=tenant.id,
                external_ticket_id='existing-ticket',
                customer_email='customer@example.com',
                subject='Updated subject'
            )
            db.session.commit()

            assert ticket2.id == original_id
            assert ticket2.subject == 'Updated subject'


class TestSupportReviewService:
    """Tests for the SupportReviewService."""

    def test_on_ticket_resolved_satisfied(self, app, tenant, member):
        """Test handling a satisfied ticket resolution."""
        with app.app_context():
            service = SupportReviewService(tenant.id)

            result = service.on_ticket_resolved(
                external_ticket_id='ticket-123',
                customer_email='customer@example.com',
                satisfaction='satisfied',
                customer_name='Test Customer',
                subject='Help with points'
            )

            assert result['success'] is True
            assert result['eligible_for_review_email'] is True
            assert result['satisfaction'] == 'satisfied'

            # Verify member was linked
            ticket = SupportTicket.query.filter_by(
                external_ticket_id='ticket-123'
            ).first()
            assert ticket.member_id == member.id

    def test_on_ticket_resolved_dissatisfied(self, app, tenant):
        """Test handling a dissatisfied ticket resolution."""
        with app.app_context():
            service = SupportReviewService(tenant.id)

            result = service.on_ticket_resolved(
                external_ticket_id='ticket-456',
                customer_email='unhappy@example.com',
                satisfaction='dissatisfied'
            )

            assert result['success'] is True
            assert result['eligible_for_review_email'] is False
            assert result['satisfaction'] == 'dissatisfied'

    def test_satisfaction_mapping(self, app, tenant):
        """Test various satisfaction string mappings."""
        with app.app_context():
            service = SupportReviewService(tenant.id)

            # Test various mappings
            mappings = {
                'satisfied': TicketSatisfaction.SATISFIED,
                'happy': TicketSatisfaction.SATISFIED,
                'positive': TicketSatisfaction.SATISFIED,
                'neutral': TicketSatisfaction.NEUTRAL,
                'dissatisfied': TicketSatisfaction.DISSATISFIED,
                'unhappy': TicketSatisfaction.DISSATISFIED,
                'negative': TicketSatisfaction.DISSATISFIED,
                'not_rated': TicketSatisfaction.NOT_RATED,
                'unknown': TicketSatisfaction.NOT_RATED,  # Default
            }

            for input_val, expected in mappings.items():
                result = service._map_satisfaction(input_val)
                assert result == expected, f"Failed for {input_val}"

    def test_get_review_email_stats(self, app, tenant):
        """Test getting review email statistics."""
        with app.app_context():
            # Create some tickets with various states
            for i in range(5):
                ticket = SupportTicket(
                    tenant_id=tenant.id,
                    external_ticket_id=f'stat-ticket-{i}',
                    customer_email=f'customer{i}@example.com',
                    status=TicketStatus.RESOLVED.value,
                    satisfaction=TicketSatisfaction.SATISFIED.value,
                    resolved_at=datetime.utcnow() - timedelta(days=1)
                )
                ticket.mark_review_email_sent(f'tracking-{i}')

                # Simulate opens and clicks
                if i < 3:  # 3 opens
                    ticket.record_email_opened()
                if i < 1:  # 1 click
                    ticket.record_email_clicked()

                db.session.add(ticket)

            db.session.commit()

            service = SupportReviewService(tenant.id)
            stats = service.get_review_email_stats(days=30)

            assert stats['total_sent'] == 5
            assert stats['total_opened'] == 3
            assert stats['total_clicked'] == 1
            assert stats['open_rate'] == 60.0
            assert stats['click_rate'] == 20.0

    def test_track_email_opened(self, app, tenant):
        """Test tracking email opens."""
        with app.app_context():
            ticket = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='track-open-test',
                customer_email='customer@example.com',
                status=TicketStatus.RESOLVED.value
            )
            ticket.mark_review_email_sent('tracking-open-123')
            db.session.add(ticket)
            db.session.commit()

            service = SupportReviewService(tenant.id)
            result = service.track_email_opened('tracking-open-123')

            assert result['success'] is True

            # Verify timestamp was set
            ticket = SupportTicket.find_by_tracking_id('tracking-open-123')
            assert ticket.review_email_opened_at is not None

    def test_track_email_clicked(self, app, tenant):
        """Test tracking email clicks."""
        with app.app_context():
            ticket = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='track-click-test',
                customer_email='customer@example.com',
                status=TicketStatus.RESOLVED.value
            )
            ticket.mark_review_email_sent('tracking-click-123')
            db.session.add(ticket)
            db.session.commit()

            service = SupportReviewService(tenant.id)
            result = service.track_email_clicked('tracking-click-123')

            assert result['success'] is True

            # Verify timestamps were set (click also records open)
            ticket = SupportTicket.find_by_tracking_id('tracking-click-123')
            assert ticket.review_email_clicked_at is not None
            assert ticket.review_email_opened_at is not None

    def test_get_ticket_status(self, app, tenant):
        """Test getting ticket status."""
        with app.app_context():
            ticket = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='status-test',
                customer_email='customer@example.com',
                subject='Test Subject'
            )
            db.session.add(ticket)
            db.session.commit()

            service = SupportReviewService(tenant.id)
            status = service.get_ticket_status('status-test')

            assert status is not None
            assert status['external_ticket_id'] == 'status-test'
            assert status['subject'] == 'Test Subject'

    def test_get_ticket_status_not_found(self, app, tenant):
        """Test getting status for non-existent ticket."""
        with app.app_context():
            service = SupportReviewService(tenant.id)
            status = service.get_ticket_status('non-existent')

            assert status is None


class TestEmailTracking:
    """Tests for email tracking functionality."""

    def test_tracking_id_unique(self, app, tenant):
        """Test that tracking IDs must be unique."""
        with app.app_context():
            ticket1 = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='unique-test-1',
                customer_email='customer1@example.com'
            )
            ticket1.mark_review_email_sent('unique-tracking-id')
            db.session.add(ticket1)
            db.session.commit()

            ticket2 = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='unique-test-2',
                customer_email='customer2@example.com'
            )
            ticket2.mark_review_email_sent('unique-tracking-id')
            db.session.add(ticket2)

            # Should fail due to unique constraint
            with pytest.raises(Exception):
                db.session.commit()

    def test_find_by_tracking_id(self, app, tenant):
        """Test finding ticket by tracking ID."""
        with app.app_context():
            ticket = SupportTicket(
                tenant_id=tenant.id,
                external_ticket_id='find-by-tracking',
                customer_email='customer@example.com'
            )
            ticket.mark_review_email_sent('find-tracking-123')
            db.session.add(ticket)
            db.session.commit()

            found = SupportTicket.find_by_tracking_id('find-tracking-123')
            assert found is not None
            assert found.external_ticket_id == 'find-by-tracking'

            not_found = SupportTicket.find_by_tracking_id('non-existent')
            assert not_found is None
