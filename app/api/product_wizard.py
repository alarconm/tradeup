"""
Membership Product Setup Wizard API.

Guides merchants through creating purchasable tier products in Shopify.
Supports draft/active status, auto-save, and resume functionality.
"""

from datetime import datetime
from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm.attributes import flag_modified

from ..extensions import db
from ..models import Tenant, MembershipTier
from ..middleware.shopify_auth import require_shopify_auth
from ..services.product_templates import (
    get_template_list,
    get_template,
    generate_product_drafts,
    validate_product_draft,
)

product_wizard_bp = Blueprint('product_wizard', __name__)


# ==================== Wizard Status ====================

@product_wizard_bp.route('/status', methods=['GET'])
@require_shopify_auth
def get_wizard_status():
    """
    Get current wizard state.

    Returns information about:
    - Whether there's a draft in progress
    - Current step in the wizard
    - Whether products have been created
    - Whether products are in draft mode
    """
    tenant = g.tenant
    settings = tenant.settings or {}

    wizard_state = settings.get('product_wizard', {})
    products_state = settings.get('membership_products', {})

    # Get tier count for context
    tier_count = MembershipTier.query.filter_by(
        tenant_id=g.tenant_id,
        is_active=True
    ).count()

    return jsonify({
        'success': True,
        'has_tiers': tier_count > 0,
        'tier_count': tier_count,
        'has_draft': wizard_state.get('draft_in_progress', False),
        'draft_step': wizard_state.get('draft_step', 1),
        'draft_template': wizard_state.get('draft_template'),
        'last_saved_at': wizard_state.get('last_saved_at'),
        'has_products': bool(products_state.get('products')),
        'products_count': len(products_state.get('products', [])),
        'products_are_draft': products_state.get('draft_mode', False),
        'products_created_at': products_state.get('created_at'),
    })


# ==================== Templates ====================

@product_wizard_bp.route('/templates', methods=['GET'])
@require_shopify_auth
def get_templates():
    """
    Get available product templates.

    Returns list of templates with preview images and descriptions.
    """
    templates = get_template_list()

    return jsonify({
        'success': True,
        'templates': templates,
    })


@product_wizard_bp.route('/templates/<template_id>/preview', methods=['GET'])
@require_shopify_auth
def preview_template(template_id: str):
    """
    Preview what products would look like with a given template.

    Generates product drafts based on current tiers and selected template.
    """
    template = get_template(template_id)
    if not template:
        return jsonify({
            'success': False,
            'error': f'Template "{template_id}" not found'
        }), 404

    # Get current tiers
    tiers = MembershipTier.query.filter_by(
        tenant_id=g.tenant_id,
        is_active=True
    ).order_by(MembershipTier.display_order).all()

    if not tiers:
        return jsonify({
            'success': False,
            'error': 'No active tiers found. Create tiers first.'
        }), 400

    # Convert tiers to dicts for template processing
    tier_dicts = [tier.to_dict() for tier in tiers]

    # Generate product drafts
    products = generate_product_drafts(template_id, tier_dicts)

    return jsonify({
        'success': True,
        'template': {
            'id': template['id'],
            'name': template['name'],
            'description': template['description'],
            'preview_image': template['preview_image'],
        },
        'products': products,
    })


# ==================== Draft Management ====================

@product_wizard_bp.route('/save', methods=['POST'])
@require_shopify_auth
def save_progress():
    """
    Save wizard draft progress.

    Allows users to leave and resume later.
    """
    tenant = g.tenant
    data = request.json or {}

    settings = tenant.settings or {}
    settings['product_wizard'] = {
        'draft_in_progress': True,
        'draft_step': data.get('step', 1),
        'draft_template': data.get('template'),
        'draft_products': data.get('products', []),
        'publish_as_active': data.get('publish_as_active', False),
        'last_saved_at': datetime.utcnow().isoformat(),
    }

    tenant.settings = settings
    flag_modified(tenant, 'settings')
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Progress saved',
        'last_saved_at': settings['product_wizard']['last_saved_at'],
    })


@product_wizard_bp.route('/draft', methods=['GET'])
@require_shopify_auth
def get_draft():
    """
    Get saved draft data to resume wizard.
    """
    tenant = g.tenant
    settings = tenant.settings or {}
    wizard_state = settings.get('product_wizard', {})

    if not wizard_state.get('draft_in_progress'):
        return jsonify({
            'success': True,
            'has_draft': False,
        })

    return jsonify({
        'success': True,
        'has_draft': True,
        'step': wizard_state.get('draft_step', 1),
        'template': wizard_state.get('draft_template'),
        'products': wizard_state.get('draft_products', []),
        'publish_as_active': wizard_state.get('publish_as_active', False),
        'last_saved_at': wizard_state.get('last_saved_at'),
    })


@product_wizard_bp.route('/reset', methods=['DELETE'])
@require_shopify_auth
def reset_wizard():
    """
    Discard draft and reset wizard state.
    """
    tenant = g.tenant
    settings = tenant.settings or {}

    if 'product_wizard' in settings:
        del settings['product_wizard']
        tenant.settings = settings
        flag_modified(tenant, 'settings')
        db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Wizard reset successfully',
    })


