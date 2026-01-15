"""
Cashback Service for TradeUp.

Manages cashback campaigns and processes order cashback calculations.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from flask import current_app

from ..extensions import db
from ..models.member import Member
from ..models.tenant import Tenant
from ..models.cashback_campaign import CashbackCampaign, CashbackRedemption
from ..models.promotions import CreditEventType


class CashbackService:
    """
    Service for managing cashback campaigns.

    Usage:
        service = CashbackService(tenant_id)
        campaigns = service.get_active_campaigns()
        cashback = service.process_order_cashback(order_data, member)
    """

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    # ==================== CAMPAIGN MANAGEMENT ====================

    def create_campaign(self, data: Dict[str, Any], created_by: str = None) -> Dict[str, Any]:
        """
        Create a new cashback campaign.

        Args:
            data: Campaign configuration
            created_by: User creating the campaign

        Returns:
            Dict with created campaign
        """
        try:
            campaign = CashbackCampaign(
                tenant_id=self.tenant_id,
                name=data['name'],
                description=data.get('description'),
                internal_notes=data.get('internal_notes'),
                cashback_rate=Decimal(str(data['cashback_rate'])),
                min_purchase=Decimal(str(data['min_purchase'])) if data.get('min_purchase') else None,
                max_cashback=Decimal(str(data['max_cashback'])) if data.get('max_cashback') else None,
                max_total_cashback=Decimal(str(data['max_total_cashback'])) if data.get('max_total_cashback') else None,
                start_date=datetime.fromisoformat(data['start_date'].replace('Z', '+00:00')),
                end_date=datetime.fromisoformat(data['end_date'].replace('Z', '+00:00')),
                applies_to=data.get('applies_to', 'all'),
                applies_to_new_customers=data.get('applies_to_new_customers', True),
                applies_to_existing_customers=data.get('applies_to_existing_customers', True),
                stackable_with_discounts=data.get('stackable_with_discounts', True),
                stackable_with_promotions=data.get('stackable_with_promotions', True),
                max_uses_total=data.get('max_uses_total'),
                max_uses_per_customer=data.get('max_uses_per_customer', 1),
                status='draft',
                created_by=created_by
            )

            # Handle tier restriction
            if data.get('tier_restriction'):
                import json
                campaign.tier_restriction = json.dumps(data['tier_restriction'])

            # Handle product filters
            if data.get('included_products'):
                import json
                campaign.included_products = json.dumps(data['included_products'])
            if data.get('excluded_products'):
                import json
                campaign.excluded_products = json.dumps(data['excluded_products'])

            db.session.add(campaign)
            db.session.commit()

            return {
                'success': True,
                'campaign': campaign.to_dict_admin()
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to create cashback campaign: {e}")
            return {'success': False, 'error': str(e)}

    def update_campaign(self, campaign_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing campaign."""
        campaign = CashbackCampaign.query.filter_by(
            id=campaign_id,
            tenant_id=self.tenant_id
        ).first()

        if not campaign:
            return {'success': False, 'error': 'Campaign not found'}

        # Can't update active campaigns (except to pause/cancel)
        if campaign.status == 'active' and 'status' not in data:
            return {'success': False, 'error': 'Cannot modify active campaign. Pause it first.'}

        try:
            # Update allowed fields
            updateable = [
                'name', 'description', 'internal_notes', 'cashback_rate',
                'min_purchase', 'max_cashback', 'max_total_cashback',
                'start_date', 'end_date', 'applies_to', 'applies_to_new_customers',
                'applies_to_existing_customers', 'stackable_with_discounts',
                'stackable_with_promotions', 'max_uses_total', 'max_uses_per_customer',
                'status'
            ]

            for field in updateable:
                if field in data:
                    value = data[field]

                    # Handle decimal fields
                    if field in ['cashback_rate', 'min_purchase', 'max_cashback', 'max_total_cashback']:
                        value = Decimal(str(value)) if value is not None else None

                    # Handle datetime fields
                    if field in ['start_date', 'end_date'] and value:
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))

                    setattr(campaign, field, value)

            # Handle JSON fields
            if 'tier_restriction' in data:
                import json
                campaign.tier_restriction = json.dumps(data['tier_restriction']) if data['tier_restriction'] else None

            db.session.commit()

            return {
                'success': True,
                'campaign': campaign.to_dict_admin()
            }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    def activate_campaign(self, campaign_id: int) -> Dict[str, Any]:
        """Activate a campaign."""
        campaign = CashbackCampaign.query.filter_by(
            id=campaign_id,
            tenant_id=self.tenant_id
        ).first()

        if not campaign:
            return {'success': False, 'error': 'Campaign not found'}

        if campaign.status not in ['draft', 'scheduled', 'paused']:
            return {'success': False, 'error': f'Cannot activate campaign with status: {campaign.status}'}

        campaign.status = 'active'
        campaign.activated_at = datetime.utcnow()
        db.session.commit()

        return {
            'success': True,
            'campaign': campaign.to_dict(),
            'message': 'Campaign activated'
        }

    def pause_campaign(self, campaign_id: int) -> Dict[str, Any]:
        """Pause an active campaign."""
        campaign = CashbackCampaign.query.filter_by(
            id=campaign_id,
            tenant_id=self.tenant_id
        ).first()

        if not campaign:
            return {'success': False, 'error': 'Campaign not found'}

        if campaign.status != 'active':
            return {'success': False, 'error': 'Can only pause active campaigns'}

        campaign.status = 'paused'
        db.session.commit()

        return {
            'success': True,
            'campaign': campaign.to_dict(),
            'message': 'Campaign paused'
        }

    def end_campaign(self, campaign_id: int) -> Dict[str, Any]:
        """End a campaign."""
        campaign = CashbackCampaign.query.filter_by(
            id=campaign_id,
            tenant_id=self.tenant_id
        ).first()

        if not campaign:
            return {'success': False, 'error': 'Campaign not found'}

        campaign.status = 'ended'
        campaign.ended_at = datetime.utcnow()
        db.session.commit()

        return {
            'success': True,
            'campaign': campaign.to_dict(),
            'message': 'Campaign ended'
        }

    def delete_campaign(self, campaign_id: int) -> Dict[str, Any]:
        """Delete a campaign (only draft campaigns)."""
        campaign = CashbackCampaign.query.filter_by(
            id=campaign_id,
            tenant_id=self.tenant_id
        ).first()

        if not campaign:
            return {'success': False, 'error': 'Campaign not found'}

        if campaign.status not in ['draft']:
            return {'success': False, 'error': 'Can only delete draft campaigns'}

        db.session.delete(campaign)
        db.session.commit()

        return {'success': True, 'message': 'Campaign deleted'}

    def get_campaign(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        """Get a single campaign."""
        campaign = CashbackCampaign.query.filter_by(
            id=campaign_id,
            tenant_id=self.tenant_id
        ).first()

        if not campaign:
            return None

        return campaign.to_dict_admin()

    def get_campaigns(
        self,
        status: str = None,
        include_stats: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all campaigns for the tenant.

        Args:
            status: Filter by status
            include_stats: Include redemption stats

        Returns:
            List of campaigns
        """
        query = CashbackCampaign.query.filter_by(tenant_id=self.tenant_id)

        if status:
            query = query.filter_by(status=status)

        campaigns = query.order_by(CashbackCampaign.created_at.desc()).all()

        result = []
        for campaign in campaigns:
            data = campaign.to_dict()

            if include_stats:
                data['stats'] = self._get_campaign_stats(campaign.id)

            result.append(data)

        return result

    def get_active_campaigns(self) -> List[CashbackCampaign]:
        """Get currently active campaigns."""
        now = datetime.utcnow()
        return CashbackCampaign.query.filter(
            CashbackCampaign.tenant_id == self.tenant_id,
            CashbackCampaign.status.in_(['active', 'scheduled']),
            CashbackCampaign.start_date <= now,
            CashbackCampaign.end_date >= now
        ).all()

    # ==================== ORDER PROCESSING ====================

    def process_order_cashback(
        self,
        order_data: Dict[str, Any],
        member: Member = None,
        customer_email: str = None
    ) -> Dict[str, Any]:
        """
        Process cashback for an order.

        Called from order webhook to calculate and issue cashback.

        Args:
            order_data: Shopify order data
            member: Member (if applicable)
            customer_email: Customer email (for non-members)

        Returns:
            Dict with cashback details
        """
        order_total = Decimal(str(order_data.get('subtotal_price', order_data.get('total_price', 0))))
        order_id = order_data.get('id') or order_data.get('shopify_order_id')
        order_number = order_data.get('order_number') or order_data.get('name')

        # Get active campaigns
        active_campaigns = self.get_active_campaigns()

        if not active_campaigns:
            return {
                'success': True,
                'cashback': Decimal('0'),
                'message': 'No active cashback campaigns'
            }

        # Determine customer attributes
        is_new = self._is_new_customer(order_data)
        tier_name = member.tier.name if member and member.tier else None
        email = member.email if member else customer_email or order_data.get('email')

        results = {
            'order_id': order_id,
            'order_total': float(order_total),
            'campaigns_applied': [],
            'total_cashback': Decimal('0')
        }

        for campaign in active_campaigns:
            # Check eligibility
            eligible, reason = campaign.check_customer_eligibility(
                customer_id=email,
                is_new=is_new,
                tier_name=tier_name
            )

            if not eligible:
                continue

            # Check per-customer limit
            if member and campaign.max_uses_per_customer:
                existing_redemptions = CashbackRedemption.query.filter_by(
                    campaign_id=campaign.id,
                    member_id=member.id
                ).count()

                if existing_redemptions >= campaign.max_uses_per_customer:
                    continue

            # Calculate cashback
            cashback = campaign.calculate_cashback(order_total)

            if cashback <= 0:
                continue

            # Record redemption
            redemption = CashbackRedemption(
                tenant_id=self.tenant_id,
                campaign_id=campaign.id,
                member_id=member.id if member else None,
                shopify_order_id=str(order_id),
                order_number=str(order_number),
                order_total=order_total,
                cashback_rate=campaign.cashback_rate,
                cashback_amount=cashback,
                customer_email=email,
                customer_tier=tier_name
            )
            db.session.add(redemption)

            # Update campaign usage
            campaign.record_usage(cashback)

            results['campaigns_applied'].append({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'cashback_rate': float(campaign.cashback_rate),
                'cashback_amount': float(cashback)
            })

            results['total_cashback'] += cashback

        if results['total_cashback'] > 0:
            # Issue the store credit
            from .store_credit_service import store_credit_service

            if member:
                try:
                    entry = store_credit_service.add_credit(
                        member_id=member.id,
                        amount=results['total_cashback'],
                        event_type=CreditEventType.PROMOTION_BONUS.value,
                        description=f'Cashback from order {order_number}',
                        source_type='cashback',
                        source_id=str(order_id),
                        created_by='system:cashback',
                        sync_to_shopify=True
                    )

                    # Update redemption records
                    for redemption in CashbackRedemption.query.filter_by(
                        shopify_order_id=str(order_id)
                    ).all():
                        redemption.credit_issued = True
                        redemption.credit_entry_id = entry.id if entry else None
                        redemption.issued_at = datetime.utcnow()

                except Exception as e:
                    current_app.logger.error(f"Failed to issue cashback credit: {e}")
                    results['credit_error'] = str(e)

            db.session.commit()

        results['total_cashback'] = float(results['total_cashback'])
        results['success'] = True

        return results

    def _is_new_customer(self, order_data: Dict) -> bool:
        """Check if this is a new customer."""
        # Check orders_count from Shopify customer data
        customer = order_data.get('customer', {})
        orders_count = customer.get('orders_count', 1)
        return orders_count <= 1

    def _get_campaign_stats(self, campaign_id: int) -> Dict[str, Any]:
        """Get statistics for a campaign."""
        from sqlalchemy import func

        redemptions = CashbackRedemption.query.filter_by(
            campaign_id=campaign_id
        )

        total_redemptions = redemptions.count()
        total_cashback = db.session.query(
            func.sum(CashbackRedemption.cashback_amount)
        ).filter_by(campaign_id=campaign_id).scalar() or Decimal('0')

        total_order_value = db.session.query(
            func.sum(CashbackRedemption.order_total)
        ).filter_by(campaign_id=campaign_id).scalar() or Decimal('0')

        unique_customers = db.session.query(
            func.count(func.distinct(CashbackRedemption.customer_email))
        ).filter_by(campaign_id=campaign_id).scalar() or 0

        return {
            'total_redemptions': total_redemptions,
            'total_cashback_issued': float(total_cashback),
            'total_order_value': float(total_order_value),
            'unique_customers': unique_customers,
            'average_order_value': float(total_order_value / total_redemptions) if total_redemptions > 0 else 0
        }


def get_cashback_service(tenant_id: int) -> CashbackService:
    """Get cashback service for a tenant."""
    return CashbackService(tenant_id)
