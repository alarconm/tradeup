"""
Loyalty Page Analytics Models

Database models to store page view and engagement analytics for the loyalty page builder.
"""

from datetime import datetime, date
from app import db


class LoyaltyPageView(db.Model):
    """
    Individual page view events for the loyalty landing page.

    Tracks each page view with metadata like device type, referrer, and session info.
    Aggregated daily for dashboard reporting.
    """

    __tablename__ = 'loyalty_page_views'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    page_id = db.Column(db.Integer, db.ForeignKey('loyalty_pages.id'), nullable=True, index=True)

    # Session identification (anonymous tracking)
    session_id = db.Column(db.String(64), nullable=True, index=True)

    # Device and browser info
    device_type = db.Column(db.String(20), nullable=True)  # 'desktop', 'mobile', 'tablet'
    browser = db.Column(db.String(50), nullable=True)

    # Traffic source
    referrer = db.Column(db.String(500), nullable=True)
    utm_source = db.Column(db.String(100), nullable=True)
    utm_medium = db.Column(db.String(100), nullable=True)
    utm_campaign = db.Column(db.String(100), nullable=True)

    # Member tracking (if logged in)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True, index=True)
    is_member = db.Column(db.Boolean, default=False, nullable=False)

    # Timing
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('loyalty_page_views', lazy='dynamic'))
    page = db.relationship('LoyaltyPage', backref=db.backref('views', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_page_views_tenant_date', 'tenant_id', 'viewed_at'),
    )

    def __repr__(self):
        return f'<LoyaltyPageView {self.id} tenant={self.tenant_id} at={self.viewed_at}>'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'page_id': self.page_id,
            'session_id': self.session_id,
            'device_type': self.device_type,
            'browser': self.browser,
            'referrer': self.referrer,
            'utm_source': self.utm_source,
            'utm_medium': self.utm_medium,
            'utm_campaign': self.utm_campaign,
            'member_id': self.member_id,
            'is_member': self.is_member,
            'viewed_at': self.viewed_at.isoformat() if self.viewed_at else None,
        }


class LoyaltyPageEngagement(db.Model):
    """
    Section engagement tracking for the loyalty page.

    Tracks scroll depth, time spent, and interactions with specific sections.
    """

    __tablename__ = 'loyalty_page_engagements'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    page_id = db.Column(db.Integer, db.ForeignKey('loyalty_pages.id'), nullable=True, index=True)

    # Session identification
    session_id = db.Column(db.String(64), nullable=True, index=True)

    # Section tracking
    section_id = db.Column(db.String(50), nullable=False)  # e.g., 'hero', 'tiers', 'rewards'
    section_type = db.Column(db.String(50), nullable=True)

    # Engagement metrics
    time_in_view_seconds = db.Column(db.Integer, default=0, nullable=False)  # How long section was visible
    scroll_depth_percent = db.Column(db.Integer, default=0, nullable=False)  # 0-100
    was_visible = db.Column(db.Boolean, default=False, nullable=False)  # Did user scroll to this section

    # Timing
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('loyalty_page_engagements', lazy='dynamic'))
    page = db.relationship('LoyaltyPage', backref=db.backref('engagements', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_page_engagement_tenant_date', 'tenant_id', 'recorded_at'),
        db.Index('idx_page_engagement_section', 'tenant_id', 'section_id'),
    )

    def __repr__(self):
        return f'<LoyaltyPageEngagement {self.id} section={self.section_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'page_id': self.page_id,
            'session_id': self.session_id,
            'section_id': self.section_id,
            'section_type': self.section_type,
            'time_in_view_seconds': self.time_in_view_seconds,
            'scroll_depth_percent': self.scroll_depth_percent,
            'was_visible': self.was_visible,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
        }


class LoyaltyPageCTAClick(db.Model):
    """
    CTA (Call-to-Action) click tracking for the loyalty page.

    Tracks clicks on buttons, links, and other interactive elements.
    """

    __tablename__ = 'loyalty_page_cta_clicks'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    page_id = db.Column(db.Integer, db.ForeignKey('loyalty_pages.id'), nullable=True, index=True)

    # Session identification
    session_id = db.Column(db.String(64), nullable=True, index=True)

    # Click details
    cta_id = db.Column(db.String(100), nullable=False)  # e.g., 'hero_cta', 'reward_redeem_123'
    cta_text = db.Column(db.String(200), nullable=True)  # Button/link text
    cta_url = db.Column(db.String(500), nullable=True)  # Destination URL
    section_id = db.Column(db.String(50), nullable=True)  # Which section the CTA is in

    # Member tracking
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True, index=True)
    is_member = db.Column(db.Boolean, default=False, nullable=False)

    # Timing
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('loyalty_page_cta_clicks', lazy='dynamic'))
    page = db.relationship('LoyaltyPage', backref=db.backref('cta_clicks', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_cta_clicks_tenant_date', 'tenant_id', 'clicked_at'),
        db.Index('idx_cta_clicks_cta', 'tenant_id', 'cta_id'),
    )

    def __repr__(self):
        return f'<LoyaltyPageCTAClick {self.id} cta={self.cta_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'page_id': self.page_id,
            'session_id': self.session_id,
            'cta_id': self.cta_id,
            'cta_text': self.cta_text,
            'cta_url': self.cta_url,
            'section_id': self.section_id,
            'member_id': self.member_id,
            'is_member': self.is_member,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
        }


