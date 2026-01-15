"""
SMS Marketing Integration Service for TradeUp.

Supports Postscript and Attentive for SMS marketing automation.
Syncs member data and sends events for automation triggers.
"""

import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from flask import current_app

from ..extensions import db
from ..models.member import Member
from ..models.tenant import Tenant


class PostscriptService:
    """
    Postscript SMS integration service.

    API Documentation: https://developers.postscript.io/

    Usage:
        service = PostscriptService(tenant_id)
        if service.is_enabled():
            service.track_event('tier_upgraded', subscriber_phone, properties)
    """

    BASE_URL = "https://api.postscript.io/api/v2"

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._tenant = None
        self._settings = None
        self._shop_id = None
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
                self._settings = integrations.get('postscript', {})
        return self._settings

    @property
    def shop_id(self) -> Optional[str]:
        if self._shop_id is None:
            self._shop_id = self.settings.get('shop_id')
        return self._shop_id

    @property
    def api_key(self) -> Optional[str]:
        if self._api_key is None:
            self._api_key = self.settings.get('api_key')
        return self._api_key

    def is_enabled(self) -> bool:
        """Check if Postscript integration is enabled."""
        return bool(self.settings.get('enabled') and self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> Dict[str, Any]:
        """Test the Postscript API connection."""
        if not self.api_key:
            return {'success': False, 'error': 'API key not configured'}

        try:
            response = requests.get(
                f'{self.BASE_URL}/shop',
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'shop': data.get('shop', {})
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Postscript connection test failed: {e}")
            return {'success': False, 'error': str(e)}

    def track_event(
        self,
        event_name: str,
        phone: str,
        properties: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Track a custom event for a subscriber.

        Args:
            event_name: Name of the event (e.g., 'tradeup_tier_upgraded')
            phone: Subscriber's phone number (E.164 format)
            properties: Event properties

        Returns:
            Dict with success status
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Postscript not enabled'}

        try:
            payload = {
                'event': {
                    'event_type': f'tradeup_{event_name}',
                    'phone_number': phone,
                    'properties': properties or {}
                }
            }

            response = requests.post(
                f'{self.BASE_URL}/events',
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201, 202]:
                return {'success': True}
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'details': response.text
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Postscript track_event failed: {e}")
            return {'success': False, 'error': str(e)}

    def sync_subscriber(self, member: Member) -> Dict[str, Any]:
        """
        Sync member data to Postscript subscriber.

        Args:
            member: Member to sync

        Returns:
            Dict with success status
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Postscript not enabled'}

        if not member.phone:
            return {'success': False, 'error': 'Member has no phone number'}

        try:
            # Build subscriber properties
            properties = {
                'tradeup_member_id': str(member.id),
                'tradeup_tier': member.tier.name if member.tier else 'Member',
                'tradeup_member_since': member.membership_start_date.isoformat() if member.membership_start_date else None,
                'tradeup_lifetime_spent': float(member.lifetime_spend or 0)
            }

            # Add credit balance if available
            if hasattr(member, 'store_credit_balance'):
                properties['tradeup_credit_balance'] = float(member.store_credit_balance or 0)

            payload = {
                'subscriber': {
                    'phone_number': member.phone,
                    'email': member.email,
                    'properties': properties
                }
            }

            response = requests.post(
                f'{self.BASE_URL}/subscribers',
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201]:
                return {'success': True, 'subscriber': response.json()}
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'details': response.text
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Postscript sync_subscriber failed: {e}")
            return {'success': False, 'error': str(e)}


class AttentiveService:
    """
    Attentive SMS integration service.

    API Documentation: https://docs.attentivemobile.com/

    Usage:
        service = AttentiveService(tenant_id)
        if service.is_enabled():
            service.track_event('tier_upgraded', subscriber_phone, properties)
    """

    BASE_URL = "https://api.attentivemobile.com/v1"

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
                self._settings = integrations.get('attentive', {})
        return self._settings

    @property
    def api_key(self) -> Optional[str]:
        if self._api_key is None:
            self._api_key = self.settings.get('api_key')
        return self._api_key

    def is_enabled(self) -> bool:
        """Check if Attentive integration is enabled."""
        return bool(self.settings.get('enabled') and self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> Dict[str, Any]:
        """Test the Attentive API connection."""
        if not self.api_key:
            return {'success': False, 'error': 'API key not configured'}

        try:
            # Attentive uses a different endpoint structure
            response = requests.get(
                f'{self.BASE_URL}/me',
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'account': data
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Attentive connection test failed: {e}")
            return {'success': False, 'error': str(e)}

    def track_event(
        self,
        event_name: str,
        phone: str,
        properties: Dict[str, Any] = None,
        email: str = None
    ) -> Dict[str, Any]:
        """
        Track a custom event for a subscriber.

        Args:
            event_name: Name of the event
            phone: Subscriber's phone number
            properties: Event properties
            email: Optional email address

        Returns:
            Dict with success status
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Attentive not enabled'}

        try:
            payload = {
                'type': f'tradeup_{event_name}',
                'user': {
                    'phone': phone
                },
                'properties': properties or {}
            }

            if email:
                payload['user']['email'] = email

            response = requests.post(
                f'{self.BASE_URL}/events/custom',
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201, 202]:
                return {'success': True}
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'details': response.text
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Attentive track_event failed: {e}")
            return {'success': False, 'error': str(e)}

    def sync_subscriber(self, member: Member) -> Dict[str, Any]:
        """
        Sync member data to Attentive subscriber.

        Args:
            member: Member to sync

        Returns:
            Dict with success status
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Attentive not enabled'}

        if not member.phone:
            return {'success': False, 'error': 'Member has no phone number'}

        try:
            # Build subscriber attributes
            custom_attributes = [
                {'name': 'tradeup_member_id', 'value': str(member.id)},
                {'name': 'tradeup_tier', 'value': member.tier.name if member.tier else 'Member'},
            ]

            if member.membership_start_date:
                custom_attributes.append({
                    'name': 'tradeup_member_since',
                    'value': member.membership_start_date.isoformat()
                })

            if member.lifetime_spend:
                custom_attributes.append({
                    'name': 'tradeup_lifetime_spent',
                    'value': str(float(member.lifetime_spend))
                })

            payload = {
                'user': {
                    'phone': member.phone,
                    'email': member.email
                },
                'customAttributes': custom_attributes
            }

            response = requests.post(
                f'{self.BASE_URL}/subscriptions',
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201]:
                return {'success': True, 'subscriber': response.json()}
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'details': response.text
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Attentive sync_subscriber failed: {e}")
            return {'success': False, 'error': str(e)}


class SMSService:
    """
    Unified SMS service that routes to the appropriate provider.

    This service automatically detects which SMS provider is enabled
    and routes events/syncs to the correct API.

    Usage:
        service = get_sms_service(tenant_id)
        service.send_event('tier_upgraded', member, properties)
    """

    # Events that can trigger SMS automations
    SUPPORTED_EVENTS = [
        'member_enrolled',
        'tier_upgraded',
        'tier_downgraded',
        'trade_in_completed',
        'credit_issued',
        'points_earned',
        'points_redeemed',
        'referral_success',
        'birthday'
    ]

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.postscript = PostscriptService(tenant_id)
        self.attentive = AttentiveService(tenant_id)

    def is_enabled(self) -> bool:
        """Check if any SMS provider is enabled."""
        return self.postscript.is_enabled() or self.attentive.is_enabled()

    def get_enabled_provider(self) -> Optional[str]:
        """Get the name of the enabled provider."""
        if self.postscript.is_enabled():
            return 'postscript'
        elif self.attentive.is_enabled():
            return 'attentive'
        return None

    def send_event(
        self,
        event_name: str,
        member: Member,
        properties: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Send an event to the enabled SMS provider.

        Args:
            event_name: Name of the event
            member: Member associated with the event
            properties: Additional event properties

        Returns:
            Dict with success status and provider used
        """
        if not member.phone:
            return {'success': False, 'error': 'Member has no phone number'}

        # Build event properties
        event_props = {
            'member_id': member.id,
            'member_name': member.name,
            'member_email': member.email,
            'tier': member.tier.name if member.tier else 'Member',
            **(properties or {})
        }

        results = {}

        # Send to Postscript if enabled
        if self.postscript.is_enabled():
            results['postscript'] = self.postscript.track_event(
                event_name, member.phone, event_props
            )

        # Send to Attentive if enabled
        if self.attentive.is_enabled():
            results['attentive'] = self.attentive.track_event(
                event_name, member.phone, event_props, member.email
            )

        success = any(r.get('success') for r in results.values())
        return {
            'success': success,
            'results': results
        }

    def sync_member(self, member: Member) -> Dict[str, Any]:
        """
        Sync member data to all enabled SMS providers.

        Args:
            member: Member to sync

        Returns:
            Dict with sync results
        """
        results = {}

        if self.postscript.is_enabled():
            results['postscript'] = self.postscript.sync_subscriber(member)

        if self.attentive.is_enabled():
            results['attentive'] = self.attentive.sync_subscriber(member)

        success = any(r.get('success') for r in results.values())
        return {
            'success': success,
            'results': results
        }

    def sync_all_members(self) -> Dict[str, Any]:
        """
        Sync all members with phone numbers to SMS providers.

        Returns:
            Dict with sync statistics
        """
        members = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.phone.isnot(None),
            Member.status == 'active'
        ).all()

        stats = {
            'total': len(members),
            'synced': 0,
            'failed': 0,
            'errors': []
        }

        for member in members:
            result = self.sync_member(member)
            if result.get('success'):
                stats['synced'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append({
                    'member_id': member.id,
                    'error': result.get('error') or 'Unknown error'
                })

        return stats


def get_sms_service(tenant_id: int) -> SMSService:
    """Get SMS service for a tenant."""
    return SMSService(tenant_id)


def get_postscript_service(tenant_id: int) -> PostscriptService:
    """Get Postscript service for a tenant."""
    return PostscriptService(tenant_id)


def get_attentive_service(tenant_id: int) -> AttentiveService:
    """Get Attentive service for a tenant."""
    return AttentiveService(tenant_id)
