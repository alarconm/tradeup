"""
Shopify Data API endpoints.

Provides access to Shopify store data for use in promotion configuration:
- Collections (for filtering promotions by collection)
- Vendors (for filtering by brand/vendor)
- Product types
- Product tags
"""
from flask import Blueprint, request, jsonify, g
from ..services.shopify_client import ShopifyClient
from ..middleware.shop_auth import require_shop_auth

shopify_data_bp = Blueprint('shopify_data', __name__)


def get_shopify_client_for_tenant():
    """Create Shopify client for the current tenant."""
    tenant_id = g.tenant_id
    return ShopifyClient(tenant_id)


@shopify_data_bp.route('/collections', methods=['GET'])
@require_shop_auth
def list_collections():
    """
    List all Shopify collections.

    Returns:
        List of collections with id, title, handle
    """
    client = get_shopify_client_for_tenant()
    if not client:
        return jsonify({'error': 'Shopify not configured'}), 500

    try:
        collections = client.get_collections()
        return jsonify({
            'collections': collections,
            'count': len(collections)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@shopify_data_bp.route('/vendors', methods=['GET'])
@require_shop_auth
def list_vendors():
    """
    List all unique vendors/brands in the store.

    Returns:
        List of vendor names
    """
    client = get_shopify_client_for_tenant()
    if not client:
        return jsonify({'error': 'Shopify not configured'}), 500

    try:
        vendors = client.get_vendors()
        return jsonify({
            'vendors': vendors,
            'count': len(vendors)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@shopify_data_bp.route('/product-types', methods=['GET'])
@require_shop_auth
def list_product_types():
    """
    List all unique product types in the store.

    Returns:
        List of product type names
    """
    client = get_shopify_client_for_tenant()
    if not client:
        return jsonify({'error': 'Shopify not configured'}), 500

    try:
        product_types = client.get_product_types()
        return jsonify({
            'product_types': product_types,
            'count': len(product_types)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@shopify_data_bp.route('/tags', methods=['GET'])
@require_shop_auth
def list_tags():
    """
    List commonly used product tags in the store.

    Note: Shopify doesn't provide a direct API to list all tags.
    This returns a curated list of common/useful tags.

    Returns:
        List of tag names
    """
    # Common e-commerce tags that are typically used
    # In a real implementation, you could query recent products and extract tags
    common_tags = [
        'sale',
        'new',
        'featured',
        'bestseller',
        'preorder',
        'exclusive',
        'limited',
        'clearance',
    ]

    return jsonify({
        'tags': common_tags,
        'count': len(common_tags),
        'note': 'This is a list of common tags. Actual tags depend on your products.'
    })
