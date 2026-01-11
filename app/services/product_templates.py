"""
Product Templates Service for TradeUp.

Provides pre-built templates for membership products with professional
placeholder images, descriptions, and pricing suggestions.

Templates are designed to work out-of-the-box while allowing full customization.
"""

from typing import Dict, List, Any, Optional
from decimal import Decimal


# Base URL for template images (served from frontend/public)
TEMPLATE_IMAGE_BASE = '/product-templates'

# Shopify CDN placeholder for missing images
PLACEHOLDER_IMAGE = 'https://cdn.shopify.com/s/files/1/0533/2089/files/placeholder-images-product-1_large.png'

# Color-coded placeholders for different tiers (using placehold.co)
TIER_PLACEHOLDER_COLORS = {
    'bronze': '#cd7f32',     # Bronze color
    'silver': '#c0c0c0',     # Silver color
    'gold': '#ffd700',       # Gold color
    'platinum': '#e5e4e2',   # Platinum color
    'diamond': '#b9f2ff',    # Diamond blue
    'member': '#5c6ac4',     # Polaris purple
    'vip': '#9c27b0',        # VIP purple
    'rookie': '#4caf50',     # Rookie green
    'allstar': '#ff9800',    # All-star orange
    'mvp': '#f44336',        # MVP red
    'collector': '#2196f3',  # Collector blue
    'champion': '#ff5722',   # Champion orange
    'legend': '#9c27b0',     # Legend purple
    'master': '#673ab7',     # Master deep purple
    'default': '#5c6ac4',    # Default Polaris purple
}


# ==================== Template Definitions ====================

