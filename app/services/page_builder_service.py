"""
Loyalty Page Builder Service

Manages customizable loyalty landing page configuration.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from app import db


# Default page sections that can be enabled/disabled
DEFAULT_SECTIONS = [
    {
        'id': 'hero',
        'type': 'hero',
        'enabled': True,
        'order': 0,
        'settings': {
            'title': 'Join Our Rewards Program',
            'subtitle': 'Earn points on every purchase and unlock exclusive rewards',
            'cta_text': 'Join Now',
            'cta_link': '/account/register',
            'background_type': 'gradient',  # gradient, image, solid
            'background_color': '#e85d27',
            'text_color': '#ffffff',
        }
    },
    {
        'id': 'how_it_works',
        'type': 'how_it_works',
        'enabled': True,
        'order': 1,
        'settings': {
            'title': 'How It Works',
            'steps': [
                {'icon': 'star', 'title': 'Sign Up', 'description': 'Create your free account'},
                {'icon': 'shopping-cart', 'title': 'Shop & Earn', 'description': 'Earn points on every purchase'},
                {'icon': 'gift', 'title': 'Redeem', 'description': 'Use points for rewards and discounts'},
            ]
        }
    },
    {
        'id': 'tiers',
        'type': 'tier_comparison',
        'enabled': True,
        'order': 2,
        'settings': {
            'title': 'Membership Tiers',
            'show_benefits': True,
            'show_prices': True,
            'highlight_tier': None,  # tier_id to highlight
        }
    },
    {
        'id': 'rewards',
        'type': 'rewards_catalog',
        'enabled': True,
        'order': 3,
        'settings': {
            'title': 'Available Rewards',
            'show_points_cost': True,
            'max_items': 6,
        }
    },
    {
        'id': 'earning_rules',
        'type': 'earning_rules',
        'enabled': True,
        'order': 4,
        'settings': {
            'title': 'Ways to Earn',
            'show_points_values': True,
        }
    },
    {
        'id': 'faq',
        'type': 'faq',
        'enabled': False,
        'order': 5,
        'settings': {
            'title': 'Frequently Asked Questions',
            'items': [
                {'question': 'How do I earn points?', 'answer': 'Earn points on every purchase. The more you shop, the more you earn!'},
                {'question': 'How do I redeem rewards?', 'answer': 'Use your points at checkout or in your account dashboard.'},
                {'question': 'Do points expire?', 'answer': 'Points expire after 12 months of account inactivity.'},
            ]
        }
    },
    {
        'id': 'referrals',
        'type': 'referral_banner',
        'enabled': True,
        'order': 6,
        'settings': {
            'title': 'Refer Friends & Earn',
            'description': 'Give $10, Get $10 for every friend you refer',
            'show_code_input': True,
        }
    },
]

# Pre-built templates - stored as JSON configs
# Each template includes all section types with appropriate enabled states
TEMPLATES = {
    'classic': {
        'name': 'Classic',
        'description': 'Traditional loyalty page layout with all essential sections',
        'preview_image': '/static/templates/classic-preview.png',
        'sections': ['hero', 'how_it_works', 'tiers', 'rewards', 'earning_rules', 'faq', 'referrals'],
        'section_settings': {
            'hero': {
                'title': 'Welcome to Our Rewards Program',
                'subtitle': 'Join thousands of loyal customers earning points on every purchase',
                'cta_text': 'Join Now - It\'s Free!',
                'cta_link': '/account/register',
                'background_type': 'solid',
                'background_color': '#1a365d',
                'text_color': '#ffffff',
            },
            'how_it_works': {
                'title': 'How Our Program Works',
                'steps': [
                    {'icon': 'user-plus', 'title': 'Sign Up', 'description': 'Create your free rewards account in seconds'},
                    {'icon': 'shopping-bag', 'title': 'Shop & Earn', 'description': 'Earn 1 point for every dollar you spend'},
                    {'icon': 'arrow-up-circle', 'title': 'Level Up', 'description': 'Unlock higher tiers for more benefits'},
                    {'icon': 'gift', 'title': 'Redeem Rewards', 'description': 'Use your points for discounts and perks'},
                ]
            },
            'tiers': {
                'title': 'Membership Tiers',
                'show_benefits': True,
                'show_prices': True,
                'highlight_tier': None,
            },
            'rewards': {
                'title': 'Rewards Catalog',
                'show_points_cost': True,
                'max_items': 6,
            },
            'earning_rules': {
                'title': 'Ways to Earn Points',
                'show_points_values': True,
            },
            'faq': {
                'title': 'Frequently Asked Questions',
                'items': [
                    {'question': 'How do I join the rewards program?', 'answer': 'Simply create an account during checkout or visit our rewards page to sign up. It\'s completely free!'},
                    {'question': 'How do I earn points?', 'answer': 'Earn points on every purchase. The more you spend, the more points you earn. Higher tier members earn bonus points!'},
                    {'question': 'How do I redeem my points?', 'answer': 'Use your points at checkout for instant discounts, or browse our rewards catalog for exclusive perks.'},
                    {'question': 'Do my points expire?', 'answer': 'Points remain active as long as you make at least one purchase every 12 months.'},
                ]
            },
            'referrals': {
                'title': 'Refer Friends & Earn Bonus Points',
                'description': 'Share your unique referral link. You and your friend both earn 500 bonus points when they make their first purchase!',
                'show_code_input': True,
            },
        },
        'colors': {
            'primary': '#1a365d',
            'secondary': '#2d4a6f',
            'accent': '#e85d27',
            'background': '#ffffff',
        }
    },
    'modern': {
        'name': 'Modern',
        'description': 'Clean, minimal design with contemporary aesthetics',
        'preview_image': '/static/templates/modern-preview.png',
        'sections': ['hero', 'how_it_works', 'tiers', 'rewards', 'earning_rules', 'faq', 'referrals'],
        'section_settings': {
            'hero': {
                'title': 'Earn While You Shop',
                'subtitle': 'Simple. Rewarding. Worth it.',
                'cta_text': 'Get Started',
                'cta_link': '/account/register',
                'background_type': 'gradient',
                'background_color': '#000000',
                'text_color': '#ffffff',
            },
            'how_it_works': {
                'title': 'Three Simple Steps',
                'steps': [
                    {'icon': 'check-circle', 'title': 'Join', 'description': 'Free to sign up'},
                    {'icon': 'coins', 'title': 'Earn', 'description': 'Points on every order'},
                    {'icon': 'sparkles', 'title': 'Enjoy', 'description': 'Exclusive rewards'},
                ]
            },
            'tiers': {
                'title': 'Member Levels',
                'show_benefits': True,
                'show_prices': False,
                'highlight_tier': None,
            },
            'rewards': {
                'title': 'Your Rewards',
                'show_points_cost': True,
                'max_items': 4,
            },
            'earning_rules': {
                'title': 'Earn More',
                'show_points_values': True,
            },
            'faq': {
                'title': 'Questions?',
                'items': [
                    {'question': 'Is it free to join?', 'answer': 'Yes, always free. No hidden fees.'},
                    {'question': 'How fast do I earn?', 'answer': 'Instantly. Points added after each purchase.'},
                    {'question': 'Can I combine with other offers?', 'answer': 'Yes! Rewards work with most promotions.'},
                ]
            },
            'referrals': {
                'title': 'Share the Love',
                'description': 'Invite friends. Both of you earn rewards.',
                'show_code_input': True,
            },
        },
        'colors': {
            'primary': '#000000',
            'secondary': '#4a4a4a',
            'accent': '#0066ff',
            'background': '#fafafa',
        }
    },
    'gamified': {
        'name': 'Gamified',
        'description': 'Badges and achievements focused with engaging visuals',
        'preview_image': '/static/templates/gamified-preview.png',
        'sections': ['hero', 'how_it_works', 'tiers', 'rewards', 'earning_rules', 'faq', 'referrals'],
        'section_settings': {
            'hero': {
                'title': 'Level Up Your Shopping!',
                'subtitle': 'Earn XP, unlock achievements, and claim epic rewards',
                'cta_text': 'Start Your Adventure',
                'cta_link': '/account/register',
                'background_type': 'gradient',
                'background_color': '#6366f1',
                'text_color': '#ffffff',
            },
            'how_it_works': {
                'title': 'Your Quest Begins',
                'steps': [
                    {'icon': 'trophy', 'title': 'Create Profile', 'description': 'Set up your player account'},
                    {'icon': 'zap', 'title': 'Earn XP', 'description': 'Gain experience with every purchase'},
                    {'icon': 'award', 'title': 'Unlock Badges', 'description': 'Complete challenges for achievements'},
                    {'icon': 'star', 'title': 'Claim Rewards', 'description': 'Redeem your points for loot'},
                ]
            },
            'tiers': {
                'title': 'Player Ranks',
                'show_benefits': True,
                'show_prices': True,
                'highlight_tier': None,
            },
            'rewards': {
                'title': 'Reward Shop',
                'show_points_cost': True,
                'max_items': 8,
            },
            'earning_rules': {
                'title': 'XP Multipliers',
                'show_points_values': True,
            },
            'faq': {
                'title': 'Player Guide',
                'items': [
                    {'question': 'How do I level up?', 'answer': 'Earn XP through purchases and completing challenges. Each level unlocks new rewards and benefits!'},
                    {'question': 'What are achievements?', 'answer': 'Special badges you unlock by reaching milestones. Collect them all for bonus rewards!'},
                    {'question': 'Do I keep my progress?', 'answer': 'Your XP and achievements are saved forever. Keep climbing the leaderboard!'},
                    {'question': 'Are there limited-time events?', 'answer': 'Yes! Watch for special events with double XP and exclusive rewards.'},
                ]
            },
            'referrals': {
                'title': 'Recruit Your Squad',
                'description': 'Invite friends and both earn a 1000 XP bonus when they join the adventure!',
                'show_code_input': True,
            },
        },
        'colors': {
            'primary': '#6366f1',
            'secondary': '#8b5cf6',
            'accent': '#fbbf24',
            'background': '#0f0f23',
        }
    },
}


class PageBuilderService:
    """Service for managing loyalty page configuration."""

    def __init__(self, tenant_id: int, settings: Optional[Dict] = None):
        self.tenant_id = tenant_id
        self.settings = settings or {}

    def get_page_config(self) -> Dict[str, Any]:
        """Get the current page configuration."""
        page_config = self.settings.get('loyalty_page', {})

        if not page_config:
            # Return default config
            return {
                'enabled': True,
                'template': 'minimal',
                'sections': DEFAULT_SECTIONS.copy(),
                'colors': TEMPLATES['minimal']['colors'].copy(),
                'custom_css': '',
                'meta': {
                    'title': 'Rewards Program',
                    'description': 'Join our rewards program and earn points on every purchase',
                },
                'last_updated': None,
            }

        return page_config

    def update_page_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update the page configuration."""
        from sqlalchemy.orm.attributes import flag_modified
        from app.models.tenant import Tenant

        tenant = Tenant.query.get(self.tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")

        if not tenant.settings:
            tenant.settings = {}

        # Merge with existing config
        current_config = tenant.settings.get('loyalty_page', {})
        current_config.update(config)
        current_config['last_updated'] = datetime.utcnow().isoformat()

        tenant.settings['loyalty_page'] = current_config
        flag_modified(tenant, 'settings')
        db.session.commit()

        return current_config

    def apply_template(self, template_name: str) -> Dict[str, Any]:
        """Apply a pre-built template with one-click functionality.

        Applies template colors, section configurations, and custom section
        settings to create a complete starting point for the loyalty page.
        """
        if template_name not in TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}")

        template = TEMPLATES[template_name]
        template_section_settings = template.get('section_settings', {})

        # Create section config based on template
        sections = []
        order = 0
        for section in DEFAULT_SECTIONS:
            section_copy = {
                'id': section['id'],
                'type': section['type'],
                'enabled': section['id'] in template['sections'],
                'order': order if section['id'] in template['sections'] else 999,
                'settings': section['settings'].copy(),
            }

            # Apply template-specific section settings if available
            if section['id'] in template_section_settings:
                section_copy['settings'] = template_section_settings[section['id']].copy()

            if section['id'] in template['sections']:
                order += 1

            sections.append(section_copy)

        # Sort sections by order
        sections.sort(key=lambda s: s['order'])

        config = {
            'template': template_name,
            'sections': sections,
            'colors': template['colors'].copy(),
        }

        return self.update_page_config(config)

    def update_section(self, section_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific section's settings."""
        config = self.get_page_config()

        for section in config.get('sections', []):
            if section['id'] == section_id:
                section['settings'].update(settings)
                break

        return self.update_page_config(config)

    def reorder_sections(self, section_order: List[str]) -> Dict[str, Any]:
        """Reorder sections based on provided list of section IDs."""
        config = self.get_page_config()

        # Create order map
        order_map = {sid: i for i, sid in enumerate(section_order)}

        for section in config.get('sections', []):
            if section['id'] in order_map:
                section['order'] = order_map[section['id']]

        # Sort sections
        config['sections'].sort(key=lambda s: s.get('order', 999))

        return self.update_page_config(config)

    def toggle_section(self, section_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a section."""
        config = self.get_page_config()

        for section in config.get('sections', []):
            if section['id'] == section_id:
                section['enabled'] = enabled
                break

        return self.update_page_config(config)

    def get_available_templates(self) -> List[Dict[str, Any]]:
        """Get list of available templates with preview info."""
        return [
            {
                'id': key,
                'name': val['name'],
                'description': val['description'],
                'colors': val['colors'],
                'preview_image': val.get('preview_image'),
                'sections': val['sections'],
            }
            for key, val in TEMPLATES.items()
        ]

    def render_page_html(self, customer_data: Optional[Dict] = None) -> str:
        """
        Render the loyalty page as HTML.
        This is used by the app proxy to serve the public page.
        """
        config = self.get_page_config()

        if not config.get('enabled', True):
            return '<html><body><h1>Rewards program page is not available.</h1></body></html>'

        # Get active sections
        active_sections = [s for s in config.get('sections', []) if s.get('enabled', False)]
        active_sections.sort(key=lambda s: s.get('order', 999))

        colors = config.get('colors', TEMPLATES['minimal']['colors'])
        meta = config.get('meta', {})

        # Build HTML (simplified version - in production, use templates)
        html_parts = [
            '<!DOCTYPE html>',
            '<html lang="en">',
            '<head>',
            f'<title>{meta.get("title", "Rewards")}</title>',
            f'<meta name="description" content="{meta.get("description", "")}">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            '<link rel="stylesheet" href="https://unpkg.com/@shopify/polaris@latest/build/esm/styles.css">',
            f'<style>',
            f':root {{',
            f'  --color-primary: {colors.get("primary", "#e85d27")};',
            f'  --color-secondary: {colors.get("secondary", "#666")};',
            f'  --color-accent: {colors.get("accent", "#ffd700")};',
            f'  --color-background: {colors.get("background", "#fff")};',
            f'}}',
            'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; background: var(--color-background); }',
            '.hero { padding: 80px 20px; text-align: center; background: var(--color-primary); color: white; }',
            '.section { padding: 60px 20px; max-width: 1200px; margin: 0 auto; }',
            '.section-title { font-size: 2rem; margin-bottom: 30px; text-align: center; }',
            '.steps { display: flex; justify-content: center; gap: 40px; flex-wrap: wrap; }',
            '.step { text-align: center; max-width: 200px; }',
            '.cta-button { display: inline-block; padding: 15px 30px; background: white; color: var(--color-primary); text-decoration: none; border-radius: 4px; font-weight: bold; }',
            config.get('custom_css', ''),
            '</style>',
            '</head>',
            '<body>',
        ]

        # Render sections
        for section in active_sections:
            section_type = section.get('type')
            settings = section.get('settings', {})

            if section_type == 'hero':
                html_parts.append(f'''
                <div class="hero">
                    <h1>{settings.get("title", "")}</h1>
                    <p>{settings.get("subtitle", "")}</p>
                    <a href="{settings.get("cta_link", "/account")}" class="cta-button">{settings.get("cta_text", "Join Now")}</a>
                </div>
                ''')

            elif section_type == 'how_it_works':
                steps_html = ''
                for step in settings.get('steps', []):
                    steps_html += f'<div class="step"><h3>{step.get("title", "")}</h3><p>{step.get("description", "")}</p></div>'
                html_parts.append(f'''
                <div class="section">
                    <h2 class="section-title">{settings.get("title", "How It Works")}</h2>
                    <div class="steps">{steps_html}</div>
                </div>
                ''')

            elif section_type == 'tier_comparison':
                html_parts.append(f'''
                <div class="section">
                    <h2 class="section-title">{settings.get("title", "Membership Tiers")}</h2>
                    <p style="text-align: center;">Tier comparison coming soon...</p>
                </div>
                ''')

            elif section_type == 'rewards_catalog':
                html_parts.append(f'''
                <div class="section">
                    <h2 class="section-title">{settings.get("title", "Available Rewards")}</h2>
                    <p style="text-align: center;">Rewards catalog coming soon...</p>
                </div>
                ''')

            elif section_type == 'faq':
                faq_html = ''
                for item in settings.get('items', []):
                    faq_html += f'<div style="margin-bottom: 20px;"><strong>{item.get("question", "")}</strong><p>{item.get("answer", "")}</p></div>'
                html_parts.append(f'''
                <div class="section">
                    <h2 class="section-title">{settings.get("title", "FAQ")}</h2>
                    {faq_html}
                </div>
                ''')

        html_parts.extend([
            '</body>',
            '</html>',
        ])

        return '\n'.join(html_parts)
