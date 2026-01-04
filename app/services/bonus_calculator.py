"""
Bonus calculation service.
Core Quick Flip bonus logic.
"""
from decimal import Decimal
from typing import Optional, Dict, Any
from ..models import TradeInItem, Member


class BonusCalculator:
    """
    Calculator for Quick Flip bonuses.

    Bonus = (Sale Price - Trade Value) × Tier Bonus Rate

    Only applies if:
    - Item sold within quick_flip_days of listing
    - Member has an active tier
    - Sale price > trade value (there's profit)
    """

    def calculate_bonus(self, item: TradeInItem) -> Dict[str, Any]:
        """
        Calculate potential bonus for a trade-in item.

        Args:
            item: TradeInItem to calculate bonus for

        Returns:
            Dict with bonus calculation details:
            {
                'eligible': bool,
                'reason': str,
                'bonus_amount': Decimal or None,
                'calculation': {
                    'sale_price': Decimal,
                    'trade_value': Decimal,
                    'profit': Decimal,
                    'bonus_rate': Decimal,
                    'days_to_sell': int,
                    'quick_flip_days': int
                }
            }
        """
        result = {
            'eligible': False,
            'reason': '',
            'bonus_amount': None,
            'calculation': {}
        }

        # Check if item has been sold
        if not item.sold_date or not item.sold_price:
            result['reason'] = 'Item has not been sold yet'
            return result

        # Check if item was listed
        if not item.listed_date:
            result['reason'] = 'Item was never listed'
            return result

        # Get member and tier
        batch = item.batch
        if not batch:
            result['reason'] = 'Item not associated with a batch'
            return result

        member = batch.member
        if not member:
            result['reason'] = 'Batch not associated with a member'
            return result

        if not member.tier:
            result['reason'] = 'Member does not have an active tier'
            return result

        tier = member.tier

        # Calculate days to sell
        days_to_sell = item.days_to_sell
        if days_to_sell is None:
            days_to_sell = (item.sold_date - item.listed_date).days
            item.days_to_sell = days_to_sell

        # Check if within quick flip window
        if days_to_sell > tier.quick_flip_days:
            result['reason'] = f'Sold in {days_to_sell} days, exceeds {tier.quick_flip_days} day window'
            result['calculation'] = {
                'days_to_sell': days_to_sell,
                'quick_flip_days': tier.quick_flip_days
            }
            return result

        # Calculate profit
        profit = item.sold_price - item.trade_value
        if profit <= 0:
            result['reason'] = 'No profit on sale'
            result['calculation'] = {
                'sale_price': float(item.sold_price),
                'trade_value': float(item.trade_value),
                'profit': float(profit)
            }
            return result

        # Calculate bonus
        bonus_amount = profit * tier.bonus_rate
        bonus_amount = Decimal(str(round(bonus_amount, 2)))

        result['eligible'] = True
        result['reason'] = f'Quick Flip bonus - sold in {days_to_sell} days'
        result['bonus_amount'] = float(bonus_amount)
        result['calculation'] = {
            'sale_price': float(item.sold_price),
            'trade_value': float(item.trade_value),
            'profit': float(profit),
            'bonus_rate': float(tier.bonus_rate),
            'days_to_sell': days_to_sell,
            'quick_flip_days': tier.quick_flip_days,
            'tier_name': tier.name
        }

        return result

    def calculate_batch_bonus(self, batch) -> Dict[str, Any]:
        """
        Calculate total bonus for all items in a batch.

        Args:
            batch: TradeInBatch to calculate bonuses for

        Returns:
            Dict with batch bonus summary
        """
        results = []
        total_bonus = Decimal('0')
        eligible_count = 0

        for item in batch.items:
            item_result = self.calculate_bonus(item)
            results.append({
                'item_id': item.id,
                'product_title': item.product_title,
                **item_result
            })

            if item_result['eligible']:
                total_bonus += Decimal(str(item_result['bonus_amount']))
                eligible_count += 1

        return {
            'batch_id': batch.id,
            'batch_reference': batch.batch_reference,
            'total_items': len(results),
            'eligible_items': eligible_count,
            'total_bonus': float(total_bonus),
            'items': results
        }

    def estimate_bonus(
        self,
        trade_value: Decimal,
        expected_sale_price: Decimal,
        bonus_rate: Decimal
    ) -> Dict[str, Any]:
        """
        Estimate potential bonus for a trade-in (before sale).

        Args:
            trade_value: What shop paid for item
            expected_sale_price: Expected sale price
            bonus_rate: Member's tier bonus rate

        Returns:
            Dict with bonus estimate
        """
        expected_profit = expected_sale_price - trade_value

        if expected_profit <= 0:
            return {
                'potential_bonus': 0,
                'note': 'No bonus if sold at or below trade value'
            }

        potential_bonus = expected_profit * bonus_rate

        return {
            'trade_value': float(trade_value),
            'expected_sale_price': float(expected_sale_price),
            'expected_profit': float(expected_profit),
            'bonus_rate': float(bonus_rate),
            'potential_bonus': float(round(potential_bonus, 2)),
            'note': f'If sold within quick flip window at ${expected_sale_price}'
        }
