"""
Notification Service for TradeUp.

Handles email notifications via SendGrid for:
- Welcome emails on member enrollment
- Trade-in status updates (created, completed)
- Tier changes (upgrades/downgrades)
- Store credit issued (non-trade-in credits only)
- Custom notifications

IMPORTANT: Notification Strategy
--------------------------------
TradeUp sends its own notifications instead of using Shopify's native emails because:
1. TradeUp emails are more detailed (include tier info, bonus breakdown, etc.)
2. Consistent branding and messaging across all notification types
3. Tenant-configurable from/reply-to addresses

For trade-in completions, the `trade_in_completed` email includes store credit details,
so we disable Shopify's native "store credit issued" notification to avoid duplicates.

Configuration:
- SENDGRID_API_KEY: SendGrid API key
- Tenant settings.notifications for per-tenant customization
"""
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from flask import current_app

# SendGrid import with fallback
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content, Personalization
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False


class NotificationService:
    """
    Service for sending email notifications to members.
    Uses SendGrid as the email provider.
    """

    # Email templates (can be overridden by tenant settings)
    DEFAULT_TEMPLATES = {
        'welcome': {
            'subject': 'Welcome to {shop_name} Rewards!',
            'text': '''Hi {member_name},

Welcome to {shop_name}'s rewards program!

Your Member Number: {member_number}
Your Tier: {tier_name}

As a member, you'll earn bonus store credit on every trade-in based on your tier level.

Current Bonus Rate: {bonus_percent}%

Thank you for joining!

{shop_name}
''',
            'html': '''
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>Welcome to {shop_name} Rewards!</h2>
    <p>Hi {member_name},</p>
    <p>Welcome to our rewards program! Here are your membership details:</p>
    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Member Number:</strong> {member_number}</p>
        <p><strong>Your Tier:</strong> {tier_name}</p>
        <p><strong>Trade-in Bonus Rate:</strong> {bonus_percent}%</p>
    </div>
    <p>As a member, you'll earn bonus store credit on every trade-in based on your tier level.</p>
    <p>Thank you for joining!</p>
    <p>{shop_name}</p>
</div>
'''
        },
        'trade_in_created': {
            'subject': 'Trade-In Received - {batch_reference}',
            'text': '''Hi {member_name},

We've received your trade-in submission.

Batch Reference: {batch_reference}
Items: {item_count}
Trade Value: ${trade_value}
Category: {category}

We'll process your items and update you when complete.

{shop_name}
''',
            'html': '''
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>Trade-In Received</h2>
    <p>Hi {member_name},</p>
    <p>We've received your trade-in submission.</p>
    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Batch Reference:</strong> {batch_reference}</p>
        <p><strong>Items:</strong> {item_count}</p>
        <p><strong>Trade Value:</strong> ${trade_value}</p>
        <p><strong>Category:</strong> {category}</p>
    </div>
    <p>We'll process your items and update you when complete.</p>
    <p>{shop_name}</p>
</div>
'''
        },
        'trade_in_completed': {
            'subject': 'Trade-In Complete - ${credit_amount} Store Credit Issued!',
            'text': '''Hi {member_name},

Great news! Your trade-in has been completed.

Batch Reference: {batch_reference}
Trade Value: ${trade_value}
Tier Bonus ({tier_name} - {bonus_percent}%): ${bonus_amount}
Total Credit Issued: ${credit_amount}

Your store credit has been added to your account and can be used on your next purchase.

Thank you for trading with us!

{shop_name}
''',
            'html': '''
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>Trade-In Complete!</h2>
    <p>Hi {member_name},</p>
    <p>Great news! Your trade-in has been completed.</p>
    <div style="background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Batch Reference:</strong> {batch_reference}</p>
        <p><strong>Trade Value:</strong> ${trade_value}</p>
        <p><strong>Tier Bonus ({tier_name} - {bonus_percent}%):</strong> ${bonus_amount}</p>
        <h3 style="color: #2e7d32;">Total Credit Issued: ${credit_amount}</h3>
    </div>
    <p>Your store credit has been added to your account and can be used on your next purchase.</p>
    <p>Thank you for trading with us!</p>
    <p>{shop_name}</p>
</div>
'''
        },
        'tier_upgrade': {
            'subject': 'Congratulations! You\'ve been upgraded to {new_tier}!',
            'text': '''Hi {member_name},

Congratulations! You've been upgraded from {old_tier} to {new_tier}!

Your new trade-in bonus rate: {bonus_percent}%

Thank you for your continued loyalty!

{shop_name}
''',
            'html': '''
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>🎉 Tier Upgrade!</h2>
    <p>Hi {member_name},</p>
    <p>Congratulations! You've been upgraded!</p>
    <div style="background: #fff3e0; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Previous Tier:</strong> {old_tier}</p>
        <p><strong>New Tier:</strong> <span style="color: #e65100; font-weight: bold;">{new_tier}</span></p>
        <p><strong>New Trade-in Bonus Rate:</strong> {bonus_percent}%</p>
    </div>
    <p>Thank you for your continued loyalty!</p>
    <p>{shop_name}</p>
</div>
'''
        },
        'credit_issued': {
            'subject': '${credit_amount} Store Credit Added to Your Account',
            'text': '''Hi {member_name},

Store credit has been added to your account!

Amount: ${credit_amount}
Reason: {reason}
New Balance: ${new_balance}

Use it on your next purchase!

{shop_name}
''',
            'html': '''
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>Store Credit Added!</h2>
    <p>Hi {member_name},</p>
    <p>Store credit has been added to your account!</p>
    <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Amount Added:</strong> <span style="color: #1565c0; font-weight: bold;">${credit_amount}</span></p>
        <p><strong>Reason:</strong> {reason}</p>
        <p><strong>New Balance:</strong> ${new_balance}</p>
    </div>
    <p>Use it on your next purchase!</p>
    <p>{shop_name}</p>
</div>
'''
        },
        'credit_expiring': {
            'subject': 'Your ${expiring_amount} Store Credit is Expiring Soon!',
            'text': '''Hi {member_name},

This is a friendly reminder that you have store credit expiring soon!

Amount Expiring: ${expiring_amount}
Expiration Date: {expiration_date}

Don't let it go to waste - use it on your next purchase!

{shop_name}
''',
            'html': '''
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>⏰ Credit Expiring Soon!</h2>
    <p>Hi {member_name},</p>
    <p>This is a friendly reminder that you have store credit expiring soon!</p>
    <div style="background: #fff8e1; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
        <p><strong>Amount Expiring:</strong> <span style="color: #e65100; font-weight: bold;">${expiring_amount}</span></p>
        <p><strong>Expiration Date:</strong> {expiration_date}</p>
    </div>
    <p>Don't let it go to waste - use it on your next purchase!</p>
    <p>{shop_name}</p>
</div>
'''
        },
        'monthly_credit': {
            'subject': 'Your Monthly ${credit_amount} Store Credit Has Arrived!',
            'text': '''Hi {member_name},

Your monthly membership credit has been added to your account!

Amount: ${credit_amount}
Tier: {tier_name}
{expiration_info}

Thank you for being a valued {tier_name} member!

{shop_name}
''',
            'html': '''
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>🎁 Monthly Credit Arrived!</h2>
    <p>Hi {member_name},</p>
    <p>Your monthly membership credit has been added to your account!</p>
    <div style="background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Amount:</strong> <span style="color: #2e7d32; font-weight: bold;">${credit_amount}</span></p>
        <p><strong>Tier:</strong> {tier_name}</p>
        {expiration_html}
    </div>
    <p>Thank you for being a valued {tier_name} member!</p>
    <p>{shop_name}</p>
</div>
'''
        },
        'referral_success': {
            'subject': 'You Earned ${reward_amount} for Your Referral!',
            'text': '''Hi {member_name},

Congratulations! {referred_name} signed up using your referral code.

Your Reward: ${reward_amount}
Their Reward: ${referred_reward}

Keep sharing your referral code to earn more rewards!
Your Code: {referral_code}

{shop_name}
''',
            'html': '''
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>🎉 Referral Reward!</h2>
    <p>Hi {member_name},</p>
    <p>Congratulations! <strong>{referred_name}</strong> signed up using your referral code.</p>
    <div style="background: #f3e5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Your Reward:</strong> <span style="color: #7b1fa2; font-weight: bold;">${reward_amount}</span></p>
        <p><strong>Their Reward:</strong> ${referred_reward}</p>
    </div>
    <p>Keep sharing your referral code to earn more rewards!</p>
    <p style="background: #f5f5f5; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 18px; text-align: center;">{referral_code}</p>
    <p>{shop_name}</p>
</div>
'''
        }
    }

    def __init__(self):
        self.api_key = os.getenv('SENDGRID_API_KEY')
        self.default_from_email = os.getenv('SENDGRID_FROM_EMAIL', 'noreply@tradeup.app')
        self.default_from_name = os.getenv('SENDGRID_FROM_NAME', 'TradeUp')

    def _get_client(self) -> Optional['SendGridAPIClient']:
        """Get SendGrid client if available."""
        if not SENDGRID_AVAILABLE:
            current_app.logger.warning("SendGrid not installed. Run: pip install sendgrid")
            return None

        if not self.api_key:
            current_app.logger.warning("SENDGRID_API_KEY not configured")
            return None

        return SendGridAPIClient(api_key=self.api_key)

    def _get_tenant_settings(self, tenant_id: int) -> Dict[str, Any]:
        """Get notification settings for a tenant with granular controls."""
        from ..models import Tenant
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return {}

        settings = tenant.settings or {}
        notifications = settings.get('notifications', {})

        # Get legacy toggles (for backward compatibility)
        trade_in_updates = notifications.get('trade_in_updates', True)
        tier_change = notifications.get('tier_change', True)
        credit_issued = notifications.get('credit_issued', True)

        return {
            'enabled': notifications.get('enabled', True),

            # Member notifications
            'welcome_email': notifications.get('welcome_email', True),

            # Trade-in notifications - use granular setting if set, else fall back to legacy toggle
            'trade_in_updates': trade_in_updates,  # Legacy toggle
            'trade_in_created': notifications.get('trade_in_created', trade_in_updates),
            'trade_in_approved': notifications.get('trade_in_approved', trade_in_updates),
            'trade_in_rejected': notifications.get('trade_in_rejected', trade_in_updates),

            # Tier notifications - use granular setting if set, else fall back to legacy toggle
            'tier_change': tier_change,  # Legacy toggle
            'tier_upgrade': notifications.get('tier_upgrade', tier_change),
            'tier_downgrade': notifications.get('tier_downgrade', tier_change),
            'tier_expiring': notifications.get('tier_expiring', tier_change),

            # Credit notifications - use granular setting if set, else fall back to legacy toggle
            'credit_issued': credit_issued,  # Legacy toggle
            'credit_added': notifications.get('credit_added', credit_issued),
            'credit_expiring': notifications.get('credit_expiring', credit_issued),
            'monthly_credit': notifications.get('monthly_credit', credit_issued),

            # Referral notifications
            'referral_success': notifications.get('referral_success', True),

            # Daily digest
            'daily_digest': notifications.get('daily_digest', False),

            # Sender configuration
            'from_name': notifications.get('from_name') or tenant.shop_name or self.default_from_name,
            'from_email': notifications.get('from_email') or self.default_from_email,
            'reply_to': notifications.get('reply_to'),
            'shop_name': tenant.shop_name
        }

    def _render_template(
        self,
        template_key: str,
        variables: Dict[str, Any],
        tenant_settings: Dict[str, Any]
    ) -> Dict[str, str]:
        """Render an email template with variables."""
        template = self.DEFAULT_TEMPLATES.get(template_key, {})

        # Add shop name to variables
        variables['shop_name'] = tenant_settings.get('shop_name', 'TradeUp')

        # Render subject, text, and html
        subject = template.get('subject', 'Notification').format(**variables)
        text = template.get('text', '').format(**variables)
        html = template.get('html', '').format(**variables)

        return {
            'subject': subject,
            'text': text,
            'html': html
        }

    def _send_email(
        self,
        to_email: str,
        to_name: Optional[str],
        subject: str,
        text_content: str,
        html_content: str,
        from_email: str,
        from_name: str
    ) -> Dict[str, Any]:
        """Send an email via SendGrid."""
        client = self._get_client()
        if not client:
            return {'success': False, 'error': 'SendGrid not configured'}

        try:
            message = Mail(
                from_email=Email(from_email, from_name),
                to_emails=To(to_email, to_name),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )

            response = client.send(message)

            if response.status_code in [200, 202]:
                current_app.logger.info(f"Email sent to {to_email}: {subject}")
                return {'success': True, 'status_code': response.status_code}
            else:
                current_app.logger.error(f"SendGrid error: {response.status_code}")
                return {'success': False, 'error': f"Status code: {response.status_code}"}

        except Exception as e:
            current_app.logger.error(f"Failed to send email: {str(e)}")
            return {'success': False, 'error': str(e)}

    # ==================== Public Methods ====================

    def send_welcome_email(self, tenant_id: int, member_id: int) -> Dict[str, Any]:
        """
        Send welcome email to newly enrolled member.

        Args:
            tenant_id: Tenant ID
            member_id: Member ID

        Returns:
            Dict with send result
        """
        from ..models import Member
        settings = self._get_tenant_settings(tenant_id)

        if not settings.get('enabled') or not settings.get('welcome_email'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        member = Member.query.get(member_id)
        if not member:
            return {'success': False, 'error': 'Member not found'}

        tier_name = member.tier.name if member.tier else 'Standard'
        bonus_percent = float(member.tier.bonus_rate * 100) if member.tier else 0

        variables = {
            'member_name': member.name or member.email.split('@')[0],
            'member_number': member.member_number,
            'tier_name': tier_name,
            'bonus_percent': f"{bonus_percent:.0f}"
        }

        rendered = self._render_template('welcome', variables, settings)

        return self._send_email(
            to_email=member.email,
            to_name=member.name,
            subject=rendered['subject'],
            text_content=rendered['text'],
            html_content=rendered['html'],
            from_email=settings['from_email'],
            from_name=settings['from_name']
        )

    def send_trade_in_created(self, tenant_id: int, batch_id: int) -> Dict[str, Any]:
        """
        Send notification when trade-in batch is created.

        Args:
            tenant_id: Tenant ID
            batch_id: Trade-in batch ID

        Returns:
            Dict with send result
        """
        from ..models import TradeInBatch
        settings = self._get_tenant_settings(tenant_id)

        # Use granular setting (trade_in_created) with legacy fallback (trade_in_updates)
        if not settings.get('enabled') or not settings.get('trade_in_created'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        batch = TradeInBatch.query.get(batch_id)
        if not batch or not batch.member:
            return {'success': False, 'error': 'Batch or member not found'}

        member = batch.member
        variables = {
            'member_name': member.name or member.email.split('@')[0],
            'batch_reference': batch.batch_reference,
            'item_count': batch.total_items or 0,
            'trade_value': f"{float(batch.total_trade_value or 0):.2f}",
            'category': batch.category or 'Other'
        }

        rendered = self._render_template('trade_in_created', variables, settings)

        return self._send_email(
            to_email=member.email,
            to_name=member.name,
            subject=rendered['subject'],
            text_content=rendered['text'],
            html_content=rendered['html'],
            from_email=settings['from_email'],
            from_name=settings['from_name']
        )

    def send_trade_in_completed(
        self,
        tenant_id: int,
        batch_id: int,
        bonus_amount: float
    ) -> Dict[str, Any]:
        """
        Send notification when trade-in batch is completed.

        Args:
            tenant_id: Tenant ID
            batch_id: Trade-in batch ID
            bonus_amount: Bonus amount issued

        Returns:
            Dict with send result
        """
        from ..models import TradeInBatch
        settings = self._get_tenant_settings(tenant_id)

        # Use granular setting (trade_in_approved) with legacy fallback (trade_in_updates)
        if not settings.get('enabled') or not settings.get('trade_in_approved'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        batch = TradeInBatch.query.get(batch_id)
        if not batch or not batch.member:
            return {'success': False, 'error': 'Batch or member not found'}

        member = batch.member
        tier_name = member.tier.name if member.tier else 'Standard'
        bonus_percent = float(member.tier.bonus_rate * 100) if member.tier else 0
        trade_value = float(batch.total_trade_value or 0)
        credit_amount = trade_value + bonus_amount

        variables = {
            'member_name': member.name or member.email.split('@')[0],
            'batch_reference': batch.batch_reference,
            'trade_value': f"{trade_value:.2f}",
            'tier_name': tier_name,
            'bonus_percent': f"{bonus_percent:.0f}",
            'bonus_amount': f"{bonus_amount:.2f}",
            'credit_amount': f"{credit_amount:.2f}"
        }

        rendered = self._render_template('trade_in_completed', variables, settings)

        return self._send_email(
            to_email=member.email,
            to_name=member.name,
            subject=rendered['subject'],
            text_content=rendered['text'],
            html_content=rendered['html'],
            from_email=settings['from_email'],
            from_name=settings['from_name']
        )

    def send_tier_upgrade(
        self,
        tenant_id: int,
        member_id: int,
        old_tier_name: str,
        new_tier_name: str,
        new_bonus_rate: float
    ) -> Dict[str, Any]:
        """
        Send notification when member's tier is upgraded.

        Args:
            tenant_id: Tenant ID
            member_id: Member ID
            old_tier_name: Previous tier name
            new_tier_name: New tier name
            new_bonus_rate: New bonus rate (decimal, e.g., 0.10)

        Returns:
            Dict with send result
        """
        from ..models import Member
        settings = self._get_tenant_settings(tenant_id)

        # Use granular setting (tier_upgrade) with legacy fallback (tier_change)
        if not settings.get('enabled') or not settings.get('tier_upgrade'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        member = Member.query.get(member_id)
        if not member:
            return {'success': False, 'error': 'Member not found'}

        variables = {
            'member_name': member.name or member.email.split('@')[0],
            'old_tier': old_tier_name,
            'new_tier': new_tier_name,
            'bonus_percent': f"{new_bonus_rate * 100:.0f}"
        }

        rendered = self._render_template('tier_upgrade', variables, settings)

        return self._send_email(
            to_email=member.email,
            to_name=member.name,
            subject=rendered['subject'],
            text_content=rendered['text'],
            html_content=rendered['html'],
            from_email=settings['from_email'],
            from_name=settings['from_name']
        )

    def send_credit_issued(
        self,
        tenant_id: int,
        member_id: int,
        credit_amount: float,
        reason: str,
        new_balance: float
    ) -> Dict[str, Any]:
        """
        Send notification when store credit is issued.

        Args:
            tenant_id: Tenant ID
            member_id: Member ID
            credit_amount: Amount of credit issued
            reason: Reason for credit
            new_balance: New total balance

        Returns:
            Dict with send result
        """
        from ..models import Member
        settings = self._get_tenant_settings(tenant_id)

        # Use granular setting (credit_added) with legacy fallback (credit_issued)
        if not settings.get('enabled') or not settings.get('credit_added'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        member = Member.query.get(member_id)
        if not member:
            return {'success': False, 'error': 'Member not found'}

        variables = {
            'member_name': member.name or member.email.split('@')[0],
            'credit_amount': f"{credit_amount:.2f}",
            'reason': reason,
            'new_balance': f"{new_balance:.2f}"
        }

        rendered = self._render_template('credit_issued', variables, settings)

        return self._send_email(
            to_email=member.email,
            to_name=member.name,
            subject=rendered['subject'],
            text_content=rendered['text'],
            html_content=rendered['html'],
            from_email=settings['from_email'],
            from_name=settings['from_name']
        )

    def send_custom_email(
        self,
        tenant_id: int,
        to_email: str,
        to_name: Optional[str],
        subject: str,
        text_content: str,
        html_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a custom email.

        Args:
            tenant_id: Tenant ID
            to_email: Recipient email
            to_name: Recipient name
            subject: Email subject
            text_content: Plain text content
            html_content: HTML content (optional)

        Returns:
            Dict with send result
        """
        settings = self._get_tenant_settings(tenant_id)

        if not settings.get('enabled'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        return self._send_email(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            text_content=text_content,
            html_content=html_content or text_content,
            from_email=settings['from_email'],
            from_name=settings['from_name']
        )

    def send_bulk_tier_email(
        self,
        tenant_id: int,
        tier_names: List[str],
        subject: str,
        text_content: str,
        html_content: Optional[str] = None,
        created_by: str = 'admin'
    ) -> Dict[str, Any]:
        """
        Send bulk email to all members in specified tiers.

        Args:
            tenant_id: Tenant ID
            tier_names: List of tier names to email (e.g., ['GOLD', 'PLATINUM'])
            subject: Email subject
            text_content: Plain text content
            html_content: HTML content (optional)
            created_by: Staff email for audit

        Returns:
            Dict with send results (sent count, failed count, etc.)
        """
        from ..models import Member, Tier

        settings = self._get_tenant_settings(tenant_id)

        if not settings.get('enabled'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        # Get tier IDs for the specified tier names
        tiers = Tier.query.filter(
            Tier.tenant_id == tenant_id,
            Tier.name.in_(tier_names)
        ).all()

        if not tiers:
            return {'success': False, 'error': f'No tiers found matching: {tier_names}'}

        tier_ids = [t.id for t in tiers]

        # Get active members in these tiers
        members = Member.query.filter(
            Member.tenant_id == tenant_id,
            Member.tier_id.in_(tier_ids),
            Member.status == 'active'
        ).all()

        if not members:
            return {
                'success': True,
                'sent': 0,
                'failed': 0,
                'message': 'No active members found in specified tiers'
            }

        # Send emails
        sent_count = 0
        failed_count = 0
        failed_emails = []

        for member in members:
            if not member.email:
                failed_count += 1
                continue

            # Personalize content with member variables
            personalized_text = text_content.replace('{member_name}', member.name or 'Member')
            personalized_text = personalized_text.replace('{member_number}', member.member_number or '')
            personalized_text = personalized_text.replace('{tier_name}', member.tier.name if member.tier else 'Member')

            personalized_html = html_content or personalized_text
            if html_content:
                personalized_html = html_content.replace('{member_name}', member.name or 'Member')
                personalized_html = personalized_html.replace('{member_number}', member.member_number or '')
                personalized_html = personalized_html.replace('{tier_name}', member.tier.name if member.tier else 'Member')

            result = self._send_email(
                to_email=member.email,
                to_name=member.name,
                subject=subject,
                text_content=personalized_text,
                html_content=personalized_html,
                from_email=settings['from_email'],
                from_name=settings['from_name']
            )

            if result.get('success'):
                sent_count += 1
            else:
                failed_count += 1
                failed_emails.append(member.email)

        # Log the bulk operation
        current_app.logger.info(
            f"Bulk email to tiers {tier_names}: {sent_count} sent, {failed_count} failed. By: {created_by}"
        )

        return {
            'success': True,
            'tiers': tier_names,
            'total_recipients': len(members),
            'sent': sent_count,
            'failed': failed_count,
            'failed_emails': failed_emails[:10],  # Limit to first 10 for response size
            'created_by': created_by
        }

    def get_tier_member_counts(self, tenant_id: int) -> Dict[str, int]:
        """
        Get counts of active members by tier.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dict mapping tier names to member counts
        """
        from ..models import Member, Tier
        from ..extensions import db
        from sqlalchemy import func

        counts = db.session.query(
            Tier.name,
            func.count(Member.id)
        ).join(
            Member, Member.tier_id == Tier.id
        ).filter(
            Member.tenant_id == tenant_id,
            Member.status == 'active'
        ).group_by(Tier.name).all()

        return {tier_name: count for tier_name, count in counts}

    def send_credit_expiring(
        self,
        tenant_id: int,
        member_id: int,
        expiring_amount: float,
        expiration_date: str
    ) -> Dict[str, Any]:
        """
        Send notification when member's store credit is expiring soon.

        Args:
            tenant_id: Tenant ID
            member_id: Member ID
            expiring_amount: Amount of credit expiring
            expiration_date: Date credit expires (formatted string)

        Returns:
            Dict with send result
        """
        from ..models import Member
        settings = self._get_tenant_settings(tenant_id)

        # Use granular setting (credit_expiring)
        if not settings.get('enabled') or not settings.get('credit_expiring'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        member = Member.query.get(member_id)
        if not member:
            return {'success': False, 'error': 'Member not found'}

        variables = {
            'member_name': member.name or member.email.split('@')[0],
            'expiring_amount': f"{expiring_amount:.2f}",
            'expiration_date': expiration_date
        }

        rendered = self._render_template('credit_expiring', variables, settings)

        return self._send_email(
            to_email=member.email,
            to_name=member.name,
            subject=rendered['subject'],
            text_content=rendered['text'],
            html_content=rendered['html'],
            from_email=settings['from_email'],
            from_name=settings['from_name']
        )

    def send_monthly_credit(
        self,
        tenant_id: int,
        member_id: int,
        credit_amount: float,
        tier_name: str,
        expiration_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send notification when monthly credit is issued.

        Args:
            tenant_id: Tenant ID
            member_id: Member ID
            credit_amount: Amount of monthly credit
            tier_name: Member's tier name
            expiration_date: When credit expires (optional)

        Returns:
            Dict with send result
        """
        from ..models import Member
        settings = self._get_tenant_settings(tenant_id)

        # Use granular setting (monthly_credit)
        if not settings.get('enabled') or not settings.get('monthly_credit'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        member = Member.query.get(member_id)
        if not member:
            return {'success': False, 'error': 'Member not found'}

        expiration_info = f"Expires: {expiration_date}" if expiration_date else "No expiration"
        expiration_html = f"<p><strong>Expires:</strong> {expiration_date}</p>" if expiration_date else ""

        variables = {
            'member_name': member.name or member.email.split('@')[0],
            'credit_amount': f"{credit_amount:.2f}",
            'tier_name': tier_name,
            'expiration_info': expiration_info,
            'expiration_html': expiration_html
        }

        rendered = self._render_template('monthly_credit', variables, settings)

        return self._send_email(
            to_email=member.email,
            to_name=member.name,
            subject=rendered['subject'],
            text_content=rendered['text'],
            html_content=rendered['html'],
            from_email=settings['from_email'],
            from_name=settings['from_name']
        )

    def send_referral_success(
        self,
        tenant_id: int,
        referrer_member_id: int,
        referred_name: str,
        referrer_reward: float,
        referred_reward: float,
        referral_code: str
    ) -> Dict[str, Any]:
        """
        Send notification when a referral is successful.

        Args:
            tenant_id: Tenant ID
            referrer_member_id: ID of the referring member
            referred_name: Name of the person who signed up
            referrer_reward: Reward given to the referrer
            referred_reward: Reward given to the new member
            referral_code: The referral code used

        Returns:
            Dict with send result
        """
        from ..models import Member
        settings = self._get_tenant_settings(tenant_id)

        # Use granular setting (referral_success)
        if not settings.get('enabled') or not settings.get('referral_success'):
            return {'success': False, 'skipped': True, 'reason': 'Email disabled'}

        member = Member.query.get(referrer_member_id)
        if not member:
            return {'success': False, 'error': 'Member not found'}

        variables = {
            'member_name': member.name or member.email.split('@')[0],
            'referred_name': referred_name,
            'reward_amount': f"{referrer_reward:.2f}",
            'referred_reward': f"{referred_reward:.2f}",
            'referral_code': referral_code
        }

        rendered = self._render_template('referral_success', variables, settings)

        return self._send_email(
            to_email=member.email,
            to_name=member.name,
            subject=rendered['subject'],
            text_content=rendered['text'],
            html_content=rendered['html'],
            from_email=settings['from_email'],
            from_name=settings['from_name']
        )


# Singleton instance
notification_service = NotificationService()
