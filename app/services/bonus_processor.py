"""
Bonus processor service.
Handles issuing bonuses as store credit.
"""
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..extensions import db
from ..models import TradeInItem, Member, BonusTransaction
from .bonus_calculator import BonusCalculator


class BonusProcessor:
    """
    Processor for issuing Quick Flip bonuses.
    Calculates eligible bonuses and issues store credit.
    """

    def __init__(self, tenant_id: int, shopify_client=None):
        self.tenant_id = tenant_id
        self.calculator = BonusCalculator()
        self.shopify_client = shopify_client

    def process_pending_bonuses(
        self,
        dry_run: bool = False,
        created_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Process all pending bonus-eligible items.

        Args:
            dry_run: If True, calculate but don't issue bonuses
            created_by: Who initiated the processing

        Returns:
            Dict with processing results
        """
        # Find eligible items that haven't been processed
        pending_items = (
            TradeInItem.query
            .join(TradeInItem.batch)
            .join(Member)
            .filter(
                Member.tenant_id == self.tenant_id,
                TradeInItem.eligible_for_bonus == True,
                TradeInItem.bonus_status == 'pending'
            )
            .all()
        )

        results = {
            'processed': 0,
            'issued': 0,
            'skipped': 0,
            'errors': 0,
            'total_bonus_amount': Decimal('0'),
            'dry_run': dry_run,
            'items': []
        }

        for item in pending_items:
            item_result = self._process_item(item, dry_run, created_by)
            results['items'].append(item_result)
            results['processed'] += 1

            if item_result['status'] == 'issued':
                results['issued'] += 1
                results['total_bonus_amount'] += Decimal(str(item_result['bonus_amount']))
            elif item_result['status'] == 'skipped':
                results['skipped'] += 1
            elif item_result['status'] == 'error':
                results['errors'] += 1

        results['total_bonus_amount'] = float(results['total_bonus_amount'])

        return results

    def _process_item(
        self,
        item: TradeInItem,
        dry_run: bool,
        created_by: str
    ) -> Dict[str, Any]:
        """Process a single item for bonus."""
        result = {
            'item_id': item.id,
            'product_title': item.product_title,
            'status': 'pending',
            'bonus_amount': 0,
            'message': ''
        }

        try:
            # Calculate bonus
            calc_result = self.calculator.calculate_bonus(item)

            if not calc_result['eligible']:
                result['status'] = 'skipped'
                result['message'] = calc_result['reason']
                if not dry_run:
                    item.bonus_status = 'not_applicable'
                    db.session.commit()
                return result

            bonus_amount = Decimal(str(calc_result['bonus_amount']))
            result['bonus_amount'] = float(bonus_amount)
            result['calculation'] = calc_result['calculation']

            if dry_run:
                result['status'] = 'would_issue'
                result['message'] = f'Would issue ${bonus_amount} bonus'
                return result

            # Issue the bonus
            member = item.batch.member

            # Create bonus transaction record
            transaction = BonusTransaction(
                member_id=member.id,
                trade_in_item_id=item.id,
                bonus_amount=bonus_amount,
                transaction_type='credit',
                reason=calc_result['reason'],
                sale_price=item.sold_price,
                trade_value=item.trade_value,
                profit=item.sold_price - item.trade_value,
                bonus_rate=member.tier.bonus_rate,
                days_to_sell=item.days_to_sell,
                created_by=created_by
            )

            # Issue store credit via Shopify (if client available)
            if self.shopify_client and member.shopify_customer_id:
                try:
                    credit_result = self.shopify_client.add_store_credit(
                        customer_id=member.shopify_customer_id,
                        amount=float(bonus_amount),
                        note=f'Quick Flip Bonus - {item.product_title}'
                    )
                    transaction.store_credit_txn_id = credit_result.get('transaction_id')
                except Exception as e:
                    result['status'] = 'error'
                    result['message'] = f'Shopify error: {str(e)}'
                    return result

            # Update item status
            item.bonus_amount = bonus_amount
            item.bonus_status = 'issued'

            # Update member totals
            member.total_bonus_earned = (member.total_bonus_earned or Decimal('0')) + bonus_amount

            db.session.add(transaction)
            db.session.commit()

            result['status'] = 'issued'
            result['message'] = f'Issued ${bonus_amount} bonus'
            result['transaction_id'] = transaction.id

        except Exception as e:
            result['status'] = 'error'
            result['message'] = str(e)
            db.session.rollback()

        return result

    def process_single_item(
        self,
        item_id: int,
        created_by: str = 'system'
    ) -> Dict[str, Any]:
        """Process a single item for bonus."""
        item = TradeInItem.query.get(item_id)
        if not item:
            return {'status': 'error', 'message': 'Item not found'}

        return self._process_item(item, dry_run=False, created_by=created_by)

    def reverse_bonus(
        self,
        transaction_id: int,
        reason: str,
        created_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Reverse a bonus (e.g., for refunded orders).

        Args:
            transaction_id: Original bonus transaction ID
            reason: Reason for reversal
            created_by: Who initiated the reversal

        Returns:
            Dict with reversal result
        """
        original = BonusTransaction.query.get(transaction_id)
        if not original:
            return {'status': 'error', 'message': 'Transaction not found'}

        # Create reversal transaction
        reversal = BonusTransaction(
            member_id=original.member_id,
            trade_in_item_id=original.trade_in_item_id,
            bonus_amount=-original.bonus_amount,
            transaction_type='reversal',
            reason=reason,
            notes=f'Reversal of transaction #{transaction_id}',
            created_by=created_by
        )

        # Update member totals
        member = original.member
        member.total_bonus_earned = (member.total_bonus_earned or Decimal('0')) - original.bonus_amount

        # Update item status
        if original.trade_in_item:
            original.trade_in_item.bonus_status = 'reversed'

        # TODO: Reverse Shopify store credit if applicable

        db.session.add(reversal)
        db.session.commit()

        return {
            'status': 'reversed',
            'original_transaction_id': transaction_id,
            'reversal_transaction_id': reversal.id,
            'amount_reversed': float(original.bonus_amount)
        }