# ==================== Product Creation ====================

@product_wizard_bp.route('/create', methods=['POST'])
@require_shopify_auth
def create_products():
    """
    Create membership products from wizard configuration.

    Request body:
        products: List of product definitions
        publish_as_active: bool (default False = create as draft)
    """
    tenant = g.tenant
    data = request.json or {}

    products_config = data.get('products', [])
    publish_active = data.get('publish_as_active', False)

    if not products_config:
        return jsonify({
            'success': False,
            'error': 'No products provided'
        }), 400

    # Validate all products first
    all_errors = []
    for i, config in enumerate(products_config):
        errors = validate_product_draft(config)
        if errors:
            all_errors.append({
                'product': config.get('tier_name', f'Product {i+1}'),
                'errors': errors
            })

    if all_errors:
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'validation_errors': all_errors
        }), 400

    # Create products in Shopify
    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(g.tenant_id)

        status = 'ACTIVE' if publish_active else 'DRAFT'
        results = []
        errors = []

        for config in products_config:
            try:
                tier_name = config.get('tier_name', 'Member')
                tier_slug = config.get('tier_slug', tier_name.lower().replace(' ', '-'))

                # Build variants
                variants = [{
                    'title': 'Monthly',
                    'price': str(config['monthly_price']),
                    'sku': f"TU-{tier_slug.upper()}-MONTHLY",
                }]

                if config.get('yearly_price'):
                    variants.append({
                        'title': 'Yearly',
                        'price': str(config['yearly_price']),
                        'sku': f"TU-{tier_slug.upper()}-YEARLY",
                    })

                # Create/update product
                result = client.product_set(
                    title=config['title'],
                    body_html=config['description'],
                    vendor=tenant.shop_name or 'TradeUp',
                    product_type='Membership',
                    tags=['tradeup-membership', f'tier-{tier_slug}', 'membership'],
                    variants=variants,
                    status=status,
                )

                # Add image if provided
                image_url = config.get('image_url')
                if image_url and not image_url.startswith('/product-templates'):
                    # Custom image - would need to upload
                    # For now, skip template images (they're placeholders)
                    pass

                results.append({
                    'tier_id': config.get('tier_id'),
                    'tier_name': tier_name,
                    'product_id': result.get('id'),
                    'handle': result.get('handle'),
                    'status': status,
                    'action': result.get('action', 'created'),
                })

            except Exception as e:
                import traceback
                traceback.print_exc()
                errors.append({
                    'tier': config.get('tier_name', 'Unknown'),
                    'error': str(e)
                })

        # Save state to tenant settings
        settings = tenant.settings or {}
        settings['membership_products'] = {
            'created_at': datetime.utcnow().isoformat(),
            'products': results,
            'draft_mode': not publish_active,
        }

        # Clear wizard draft
        if 'product_wizard' in settings:
            del settings['product_wizard']

        tenant.settings = settings
        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': len(errors) == 0,
            'products': results,
            'errors': errors,
            'draft_mode': not publish_active,
            'message': f'Created {len(results)} products' + (' as drafts' if not publish_active else ''),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Failed to create products: {str(e)}'
        }), 500


# ==================== Publish ====================

@product_wizard_bp.route('/publish', methods=['POST'])
@require_shopify_auth
def publish_products():
    """
    Publish draft products (change status from DRAFT to ACTIVE).
    """
    tenant = g.tenant
    settings = tenant.settings or {}
    products_state = settings.get('membership_products', {})

    if not products_state.get('products'):
        return jsonify({
            'success': False,
            'error': 'No products found to publish'
        }), 400

    if not products_state.get('draft_mode'):
        return jsonify({
            'success': False,
            'error': 'Products are already active'
        }), 400

    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(g.tenant_id)

        results = []
        errors = []

        for product_info in products_state['products']:
            product_id = product_info.get('product_id')
            if not product_id:
                continue

            try:
                # Update product status to ACTIVE
                result = client.update_product_status(product_id, 'ACTIVE')
                results.append({
                    'product_id': product_id,
                    'tier_name': product_info.get('tier_name'),
                    'status': 'ACTIVE',
                })
            except Exception as e:
                errors.append({
                    'product_id': product_id,
                    'tier_name': product_info.get('tier_name'),
                    'error': str(e)
                })

        # Update settings
        products_state['draft_mode'] = False
        products_state['published_at'] = datetime.utcnow().isoformat()
        settings['membership_products'] = products_state

        tenant.settings = settings
        flag_modified(tenant, 'settings')
        db.session.commit()

        return jsonify({
            'success': len(errors) == 0,
            'products': results,
            'errors': errors,
            'message': f'Published {len(results)} products',
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Failed to publish products: {str(e)}'
        }), 500


# ==================== Existing Products ====================

@product_wizard_bp.route('/products', methods=['GET'])
@require_shopify_auth
def get_existing_products():
    """
    Get existing membership products from Shopify.
    """
    try:
        from ..services.shopify_client import ShopifyClient
        client = ShopifyClient(g.tenant_id)

        products = client.get_products_by_tag('tradeup-membership')

        return jsonify({
            'success': True,
            'products': products,
            'count': len(products),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
