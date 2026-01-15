"""
Recharge Integration Service for TradeUp.

Tracks subscription revenue for loyalty tier eligibility and
awards points on recurring subscription payments.

API Documentation: https://developer.rechargepayments.com/
"""

import requests
import hmac
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
from flask import current_app

from ..extensions import db
from ..models.member import Member
from ..models.tenant import Tenant


class RechargeService:
    """
    Recharge subscription integration.

    Tracks subscription payments for tier eligibility and
    awards points on recurring charges.

    Usage:
        service = RechargeService(tenant_id)
        result = service.handle_charge_success(charge_data)
    """

    BASE_URL = "https://api.rechargeapps.com"
    API_VERSION = "2021-11"

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._tenant = None
        self._settings = None
        self._api_key = None

    @property
    def tenant(self) -> Tenant:
        if self._tenant is None:
            self._tenant = Tenant.query.get(self.tenant_id)
        return self._tenant

    @property
    def settings(self) -> Dict[str, Any]:
        if self._settings is None:
            self._settings = {}
            if self.tenant and self.tenant.settings:
                integrations = self.tenant.settings.get('integrations', {})
                self._settings = integrations.get('recharge', {})
        return self._settings

    @property
    def api_key(self) -> Optional[str]:
        if self._api_key is None:
            self._api_key = self.settings.get('api_key')
        return self._api_key

    def is_enabled(self) -> bool:
        """Check if Recharge integration is enabled."""
        return bool(self.settings.get('enabled') and self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            'X-Recharge-Access-Token': self.api_key,
            'X-Recharge-Version': self.API_VERSION,
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> Dict[str, Any]:
        """Test the Recharge API connection."""
        if not self.api_key:
            return {'success': False, 'error': 'API key not configured'}

        try:
            response = requests.get(
                f'{self.BASE_URL}/store',
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                store = data.get('store', {})
                return {
                    'success': True,
                    'store': {
                        'name': store.get('name'),
                        'domain': store.get('domain'),
                        'email': store.get('email')
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Recharge connection test failed: {e}")
            return {'success': False, 'error': str(e)}

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Verify Recharge webhook signature.

        Args:
            payload: Raw request body
            signature: X-Recharge-Hmac-Sha256 header value

        Returns:
            True if signature is valid
        """
        webhook_secret = self.settings.get('webhook_secret')
        if not webhook_secret:
            return False

        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    def handle_subscription_created(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a new subscription from Recharge webhook.

        Args:
            subscription_data: Subscription data from webhook

        Returns:
            Dict with processing result
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Recharge not enabled'}

        customer_email = subscription_data.get('email')
        if not customer_email:
            return {'success': False, 'error': 'No email in subscription data'}

        # Find or track member
        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if member:
            # Update member subscription tracking
            self._track_subscription(member, subscription_data)

        return {
            'success': True,
            'message': 'Subscription tracked',
            'member_id': member.id if member else None
        }

    def handle_charge_success(self, charge_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a successful charge from Recharge webhook.

        Awards points and tracks revenue for tier eligibility.

        Args:
            charge_data: Charge data from webhook

        Returns:
            Dict with processing result
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Recharge not enabled'}

        customer_email = charge_data.get('email')
        if not customer_email:
            return {'success': False, 'error': 'No email in charge data'}

        # Find member
        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if not member:
            return {
                'success': False,
                'error': 'Customer is not a member',
                'email': customer_email
            }

        # Track charge for tier eligibility
        charge_amount = Decimal(str(charge_data.get('total_price', 0)))
        self._track_charge(member, charge_data, charge_amount)

        # Award points if enabled
        points_result = None
        if self.settings.get('award_points_on_subscription', True):
            points_result = self._award_subscription_points(member, charge_amount, charge_data)

        # Send to integrations (Klaviyo, SMS)
        self._notify_integrations('subscription_payment', member, {
            'charge_id': charge_data.get('id'),
            'amount': float(charge_amount),
            'subscription_id': charge_data.get('subscription_id')
        })

        return {
            'success': True,
            'message': 'Charge processed',
            'member_id': member.id,
            'points_awarded': points_result.get('points') if points_result else 0
        }

    def handle_subscription_cancelled(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle subscription cancellation from Recharge webhook.

        Args:
            subscription_data: Subscription data from webhook

        Returns:
            Dict with processing result
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Recharge not enabled'}

        customer_email = subscription_data.get('email')
        if not customer_email:
            return {'success': False, 'error': 'No email in subscription data'}

        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if member:
            # Log cancellation
            current_app.logger.info(
                f"Subscription cancelled for member {member.id}: {subscription_data.get('id')}"
            )

            # Notify integrations
            self._notify_integrations('subscription_cancelled', member, {
                'subscription_id': subscription_data.get('id'),
                'product_title': subscription_data.get('product_title')
            })

        return {
            'success': True,
            'message': 'Cancellation processed',
            'member_id': member.id if member else None
        }

    def _track_subscription(self, member: Member, subscription_data: Dict[str, Any]):
        """Track subscription in member metadata."""
        # Store subscription info for reference
        if member.metadata is None:
            member.metadata = {}

        if 'subscriptions' not in member.metadata:
            member.metadata['subscriptions'] = []

        # Add or update subscription
        sub_id = subscription_data.get('id')
        existing = next(
            (s for s in member.metadata['subscriptions'] if s.get('id') == sub_id),
            None
        )

        sub_info = {
            'id': sub_id,
            'product_title': subscription_data.get('product_title'),
            'status': subscription_data.get('status'),
            'price': float(subscription_data.get('price', 0)),
            'updated_at': datetime.utcnow().isoformat()
        }

        if existing:
            existing.update(sub_info)
        else:
            member.metadata['subscriptions'].append(sub_info)

        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(member, 'metadata')
        db.session.commit()

    def _track_charge(self, member: Member, charge_data: Dict[str, Any], amount: Decimal):
        """Track charge for tier eligibility."""
        # Update member's total subscription value
        if not hasattr(member, 'subscription_total') or member.subscription_total is None:
            # If member model doesn't have this field, track in metadata
            if member.metadata is None:
                member.metadata = {}

            current_total = Decimal(str(member.metadata.get('subscription_total', 0)))
            member.metadata['subscription_total'] = float(current_total + amount)

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(member, 'metadata')
            db.session.commit()

    def _award_subscription_points(
        self,
        member: Member,
        amount: Decimal,
        charge_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Award points for subscription payment."""
        try:
            from ..services.points_service import get_points_service

            points_service = get_points_service(self.tenant_id)

            # Calculate points (default: 1 point per dollar)
            points_per_dollar = self.settings.get('points_per_dollar', 1)
            points = int(float(amount) * points_per_dollar)

            if points <= 0:
                return {'success': True, 'points': 0}

            # Award points
            result = points_service.award_points(
                member_id=member.id,
                points=points,
                source='subscription',
                source_id=str(charge_data.get('id', '')),
                description=f'Points for subscription payment ${amount:.2f}',
                metadata={
                    'charge_id': charge_data.get('id'),
                    'subscription_id': charge_data.get('subscription_id'),
                    'amount': float(amount)
                }
            )

            return {
                'success': result.get('success', False),
                'points': points
            }

        except Exception as e:
            current_app.logger.error(f"Failed to award subscription points: {e}")
            return {'success': False, 'error': str(e), 'points': 0}

    def _notify_integrations(self, event_type: str, member: Member, properties: Dict[str, Any]):
        """Send event to enabled integrations."""
        try:
            # Klaviyo
            from ..services.klaviyo_service import get_klaviyo_service
            klaviyo = get_klaviyo_service(self.tenant_id)
            if klaviyo.is_enabled():
                klaviyo.track_event(
                    event_name=f'tradeup_{event_type}',
                    email=member.email,
                    properties=properties
                )

            # SMS
            from ..services.sms_service import get_sms_service
            sms = get_sms_service(self.tenant_id)
            if sms.is_enabled() and member.phone:
                sms.send_event(event_type, member, properties)

        except Exception as e:
            current_app.logger.error(f"Failed to notify integrations: {e}")

    def get_customer_subscriptions(self, customer_email: str) -> Dict[str, Any]:
        """
        Get subscriptions for a customer from Recharge.

        Args:
            customer_email: Customer's email address

        Returns:
            Dict with subscription data
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Recharge not enabled'}

        try:
            response = requests.get(
                f'{self.BASE_URL}/subscriptions',
                headers=self._get_headers(),
                params={'email': customer_email},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'subscriptions': data.get('subscriptions', [])
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Recharge get subscriptions failed: {e}")
            return {'success': False, 'error': str(e)}

    def calculate_subscription_value(self, customer_email: str) -> Dict[str, Any]:
        """
        Calculate total subscription value for CLV.

        Args:
            customer_email: Customer's email address

        Returns:
            Dict with subscription value data
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Recharge not enabled'}

        try:
            response = requests.get(
                f'{self.BASE_URL}/charges',
                headers=self._get_headers(),
                params={
                    'email': customer_email,
                    'status': 'SUCCESS'
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                charges = data.get('charges', [])

                total_value = sum(
                    Decimal(str(c.get('total_price', 0)))
                    for c in charges
                )

                return {
                    'success': True,
                    'total_subscription_value': float(total_value),
                    'charge_count': len(charges)
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Recharge calculate value failed: {e}")
            return {'success': False, 'error': str(e)}


def get_recharge_service(tenant_id: int) -> RechargeService:
    """Get Recharge service for a tenant."""
    return RechargeService(tenant_id)
