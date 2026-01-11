"""
Customer Segments API for TradeUp.

Syncs customer segments to Shopify for use with:
- Shopify Email marketing campaigns
- Flow automations
- Customer targeting

Segments created:
- TradeUp: Gold Members (tier-based)
- TradeUp: Has 500+ Points (points threshold)
- TradeUp: Reward Available (can redeem)
- TradeUp: At Risk (No activity 30 days)
- TradeUp: VIP (Top 10% spenders)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, request, jsonify, g, current_app
from sqlalchemy import func, and_, or_

from ..extensions import db
from ..models import Member, MembershipTier, Tenant
from ..models.loyalty_points import PointsBalance, PointsLedger, Reward
from ..middleware.shopify_auth import require_shopify_auth
from ..services.shopify_client import ShopifyClient

segments_bp = Blueprint('segments', __name__)


# ==============================================================================
# Segment Definitions
# ==============================================================================

# Default segment definitions with Shopify segment query syntax
SEGMENT_DEFINITIONS = {
    'tier_segments': [
        {
            'key': 'bronze',
            'name': 'TradeUp: Bronze Members',
            'description': 'Members in the Bronze tier',
            'query_template': "customer_tags CONTAINS 'tradeup-bronze'"
        },
        {
            'key': 'silver',
            'name': 'TradeUp: Silver Members',
            'description': 'Members in the Silver tier',
            'query_template': "customer_tags CONTAINS 'tradeup-silver'"
        },
        {
            'key': 'gold',
            'name': 'TradeUp: Gold Members',
            'description': 'Members in the Gold tier',
            'query_template': "customer_tags CONTAINS 'tradeup-gold'"
        },
        {
            'key': 'platinum',
            'name': 'TradeUp: Platinum Members',
            'description': 'Members in the Platinum tier',
            'query_template': "customer_tags CONTAINS 'tradeup-platinum'"
        },
    ],
    'points_segments': [
        {
            'key': 'points_500',
            'name': 'TradeUp: Has 500+ Points',
            'description': 'Members with 500 or more points available',
            'query_template': "customer_tags CONTAINS 'tradeup-points-500plus'"
        },
        {
            'key': 'points_1000',
            'name': 'TradeUp: Has 1000+ Points',
            'description': 'Members with 1000 or more points available',
            'query_template': "customer_tags CONTAINS 'tradeup-points-1000plus'"
        },
    ],
    'engagement_segments': [
        {
            'key': 'reward_available',
            'name': 'TradeUp: Reward Available',
            'description': 'Members who can redeem at least one reward',
            'query_template': "customer_tags CONTAINS 'tradeup-reward-available'"
        },
        {
            'key': 'at_risk',
            'name': 'TradeUp: At Risk (No activity 30 days)',
            'description': 'Members with no activity in the last 30 days',
            'query_template': "customer_tags CONTAINS 'tradeup-at-risk'"
        },
        {
            'key': 'vip',
            'name': 'TradeUp: VIP (Top 10% spenders)',
            'description': 'Top 10% members by total spending',
            'query_template': "customer_tags CONTAINS 'tradeup-vip'"
        },
        {
            'key': 'new_member',
            'name': 'TradeUp: New Member (Last 30 days)',
            'description': 'Members who joined in the last 30 days',
            'query_template': "customer_tags CONTAINS 'tradeup-new-member'"
        },
    ],
    'all_members': {
        'key': 'all_members',
        'name': 'TradeUp: All Members',
        'description': 'All TradeUp loyalty program members',
        'query_template': "customer_tags CONTAINS 'tradeup-member'"
    }
}


# ==============================================================================
# Sync Segments Endpoint
# ==============================================================================

@segments_bp.route('/sync', methods=['POST'])
@require_shopify_auth
def sync_segments():
    """
    Sync customer segments to Shopify.

    Creates or updates segments in Shopify based on:
    - Membership tiers (Bronze, Silver, Gold, Platinum)
    - Points thresholds (500+, 1000+)
    - Engagement status (reward available, at risk, VIP)

    Also updates customer tags in Shopify to match segment criteria.

    Returns:
        Created/updated segments with their Shopify IDs
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    # Options
    sync_tags = data.get('sync_tags', True)  # Also update customer tags
    segment_types = data.get('segment_types', ['tier', 'points', 'engagement', 'all'])

    try:
        # Get tenant for Shopify client
        tenant = Tenant.query.get(tenant_id)
        if not tenant or not tenant.shopify_access_token:
            return jsonify({'error': 'Shopify not connected'}), 400

        client = ShopifyClient(tenant_id)
        results = {
            'segments_created': [],
            'segments_updated': [],
            'tags_synced': 0,
            'errors': []
        }

        # Step 1: Sync customer tags if enabled
        if sync_tags:
            tag_result = _sync_customer_tags(tenant_id, client)
            results['tags_synced'] = tag_result.get('synced', 0)
            if tag_result.get('errors'):
                results['errors'].extend(tag_result['errors'])

        # Step 2: Create/update segments in Shopify
        segments_to_create = []

        if 'tier' in segment_types:
            # Get tiers for this tenant
            tiers = MembershipTier.query.filter_by(tenant_id=tenant_id).all()
            for tier in tiers:
                tier_slug = tier.name.lower().replace(' ', '-')
                segments_to_create.append({
                    'name': f'TradeUp: {tier.name} Members',
                    'query': f"customer_tags CONTAINS 'tradeup-{tier_slug}'"
                })

        if 'points' in segment_types:
            for seg in SEGMENT_DEFINITIONS['points_segments']:
                segments_to_create.append({
                    'name': seg['name'],
                    'query': seg['query_template']
                })

        if 'engagement' in segment_types:
            for seg in SEGMENT_DEFINITIONS['engagement_segments']:
                segments_to_create.append({
                    'name': seg['name'],
                    'query': seg['query_template']
                })

        if 'all' in segment_types:
            seg = SEGMENT_DEFINITIONS['all_members']
            segments_to_create.append({
                'name': seg['name'],
                'query': seg['query_template']
            })

        # Create/update each segment
        for seg_def in segments_to_create:
            try:
                result = client.create_or_update_segment(
                    name=seg_def['name'],
                    segment_query=seg_def['query']
                )
                if result.get('action') == 'created':
                    results['segments_created'].append({
                        'name': seg_def['name'],
                        'id': result.get('id')
                    })
                else:
                    results['segments_updated'].append({
                        'name': seg_def['name'],
                        'id': result.get('id')
                    })
            except Exception as e:
                results['errors'].append({
                    'segment': seg_def['name'],
                    'error': str(e)
                })

        return jsonify({
            'success': len(results['errors']) == 0,
            'results': results,
            'message': f"Created {len(results['segments_created'])} segments, updated {len(results['segments_updated'])}"
        })

    except Exception as e:
        current_app.logger.error(f"Error syncing segments: {e}")
        return jsonify({'error': str(e)}), 500


