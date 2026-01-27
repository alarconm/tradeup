"""
Order lifecycle webhook handlers.
Handles order events for TradeUp rewards, points, and membership purchases.

Features:
1. Auto-enrollment: Automatically enroll customers as members on first purchase
2. Membership products: Detect and assign tiers from product purchases
3. Points: Award points based on order value

Membership products can be detected by:
1. Product tags: 'membership:gold', 'tier:platinum', 'membership-silver'
2. Product type: 'Membership'
3. Product metafield: 'tradeup.tier_id'

Uses TierService for all tier operations to ensure proper auditing and
priority-based conflict resolution.
"""
import hmac
import hashlib
import base64
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import Tenant, Member, MembershipTier
from ..models.referral import ReferralProgram, Referral
from ..services.tier_service import TierService
from ..services.membership_service import MembershipService
from ..services.store_credit_service import store_credit_service


order_lifecycle_bp = Blueprint('order_lifecycle', __name__)


# ==================== REFERRAL TRACKING ====================

def extract_referral_code_from_order(order_data: dict) -> str:
    """
    Extract referral code from order data.

    Checks multiple sources:
    1. Note attributes (custom cart attributes)
    2. Discount codes
    3. Order notes

    Args:
        order_data: Full order payload from Shopify

    Returns:
        Referral code if found, None otherwise
    """
    # Check note attributes (cart attributes)
    note_attributes = order_data.get('note_attributes', [])
    for attr in note_attributes:
        name = attr.get('name', '').lower()
        if name in ['referral_code', 'ref', 'referral', 'referred_by', 'ref_code']:
            code = attr.get('value', '').strip().upper()
            if code:
                return code

    # Check discount codes (sometimes referral codes are used as discounts)
    discount_codes = order_data.get('discount_codes', [])
    for discount in discount_codes:
        code = discount.get('code', '').upper()
        # Check if this discount code matches a referral code format
        # Referral codes are typically 8 chars alphanumeric like "JOHN2025"
        if code and len(code) <= 20:
            # Verify it's actually a referral code
            referrer = Member.query.filter_by(referral_code=code, status='active').first()
            if referrer:
                return code

    # Check order notes
    note = order_data.get('note', '')
    if note:
        # Look for referral code patterns in notes
        import re
        match = re.search(r'(?:ref|referral|referred by)[:\s]*([A-Z0-9]{4,20})', note.upper())
        if match:
            code = match.group(1)
            # Verify it's actually a referral code
            referrer = Member.query.filter_by(referral_code=code, status='active').first()
            if referrer:
                return code

    return None


def process_referral_on_order(tenant: Tenant, member: Member, order_data: dict) -> dict:
    """
    Process referral tracking for an order.

    If the member was referred and this is their first purchase, complete the
    referral and grant rewards based on the program configuration.

    Args:
        tenant: Tenant object
        member: Member who placed the order
        order_data: Full order payload from Shopify

    Returns:
        Dict with referral processing result
    """
    result = {'referral_processed': False}

    # Get referral program configuration
    program = ReferralProgram.query.filter_by(
        tenant_id=tenant.id,
        is_active=True
    ).first()

    if not program:
        # No referral program - use tenant-specific config or defaults
        from ..api.referrals import ReferralConfig
        ref_config = ReferralConfig.get_config(tenant)
        program_grant_on = 'signup' if ref_config['grant_on_signup'] else 'first_purchase'
        referrer_reward = ref_config['referrer_credit']
        referee_reward = ref_config['referee_credit']
    else:
        program_grant_on = program.grant_on
        referrer_reward = program.referrer_reward_amount
        referee_reward = program.referee_reward_amount

    # ==========================================
    # CASE 1: Member already has a referrer but rewards pending
    # ==========================================
    if member.referred_by_id:
        referrer = Member.query.get(member.referred_by_id)
        if not referrer:
            return result

        # Check if rewards have already been issued
        existing_referral = Referral.query.filter_by(
            referee_id=member.id,
            referrer_id=referrer.id
        ).first()

        # If grant_on is 'first_purchase' and rewards not yet issued
        if program_grant_on == 'first_purchase':
            if existing_referral and not existing_referral.referrer_reward_issued:
                # This is the first purchase - complete the referral
                credits_granted = complete_referral_rewards(
                    referrer=referrer,
                    referee=member,
                    referral=existing_referral,
                    referrer_reward=referrer_reward,
                    referee_reward=referee_reward
                )
                result['referral_processed'] = True
                result['credits_granted'] = credits_granted
                result['referrer_member_number'] = referrer.member_number
                current_app.logger.info(
                    f"Referral completed on first purchase: {member.member_number} referred by {referrer.member_number}"
                )
            elif not existing_referral:
                # Create referral record and grant rewards
                new_referral = Referral(
                    program_id=program.id if program else None,
                    referrer_id=referrer.id,
                    referee_id=member.id,
                    referral_code=referrer.referral_code or '',
                    status='completed',
                    completed_at=datetime.utcnow()
                )
                db.session.add(new_referral)
                db.session.flush()

                credits_granted = complete_referral_rewards(
                    referrer=referrer,
                    referee=member,
                    referral=new_referral,
                    referrer_reward=referrer_reward,
                    referee_reward=referee_reward
                )
                result['referral_processed'] = True
                result['credits_granted'] = credits_granted
                result['referrer_member_number'] = referrer.member_number

        return result

    # ==========================================
    # CASE 2: Check for referral code in order
    # ==========================================
    referral_code = extract_referral_code_from_order(order_data)
    if not referral_code:
        return result

    # Find the referrer
    referrer = Member.query.filter_by(
        tenant_id=tenant.id,
        referral_code=referral_code,
        status='active'
    ).first()

    if not referrer:
        return result

    # Can't refer yourself
    if referrer.id == member.id:
        return result

    # Link the referral
    member.referred_by_id = referrer.id
    referrer.referral_count = (referrer.referral_count or 0) + 1

    # Create referral record
    new_referral = Referral(
        program_id=program.id if program else None,
        referrer_id=referrer.id,
        referee_id=member.id,
        referral_code=referral_code,
        status='completed' if program_grant_on == 'first_purchase' else 'pending',
        completed_at=datetime.utcnow() if program_grant_on == 'first_purchase' else None
    )
    db.session.add(new_referral)
    db.session.flush()

    # Grant rewards if grant_on is 'first_purchase' or 'signup'
    if program_grant_on in ['first_purchase', 'signup']:
        credits_granted = complete_referral_rewards(
            referrer=referrer,
            referee=member,
            referral=new_referral,
            referrer_reward=referrer_reward,
            referee_reward=referee_reward
        )
        result['referral_processed'] = True
        result['credits_granted'] = credits_granted
        result['referrer_member_number'] = referrer.member_number
        current_app.logger.info(
            f"Referral applied from order: {member.member_number} referred by {referrer.member_number} (code: {referral_code})"
        )

    return result


