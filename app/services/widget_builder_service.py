"""
Widget Visual Builder Service

Manages customizable loyalty widget configuration for customer-facing display.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from app import db


# Default widget configuration
DEFAULT_WIDGET_CONFIG = {
    'enabled': True,
    'position': 'bottom-right',  # bottom-right, bottom-left, left-tab, right-tab
    'theme': 'default',

    # Appearance
    'appearance': {
        'primary_color': '#e85d27',
        'text_color': '#ffffff',
        'background_color': '#ffffff',
        'border_radius': 16,
        'shadow': True,
        'animation': 'slide',  # slide, fade, none
    },

    # Launcher button
    'launcher': {
        'icon': 'gift',  # gift, star, heart, trophy, custom
        'custom_icon_url': None,
        'text': 'Rewards',
        'show_points_badge': True,
        'size': 'medium',  # small, medium, large
    },

    # Panel content
    'panel': {
        'show_points_balance': True,
        'show_tier_progress': True,
        'show_available_rewards': True,
        'show_earning_rules': True,
        'show_referral_link': True,
        'max_rewards_shown': 4,
        'welcome_message': 'Welcome to our rewards program!',
        'guest_message': 'Join to earn points on every purchase',
    },

    # Branding
    'branding': {
        'show_logo': True,
        'logo_url': None,
        'program_name': 'Rewards',
        'powered_by': True,  # Show "Powered by TradeUp"
    },

    # Behavior
    'behavior': {
        'auto_open_for_new_members': True,
        'auto_open_delay_ms': 3000,
        'close_on_outside_click': True,
        'show_notifications': True,
    },

    # Display rules
    'display_rules': {
        'hide_on_mobile': False,
        'hide_on_pages': [],  # List of page paths to hide widget
        'show_only_for_members': False,
        'hide_during_checkout': True,
    },
}

# Pre-built widget themes
WIDGET_THEMES = {
    'default': {
        'name': 'Default',
        'description': 'Clean and modern',
        'appearance': {
            'primary_color': '#e85d27',
            'text_color': '#ffffff',
            'background_color': '#ffffff',
            'border_radius': 16,
        }
    },
    'dark': {
        'name': 'Dark Mode',
        'description': 'Sleek dark theme',
        'appearance': {
            'primary_color': '#6366f1',
            'text_color': '#ffffff',
            'background_color': '#1f2937',
            'border_radius': 12,
        }
    },
    'minimal': {
        'name': 'Minimal',
        'description': 'Simple and subtle',
        'appearance': {
            'primary_color': '#374151',
            'text_color': '#ffffff',
            'background_color': '#f9fafb',
            'border_radius': 8,
        }
    },
    'playful': {
        'name': 'Playful',
        'description': 'Fun and colorful',
        'appearance': {
            'primary_color': '#ec4899',
            'text_color': '#ffffff',
            'background_color': '#fdf2f8',
            'border_radius': 24,
        }
    },
    'luxury': {
        'name': 'Luxury',
        'description': 'Premium gold accents',
        'appearance': {
            'primary_color': '#d4af37',
            'text_color': '#1a1a1a',
            'background_color': '#fafafa',
            'border_radius': 4,
        }
    },
}


class WidgetBuilderService:
    """Service for managing widget configuration."""

    def __init__(self, tenant_id: int, settings: Optional[Dict] = None):
        self.tenant_id = tenant_id
        self.settings = settings or {}

    def get_widget_config(self) -> Dict[str, Any]:
        """Get the current widget configuration."""
        widget_config = self.settings.get('widget', {})

        if not widget_config:
            return DEFAULT_WIDGET_CONFIG.copy()

        # Merge with defaults for any missing keys
        merged = DEFAULT_WIDGET_CONFIG.copy()
        self._deep_merge(merged, widget_config)
        return merged

    def _deep_merge(self, base: dict, override: dict) -> None:
        """Deep merge override into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def update_widget_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update the widget configuration."""
        from sqlalchemy.orm.attributes import flag_modified
        from app.models.tenant import Tenant

        tenant = Tenant.query.get(self.tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")

        if not tenant.settings:
            tenant.settings = {}

        # Get current config and merge updates
        current_config = tenant.settings.get('widget', DEFAULT_WIDGET_CONFIG.copy())
        self._deep_merge(current_config, config)
        current_config['last_updated'] = datetime.utcnow().isoformat()

        tenant.settings['widget'] = current_config
        flag_modified(tenant, 'settings')
        db.session.commit()

        return current_config

    def apply_theme(self, theme_name: str) -> Dict[str, Any]:
        """Apply a pre-built theme."""
        if theme_name not in WIDGET_THEMES:
            raise ValueError(f"Unknown theme: {theme_name}")

        theme = WIDGET_THEMES[theme_name]

        config = {
            'theme': theme_name,
            'appearance': theme['appearance'].copy(),
        }

        return self.update_widget_config(config)

    def get_available_themes(self) -> list:
        """Get list of available themes."""
        return [
            {
                'id': key,
                'name': val['name'],
                'description': val['description'],
                'appearance': val['appearance'],
            }
            for key, val in WIDGET_THEMES.items()
        ]

    def get_widget_embed_code(self) -> str:
        """Generate the embed code for the widget."""
        config = self.get_widget_config()

        # Generate JavaScript snippet for widget initialization
        embed_code = f'''
<script>
  window.TradeUpWidget = {{
    config: {config},
    init: function() {{
      // Widget initialization code
      console.log('TradeUp Widget initialized');
    }}
  }};
</script>
<script src="https://cdn.tradeup.com/widget.js" async></script>
'''
        return embed_code

    def generate_css_variables(self) -> str:
        """Generate CSS custom properties for the widget."""
        config = self.get_widget_config()
        appearance = config.get('appearance', {})

        css = f'''
:root {{
  --tradeup-primary: {appearance.get('primary_color', '#e85d27')};
  --tradeup-text: {appearance.get('text_color', '#ffffff')};
  --tradeup-bg: {appearance.get('background_color', '#ffffff')};
  --tradeup-radius: {appearance.get('border_radius', 16)}px;
}}
'''
        return css
