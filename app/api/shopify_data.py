"""
Shopify Data API endpoints.

Provides access to Shopify store data for use in promotion configuration:
- Collections (for filtering promotions by collection)
- Vendors (for filtering by brand/vendor)
- Product types
- Product tags
"""
import logging
from flask import Blueprint, request, jsonify, g
from ..services.shopify_client import ShopifyClient
from ..middleware.shopify_auth import require_shopify_auth

logger = logging.getLogger(__name__)

shopify_data_bp = Blueprint('shopify_data', __name__)


def get_shopify_client_for_tenant():
    """Create Shopify client for the current tenant."""
    tenant_id = g.tenant_id
    tenant = g.tenant

    # Check if tenant has Shopify credentials
    if not tenant or not tenant.shopify_domain or not tenant.shopify_access_token:
        return None

    try:
        return ShopifyClient(tenant_id)
    except Exception as e:
        logger.warning('Failed to create client: %s', e)
        return None


@shopify_data_bp.route('/collections', methods=['GET'])
@require_shopify_auth
def list_collections():
    """
    List all Shopify collections.

    Returns:
        List of collections with id, title, handle
    """
    client = get_shopify_client_for_tenant()
    if not client:
        logger.error('Collections: Shopify client not created')
        return jsonify({'error': 'Shopify not configured'}), 500

    try:
        logger.info(f'Fetching collections for tenant {g.tenant_id}')
        collections = client.get_collections()
        logger.info(f'Found {len(collections)} collections')
        return jsonify({
            'collections': collections,
            'count': len(collections)
        })
    except Exception as e:
        logger.exception(f'Collections error: {e}')
        return jsonify({'error': str(e)}), 500


@shopify_data_bp.route('/vendors', methods=['GET'])
@require_shopify_auth
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
@require_shopify_auth
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
@require_shopify_auth
def list_tags():
    """
    List product tags from the store's products.

    Fetches actual tags from products in the Shopify store.

    Returns:
        List of tag names
    """
    client = get_shopify_client_for_tenant()
    if not client:
        return jsonify({'error': 'Shopify not configured'}), 500

    try:
        tags = client.get_product_tags()
        return jsonify({
            'tags': tags,
            'count': len(tags)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@shopify_data_bp.route('/customer-tags', methods=['GET'])
@require_shopify_auth
def list_customer_tags():
    """
    List customer tags from the store's customers.

    Fetches actual tags from customers in the Shopify store.

    Returns:
        List of tag names
    """
    client = get_shopify_client_for_tenant()
    if not client:
        return jsonify({'error': 'Shopify not configured'}), 500

    try:
        tags = client.get_customer_tags()
        return jsonify({
            'customer_tags': tags,
            'count': len(tags)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@shopify_data_bp.route('/segments', methods=['GET'])
@require_shopify_auth
def list_segments():
    """
    List customer segments from Shopify.

    Returns:
        List of segments with id, name, query
    """
    client = get_shopify_client_for_tenant()
    if not client:
        return jsonify({'error': 'Shopify not configured'}), 500

    try:
        segments = client.get_segments()
        return jsonify({
            'segments': segments,
            'count': len(segments)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