@segments_bp.route('/list', methods=['GET'])
@require_shopify_auth
def list_segments():
    """
    List all TradeUp segments in Shopify.

    Returns:
        List of segments with their Shopify IDs and queries
    """
    tenant_id = g.tenant_id

    try:
        client = ShopifyClient(tenant_id)
        segments = client.get_segments()

        # Filter to only TradeUp segments
        tradeup_segments = [
            s for s in segments
            if s.get('name', '').startswith('TradeUp:')
        ]

        return jsonify({
            'segments': tradeup_segments,
            'count': len(tradeup_segments),
            'total_shopify_segments': len(segments)
        })

    except Exception as e:
        current_app.logger.error(f"Error listing segments: {e}")
        return jsonify({'error': str(e)}), 500


@segments_bp.route('/definitions', methods=['GET'])
@require_shopify_auth
def get_segment_definitions():
    """
    Get available segment definitions.

    Returns definitions that can be synced to Shopify.
    """
    tenant_id = g.tenant_id

    # Get tiers for this tenant to customize tier segments
    tiers = MembershipTier.query.filter_by(tenant_id=tenant_id).all()

    tier_segments = []
    for tier in tiers:
        tier_slug = tier.name.lower().replace(' ', '-')
        tier_segments.append({
            'key': tier_slug,
            'name': f'TradeUp: {tier.name} Members',
            'description': f'Members in the {tier.name} tier',
            'query_template': f"customer_tags CONTAINS 'tradeup-{tier_slug}'"
        })

    return jsonify({
        'tier_segments': tier_segments,
        'points_segments': SEGMENT_DEFINITIONS['points_segments'],
        'engagement_segments': SEGMENT_DEFINITIONS['engagement_segments'],
        'all_members': SEGMENT_DEFINITIONS['all_members']
    })


