"""
Trade-in service for managing batches and items.

Handles trade-in batches, items, and tier-based bonus credit.
Bonus = trade_in_value × tier.bonus_rate
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from flask import current_app
from ..extensions import db
from ..models import Member, TradeInBatch, TradeInItem


class TradeInService:
    """Service for trade-in operations."""

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._store_credit_service = None

    @property
    def store_credit_service(self):
        """Lazy load store credit service."""
        if self._store_credit_service is None:
            from .store_credit_service import store_credit_service
            self._store_credit_service = store_credit_service
        return self._store_credit_service

    # Category choices for TCGs and collectibles
    CATEGORIES = {
        'pokemon': {'icon': '⚡', 'name': 'Pokemon'},
        'magic': {'icon': '🔮', 'name': 'Magic: The Gathering'},
        'yugioh': {'icon': '🃏', 'name': 'Yu-Gi-Oh!'},
        'sports': {'icon': '🏈', 'name': 'Sports Cards'},
        'baseball': {'icon': '⚾', 'name': 'Baseball Cards'},
        'basketball': {'icon': '🏀', 'name': 'Basketball Cards'},
        'football': {'icon': '🏈', 'name': 'Football Cards'},
        'hockey': {'icon': '🏒', 'name': 'Hockey Cards'},
        'one_piece': {'icon': '🏴‍☠️', 'name': 'One Piece'},
        'disney_lorcana': {'icon': '✨', 'name': 'Disney Lorcana'},
        'flesh_blood': {'icon': '⚔️', 'name': 'Flesh and Blood'},
        'digimon': {'icon': '🦖', 'name': 'Digimon'},
        'weiss': {'icon': '🎭', 'name': 'Weiss Schwarz'},
        'tcg_other': {'icon': '🎴', 'name': 'Other TCG'},
        'videogames': {'icon': '🎮', 'name': 'Video Games'},
        'comics': {'icon': '📚', 'name': 'Comics'},
        'figures': {'icon': '🎨', 'name': 'Figures & Toys'},
        'other': {'icon': '📦', 'name': 'Other'},
    }

    def create_batch(
        self,
        member_id: Optional[int] = None,
        guest_name: Optional[str] = None,
        guest_email: Optional[str] = None,
        guest_phone: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[str] = None,
        category: Optional[str] = None
    ) -> TradeInBatch:
        """
        Create a new trade-in batch for a member or guest.

        Supports both member and non-member trade-ins:
        - For members: provide member_id
        - For guests: provide guest_name and/or guest_email

        Args:
            member_id: ID of the member trading in items (optional for guests)
            guest_name: Name of guest customer (for non-member trade-ins)
            guest_email: Email of guest customer (for non-member trade-ins)
            guest_phone: Phone of guest customer (for non-member trade-ins)
            notes: Optional notes about the batch
            created_by: Employee who processed the trade-in
            category: Category of items (sports, pokemon, magic, riftbound, tcg_other, other)

        Returns:
            Created TradeInBatch object

        Raises:
            ValueError: If member_id provided but member not found/inactive,
                       or if neither member_id nor guest info provided
        """
        # Validate - need either member or guest info
        if not member_id and not (guest_name or guest_email):
            raise ValueError('Either member_id or guest info (name/email) is required')

        # If member_id provided, validate it
        member = None
        if member_id:
            member = Member.query.get(member_id)
            if not member or member.tenant_id != self.tenant_id:
                raise ValueError('Member not found')
            if member.status != 'active':
                raise ValueError('Member is not active')

        # Validate category
        valid_category = category if category in self.CATEGORIES else 'other'

        batch_reference = TradeInBatch.generate_batch_reference(self.tenant_id)

        batch = TradeInBatch(
            tenant_id=self.tenant_id,  # Required for tenant isolation
            member_id=member_id,
            guest_name=guest_name,
            guest_email=guest_email,
            guest_phone=guest_phone,
            batch_reference=batch_reference,
            trade_in_date=datetime.utcnow(),
            status='pending',
            category=valid_category,
            notes=notes,
            created_by=created_by
        )

        db.session.add(batch)
        db.session.commit()

        # Sync to partner integrations (async/non-blocking)
        try:
            from .partner_sync_service import PartnerSyncService
            sync_service = PartnerSyncService(self.tenant_id)
            sync_service.sync_trade_in(batch)
        except Exception as e:
            # Log but don't fail the trade-in creation
            print(f"Partner sync error (non-blocking): {e}")

        # Send trade-in created email notification
        try:
            from .notification_service import notification_service
            notification_service.send_trade_in_created(
                tenant_id=self.tenant_id,
                batch_id=batch.id
            )
        except Exception as e:
            # Log but don't fail the trade-in creation
            print(f"Notification error (non-blocking): {e}")

        return batch

    def add_item(
        self,
        batch_id: int,
        trade_value: Decimal,
        product_title: Optional[str] = None,
        product_sku: Optional[str] = None,
        market_value: Optional[Decimal] = None,
        notes: Optional[str] = None
    ) -> TradeInItem:
        """
        Add an item to a trade-in batch.

        Args:
            batch_id: ID of the batch
            trade_value: What the shop paid for the item
            product_title: Product title/description
            product_sku: SKU or identifier
            market_value: TCGPlayer market value
            notes: Item notes

        Returns:
            Created TradeInItem object
        """
        batch = TradeInBatch.query.get(batch_id)
        if not batch:
            raise ValueError('Batch not found')
        if batch.tenant_id != self.tenant_id:
            raise ValueError('Batch not found')  # Don't reveal tenant mismatch

        item = TradeInItem(
            batch_id=batch_id,
            trade_value=trade_value,
            product_title=product_title,
            product_sku=product_sku,
            market_value=market_value,
            notes=notes
        )

        db.session.add(item)

        # Update batch totals
        batch.total_items += 1
        batch.total_trade_value = (batch.total_trade_value or Decimal('0')) + trade_value

        db.session.commit()

        return item

    def add_items_bulk(
        self,
        batch_id: int,
        items_data: List[Dict[str, Any]]
    ) -> List[TradeInItem]:
        """
        Add multiple items to a batch.

        Args:
            batch_id: ID of the batch
            items_data: List of item dictionaries

        Returns:
            List of created TradeInItem objects
        """
        batch = TradeInBatch.query.get(batch_id)
        if not batch:
            raise ValueError('Batch not found')
        if batch.tenant_id != self.tenant_id:
            raise ValueError('Batch not found')  # Don't reveal tenant mismatch

        created_items = []
        total_value = Decimal('0')

        for item_data in items_data:
            item = TradeInItem(
                batch_id=batch_id,
                trade_value=Decimal(str(item_data['trade_value'])),
                product_title=item_data.get('product_title'),
                product_sku=item_data.get('product_sku'),
                market_value=Decimal(str(item_data['market_value'])) if item_data.get('market_value') else None,
                notes=item_data.get('notes')
            )
            db.session.add(item)
            created_items.append(item)
            total_value += item.trade_value

        # Update batch totals
        batch.total_items += len(created_items)
        batch.total_trade_value = (batch.total_trade_value or Decimal('0')) + total_value

        db.session.commit()

        return created_items

    def mark_item_listed(
        self,
        item_id: int,
        shopify_product_id: str,
        listing_price: Decimal,
        product_title: Optional[str] = None
    ) -> TradeInItem:
        """
        Mark an item as listed in Shopify.

        Args:
            item_id: ID of the item
            shopify_product_id: Shopify product ID
            listing_price: Listed price
            product_title: Updated title (if different)

        Returns:
            Updated TradeInItem object
        """
        item = TradeInItem.query.get(item_id)
        if not item:
            raise ValueError('Item not found')

        item.shopify_product_id = shopify_product_id
        item.listing_price = listing_price
        item.listed_date = datetime.utcnow()

        if product_title:
            item.product_title = product_title

        # Check if all items in batch are listed
        batch = item.batch
        unlisted_count = TradeInItem.query.filter_by(
            batch_id=batch.id,
            listed_date=None
        ).count()

        if unlisted_count == 0:
            batch.status = 'listed'

        db.session.commit()

        return item

    def record_sale(
        self,
        shopify_product_id: str,
        sold_price: Decimal,
        shopify_order_id: Optional[str] = None
    ) -> Optional[TradeInItem]:
        """
        Record a sale for a trade-in item.

        Args:
            shopify_product_id: Shopify product ID
            sold_price: Sale price
            shopify_order_id: Shopify order ID

        Returns:
            Updated TradeInItem or None if not found
        """
        item = TradeInItem.query.filter_by(
            shopify_product_id=shopify_product_id
        ).first()

        if not item:
            return None

        item.sold_date = datetime.utcnow()
        item.sold_price = sold_price
        item.shopify_order_id = shopify_order_id

        # Calculate days to sell (for analytics)
        if item.listed_date:
            item.days_to_sell = item.calculate_days_to_sell()

        db.session.commit()

        return item

    def get_batch_by_member_tag(self, member_number: str) -> List[TradeInBatch]:
        """
        Get trade-in batches by member number tag.

        Args:
            member_number: Member number (TU1001 or legacy QF1001)

        Returns:
            List of TradeInBatch objects
        """
        # Normalize member number - support both TU and legacy QF prefixes
        upper_num = member_number.upper()
        if not upper_num.startswith('TU') and not upper_num.startswith('QF'):
            member_number = f'TU{member_number}'
        else:
            member_number = upper_num

        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            member_number=member_number
        ).first()

        if not member:
            return []

        return TradeInBatch.query.filter_by(member_id=member.id).all()

    def get_pending_items(self) -> List[TradeInItem]:
        """Get items that are listed but not yet sold."""
        return (
            TradeInItem.query
            .join(TradeInItem.batch)
            .join(Member)
            .filter(
                Member.tenant_id == self.tenant_id,
                TradeInItem.listed_date.isnot(None),
                TradeInItem.sold_date.is_(None)
            )
            .all()
        )

    def complete_batch(
        self,
        batch_id: int,
        created_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Complete a trade-in batch and issue tier bonus credit.

        When a batch is completed:
        1. Calculate bonus based on total trade value × tier.bonus_rate
        2. Issue bonus as store credit (synced to Shopify)
        3. Update member stats
        4. Mark batch as completed

        Args:
            batch_id: ID of the batch to complete
            created_by: Who completed the batch

        Returns:
            Dict with completion details and bonus info
        """
        batch = TradeInBatch.query.get(batch_id)
        if not batch:
            raise ValueError('Batch not found')
        if batch.tenant_id != self.tenant_id:
            raise ValueError('Batch not found')  # Don't reveal tenant mismatch

        if batch.status == 'completed':
            raise ValueError('Batch is already completed')

        member = batch.member
        is_guest = member is None

        # Calculate bonus (only for members)
        bonus_info = self.calculate_tier_bonus(batch)

        # Issue bonus credit if member has a tier with bonus
        bonus_entry = None
        if not is_guest and bonus_info['bonus_amount'] > 0:
            from ..models.promotions import CreditEventType
            bonus_entry = self.store_credit_service.add_credit(
                member_id=member.id,
                amount=Decimal(str(bonus_info['bonus_amount'])),
                event_type=CreditEventType.TRADE_IN.value,
                description=f"Trade-in bonus ({bonus_info['tier_name']} tier {bonus_info['bonus_percent']}%)",
                source_type='trade_in',
                source_id=str(batch.id),
                source_reference=batch.batch_reference,
                created_by=created_by,
                sync_to_shopify=True
            )

        # Update batch
        batch.status = 'completed'
        batch.completed_at = datetime.utcnow()
        batch.completed_by = created_by
        batch.bonus_amount = Decimal(str(bonus_info['bonus_amount'])) if not is_guest else Decimal('0')

        # Update member stats (only for members)
        if not is_guest:
            member.total_trade_ins = (member.total_trade_ins or 0) + 1
            member.total_trade_value = (member.total_trade_value or Decimal('0')) + batch.total_trade_value
            if bonus_info['bonus_amount'] > 0:
                member.total_bonus_earned = (member.total_bonus_earned or Decimal('0')) + Decimal(str(bonus_info['bonus_amount']))

        db.session.commit()

        # Send completion email notification
        try:
            from .notification_service import notification_service
            notification_service.send_trade_in_completed(
                tenant_id=self.tenant_id,
                batch_id=batch.id,
                bonus_amount=float(bonus_info['bonus_amount']) if not is_guest else 0
            )
        except Exception as e:
            # Log but don't fail the completion
            print(f"Failed to send trade-in completion email: {e}")

        # Sync member metafields to Shopify (trade count, bonus earned, etc.)
        if not is_guest and member.shopify_customer_id:
            try:
                from .membership_service import MembershipService
                from .shopify_client import ShopifyClient
                shopify_client = ShopifyClient(self.tenant_id)
                membership_svc = MembershipService(self.tenant_id, shopify_client)
                membership_svc.sync_member_metafields_to_shopify(member)

                # Trigger Shopify Flow event for trade-in completion
                from .flow_service import FlowService
                flow_svc = FlowService(self.tenant_id, shopify_client)
                flow_svc.trigger_trade_in_completed(
                    member_id=member.id,
                    member_number=member.member_number,
                    email=member.email,
                    batch_reference=batch.batch_reference,
                    trade_value=float(batch.total_trade_value or 0),
                    bonus_amount=float(bonus_info['bonus_amount']),
                    item_count=batch.total_items,
                    category=batch.category or 'other',
                    shopify_customer_id=member.shopify_customer_id
                )
            except Exception as sync_err:
                print(f"Failed to sync metafields/trigger Flow: {sync_err}")

        # Build response
        result = {
            'success': True,
            'batch_id': batch.id,
            'batch_reference': batch.batch_reference,
            'trade_value': float(batch.total_trade_value),
            'is_guest': is_guest,
            'bonus': bonus_info if not is_guest else {'eligible': False, 'reason': 'Guest trade-in (no bonus)', 'bonus_amount': 0},
            'bonus_credit_entry': bonus_entry.to_dict() if bonus_entry else None,
        }

        if is_guest:
            result['guest'] = {
                'name': batch.guest_name,
                'email': batch.guest_email,
                'phone': batch.guest_phone
            }
        else:
            result['member'] = {
                'id': member.id,
                'member_number': member.member_number,
                'total_bonus_earned': float(member.total_bonus_earned)
            }

        return result

    def calculate_tier_bonus(self, batch: TradeInBatch) -> Dict[str, Any]:
        """
        Calculate tier-based bonus for a trade-in batch.

        Bonus = total_trade_value × tier.bonus_rate

        Args:
            batch: TradeInBatch to calculate bonus for

        Returns:
            Dict with bonus calculation details
        """
        member = batch.member
        if not member or not member.tier:
            return {
                'eligible': False,
                'reason': 'Member has no active tier',
                'tier_name': None,
                'bonus_percent': 0,
                'bonus_amount': 0,
                'trade_value': float(batch.total_trade_value or 0)
            }

        tier = member.tier
        trade_value = batch.total_trade_value or Decimal('0')
        bonus_rate = tier.bonus_rate or Decimal('0')
        bonus_amount = trade_value * bonus_rate

        # Round to 2 decimal places
        bonus_amount = Decimal(str(round(float(bonus_amount), 2)))

        return {
            'eligible': True,
            'reason': f'{tier.name} tier bonus',
            'tier_name': tier.name,
            'tier_id': tier.id,
            'bonus_percent': float(bonus_rate * 100),
            'bonus_rate': float(bonus_rate),
            'trade_value': float(trade_value),
            'bonus_amount': float(bonus_amount)
        }

    def preview_batch_bonus(self, batch_id: int) -> Dict[str, Any]:
        """
        Preview the bonus that would be issued for a batch.
        Does NOT issue the bonus - just calculates it.

        Args:
            batch_id: ID of the batch

        Returns:
            Dict with bonus preview
        """
        batch = TradeInBatch.query.get(batch_id)
        if not batch:
            raise ValueError('Batch not found')
        if batch.tenant_id != self.tenant_id:
            raise ValueError('Batch not found')  # Don't reveal tenant mismatch

        bonus_info = self.calculate_tier_bonus(batch)

        return {
            'batch_id': batch.id,
            'batch_reference': batch.batch_reference,
            'status': batch.status,
            'total_items': batch.total_items,
            'trade_value': float(batch.total_trade_value or 0),
            'bonus': bonus_info
        }

    def update_status(
        self,
        batch_id: int,
        new_status: str,
        reason: Optional[str] = None,
        updated_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Update trade-in batch status and sync to Shopify customer metafields.

        Valid status transitions:
        - pending -> under_review, approved, rejected, cancelled
        - under_review -> approved, rejected
        - approved -> completed, listed
        - listed -> completed

        Args:
            batch_id: ID of the batch to update
            new_status: New status value
            reason: Optional reason for status change (useful for rejections)
            updated_by: Who made the update

        Returns:
            Dict with update result
        """
        valid_statuses = ['pending', 'under_review', 'approved', 'rejected',
                         'completed', 'listed', 'cancelled']

        if new_status not in valid_statuses:
            raise ValueError(f'Invalid status: {new_status}. Valid: {valid_statuses}')

        batch = TradeInBatch.query.get(batch_id)
        if not batch:
            raise ValueError('Batch not found')
        if batch.tenant_id != self.tenant_id:
            raise ValueError('Batch not found')

        old_status = batch.status

        # Update the batch
        batch.status = new_status
        batch.updated_at = datetime.utcnow()

        # Store rejection/cancellation reason in notes
        if reason and new_status in ['rejected', 'cancelled']:
            batch.notes = f"{batch.notes or ''}\n[{new_status.upper()}] {reason}".strip()

        db.session.commit()

        # Sync to Shopify customer metafields if member exists
        member = batch.member
        if member and member.shopify_customer_id:
            self._sync_trade_in_status_to_shopify(member, batch)

        # Send status notification email
        try:
            from .notification_service import notification_service
            if new_status == 'approved':
                notification_service.send_trade_in_approved(
                    tenant_id=self.tenant_id,
                    batch_id=batch.id
                )
            elif new_status == 'rejected':
                notification_service.send_trade_in_rejected(
                    tenant_id=self.tenant_id,
                    batch_id=batch.id,
                    reason=reason
                )
        except Exception as e:
            print(f"Failed to send status notification: {e}")

        return {
            'success': True,
            'batch_id': batch.id,
            'batch_reference': batch.batch_reference,
            'old_status': old_status,
            'new_status': new_status,
            'reason': reason,
            'member_synced': member is not None and member.shopify_customer_id is not None
        }

    def _sync_trade_in_status_to_shopify(self, member: Member, batch: TradeInBatch) -> bool:
        """
        Sync trade-in status to Shopify customer metafields.

        Updates metafields:
        - tradeup.latest_trade_in_status: Current status
        - tradeup.latest_trade_in_reference: Batch reference number
        - tradeup.latest_trade_in_date: Date of trade-in
        - tradeup.trade_in_count: Total number of trade-ins
        - tradeup.trade_in_total_value: Lifetime trade-in value

        Args:
            member: Member whose metafields to update
            batch: The trade-in batch

        Returns:
            True if sync succeeded
        """
        if not member.shopify_customer_id:
            return False

        try:
            from .shopify_client import ShopifyClient
            shopify_client = ShopifyClient(self.tenant_id)

            # Build metafields to sync
            metafields = [
                {
                    'namespace': 'tradeup',
                    'key': 'latest_trade_in_status',
                    'value': batch.status,
                    'type': 'single_line_text_field'
                },
                {
                    'namespace': 'tradeup',
                    'key': 'latest_trade_in_reference',
                    'value': batch.batch_reference,
                    'type': 'single_line_text_field'
                },
                {
                    'namespace': 'tradeup',
                    'key': 'latest_trade_in_date',
                    'value': batch.trade_in_date.isoformat() if batch.trade_in_date else '',
                    'type': 'single_line_text_field'
                },
                {
                    'namespace': 'tradeup',
                    'key': 'trade_in_count',
                    'value': str(member.total_trade_ins or 0),
                    'type': 'number_integer'
                },
                {
                    'namespace': 'tradeup',
                    'key': 'trade_in_total_value',
                    'value': str(float(member.total_trade_value or 0)),
                    'type': 'number_decimal'
                }
            ]

            result = shopify_client.set_customer_metafields(
                customer_id=member.shopify_customer_id,
                metafields=metafields
            )

            if result.get('success'):
                current_app.logger.info(
                    f"Synced trade-in status to Shopify for member {member.member_number}: {batch.status}"
                )
                return True
            else:
                current_app.logger.warning(
                    f"Failed to sync trade-in metafields: {result.get('error')}"
                )
                return False

        except Exception as e:
            current_app.logger.error(
                f"Error syncing trade-in status to Shopify: {e}"
            )
            return False

    def get_member_trade_in_summary(self, member_id: int) -> Dict[str, Any]:
        """
        Get trade-in summary for a member (for customer account display).

        Args:
            member_id: Member ID

        Returns:
            Dict with trade-in summary
        """
        member = Member.query.get(member_id)
        if not member or member.tenant_id != self.tenant_id:
            return {'success': False, 'error': 'Member not found'}

        # Get recent trade-ins
        recent_batches = TradeInBatch.query.filter_by(
            member_id=member_id
        ).order_by(TradeInBatch.created_at.desc()).limit(5).all()

        # Get counts by status
        status_counts = db.session.query(
            TradeInBatch.status,
            db.func.count(TradeInBatch.id)
        ).filter(
            TradeInBatch.member_id == member_id
        ).group_by(TradeInBatch.status).all()

        counts = {status: count for status, count in status_counts}

        return {
            'success': True,
            'member_id': member_id,
            'total_trade_ins': member.total_trade_ins or 0,
            'total_trade_value': float(member.total_trade_value or 0),
            'total_bonus_earned': float(member.total_bonus_earned or 0),
            'status_counts': counts,
            'recent_trade_ins': [b.to_dict() for b in recent_batches]
        }
