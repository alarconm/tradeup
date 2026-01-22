"""
Loyalty Page API Endpoints

API endpoints for the loyalty landing page builder.
Supports draft/publish workflow using the LoyaltyPage model.
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime

from app import db
from app.models.loyalty_page import LoyaltyPage, DEFAULT_PAGE_CONFIG
from app.middleware.shopify_auth import require_shopify_auth
from app.services.page_builder_service import PageBuilderService

loyalty_page_bp = Blueprint('loyalty_page', __name__)


def get_page() -> LoyaltyPage:
    """Get or create the loyalty page for the current tenant."""
    return LoyaltyPage.get_or_create(g.tenant.id, DEFAULT_PAGE_CONFIG)


@loyalty_page_bp.route('', methods=['GET'])
@require_shopify_auth
def get_page_config():
    """
    Get current page configuration.

    Returns both published and draft configs so the frontend can show
    the editing state and published state.
    """
    page = get_page()
    db.session.commit()  # Commit in case page was created

    return jsonify({
        'success': True,
        'page': page.to_dict(),
        'draft_config': page.get_draft_config(),
        'published_config': page.get_published_config(),
        'has_unsaved_changes': page.has_unsaved_changes(),
    })


@loyalty_page_bp.route('', methods=['PUT'])
@require_shopify_auth
def save_page_config():
    """
    Save page configuration as draft.

    This saves the configuration without publishing it.
    The draft can be previewed before publishing.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    page = get_page()

    # Update the draft configuration
    page.update_draft(data)
    db.session.commit()

    return jsonify({
        'success': True,
        'page': page.to_dict(),
        'draft_config': page.get_draft_config(),
        'has_unsaved_changes': page.has_unsaved_changes(),
    })


@loyalty_page_bp.route('/publish', methods=['POST'])
@require_shopify_auth
def publish_page():
    """
    Publish the current draft.

    Moves the draft configuration to the published configuration
    and makes the page live at the app proxy URL.
    """
    page = get_page()

    # Check if there's a draft to publish
    draft = page.get_draft_config()
    if not draft:
        return jsonify({
            'error': 'No draft configuration to publish'
        }), 400

    # Publish the page
    page.publish()
    db.session.commit()

    return jsonify({
        'success': True,
        'page': page.to_dict(),
        'published_config': page.get_published_config(),
        'message': 'Page published successfully',
    })


@loyalty_page_bp.route('/unpublish', methods=['POST'])
@require_shopify_auth
def unpublish_page():
    """
    Unpublish the page.

    The page configuration is retained but the public page
    will no longer be accessible.
    """
    page = get_page()

    if not page.is_published:
        return jsonify({
            'error': 'Page is not currently published'
        }), 400

    # Unpublish the page
    page.unpublish()
    db.session.commit()

    return jsonify({
        'success': True,
        'page': page.to_dict(),
        'message': 'Page unpublished successfully',
    })


@loyalty_page_bp.route('/preview', methods=['GET'])
@require_shopify_auth
def preview_page():
    """
    Preview the page with the latest draft configuration.

    Returns HTML that can be rendered in an iframe for preview.
    Uses the draft config if available, otherwise the published config.
    """
    page = get_page()
    db.session.commit()  # Commit in case page was created

    # Get the draft config for preview (or published if no draft)
    config = page.get_draft_config()

    if not config:
        return jsonify({
            'error': 'No page configuration found'
        }), 404

    # Use the page builder service to render HTML
    settings = g.tenant.settings or {}
    service = PageBuilderService(g.tenant.id, settings)

    # Temporarily override the service config with our page config
    # to render the correct preview
    html = _render_page_html(config)

    return html, 200, {'Content-Type': 'text/html'}


@loyalty_page_bp.route('/discard-draft', methods=['POST'])
@require_shopify_auth
def discard_draft():
    """
    Discard the current draft and revert to published version.
    """
    page = get_page()

    if not page.has_unsaved_changes():
        return jsonify({
            'error': 'No draft changes to discard'
        }), 400

    page.discard_draft()
    db.session.commit()

    return jsonify({
        'success': True,
        'page': page.to_dict(),
        'message': 'Draft discarded successfully',
    })


