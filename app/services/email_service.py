"""
Email Notification Service for TradeUp.

Handles transactional emails for:
- Welcome emails on enrollment
- Trade-in status updates
- Tier change notifications
- Store credit issued
- Credit expiration warnings
- Nudge emails (points expiring, tier progress, inactive, trade-in reminder)
"""
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from flask import current_app, render_template_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


class EmailService:
    """Service for sending transactional emails."""

    # Default brand colors for email templates
    DEFAULT_BRAND_COLOR = '#4F46E5'
    DEFAULT_BRAND_COLOR_DARK = '#3730A3'

    # HTML template file mappings for nudge emails
    HTML_TEMPLATE_FILES = {
        'points_expiring': 'points_expiring.html',
        'tier_progress': 'tier_progress.html',
        'inactive_reengagement': 'inactive_reminder.html',
        'trade_in_reminder': 'trade_in_reminder.html',
    }

    # Default email templates
    DEFAULT_TEMPLATES = {
        'welcome': {
            'name': 'Welcome to the Program',
            'subject': 'Welcome to {{program_name}}, {{member_name}}!',
            'body': '''
Hi {{member_name}},

Welcome to {{program_name}}! We're thrilled to have you as a member.

{{#if tier_name}}
You've been enrolled in the **{{tier_name}}** tier, which gives you:
{{tier_benefits}}
{{/if}}

Your member number is: **{{member_number}}**

Start earning rewards on your purchases and trade-ins today!

Best,
The {{shop_name}} Team
            ''',
            'category': 'enrollment',
        },
        'trade_in_received': {
            'name': 'Trade-In Received',
            'subject': 'We received your trade-in #{{trade_in_id}}',
            'body': '''
Hi {{member_name}},

Thank you for your trade-in submission! We've received your items and will review them soon.

**Trade-In Details:**
- ID: #{{trade_in_id}}
- Items: {{item_count}}
- Estimated Value: {{estimated_value}}

We'll notify you once your trade-in has been reviewed.

Best,
The {{shop_name}} Team
            ''',
            'category': 'trade_in',
        },
        'trade_in_approved': {
            'name': 'Trade-In Approved',
            'subject': 'Your trade-in #{{trade_in_id}} has been approved!',
            'body': '''
Hi {{member_name}},

Great news! Your trade-in has been approved.

**Trade-In Details:**
- ID: #{{trade_in_id}}
- Credit Issued: {{credit_amount}}
{{#if tier_bonus}}
- Tier Bonus ({{tier_name}}): +{{tier_bonus}}
- Total Credit: {{total_credit}}
{{/if}}

Your store credit has been added to your account and is ready to use!

Best,
The {{shop_name}} Team
            ''',
            'category': 'trade_in',
        },
        'trade_in_rejected': {
            'name': 'Trade-In Update',
            'subject': 'Update on your trade-in #{{trade_in_id}}',
            'body': '''
Hi {{member_name}},

We've reviewed your trade-in submission.

**Trade-In Details:**
- ID: #{{trade_in_id}}
- Status: {{status}}
{{#if reason}}
- Notes: {{reason}}
{{/if}}

If you have questions, please contact us.

Best,
The {{shop_name}} Team
            ''',
            'category': 'trade_in',
        },
        'tier_upgrade': {
            'name': 'Tier Upgrade',
            'subject': 'Congratulations! You\'ve been upgraded to {{new_tier}}',
            'body': '''
Hi {{member_name}},

Exciting news! You've been upgraded from **{{old_tier}}** to **{{new_tier}}**!

Your new benefits include:
{{tier_benefits}}

Thank you for being a valued member!

Best,
The {{shop_name}} Team
            ''',
            'category': 'tier',
        },
        'tier_downgrade': {
            'name': 'Tier Change Notice',
            'subject': 'Your membership tier has changed',
            'body': '''
Hi {{member_name}},

Your membership tier has changed from **{{old_tier}}** to **{{new_tier}}**.

{{#if reason}}
Reason: {{reason}}
{{/if}}

Your current benefits:
{{tier_benefits}}

Best,
The {{shop_name}} Team
            ''',
            'category': 'tier',
        },
        'credit_issued': {
            'name': 'Store Credit Added',
            'subject': '{{credit_amount}} store credit added to your account',
            'body': '''
Hi {{member_name}},

Good news! Store credit has been added to your account.

**Credit Details:**
- Amount: {{credit_amount}}
- Reason: {{reason}}
{{#if expiration_date}}
- Expires: {{expiration_date}}
{{/if}}

Your current balance: {{current_balance}}

Best,
The {{shop_name}} Team
            ''',
            'category': 'credit',
        },
        'credit_expiring': {
            'name': 'Credit Expiration Warning',
            'subject': '{{amount}} in store credit expiring soon',
            'body': '''
Hi {{member_name}},

This is a friendly reminder that you have store credit expiring soon.

**Expiring Credit:**
- Amount: {{amount}}
- Expires: {{expiration_date}}

Don't let it go to waste - visit our store today!

Best,
The {{shop_name}} Team
            ''',
            'category': 'credit',
        },
        'monthly_credit': {
            'name': 'Monthly Credit Issued',
            'subject': 'Your monthly {{credit_amount}} credit is here!',
            'body': '''
Hi {{member_name}},

Your monthly membership credit has arrived!

**Credit Details:**
- Amount: {{credit_amount}}
- Tier: {{tier_name}}
{{#if expiration_date}}
- Expires: {{expiration_date}}
{{/if}}

Thank you for being a {{tier_name}} member!

Best,
The {{shop_name}} Team
            ''',
            'category': 'credit',
        },
        'referral_success': {
            'name': 'Referral Reward',
            'subject': 'You earned {{reward_amount}} for your referral!',
            'body': '''
Hi {{member_name}},

Congratulations! {{referred_name}} signed up using your referral code.

**Reward Details:**
- Your Reward: {{reward_amount}}
- Their Reward: {{referred_reward}}

Keep sharing your code to earn more rewards!
Your referral code: **{{referral_code}}**

Best,
The {{shop_name}} Team
            ''',
            'category': 'referral',
        },
        'password_reset': {
            'name': 'Password Reset',
            'subject': 'Reset your {{program_name}} password',
            'body': '''
Hi {{member_name}},

We received a request to reset your password for your {{program_name}} account.

Click the link below to reset your password:

**{{reset_link}}**

This link will expire in 1 hour.

If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.

Best,
The {{shop_name}} Team
            ''',
            'category': 'account',
        },
        'billing_subscription_activated': {
            'name': 'Subscription Activated',
            'subject': 'Your TradeUp subscription is now active',
            'body': '''
Hi {{merchant_name}},

Great news! Your TradeUp subscription has been activated.

**Subscription Details:**
- Plan: {{plan_name}}
- Status: Active
{{#if trial_days}}
- Trial Period: {{trial_days}} days remaining
{{/if}}

You now have full access to all TradeUp features included in your plan.

Need help getting started? Visit our documentation or contact support.

Best,
The TradeUp Team
            ''',
            'category': 'billing',
        },
        'billing_subscription_cancelled': {
            'name': 'Subscription Cancelled',
            'subject': 'Your TradeUp subscription has been cancelled',
            'body': '''
Hi {{merchant_name}},

Your TradeUp subscription has been cancelled.

**Details:**
- Plan: {{plan_name}}
- Status: Cancelled
- Access Until: {{access_until}}

Your data will be preserved if you decide to resubscribe later.

If you have any feedback about your experience, we'd love to hear from you.

Best,
The TradeUp Team
            ''',
            'category': 'billing',
        },
        'billing_usage_warning': {
            'name': 'Usage Limit Warning',
            'subject': 'TradeUp usage approaching limit',
            'body': '''
Hi {{merchant_name}},

Your TradeUp usage is approaching the capped amount for this billing period.

**Current Usage:**
- Balance Used: {{balance_used}}
- Capped Amount: {{capped_amount}}

To avoid service interruption, consider upgrading your plan.

Best,
The TradeUp Team
            ''',
            'category': 'billing',
        },
        'anniversary_reward': {
            'name': 'Anniversary Reward',
            'subject': 'Happy {{anniversary_year}} Anniversary, {{member_name}}! {{shop_name}} has a gift for you',
            'body': '''
Hi {{member_name}},

Happy {{anniversary_year}} Anniversary with {{shop_name}}!

We're celebrating **{{years_number}} year(s)** of you being a valued member of our rewards program. Time flies when we're having fun together!

**Your Anniversary Gift:**
{{reward_description}}

{{#if custom_message}}
{{custom_message}}
{{/if}}

Don't let this special gift go to waste - visit us today and treat yourself to something you love!

**[Shop Now]({{shop_url}})**

Thank you for being part of our community. Here's to many more years together!

Warmly,
The {{shop_name}} Team
            ''',
            'category': 'anniversary',
        },
        'points_expiring': {
            'name': 'Points Expiring Reminder',
            'subject': '{{expiring_points}} points expiring in {{days_until}} days!',
            'body': '''
Hi {{member_name}},

This is a friendly reminder that you have **{{expiring_points}} points** expiring on **{{expiration_date}}**!

That's only **{{days_until}} days** away.

**Don't let your points go to waste!**

{{#if rewards_available}}
Here are some great ways to redeem your points:
{{rewards_list}}
{{/if}}

Visit {{shop_name}} today to redeem your points before they expire.

**[Redeem Points Now]({{shop_url}})**

Your current points balance: **{{current_balance}} points**

Best,
The {{shop_name}} Team
            ''',
            'category': 'nudge',
        },
        'tier_progress': {
            'name': 'Tier Progress Reminder',
            'subject': "You're {{progress_percent}}% of the way to {{next_tier}}!",
            'body': '''
Hi {{member_name}},

Great news! You're making excellent progress toward your next membership tier.

**Your Progress:**
- Current Tier: **{{current_tier}}**
- Next Tier: **{{next_tier}}**
- Progress: **{{progress_percent}}%**
- Points Needed: **{{points_needed}} more points**

You currently have **{{current_points}} points**. Just **{{points_needed}} more points** and you'll unlock **{{next_tier}}**!

{{#if next_tier_benefits}}
**Benefits you'll unlock with {{next_tier}}:**
{{next_tier_benefits}}
{{/if}}

Keep earning points through purchases and trade-ins to reach your goal!

**[Shop Now]({{shop_url}})**

Best,
The {{shop_name}} Team
            ''',
            'category': 'nudge',
        },
        'inactive_reengagement': {
            'name': 'Inactive Member Re-engagement',
            'subject': 'We miss you, {{member_name}}! Here\'s {{incentive_text}} to welcome you back',
            'body': '''
Hi {{member_name}},

We've noticed it's been a while since we've seen you at {{shop_name}} - **{{days_inactive}} days** to be exact! We miss having you around.

**Your Account Status:**
- Points Balance: **{{points_balance}} points** (ready to use!)
- Current Tier: **{{tier_name}}**

{{#if missed_opportunities}}
**Here's what you've been missing:**
{{missed_opportunities}}
{{/if}}

**Come back and get {{incentive_text}}!**

We'd love to welcome you back with a special reward. Visit {{shop_name}} today and we'll make it worth your while.

**[Shop Now & Claim Your Reward]({{shop_url}})**

Your points are waiting for you, and we've got some exciting new items we think you'll love!

Best,
The {{shop_name}} Team

P.S. Your {{points_balance}} points are still available - don't let them go to waste!
            ''',
            'category': 'nudge',
        },
        'trade_in_reminder': {
            'name': 'Trade-In Reminder',
            'subject': 'Have items to trade in? {{shop_name}} is ready for your next trade-in!',
            'body': '''
Hi {{member_name}},

It's been **{{days_since_last}} days** since your last trade-in at {{shop_name}}. We wanted to remind you about our trade-in program - a great way to turn your unused items into store credit!

**Why Trade In With Us?**
- Get instant store credit for your items
- Fair pricing based on current market values
- Quick and easy process

{{#if has_tier_bonus}}
**As a {{tier_name}} member, you get an extra {{tier_bonus}}% bonus on all trade-ins!**
{{/if}}

{{#if credit_rates}}
**Current Tier Bonuses:**
{{credit_rates}}
{{/if}}

**Items We Accept:**
- Sports cards (baseball, basketball, football, hockey)
- Pokemon cards
- Magic: The Gathering cards
- Other trading card games

Bring in your items today and see what they're worth. Our team is ready to help!

**[Start Your Trade-In]({{shop_url}})**

Best,
The {{shop_name}} Team

P.S. Not sure what your cards are worth? Stop by and we'll give you a free evaluation!
            ''',
            'category': 'nudge',
        },
    }

    def __init__(self):
        self.sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')

    def get_template(self, template_key: str, tenant_id: int) -> Optional[Dict[str, Any]]:
        """
        Get an email template by key.
        First checks for custom tenant template in database, falls back to default.
        """
        # Check for custom template in tenant settings
        custom_template = self._get_custom_template(template_key, tenant_id)
        if custom_template:
            return custom_template

        # Fall back to default template
        return self.DEFAULT_TEMPLATES.get(template_key)

    def _get_custom_template(self, template_key: str, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Get a custom template from the database if it exists."""
        try:
            from flask import has_app_context
            if not has_app_context():
                return None

            from ..models.tenant import Tenant
            tenant = Tenant.query.get(tenant_id)
            if not tenant or not tenant.settings:
                return None

            # Custom templates stored in tenant.settings['email_templates'][template_key]
            email_templates = tenant.settings.get('email_templates', {})
            custom = email_templates.get(template_key)

            if custom:
                # Merge with default to ensure all required fields exist
                default = self.DEFAULT_TEMPLATES.get(template_key, {})
                return {
                    'name': custom.get('name', default.get('name', template_key)),
                    'subject': custom.get('subject', default.get('subject', '')),
                    'body': custom.get('body', default.get('body', '')),
                    'category': custom.get('category', default.get('category', 'general')),
                    'is_custom': True,
                }
            return None
        except Exception:
            return None

    def save_custom_template(
        self,
        template_key: str,
        tenant_id: int,
        name: str,
        subject: str,
        body: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save a custom email template for a tenant.

        Args:
            template_key: Template identifier (e.g., 'welcome', 'trade_in_approved')
            tenant_id: Tenant ID
            name: Display name for the template
            subject: Email subject (supports {{variable}} placeholders)
            body: Email body (supports {{variable}} placeholders)
            category: Optional category for grouping

        Returns:
            Dict with success status and the saved template
        """
        try:
            from ..models.tenant import Tenant
            from ..extensions import db

            tenant = Tenant.query.get(tenant_id)
            if not tenant:
                return {'success': False, 'error': 'Tenant not found'}

            # Initialize settings if needed
            if tenant.settings is None:
                tenant.settings = {}

            # Initialize email_templates if needed
            if 'email_templates' not in tenant.settings:
                tenant.settings = {**tenant.settings, 'email_templates': {}}

            # Get default category if not provided
            if not category:
                default = self.DEFAULT_TEMPLATES.get(template_key, {})
                category = default.get('category', 'general')

            # Save the custom template
            email_templates = tenant.settings.get('email_templates', {})
            email_templates[template_key] = {
                'name': name,
                'subject': subject,
                'body': body,
                'category': category,
                'updated_at': datetime.utcnow().isoformat(),
            }

            tenant.settings = {**tenant.settings, 'email_templates': email_templates}
            db.session.commit()

            return {
                'success': True,
                'template': {
                    'id': template_key,
                    **email_templates[template_key],
                    'is_custom': True,
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def reset_template_to_default(self, template_key: str, tenant_id: int) -> Dict[str, Any]:
        """
        Reset a custom template back to the default.

        Args:
            template_key: Template identifier
            tenant_id: Tenant ID

        Returns:
            Dict with success status
        """
        try:
            from ..models.tenant import Tenant
            from ..extensions import db

            tenant = Tenant.query.get(tenant_id)
            if not tenant or not tenant.settings:
                return {'success': True, 'message': 'No custom template to reset'}

            email_templates = tenant.settings.get('email_templates', {})
            if template_key in email_templates:
                del email_templates[template_key]
                tenant.settings = {**tenant.settings, 'email_templates': email_templates}
                db.session.commit()

            return {'success': True, 'message': f'Template {template_key} reset to default'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_all_templates(self, tenant_id: int) -> List[Dict[str, Any]]:
        """Get all available email templates for a tenant, with custom overrides."""
        templates = []

        # Get custom templates from database
        custom_templates = {}
        try:
            from flask import has_app_context
            if has_app_context():
                from ..models.tenant import Tenant
                tenant = Tenant.query.get(tenant_id)
                if tenant and tenant.settings:
                    custom_templates = tenant.settings.get('email_templates', {})
        except Exception:
            pass

        # Build template list with custom overrides
        for key, template in self.DEFAULT_TEMPLATES.items():
            if key in custom_templates:
                # Use custom template
                custom = custom_templates[key]
                templates.append({
                    'id': key,
                    'name': custom.get('name', template['name']),
                    'subject': custom.get('subject', template['subject']),
                    'body': custom.get('body', template['body']),
                    'category': custom.get('category', template['category']),
                    'is_custom': True,
                    'updated_at': custom.get('updated_at'),
                })
            else:
                # Use default template
                templates.append({
                    'id': key,
                    'name': template['name'],
                    'subject': template['subject'],
                    'body': template['body'],
                    'category': template['category'],
                    'is_custom': False,
                })

        return templates

    def render_template(self, template: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, str]:
        """
        Render a template with the provided data.
        Uses simple {{variable}} replacement (Handlebars-like).
        """
        subject = template['subject']
        body = template['body']

        # Simple variable replacement
        for key, value in data.items():
            placeholder = '{{' + key + '}}'
            subject = subject.replace(placeholder, str(value or ''))
            body = body.replace(placeholder, str(value or ''))

        # Handle conditionals (basic support)
        # {{#if var}}...{{/if}} - include content if var is truthy
        import re

        def replace_conditionals(text: str, data: Dict[str, Any]) -> str:
            pattern = r'\{\{#if (\w+)\}\}(.*?)\{\{/if\}\}'

            def replacer(match):
                var_name = match.group(1)
                content = match.group(2)
                if data.get(var_name):
                    return content
                return ''

            return re.sub(pattern, replacer, text, flags=re.DOTALL)

        subject = replace_conditionals(subject, data)
        body = replace_conditionals(body, data)

        return {
            'subject': subject.strip(),
            'body': body.strip(),
        }

    def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email using SendGrid.
        """
        if not self.sendgrid_api_key:
            current_app.logger.warning('SendGrid API key not configured, email not sent')
            return {'success': False, 'error': 'SendGrid not configured'}

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)

            sender = Email(
                email=from_email or 'noreply@tradeup.io',
                name=from_name or 'TradeUp'
            )

            recipient = To(email=to_email, name=to_name)

            # Convert markdown-like formatting to HTML
            html_body = self._markdown_to_html(body)

            message = Mail(
                from_email=sender,
                to_emails=recipient,
                subject=subject,
                html_content=html_body
            )

            response = sg.send(message)

            return {
                'success': True,
                'status_code': response.status_code,
            }

        except Exception as e:
            current_app.logger.error(f'Failed to send email: {str(e)}')
            return {'success': False, 'error': str(e)}

    def _markdown_to_html(self, text: str) -> str:
        """Convert simple markdown to HTML."""
        import re

        # Convert **bold** to <strong>
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

        # Convert newlines to <br>
        text = text.replace('\n\n', '</p><p>')
        text = text.replace('\n', '<br>')

        # Wrap in paragraphs
        text = f'<p>{text}</p>'

        # Wrap in basic HTML email template
        html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        p {{ margin: 0 0 16px 0; }}
        strong {{ font-weight: 600; }}
    </style>
</head>
<body>
    {text}
</body>
</html>
        '''

        return html

    def _get_html_template_path(self, template_key: str) -> Optional[Path]:
        """Get the path to an HTML template file."""
        if template_key not in self.HTML_TEMPLATE_FILES:
            return None

        # Get the templates directory path
        templates_dir = Path(__file__).parent.parent / 'templates' / 'emails'
        template_file = templates_dir / self.HTML_TEMPLATE_FILES[template_key]

        if template_file.exists():
            return template_file
        return None

    def _load_html_template(self, template_key: str) -> Optional[str]:
        """Load an HTML template file."""
        template_path = self._get_html_template_path(template_key)
        if not template_path:
            return None

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            current_app.logger.warning(f'Failed to load HTML template {template_key}: {str(e)}')
            return None

    def _get_brand_colors(self, tenant_id: int) -> Dict[str, str]:
        """Get brand colors for a tenant, with defaults."""
        brand_color = self.DEFAULT_BRAND_COLOR
        brand_color_dark = self.DEFAULT_BRAND_COLOR_DARK

        try:
            from flask import has_app_context
            if has_app_context():
                from ..models.tenant import Tenant
                tenant = Tenant.query.get(tenant_id)
                if tenant and tenant.settings:
                    branding = tenant.settings.get('branding', {})
                    brand_color = branding.get('primary_color', self.DEFAULT_BRAND_COLOR)
                    brand_color_dark = branding.get('primary_color_dark', self.DEFAULT_BRAND_COLOR_DARK)
        except Exception:
            pass

        return {
            'brand_color': brand_color,
            'brand_color_dark': brand_color_dark,
        }

    def render_html_template(
        self,
        template_key: str,
        tenant_id: int,
        data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Render an HTML email template with data.

        Uses mobile-responsive HTML templates for nudge emails.
        Falls back to markdown conversion for other templates.

        Args:
            template_key: The template identifier
            tenant_id: Tenant ID for branding
            data: Template variables

        Returns:
            Rendered HTML string or None if template not found
        """
        import re

        html_content = self._load_html_template(template_key)
        if not html_content:
            return None

        # Get brand colors
        colors = self._get_brand_colors(tenant_id)
        data = {**data, **colors}

        # Replace simple {{variable}} placeholders
        for key, value in data.items():
            placeholder = '{{' + key + '}}'
            html_content = html_content.replace(placeholder, str(value or ''))

        # Handle conditionals: {{#if var}}...{{/if}}
        def replace_conditionals(text: str, context: Dict[str, Any]) -> str:
            pattern = r'\{\{#if (\w+)\}\}(.*?)\{\{/if\}\}'

            def replacer(match):
                var_name = match.group(1)
                content = match.group(2)
                if context.get(var_name):
                    return content
                return ''

            return re.sub(pattern, replacer, text, flags=re.DOTALL)

        html_content = replace_conditionals(html_content, data)

        # Clean up any remaining unmatched placeholders
        html_content = re.sub(r'\{\{[^}]+\}\}', '', html_content)

        return html_content

    def send_html_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email with pre-rendered HTML content.
        """
        if not self.sendgrid_api_key:
            current_app.logger.warning('SendGrid API key not configured, email not sent')
            return {'success': False, 'error': 'SendGrid not configured'}

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)

            sender = Email(
                email=from_email or 'noreply@tradeup.io',
                name=from_name or 'TradeUp'
            )

            recipient = To(email=to_email, name=to_name)

            message = Mail(
                from_email=sender,
                to_emails=recipient,
                subject=subject,
                html_content=html_body
            )

            response = sg.send(message)

            return {
                'success': True,
                'status_code': response.status_code,
            }

        except Exception as e:
            current_app.logger.error(f'Failed to send HTML email: {str(e)}')
            return {'success': False, 'error': str(e)}

    def send_template_email(
        self,
        template_key: str,
        tenant_id: int,
        to_email: str,
        to_name: str,
        data: Dict[str, Any],
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email using a template.

        For nudge emails (points_expiring, tier_progress, inactive_reengagement,
        trade_in_reminder), uses mobile-responsive HTML templates.
        For other emails, uses the simple markdown-to-HTML conversion.
        """
        template = self.get_template(template_key, tenant_id)
        if not template:
            return {'success': False, 'error': f'Template not found: {template_key}'}

        rendered = self.render_template(template, data)

        # Check if we have an HTML template for this key
        html_body = self.render_html_template(template_key, tenant_id, data)

        if html_body:
            # Use the mobile-responsive HTML template
            return self.send_html_email(
                to_email=to_email,
                to_name=to_name,
                subject=rendered['subject'],
                html_body=html_body,
                from_email=from_email,
                from_name=from_name,
            )
        else:
            # Fall back to markdown-to-HTML conversion
            return self.send_email(
                to_email=to_email,
                to_name=to_name,
                subject=rendered['subject'],
                body=rendered['body'],
                from_email=from_email,
                from_name=from_name,
            )


# Singleton instance
email_service = EmailService()
