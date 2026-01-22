"""
Loyalty Page Analytics API Endpoints

API endpoints for tracking and retrieving loyalty page analytics.
Includes public tracking endpoint (no auth) and admin analytics dashboard (auth required).
"""

import logging
from datetime import datetime, timedelta, date
from flask import Blueprint, request, jsonify, g, Response
from sqlalchemy import func, distinct, case

from app import db
from app.models.loyalty_page import LoyaltyPage
from app.models.loyalty_page_analytics import (
    LoyaltyPageView,
    LoyaltyPageEngagement,
    LoyaltyPageCTAClick,
    LoyaltyPageAnalyticsSummary,
)
from app.models.tenant import Tenant
from app.middleware.shopify_auth import require_shopify_auth

logger = logging.getLogger(__name__)

loyalty_page_analytics_bp = Blueprint('loyalty_page_analytics', __name__)


# ==============================================================================
# PUBLIC TRACKING ENDPOINTS (No auth - called from storefront)
# ==============================================================================

@loyalty_page_analytics_bp.route('/track/view', methods=['POST', 'OPTIONS'])
def track_page_view():
    """
    Track a page view event.

    This endpoint is called from the storefront tracking script.
    No authentication required - uses shop domain from request.

    Expected JSON body:
    {
        "shop": "store.myshopify.com",
        "session_id": "abc123",
        "device_type": "mobile",
        "browser": "Chrome",
        "referrer": "https://google.com",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "summer_sale",
        "member_id": 123,  // optional
        "is_member": false
    }
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return _cors_response({'ok': True})

    try:
        data = request.get_json(silent=True) or {}

        # Validate shop domain
        shop = data.get('shop', '')
        if not shop:
            return _cors_response({'error': 'Shop domain required'}, 400)

        # Find tenant
        tenant = Tenant.query.filter_by(shopify_domain=shop).first()
        if not tenant:
            # Shop not found - log and return success to avoid retries
            logger.info(f"Page view tracking for unknown shop: {shop}")
            return _cors_response({'ok': True, 'tracked': False})

        # Find active loyalty page
        page = LoyaltyPage.query.filter_by(
            tenant_id=tenant.id,
            is_published=True
        ).first()

        # Create page view record
        view = LoyaltyPageView(
            tenant_id=tenant.id,
            page_id=page.id if page else None,
            session_id=data.get('session_id'),
            device_type=data.get('device_type'),
            browser=data.get('browser'),
            referrer=data.get('referrer', '')[:500] if data.get('referrer') else None,
            utm_source=data.get('utm_source', '')[:100] if data.get('utm_source') else None,
            utm_medium=data.get('utm_medium', '')[:100] if data.get('utm_medium') else None,
            utm_campaign=data.get('utm_campaign', '')[:100] if data.get('utm_campaign') else None,
            member_id=data.get('member_id'),
            is_member=data.get('is_member', False),
            viewed_at=datetime.utcnow()
        )

        db.session.add(view)
        db.session.commit()

        logger.debug(f"Page view tracked: tenant={tenant.id}, session={data.get('session_id')}")
        return _cors_response({'ok': True, 'tracked': True, 'view_id': view.id})

    except Exception as e:
        logger.error(f"Page view tracking error: {e}")
        db.session.rollback()
        # Always return success to prevent retries
        return _cors_response({'ok': True, 'error': 'internal'})


@loyalty_page_analytics_bp.route('/track/engagement', methods=['POST', 'OPTIONS'])
def track_section_engagement():
    """
    Track section engagement (scroll depth, time in view).

    Expected JSON body:
    {
        "shop": "store.myshopify.com",
        "session_id": "abc123",
        "sections": [
            {
                "section_id": "hero",
                "section_type": "hero",
                "time_in_view_seconds": 5,
                "scroll_depth_percent": 100,
                "was_visible": true
            },
            ...
        ]
    }
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return _cors_response({'ok': True})

    try:
        data = request.get_json(silent=True) or {}

        # Validate shop domain
        shop = data.get('shop', '')
        if not shop:
            return _cors_response({'error': 'Shop domain required'}, 400)

        # Find tenant
        tenant = Tenant.query.filter_by(shopify_domain=shop).first()
        if not tenant:
            return _cors_response({'ok': True, 'tracked': False})

        # Find active loyalty page
        page = LoyaltyPage.query.filter_by(
            tenant_id=tenant.id,
            is_published=True
        ).first()

        # Track each section
        sections = data.get('sections', [])
        tracked_count = 0

        for section_data in sections:
            engagement = LoyaltyPageEngagement(
                tenant_id=tenant.id,
                page_id=page.id if page else None,
                session_id=data.get('session_id'),
                section_id=section_data.get('section_id', 'unknown'),
                section_type=section_data.get('section_type'),
                time_in_view_seconds=section_data.get('time_in_view_seconds', 0),
                scroll_depth_percent=min(100, max(0, section_data.get('scroll_depth_percent', 0))),
                was_visible=section_data.get('was_visible', False),
                recorded_at=datetime.utcnow()
            )
            db.session.add(engagement)
            tracked_count += 1

        db.session.commit()

        logger.debug(f"Section engagement tracked: tenant={tenant.id}, sections={tracked_count}")
        return _cors_response({'ok': True, 'tracked': True, 'sections_tracked': tracked_count})

    except Exception as e:
        logger.error(f"Section engagement tracking error: {e}")
        db.session.rollback()
        return _cors_response({'ok': True, 'error': 'internal'})


