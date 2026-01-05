"""
Trade-in service for managing batches and items.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from ..extensions import db
from ..models import Member, TradeInBatch, TradeInItem


class TradeInService:
    """Service for trade-in operations."""

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    # Category choices matching ORB Sports Cards
    CATEGORIES = {
        'sports': {'icon': '🏈', 'name': 'Sports'},
        'pokemon': {'icon': '⚡', 'name': 'Pokemon'},
        'magic': {'icon': '🔮', 'name': 'Magic'},
        'riftbound': {'icon': '🌀', 'name': 'Riftbound'},
        'tcg_other': {'icon': '🎴', 'name': 'TCG Other'},
        'other': {'icon': '📦', 'name': 'Other'},
    }

    def create_batch(
        self,
        member_id: int,
        notes: Optional[str] = None,
        created_by: Optional[str] = None,
        category: Optional[str] = None
    ) -> TradeInBatch:
        """
        Create a new trade-in batch for a member.

        Args:
            member_id: ID of the member trading in items
            notes: Optional notes about the batch
            created_by: Employee who processed the trade-in
            category: Category of items (sports, pokemon, magic, riftbound, tcg_other, other)

        Returns:
            Created TradeInBatch object

        Raises:
            ValueError: If member not found or not active
        """
        member = Member.query.get(member_id)
        if not member or member.tenant_id != self.tenant_id:
            raise ValueError('Member not found')

        if member.status != 'active':
            raise ValueError('Member is not active')

        # Validate category
        valid_category = category if category in self.CATEGORIES else 'other'

        batch_reference = TradeInBatch.generate_batch_reference(self.tenant_id)

        batch = TradeInBatch(
            member_id=member_id,
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

        # Calculate days to sell
        if item.listed_date:
            item.days_to_sell = item.calculate_days_to_sell()

            # Check bonus eligibility
            member = item.batch.member
            if member and member.tier:
                quick_flip_days = member.tier.quick_flip_days
                item.eligible_for_bonus = item.days_to_sell <= quick_flip_days

        db.session.commit()

        return item

    def get_batch_by_member_tag(self, member_number: str) -> List[TradeInBatch]:
        """
        Get trade-in batches by member number tag.

        Args:
            member_number: Member number (QF1001)

        Returns:
            List of TradeInBatch objects
        """
        # Normalize member number
        if not member_number.upper().startswith('QF'):
            member_number = f'QF{member_number}'

        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            member_number=member_number.upper()
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