PRODUCT_TEMPLATES = {
    'modern': {
        'id': 'modern',
        'name': 'Modern Minimal',
        'description': 'Clean, professional look with gradient accents. Perfect for any store.',
        'preview_image': 'https://placehold.co/800x600/5c6ac4/ffffff?text=Modern+Minimal',
        'style': 'gradient',
        'tier_images': {
            'bronze': f'{TEMPLATE_IMAGE_BASE}/modern/bronze.png',
            'silver': f'{TEMPLATE_IMAGE_BASE}/modern/silver.png',
            'gold': f'{TEMPLATE_IMAGE_BASE}/modern/gold.png',
            'platinum': f'{TEMPLATE_IMAGE_BASE}/modern/platinum.png',
            'diamond': f'{TEMPLATE_IMAGE_BASE}/modern/diamond.png',
            'member': f'{TEMPLATE_IMAGE_BASE}/modern/member.png',
            'vip': f'{TEMPLATE_IMAGE_BASE}/modern/vip.png',
            'default': f'{TEMPLATE_IMAGE_BASE}/modern/default.png',
        },
        'title_template': '{tier_name} Membership',
        'description_template': '''
<p><strong>Unlock exclusive benefits with {tier_name} membership!</strong></p>

<h4>Your Benefits:</h4>
<ul>
{benefits_list}
</ul>

<p>Join today and start earning rewards on every purchase and trade-in.</p>
''',
    },

    'sports': {
        'id': 'sports',
        'name': 'Sports Card Pro',
        'description': 'Designed for sports card and memorabilia collectors.',
        'preview_image': 'https://placehold.co/800x600/4caf50/ffffff?text=Sports+Card+Pro',
        'style': 'bold',
        'tier_images': {
            'rookie': f'{TEMPLATE_IMAGE_BASE}/sports/rookie.png',
            'all-star': f'{TEMPLATE_IMAGE_BASE}/sports/all-star.png',
            'allstar': f'{TEMPLATE_IMAGE_BASE}/sports/all-star.png',
            'mvp': f'{TEMPLATE_IMAGE_BASE}/sports/mvp.png',
            'hall-of-fame': f'{TEMPLATE_IMAGE_BASE}/sports/hall-of-fame.png',
            'bronze': f'{TEMPLATE_IMAGE_BASE}/sports/bronze.png',
            'silver': f'{TEMPLATE_IMAGE_BASE}/sports/silver.png',
            'gold': f'{TEMPLATE_IMAGE_BASE}/sports/gold.png',
            'default': f'{TEMPLATE_IMAGE_BASE}/sports/default.png',
        },
        'title_template': '{tier_name} Collector Membership',
        'description_template': '''
<p><strong>Level up your collecting game with {tier_name} status!</strong></p>

<h4>Collector Benefits:</h4>
<ul>
{benefits_list}
</ul>

<p>Whether you're hunting for rookies or chasing Hall of Famers, we've got you covered.</p>
''',
    },

    'tcg': {
        'id': 'tcg',
        'name': 'TCG Gaming',
        'description': 'Perfect for Pokemon, Magic: The Gathering, and trading card games.',
        'preview_image': 'https://placehold.co/800x600/2196f3/ffffff?text=TCG+Gaming',
        'style': 'playful',
        'tier_images': {
            'collector': f'{TEMPLATE_IMAGE_BASE}/tcg/collector.png',
            'champion': f'{TEMPLATE_IMAGE_BASE}/tcg/champion.png',
            'legend': f'{TEMPLATE_IMAGE_BASE}/tcg/legend.png',
            'master': f'{TEMPLATE_IMAGE_BASE}/tcg/master.png',
            'bronze': f'{TEMPLATE_IMAGE_BASE}/tcg/bronze.png',
            'silver': f'{TEMPLATE_IMAGE_BASE}/tcg/silver.png',
            'gold': f'{TEMPLATE_IMAGE_BASE}/tcg/gold.png',
            'platinum': f'{TEMPLATE_IMAGE_BASE}/tcg/platinum.png',
            'default': f'{TEMPLATE_IMAGE_BASE}/tcg/default.png',
        },
        'title_template': '{tier_name} Player Membership',
        'description_template': '''
<p><strong>Join the {tier_name} ranks and power up your collection!</strong></p>

<h4>Player Perks:</h4>
<ul>
{benefits_list}
</ul>

<p>From sealed product to singles, maximize your value on every trade and purchase.</p>
''',
    },

    'classic': {
        'id': 'classic',
        'name': 'Classic Tiers',
        'description': 'Traditional Gold, Silver, Bronze hierarchy. Works for any business.',
        'preview_image': 'https://placehold.co/800x600/ffd700/333333?text=Classic+Tiers',
        'style': 'elegant',
        'tier_images': {
            'bronze': f'{TEMPLATE_IMAGE_BASE}/classic/bronze.png',
            'silver': f'{TEMPLATE_IMAGE_BASE}/classic/silver.png',
            'gold': f'{TEMPLATE_IMAGE_BASE}/classic/gold.png',
            'platinum': f'{TEMPLATE_IMAGE_BASE}/classic/platinum.png',
            'diamond': f'{TEMPLATE_IMAGE_BASE}/classic/diamond.png',
            'default': f'{TEMPLATE_IMAGE_BASE}/classic/default.png',
        },
        'title_template': '{tier_name} Membership',
        'description_template': '''
<p><strong>Welcome to {tier_name} membership!</strong></p>

<h4>Member Benefits:</h4>
<ul>
{benefits_list}
</ul>

<p>Thank you for being a valued member of our community.</p>
''',
    },
}


# ==================== Helper Functions ====================

