"""
API endpoint tests for Store Credit Events.

Tests the REST API endpoints for bulk store credit events.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from decimal import Decimal


class TestPreviewEndpoint:
    """Test /api/store-credit-events/preview endpoint."""

    def test_preview_requires_auth(self, client):
        """Should require authentication."""
        response = client.post('/api/store-credit-events/preview', json={
            'start_datetime': '2026-01-24T17:00:00Z',
            'end_datetime': '2026-01-24T20:00:00Z',
        })
        assert response.status_code in [401, 403]

    def test_preview_requires_datetimes(self, client, auth_headers):
        """Should require start and end datetime."""
        response = client.post(
            '/api/store-credit-events/preview',
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'start_datetime' in data.get('error', '').lower() or 'required' in data.get('error', '').lower()

    def test_preview_validates_collection_ids(self, client, auth_headers):
        """Should validate collection_ids format."""
        response = client.post(
            '/api/store-credit-events/preview',
            headers=auth_headers,
            json={
                'start_datetime': '2026-01-24T17:00:00Z',
                'end_datetime': '2026-01-24T20:00:00Z',
                'collection_ids': 'not-a-list'  # Should be a list
            }
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'collection_ids' in data.get('error', '').lower()

    def test_preview_validates_collection_gid_format(self, client, auth_headers):
        """Should validate collection IDs are proper GIDs."""
        response = client.post(
            '/api/store-credit-events/preview',
            headers=auth_headers,
            json={
                'start_datetime': '2026-01-24T17:00:00Z',
                'end_datetime': '2026-01-24T20:00:00Z',
                'collection_ids': ['invalid-id']  # Should be gid://shopify/Collection/123
            }
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'invalid' in data.get('error', '').lower()

    def test_preview_validates_audience(self, client, auth_headers):
        """Should validate audience parameter."""
        response = client.post(
            '/api/store-credit-events/preview',
            headers=auth_headers,
            json={
                'start_datetime': '2026-01-24T17:00:00Z',
                'end_datetime': '2026-01-24T20:00:00Z',
                'sources': ['pos'],
                'audience': 'invalid_value'
            }
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'audience' in data.get('error', '').lower()

    @patch('app.api.store_credit_events.get_service_for_tenant')
    def test_preview_returns_summary(self, mock_service, client, auth_headers):
        """Should return preview summary."""
        mock_svc = MagicMock()
        mock_svc.preview_event.return_value = {
            'total_orders': 10,
            'unique_customers': 5,
            'total_order_value': 1000.0,
            'total_credit_amount': 100.0,
            'by_source': {'pos': 10},
            'top_customers': []
        }
        mock_service.return_value = mock_svc

        response = client.post(
            '/api/store-credit-events/preview',
            headers=auth_headers,
            json={
                'start_datetime': '2026-01-24T17:00:00Z',
                'end_datetime': '2026-01-24T20:00:00Z',
                'credit_percent': 10
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'summary' in data
        assert data['summary']['total_orders'] == 10
        assert data['summary']['total_credit_to_issue'] == 100.0


class TestRunEndpoint:
    """Test /api/store-credit-events/run endpoint."""

    def test_run_requires_auth(self, client):
        """Should require authentication."""
        response = client.post('/api/store-credit-events/run', json={
            'start_datetime': '2026-01-24T17:00:00Z',
            'end_datetime': '2026-01-24T20:00:00Z',
            'sources': ['pos']
        })
        assert response.status_code in [401, 403]

    def test_run_requires_sources(self, client, auth_headers):
        """Should require sources parameter."""
        response = client.post(
            '/api/store-credit-events/run',
            headers=auth_headers,
            json={
                'start_datetime': '2026-01-24T17:00:00Z',
                'end_datetime': '2026-01-24T20:00:00Z',
                # Missing sources
            }
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'sources' in data.get('error', '').lower()

    @patch('app.api.store_credit_events.get_service_for_tenant')
    def test_run_returns_transformed_response(self, mock_service, client, auth_headers):
        """Should transform backend response for frontend."""
        mock_svc = MagicMock()
        mock_svc.run_event.return_value = {
            'event': {'job_id': 'test-123'},
            'summary': {
                'total_customers': 5,
                'successful': 4,
                'skipped': 1,
                'failed': 0,
                'total_credited': 50.0
            },
            'results': [
                {
                    'customer_id': 'gid://shopify/Customer/1',
                    'customer_email': 'test@example.com',
                    'credit_amount': 10.0,
                    'success': True,
                    'skipped': False
                }
            ]
        }
        mock_service.return_value = mock_svc

        response = client.post(
            '/api/store-credit-events/run',
            headers=auth_headers,
            json={
                'start_datetime': '2026-01-24T17:00:00Z',
                'end_datetime': '2026-01-24T20:00:00Z',
                'sources': ['pos'],
                'credit_percent': 10
            }
        )

        assert response.status_code == 200
        data = response.get_json()

        # Verify transformed response format
        assert 'job_id' in data
        assert 'success_count' in data
        assert 'failure_count' in data
        assert 'total_credit_issued' in data
        assert 'results' in data
        assert data['success_count'] == 4
        assert data['total_credit_issued'] == 50.0


class TestSourcesEndpoint:
    """Test /api/store-credit-events/sources endpoint."""

    def test_sources_requires_auth(self, client):
        """Should require authentication."""
        response = client.get('/api/store-credit-events/sources?start_datetime=2026-01-24&end_datetime=2026-01-25')
        assert response.status_code in [401, 403]

    def test_sources_requires_dates(self, client, auth_headers):
        """Should require start and end datetime."""
        response = client.get(
            '/api/store-credit-events/sources',
            headers=auth_headers
        )
        assert response.status_code == 400

    @patch('app.api.store_credit_events.get_service_for_tenant')
    def test_sources_returns_source_list(self, mock_service, client, auth_headers):
        """Should return list of sources with counts."""
        mock_svc = MagicMock()
        mock_svc.fetch_orders.return_value = [
            MagicMock(source_name='Point of Sale'),
            MagicMock(source_name='Point of Sale'),
            MagicMock(source_name='web'),
        ]
        mock_service.return_value = mock_svc

        response = client.get(
            '/api/store-credit-events/sources?start_datetime=2026-01-24T00:00:00Z&end_datetime=2026-01-25T00:00:00Z',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'sources' in data
        assert 'total_orders' in data
        assert data['total_orders'] == 3


class TestInputValidation:
    """Test input validation and injection prevention."""

    def test_rejects_sql_injection_in_datetime(self, client, auth_headers):
        """Should reject SQL injection attempts in datetime."""
        response = client.post(
            '/api/store-credit-events/preview',
            headers=auth_headers,
            json={
                'start_datetime': "2026-01-24'; DROP TABLE orders;--",
                'end_datetime': '2026-01-24T20:00:00Z',
            }
        )
        assert response.status_code == 400

    def test_rejects_invalid_product_tags(self, client, auth_headers):
        """Should reject invalid product_tags."""
        response = client.post(
            '/api/store-credit-events/preview',
            headers=auth_headers,
            json={
                'start_datetime': '2026-01-24T17:00:00Z',
                'end_datetime': '2026-01-24T20:00:00Z',
                'product_tags': [123]  # Should be strings
            }
        )
        assert response.status_code == 400

    def test_rejects_oversized_tags(self, client, auth_headers):
        """Should reject product tags over 255 characters."""
        response = client.post(
            '/api/store-credit-events/preview',
            headers=auth_headers,
            json={
                'start_datetime': '2026-01-24T17:00:00Z',
                'end_datetime': '2026-01-24T20:00:00Z',
                'product_tags': ['x' * 300]  # Over 255 chars
            }
        )
        assert response.status_code == 400


class TestTemplatesEndpoint:
    """Test /api/store-credit-events/templates endpoint."""

    def test_templates_returns_list(self, client):
        """Should return template list without auth."""
        response = client.get('/api/store-credit-events/templates')

        assert response.status_code == 200
        data = response.get_json()
        assert 'templates' in data
        assert len(data['templates']) >= 1

        # Check template structure
        template = data['templates'][0]
        assert 'id' in template
        assert 'name' in template
        assert 'default_credit_percent' in template