class LoyaltyPageAnalyticsSummary(db.Model):
    """
    Daily aggregated analytics summary for the loyalty page.

    Pre-computed daily metrics for fast dashboard queries.
    """

    __tablename__ = 'loyalty_page_analytics_summary'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    page_id = db.Column(db.Integer, db.ForeignKey('loyalty_pages.id'), nullable=True, index=True)

    # Date for this summary
    summary_date = db.Column(db.Date, nullable=False, index=True)

    # View metrics
    total_views = db.Column(db.Integer, default=0, nullable=False)
    unique_visitors = db.Column(db.Integer, default=0, nullable=False)
    member_views = db.Column(db.Integer, default=0, nullable=False)
    guest_views = db.Column(db.Integer, default=0, nullable=False)

    # Device breakdown
    desktop_views = db.Column(db.Integer, default=0, nullable=False)
    mobile_views = db.Column(db.Integer, default=0, nullable=False)
    tablet_views = db.Column(db.Integer, default=0, nullable=False)

    # Engagement metrics
    avg_scroll_depth = db.Column(db.Float, default=0.0, nullable=False)  # 0-100
    avg_time_on_page_seconds = db.Column(db.Float, default=0.0, nullable=False)
    bounce_rate = db.Column(db.Float, default=0.0, nullable=False)  # 0-100

    # CTA metrics
    total_cta_clicks = db.Column(db.Integer, default=0, nullable=False)
    unique_cta_clickers = db.Column(db.Integer, default=0, nullable=False)
    cta_click_rate = db.Column(db.Float, default=0.0, nullable=False)  # clicks / views * 100

    # Top traffic sources (JSON)
    top_referrers = db.Column(db.JSON, nullable=True)  # [{referrer: x, count: y}, ...]
    top_utm_sources = db.Column(db.JSON, nullable=True)

    # Section engagement (JSON)
    section_engagement = db.Column(db.JSON, nullable=True)  # {section_id: {views: x, avg_time: y}, ...}

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('loyalty_page_analytics_summaries', lazy='dynamic'))
    page = db.relationship('LoyaltyPage', backref=db.backref('analytics_summaries', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'page_id', 'summary_date', name='unique_daily_analytics'),
        db.Index('idx_analytics_summary_tenant_date', 'tenant_id', 'summary_date'),
    )

    def __repr__(self):
        return f'<LoyaltyPageAnalyticsSummary {self.id} date={self.summary_date}>'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'page_id': self.page_id,
            'summary_date': self.summary_date.isoformat() if self.summary_date else None,
            'total_views': self.total_views,
            'unique_visitors': self.unique_visitors,
            'member_views': self.member_views,
            'guest_views': self.guest_views,
            'desktop_views': self.desktop_views,
            'mobile_views': self.mobile_views,
            'tablet_views': self.tablet_views,
            'avg_scroll_depth': self.avg_scroll_depth,
            'avg_time_on_page_seconds': self.avg_time_on_page_seconds,
            'bounce_rate': self.bounce_rate,
            'total_cta_clicks': self.total_cta_clicks,
            'unique_cta_clickers': self.unique_cta_clickers,
            'cta_click_rate': self.cta_click_rate,
            'top_referrers': self.top_referrers,
            'top_utm_sources': self.top_utm_sources,
            'section_engagement': self.section_engagement,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_or_create(cls, tenant_id: int, page_id: int, summary_date: date):
        """
        Get existing summary or create a new one for the given date.
        """
        summary = cls.query.filter_by(
            tenant_id=tenant_id,
            page_id=page_id,
            summary_date=summary_date
        ).first()

        if not summary:
            summary = cls(
                tenant_id=tenant_id,
                page_id=page_id,
                summary_date=summary_date
            )
            db.session.add(summary)
            db.session.flush()

        return summary