def get_template_list() -> List[Dict[str, Any]]:
    """
    Get list of available templates for the template selector.

    Returns simplified template info without full content.
    """
    templates = []
    for template_id, template in PRODUCT_TEMPLATES.items():
        templates.append({
            'id': template_id,
            'name': template['name'],
            'description': template['description'],
            'preview_image': template['preview_image'],
            'style': template['style'],
        })
    return templates


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific template by ID."""
    return PRODUCT_TEMPLATES.get(template_id)


def get_tier_image(template_id: str, tier_name: str) -> str:
    """
    Get the appropriate image URL for a tier within a template.

    Matches tier names case-insensitively and falls back to a
    dynamically generated placeholder image.
    """
    # Generate a placeholder image URL using placehold.co
    # This provides an immediate working image while local assets are developed
    tier_slug = tier_name.lower().replace(' ', '-').replace('_', '-')
    tier_simple = tier_name.lower().replace(' ', '').replace('-', '').replace('_', '')

    # Find the best matching color for this tier
    color = TIER_PLACEHOLDER_COLORS.get(tier_simple)
    if not color:
        color = TIER_PLACEHOLDER_COLORS.get(tier_slug)
    if not color:
        # Try partial matching
        for key, val in TIER_PLACEHOLDER_COLORS.items():
            if key in tier_simple or tier_simple in key:
                color = val
                break
    if not color:
        color = TIER_PLACEHOLDER_COLORS['default']

    # Remove # from color for URL
    color_hex = color.lstrip('#')

    # Use placehold.co to generate a placeholder with the tier name
    # Format: https://placehold.co/400x400/colorHex/white?text=TierName
    placeholder_url = f'https://placehold.co/600x600/{color_hex}/ffffff?text={tier_name.replace(" ", "+")}'

    return placeholder_url


def generate_product_title(template_id: str, tier_name: str) -> str:
    """Generate product title from template."""
    template = PRODUCT_TEMPLATES.get(template_id)
    if not template:
        return f'{tier_name} Membership'

    title_template = template.get('title_template', '{tier_name} Membership')
    return title_template.format(tier_name=tier_name)


def generate_product_description(
    template_id: str,
    tier_name: str,
    benefits: List[str],
    trade_in_bonus_pct: float = 0,
    cashback_pct: float = 0
) -> str:
    """
    Generate product description from template with tier benefits.

    Args:
        template_id: The template to use
        tier_name: Name of the tier
        benefits: List of benefit strings
        trade_in_bonus_pct: Trade-in bonus percentage (e.g., 5 for 5%)
        cashback_pct: Purchase cashback percentage (e.g., 2 for 2%)
    """
    template = PRODUCT_TEMPLATES.get(template_id)
    if not template:
        template = PRODUCT_TEMPLATES['modern']

    # Build benefits list
    all_benefits = list(benefits) if benefits else []

    # Add standard benefits based on percentages
    if trade_in_bonus_pct > 0:
        all_benefits.insert(0, f'{trade_in_bonus_pct:.0f}% bonus on all trade-ins')
    if cashback_pct > 0:
        all_benefits.insert(0, f'{cashback_pct:.0f}% cashback on purchases')

    # Generate HTML list
    if all_benefits:
        benefits_html = '\n'.join(f'<li>{benefit}</li>' for benefit in all_benefits)
    else:
        benefits_html = '<li>Exclusive member benefits</li>'

    # Apply template
    description_template = template.get('description_template', '<p>{tier_name} Membership</p>')
    description = description_template.format(
        tier_name=tier_name,
        benefits_list=benefits_html
    )

    return description.strip()


def generate_product_drafts(
    template_id: str,
    tiers: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Generate product draft configurations from a template and tier list.

    Args:
        template_id: Template to use for styling
        tiers: List of tier dicts with id, name, monthly_price, yearly_price,
               bonus_rate, purchase_cashback_pct, benefits

    Returns:
        List of product draft configurations ready for the wizard
    """
    products = []

    for tier in tiers:
        tier_name = tier.get('name', 'Member')
        tier_slug = tier_name.lower().replace(' ', '-')

        # Calculate percentages from decimal rates
        trade_in_bonus_pct = float(tier.get('bonus_rate', 0)) * 100
        cashback_pct = float(tier.get('purchase_cashback_pct', 0))

        # Get benefits from tier or empty list
        tier_benefits = tier.get('benefits', {})
        if isinstance(tier_benefits, dict):
            benefits = tier_benefits.get('features', [])
        elif isinstance(tier_benefits, list):
            benefits = tier_benefits
        else:
            benefits = []

        product = {
            'tier_id': tier.get('id'),
            'tier_name': tier_name,
            'tier_slug': tier_slug,
            'title': generate_product_title(template_id, tier_name),
            'description': generate_product_description(
                template_id,
                tier_name,
                benefits,
                trade_in_bonus_pct,
                cashback_pct
            ),
            'image_url': get_tier_image(template_id, tier_name),
            'image_source': 'template',
            'monthly_price': float(tier.get('monthly_price', 0)),
            'yearly_price': float(tier.get('yearly_price')) if tier.get('yearly_price') else None,
            'customized': False,
        }

        products.append(product)

    return products


# ==================== Validation ====================

def validate_product_draft(draft: Dict[str, Any]) -> List[str]:
    """
    Validate a product draft configuration.

    Returns list of error messages (empty if valid).
    """
    errors = []

    if not draft.get('title'):
        errors.append('Product title is required')
    elif len(draft['title']) > 255:
        errors.append('Product title must be 255 characters or less')

    if not draft.get('description'):
        errors.append('Product description is required')

    monthly_price = draft.get('monthly_price')
    if monthly_price is None or monthly_price < 0:
        errors.append('Monthly price must be 0 or greater')

    yearly_price = draft.get('yearly_price')
    if yearly_price is not None and yearly_price < 0:
        errors.append('Yearly price must be 0 or greater')

    return errors
