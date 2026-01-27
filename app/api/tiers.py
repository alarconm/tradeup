"""
Tier Management API.

Provides REST endpoints for managing membership tiers, including:
- Staff tier assignment
- Promotional tier application
- Eligibility rule management
- Tier history and audit trail
- Promotion CRUD operations
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from ..extensions import db
from ..models import Member, MembershipTier, Tenant
from ..models.tier_history import (
    TierChangeLog,
    TierEligibilityRule,
    TierPromotion,
    MemberPromoUsage
)
from ..services.tier_service import TierService


tiers_bp = Blueprint('tiers', __name__, url_prefix='/api/tiers')


def get_tenant():
    """Get tenant from request context, header, or shop parameter."""
    if hasattr(g, 'tenant') and g.tenant:
        return g.tenant

    # Try X-Tenant-ID header
    tenant_id = request.headers.get('X-Tenant-ID')
    if tenant_id:
        tenant = Tenant.query.get(int(tenant_id))
        if tenant:
            return tenant

    # Try shop parameter (from URL query string)
    shop = request.args.get('shop')
    if shop:
        tenant = Tenant.query.filter_by(shopify_domain=shop).first()
        if tenant:
            return tenant

    # Try X-Shop-Domain header
    shop = request.headers.get('X-Shop-Domain')
    if shop:
        tenant = Tenant.query.filter_by(shopify_domain=shop).first()
        if tenant:
            return tenant

    return None


def get_current_user():
    """Get current user email for audit purposes."""
    return request.headers.get('X-Staff-Email', 'api:unknown')


# ==================== Tier Assignment Endpoints ====================

@tiers_bp.route('/assign', methods=['POST'])
def assign_tier():
    """
    Assign a tier to a member (staff action).

    Request body:
    {
        "member_id": 123,
        "tier_id": 1,  # or null to remove tier
        "reason": "VIP customer upgrade",
        "duration_days": 365,  # optional - null for permanent
        "notes": "Requested via email"  # optional
    }
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    data = request.json or {}
    member_id = data.get('member_id')
    tier_id = data.get('tier_id')
    reason = data.get('reason')
    duration_days = data.get('duration_days')
    notes = data.get('notes')
    staff_email = get_current_user()

    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400

    tier_service = TierService(tenant.id)
    result = tier_service.staff_assign_tier(
        member_id=member_id,
        tier_id=tier_id,
        staff_email=staff_email,
        reason=reason,
        duration_days=duration_days,
        notes=notes
    )

    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code


@tiers_bp.route('/bulk-assign', methods=['POST'])
def bulk_assign_tier():
    """
    Assign a tier to multiple members at once.

    Request body:
    {
        "member_ids": [1, 2, 3],
        "tier_id": 1,  # or null to remove tier
        "reason": "Bulk upgrade campaign",
        "duration_days": 30
    }
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    data = request.json or {}
    member_ids = data.get('member_ids', [])
    tier_id = data.get('tier_id')
    reason = data.get('reason')
    duration_days = data.get('duration_days')
    staff_email = get_current_user()

    if not member_ids:
        return jsonify({'error': 'member_ids is required'}), 400

    tier_service = TierService(tenant.id)

    # Handle tier removal (tier_id is null or empty)
    if not tier_id:
        results = {
            'successful': 0,
            'failed': 0,
            'failures': []
        }
        for member_id in member_ids:
            result = tier_service.remove_tier(
                member_id=member_id,
                source_type='staff',
                source_reference=staff_email,
                reason=reason or 'Bulk tier removal',
                created_by=staff_email
            )
            if result.get('success'):
                results['successful'] += 1
            else:
                results['failed'] += 1
                results['failures'].append({
                    'member_id': member_id,
                    'error': result.get('error')
                })
        return jsonify(results), 200

    # Assign tier
    expires_at = None
    if duration_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=duration_days)

    result = tier_service.bulk_assign_tier(
        member_ids=member_ids,
        tier_id=tier_id,
        source_type='staff',
        source_reference=staff_email,
        reason=reason,
        expires_at=expires_at,
        created_by=staff_email
    )

    # Normalize response format
    return jsonify({
        'successful': result.get('success_count', 0),
        'failed': result.get('failure_count', 0),
        'failures': result.get('failures', [])
    }), 200


# ==================== Promotion Endpoints ====================

@tiers_bp.route('/promotions', methods=['GET'])
def list_promotions():
    """List all tier promotions."""
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    active_only = request.args.get('active', 'true').lower() == 'true'

    query = TierPromotion.query.filter_by(tenant_id=tenant.id)
    if active_only:
        query = query.filter_by(is_active=True)

    promotions = query.order_by(TierPromotion.starts_at.desc()).all()

    return jsonify({
        'promotions': [p.to_dict() for p in promotions]
    })


@tiers_bp.route('/promotions', methods=['POST'])
def create_promotion():
    """
    Create a new tier promotion.

    Request body:
    {
        "name": "Summer VIP Sale",
        "tier_id": 2,
        "code": "SUMMER2025",
        "description": "Get VIP status for the summer",
        "starts_at": "2025-06-01T00:00:00Z",
        "ends_at": "2025-08-31T23:59:59Z",
        "grant_duration_days": 90,
        "target_type": "all",
        "max_uses": 100,
        "upgrade_only": true,
        "revert_on_expire": true
    }
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    data = request.json or {}

    # Validate required fields
    required = ['name', 'tier_id', 'starts_at', 'ends_at']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    # Validate tier exists
    tier = MembershipTier.query.filter_by(
        id=data['tier_id'],
        tenant_id=tenant.id,
        is_active=True
    ).first()
    if not tier:
        return jsonify({'error': 'Tier not found'}), 404

    # Parse dates
    try:
        starts_at = datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00'))
        ends_at = datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00'))
    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400

    promotion = TierPromotion(
        tenant_id=tenant.id,
        tier_id=data['tier_id'],
        name=data['name'],
        code=data.get('code', '').upper() or None,
        description=data.get('description'),
        starts_at=starts_at,
        ends_at=ends_at,
        grant_duration_days=data.get('grant_duration_days'),
        target_type=data.get('target_type', 'all'),
        target_tiers=data.get('target_tiers'),
        target_tags=data.get('target_tags'),
        max_uses=data.get('max_uses'),
        max_uses_per_member=data.get('max_uses_per_member', 1),
        stackable=data.get('stackable', False),
        upgrade_only=data.get('upgrade_only', True),
        revert_on_expire=data.get('revert_on_expire', True),
        is_active=True,
        created_by=get_current_user()
    )

    db.session.add(promotion)
    db.session.commit()

    return jsonify({
        'success': True,
        'promotion': promotion.to_dict()
    }), 201


