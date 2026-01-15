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


    # ==================== POINTS EXPIRATION ====================

    def process_points_expiration(self, tenant_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Process points expiration for a tenant.

        Finds all earn transactions with expires_at <= now and remaining_points > 0,
        creates expiration transactions, and updates member balances.

        Args:
            tenant_id: The tenant to process
            dry_run: If True, calculate but don't expire points

        Returns:
            Summary of points expired
        """
        from .points_service import PointsService
        from ..models.points import PointsTransaction

        now = datetime.utcnow()

        results = {
            'processed': 0,
            'members_affected': 0,
            'total_points_expired': 0,
            'errors': [],
            'details': [],
            'dry_run': dry_run,
            'run_date': now.isoformat()
        }

        # Find all members with expired points
        expired_query = db.session.query(
            PointsTransaction.member_id,
            db.func.sum(PointsTransaction.remaining_points).label('expiring_points')
        ).join(
            Member, PointsTransaction.member_id == Member.id
        ).filter(
            Member.tenant_id == tenant_id,
            PointsTransaction.transaction_type == 'earn',
            PointsTransaction.reversed_at.is_(None),
            PointsTransaction.expires_at.isnot(None),
            PointsTransaction.expires_at <= now,
            PointsTransaction.remaining_points > 0
        ).group_by(PointsTransaction.member_id).all()

        points_service = PointsService(tenant_id)

        for member_id, expiring_points in expired_query:
            results['processed'] += 1
            results['members_affected'] += 1

            if not dry_run:
                try:
                    expired = points_service._expire_member_points(member_id, now)
                    results['total_points_expired'] += expired
                    results['details'].append({
                        'member_id': member_id,
                        'points_expired': expired,
                        'status': 'expired'
                    })
                except Exception as e:
                    results['errors'].append({
                        'member_id': member_id,
                        'error': str(e)
                    })
            else:
                results['total_points_expired'] += int(expiring_points or 0)
                results['details'].append({
                    'member_id': member_id,
                    'points_to_expire': int(expiring_points or 0),
                    'status': 'would_expire'
                })

        if not dry_run:
            self._log_scheduled_task('points_expiration', tenant_id, results)

        return results

    def send_points_expiry_warnings(self, tenant_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Send warning emails to members with points expiring soon.

        Warning intervals are configurable in tenant.settings.points.warning_days
        Default: [30, 7, 1] - warnings at 30, 7, and 1 day(s) before expiry

        Args:
            tenant_id: The tenant to process
            dry_run: If True, calculate but don't send emails

        Returns:
            Summary of warnings sent
        """
        from .points_service import PointsService
        from ..models.points import PointsTransaction
        from .notification_service import NotificationService

        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return {'success': False, 'error': 'Tenant not found'}

        settings = tenant.settings or {}
        points_settings = settings.get('points', {})

        # Get warning intervals (default: 30, 7, 1 days)
        warning_days = points_settings.get('warning_days', [30, 7, 1])
        if not isinstance(warning_days, list):
            warning_days = [30, 7, 1]

        now = datetime.utcnow()

        results = {
            'warnings_sent': 0,
            'members_notified': 0,
            'errors': [],
            'details': [],
            'dry_run': dry_run,
            'run_date': now.isoformat()
        }

        notification_service = NotificationService(tenant_id)

        for days in warning_days:
            # Find points expiring in exactly N days (±12 hours to catch daily runs)
            window_start = now + timedelta(days=days-0.5)
            window_end = now + timedelta(days=days+0.5)

            expiring_query = db.session.query(
                PointsTransaction.member_id,
                db.func.sum(PointsTransaction.remaining_points).label('expiring_points'),
                db.func.min(PointsTransaction.expires_at).label('earliest_expiry')
            ).join(
                Member, PointsTransaction.member_id == Member.id
            ).filter(
                Member.tenant_id == tenant_id,
                PointsTransaction.transaction_type == 'earn',
                PointsTransaction.reversed_at.is_(None),
                PointsTransaction.expires_at.isnot(None),
                PointsTransaction.expires_at >= window_start,
                PointsTransaction.expires_at <= window_end,
                PointsTransaction.remaining_points > 0
            ).group_by(PointsTransaction.member_id).all()

            for member_id, expiring_points, earliest_expiry in expiring_query:
                member = Member.query.get(member_id)
                if not member or not member.email:
                    continue

                # Check if we already sent this warning (check dismissed_warnings in settings)
                member_settings = settings.get('member_warnings', {}).get(str(member_id), {})
                warning_key = f'points_expiry_{days}d_{earliest_expiry.strftime("%Y-%m")}'
                if member_settings.get(warning_key):
                    continue  # Already sent

                if not dry_run:
                    try:
                        # Send notification
                        notification_service.send_notification(
                            member_id=member_id,
                            notification_type='points_expiring',
                            context={
                                'expiring_points': int(expiring_points),
                                'days_until_expiry': days,
                                'expiry_date': earliest_expiry.isoformat(),
                                'member_name': member.name or member.email.split('@')[0],
                                'current_balance': member.points_balance or 0
                            }
                        )

                        results['warnings_sent'] += 1
                        results['members_notified'] += 1
                        results['details'].append({
                            'member_id': member_id,
                            'email': member.email,
                            'expiring_points': int(expiring_points),
                            'days_until_expiry': days,
                            'status': 'sent'
                        })
                    except Exception as e:
                        results['errors'].append({
                            'member_id': member_id,
                            'error': str(e)
                        })
                else:
                    results['warnings_sent'] += 1
                    results['details'].append({
                        'member_id': member_id,
                        'email': member.email,
                        'expiring_points': int(expiring_points),
                        'days_until_expiry': days,
                        'status': 'would_send'
                    })

        if not dry_run:
            self._log_scheduled_task('points_expiry_warnings', tenant_id, results)

        return results

    def get_expiring_points_summary(self, tenant_id: int, days_ahead: int = 30) -> Dict[str, Any]:
        """
        Get summary of points expiring within specified days.

        Args:
            tenant_id: The tenant to query
            days_ahead: Days to look ahead (default 30)

        Returns:
            Summary with member breakdown
        """
        from ..models.points import PointsTransaction

        now = datetime.utcnow()
        future_date = now + timedelta(days=days_ahead)

        expiring_query = db.session.query(
            PointsTransaction.member_id,
            db.func.sum(PointsTransaction.remaining_points).label('expiring_points'),
            db.func.min(PointsTransaction.expires_at).label('earliest_expiry')
        ).join(
            Member, PointsTransaction.member_id == Member.id
        ).filter(
            Member.tenant_id == tenant_id,
            PointsTransaction.transaction_type == 'earn',
            PointsTransaction.reversed_at.is_(None),
            PointsTransaction.expires_at.isnot(None),
            PointsTransaction.expires_at > now,
            PointsTransaction.expires_at <= future_date,
            PointsTransaction.remaining_points > 0
        ).group_by(PointsTransaction.member_id).all()

        members_list = []
        total_expiring = 0

        for member_id, expiring_points, earliest_expiry in expiring_query:
            member = Member.query.get(member_id)
            if not member:
                continue

            points = int(expiring_points or 0)
            total_expiring += points

            members_list.append({
                'member_id': member_id,
                'member_number': member.member_number,
                'email': member.email,
                'name': member.name,
                'expiring_points': points,
                'earliest_expiry': earliest_expiry.isoformat() if earliest_expiry else None,
                'current_balance': member.points_balance or 0
            })

        # Sort by earliest expiry
        members_list.sort(key=lambda x: x['earliest_expiry'] or '')

        return {
            'days_ahead': days_ahead,
            'total_expiring_points': total_expiring,
            'members_with_expiring_points': len(members_list),
            'members': members_list
        }


# Singleton instance
scheduled_tasks_service = ScheduledTasksService()
