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

# Pre-built templates
TEMPLATES = {
    'minimal': {
        'name': 'Minimal',
        'description': 'Clean, simple design focused on essentials',
        'sections': ['hero', 'how_it_works', 'tiers'],
        'colors': {
            'primary': '#000000',
            'secondary': '#666666',
            'accent': '#e85d27',
            'background': '#ffffff',
        }
    },
    'bold': {
        'name': 'Bold',
        'description': 'Vibrant colors and large typography',
        'sections': ['hero', 'how_it_works', 'rewards', 'earning_rules', 'referrals'],
        'colors': {
            'primary': '#e85d27',
            'secondary': '#ff7a50',
            'accent': '#ffd700',
            'background': '#1a1a2e',
        }
    },
    'elegant': {
        'name': 'Elegant',
        'description': 'Sophisticated design with premium feel',
        'sections': ['hero', 'tiers', 'rewards', 'faq'],
        'colors': {
            'primary': '#2c3e50',
            'secondary': '#34495e',
            'accent': '#d4af37',
            'background': '#f8f9fa',
        }
    },
    'playful': {
        'name': 'Playful',
        'description': 'Fun, colorful design for collectibles',
        'sections': ['hero', 'how_it_works', 'rewards', 'earning_rules', 'referrals', 'faq'],
        'colors': {
            'primary': '#6366f1',
            'secondary': '#a855f7',
            'accent': '#22d3ee',
            'background': '#faf5ff',
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
        """Apply a pre-built template."""
        if template_name not in TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}")

        template = TEMPLATES[template_name]

        # Create section config based on template
        sections = []
        for section in DEFAULT_SECTIONS:
            section_copy = section.copy()
            section_copy['enabled'] = section['id'] in template['sections']
            sections.append(section_copy)

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
        """Get list of available templates."""
        return [
            {
                'id': key,
                'name': val['name'],
                'description': val['description'],
                'colors': val['colors'],
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
