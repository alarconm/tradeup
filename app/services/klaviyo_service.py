"""
Klaviyo Integration Service for TradeUp.

Syncs member data and loyalty events to Klaviyo for email marketing automation.

API Documentation: https://developers.klaviyo.com/en/reference/api_overview
API Revision: 2024-10-15
"""

import requests
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from flask import current_app

from ..extensions import db
from ..models.member import Member
from ..models.tenant import Tenant


class KlaviyoService:
    """
    Klaviyo API integration for email marketing.

    Supports:
    - Profile sync (member data → Klaviyo profile)
    - Event tracking (loyalty events → Klaviyo events)
    - List management (add members to lists)
    - Bulk sync operations
    """

    BASE_URL = "https://a.klaviyo.com/api"
    API_REVISION = "2024-10-15"

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._api_key = None
        self._settings = None

    @property
    def api_key(self) -> Optional[str]:
        """Get Klaviyo API key from tenant settings."""
        if self._api_key is None:
            self._load_settings()
        return self._api_key

    @property
    def settings(self) -> Dict[str, Any]:
        """Get Klaviyo settings from tenant."""
        if self._settings is None:
            self._load_settings()
        return self._settings or {}

    def _load_settings(self):
        """Load Klaviyo settings from tenant."""
        tenant = Tenant.query.get(self.tenant_id)
        if not tenant:
            self._settings = {}
            self._api_key = None
            return

        all_settings = tenant.settings or {}
        integrations = all_settings.get('integrations', {})
        klaviyo = integrations.get('klaviyo', {})

        self._settings = klaviyo
        self._api_key = klaviyo.get('api_key')

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Klaviyo API requests."""
        if not self.api_key:
            raise ValueError("Klaviyo API key not configured")

        return {
            "Authorization": f"Klaviyo-API-Key {self.api_key}",
            "revision": self.API_REVISION,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def is_enabled(self) -> bool:
        """Check if Klaviyo integration is enabled."""
        return bool(self.api_key) and self.settings.get('enabled', False)

    # ==================== CONNECTION TEST ====================

    def test_connection(self) -> Dict[str, Any]:
        """
        Test Klaviyo API connection.

        Returns:
            Dict with connection status
        """
        if not self.api_key:
            return {
                'success': False,
                'error': 'API key not configured'
            }

        try:
            # Try to get account info
            response = requests.get(
                f"{self.BASE_URL}/accounts/",
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'account': data.get('data', [{}])[0].get('attributes', {}),
                    'message': 'Connected successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'details': response.text
                }

        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Connection error: {str(e)}'
            }

    # ==================== PROFILE MANAGEMENT ====================

    def upsert_profile(self, member: Member, extra_properties: Dict = None) -> Dict[str, Any]:
        """
        Create or update a Klaviyo profile.

        Args:
            member: TradeUp member
            extra_properties: Additional profile properties

        Returns:
            Dict with profile ID and status
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Klaviyo not enabled'}

        properties = {
            'email': member.email,
            'first_name': member.name.split()[0] if member.name else None,
            'last_name': ' '.join(member.name.split()[1:]) if member.name and len(member.name.split()) > 1 else None,
            'phone_number': member.phone,
            # Custom properties
            'tradeup_member_number': member.member_number,
            'tradeup_tier': member.tier.name if member.tier else None,
            'tradeup_status': member.status,
            'tradeup_points_balance': member.points_balance or 0,
            'tradeup_store_credit': float(member.store_credit_balance or 0),
            'tradeup_total_spent': float(member.total_spent or 0),
            'tradeup_order_count': member.order_count or 0,
            'tradeup_referral_code': member.referral_code,
            'tradeup_member_since': member.created_at.isoformat() if member.created_at else None,
        }

        # Add extra properties if provided
        if extra_properties:
            properties.update(extra_properties)

        # Remove None values
        properties = {k: v for k, v in properties.items() if v is not None}

        payload = {
            "data": {
                "type": "profile",
                "attributes": properties
            }
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/profiles/",
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201, 202]:
                data = response.json()
                profile_id = data.get('data', {}).get('id')
                return {
                    'success': True,
                    'profile_id': profile_id,
                    'message': 'Profile synced'
                }
            elif response.status_code == 409:
                # Profile exists, try to update by email
                return self._update_profile_by_email(member.email, properties)
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'details': response.text
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Klaviyo profile sync failed: {e}")
            return {'success': False, 'error': str(e)}

    def _update_profile_by_email(self, email: str, properties: Dict) -> Dict[str, Any]:
        """Update profile by email lookup."""
        # First, find profile by email
        try:
            response = requests.get(
                f"{self.BASE_URL}/profiles/",
                headers=self._get_headers(),
                params={'filter': f'equals(email,"{email}")'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                profiles = data.get('data', [])
                if profiles:
                    profile_id = profiles[0].get('id')
                    return self._patch_profile(profile_id, properties)

            return {'success': False, 'error': 'Profile not found for update'}

        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def _patch_profile(self, profile_id: str, properties: Dict) -> Dict[str, Any]:
        """Patch an existing profile."""
        payload = {
            "data": {
                "type": "profile",
                "id": profile_id,
                "attributes": properties
            }
        }

        try:
            response = requests.patch(
                f"{self.BASE_URL}/profiles/{profile_id}/",
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 202]:
                return {
                    'success': True,
                    'profile_id': profile_id,
                    'message': 'Profile updated'
                }
            else:
                return {
                    'success': False,
                    'error': f'Update failed: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    # ==================== EVENT TRACKING ====================

    def track_event(
        self,
        event_name: str,
        email: str,
        properties: Dict[str, Any],
        unique_id: str = None
    ) -> Dict[str, Any]:
        """
        Track a custom event in Klaviyo.

        Args:
            event_name: Event name (e.g., 'tradeup_member_enrolled')
            email: Customer email
            properties: Event properties
            unique_id: Unique event ID for deduplication

        Returns:
            Dict with tracking status
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Klaviyo not enabled'}

        # Check if this event type should be synced
        sync_events = self.settings.get('sync_on_events', [])
        event_key = event_name.replace('tradeup_', '')
        if sync_events and event_key not in sync_events:
            return {'success': True, 'message': 'Event type not configured for sync', 'skipped': True}

        payload = {
            "data": {
                "type": "event",
                "attributes": {
                    "metric": {
                        "data": {
                            "type": "metric",
                            "attributes": {
                                "name": event_name
                            }
                        }
                    },
                    "profile": {
                        "data": {
                            "type": "profile",
                            "attributes": {
                                "email": email
                            }
                        }
                    },
                    "properties": properties,
                    "time": datetime.utcnow().isoformat() + "Z"
                }
            }
        }

        if unique_id:
            payload['data']['attributes']['unique_id'] = unique_id

        try:
            response = requests.post(
                f"{self.BASE_URL}/events/",
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201, 202]:
                return {
                    'success': True,
                    'event': event_name,
                    'message': 'Event tracked'
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'details': response.text
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Klaviyo event tracking failed: {e}")
            return {'success': False, 'error': str(e)}

    # ==================== LOYALTY EVENTS ====================

    def track_member_enrolled(self, member: Member) -> Dict[str, Any]:
        """Track member enrollment event."""
        return self.track_event(
            event_name='tradeup_member_enrolled',
            email=member.email,
            properties={
                'member_number': member.member_number,
                'tier': member.tier.name if member.tier else 'none',
                'referral_code': member.referral_code,
                'signup_date': member.created_at.isoformat() if member.created_at else None
            },
            unique_id=f'enrolled_{member.member_number}'
        )

    def track_tier_upgraded(
        self,
        member: Member,
        old_tier: str,
        new_tier: str,
        reason: str = None
    ) -> Dict[str, Any]:
        """Track tier upgrade/change event."""
        return self.track_event(
            event_name='tradeup_tier_upgraded',
            email=member.email,
            properties={
                'member_number': member.member_number,
                'old_tier': old_tier,
                'new_tier': new_tier,
                'reason': reason,
                'points_balance': member.points_balance or 0,
                'store_credit': float(member.store_credit_balance or 0)
            },
            unique_id=f'tier_{member.member_number}_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
        )

    def track_trade_in_completed(
        self,
        member: Member,
        trade_in_id: int,
        credit_amount: Decimal,
        item_count: int
    ) -> Dict[str, Any]:
        """Track trade-in completion event."""
        return self.track_event(
            event_name='tradeup_trade_in_completed',
            email=member.email,
            properties={
                'member_number': member.member_number,
                'trade_in_id': trade_in_id,
                'credit_amount': float(credit_amount),
                'item_count': item_count,
                'tier': member.tier.name if member.tier else 'none',
                'total_credit': float(member.store_credit_balance or 0)
            },
            unique_id=f'tradein_{trade_in_id}'
        )

    def track_credit_issued(
        self,
        member: Member,
        amount: Decimal,
        event_type: str,
        description: str = None
    ) -> Dict[str, Any]:
        """Track store credit issued event."""
        return self.track_event(
            event_name='tradeup_credit_issued',
            email=member.email,
            properties={
                'member_number': member.member_number,
                'amount': float(amount),
                'event_type': event_type,
                'description': description,
                'new_balance': float(member.store_credit_balance or 0),
                'tier': member.tier.name if member.tier else 'none'
            }
        )

    def track_points_earned(
        self,
        member: Member,
        points: int,
        source: str,
        new_balance: int
    ) -> Dict[str, Any]:
        """Track points earned event."""
        return self.track_event(
            event_name='tradeup_points_earned',
            email=member.email,
            properties={
                'member_number': member.member_number,
                'points_earned': points,
                'source': source,
                'new_balance': new_balance,
                'tier': member.tier.name if member.tier else 'none'
            }
        )

    def track_referral_success(
        self,
        referrer: Member,
        referee_email: str,
        reward_amount: Decimal
    ) -> Dict[str, Any]:
        """Track successful referral event."""
        return self.track_event(
            event_name='tradeup_referral_success',
            email=referrer.email,
            properties={
                'member_number': referrer.member_number,
                'referee_email': referee_email,
                'reward_amount': float(reward_amount),
                'total_referrals': referrer.referral_count or 0,
                'referral_code': referrer.referral_code
            }
        )

    def track_points_expiring(
        self,
        member: Member,
        expiring_points: int,
        days_until_expiry: int
    ) -> Dict[str, Any]:
        """Track points expiring warning event."""
        return self.track_event(
            event_name='tradeup_points_expiring',
            email=member.email,
            properties={
                'member_number': member.member_number,
                'expiring_points': expiring_points,
                'days_until_expiry': days_until_expiry,
                'current_balance': member.points_balance or 0,
                'tier': member.tier.name if member.tier else 'none'
            }
        )

    # ==================== LIST MANAGEMENT ====================

    def get_lists(self) -> Dict[str, Any]:
        """Get available Klaviyo lists."""
        if not self.is_enabled():
            return {'success': False, 'error': 'Klaviyo not enabled'}

        try:
            response = requests.get(
                f"{self.BASE_URL}/lists/",
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                lists = [
                    {
                        'id': lst.get('id'),
                        'name': lst.get('attributes', {}).get('name'),
                        'created': lst.get('attributes', {}).get('created')
                    }
                    for lst in data.get('data', [])
                ]
                return {
                    'success': True,
                    'lists': lists
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def add_to_list(self, list_id: str, email: str) -> Dict[str, Any]:
        """Add a profile to a list."""
        if not self.is_enabled():
            return {'success': False, 'error': 'Klaviyo not enabled'}

        payload = {
            "data": [
                {
                    "type": "profile",
                    "attributes": {
                        "email": email
                    }
                }
            ]
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/lists/{list_id}/relationships/profiles/",
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201, 202, 204]:
                return {
                    'success': True,
                    'message': f'Added to list {list_id}'
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    # ==================== BULK OPERATIONS ====================

    def sync_all_members(self, batch_size: int = 100) -> Dict[str, Any]:
        """
        Sync all members to Klaviyo.

        Args:
            batch_size: Number of members to process at a time

        Returns:
            Sync results summary
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Klaviyo not enabled'}

        results = {
            'total': 0,
            'synced': 0,
            'errors': []
        }

        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        results['total'] = len(members)

        for member in members:
            try:
                result = self.upsert_profile(member)
                if result.get('success'):
                    results['synced'] += 1
                else:
                    results['errors'].append({
                        'member_id': member.id,
                        'error': result.get('error')
                    })
            except Exception as e:
                results['errors'].append({
                    'member_id': member.id,
                    'error': str(e)
                })

        return {
            'success': len(results['errors']) == 0,
            **results
        }


def get_klaviyo_service(tenant_id: int) -> KlaviyoService:
    """Get Klaviyo service for a tenant."""
    return KlaviyoService(tenant_id)