@loyalty_page_analytics_bp.route('/track/click', methods=['POST', 'OPTIONS'])
def track_cta_click():
    """
    Track CTA (call-to-action) click events.

    Expected JSON body:
    {
        "shop": "store.myshopify.com",
        "session_id": "abc123",
        "cta_id": "hero_cta",
        "cta_text": "Join Now",
        "cta_url": "/account/register",
        "section_id": "hero",
        "member_id": 123,
        "is_member": false
    }
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return _cors_response({'ok': True})

    try:
        data = request.get_json(silent=True) or {}

        # Validate shop domain
        shop = data.get('shop', '')
        if not shop:
            return _cors_response({'error': 'Shop domain required'}, 400)

        # Find tenant
        tenant = Tenant.query.filter_by(shopify_domain=shop).first()
        if not tenant:
            return _cors_response({'ok': True, 'tracked': False})

        # Find active loyalty page
        page = LoyaltyPage.query.filter_by(
            tenant_id=tenant.id,
            is_published=True
        ).first()

        # Create click record
        click = LoyaltyPageCTAClick(
            tenant_id=tenant.id,
            page_id=page.id if page else None,
            session_id=data.get('session_id'),
            cta_id=data.get('cta_id', 'unknown'),
            cta_text=data.get('cta_text', '')[:200] if data.get('cta_text') else None,
            cta_url=data.get('cta_url', '')[:500] if data.get('cta_url') else None,
            section_id=data.get('section_id'),
            member_id=data.get('member_id'),
            is_member=data.get('is_member', False),
            clicked_at=datetime.utcnow()
        )

        db.session.add(click)
        db.session.commit()

        logger.debug(f"CTA click tracked: tenant={tenant.id}, cta={data.get('cta_id')}")
        return _cors_response({'ok': True, 'tracked': True, 'click_id': click.id})

    except Exception as e:
        logger.error(f"CTA click tracking error: {e}")
        db.session.rollback()
        return _cors_response({'ok': True, 'error': 'internal'})


# ==============================================================================
# ADMIN ANALYTICS ENDPOINTS (Auth required)
# ==============================================================================

@loyalty_page_analytics_bp.route('/dashboard', methods=['GET'])
@require_shopify_auth
def get_analytics_dashboard():
    """
    Get analytics dashboard data for the loyalty page.

    Query params:
        period: '7', '30', '90' (days, default: '30')

    Returns comprehensive analytics including:
    - Overview metrics (views, visitors, engagement)
    - Traffic breakdown (device, referrer, UTM)
    - Section engagement metrics
    - CTA performance
    - Daily trends
    """
    tenant_id = g.tenant_id
    period = request.args.get('period', '30')

    try:
        days = int(period)
    except ValueError:
        days = 30

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Previous period for comparison
    prev_start = start_date - timedelta(days=days)
    prev_end = start_date

    try:
        # Get active loyalty page
        page = LoyaltyPage.query.filter_by(tenant_id=tenant_id).first()
        page_id = page.id if page else None

        # ==================== OVERVIEW METRICS ====================
        # Current period
        total_views = LoyaltyPageView.query.filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= start_date
        ).count()

        unique_visitors = db.session.query(
            func.count(distinct(LoyaltyPageView.session_id))
        ).filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= start_date,
            LoyaltyPageView.session_id.isnot(None)
        ).scalar() or 0

        member_views = LoyaltyPageView.query.filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= start_date,
            LoyaltyPageView.is_member == True
        ).count()

        # Previous period for comparison
        prev_views = LoyaltyPageView.query.filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= prev_start,
            LoyaltyPageView.viewed_at < prev_end
        ).count()

        prev_visitors = db.session.query(
            func.count(distinct(LoyaltyPageView.session_id))
        ).filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= prev_start,
            LoyaltyPageView.viewed_at < prev_end,
            LoyaltyPageView.session_id.isnot(None)
        ).scalar() or 0

        # ==================== DEVICE BREAKDOWN ====================
        device_counts = db.session.query(
            LoyaltyPageView.device_type,
            func.count(LoyaltyPageView.id)
        ).filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= start_date
        ).group_by(LoyaltyPageView.device_type).all()

        device_breakdown = {
            'desktop': 0,
            'mobile': 0,
            'tablet': 0,
            'unknown': 0
        }
        for device_type, count in device_counts:
            key = device_type if device_type in device_breakdown else 'unknown'
            device_breakdown[key] = count

        # ==================== TRAFFIC SOURCES ====================
        # Top referrers
        top_referrers = db.session.query(
            LoyaltyPageView.referrer,
            func.count(LoyaltyPageView.id).label('count')
        ).filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= start_date,
            LoyaltyPageView.referrer.isnot(None),
            LoyaltyPageView.referrer != ''
        ).group_by(LoyaltyPageView.referrer).order_by(
            func.count(LoyaltyPageView.id).desc()
        ).limit(10).all()

        referrers = [{'referrer': r, 'count': c} for r, c in top_referrers]

        # UTM sources
        utm_sources = db.session.query(
            LoyaltyPageView.utm_source,
            func.count(LoyaltyPageView.id).label('count')
        ).filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= start_date,
            LoyaltyPageView.utm_source.isnot(None)
        ).group_by(LoyaltyPageView.utm_source).order_by(
            func.count(LoyaltyPageView.id).desc()
        ).limit(10).all()

        utm_list = [{'source': s, 'count': c} for s, c in utm_sources]

        # ==================== SECTION ENGAGEMENT ====================
        section_engagement = db.session.query(
            LoyaltyPageEngagement.section_id,
            func.count(LoyaltyPageEngagement.id).label('views'),
            func.avg(LoyaltyPageEngagement.time_in_view_seconds).label('avg_time'),
            func.avg(LoyaltyPageEngagement.scroll_depth_percent).label('avg_scroll'),
            func.sum(case((LoyaltyPageEngagement.was_visible == True, 1), else_=0)).label('visible_count')
        ).filter(
            LoyaltyPageEngagement.tenant_id == tenant_id,
            LoyaltyPageEngagement.recorded_at >= start_date
        ).group_by(LoyaltyPageEngagement.section_id).all()

        sections = [
            {
                'section_id': se.section_id,
                'views': se.views,
                'avg_time_seconds': round(float(se.avg_time or 0), 1),
                'avg_scroll_depth': round(float(se.avg_scroll or 0), 1),
                'visibility_rate': round(se.visible_count / se.views * 100, 1) if se.views > 0 else 0
            }
            for se in section_engagement
        ]

        # ==================== CTA PERFORMANCE ====================
        total_clicks = LoyaltyPageCTAClick.query.filter(
            LoyaltyPageCTAClick.tenant_id == tenant_id,
            LoyaltyPageCTAClick.clicked_at >= start_date
        ).count()

        unique_clickers = db.session.query(
            func.count(distinct(LoyaltyPageCTAClick.session_id))
        ).filter(
            LoyaltyPageCTAClick.tenant_id == tenant_id,
            LoyaltyPageCTAClick.clicked_at >= start_date,
            LoyaltyPageCTAClick.session_id.isnot(None)
        ).scalar() or 0

        # Click rate
        click_rate = (unique_clickers / unique_visitors * 100) if unique_visitors > 0 else 0

        # Top CTAs
        top_ctas = db.session.query(
            LoyaltyPageCTAClick.cta_id,
            LoyaltyPageCTAClick.cta_text,
            LoyaltyPageCTAClick.section_id,
            func.count(LoyaltyPageCTAClick.id).label('clicks')
        ).filter(
            LoyaltyPageCTAClick.tenant_id == tenant_id,
            LoyaltyPageCTAClick.clicked_at >= start_date
        ).group_by(
            LoyaltyPageCTAClick.cta_id,
            LoyaltyPageCTAClick.cta_text,
            LoyaltyPageCTAClick.section_id
        ).order_by(func.count(LoyaltyPageCTAClick.id).desc()).limit(10).all()

        cta_list = [
            {
                'cta_id': cta.cta_id,
                'cta_text': cta.cta_text,
                'section_id': cta.section_id,
                'clicks': cta.clicks
            }
            for cta in top_ctas
        ]

        # ==================== DAILY TRENDS ====================
        daily_views = db.session.query(
            func.date(LoyaltyPageView.viewed_at).label('date'),
            func.count(LoyaltyPageView.id).label('views'),
            func.count(distinct(LoyaltyPageView.session_id)).label('visitors')
        ).filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= start_date
        ).group_by(func.date(LoyaltyPageView.viewed_at)).order_by('date').all()

        daily_clicks = db.session.query(
            func.date(LoyaltyPageCTAClick.clicked_at).label('date'),
            func.count(LoyaltyPageCTAClick.id).label('clicks')
        ).filter(
            LoyaltyPageCTAClick.tenant_id == tenant_id,
            LoyaltyPageCTAClick.clicked_at >= start_date
        ).group_by(func.date(LoyaltyPageCTAClick.clicked_at)).all()

        clicks_by_date = {str(d): c for d, c in daily_clicks}

        trends = []
        for row in daily_views:
            date_str = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            trends.append({
                'date': date_str,
                'views': row.views,
                'visitors': row.visitors,
                'clicks': clicks_by_date.get(date_str, 0)
            })

        # ==================== CALCULATE CHANGES ====================
        def calc_change(current, previous):
            if previous > 0:
                pct = ((current - previous) / previous) * 100
            else:
                pct = 100 if current > 0 else 0
            return {
                'current': current,
                'previous': previous,
                'change_pct': round(pct, 1),
                'trend': 'up' if pct > 0 else 'down' if pct < 0 else 'flat'
            }

        return jsonify({
            'success': True,
            'period_days': days,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'overview': {
                'total_views': calc_change(total_views, prev_views),
                'unique_visitors': calc_change(unique_visitors, prev_visitors),
                'member_views': member_views,
                'guest_views': total_views - member_views,
            },
            'device_breakdown': device_breakdown,
            'traffic_sources': {
                'referrers': referrers,
                'utm_sources': utm_list
            },
            'section_engagement': sections,
            'cta_performance': {
                'total_clicks': total_clicks,
                'unique_clickers': unique_clickers,
                'click_rate': round(click_rate, 2),
                'top_ctas': cta_list
            },
            'daily_trends': trends,
            'page': {
                'id': page_id,
                'is_published': page.is_published if page else False,
                'version': page.version if page else 0
            }
        })

    except Exception as e:
        logger.error(f"Analytics dashboard error: {e}")
        return jsonify({'error': str(e)}), 500


@loyalty_page_analytics_bp.route('/summary/refresh', methods=['POST'])
@require_shopify_auth
def refresh_analytics_summary():
    """
    Manually refresh the daily analytics summary.

    Aggregates raw data into summary tables for faster queries.
    Normally run via scheduled job, but can be triggered manually.
    """
    tenant_id = g.tenant_id

    try:
        # Get the date to summarize (default: yesterday)
        summary_date = date.today() - timedelta(days=1)

        page = LoyaltyPage.query.filter_by(tenant_id=tenant_id).first()
        page_id = page.id if page else None

        # Get or create summary record
        summary = LoyaltyPageAnalyticsSummary.get_or_create(
            tenant_id=tenant_id,
            page_id=page_id,
            summary_date=summary_date
        )

        # Calculate metrics for the day
        day_start = datetime.combine(summary_date, datetime.min.time())
        day_end = datetime.combine(summary_date, datetime.max.time())

        # View metrics
        summary.total_views = LoyaltyPageView.query.filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= day_start,
            LoyaltyPageView.viewed_at <= day_end
        ).count()

        summary.unique_visitors = db.session.query(
            func.count(distinct(LoyaltyPageView.session_id))
        ).filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= day_start,
            LoyaltyPageView.viewed_at <= day_end,
            LoyaltyPageView.session_id.isnot(None)
        ).scalar() or 0

        summary.member_views = LoyaltyPageView.query.filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= day_start,
            LoyaltyPageView.viewed_at <= day_end,
            LoyaltyPageView.is_member == True
        ).count()

        summary.guest_views = summary.total_views - summary.member_views

        # Device breakdown
        device_counts = db.session.query(
            LoyaltyPageView.device_type,
            func.count(LoyaltyPageView.id)
        ).filter(
            LoyaltyPageView.tenant_id == tenant_id,
            LoyaltyPageView.viewed_at >= day_start,
            LoyaltyPageView.viewed_at <= day_end
        ).group_by(LoyaltyPageView.device_type).all()

        for device_type, count in device_counts:
            if device_type == 'desktop':
                summary.desktop_views = count
            elif device_type == 'mobile':
                summary.mobile_views = count
            elif device_type == 'tablet':
                summary.tablet_views = count

        # Engagement metrics
        avg_scroll = db.session.query(
            func.avg(LoyaltyPageEngagement.scroll_depth_percent)
        ).filter(
            LoyaltyPageEngagement.tenant_id == tenant_id,
            LoyaltyPageEngagement.recorded_at >= day_start,
            LoyaltyPageEngagement.recorded_at <= day_end
        ).scalar()
        summary.avg_scroll_depth = float(avg_scroll or 0)

        avg_time = db.session.query(
            func.avg(LoyaltyPageEngagement.time_in_view_seconds)
        ).filter(
            LoyaltyPageEngagement.tenant_id == tenant_id,
            LoyaltyPageEngagement.recorded_at >= day_start,
            LoyaltyPageEngagement.recorded_at <= day_end
        ).scalar()
        summary.avg_time_on_page_seconds = float(avg_time or 0)

        # CTA metrics
        summary.total_cta_clicks = LoyaltyPageCTAClick.query.filter(
            LoyaltyPageCTAClick.tenant_id == tenant_id,
            LoyaltyPageCTAClick.clicked_at >= day_start,
            LoyaltyPageCTAClick.clicked_at <= day_end
        ).count()

        summary.unique_cta_clickers = db.session.query(
            func.count(distinct(LoyaltyPageCTAClick.session_id))
        ).filter(
            LoyaltyPageCTAClick.tenant_id == tenant_id,
            LoyaltyPageCTAClick.clicked_at >= day_start,
            LoyaltyPageCTAClick.clicked_at <= day_end,
            LoyaltyPageCTAClick.session_id.isnot(None)
        ).scalar() or 0

        summary.cta_click_rate = (
            summary.unique_cta_clickers / summary.unique_visitors * 100
            if summary.unique_visitors > 0 else 0
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'summary_date': summary_date.isoformat(),
            'summary': summary.to_dict()
        })

    except Exception as e:
        logger.error(f"Analytics summary refresh error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _cors_response(data, status=200):
    """Helper to create CORS-enabled response for tracking endpoints."""
    response = jsonify(data)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Cache-Control'] = 'no-store'
    return response, status