@tiers_bp.route('/promotions/<int:promo_id>', methods=['GET'])
def get_promotion(promo_id):
    """Get a specific promotion."""
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    promotion = TierPromotion.query.filter_by(
        id=promo_id,
        tenant_id=tenant.id
    ).first()

    if not promotion:
        return jsonify({'error': 'Promotion not found'}), 404

    return jsonify({'promotion': promotion.to_dict()})


@tiers_bp.route('/promotions/<int:promo_id>', methods=['PUT'])
def update_promotion(promo_id):
    """Update a promotion."""
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    promotion = TierPromotion.query.filter_by(
        id=promo_id,
        tenant_id=tenant.id
    ).first()

    if not promotion:
        return jsonify({'error': 'Promotion not found'}), 404

    data = request.json or {}

    # Update allowed fields
    if 'name' in data:
        promotion.name = data['name']
    if 'description' in data:
        promotion.description = data['description']
    if 'code' in data:
        promotion.code = data['code'].upper() if data['code'] else None
    if 'ends_at' in data:
        promotion.ends_at = datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00'))
    if 'max_uses' in data:
        promotion.max_uses = data['max_uses']
    if 'is_active' in data:
        promotion.is_active = data['is_active']

    db.session.commit()

    return jsonify({
        'success': True,
        'promotion': promotion.to_dict()
    })


@tiers_bp.route('/promotions/<int:promo_id>', methods=['DELETE'])
def delete_promotion(promo_id):
    """Deactivate a promotion (soft delete)."""
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    promotion = TierPromotion.query.filter_by(
        id=promo_id,
        tenant_id=tenant.id
    ).first()

    if not promotion:
        return jsonify({'error': 'Promotion not found'}), 404

    promotion.is_active = False
    db.session.commit()

    return jsonify({'success': True, 'message': 'Promotion deactivated'})