def _render_page_html(config: dict) -> str:
    """
    Render the loyalty page as HTML from the given configuration.

    Args:
        config: Page configuration dictionary

    Returns:
        HTML string
    """
    from app.services.page_builder_service import TEMPLATES

    if not config.get('sections'):
        config = DEFAULT_PAGE_CONFIG.copy()

    # Get active sections
    active_sections = [s for s in config.get('sections', []) if s.get('enabled', False)]
    active_sections.sort(key=lambda s: s.get('order', 999))

    colors = config.get('colors', TEMPLATES.get('minimal', {}).get('colors', {}))
    meta = config.get('meta', {})

    # Build HTML
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        f'<title>{meta.get("title", "Rewards Program")}</title>',
        f'<meta name="description" content="{meta.get("description", "")}">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<style>',
        ':root {',
        f'  --color-primary: {colors.get("primary", "#e85d27")};',
        f'  --color-secondary: {colors.get("secondary", "#666")};',
        f'  --color-accent: {colors.get("accent", "#ffd700")};',
        f'  --color-background: {colors.get("background", "#fff")};',
        '}',
        'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; background: var(--color-background); }',
        '.hero { padding: 80px 20px; text-align: center; background: var(--color-primary); color: white; }',
        '.hero h1 { font-size: 2.5rem; margin-bottom: 10px; }',
        '.hero p { font-size: 1.2rem; margin-bottom: 30px; opacity: 0.9; }',
        '.section { padding: 60px 20px; max-width: 1200px; margin: 0 auto; }',
        '.section-title { font-size: 2rem; margin-bottom: 30px; text-align: center; color: var(--color-primary); }',
        '.steps { display: flex; justify-content: center; gap: 40px; flex-wrap: wrap; }',
        '.step { text-align: center; max-width: 200px; }',
        '.step h3 { color: var(--color-primary); }',
        '.cta-button { display: inline-block; padding: 15px 30px; background: white; color: var(--color-primary); text-decoration: none; border-radius: 4px; font-weight: bold; transition: transform 0.2s; }',
        '.cta-button:hover { transform: translateY(-2px); }',
        '.faq-item { margin-bottom: 20px; padding: 20px; background: #f8f9fa; border-radius: 8px; }',
        '.faq-item strong { color: var(--color-primary); }',
        '.tier-card { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 30px; text-align: center; }',
        '.rewards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }',
        '.reward-card { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; text-align: center; }',
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
            <div class="hero" style="background-color: {settings.get("background_color", "var(--color-primary)")}; color: {settings.get("text_color", "#ffffff")};">
                <h1>{settings.get("title", "Join Our Rewards Program")}</h1>
                <p>{settings.get("subtitle", "Earn points on every purchase")}</p>
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
                <div style="text-align: center; color: #666;">
                    <p>Tier comparison will display your configured tiers when live.</p>
                </div>
            </div>
            ''')

        elif section_type == 'rewards_catalog':
            html_parts.append(f'''
            <div class="section">
                <h2 class="section-title">{settings.get("title", "Available Rewards")}</h2>
                <div style="text-align: center; color: #666;">
                    <p>Rewards catalog will display your configured rewards when live.</p>
                </div>
            </div>
            ''')

        elif section_type == 'earning_rules':
            html_parts.append(f'''
            <div class="section">
                <h2 class="section-title">{settings.get("title", "Ways to Earn")}</h2>
                <div style="text-align: center; color: #666;">
                    <p>Earning rules will display your configured points rules when live.</p>
                </div>
            </div>
            ''')

        elif section_type == 'faq':
            faq_html = ''
            for item in settings.get('items', []):
                faq_html += f'<div class="faq-item"><strong>{item.get("question", "")}</strong><p>{item.get("answer", "")}</p></div>'
            html_parts.append(f'''
            <div class="section">
                <h2 class="section-title">{settings.get("title", "FAQ")}</h2>
                {faq_html}
            </div>
            ''')

        elif section_type == 'referral_banner':
            html_parts.append(f'''
            <div class="section" style="background: linear-gradient(135deg, var(--color-primary), var(--color-accent)); border-radius: 12px; color: white; text-align: center;">
                <h2 style="color: white;">{settings.get("title", "Refer Friends & Earn")}</h2>
                <p>{settings.get("description", "Share with friends and earn rewards")}</p>
            </div>
            ''')

    html_parts.extend([
        '</body>',
        '</html>',
    ])

    return '\n'.join(html_parts)