@segments_bp.route('/sync-tags', methods=['POST'])
@require_shopify_auth
def sync_customer_tags():
    """
    Sync TradeUp membership tags to Shopify customers.

    Updates customer tags based on:
    - Tier membership (tradeup-gold, etc.)
    - Points balance (tradeup-points-500plus, etc.)
    - Engagement status (tradeup-at-risk, etc.)

    This is needed for segment queries to work.

    Returns:
        Number of customers updated
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    # Options
    batch_size = data.get('batch_size', 50)
    member_ids = data.get('member_ids')  # Optional: sync only specific members

    try:
        client = ShopifyClient(tenant_id)
        result = _sync_customer_tags(tenant_id, client, batch_size, member_ids)

        return jsonify({
            'success': True,
            'synced': result.get('synced', 0),
            'failed': result.get('failed', 0),
            'errors': result.get('errors', [])[:10]  # Limit errors in response
        })

    except Exception as e:
        current_app.logger.error(f"Error syncing tags: {e}")
        return jsonify({'error': str(e)}), 500


@segments_bp.route('/member-counts', methods=['GET'])
@require_shopify_auth
def get_segment_member_counts():
    """
    Get member counts for each segment type.

    Useful for preview before syncing and for analytics.

    Returns:
        Counts for each segment category
    """
    tenant_id = g.tenant_id

    try:
        # Tier counts
        tier_counts = db.session.query(
            MembershipTier.name,
            func.count(Member.id)
        ).join(
            Member, Member.tier_id == MembershipTier.id
        ).filter(
            Member.tenant_id == tenant_id,
            Member.status == 'active'
        ).group_by(MembershipTier.name).all()

        # Points threshold counts (using PointsLedger sum)
        points_subquery = db.session.query(
            PointsLedger.member_id,
            func.sum(PointsLedger.points).label('balance')
        ).filter(
            PointsLedger.tenant_id == tenant_id,
            PointsLedger.reversed_at.is_(None)
        ).group_by(PointsLedger.member_id).subquery()

        # Count members with 500+ points
        points_500_count = db.session.query(func.count()).filter(
            points_subquery.c.balance >= 500
        ).scalar() or 0

        # Count members with 1000+ points
        points_1000_count = db.session.query(func.count()).filter(
            points_subquery.c.balance >= 1000
        ).scalar() or 0

        # At-risk members (no activity in 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        at_risk_count = Member.query.filter(
            Member.tenant_id == tenant_id,
            Member.status == 'active',
            or_(
                Member.updated_at < thirty_days_ago,
                Member.updated_at.is_(None)
            )
        ).count()

        # New members (joined in last 30 days)
        new_member_count = Member.query.filter(
            Member.tenant_id == tenant_id,
            Member.status == 'active',
            Member.created_at >= thirty_days_ago
        ).count()

        # Total active members
        total_members = Member.query.filter_by(
            tenant_id=tenant_id,
            status='active'
        ).count()

        # Members who can redeem (have enough points for cheapest reward)
        cheapest_reward = Reward.query.filter(
            Reward.tenant_id == tenant_id,
            Reward.is_active == True
        ).order_by(Reward.points_cost.asc()).first()

        reward_available_count = 0
        if cheapest_reward:
            reward_available_count = db.session.query(func.count()).filter(
                points_subquery.c.balance >= cheapest_reward.points_cost
            ).scalar() or 0

        return jsonify({
            'tier_counts': {name: count for name, count in tier_counts},
            'points_counts': {
                '500+': points_500_count,
                '1000+': points_1000_count
            },
            'engagement_counts': {
                'at_risk': at_risk_count,
                'new_member': new_member_count,
                'reward_available': reward_available_count
            },
            'total_active_members': total_members,
            'cheapest_reward_cost': cheapest_reward.points_cost if cheapest_reward else None
        })

    except Exception as e:
        current_app.logger.error(f"Error getting member counts: {e}")
        return jsonify({'error': str(e)}), 500


# ==============================================================================
# VIP Calculation
# ==============================================================================

@segments_bp.route('/calculate-vip', methods=['POST'])
@require_shopify_auth
def calculate_vip_members():
    """
    Calculate and tag VIP members (top 10% spenders).

    Uses total lifetime spending from Shopify customer data.

    Returns:
        List of VIP member IDs and threshold amount
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    top_percent = data.get('top_percent', 10)
    apply_tags = data.get('apply_tags', False)

    try:
        client = ShopifyClient(tenant_id)

        # Get all members with their Shopify customer IDs
        members = Member.query.filter(
            Member.tenant_id == tenant_id,
            Member.status == 'active',
            Member.shopify_customer_id.isnot(None)
        ).all()

        if not members:
            return jsonify({
                'vip_members': [],
                'threshold_amount': 0,
                'message': 'No members found'
            })

        # Get spending data for each member
        member_spending = []
        for member in members:
            try:
                customer_data = client.get_customer_by_id(member.shopify_customer_id)
                if customer_data:
                    member_spending.append({
                        'member_id': member.id,
                        'shopify_customer_id': member.shopify_customer_id,
                        'amount_spent': customer_data.get('amountSpent', 0),
                        'name': member.name
                    })
            except Exception as e:
                current_app.logger.warning(f"Could not get customer data for {member.id}: {e}")

        if not member_spending:
            return jsonify({
                'vip_members': [],
                'threshold_amount': 0,
                'message': 'No spending data available'
            })

        # Sort by spending and calculate threshold
        member_spending.sort(key=lambda x: x['amount_spent'], reverse=True)

        vip_count = max(1, int(len(member_spending) * (top_percent / 100)))
        vip_threshold = member_spending[vip_count - 1]['amount_spent']
        vip_members = member_spending[:vip_count]

        # Apply VIP tags if requested
        if apply_tags:
            for vip in vip_members:
                try:
                    client.add_customer_tag(vip['shopify_customer_id'], 'tradeup-vip')
                except Exception as e:
                    current_app.logger.error(f"Failed to tag VIP {vip['member_id']}: {e}")

        return jsonify({
            'vip_members': vip_members,
            'vip_count': len(vip_members),
            'total_members': len(member_spending),
            'threshold_amount': vip_threshold,
            'top_percent': top_percent,
            'tags_applied': apply_tags
        })

    except Exception as e:
        current_app.logger.error(f"Error calculating VIP: {e}")
        return jsonify({'error': str(e)}), 500


