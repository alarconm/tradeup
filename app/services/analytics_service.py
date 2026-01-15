"""
Advanced Analytics Service for TradeUp.

Provides comprehensive analytics and reporting:
- Customer Lifetime Value (CLV) calculations
- Cohort analysis and retention metrics
- Tier performance comparison
- Program ROI analysis
- Industry benchmarks

CLV Formula: AOV × Purchase Frequency × Lifespan
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import func, and_, or_, extract, case
from flask import current_app

from ..extensions import db
from ..models.member import Member, MembershipTier
from ..models.tenant import Tenant
from ..models.trade_in import TradeInBatch, TradeInItem
from ..models.promotions import StoreCreditLedger, CreditEventType


class AnalyticsService:
    """
    Advanced analytics and CLV calculations.

    Usage:
        service = AnalyticsService(tenant_id)
        clv_data = service.calculate_clv(member_id)
        cohort_data = service.get_cohort_analysis()
    """

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    # ==================== CLV CALCULATIONS ====================

    def calculate_clv(self, member_id: int) -> Dict[str, Any]:
        """
        Calculate Customer Lifetime Value for a specific member.

        Formula: AOV × Purchase Frequency × Lifespan

        Returns:
            Dict with CLV breakdown and comparison to averages
        """
        member = Member.query.filter_by(
            id=member_id,
            tenant_id=self.tenant_id
        ).first()

        if not member:
            return {'success': False, 'error': 'Member not found'}

        # Calculate member metrics
        aov = self._calculate_member_aov(member_id)
        frequency = self._calculate_purchase_frequency(member_id)
        lifespan = self._calculate_member_lifespan(member)
        projected_lifespan = self._project_lifespan(member)

        # Calculate CLV
        clv = aov * frequency * projected_lifespan

        # Get tier averages for comparison
        tier_avg_clv = self._get_tier_average_clv(member.tier_id) if member.tier_id else None
        overall_avg_clv = self._get_overall_average_clv()

        return {
            'success': True,
            'member_id': member_id,
            'member_number': member.member_number,
            'tier': member.tier.name if member.tier else None,
            'clv': {
                'value': float(clv),
                'aov': float(aov),
                'purchase_frequency': float(frequency),
                'actual_lifespan_months': lifespan,
                'projected_lifespan_months': projected_lifespan,
            },
            'comparison': {
                'tier_average_clv': float(tier_avg_clv) if tier_avg_clv else None,
                'overall_average_clv': float(overall_avg_clv),
                'percentile': self._calculate_clv_percentile(clv),
            },
            'metrics': {
                'total_spent': float(member.total_spent or 0),
                'order_count': member.order_count or 0,
                'days_since_last_order': self._days_since_last_order(member),
                'trade_in_count': self._get_trade_in_count(member_id),
                'credit_issued': float(member.store_credit_balance or 0),
            }
        }

    def get_clv_dashboard(self) -> Dict[str, Any]:
        """
        Get CLV dashboard metrics for the tenant.

        Returns:
            Comprehensive CLV analytics dashboard data
        """
        # Overall CLV metrics
        overall_clv = self._get_overall_average_clv()
        median_clv = self._get_median_clv()
        top_percentile_clv = self._get_percentile_clv(90)

        # CLV by tier
        clv_by_tier = self._get_clv_by_tier()

        # CLV distribution
        clv_distribution = self._get_clv_distribution()

        # Top customers by CLV
        top_customers = self._get_top_customers_by_clv(limit=10)

        # CLV trends
        clv_trend = self._get_clv_trend(months=6)

        return {
            'success': True,
            'overall_metrics': {
                'average_clv': float(overall_clv),
                'median_clv': float(median_clv),
                '90th_percentile_clv': float(top_percentile_clv),
                'total_members': self._get_total_active_members(),
            },
            'by_tier': clv_by_tier,
            'distribution': clv_distribution,
            'top_customers': top_customers,
            'trend': clv_trend,
        }

    # ==================== COHORT ANALYSIS ====================

    def get_cohort_analysis(
        self,
        cohort_type: str = 'monthly',
        metric: str = 'retention',
        months: int = 6
    ) -> Dict[str, Any]:
        """
        Get cohort retention analysis.

        Args:
            cohort_type: 'monthly' or 'weekly'
            metric: 'retention' or 'revenue'
            months: Number of months to analyze

        Returns:
            Cohort matrix data for visualization
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)

        # Get members grouped by signup cohort
        cohorts = self._get_signup_cohorts(start_date, end_date, cohort_type)

        if metric == 'retention':
            matrix = self._calculate_retention_matrix(cohorts, months)
        else:
            matrix = self._calculate_revenue_matrix(cohorts, months)

        return {
            'success': True,
            'cohort_type': cohort_type,
            'metric': metric,
            'period_months': months,
            'matrix': matrix,
            'summary': {
                'total_cohorts': len(cohorts),
                'average_retention_30d': self._calculate_avg_retention(30),
                'average_retention_60d': self._calculate_avg_retention(60),
                'average_retention_90d': self._calculate_avg_retention(90),
            }
        }

    # ==================== TIER PERFORMANCE ====================

    def get_tier_performance(self) -> Dict[str, Any]:
        """
        Compare performance metrics across tiers.

        Returns:
            Tier comparison data including AOV, retention, engagement
        """
        tiers = MembershipTier.query.filter_by(
            tenant_id=self.tenant_id,
            is_active=True
        ).order_by(MembershipTier.trade_in_rate.desc()).all()

        tier_metrics = []
        for tier in tiers:
            members = Member.query.filter_by(
                tenant_id=self.tenant_id,
                tier_id=tier.id,
                status='active'
            ).all()

            member_ids = [m.id for m in members]

            if not member_ids:
                tier_metrics.append({
                    'tier_id': tier.id,
                    'tier_name': tier.name,
                    'member_count': 0,
                    'metrics': None
                })
                continue

            metrics = {
                'member_count': len(members),
                'average_clv': float(self._calculate_tier_clv(tier.id)),
                'average_aov': float(self._calculate_tier_aov(member_ids)),
                'average_order_frequency': float(self._calculate_tier_frequency(member_ids)),
                'retention_30d': self._calculate_tier_retention(tier.id, 30),
                'retention_90d': self._calculate_tier_retention(tier.id, 90),
                'trade_in_rate': len([m for m in members if self._get_trade_in_count(m.id) > 0]) / len(members) * 100 if members else 0,
                'total_revenue': float(sum(m.total_spent or 0 for m in members)),
                'total_credit_issued': float(self._get_tier_credit_issued(tier.id)),
            }

            tier_metrics.append({
                'tier_id': tier.id,
                'tier_name': tier.name,
                'tier_color': tier.badge_color,
                'metrics': metrics
            })

        return {
            'success': True,
            'tiers': tier_metrics,
            'comparison_insights': self._generate_tier_insights(tier_metrics)
        }

    # ==================== PROGRAM ROI ====================

    def get_program_roi(self, period_days: int = 30) -> Dict[str, Any]:
        """
        Calculate program ROI - credit issued vs revenue driven.

        Args:
            period_days: Analysis period in days

        Returns:
            ROI metrics and breakdown
        """
        start_date = datetime.utcnow() - timedelta(days=period_days)

        # Get credit issued during period
        credit_issued = db.session.query(
            func.sum(StoreCreditLedger.amount)
        ).join(
            Member, StoreCreditLedger.member_id == Member.id
        ).filter(
            Member.tenant_id == self.tenant_id,
            StoreCreditLedger.amount > 0,
            StoreCreditLedger.created_at >= start_date
        ).scalar() or Decimal('0')

        # Get credit redeemed during period
        credit_redeemed = db.session.query(
            func.sum(func.abs(StoreCreditLedger.amount))
        ).join(
            Member, StoreCreditLedger.member_id == Member.id
        ).filter(
            Member.tenant_id == self.tenant_id,
            StoreCreditLedger.amount < 0,
            StoreCreditLedger.created_at >= start_date
        ).scalar() or Decimal('0')

        # Get revenue from members during period
        member_revenue = db.session.query(
            func.sum(Member.total_spent)
        ).filter(
            Member.tenant_id == self.tenant_id,
            Member.status == 'active'
        ).scalar() or Decimal('0')

        # Calculate breakdown by event type
        credit_by_type = db.session.query(
            StoreCreditLedger.event_type,
            func.sum(StoreCreditLedger.amount)
        ).join(
            Member, StoreCreditLedger.member_id == Member.id
        ).filter(
            Member.tenant_id == self.tenant_id,
            StoreCreditLedger.amount > 0,
            StoreCreditLedger.created_at >= start_date
        ).group_by(StoreCreditLedger.event_type).all()

        breakdown = {et: float(amount) for et, amount in credit_by_type}

        # Calculate ROI
        roi = ((float(member_revenue) - float(credit_issued)) / float(credit_issued) * 100) if credit_issued > 0 else 0

        return {
            'success': True,
            'period_days': period_days,
            'metrics': {
                'credit_issued': float(credit_issued),
                'credit_redeemed': float(credit_redeemed),
                'credit_outstanding': float(credit_issued - credit_redeemed),
                'member_revenue': float(member_revenue),
                'roi_percentage': round(roi, 2),
                'redemption_rate': (float(credit_redeemed) / float(credit_issued) * 100) if credit_issued > 0 else 0,
            },
            'breakdown_by_type': breakdown,
            'insights': self._generate_roi_insights(credit_issued, credit_redeemed, member_revenue)
        }

    # ==================== BENCHMARKS ====================

    def get_benchmarks(self, category: str = 'all') -> Dict[str, Any]:
        """
        Get industry benchmark comparisons.

        Note: In production, this would compare against aggregated
        anonymized data from all TradeUp tenants.

        Args:
            category: Store category for targeted benchmarks

        Returns:
            Benchmark comparison data
        """
        # Get current tenant's metrics
        tenant_metrics = self._calculate_tenant_metrics()

        # Industry benchmarks (these would come from aggregated data)
        benchmarks = self._get_industry_benchmarks(category)

        return {
            'success': True,
            'category': category,
            'your_metrics': tenant_metrics,
            'benchmarks': benchmarks,
            'percentiles': {
                'member_growth': self._calculate_benchmark_percentile('member_growth', tenant_metrics.get('member_growth_rate', 0)),
                'redemption_rate': self._calculate_benchmark_percentile('redemption_rate', tenant_metrics.get('redemption_rate', 0)),
                'average_clv': self._calculate_benchmark_percentile('clv', tenant_metrics.get('average_clv', 0)),
                'engagement_score': self._calculate_benchmark_percentile('engagement', tenant_metrics.get('engagement_score', 0)),
            }
        }

    # ==================== HELPER METHODS ====================

    def _calculate_member_aov(self, member_id: int) -> Decimal:
        """Calculate average order value for a member."""
        member = Member.query.get(member_id)
        if not member or not member.order_count or member.order_count == 0:
            return Decimal('0')
        return Decimal(str(member.total_spent or 0)) / member.order_count

    def _calculate_purchase_frequency(self, member_id: int) -> Decimal:
        """Calculate annual purchase frequency for a member."""
        member = Member.query.get(member_id)
        if not member or not member.created_at:
            return Decimal('0')

        months_active = max(1, (datetime.utcnow() - member.created_at).days / 30)
        orders = member.order_count or 0

        # Annualized frequency
        return Decimal(str(orders)) / Decimal(str(months_active)) * 12

    def _calculate_member_lifespan(self, member: Member) -> int:
        """Calculate actual lifespan in months."""
        if not member.created_at:
            return 0
        return max(1, (datetime.utcnow() - member.created_at).days // 30)

    def _project_lifespan(self, member: Member) -> int:
        """Project expected lifespan based on activity."""
        # Simple projection: Active members projected to 24 months
        # Could be enhanced with churn prediction
        if member.status != 'active':
            return self._calculate_member_lifespan(member)

        # Base projection on tier
        if member.tier:
            # Higher tiers tend to stay longer
            tier_bonus = {
                1: 12,  # Basic tier
                2: 18,  # Mid tier
                3: 24,  # High tier
            }.get(member.tier_id, 18)
            return tier_bonus

        return 18  # Default projection

    def _get_tier_average_clv(self, tier_id: int) -> Decimal:
        """Get average CLV for a tier."""
        return self._calculate_tier_clv(tier_id)

    def _get_overall_average_clv(self) -> Decimal:
        """Get overall average CLV."""
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        if not members:
            return Decimal('0')

        total_clv = sum(
            float(self._calculate_member_aov(m.id)) *
            float(self._calculate_purchase_frequency(m.id)) *
            self._project_lifespan(m)
            for m in members
        )

        return Decimal(str(total_clv / len(members)))

    def _calculate_clv_percentile(self, clv: Decimal) -> int:
        """Calculate what percentile a CLV falls in."""
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        if not members:
            return 50

        clv_values = sorted([
            float(self._calculate_member_aov(m.id)) *
            float(self._calculate_purchase_frequency(m.id)) *
            self._project_lifespan(m)
            for m in members
        ])

        clv_float = float(clv)
        rank = sum(1 for v in clv_values if v < clv_float)
        return int(rank / len(clv_values) * 100)

    def _days_since_last_order(self, member: Member) -> Optional[int]:
        """Calculate days since last order."""
        if not member.last_order_at:
            return None
        return (datetime.utcnow() - member.last_order_at).days

    def _get_trade_in_count(self, member_id: int) -> int:
        """Get number of trade-ins for a member."""
        return TradeInBatch.query.filter_by(
            member_id=member_id,
            status='completed'
        ).count()

    def _get_median_clv(self) -> Decimal:
        """Get median CLV across all members."""
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        if not members:
            return Decimal('0')

        clv_values = sorted([
            float(self._calculate_member_aov(m.id)) *
            float(self._calculate_purchase_frequency(m.id)) *
            self._project_lifespan(m)
            for m in members
        ])

        mid = len(clv_values) // 2
        if len(clv_values) % 2 == 0:
            return Decimal(str((clv_values[mid-1] + clv_values[mid]) / 2))
        return Decimal(str(clv_values[mid]))

    def _get_percentile_clv(self, percentile: int) -> Decimal:
        """Get CLV at a specific percentile."""
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        if not members:
            return Decimal('0')

        clv_values = sorted([
            float(self._calculate_member_aov(m.id)) *
            float(self._calculate_purchase_frequency(m.id)) *
            self._project_lifespan(m)
            for m in members
        ])

        index = int(len(clv_values) * percentile / 100)
        return Decimal(str(clv_values[min(index, len(clv_values)-1)]))

    def _get_clv_by_tier(self) -> List[Dict]:
        """Get CLV metrics broken down by tier."""
        tiers = MembershipTier.query.filter_by(
            tenant_id=self.tenant_id,
            is_active=True
        ).all()

        result = []
        for tier in tiers:
            clv = self._calculate_tier_clv(tier.id)
            member_count = Member.query.filter_by(
                tenant_id=self.tenant_id,
                tier_id=tier.id,
                status='active'
            ).count()

            result.append({
                'tier_id': tier.id,
                'tier_name': tier.name,
                'average_clv': float(clv),
                'member_count': member_count
            })

        return sorted(result, key=lambda x: x['average_clv'], reverse=True)

    def _get_clv_distribution(self) -> Dict[str, int]:
        """Get CLV distribution buckets."""
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        buckets = {
            '$0-50': 0,
            '$51-100': 0,
            '$101-250': 0,
            '$251-500': 0,
            '$501-1000': 0,
            '$1000+': 0
        }

        for member in members:
            clv = float(self._calculate_member_aov(member.id)) * \
                  float(self._calculate_purchase_frequency(member.id)) * \
                  self._project_lifespan(member)

            if clv <= 50:
                buckets['$0-50'] += 1
            elif clv <= 100:
                buckets['$51-100'] += 1
            elif clv <= 250:
                buckets['$101-250'] += 1
            elif clv <= 500:
                buckets['$251-500'] += 1
            elif clv <= 1000:
                buckets['$501-1000'] += 1
            else:
                buckets['$1000+'] += 1

        return buckets

    def _get_top_customers_by_clv(self, limit: int = 10) -> List[Dict]:
        """Get top customers ranked by CLV."""
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).all()

        member_clvs = []
        for member in members:
            clv = float(self._calculate_member_aov(member.id)) * \
                  float(self._calculate_purchase_frequency(member.id)) * \
                  self._project_lifespan(member)

            member_clvs.append({
                'member_id': member.id,
                'member_number': member.member_number,
                'name': member.name,
                'email': member.email,
                'tier': member.tier.name if member.tier else None,
                'clv': round(clv, 2),
                'total_spent': float(member.total_spent or 0),
                'order_count': member.order_count or 0
            })

        return sorted(member_clvs, key=lambda x: x['clv'], reverse=True)[:limit]

    def _get_clv_trend(self, months: int = 6) -> List[Dict]:
        """Get CLV trend over time."""
        # Simplified: return monthly snapshots
        trend = []
        for i in range(months, 0, -1):
            date = datetime.utcnow() - timedelta(days=i*30)
            trend.append({
                'month': date.strftime('%Y-%m'),
                'average_clv': float(self._get_overall_average_clv()),  # Would need historical data
            })
        return trend

    def _get_total_active_members(self) -> int:
        """Get total active members."""
        return Member.query.filter_by(
            tenant_id=self.tenant_id,
            status='active'
        ).count()

    def _calculate_tier_clv(self, tier_id: int) -> Decimal:
        """Calculate average CLV for a tier."""
        members = Member.query.filter_by(
            tenant_id=self.tenant_id,
            tier_id=tier_id,
            status='active'
        ).all()

        if not members:
            return Decimal('0')

        total_clv = sum(
            float(self._calculate_member_aov(m.id)) *
            float(self._calculate_purchase_frequency(m.id)) *
            self._project_lifespan(m)
            for m in members
        )

        return Decimal(str(total_clv / len(members)))

    def _calculate_tier_aov(self, member_ids: List[int]) -> Decimal:
        """Calculate average AOV for a list of members."""
        if not member_ids:
            return Decimal('0')

        total_aov = sum(float(self._calculate_member_aov(mid)) for mid in member_ids)
        return Decimal(str(total_aov / len(member_ids)))

    def _calculate_tier_frequency(self, member_ids: List[int]) -> Decimal:
        """Calculate average purchase frequency for a list of members."""
        if not member_ids:
            return Decimal('0')

        total_freq = sum(float(self._calculate_purchase_frequency(mid)) for mid in member_ids)
        return Decimal(str(total_freq / len(member_ids)))

    def _calculate_tier_retention(self, tier_id: int, days: int) -> float:
        """Calculate retention rate for a tier over N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Members who joined more than N days ago
        joined = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.tier_id == tier_id,
            Member.created_at < cutoff
        ).count()

        if joined == 0:
            return 100.0

        # Of those, how many are still active
        retained = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.tier_id == tier_id,
            Member.created_at < cutoff,
            Member.status == 'active'
        ).count()

        return round(retained / joined * 100, 1)

    def _get_tier_credit_issued(self, tier_id: int) -> Decimal:
        """Get total credit issued to members of a tier."""
        result = db.session.query(
            func.sum(StoreCreditLedger.amount)
        ).join(
            Member, StoreCreditLedger.member_id == Member.id
        ).filter(
            Member.tenant_id == self.tenant_id,
            Member.tier_id == tier_id,
            StoreCreditLedger.amount > 0
        ).scalar()

        return result or Decimal('0')

    def _generate_tier_insights(self, tier_metrics: List[Dict]) -> List[str]:
        """Generate insights from tier comparison data."""
        insights = []

        valid_tiers = [t for t in tier_metrics if t['metrics']]
        if len(valid_tiers) < 2:
            return insights

        # Find best performing tier
        best_clv = max(valid_tiers, key=lambda x: x['metrics']['average_clv'])
        insights.append(f"{best_clv['tier_name']} members have the highest CLV at ${best_clv['metrics']['average_clv']:.2f}")

        # Find best retention
        best_retention = max(valid_tiers, key=lambda x: x['metrics']['retention_90d'])
        insights.append(f"{best_retention['tier_name']} tier has the best 90-day retention at {best_retention['metrics']['retention_90d']}%")

        return insights

    def _generate_roi_insights(
        self,
        credit_issued: Decimal,
        credit_redeemed: Decimal,
        revenue: Decimal
    ) -> List[str]:
        """Generate ROI insights."""
        insights = []

        redemption_rate = float(credit_redeemed) / float(credit_issued) * 100 if credit_issued > 0 else 0

        if redemption_rate < 30:
            insights.append("Low redemption rate suggests members may not be aware of their credits")
        elif redemption_rate > 80:
            insights.append("High redemption rate indicates strong program engagement")

        if float(revenue) > float(credit_issued) * 5:
            insights.append("Excellent ROI - members are generating 5x+ the credit issued")

        return insights

    def _get_signup_cohorts(
        self,
        start_date: datetime,
        end_date: datetime,
        cohort_type: str
    ) -> Dict[str, List[int]]:
        """Group members by signup date into cohorts."""
        members = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.created_at >= start_date,
            Member.created_at <= end_date
        ).all()

        cohorts = {}
        for member in members:
            if cohort_type == 'monthly':
                key = member.created_at.strftime('%Y-%m')
            else:  # weekly
                key = member.created_at.strftime('%Y-W%W')

            if key not in cohorts:
                cohorts[key] = []
            cohorts[key].append(member.id)

        return cohorts

    def _calculate_retention_matrix(self, cohorts: Dict, months: int) -> List[Dict]:
        """Calculate retention matrix for cohorts."""
        matrix = []

        for cohort_key, member_ids in sorted(cohorts.items()):
            row = {'cohort': cohort_key, 'size': len(member_ids), 'retention': []}

            for month_offset in range(months):
                retained = self._count_retained_members(member_ids, month_offset)
                retention_pct = retained / len(member_ids) * 100 if member_ids else 0
                row['retention'].append(round(retention_pct, 1))

            matrix.append(row)

        return matrix

    def _calculate_revenue_matrix(self, cohorts: Dict, months: int) -> List[Dict]:
        """Calculate revenue matrix for cohorts."""
        matrix = []

        for cohort_key, member_ids in sorted(cohorts.items()):
            row = {'cohort': cohort_key, 'size': len(member_ids), 'revenue': []}

            for month_offset in range(months):
                revenue = self._calculate_cohort_revenue(member_ids, month_offset)
                row['revenue'].append(float(revenue))

            matrix.append(row)

        return matrix

    def _count_retained_members(self, member_ids: List[int], month_offset: int) -> int:
        """Count members still active after N months."""
        if not member_ids:
            return 0

        # Simplified: check if members are still active
        return Member.query.filter(
            Member.id.in_(member_ids),
            Member.status == 'active'
        ).count()

    def _calculate_cohort_revenue(self, member_ids: List[int], month_offset: int) -> Decimal:
        """Calculate total revenue from cohort in a specific month."""
        if not member_ids:
            return Decimal('0')

        result = db.session.query(
            func.sum(Member.total_spent)
        ).filter(
            Member.id.in_(member_ids)
        ).scalar()

        return result or Decimal('0')

    def _calculate_avg_retention(self, days: int) -> float:
        """Calculate average retention rate over N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        joined = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.created_at < cutoff
        ).count()

        if joined == 0:
            return 100.0

        retained = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.created_at < cutoff,
            Member.status == 'active'
        ).count()

        return round(retained / joined * 100, 1)

    def _calculate_tenant_metrics(self) -> Dict[str, Any]:
        """Calculate current tenant's key metrics."""
        total_members = self._get_total_active_members()

        # Member growth (last 30 days)
        new_members = Member.query.filter(
            Member.tenant_id == self.tenant_id,
            Member.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()

        growth_rate = new_members / total_members * 100 if total_members > 0 else 0

        # Redemption rate
        credit_issued = db.session.query(
            func.sum(StoreCreditLedger.amount)
        ).join(Member).filter(
            Member.tenant_id == self.tenant_id,
            StoreCreditLedger.amount > 0
        ).scalar() or 0

        credit_redeemed = db.session.query(
            func.sum(func.abs(StoreCreditLedger.amount))
        ).join(Member).filter(
            Member.tenant_id == self.tenant_id,
            StoreCreditLedger.amount < 0
        ).scalar() or 0

        redemption_rate = float(credit_redeemed) / float(credit_issued) * 100 if credit_issued > 0 else 0

        return {
            'total_members': total_members,
            'member_growth_rate': round(growth_rate, 1),
            'average_clv': float(self._get_overall_average_clv()),
            'redemption_rate': round(redemption_rate, 1),
            'engagement_score': self._calculate_engagement_score(),
        }

    def _calculate_engagement_score(self) -> float:
        """Calculate overall program engagement score (0-100)."""
        # Composite score based on multiple factors
        active_rate = self._calculate_avg_retention(30)
        redemption_rate = self._calculate_tenant_metrics().get('redemption_rate', 0)

        # Weighted average
        return round((active_rate * 0.5 + redemption_rate * 0.5), 1)

    def _get_industry_benchmarks(self, category: str) -> Dict[str, Any]:
        """Get industry benchmark data."""
        # These would come from aggregated data in production
        return {
            'average_clv': 150.00,
            'redemption_rate': 45.0,
            'retention_30d': 75.0,
            'retention_90d': 55.0,
            'member_growth_rate': 8.0,
            'engagement_score': 60.0,
        }

    def _calculate_benchmark_percentile(self, metric: str, value: float) -> int:
        """Calculate percentile ranking for a metric."""
        # Simplified - would use actual aggregated data
        benchmarks = {
            'member_growth': [5, 10, 15, 20, 25],
            'redemption_rate': [20, 35, 50, 65, 80],
            'clv': [50, 100, 150, 250, 500],
            'engagement': [30, 45, 60, 75, 90],
        }

        thresholds = benchmarks.get(metric, [])
        for i, threshold in enumerate(thresholds):
            if value < threshold:
                return i * 20 + 10
        return 90


# Singleton placeholder - instantiate per tenant
def get_analytics_service(tenant_id: int) -> AnalyticsService:
    """Get analytics service for a tenant."""
    return AnalyticsService(tenant_id)
