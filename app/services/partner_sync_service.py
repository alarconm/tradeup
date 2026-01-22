"""
Partner Sync Service.
Handles synchronization of data with external partner systems.
"""
import json
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from ..extensions import db
from ..models import PartnerIntegration, PartnerSyncLog, TradeInBatch, Member


class PartnerSyncService:
    """
    Service for syncing data with partner systems.

    Supports:
    - Pushing trade-ins to partner cash ledger
    - Pushing store credit issuance to partner
    - Pushing member enrollments to partner
    """

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def get_enabled_integrations(self) -> List[PartnerIntegration]:
        """Get all enabled integrations for the tenant."""
        return PartnerIntegration.query.filter_by(
            tenant_id=self.tenant_id,
            enabled=True
        ).all()

    def sync_trade_in(self, batch: TradeInBatch) -> List[Dict[str, Any]]:
        """
        Sync a trade-in batch to all enabled partner integrations.

        Args:
            batch: TradeInBatch to sync

        Returns:
            List of sync results
        """
        results = []
        integrations = PartnerIntegration.query.filter_by(
            tenant_id=self.tenant_id,
            enabled=True,
            sync_trade_ins=True
        ).all()

        for integration in integrations:
            result = self._sync_trade_in_to_partner(integration, batch)
            results.append(result)

        return results

    def _sync_trade_in_to_partner(
        self,
        integration: PartnerIntegration,
        batch: TradeInBatch
    ) -> Dict[str, Any]:
        """
        Sync a single trade-in batch to a specific partner.

        Args:
            integration: Partner integration config
            batch: TradeInBatch to sync

        Returns:
            Sync result dict
        """
        # Build the payload based on partner type
        if integration.partner_type == 'wordpress':
            payload = self._build_wordpress_trade_in_payload(integration, batch)
            endpoint = f"{integration.api_url}/tradeup/trade-in"
        else:
            payload = self._build_generic_trade_in_payload(integration, batch)
            endpoint = f"{integration.api_url}/trade-in"

        # Create sync log
        sync_log = PartnerSyncLog(
            integration_id=integration.id,
            sync_type='trade_in',
            record_id=batch.id,
            record_reference=batch.batch_reference,
            request_payload=payload,
            status='pending'
        )
        db.session.add(sync_log)
        db.session.commit()

        # Send to partner
        try:
            response = self._send_to_partner(integration, endpoint, payload)

            sync_log.response_status = response.get('status_code')
            sync_log.response_body = response.get('body')

            if response.get('success'):
                sync_log.status = 'success'
                integration.last_sync_status = 'success'
                integration.sync_count += 1
            else:
                sync_log.status = 'failed'
                sync_log.error_message = response.get('error')
                integration.last_sync_status = 'failed'
                integration.last_sync_error = response.get('error')

            integration.last_sync_at = datetime.utcnow()
            db.session.commit()

            return {
                'integration': integration.name,
                'success': response.get('success', False),
                'status_code': response.get('status_code'),
                'error': response.get('error')
            }

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            integration.last_sync_status = 'failed'
            integration.last_sync_error = str(e)
            integration.last_sync_at = datetime.utcnow()
            db.session.commit()

            return {
                'integration': integration.name,
                'success': False,
                'error': str(e)
            }

    def _build_wordpress_trade_in_payload(
        self,
        integration: PartnerIntegration,
        batch: TradeInBatch
    ) -> Dict[str, Any]:
        """Build WordPress/ORB-compatible trade-in payload."""
        member = batch.member

        # Map category to ORB's cash ledger kind
        category_to_kind = {
            'sports': 'credit_buy',
            'pokemon': 'credit_buy',
            'magic': 'credit_buy',
            'riftbound': 'credit_buy',
            'tcg_other': 'credit_buy',
            'other': 'credit_buy'
        }

        return {
            'kind': category_to_kind.get(batch.category, 'credit_buy'),
            'amount': float(batch.total_trade_value),
            'category': batch.category,
            'shopify_customer_id': member.shopify_customer_id if member else None,
            'shopify_customer_gid': member.shopify_customer_gid if member else None,
            'partner_customer_id': member.partner_customer_id if member else None,
            'member_number': member.member_number if member else None,
            'member_name': member.name if member else None,
            'batch_reference': batch.batch_reference,
            'total_items': batch.total_items,
            'notes': batch.notes,
            'description': f'TradeUp {batch.batch_reference} - {batch.total_items} items',
            'source': 'tradeup',
            'created_at': batch.created_at.isoformat()
        }

    def _build_generic_trade_in_payload(
        self,
        integration: PartnerIntegration,
        batch: TradeInBatch
    ) -> Dict[str, Any]:
        """Build generic trade-in payload."""
        member = batch.member

        payload = {
            'batch_id': batch.id,
            'batch_reference': batch.batch_reference,
            'category': batch.category,
            'total_value': float(batch.total_trade_value),
            'total_items': batch.total_items,
            'status': batch.status,
            'notes': batch.notes,
            'created_at': batch.created_at.isoformat(),
            'member': {
                'id': member.id if member else None,
                'member_number': member.member_number if member else None,
                'name': member.name if member else None,
                'email': member.email if member else None,
                'shopify_customer_id': member.shopify_customer_id if member else None
            }
        }

        # Apply field mapping if configured
        if integration.field_mapping:
            mapped_payload = {}
            for source_field, target_field in integration.field_mapping.items():
                if source_field in payload:
                    mapped_payload[target_field] = payload[source_field]
                else:
                    mapped_payload[target_field] = payload.get(source_field)
            return mapped_payload

        return payload

    # Note: Bonus syncing has been removed. Store credit is now
    # synced directly via StoreCreditService and Shopify's native store credit.

    def _send_to_partner(
        self,
        integration: PartnerIntegration,
        endpoint: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send data to partner API.

        Args:
            integration: Partner integration config
            endpoint: API endpoint URL
            payload: Data to send

        Returns:
            Response dict with success, status_code, body, error
        """
        headers = {
            'Content-Type': 'application/json',
            'X-TradeUp-Source': 'tradeup-api',
            'X-TradeUp-Tenant': str(self.tenant_id)
        }

        # Add auth header if token configured
        if integration.api_token:
            headers['Authorization'] = f'Bearer {integration.api_token}'

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=30
            )

            # Parse JSON response, handling UTF-8 BOM if present
            body = None
            if response.headers.get('content-type', '').startswith('application/json'):
                try:
                    # Strip UTF-8 BOM if present and parse JSON
                    text = response.text.lstrip('\ufeff')
                    body = json.loads(text)
                except Exception:
                    body = {'text': response.text}
            else:
                body = {'text': response.text}

            return {
                'success': response.status_code in [200, 201],
                'status_code': response.status_code,
                'body': body,
                'error': None if response.status_code in [200, 201] else f'HTTP {response.status_code}'
            }

        except requests.Timeout:
            return {
                'success': False,
                'status_code': None,
                'body': None,
                'error': 'Request timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': None,
                'body': None,
                'error': str(e)
            }

    def get_sync_logs(
        self,
        integration_id: Optional[int] = None,
        sync_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[PartnerSyncLog]:
        """Get sync logs with optional filters."""
        query = PartnerSyncLog.query.join(PartnerIntegration).filter(
            PartnerIntegration.tenant_id == self.tenant_id
        )

        if integration_id:
            query = query.filter(PartnerSyncLog.integration_id == integration_id)
        if sync_type:
            query = query.filter(PartnerSyncLog.sync_type == sync_type)
        if status:
            query = query.filter(PartnerSyncLog.status == status)

        return query.order_by(PartnerSyncLog.created_at.desc()).limit(limit).all()

    def retry_failed_syncs(self, integration_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retry all failed syncs for the tenant."""
        query = PartnerSyncLog.query.join(PartnerIntegration).filter(
            PartnerIntegration.tenant_id == self.tenant_id,
            PartnerSyncLog.status == 'failed',
            PartnerSyncLog.retry_count < 3
        )

        if integration_id:
            query = query.filter(PartnerSyncLog.integration_id == integration_id)

        failed_logs = query.all()
        results = []

        for log in failed_logs:
            log.retry_count += 1

            if log.sync_type == 'trade_in':
                batch = TradeInBatch.query.get(log.record_id)
                if batch:
                    result = self._sync_trade_in_to_partner(log.integration, batch)
                    results.append(result)
            # Note: bonus sync_type logs are legacy and will be skipped

        return results