# ==============================================================================
# Helper Functions
# ==============================================================================

def _sync_customer_tags(tenant_id: int, client: ShopifyClient, batch_size: int = 50, member_ids: list = None) -> dict:
    """
    Sync TradeUp tags to Shopify customers.

    Tags applied:
    - tradeup-member (all members)
    - tradeup-{tier-slug} (tier membership)
    - tradeup-points-500plus (points >= 500)
    - tradeup-points-1000plus (points >= 1000)
    - tradeup-reward-available (can redeem a reward)
    - tradeup-at-risk (no activity 30 days)
    - tradeup-new-member (joined last 30 days)
    """
    result = {
        'synced': 0,
        'failed': 0,
        'errors': []
    }

    # Build query
    query = Member.query.filter(
        Member.tenant_id == tenant_id,
        Member.status == 'active',
        Member.shopify_customer_id.isnot(None)
    )

    if member_ids:
        query = query.filter(Member.id.in_(member_ids))

    members = query.all()

    # Get points balances
    points_query = db.session.query(
        PointsLedger.member_id,
        func.sum(PointsLedger.points).label('balance')
    ).filter(
        PointsLedger.tenant_id == tenant_id,
        PointsLedger.reversed_at.is_(None)
    ).group_by(PointsLedger.member_id)

    points_map = {row.member_id: int(row.balance or 0) for row in points_query.all()}

    # Get cheapest reward for reward-available check
    cheapest_reward = Reward.query.filter(
        Reward.tenant_id == tenant_id,
        Reward.is_active == True
    ).order_by(Reward.points_cost.asc()).first()

    min_reward_points = cheapest_reward.points_cost if cheapest_reward else 9999999

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    for member in members:
        try:
            tags_to_add = ['tradeup-member']

            # Tier tag
            if member.tier:
                tier_slug = member.tier.name.lower().replace(' ', '-')
                tags_to_add.append(f'tradeup-{tier_slug}')

            # Points threshold tags
            points_balance = points_map.get(member.id, 0)
            if points_balance >= 500:
                tags_to_add.append('tradeup-points-500plus')
            if points_balance >= 1000:
                tags_to_add.append('tradeup-points-1000plus')

            # Reward available
            if points_balance >= min_reward_points:
                tags_to_add.append('tradeup-reward-available')

            # At-risk (no activity 30 days)
            last_activity = member.updated_at or member.created_at
            if last_activity and last_activity < thirty_days_ago:
                tags_to_add.append('tradeup-at-risk')

            # New member (joined last 30 days)
            if member.created_at and member.created_at >= thirty_days_ago:
                tags_to_add.append('tradeup-new-member')

            # Add tags to Shopify customer
            for tag in tags_to_add:
                client.add_customer_tag(member.shopify_customer_id, tag)

            result['synced'] += 1

        except Exception as e:
            result['failed'] += 1
            result['errors'].append({
                'member_id': member.id,
                'error': str(e)
            })

    return result


