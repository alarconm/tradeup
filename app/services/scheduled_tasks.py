"""
Scheduled Tasks Service for TradeUp.

Handles automated background jobs:
- Monthly credit distribution to members with tier benefits
- Credit expiration cleanup
- Usage statistics calculation
- Notification triggers

These tasks can be triggered by:
1. Flask CLI commands (for cron jobs)
2. Shopify Flow triggers
3. Manual admin actions
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import and_, or_
from ..extensions import db
from ..models.member import Member, MembershipTier
from ..models.promotions import StoreCreditLedger, CreditEventType, MemberCreditBalance
from ..models.tenant import Tenant
from .store_credit_service import StoreCreditService


class ScheduledTasksService:
    """
    Service for running scheduled/background tasks.
    """

    def __init__(self):
        self.store_credit_service = StoreCreditService()

    # ==================== MONTHLY CREDIT DISTRIBUTION ====================

    def distribute_monthly_credits(self, tenant_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Distribute monthly credits to all eligible members.

        Eligibility:
        - Member status is 'active'
        - Member has a tier with monthly_credit_amount > 0
        - Member hasn't received monthly credit this month yet

        Args:
            tenant_id: The tenant to process
            dry_run: If True, calculate but don't issue credits

        Returns:
            Summary of credits distributed
        """
        now = datetime.utcnow()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Find all active members with tiers that have monthly credits
        eligible_members = db.session.query(Member).join(
            MembershipTier, Member.tier_id == MembershipTier.id
        ).filter(
            Member.tenant_id == tenant_id,
            Member.status == 'active',
            MembershipTier.monthly_credit_amount > 0,
            MembershipTier.is_active == True
        ).all()

        results = {
            'processed': 0,
            'credited': 0,
            'skipped': 0,
            'total_amount': Decimal('0'),
            'errors': [],
            'details': [],
            'dry_run': dry_run,
            'run_date': now.isoformat()
        }

        for member in eligible_members:
            results['processed'] += 1

            # Check if member already received monthly credit this month
            existing_credit = StoreCreditLedger.query.filter(
                StoreCreditLedger.member_id == member.id,
                StoreCreditLedger.event_type == 'monthly_credit',
                StoreCreditLedger.created_at >= current_month_start
            ).first()

            if existing_credit:
                results['skipped'] += 1
                results['details'].append({
                    'member_id': member.id,
                    'member_number': member.member_number,
                    'status': 'skipped',
                    'reason': 'Already received monthly credit this month'
                })
                continue

            credit_amount = member.tier.monthly_credit_amount

            if not dry_run:
                try:
                    # Calculate expiration if tier has expiration setting
                    expires_at = None
                    if member.tier.credit_expiration_days:
                        expires_at = now + timedelta(days=member.tier.credit_expiration_days)

                    # Issue the credit
                    self.store_credit_service.add_credit(
                        member_id=member.id,
                        amount=credit_amount,
                        event_type='monthly_credit',
                        description=f'Monthly {member.tier.name} tier credit - {now.strftime("%B %Y")}',
                        source_type='monthly_credit',
                        source_id=f'monthly-{now.strftime("%Y-%m")}',
                        created_by='system:scheduler',
                        expires_at=expires_at
                    )

                    results['credited'] += 1
                    results['total_amount'] += Decimal(str(credit_amount))
                    results['details'].append({
                        'member_id': member.id,
                        'member_number': member.member_number,
                        'tier': member.tier.name,
                        'amount': float(credit_amount),
                        'status': 'credited',
                        'expires_at': expires_at.isoformat() if expires_at else None
                    })

                except Exception as e:
                    results['errors'].append({
                        'member_id': member.id,
                        'error': str(e)
                    })
            else:
                # Dry run - just count
                results['credited'] += 1
                results['total_amount'] += Decimal(str(credit_amount))
                results['details'].append({
                    'member_id': member.id,
                    'member_number': member.member_number,
                    'tier': member.tier.name,
                    'amount': float(credit_amount),
                    'status': 'would_credit'
                })

        results['total_amount'] = float(results['total_amount'])

        # Log the operation
        if not dry_run:
            self._log_scheduled_task('monthly_credit_distribution', tenant_id, results)

        return results

    def get_monthly_credit_preview(self, tenant_id: int) -> Dict[str, Any]:
        """
        Preview what would happen if monthly credits were distributed now.
        """
        return self.distribute_monthly_credits(tenant_id, dry_run=True)

    # ==================== CREDIT EXPIRATION ====================

    def expire_old_credits(self, tenant_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Expire credits that have passed their expiration date.

        This creates negative ledger entries to zero out expired credits
        and updates the member's balance accordingly.

        Args:
            tenant_id: The tenant to process
            dry_run: If True, calculate but don't expire credits

        Returns:
            Summary of credits expired
        """
        now = datetime.utcnow()

        # Find all unexpired credits with expiration dates in the past
        # that haven't been marked as expired yet
        expired_credits = db.session.query(StoreCreditLedger).join(
            Member, StoreCreditLedger.member_id == Member.id
        ).filter(
            Member.tenant_id == tenant_id,
            StoreCreditLedger.expires_at.isnot(None),
            StoreCreditLedger.expires_at < now,
            StoreCreditLedger.amount > 0,  # Only positive (credit) entries
            StoreCreditLedger.event_type != 'expiration'  # Not already an expiration entry
        ).all()

        # Group by member to process expirations
        member_expirations: Dict[int, List[StoreCreditLedger]] = {}
        for credit in expired_credits:
            if credit.member_id not in member_expirations:
                member_expirations[credit.member_id] = []
            member_expirations[credit.member_id].append(credit)

        results = {
            'processed': 0,
            'expired_entries': 0,
            'members_affected': 0,
            'total_expired': Decimal('0'),
            'errors': [],
            'details': [],
            'dry_run': dry_run,
            'run_date': now.isoformat()
        }

        for member_id, credits in member_expirations.items():
            member = Member.query.get(member_id)
            if not member:
                continue

            results['members_affected'] += 1
            member_total = Decimal('0')

            for credit in credits:
                results['processed'] += 1

                # Check if this specific credit was already expired
                already_expired = StoreCreditLedger.query.filter(
                    StoreCreditLedger.member_id == member_id,
                    StoreCreditLedger.event_type == 'expiration',
                    StoreCreditLedger.source_id == f'expired:{credit.id}'
                ).first()

                if already_expired:
                    continue

                if not dry_run:
                    try:
                        # Create expiration entry (negative amount)
                        expiration_entry = StoreCreditLedger(
                            member_id=member_id,
                            event_type='expiration',
                            amount=-credit.amount,
                            balance_after=Decimal('0'),  # Will be recalculated
                            description=f'Credit expired (issued {credit.created_at.strftime("%Y-%m-%d")})',
                            source_type='expiration',
                            source_id=f'expired:{credit.id}',
                            source_reference=credit.source_reference,
                            created_by='system:scheduler'
                        )
                        db.session.add(expiration_entry)

                        member_total += credit.amount
                        results['expired_entries'] += 1

                    except Exception as e:
                        results['errors'].append({
                            'credit_id': credit.id,
                            'member_id': member_id,
                            'error': str(e)
                        })
                else:
                    member_total += credit.amount
                    results['expired_entries'] += 1

            results['total_expired'] += member_total
            results['details'].append({
                'member_id': member_id,
                'member_number': member.member_number,
                'expired_amount': float(member_total),
                'entries_expired': len([c for c in credits])
            })

        if not dry_run and results['expired_entries'] > 0:
            db.session.commit()

            # Recalculate balances for affected members
            for member_id in member_expirations.keys():
                self._recalculate_member_balance(member_id)

        results['total_expired'] = float(results['total_expired'])

        if not dry_run:
            self._log_scheduled_task('credit_expiration', tenant_id, results)

        return results

    def get_expiring_credits_preview(self, tenant_id: int, days_ahead: int = 7) -> Dict[str, Any]:
        """
        Preview credits that will expire within the specified number of days.
        Useful for sending warning notifications.
        """
        now = datetime.utcnow()
        future_date = now + timedelta(days=days_ahead)

        expiring = db.session.query(StoreCreditLedger).join(
            Member, StoreCreditLedger.member_id == Member.id
        ).filter(
            Member.tenant_id == tenant_id,
            StoreCreditLedger.expires_at.isnot(None),
            StoreCreditLedger.expires_at > now,
            StoreCreditLedger.expires_at <= future_date,
            StoreCreditLedger.amount > 0,
            StoreCreditLedger.event_type != 'expiration'
        ).all()

        # Group by member
        by_member: Dict[int, Dict] = {}
        for credit in expiring:
            if credit.member_id not in by_member:
                member = Member.query.get(credit.member_id)
                by_member[credit.member_id] = {
                    'member_id': credit.member_id,
                    'member_number': member.member_number if member else 'Unknown',
                    'email': member.email if member else None,
                    'total_expiring': Decimal('0'),
                    'credits': []
                }

            by_member[credit.member_id]['total_expiring'] += credit.amount
            by_member[credit.member_id]['credits'].append({
                'id': credit.id,
                'amount': float(credit.amount),
                'expires_at': credit.expires_at.isoformat(),
                'description': credit.description
            })

        # Convert to list
        members_list = []
        for member_data in by_member.values():
            member_data['total_expiring'] = float(member_data['total_expiring'])
            members_list.append(member_data)

        return {
            'days_ahead': days_ahead,
            'members_with_expiring_credits': len(members_list),
            'total_amount_expiring': sum(m['total_expiring'] for m in members_list),
            'members': members_list
        }

    # ==================== REFERRAL STATS ====================

    def calculate_referral_stats(self, tenant_id: int) -> Dict[str, Any]:
        """
        Calculate comprehensive referral program statistics.
        """
        from sqlalchemy import func

        # Total referrals
        total_referrals = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.referred_by_id.isnot(None)
        ).scalar() or 0

        # This month's referrals
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_referrals = db.session.query(func.count(Member.id)).filter(
            Member.tenant_id == tenant_id,
            Member.referred_by_id.isnot(None),
            Member.created_at >= month_start
        ).scalar() or 0

        # Total referral credits issued
        total_credit = db.session.query(func.sum(StoreCreditLedger.amount)).join(
            Member, StoreCreditLedger.member_id == Member.id
        ).filter(
            Member.tenant_id == tenant_id,
            StoreCreditLedger.event_type == 'referral'
        ).scalar() or Decimal('0')

        # Top referrers
        top_referrers = db.session.query(
            Member.id,
            Member.member_number,
            Member.name,
            Member.email,
            Member.referral_code,
            Member.referral_count,
            Member.referral_earnings
        ).filter(
            Member.tenant_id == tenant_id,
            Member.referral_count > 0
        ).order_by(Member.referral_count.desc()).limit(10).all()

        # Recent referrals
        recent = db.session.query(Member).filter(
            Member.tenant_id == tenant_id,
            Member.referred_by_id.isnot(None)
        ).order_by(Member.created_at.desc()).limit(10).all()

        return {
            'total_referrals': total_referrals,
            'monthly_referrals': monthly_referrals,
            'total_credit_issued': float(total_credit),
            'top_referrers': [{
                'id': r.id,
                'member_number': r.member_number,
                'name': r.name,
                'email': r.email,
                'referral_code': r.referral_code,
                'referral_count': r.referral_count or 0,
                'referral_earnings': float(r.referral_earnings or 0)
            } for r in top_referrers],
            'recent_referrals': [{
                'id': m.id,
                'member_number': m.member_number,
                'name': m.name,
                'referred_by': m.referred_by.member_number if m.referred_by else None,
                'created_at': m.created_at.isoformat()
            } for m in recent]
        }

    # ==================== HELPER METHODS ====================

    def _recalculate_member_balance(self, member_id: int):
        """Recalculate a member's credit balance from ledger entries."""
        from sqlalchemy import func

        # Sum all ledger entries
        total = db.session.query(func.sum(StoreCreditLedger.amount)).filter(
            StoreCreditLedger.member_id == member_id
        ).scalar() or Decimal('0')

        # Update or create balance record
        balance = MemberCreditBalance.query.filter_by(member_id=member_id).first()
        if not balance:
            balance = MemberCreditBalance(member_id=member_id)
            db.session.add(balance)

        balance.total_balance = total
        balance.available_balance = total
        balance.updated_at = datetime.utcnow()

        db.session.commit()

    def _log_scheduled_task(self, task_name: str, tenant_id: int, results: Dict):
        """Log a scheduled task execution for audit purposes."""
        # Could store in a ScheduledTaskLog model
        # For now, just print
        print(f"[ScheduledTask] {task_name} for tenant {tenant_id}: "
              f"processed={results.get('processed', 0)}, "
              f"errors={len(results.get('errors', []))}")


# Singleton instance
scheduled_tasks_service = ScheduledTasksService()