@tiers_bp.route('/apply-promo', methods=['POST'])
def apply_promotion():
    """
    Apply a promotional tier to a member.

    Request body:
    {
        "member_id": 123,
        "promo_code": "SUMMER2025"  # or "promotion_id": 1
    }
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    data = request.json or {}
    member_id = data.get('member_id')
    promo_code = data.get('promo_code')
    promotion_id = data.get('promotion_id')

    if not member_id:
        return jsonify({'error': 'member_id is required'}), 400
    if not promo_code and not promotion_id:
        return jsonify({'error': 'promo_code or promotion_id is required'}), 400

    tier_service = TierService(tenant.id)
    result = tier_service.apply_promotion(
        member_id=member_id,
        promotion_id=promotion_id,
        promo_code=promo_code
    )

    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code


# ==================== Eligibility Rules Endpoints ====================

@tiers_bp.route('/eligibility-rules', methods=['GET'])
def list_eligibility_rules():
    """List all eligibility rules."""
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    tier_id = request.args.get('tier_id', type=int)
    active_only = request.args.get('active', 'true').lower() == 'true'

    query = TierEligibilityRule.query.filter_by(tenant_id=tenant.id)
    if tier_id:
        query = query.filter_by(tier_id=tier_id)
    if active_only:
        query = query.filter_by(is_active=True)

    rules = query.order_by(
        TierEligibilityRule.priority.desc(),
        TierEligibilityRule.created_at.desc()
    ).all()

    return jsonify({
        'rules': [r.to_dict() for r in rules]
    })


@tiers_bp.route('/eligibility-rules', methods=['POST'])
def create_eligibility_rule():
    """
    Create a new eligibility rule.

    Request body:
    {
        "tier_id": 2,
        "name": "Gold Spend Threshold",
        "description": "Spend $500 to earn Gold status",
        "rule_type": "qualification",
        "metric": "total_spend",
        "threshold_value": 500,
        "threshold_operator": ">=",
        "time_window_days": 365,
        "rolling_window": true,
        "action": "upgrade",
        "priority": 10
    }
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    data = request.json or {}

    # Validate required fields
    required = ['tier_id', 'name', 'rule_type', 'metric', 'threshold_value']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    # Validate tier exists
    tier = MembershipTier.query.filter_by(
        id=data['tier_id'],
        tenant_id=tenant.id,
        is_active=True
    ).first()
    if not tier:
        return jsonify({'error': 'Tier not found'}), 404

    # Validate rule_type
    valid_rule_types = ['qualification', 'maintenance', 'upgrade', 'downgrade']
    if data['rule_type'] not in valid_rule_types:
        return jsonify({'error': f'Invalid rule_type. Must be one of: {", ".join(valid_rule_types)}'}), 400

    # Validate metric
    valid_metrics = [
        'total_spend', 'trade_in_count', 'trade_in_value',
        'order_count', 'points_earned', 'referrals', 'membership_duration'
    ]
    if data['metric'] not in valid_metrics:
        return jsonify({'error': f'Invalid metric. Must be one of: {", ".join(valid_metrics)}'}), 400

    rule = TierEligibilityRule(
        tenant_id=tenant.id,
        tier_id=data['tier_id'],
        name=data['name'],
        description=data.get('description'),
        rule_type=data['rule_type'],
        metric=data['metric'],
        threshold_value=data['threshold_value'],
        threshold_operator=data.get('threshold_operator', '>='),
        threshold_max=data.get('threshold_max'),
        time_window_days=data.get('time_window_days'),
        rolling_window=data.get('rolling_window', True),
        action=data.get('action', 'upgrade'),
        priority=data.get('priority', 0),
        is_active=True
    )

    db.session.add(rule)
    db.session.commit()

    return jsonify({
        'success': True,
        'rule': rule.to_dict()
    }), 201


@tiers_bp.route('/eligibility-rules/<int:rule_id>', methods=['PUT'])
def update_eligibility_rule(rule_id):
    """Update an eligibility rule."""
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    rule = TierEligibilityRule.query.filter_by(
        id=rule_id,
        tenant_id=tenant.id
    ).first()

    if not rule:
        return jsonify({'error': 'Rule not found'}), 404

    data = request.json or {}

    # Update allowed fields
    updateable = [
        'name', 'description', 'threshold_value', 'threshold_operator',
        'threshold_max', 'time_window_days', 'priority', 'is_active'
    ]
    for field in updateable:
        if field in data:
            setattr(rule, field, data[field])

    db.session.commit()

    return jsonify({
        'success': True,
        'rule': rule.to_dict()
    })


@tiers_bp.route('/eligibility-rules/<int:rule_id>', methods=['DELETE'])
def delete_eligibility_rule(rule_id):
    """Deactivate an eligibility rule (soft delete)."""
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    rule = TierEligibilityRule.query.filter_by(
        id=rule_id,
        tenant_id=tenant.id
    ).first()

    if not rule:
        return jsonify({'error': 'Rule not found'}), 404

    rule.is_active = False
    db.session.commit()

    return jsonify({'success': True, 'message': 'Rule deactivated'})


@tiers_bp.route('/check-eligibility/<int:member_id>', methods=['GET'])
def check_member_eligibility(member_id):
    """
    Check a member's eligibility for earned tiers.

    Query params:
    - apply: If 'true', automatically assign tier if eligible
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    apply_if_eligible = request.args.get('apply', 'false').lower() == 'true'

    tier_service = TierService(tenant.id)
    result = tier_service.check_earned_tier_eligibility(
        member_id=member_id,
        apply_if_eligible=apply_if_eligible
    )

    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code


# ==================== History & Audit Endpoints ====================

@tiers_bp.route('/history/<int:member_id>', methods=['GET'])
def get_member_tier_history(member_id):
    """
    Get tier change history for a member.

    Query params:
    - limit: Max records to return (default 20)
    - offset: Pagination offset (default 0)
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)

    tier_service = TierService(tenant.id)
    result = tier_service.get_tier_history(
        member_id=member_id,
        limit=limit,
        offset=offset
    )

    return jsonify(result)