@segments_bp.route('/sync-products', methods=['POST'])
@require_shopify_auth
def sync_product_segments():
    """
    Create segments based on product purchase history.

    Creates segments for customers who have purchased specific:
    - Product types (e.g., "TradeUp: Pokemon Buyers")
    - Vendors (e.g., "TradeUp: Topps Buyers")
    - Collections

    Returns:
        Created segments
    """
    tenant_id = g.tenant_id
    data = request.json or {}

    segment_type = data.get('type', 'product_type')  # product_type, vendor, collection
    values = data.get('values', [])  # List of product types/vendors/collections

    if not values:
        return jsonify({'error': 'values is required'}), 400

    try:
        client = ShopifyClient(tenant_id)
        results = {
            'segments_created': [],
            'errors': []
        }

        for value in values:
            try:
                # Create segment with appropriate query
                if segment_type == 'product_type':
                    segment_name = f"TradeUp: {value} Buyers"
                    segment_query = f"products_purchased(product_type: '{value}')"
                elif segment_type == 'vendor':
                    segment_name = f"TradeUp: {value} Buyers"
                    segment_query = f"products_purchased(vendor: '{value}')"
                elif segment_type == 'collection':
                    segment_name = f"TradeUp: {value} Buyers"
                    segment_query = f"products_purchased(collection_id: '{value}')"
                else:
                    continue

                result = client.create_or_update_segment(
                    name=segment_name,
                    segment_query=segment_query
                )
                results['segments_created'].append({
                    'name': segment_name,
                    'id': result.get('id'),
                    'action': result.get('action')
                })

            except Exception as e:
                results['errors'].append({
                    'value': value,
                    'error': str(e)
                })

        return jsonify({
            'success': len(results['errors']) == 0,
            'results': results
        })

    except Exception as e:
        current_app.logger.error(f"Error syncing product segments: {e}")
        return jsonify({'error': str(e)}), 500