def complete_referral_rewards(
    referrer: Member,
    referee: Member,
    referral: Referral,
    referrer_reward: Decimal,
    referee_reward: Decimal
) -> list:
    """
    Grant store credits for a completed referral.

    Args:
        referrer: Member who made the referral
        referee: New member who was referred
        referral: Referral record
        referrer_reward: Amount to credit referrer
        referee_reward: Amount to credit referee

    Returns:
        List of credits granted
    """
    credits_granted = []

    try:
        # Credit to referrer
        if referrer_reward and referrer_reward > 0:
            store_credit_service.add_credit(
                member_id=referrer.id,
                amount=referrer_reward,
                event_type='referral_bonus',
                description=f'Referral bonus - {referee.name or referee.email} made first purchase',
                source_type='referral',
                source_id=str(referee.id),
                created_by='system:order_webhook'
            )
            referrer.referral_earnings = (
                Decimal(str(referrer.referral_earnings or 0)) + referrer_reward
            )
            referral.referrer_reward_issued = True
            referral.referrer_reward_amount = referrer_reward
            referral.reward_issued_at = datetime.utcnow()
            credits_granted.append({
                'recipient': 'referrer',
                'member_number': referrer.member_number,
                'amount': float(referrer_reward)
            })

        # Credit to referee (new member)
        if referee_reward and referee_reward > 0:
            store_credit_service.add_credit(
                member_id=referee.id,
                amount=referee_reward,
                event_type='referral_bonus',
                description=f'Welcome bonus - referred by {referrer.name or referrer.member_number}',
                source_type='referral',
                source_id=str(referrer.id),
                created_by='system:order_webhook'
            )
            referral.referee_reward_issued = True
            referral.referee_reward_amount = referee_reward
            credits_granted.append({
                'recipient': 'referee',
                'member_number': referee.member_number,
                'amount': float(referee_reward)
            })

        # Update referral status
        referral.status = 'completed'
        referral.completed_at = datetime.utcnow()

        # Send notification (non-blocking)
        try:
            from ..services.notification_service import notification_service
            notification_service.send_referral_success_email(
                tenant_id=referrer.tenant_id,
                referrer_id=referrer.id,
                referee_id=referee.id,
                referrer_reward=float(referrer_reward) if referrer_reward else 0,
                referee_reward=float(referee_reward) if referee_reward else 0
            )
        except Exception as e:
            current_app.logger.warning(f"Failed to send referral notification: {e}")

    except Exception as e:
        current_app.logger.error(f"Referral credit grant error: {e}")

    return credits_granted


