"""
Birthday Rewards Service

Handles birthday tracking and automatic reward issuance.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from app import db
from app.models.member import Member
from app.models.promotions import StoreCreditLedger, CreditEventType


class BirthdayService:
    """Service for managing birthday rewards."""

    def __init__(self, tenant_id: int, settings: Optional[Dict] = None):
        self.tenant_id = tenant_id
        self.settings = settings or {}

    def get_birthday_settings(self) -> Dict[str, Any]:
        """Get birthday reward settings for the tenant."""
        birthday_settings = self.settings.get('birthday', {})
        return {
            'enabled': birthday_settings.get('enabled', False),
            'reward_type': birthday_settings.get('reward_type', 'credit'),  # credit or points
            'reward_amount': birthday_settings.get('reward_amount', 10),  # Default $10 or 100 points
            'send_email': birthday_settings.get('send_email', True),
            'email_days_before': birthday_settings.get('email_days_before', 0),  # 0 = on birthday
            'message': birthday_settings.get('message', 'Happy Birthday! Enjoy your special reward!'),
        }

    def set_member_birthday(self, member_id: int, month: int, day: int) -> Optional[Member]:
        """
        Set a member's birthday.
        Stores as date with year 2000 to normalize month/day.
        """
        member = Member.query.filter_by(
            id=member_id,
            tenant_id=self.tenant_id
        ).first()

        if not member:
            return None

        # Validate month/day
        if not (1 <= month <= 12 and 1 <= day <= 31):
            raise ValueError("Invalid month or day")

        # Handle February edge cases
        if month == 2 and day > 29:
            raise ValueError("Invalid day for February")

        # Store with year 2000 for consistency
        try:
            member.birthday = date(2000, month, day)
            db.session.commit()
            return member
        except ValueError as e:
            raise ValueError(f"Invalid date: {e}")

    def get_members_with_birthday_today(self) -> List[Member]:
        """Get all members whose birthday is today."""
        today = date.today()
        # Look for members with birthday matching today's month/day
        birthday_date = date(2000, today.month, today.day)

        members = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.birthday == birthday_date,
            Member.status == 'active'
        ).all()

        return members

    def get_members_with_upcoming_birthdays(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get members with birthdays in the next N days."""
        today = date.today()
        upcoming = []

        for member in Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.birthday.isnot(None),
            Member.status == 'active'
        ).all():
            if member.birthday:
                # Calculate days until birthday
                this_year_birthday = date(today.year, member.birthday.month, member.birthday.day)
                if this_year_birthday < today:
                    this_year_birthday = date(today.year + 1, member.birthday.month, member.birthday.day)

                days_until = (this_year_birthday - today).days
                if 0 <= days_until <= days_ahead:
                    upcoming.append({
                        'member': member.to_dict(),
                        'birthday': member.birthday.strftime('%m-%d'),
                        'days_until': days_until,
                        'already_rewarded': member.last_birthday_reward_year == today.year,
                    })

        # Sort by days until birthday
        upcoming.sort(key=lambda x: x['days_until'])
        return upcoming

    def issue_birthday_reward(self, member: Member) -> Dict[str, Any]:
        """
        Issue birthday reward to a member.
        Returns info about the reward issued.
        """
        settings = self.get_birthday_settings()

        if not settings['enabled']:
            return {'success': False, 'error': 'Birthday rewards not enabled'}

        # Check if already rewarded this year
        current_year = date.today().year
        if member.last_birthday_reward_year == current_year:
            return {'success': False, 'error': 'Already rewarded this year'}

        reward_type = settings['reward_type']
        reward_amount = settings['reward_amount']

        result = {
            'success': True,
            'member_id': member.id,
            'member_name': member.name,
            'reward_type': reward_type,
            'reward_amount': reward_amount,
        }

        if reward_type == 'credit':
            # Issue store credit
            ledger_entry = StoreCreditLedger(
                tenant_id=self.tenant_id,
                member_id=member.id,
                amount=Decimal(str(reward_amount)),
                event_type=CreditEventType.BIRTHDAY_REWARD,
                description=f"Birthday reward - {settings['message']}",
                reference_type='birthday',
                reference_id=str(current_year),
            )
            db.session.add(ledger_entry)
            result['credit_issued'] = reward_amount

        elif reward_type == 'points':
            # Issue points
            member.points_balance = (member.points_balance or 0) + reward_amount
            member.lifetime_points_earned = (member.lifetime_points_earned or 0) + reward_amount
            result['points_issued'] = reward_amount

        # Mark as rewarded this year
        member.last_birthday_reward_year = current_year
        db.session.commit()

        return result

    def process_birthday_rewards(self) -> Dict[str, Any]:
        """
        Process birthday rewards for all members with birthdays today.
        Called by scheduled task daily.
        """
        settings = self.get_birthday_settings()

        if not settings['enabled']:
            return {'success': False, 'error': 'Birthday rewards not enabled', 'processed': 0}

        birthday_members = self.get_members_with_birthday_today()
        results = []

        for member in birthday_members:
            result = self.issue_birthday_reward(member)
            results.append(result)

        successful = [r for r in results if r.get('success')]
        failed = [r for r in results if not r.get('success')]

        return {
            'success': True,
            'processed': len(results),
            'successful': len(successful),
            'failed': len(failed),
            'details': results,
        }

    def get_birthday_stats(self) -> Dict[str, Any]:
        """Get birthday reward statistics."""
        today = date.today()
        current_year = today.year

        # Count members with birthdays set
        members_with_birthdays = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.birthday.isnot(None),
            Member.status == 'active'
        ).count()

        # Count members rewarded this year
        rewarded_this_year = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.last_birthday_reward_year == current_year,
            Member.status == 'active'
        ).count()

        # Get upcoming birthdays (next 7 days)
        upcoming = self.get_members_with_upcoming_birthdays(days_ahead=7)

        return {
            'members_with_birthdays': members_with_birthdays,
            'rewarded_this_year': rewarded_this_year,
            'upcoming_7_days': len(upcoming),
            'upcoming_birthdays': upcoming[:5],  # Top 5 upcoming
        }