@tiers_bp.route('/audit-log', methods=['GET'])
def get_audit_log():
    """
    Get tier change audit log for the tenant.

    Query params:
    - limit: Max records to return (default 50)
    - offset: Pagination offset (default 0)
    - change_type: Filter by change type
    - source_type: Filter by source type
    - from_date: Filter from date (ISO format)
    - to_date: Filter to date (ISO format)
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    change_type = request.args.get('change_type')
    source_type = request.args.get('source_type')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = TierChangeLog.query.filter_by(tenant_id=tenant.id)

    if change_type:
        query = query.filter_by(change_type=change_type)
    if source_type:
        query = query.filter_by(source_type=source_type)
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            query = query.filter(TierChangeLog.created_at >= from_dt)
        except ValueError:
            current_app.logger.warning(f"Invalid from_date format: {from_date}")
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            query = query.filter(TierChangeLog.created_at <= to_dt)
        except ValueError:
            current_app.logger.warning(f"Invalid to_date format: {to_date}")

    total = query.count()
    logs = query.order_by(TierChangeLog.created_at.desc()).limit(limit).offset(offset).all()

    return jsonify({
        'logs': [log.to_dict() for log in logs],
        'total': total,
        'limit': limit,
        'offset': offset
    })


# ==================== Statistics Endpoints ====================

@tiers_bp.route('/stats', methods=['GET'])
def get_tier_stats():
    """Get tier statistics for the tenant."""
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get tier distribution
    from sqlalchemy import func
    tier_counts = db.session.query(
        MembershipTier.name,
        func.count(Member.id)
    ).outerjoin(
        Member, Member.tier_id == MembershipTier.id
    ).filter(
        MembershipTier.tenant_id == tenant.id,
        MembershipTier.is_active == True
    ).group_by(
        MembershipTier.id, MembershipTier.name
    ).all()

    # Count members without tier
    no_tier_count = Member.query.filter_by(
        tenant_id=tenant.id,
        tier_id=None,
        status='active'
    ).count()

    # Get recent changes
    recent_changes = TierChangeLog.query.filter_by(
        tenant_id=tenant.id
    ).order_by(
        TierChangeLog.created_at.desc()
    ).limit(10).all()

    # Get active promotions
    now = datetime.utcnow()
    active_promos = TierPromotion.query.filter(
        TierPromotion.tenant_id == tenant.id,
        TierPromotion.is_active == True,
        TierPromotion.starts_at <= now,
        TierPromotion.ends_at >= now
    ).count()

    return jsonify({
        'tier_distribution': {name: count for name, count in tier_counts},
        'no_tier_count': no_tier_count,
        'recent_changes': [log.to_dict() for log in recent_changes],
        'active_promotions': active_promos
    })


# ==================== Batch Processing Endpoints ====================

@tiers_bp.route('/process-eligibility', methods=['POST'])
def process_tier_eligibility():
    """
    Process tier eligibility for all active members.

    This endpoint triggers the batch eligibility check which:
    - Checks all active members against eligibility rules
    - Upgrades members who meet higher tier criteria
    - Downgrades members who no longer meet their current tier requirements

    Request body (optional):
        member_ids: list[int] - Specific member IDs to process (default: all active)

    Returns:
        Processing results with counts of upgrades/downgrades/unchanged
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    data = request.get_json() or {}
    member_ids = data.get('member_ids')

    try:
        service = TierService(tenant.id)
        results = service.process_activity_batch(member_ids=member_ids)

        return jsonify({
            'success': True,
            'results': results,
            'message': f'Processed {results["checked"]} members: {results["upgraded"]} upgraded, {results["downgraded"]} downgraded, {results["unchanged"]} unchanged'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tiers_bp.route('/process-expirations', methods=['POST'])
def process_tier_expirations():
    """
    Process expired tier assignments.

    This endpoint triggers the expiration check which:
    - Finds members with expired tier assignments
    - Reverts promotional tiers to previous tier
    - Removes expired tiers

    Returns:
        Processing results with counts of processed/removed/reverted
    """
    tenant = get_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    try:
        service = TierService(tenant.id)
        results = service.process_expired_tiers()

        return jsonify({
            'success': True,
            'results': results,
            'message': f'Processed {results["processed"]} expirations: {results["removed"]} removed, {results["reverted"]} reverted'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
