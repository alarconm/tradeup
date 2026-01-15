"""
Gorgias Integration Service for TradeUp.

Provides loyalty data for Gorgias customer service tickets,
enabling support agents to see member tier, credit balance,
and trade-in history directly in their support interface.

API Documentation: https://docs.gorgias.com/
"""

import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
from flask import current_app

from ..extensions import db
from ..models.member import Member
from ..models.tenant import Tenant
from ..models.trade_in import TradeInBatch


class GorgiasService:
    """
    Gorgias customer service integration.

    Provides widget data and webhook handling for displaying
    TradeUp member data in Gorgias tickets.

    Usage:
        service = GorgiasService(tenant_id)
        widget_data = service.get_widget_data(customer_email)
    """

    BASE_URL = "https://api.gorgias.com"

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._tenant = None
        self._settings = None
        self._api_key = None
        self._domain = None

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
                self._settings = integrations.get('gorgias', {})
        return self._settings

    @property
    def api_key(self) -> Optional[str]:
        if self._api_key is None:
            self._api_key = self.settings.get('api_key')
        return self._api_key

    @property
    def domain(self) -> Optional[str]:
        if self._domain is None:
            self._domain = self.settings.get('domain')  # e.g., 'mystore.gorgias.com'
        return self._domain

    def is_enabled(self) -> bool:
        """Check if Gorgias integration is enabled."""
        return bool(self.settings.get('enabled') and self.api_key and self.domain)

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            'Authorization': f'Basic {self.api_key}',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> Dict[str, Any]:
        """Test the Gorgias API connection."""
        if not self.api_key or not self.domain:
            return {'success': False, 'error': 'API key or domain not configured'}

        try:
            response = requests.get(
                f'https://{self.domain}/api/account',
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'account': {
                        'name': data.get('name'),
                        'domain': data.get('domain')
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Gorgias connection test failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_widget_data(self, customer_email: str) -> Dict[str, Any]:
        """
        Get TradeUp member data for Gorgias widget display.

        This data is shown in the Gorgias ticket sidebar to help
        support agents understand the customer's loyalty status.

        Args:
            customer_email: Customer's email address

        Returns:
            Dict with member data for widget display
        """
        # Find member by email
        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=customer_email
        ).first()

        if not member:
            return {
                'is_member': False,
                'message': 'Customer is not a TradeUp member'
            }

        # Build widget data
        widget_data = {
            'is_member': True,
            'member_id': member.id,
            'member_number': member.member_number,
            'name': member.name,
            'email': member.email,
            'status': member.status,
            'tier': {
                'name': member.tier.name if member.tier else 'No Tier',
                'level': member.tier.display_order if member.tier else 0
            },
            'member_since': member.membership_start_date.isoformat() if member.membership_start_date else None,
            'lifetime_spend': float(member.lifetime_spend or 0)
        }

        # Add credit balance if available
        from ..models.promotions import MemberCreditBalance
        credit_balance = MemberCreditBalance.query.filter_by(
            member_id=member.id
        ).first()

        if credit_balance:
            widget_data['credit_balance'] = float(credit_balance.available_credit or 0)
        else:
            widget_data['credit_balance'] = 0

        # Add points balance if available
        from ..models.loyalty_points import PointsBalance
        points_balance = PointsBalance.query.filter_by(
            member_id=member.id
        ).first()

        if points_balance:
            widget_data['points_balance'] = points_balance.current_balance or 0
        else:
            widget_data['points_balance'] = 0

        # Add recent trade-ins
        recent_trade_ins = TradeInBatch.query.filter_by(
            member_id=member.id
        ).order_by(TradeInBatch.created_at.desc()).limit(5).all()

        widget_data['recent_trade_ins'] = [{
            'id': ti.id,
            'status': ti.status,
            'item_count': ti.item_count or 0,
            'total_credit': float(ti.total_credit or 0),
            'created_at': ti.created_at.isoformat() if ti.created_at else None
        } for ti in recent_trade_ins]

        # Add referral stats
        widget_data['referral_count'] = member.referral_count or 0
        widget_data['referral_earnings'] = float(member.referral_earnings or 0)

        return widget_data

    def enrich_ticket(self, ticket_id: int, customer_email: str) -> Dict[str, Any]:
        """
        Enrich a Gorgias ticket with TradeUp member data.

        Adds internal notes to the ticket with loyalty information.

        Args:
            ticket_id: Gorgias ticket ID
            customer_email: Customer's email address

        Returns:
            Dict with success status
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Gorgias not enabled'}

        widget_data = self.get_widget_data(customer_email)

        if not widget_data.get('is_member'):
            return {'success': True, 'message': 'Customer not a member, no enrichment needed'}

        try:
            # Build internal note with member data
            note_content = self._build_ticket_note(widget_data)

            payload = {
                'ticket_id': ticket_id,
                'body_text': note_content,
                'channel': 'internal-note',
                'source': {
                    'type': 'tradeup'
                }
            }

            response = requests.post(
                f'https://{self.domain}/api/messages',
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201]:
                return {'success': True, 'message': 'Ticket enriched with TradeUp data'}
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Gorgias ticket enrichment failed: {e}")
            return {'success': False, 'error': str(e)}

    def _build_ticket_note(self, widget_data: Dict[str, Any]) -> str:
        """Build internal note content from widget data."""
        lines = [
            "═══ TradeUp Member Info ═══",
            f"Member: {widget_data.get('name', 'N/A')} ({widget_data.get('member_number', 'N/A')})",
            f"Tier: {widget_data.get('tier', {}).get('name', 'N/A')}",
            f"Store Credit: ${widget_data.get('credit_balance', 0):.2f}",
            f"Points: {widget_data.get('points_balance', 0):,}",
            f"Lifetime Spend: ${widget_data.get('lifetime_spend', 0):.2f}",
            f"Member Since: {widget_data.get('member_since', 'N/A')[:10] if widget_data.get('member_since') else 'N/A'}",
        ]

        if widget_data.get('recent_trade_ins'):
            lines.append("")
            lines.append("Recent Trade-Ins:")
            for ti in widget_data['recent_trade_ins'][:3]:
                lines.append(f"  • {ti['status']}: {ti['item_count']} items, ${ti['total_credit']:.2f}")

        return "\n".join(lines)

    def add_tag_to_ticket(self, ticket_id: int, tag: str) -> Dict[str, Any]:
        """
        Add a tag to a Gorgias ticket.

        Useful for automating ticket routing based on member tier.

        Args:
            ticket_id: Gorgias ticket ID
            tag: Tag to add (e.g., 'vip-member', 'gold-tier')

        Returns:
            Dict with success status
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Gorgias not enabled'}

        try:
            # Get current ticket
            response = requests.get(
                f'https://{self.domain}/api/tickets/{ticket_id}',
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code != 200:
                return {'success': False, 'error': 'Failed to get ticket'}

            ticket = response.json()
            current_tags = ticket.get('tags', [])

            # Check if tag already exists
            tag_names = [t.get('name') for t in current_tags]
            if tag in tag_names:
                return {'success': True, 'message': 'Tag already exists'}

            # Add new tag
            new_tags = current_tags + [{'name': tag}]

            update_response = requests.put(
                f'https://{self.domain}/api/tickets/{ticket_id}',
                headers=self._get_headers(),
                json={'tags': new_tags},
                timeout=10
            )

            if update_response.status_code == 200:
                return {'success': True, 'message': f'Tag "{tag}" added'}
            else:
                return {
                    'success': False,
                    'error': f'API error: {update_response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Gorgias add tag failed: {e}")
            return {'success': False, 'error': str(e)}


def get_gorgias_service(tenant_id: int) -> GorgiasService:
    """Get Gorgias service for a tenant."""
    return GorgiasService(tenant_id)