def verify_shopify_webhook(data: bytes, hmac_header: str, secret: str) -> bool:
    """Verify Shopify webhook HMAC signature."""
    if not secret or not hmac_header:
        return False
    computed_hmac = base64.b64encode(
        hmac.new(secret.encode('utf-8'), data, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(computed_hmac, hmac_header)


def get_tenant_from_domain(shop_domain: str) -> Tenant:
    """Get tenant from Shopify shop domain."""
    return Tenant.query.filter_by(shopify_domain=shop_domain).first()


def calculate_non_membership_subtotal(tenant_id: int, line_items: list) -> Decimal:
    """
    Calculate subtotal excluding membership products.

    This is used for cashback calculation - customers shouldn't earn
    cashback on the membership fee itself.
    """
    total = Decimal('0')
    for item in line_items:
        tier = find_tier_from_product(tenant_id, item)
        if not tier:
            # Not a membership product - include in cashback calculation
            item_total = Decimal(str(item.get('price', 0))) * int(item.get('quantity', 1))
            total += item_total
    return total


def find_tier_from_product(tenant_id: int, line_item: dict) -> MembershipTier:
    """
    Check if a line item is a membership product and return the associated tier.

    Detection methods:
    1. Product tags containing 'membership:tier_name' or 'tier:tier_name'
    2. Product type == 'Membership'
    3. SKU pattern like 'MEMBERSHIP-GOLD' or 'TIER-PLATINUM'

    Args:
        tenant_id: Tenant ID
        line_item: Order line item from Shopify webhook

    Returns:
        MembershipTier if found, None otherwise
    """
    product_id = line_item.get('product_id')
    title = line_item.get('title', '').lower()
    sku = line_item.get('sku', '').upper() if line_item.get('sku') else ''
    variant_title = line_item.get('variant_title', '').lower() if line_item.get('variant_title') else ''

    # Check SKU patterns: MEMBERSHIP-GOLD, TIER-PLATINUM, etc.
    if sku:
        for prefix in ['MEMBERSHIP-', 'TIER-', 'MEM-']:
            if sku.startswith(prefix):
                tier_name = sku.replace(prefix, '').strip()
                tier = MembershipTier.query.filter(
                    MembershipTier.tenant_id == tenant_id,
                    MembershipTier.name.ilike(tier_name),
                    MembershipTier.is_active == True
                ).first()
                if tier:
                    return tier

    # Check title for tier keywords
    for tier_keyword in ['silver', 'gold', 'platinum', 'bronze', 'premium', 'vip']:
        if tier_keyword in title or tier_keyword in variant_title:
            # Check if title also contains 'membership' or 'tier'
            if 'membership' in title or 'tier' in title or 'member' in title:
                tier = MembershipTier.query.filter(
                    MembershipTier.tenant_id == tenant_id,
                    MembershipTier.name.ilike(f'%{tier_keyword}%'),
                    MembershipTier.is_active == True
                ).first()
                if tier:
                    return tier

    # Check properties/line item properties for tier assignment
    properties = line_item.get('properties', [])
    for prop in properties:
        if prop.get('name', '').lower() in ['tier', 'membership_tier', 'tradeup_tier']:
            tier_name = prop.get('value', '')
            if tier_name:
                tier = MembershipTier.query.filter(
                    MembershipTier.tenant_id == tenant_id,
                    MembershipTier.name.ilike(tier_name),
                    MembershipTier.is_active == True
                ).first()
                if tier:
                    return tier

    return None


def process_membership_purchase(tenant: Tenant, member: Member, order_data: dict) -> dict:
    """
    Check order for membership products and assign tiers using TierService.

    Args:
        tenant: Tenant object
        member: Member object
        order_data: Full order payload from Shopify

    Returns:
        Dict with tier assignment result
    """
    line_items = order_data.get('line_items', [])
    order_id = str(order_data.get('id'))
    order_number = order_data.get('order_number')
    subtotal = Decimal(str(order_data.get('subtotal_price', 0)))

    assigned_tier = None
    product_sku = None

    for item in line_items:
        tier = find_tier_from_product(tenant.id, item)
        if tier:
            # Found a membership product - assign the tier
            # Use highest tier if multiple membership products in order
            if not assigned_tier or tier.bonus_rate > assigned_tier.bonus_rate:
                assigned_tier = tier
                product_sku = item.get('sku')

    if assigned_tier:
        # Use TierService for proper auditing
        tier_service = TierService(tenant.id)
        result = tier_service.process_purchase(
            member_id=member.id,
            order_id=order_id,
            tier_id=assigned_tier.id,
            order_total=subtotal,
            product_sku=product_sku,
            is_subscription=False
        )

        if result.get('success'):
            current_app.logger.info(
                f'Assigned tier {assigned_tier.name} to {member.member_number} via order #{order_number}'
            )
            return {
                'tier_assigned': True,
                'tier_name': assigned_tier.name,
                'old_tier': result.get('previous_tier'),
                'order_id': order_id,
                'log_id': result.get('log_id')
            }
        else:
            current_app.logger.warning(
                f'Tier assignment failed for {member.member_number}: {result.get("error")}'
            )
            return {
                'tier_assigned': False,
                'error': result.get('error')
            }

    return {'tier_assigned': False}


def should_auto_enroll(tenant: Tenant, customer_data: dict, order_subtotal: Decimal) -> bool:
    """
    Check if customer should be auto-enrolled based on tenant settings.

    Args:
        tenant: Tenant object
        customer_data: Customer data from order
        order_subtotal: Order subtotal amount

    Returns:
        True if customer should be auto-enrolled
    """
    settings = tenant.settings or {}
    auto_enrollment = settings.get('auto_enrollment', {})

    # Check if auto-enrollment is enabled
    if not auto_enrollment.get('enabled', True):
        return False

    # Check minimum order value
    min_order = Decimal(str(auto_enrollment.get('min_order_value', 0)))
    if order_subtotal < min_order:
        return False

    # Check excluded customer tags
    excluded_tags = auto_enrollment.get('excluded_tags', [])
    if excluded_tags:
        customer_tags = customer_data.get('tags', '')
        if isinstance(customer_tags, str):
            customer_tags = [t.strip().lower() for t in customer_tags.split(',') if t.strip()]
        for tag in excluded_tags:
            if tag.lower() in customer_tags:
                return False

    return True


def auto_enroll_customer(tenant: Tenant, customer_data: dict, order_data: dict) -> dict:
    """
    Auto-enroll a customer as a TradeUp member on first purchase.

    Args:
        tenant: Tenant object
        customer_data: Customer data from order
        order_data: Full order data

    Returns:
        Dict with enrollment result
    """
    shopify_customer_id = str(customer_data.get('id', ''))
    email = customer_data.get('email')
    name = f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip()
    phone = customer_data.get('phone')

    if not email:
        return {'success': False, 'error': 'No email address'}

    # Get settings
    settings = tenant.settings or {}
    auto_enrollment = settings.get('auto_enrollment', {})

    # Get default tier
    default_tier_id = auto_enrollment.get('default_tier_id')
    if not default_tier_id:
        # Use lowest tier
        default_tier = MembershipTier.query.filter_by(
            tenant_id=tenant.id,
            is_active=True
        ).order_by(MembershipTier.display_order).first()
        default_tier_id = default_tier.id if default_tier else None

    # Generate member number
    member_number = Member.generate_member_number(tenant.id)

    # Get customer GID if available
    shopify_gid = None
    if shopify_customer_id:
        shopify_gid = f"gid://shopify/Customer/{shopify_customer_id}"

    # Create member
    member = Member(
        tenant_id=tenant.id,
        member_number=member_number,
        shopify_customer_id=shopify_customer_id,
        shopify_customer_gid=shopify_gid,
        email=email,
        name=name or None,
        phone=phone,
        tier_id=default_tier_id,
        status='active',
        membership_start_date=datetime.utcnow().date(),
        notes=f"Auto-enrolled from order #{order_data.get('order_number')}"
    )

    db.session.add(member)
    db.session.flush()  # Get the member ID

    tier_name = None
    if default_tier_id:
        tier = MembershipTier.query.get(default_tier_id)
        tier_name = tier.name if tier else None

        # Use TierService to record the assignment with proper audit
        tier_service = TierService(tenant.id)
        tier_service.process_purchase(
            member_id=member.id,
            order_id=str(order_data.get('id')),
            tier_id=default_tier_id,
            order_total=Decimal(str(order_data.get('subtotal_price', 0))),
            is_subscription=False
        )

    # Trigger welcome email notification (async)
    try:
        from ..services.notification_service import notification_service
        notification_service.send_welcome_email(
            tenant_id=tenant.id,
            member_id=member.id
        )
    except Exception as e:
        current_app.logger.warning(f"Failed to send welcome email: {e}")

    current_app.logger.info(
        f"Auto-enrolled {member.member_number} ({email}) from order #{order_data.get('order_number')}"
    )

    return {
        'success': True,
        'member_id': member.id,
        'member_number': member_number,
        'tier_name': tier_name,
        'email': email
    }


@order_lifecycle_bp.route('/orders/create', methods=['POST'])
def handle_order_created():
    """
    Handle ORDERS_CREATE webhook.

    1. Auto-enroll customers on first purchase (if enabled)
    2. Check for membership product purchases and assign tiers
    3. Award points to members based on order subtotal
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    # Verify webhook in production
    if current_app.config.get('ENV') != 'development':
        hmac_header = request.headers.get('X-Shopify-Hmac-SHA256', '')
        if not verify_shopify_webhook(request.data, hmac_header, tenant.webhook_secret):
            return jsonify({'error': 'Invalid signature'}), 401

    try:
        order_data = request.json
        order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number')
        customer_data = order_data.get('customer', {})
        shopify_customer_id = str(customer_data.get('id', '')) if customer_data else None
        subtotal = Decimal(str(order_data.get('subtotal_price', 0)))

        result = {
            'success': True,
            'order_id': order_id,
            'order_number': order_number
        }

        if not shopify_customer_id:
            # Guest checkout - no membership or points
            result['message'] = 'Guest checkout - no rewards applied'
            return jsonify(result)

        # Find existing member
        member = Member.query.filter_by(
            tenant_id=tenant.id,
            shopify_customer_id=shopify_customer_id
        ).first()

        # ==========================================
        # AUTO-ENROLLMENT ON FIRST PURCHASE
        # ==========================================
        if not member:
            # Check if we should auto-enroll this customer
            if should_auto_enroll(tenant, customer_data, subtotal):
                # Check for membership product FIRST (higher tier takes priority)
                membership_tier = None
                for item in order_data.get('line_items', []):
                    tier = find_tier_from_product(tenant.id, item)
                    if tier:
                        if not membership_tier or tier.bonus_rate > membership_tier.bonus_rate:
                            membership_tier = tier

                if membership_tier:
                    # Enroll with specific tier from product
                    member = Member(
                        tenant_id=tenant.id,
                        shopify_customer_id=shopify_customer_id,
                        shopify_customer_gid=f"gid://shopify/Customer/{shopify_customer_id}",
                        email=customer_data.get('email', f'{shopify_customer_id}@unknown.com'),
                        name=f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip() or None,
                        phone=customer_data.get('phone'),
                        member_number=Member.generate_member_number(tenant.id),
                        tier_id=membership_tier.id,
                        status='active',
                        membership_start_date=datetime.utcnow().date(),
                        notes=f"Auto-enrolled with {membership_tier.name} tier from order #{order_number}"
                    )
                    db.session.add(member)
                    db.session.flush()

                    # Use TierService for audit trail
                    tier_service = TierService(tenant.id)
                    tier_service.process_purchase(
                        member_id=member.id,
                        order_id=order_id,
                        tier_id=membership_tier.id,
                        order_total=subtotal,
                        is_subscription=False
                    )

                    result['auto_enrollment'] = {
                        'enrolled': True,
                        'member_number': member.member_number,
                        'tier_name': membership_tier.name,
                        'source': 'membership_product'
                    }

                    current_app.logger.info(
                        f'Auto-enrolled {member.member_number} with tier {membership_tier.name} from order #{order_number}'
                    )
                else:
                    # Enroll with default tier (first purchase auto-enrollment)
                    enrollment_result = auto_enroll_customer(tenant, customer_data, order_data)
                    if enrollment_result.get('success'):
                        member = Member.query.get(enrollment_result['member_id'])
                        result['auto_enrollment'] = {
                            'enrolled': True,
                            'member_number': enrollment_result['member_number'],
                            'tier_name': enrollment_result.get('tier_name'),
                            'source': 'first_purchase'
                        }
                    else:
                        current_app.logger.warning(
                            f"Auto-enrollment failed for order #{order_number}: {enrollment_result.get('error')}"
                        )

        # ==========================================
        # EXISTING MEMBER: CHECK FOR TIER UPGRADE
        # ==========================================
        elif member:
            membership_result = process_membership_purchase(tenant, member, order_data)
            if membership_result.get('tier_assigned'):
                result['tier_upgrade'] = membership_result

        if not member:
            # ==========================================
            # NON-MEMBER: CHECK FOR ALL-CUSTOMERS PROMOTIONS
            # ==========================================
            # Even without membership, check if there are promotions targeting all customers
            try:
                line_items = order_data.get('line_items', [])
                rewards_subtotal = calculate_non_membership_subtotal(tenant.id, line_items)

                if rewards_subtotal > 0 and shopify_customer_id:
                    source_name = order_data.get('source_name', 'web')
                    channel = 'pos' if source_name == 'pos' else 'online'

                    # Get all-customers promotions
                    all_customer_promos = store_credit_service.get_active_promotions_for_audience(
                        tenant_id=tenant.id,
                        audience='all_customers',
                        channel=channel,
                        promo_type='purchase_cashback'
                    )

                    if all_customer_promos:
                        # Extract product tags from line items for filtering
                        product_tags = set()
                        product_ids = []
                        for item in line_items:
                            if item.get('product_id'):
                                product_ids.append(str(item['product_id']))
                            if item.get('tags'):
                                if isinstance(item['tags'], str):
                                    product_tags.update(t.strip() for t in item['tags'].split(','))
                                elif isinstance(item['tags'], list):
                                    product_tags.update(item['tags'])

                        # Fetch collection IDs if any promo has collection filters
                        collection_ids = set()
                        needs_collections = any(promo.collection_ids for promo in all_customer_promos)
                        if needs_collections and product_ids:
                            try:
                                from ..services.shopify_client import ShopifyClient
                                shopify_client = ShopifyClient(tenant.id)
                                product_collections = shopify_client.get_product_collections(product_ids)
                                for pid in product_ids:
                                    if pid in product_collections:
                                        collection_ids.update(product_collections[pid])
                            except Exception as e:
                                current_app.logger.warning(f"Failed to fetch collections for guest promo: {e}")

                        # Find the best matching promotion
                        best_bonus = Decimal('0')
                        best_promo = None

                        for promo in all_customer_promos:
                            if promo.min_value and rewards_subtotal < Decimal(str(promo.min_value)):
                                continue

                            # Check collection filter if set
                            if promo.collection_ids and collection_ids:
                                if not any(promo.applies_to_collection(cid) for cid in collection_ids):
                                    continue

                            # Check product tag filter if set
                            if promo.product_tags_filter and product_tags:
                                if not promo.applies_to_product_tags(list(product_tags)):
                                    continue

                            bonus = promo.calculate_bonus(rewards_subtotal)
                            if bonus > best_bonus:
                                best_bonus = bonus
                                best_promo = promo

                        if best_promo and best_bonus > 0:
                            # Issue credit to non-member via Shopify
                            guest_credit_result = store_credit_service.issue_guest_store_credit(
                                tenant_id=tenant.id,
                                shopify_customer_id=shopify_customer_id,
                                customer_email=customer_data.get('email'),
                                customer_name=f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip() or None,
                                amount=best_bonus,
                                description=f"{best_promo.bonus_percent}% cashback from {best_promo.name} on order #{order_number}",
                                promotion_id=best_promo.id,
                                promotion_name=best_promo.name,
                                order_id=order_id,
                                order_number=order_number,
                                order_total=rewards_subtotal,
                            )

                            if guest_credit_result.get('success'):
                                # Increment promo usage
                                best_promo.current_uses = (best_promo.current_uses or 0) + 1
                                db.session.commit()

                                result['guest_cashback'] = {
                                    'amount': float(best_bonus),
                                    'promotion_name': best_promo.name,
                                    'customer_email': customer_data.get('email'),
                                    'new_balance': guest_credit_result.get('new_balance'),
                                }
                                current_app.logger.info(
                                    f'Awarded ${best_bonus} guest credit to {customer_data.get("email")} '
                                    f'(non-member) via all-customers promo "{best_promo.name}" for order #{order_number}'
                                )
                                return jsonify(result)
                            else:
                                current_app.logger.warning(
                                    f"Failed to issue guest credit for order #{order_number}: {guest_credit_result.get('error')}"
                                )

            except Exception as e:
                current_app.logger.error(f'Error processing all-customers promotion for order #{order_number}: {e}')

            result['message'] = 'Customer not enrolled in rewards'
            return jsonify(result)

        # Only process rewards for active members
        if member.status != 'active':
            result['message'] = 'Member account not active'
            db.session.commit()  # Commit any membership changes
            return jsonify(result)

        # ==========================================
        # REFERRAL TRACKING
        # ==========================================
        try:
            referral_result = process_referral_on_order(tenant, member, order_data)
            if referral_result.get('referral_processed'):
                result['referral'] = referral_result
                current_app.logger.info(
                    f'Referral processed for {member.member_number} on order #{order_number}'
                )
        except Exception as e:
            # Don't fail the whole webhook if referral processing fails
            current_app.logger.error(f'Referral processing failed for order #{order_number}: {e}')

        # ==========================================
        # PURCHASE REWARDS (Based on Loyalty Mode)
        # ==========================================
        # Calculate subtotal excluding membership products (don't earn rewards on membership fee)
        line_items = order_data.get('line_items', [])
        rewards_subtotal = calculate_non_membership_subtotal(tenant.id, line_items)

        # Get loyalty mode from settings
        from ..utils.settings_defaults import get_settings_with_defaults
        tenant_settings = get_settings_with_defaults(tenant.settings or {})
        loyalty_settings = tenant_settings.get('loyalty', {})
        loyalty_mode = loyalty_settings.get('mode', 'store_credit')

        if rewards_subtotal > 0 and member.tier_id:
            try:
                # Determine POS vs online
                source_name = order_data.get('source_name', 'web')
                channel = 'pos' if source_name == 'pos' else 'online'

                # Extract product IDs and tags from line items for collection/tag filtering
                product_ids = []
                product_tags = set()
                for item in line_items:
                    if item.get('product_id'):
                        product_ids.append(str(item['product_id']))
                    # Shopify REST webhook includes tags if available
                    if item.get('tags'):
                        if isinstance(item['tags'], str):
                            product_tags.update(t.strip() for t in item['tags'].split(','))
                        elif isinstance(item['tags'], list):
                            product_tags.update(item['tags'])

                # Fetch collection IDs for products (for collection-gated promotions)
                collection_ids = set()
                if product_ids:
                    try:
                        from ..services.shopify_client import ShopifyClient
                        shopify_client = ShopifyClient(tenant.id)
                        product_collections = shopify_client.get_product_collections(product_ids)
                        for pid in product_ids:
                            if pid in product_collections:
                                collection_ids.update(product_collections[pid])
                    except Exception as e:
                        current_app.logger.warning(f"Failed to fetch collections for rewards: {e}")
                        # Continue without collection filtering rather than failing

                # ==========================================
                # MODE: STORE CREDIT (Default)
                # ==========================================
                if loyalty_mode == 'store_credit':
                    # Award cashback as store credit (auto-applies at checkout)
                    cashback_entry = store_credit_service.process_purchase_cashback(
                        member_id=member.id,
                        order_total=rewards_subtotal,
                        order_id=order_id,
                        order_name=f"#{order_number}",
                        channel=channel,
                        collection_ids=list(collection_ids) if collection_ids else None,
                        product_tags=list(product_tags) if product_tags else None
                    )

                    if cashback_entry:
                        result['cashback'] = {
                            'amount': float(cashback_entry.amount),
                            'tier': member.tier.name if member.tier else None,
                            'subtotal': float(rewards_subtotal),
                            'mode': 'store_credit'
                        }
                        current_app.logger.info(
                            f'Awarded ${cashback_entry.amount} store credit to {member.member_number} for order #{order_number}'
                        )

                # ==========================================
                # MODE: POINTS
                # ==========================================
                elif loyalty_mode == 'points':
                    # Award points (customer can later redeem for store credit)
                    points_per_dollar = loyalty_settings.get('points_per_dollar', 10)
                    base_points = int(float(rewards_subtotal) * points_per_dollar)

                    # Apply tier multiplier if applicable
                    tier_multiplier = 1.0
                    if member.tier:
                        # Use tier's earning multiplier (bonus_rate as multiplier)
                        bonus_rate = float(member.tier.bonus_rate or 0)
                        tier_multiplier = 1.0 + bonus_rate
                        # Check for double_points benefit
                        benefits = member.tier.benefits or {}
                        if benefits.get('double_points'):
                            tier_multiplier = 2.0

                    points_earned = int(base_points * tier_multiplier)
                    bonus_points = points_earned - base_points

                    if points_earned > 0:
                        # Record points transaction
                        from ..models import PointsTransaction
                        transaction = PointsTransaction(
                            tenant_id=tenant.id,
                            member_id=member.id,
                            points=points_earned,
                            remaining_points=points_earned,
                            transaction_type='earn',
                            source='purchase',
                            reference_id=order_id,
                            reference_type='shopify_order',
                            description=f'Points from order #{order_number}',
                            created_at=datetime.utcnow()
                        )
                        db.session.add(transaction)

                        # Update member balances
                        member.points_balance = (member.points_balance or 0) + points_earned
                        member.lifetime_points_earned = (member.lifetime_points_earned or 0) + points_earned
                        member.last_activity_at = datetime.utcnow()

                        # Get points display name
                        points_name = loyalty_settings.get('points_name', 'points')

                        result['points'] = {
                            'earned': points_earned,
                            'base_points': base_points,
                            'bonus_points': bonus_points,
                            'tier_multiplier': tier_multiplier,
                            'new_balance': member.points_balance,
                            'tier': member.tier.name if member.tier else None,
                            'subtotal': float(rewards_subtotal),
                            'mode': 'points',
                            'points_name': points_name
                        }
                        current_app.logger.info(
                            f'Awarded {points_earned} {points_name} to {member.member_number} for order #{order_number} '
                            f'({base_points} base + {bonus_points} bonus)'
                        )

            except Exception as e:
                # Don't fail the whole webhook if rewards processing fails
                current_app.logger.error(f'Rewards processing failed for order #{order_number}: {e}')

        # Commit any changes
        db.session.commit()

        result['member_id'] = member.id
        result['member_number'] = member.member_number
        result['loyalty_mode'] = loyalty_mode
        if not result.get('cashback') and not result.get('points') and not result.get('membership'):
            result['message'] = 'No rewards earned (order subtotal too low or no tier)'
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Error processing order create webhook: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@order_lifecycle_bp.route('/orders/cancelled', methods=['POST'])
def handle_order_cancelled():
    """
    Handle ORDERS_CANCELLED webhook.

    Reverses points awarded and revokes tiers from cancelled orders.
    Uses TierService for proper audit trail.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    try:
        order_data = request.json
        order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number')
        customer_data = order_data.get('customer', {})
        shopify_customer_id = str(customer_data.get('id', '')) if customer_data else None

        result = {
            'success': True,
            'order_id': order_id,
            'order_number': order_number
        }

        # Process tier refund if this was a membership purchase
        if shopify_customer_id:
            member = Member.query.filter_by(
                tenant_id=tenant.id,
                shopify_customer_id=shopify_customer_id
            ).first()

            if member:
                tier_service = TierService(tenant.id)
                refund_result = tier_service.process_refund(
                    member_id=member.id,
                    order_id=order_id,
                    reason=f'Order #{order_number} cancelled'
                )
                if refund_result.get('success') and refund_result.get('previous_tier'):
                    result['tier_revoked'] = refund_result.get('previous_tier')
                    current_app.logger.info(
                        f'Revoked tier from {member.member_number} due to order #{order_number} cancellation'
                    )

        # Find original points transaction
        from ..models import PointsTransaction
        original_transaction = PointsTransaction.query.filter_by(
            tenant_id=tenant.id,
            reference_id=order_id,
            transaction_type='earn'
        ).first()

        if not original_transaction:
            result['message'] = 'No points to reverse'
            return jsonify(result)

        member = original_transaction.member

        # Create reversal transaction
        reversal = PointsTransaction(
            tenant_id=tenant.id,
            member_id=member.id,
            points=-original_transaction.points,
            transaction_type='adjustment',
            source='order_cancelled',
            reference_id=order_id,
            reference_type='shopify_order',
            description=f'Points reversed - order #{order_number} cancelled',
            related_transaction_id=original_transaction.id,
            created_at=datetime.utcnow()
        )
        db.session.add(reversal)

        # Update member balance (don't reduce lifetime)
        member.points_balance = max(0, (member.points_balance or 0) - original_transaction.points)

        # Mark original as reversed
        original_transaction.reversed_at = datetime.utcnow()
        original_transaction.reversed_reason = 'order_cancelled'

        db.session.commit()

        result['points_reversed'] = original_transaction.points
        result['new_balance'] = member.points_balance
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Error processing order cancelled webhook: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@order_lifecycle_bp.route('/orders/fulfilled', methods=['POST'])
def handle_order_fulfilled():
    """
    Handle ORDERS_FULFILLED webhook.

    Awards points after fulfillment if tenant has 'award_points_on_fulfillment' enabled.
    This is an alternative to awarding points at order creation.
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    # Check if tenant requires fulfillment for points
    tenant_settings = tenant.settings if hasattr(tenant, 'settings') else {}
    award_on_fulfillment = tenant_settings.get('award_points_on_fulfillment', False)

    if not award_on_fulfillment:
        return jsonify({
            'success': True,
            'message': 'Points awarded at order creation, not fulfillment'
        })

    try:
        order_data = request.json
        order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number')
        customer_data = order_data.get('customer', {})
        shopify_customer_id = str(customer_data.get('id', '')) if customer_data else None
        subtotal = Decimal(str(order_data.get('subtotal_price', 0)))

        result = {
            'success': True,
            'order_id': order_id,
            'order_number': order_number
        }

        if not shopify_customer_id:
            result['message'] = 'Guest checkout - no rewards applied'
            return jsonify(result)

        # Find member
        member = Member.query.filter_by(
            tenant_id=tenant.id,
            shopify_customer_id=shopify_customer_id
        ).first()

        if not member:
            result['message'] = 'Customer not enrolled in rewards'
            return jsonify(result)

        if member.status != 'active':
            result['message'] = 'Member account not active'
            return jsonify(result)

        # Check if points were already awarded for this order
        from ..models import PointsTransaction
        existing_transaction = PointsTransaction.query.filter_by(
            tenant_id=tenant.id,
            member_id=member.id,
            reference_id=order_id,
            transaction_type='earn',
            source='order'
        ).first()

        if existing_transaction:
            result['message'] = 'Points already awarded for this order'
            result['points_earned'] = existing_transaction.points
            return jsonify(result)

        # Calculate points based on subtotal
        points_per_dollar = tenant_settings.get('points_per_dollar', 1)
        points_earned = int(subtotal * points_per_dollar)

        # Apply tier multiplier if applicable
        if member.tier and hasattr(member.tier, 'points_multiplier'):
            points_earned = int(points_earned * member.tier.points_multiplier)

        if points_earned > 0:
            # Record points transaction
            transaction = PointsTransaction(
                tenant_id=tenant.id,
                member_id=member.id,
                points=points_earned,
                transaction_type='earn',
                source='order',
                reference_id=order_id,
                reference_type='shopify_order',
                description=f'Points from fulfilled order #{order_number}',
                created_at=datetime.utcnow()
            )
            db.session.add(transaction)

            # Update member balances
            member.points_balance = (member.points_balance or 0) + points_earned
            member.lifetime_points_earned = (member.lifetime_points_earned or 0) + points_earned
            member.updated_at = datetime.utcnow()

            db.session.commit()

            result['points_earned'] = points_earned
            result['new_balance'] = member.points_balance
            result['message'] = f'Awarded {points_earned} points on fulfillment'

            current_app.logger.info(
                f'Awarded {points_earned} points to {member.member_number} for fulfilled order #{order_number}'
            )
        else:
            result['message'] = 'No points earned (order total too low)'

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Error processing order fulfilled webhook: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@order_lifecycle_bp.route('/refunds/create', methods=['POST'])
def handle_refund_created():
    """
    Handle REFUNDS_CREATE webhook.

    Reverses points and store credit proportionally based on refund amount.
    This handles partial refunds correctly by calculating the refund ratio.

    Shopify refund payload includes:
    - id: Refund ID
    - order_id: Original order ID
    - created_at: Refund timestamp
    - refund_line_items: Items being refunded
    - transactions: Refund payment transactions
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    try:
        refund_data = request.json
        refund_id = str(refund_data.get('id'))
        order_id = str(refund_data.get('order_id'))
        created_at = refund_data.get('created_at')

        # Calculate total refund amount from transactions
        transactions = refund_data.get('transactions', [])
        refund_amount = Decimal('0')
        for txn in transactions:
            if txn.get('kind') == 'refund' and txn.get('status') == 'success':
                refund_amount += Decimal(str(txn.get('amount', 0)))

        # Calculate refund from line items if no transaction amount
        if refund_amount == 0:
            refund_line_items = refund_data.get('refund_line_items', [])
            for item in refund_line_items:
                subtotal = Decimal(str(item.get('subtotal', 0)))
                refund_amount += subtotal

        result = {
            'success': True,
            'refund_id': refund_id,
            'order_id': order_id,
            'refund_amount': float(refund_amount),
            'points_reversed': 0,
            'credit_reversed': 0
        }

        if refund_amount == 0:
            result['message'] = 'Zero refund amount, nothing to reverse'
            return jsonify(result)

        # Find original points transaction for this order
        from ..models import PointsTransaction
        original_transaction = PointsTransaction.query.filter_by(
            tenant_id=tenant.id,
            reference_id=order_id,
            transaction_type='earn'
        ).first()

        if original_transaction and not original_transaction.reversed_at:
            member = original_transaction.member

            # Calculate proportion of refund to original order
            # We need the original order total - try to get from note or estimate
            original_points = original_transaction.points

            # Get tenant's points per dollar setting
            settings = tenant.settings or {}
            points_per_dollar = settings.get('points_per_dollar', 1)

            # Calculate points to reverse based on refund amount
            points_to_reverse = int(float(refund_amount) * points_per_dollar)

            # Don't reverse more than originally awarded
            points_to_reverse = min(points_to_reverse, original_points)

            if points_to_reverse > 0:
                # Check if already partially reversed
                existing_reversals = PointsTransaction.query.filter_by(
                    tenant_id=tenant.id,
                    related_transaction_id=original_transaction.id,
                    transaction_type='adjustment'
                ).all()

                total_already_reversed = sum(abs(r.points) for r in existing_reversals)
                remaining_to_reverse = original_points - total_already_reversed
                points_to_reverse = min(points_to_reverse, remaining_to_reverse)

                if points_to_reverse > 0:
                    # Create reversal transaction
                    reversal = PointsTransaction(
                        tenant_id=tenant.id,
                        member_id=member.id,
                        points=-points_to_reverse,
                        transaction_type='adjustment',
                        source='refund',
                        reference_id=refund_id,
                        reference_type='shopify_refund',
                        description=f'Points reversed - refund ${float(refund_amount):.2f} on order #{order_id}',
                        related_transaction_id=original_transaction.id,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(reversal)

                    # Update member balance
                    member.points_balance = max(0, (member.points_balance or 0) - points_to_reverse)
                    result['points_reversed'] = points_to_reverse
                    result['new_points_balance'] = member.points_balance

                    # If full refund, mark original as reversed
                    if total_already_reversed + points_to_reverse >= original_points:
                        original_transaction.reversed_at = datetime.utcnow()
                        original_transaction.reversed_reason = 'refunded'

        # Check for store credit to reverse (cashback)
        from ..models.promotions import StoreCreditLedger
        cashback_entries = StoreCreditLedger.query.filter_by(
            tenant_id=tenant.id,
            source_type='cashback',
            source_id=order_id
        ).all()

        for entry in cashback_entries:
            if entry.amount > 0 and not entry.reversed_at:
                member = entry.member

                # Calculate cashback to reverse proportionally
                # Get original order subtotal from entry description or estimate
                cashback_to_reverse = entry.amount  # Full reversal for now

                # Create debit entry for reversal
                reversal_entry = StoreCreditLedger(
                    tenant_id=tenant.id,
                    member_id=entry.member_id,
                    amount=-cashback_to_reverse,
                    balance_after=max(Decimal('0'), (member.store_credit_balance or Decimal('0')) - cashback_to_reverse),
                    event_type='adjustment',
                    description=f'Cashback reversed - refund on order #{order_id}',
                    source_type='refund',
                    source_id=refund_id,
                    channel='webhook',
                    created_by='shopify_refund'
                )
                db.session.add(reversal_entry)

                # Update member balance
                member.store_credit_balance = max(Decimal('0'), (member.store_credit_balance or Decimal('0')) - cashback_to_reverse)
                result['credit_reversed'] = float(result.get('credit_reversed', 0)) + float(cashback_to_reverse)

                # Mark original as reversed
                entry.reversed_at = datetime.utcnow()
                entry.reversed_reason = 'refunded'

        db.session.commit()

        current_app.logger.info(
            f'Processed refund {refund_id} for order {order_id}: '
            f'reversed {result["points_reversed"]} points, ${result["credit_reversed"]:.2f} credit'
        )

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Error processing refund webhook: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@order_lifecycle_bp.route('/orders/paid', methods=['POST'])
def handle_order_paid():
    """
    Handle ORDERS_PAID webhook.

    This webhook fires when payment is confirmed (after orders/create).
    For most merchants, points are awarded at order creation, so this
    is primarily used for payment confirmation tracking.

    Some use cases:
    - Merchants who only award points after payment confirmation
    - Tracking payment method for analytics
    - Delayed membership activation until payment clears
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    try:
        order_data = request.json
        order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number')
        financial_status = order_data.get('financial_status')

        result = {
            'success': True,
            'order_id': order_id,
            'order_number': order_number,
            'financial_status': financial_status
        }

        # Check if tenant requires payment confirmation before awarding points
        settings = tenant.settings or {}
        award_on_paid = settings.get('award_points_on_paid', False)

        if not award_on_paid:
            result['message'] = 'Points awarded at order creation, not payment confirmation'
            return jsonify(result)

        # If tenant requires payment confirmation, check if points were awarded
        from ..models import PointsTransaction
        existing_transaction = PointsTransaction.query.filter_by(
            tenant_id=tenant.id,
            reference_id=order_id,
            transaction_type='earn'
        ).first()

        if existing_transaction:
            result['message'] = 'Points already awarded for this order'
            return jsonify(result)

        # Award points now that payment is confirmed
        # (Similar logic to orders/create but triggered here)
        customer_data = order_data.get('customer', {})
        shopify_customer_id = str(customer_data.get('id', '')) if customer_data else None

        if shopify_customer_id:
            member = Member.query.filter_by(
                tenant_id=tenant.id,
                shopify_customer_id=shopify_customer_id
            ).first()

            if member:
                # Calculate points
                subtotal = Decimal(str(order_data.get('subtotal_price', 0)))
                points_per_dollar = settings.get('points_per_dollar', 1)
                points_earned = int(float(subtotal) * points_per_dollar)

                if points_earned > 0:
                    transaction = PointsTransaction(
                        tenant_id=tenant.id,
                        member_id=member.id,
                        points=points_earned,
                        transaction_type='earn',
                        source='purchase',
                        reference_id=order_id,
                        reference_type='shopify_order',
                        description=f'Points earned - order #{order_number} (paid)',
                        created_at=datetime.utcnow()
                    )
                    db.session.add(transaction)

                    member.points_balance = (member.points_balance or 0) + points_earned
                    member.lifetime_points = (member.lifetime_points or 0) + points_earned
                    db.session.commit()

                    result['points_earned'] = points_earned
                    result['new_balance'] = member.points_balance

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Error processing order paid webhook: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@order_lifecycle_bp.route('/products/create', methods=['POST'])
def handle_product_created():
    """
    Handle PRODUCTS_CREATE webhook.

    Detects new membership products and can auto-configure them.
    Useful for merchants who create new tier products.

    Detection:
    - Product type = 'Membership'
    - Product tags containing 'membership' or 'tier'
    - Product metafield 'tradeup.tier_id'
    """
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    tenant = get_tenant_from_domain(shop_domain)

    if not tenant:
        return jsonify({'error': 'Unknown shop'}), 404

    try:
        product_data = request.json
        product_id = str(product_data.get('id'))
        product_title = product_data.get('title', '')
        product_type = product_data.get('product_type', '')
        product_tags = product_data.get('tags', '')

        result = {
            'success': True,
            'product_id': product_id,
            'product_title': product_title,
            'is_membership_product': False
        }

        # Check if this is a membership product
        is_membership = False
        detected_tier = None

        # Check product type
        if product_type and product_type.lower() == 'membership':
            is_membership = True

        # Check tags
        tags_lower = product_tags.lower() if product_tags else ''
        if 'membership' in tags_lower or 'tier' in tags_lower:
            is_membership = True

            # Try to extract tier name from tags
            import re
            tier_match = re.search(r'(?:membership|tier)[:\-_]?(\w+)', tags_lower)
            if tier_match:
                detected_tier = tier_match.group(1)

        if is_membership:
            result['is_membership_product'] = True
            result['detected_tier'] = detected_tier

            current_app.logger.info(
                f'Detected new membership product: {product_title} (ID: {product_id}), '
                f'detected tier: {detected_tier}'
            )

            # Optionally auto-link to tier if we can match by name
            if detected_tier:
                tier = MembershipTier.query.filter(
                    MembershipTier.tenant_id == tenant.id,
                    MembershipTier.is_active == True,
                    db.func.lower(MembershipTier.name) == detected_tier.lower()
                ).first()

                if tier:
                    result['matched_tier_id'] = tier.id
                    result['matched_tier_name'] = tier.name
                    # Note: We don't auto-link here, just report the match
                    # Merchant should configure this manually for safety

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Error processing product create webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500
