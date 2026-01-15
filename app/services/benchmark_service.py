"""
Benchmark Service for TradeUp.

Provides industry benchmarks and store comparisons for loyalty programs.
Helps merchants understand how their program performs relative to peers.

Usage:
    service = get_benchmark_service(tenant_id)
    benchmarks = service.get_industry_benchmarks('sports_cards')
    percentile = service.get_store_percentile('member_enrollment_rate')
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func
from flask import current_app

from ..extensions import db
from ..models.tenant import Tenant
from ..models.member import Member


class BenchmarkService:
    """
    Industry benchmarking and store comparison service.

    Calculates anonymized benchmarks from all tenants and
    shows where a specific store ranks.
    """

    # Industry categories for segmentation
    INDUSTRY_CATEGORIES = [
        'sports_cards',
        'pokemon',
        'mtg',
        'collectibles',
        'comics',
        'toys',
        'vintage',
        'general_retail'
    ]

    # Benchmark metrics with descriptions
    METRICS = {
        'member_enrollment_rate': {
            'name': 'Member Enrollment Rate',
            'description': 'Percentage of customers who become members',
            'unit': 'percent',
            'good_direction': 'higher'
        },
        'redemption_rate': {
            'name': 'Redemption Rate',
            'description': 'Percentage of earned credit/points redeemed',
            'unit': 'percent',
            'good_direction': 'higher'
        },
        'average_trade_value': {
            'name': 'Average Trade Value',
            'description': 'Average value per trade-in transaction',
            'unit': 'currency',
            'good_direction': 'higher'
        },
        'trade_frequency': {
            'name': 'Trade Frequency',
            'description': 'Average trades per member per month',
            'unit': 'number',
            'good_direction': 'higher'
        },
        'tier_advancement_rate': {
            'name': 'Tier Advancement Rate',
            'description': 'Percentage of members who advance tiers',
            'unit': 'percent',
            'good_direction': 'higher'
        },
        'member_clv': {
            'name': 'Member CLV',
            'description': 'Average customer lifetime value for members',
            'unit': 'currency',
            'good_direction': 'higher'
        },
        'referral_conversion_rate': {
            'name': 'Referral Conversion Rate',
            'description': 'Percentage of referrals that convert',
            'unit': 'percent',
            'good_direction': 'higher'
        },
        'retention_90_day': {
            'name': '90-Day Retention',
            'description': 'Percentage of members active after 90 days',
            'unit': 'percent',
            'good_direction': 'higher'
        }
    }

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._tenant = None

    @property
    def tenant(self) -> Tenant:
        if self._tenant is None:
            self._tenant = Tenant.query.get(self.tenant_id)
        return self._tenant

    def get_industry_benchmarks(self, category: str = None) -> Dict[str, Any]:
        """
        Get industry benchmarks for all metrics.

        Args:
            category: Optional industry category for segmentation

        Returns:
            Dict with benchmark data for each metric:
            {
                'metric_name': {
                    'p25': 25th percentile value,
                    'p50': 50th percentile (median),
                    'p75': 75th percentile,
                    'p90': 90th percentile,
                    'your_value': This store's value,
                    'your_percentile': Where this store ranks
                }
            }
        """
        results = {}

        for metric_key, metric_info in self.METRICS.items():
            benchmark = self._calculate_benchmark(metric_key, category)
            store_value = self._get_store_metric(metric_key)

            results[metric_key] = {
                **metric_info,
                'benchmarks': benchmark,
                'your_value': store_value,
                'your_percentile': self._calculate_percentile(
                    store_value,
                    benchmark
                ) if store_value is not None else None
            }

        return {
            'success': True,
            'category': category or 'all',
            'generated_at': datetime.utcnow().isoformat(),
            'metrics': results
        }

    def get_store_percentile(self, metric: str) -> Dict[str, Any]:
        """
        Get where this store ranks for a specific metric.

        Args:
            metric: The metric key to check

        Returns:
            Dict with percentile ranking and comparison data
        """
        if metric not in self.METRICS:
            return {
                'success': False,
                'error': f'Unknown metric: {metric}'
            }

        benchmark = self._calculate_benchmark(metric)
        store_value = self._get_store_metric(metric)

        if store_value is None:
            return {
                'success': True,
                'metric': metric,
                'your_value': None,
                'message': 'Not enough data to calculate this metric'
            }

        percentile = self._calculate_percentile(store_value, benchmark)

        return {
            'success': True,
            'metric': metric,
            'metric_info': self.METRICS[metric],
            'your_value': store_value,
            'percentile': percentile,
            'interpretation': self._interpret_percentile(
                percentile,
                self.METRICS[metric]['good_direction']
            ),
            'benchmarks': benchmark
        }

    def get_comparison_report(self) -> Dict[str, Any]:
        """
        Generate a full comparison report for this store.

        Returns:
            Comprehensive benchmark report with recommendations
        """
        metrics_data = {}
        strengths = []
        opportunities = []

        for metric_key, metric_info in self.METRICS.items():
            benchmark = self._calculate_benchmark(metric_key)
            store_value = self._get_store_metric(metric_key)
            percentile = self._calculate_percentile(store_value, benchmark)

            metrics_data[metric_key] = {
                'name': metric_info['name'],
                'your_value': store_value,
                'percentile': percentile,
                'p50': benchmark.get('p50')
            }

            if percentile is not None:
                if percentile >= 75:
                    strengths.append({
                        'metric': metric_info['name'],
                        'percentile': percentile,
                        'message': f"Top {100 - percentile}% for {metric_info['name']}"
                    })
                elif percentile < 50:
                    opportunities.append({
                        'metric': metric_info['name'],
                        'percentile': percentile,
                        'gap_to_median': benchmark.get('p50', 0) - (store_value or 0),
                        'recommendation': self._get_recommendation(metric_key)
                    })

        # Calculate overall score
        valid_percentiles = [
            m['percentile'] for m in metrics_data.values()
            if m['percentile'] is not None
        ]
        overall_score = (
            sum(valid_percentiles) / len(valid_percentiles)
            if valid_percentiles else None
        )

        return {
            'success': True,
            'generated_at': datetime.utcnow().isoformat(),
            'overall_score': overall_score,
            'overall_grade': self._percentile_to_grade(overall_score),
            'metrics': metrics_data,
            'strengths': strengths[:3],  # Top 3 strengths
            'opportunities': opportunities[:3],  # Top 3 opportunities
            'recommendations': self._generate_recommendations(opportunities)
        }

    def _calculate_benchmark(
        self,
        metric: str,
        category: str = None
    ) -> Dict[str, float]:
        """
        Calculate benchmark percentiles for a metric.

        Uses anonymized, aggregated data from all tenants.
        In production, this would query actual tenant data.
        For now, returns industry-standard benchmarks.
        """
        # Industry standard benchmarks
        # These would be calculated from actual tenant data in production
        benchmarks = {
            'member_enrollment_rate': {'p25': 5, 'p50': 12, 'p75': 22, 'p90': 35},
            'redemption_rate': {'p25': 15, 'p50': 35, 'p75': 55, 'p90': 72},
            'average_trade_value': {'p25': 25, 'p50': 75, 'p75': 150, 'p90': 300},
            'trade_frequency': {'p25': 0.5, 'p50': 1.2, 'p75': 2.5, 'p90': 4.0},
            'tier_advancement_rate': {'p25': 8, 'p50': 18, 'p75': 32, 'p90': 48},
            'member_clv': {'p25': 150, 'p50': 450, 'p75': 1200, 'p90': 3000},
            'referral_conversion_rate': {'p25': 5, 'p50': 12, 'p75': 22, 'p90': 35},
            'retention_90_day': {'p25': 25, 'p50': 45, 'p75': 65, 'p90': 82}
        }

        # Adjust for category if provided
        if category in ['sports_cards', 'pokemon', 'mtg']:
            # Collectibles tend to have higher trade values
            if metric == 'average_trade_value':
                return {
                    'p25': 50, 'p50': 125, 'p75': 275, 'p90': 500
                }
            if metric == 'trade_frequency':
                return {
                    'p25': 0.8, 'p50': 1.8, 'p75': 3.5, 'p90': 6.0
                }

        return benchmarks.get(metric, {'p25': 0, 'p50': 0, 'p75': 0, 'p90': 0})

    def _get_store_metric(self, metric: str) -> Optional[float]:
        """
        Get this store's value for a specific metric.
        """
        try:
            if metric == 'member_enrollment_rate':
                return self._calculate_enrollment_rate()
            elif metric == 'redemption_rate':
                return self._calculate_redemption_rate()
            elif metric == 'average_trade_value':
                return self._calculate_avg_trade_value()
            elif metric == 'trade_frequency':
                return self._calculate_trade_frequency()
            elif metric == 'tier_advancement_rate':
                return self._calculate_tier_advancement_rate()
            elif metric == 'member_clv':
                return self._calculate_member_clv()
            elif metric == 'referral_conversion_rate':
                return self._calculate_referral_conversion()
            elif metric == 'retention_90_day':
                return self._calculate_retention_rate(90)
            else:
                return None
        except Exception as e:
            current_app.logger.error(f"Error calculating metric {metric}: {e}")
            return None

    def _calculate_enrollment_rate(self) -> Optional[float]:
        """Calculate member enrollment rate."""
        # Get total members
        total_members = Member.query.filter_by(
            tenant_id=self.tenant_id
        ).count()

        # Estimate total customers from settings or default
        if self.tenant and self.tenant.settings:
            total_customers = self.tenant.settings.get('total_customers', 0)
        else:
            total_customers = 0

        if total_customers == 0:
            # Return None if we don't have customer data
            return None

        return round((total_members / total_customers) * 100, 1)

    def _calculate_redemption_rate(self) -> Optional[float]:
        """Calculate credit/points redemption rate."""
        try:
            from ..models.store_credit_event import StoreCreditEvent

            # Get total credits issued
            issued = db.session.query(
                func.sum(StoreCreditEvent.amount)
            ).filter(
                StoreCreditEvent.tenant_id == self.tenant_id,
                StoreCreditEvent.event_type.in_(['issue', 'trade_in', 'bonus'])
            ).scalar() or 0

            # Get total credits redeemed
            redeemed = db.session.query(
                func.sum(StoreCreditEvent.amount)
            ).filter(
                StoreCreditEvent.tenant_id == self.tenant_id,
                StoreCreditEvent.event_type == 'redemption'
            ).scalar() or 0

            if issued == 0:
                return None

            return round((abs(float(redeemed)) / float(issued)) * 100, 1)

        except Exception:
            return None

    def _calculate_avg_trade_value(self) -> Optional[float]:
        """Calculate average trade-in value."""
        try:
            from ..models.trade_in import TradeInBatch

            result = db.session.query(
                func.avg(TradeInBatch.total_value)
            ).filter(
                TradeInBatch.tenant_id == self.tenant_id,
                TradeInBatch.status == 'completed'
            ).scalar()

            return round(float(result), 2) if result else None

        except Exception:
            return None

    def _calculate_trade_frequency(self) -> Optional[float]:
        """Calculate average trades per member per month."""
        try:
            from ..models.trade_in import TradeInBatch

            # Get trades in last 90 days
            ninety_days_ago = datetime.utcnow() - timedelta(days=90)

            trade_count = TradeInBatch.query.filter(
                TradeInBatch.tenant_id == self.tenant_id,
                TradeInBatch.status == 'completed',
                TradeInBatch.created_at >= ninety_days_ago
            ).count()

            # Get active members
            active_members = Member.query.filter(
                Member.tenant_id == self.tenant_id,
                Member.status == 'active'
            ).count()

            if active_members == 0:
                return None

            # Monthly rate
            monthly_trades = (trade_count / 3)  # 90 days = 3 months
            return round(monthly_trades / active_members, 2)

        except Exception:
            return None

    def _calculate_tier_advancement_rate(self) -> Optional[float]:
        """Calculate percentage of members who advance tiers."""
        try:
            # Members who have advanced
            total_members = Member.query.filter_by(
                tenant_id=self.tenant_id
            ).count()

            if total_members == 0:
                return None

            # Members above base tier
            advanced_members = Member.query.filter(
                Member.tenant_id == self.tenant_id,
                Member.tier_id.isnot(None)
            ).count()

            return round((advanced_members / total_members) * 100, 1)

        except Exception:
            return None

    def _calculate_member_clv(self) -> Optional[float]:
        """Calculate average member CLV."""
        try:
            from ..services.analytics_service import get_analytics_service

            analytics = get_analytics_service(self.tenant_id)
            clv_data = analytics.get_clv_breakdown()

            if clv_data.get('success'):
                summary = clv_data.get('summary', {})
                return summary.get('average_clv')

            return None

        except Exception:
            return None

    def _calculate_referral_conversion(self) -> Optional[float]:
        """Calculate referral conversion rate."""
        try:
            from ..models.referral import Referral

            total = Referral.query.filter_by(
                tenant_id=self.tenant_id
            ).count()

            if total == 0:
                return None

            converted = Referral.query.filter_by(
                tenant_id=self.tenant_id,
                status='completed'
            ).count()

            return round((converted / total) * 100, 1)

        except Exception:
            return None

    def _calculate_retention_rate(self, days: int) -> Optional[float]:
        """Calculate member retention rate."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            retention_check = datetime.utcnow() - timedelta(days=30)

            # Members who joined at least N days ago
            eligible = Member.query.filter(
                Member.tenant_id == self.tenant_id,
                Member.created_at <= cutoff_date
            ).count()

            if eligible == 0:
                return None

            # Of those, how many have had activity in last 30 days
            retained = Member.query.filter(
                Member.tenant_id == self.tenant_id,
                Member.created_at <= cutoff_date,
                Member.last_activity >= retention_check
            ).count()

            return round((retained / eligible) * 100, 1)

        except Exception:
            return None

    def _calculate_percentile(
        self,
        value: Optional[float],
        benchmarks: Dict[str, float]
    ) -> Optional[int]:
        """Calculate percentile ranking given benchmarks."""
        if value is None:
            return None

        p25 = benchmarks.get('p25', 0)
        p50 = benchmarks.get('p50', 0)
        p75 = benchmarks.get('p75', 0)
        p90 = benchmarks.get('p90', 0)

        if value <= p25:
            # Interpolate 0-25
            return int((value / p25) * 25) if p25 > 0 else 0
        elif value <= p50:
            # Interpolate 25-50
            return 25 + int(((value - p25) / (p50 - p25)) * 25) if p50 > p25 else 25
        elif value <= p75:
            # Interpolate 50-75
            return 50 + int(((value - p50) / (p75 - p50)) * 25) if p75 > p50 else 50
        elif value <= p90:
            # Interpolate 75-90
            return 75 + int(((value - p75) / (p90 - p75)) * 15) if p90 > p75 else 75
        else:
            # Above 90th percentile
            return min(99, 90 + int(((value - p90) / p90) * 9) if p90 > 0 else 99)

    def _interpret_percentile(
        self,
        percentile: Optional[int],
        good_direction: str
    ) -> str:
        """Generate human-readable interpretation."""
        if percentile is None:
            return "Not enough data"

        if good_direction == 'higher':
            if percentile >= 90:
                return "Excellent - Top 10%"
            elif percentile >= 75:
                return "Great - Top 25%"
            elif percentile >= 50:
                return "Good - Above average"
            elif percentile >= 25:
                return "Below average - Room for improvement"
            else:
                return "Needs attention - Bottom 25%"
        else:
            # For metrics where lower is better
            if percentile <= 10:
                return "Excellent - Top 10%"
            elif percentile <= 25:
                return "Great - Top 25%"
            elif percentile <= 50:
                return "Good - Below average"
            elif percentile <= 75:
                return "Above average - Room for improvement"
            else:
                return "Needs attention - Top 25%"

    def _percentile_to_grade(self, percentile: Optional[float]) -> str:
        """Convert percentile to letter grade."""
        if percentile is None:
            return "N/A"
        if percentile >= 90:
            return "A+"
        elif percentile >= 80:
            return "A"
        elif percentile >= 70:
            return "B+"
        elif percentile >= 60:
            return "B"
        elif percentile >= 50:
            return "C+"
        elif percentile >= 40:
            return "C"
        elif percentile >= 30:
            return "D"
        else:
            return "F"

    def _get_recommendation(self, metric: str) -> str:
        """Get improvement recommendation for a metric."""
        recommendations = {
            'member_enrollment_rate': (
                "Consider adding signup incentives, prominently display "
                "membership benefits on your store, and train staff to "
                "mention the loyalty program at checkout."
            ),
            'redemption_rate': (
                "Send reminders about unused credit, create time-limited "
                "promotions, and ensure rewards are easy to redeem at checkout."
            ),
            'average_trade_value': (
                "Expand accepted trade-in categories, offer bonus credit "
                "for high-value items, and promote trade-ins through email "
                "campaigns."
            ),
            'trade_frequency': (
                "Run monthly trade-in promotions, send personalized "
                "reminders based on customer interests, and offer bonus "
                "credit for repeat trades."
            ),
            'tier_advancement_rate': (
                "Review tier thresholds to ensure they're achievable, "
                "communicate progress to members, and create special "
                "events for members close to the next tier."
            ),
            'member_clv': (
                "Focus on member retention, offer exclusive deals for "
                "higher tiers, and create VIP experiences for your best "
                "customers."
            ),
            'referral_conversion_rate': (
                "Increase referral rewards, make sharing easier with "
                "one-click links, and remind members about the referral "
                "program regularly."
            ),
            'retention_90_day': (
                "Improve onboarding experience, send engagement emails "
                "in the first 90 days, and create early-bird rewards for "
                "new members."
            )
        }

        return recommendations.get(metric, "Review your program settings and compare with top performers.")

    def _generate_recommendations(
        self,
        opportunities: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate prioritized recommendations."""
        if not opportunities:
            return [
                "Your loyalty program is performing well! "
                "Consider testing new features to stay ahead."
            ]

        recs = []
        for opp in opportunities[:3]:
            metric = opp.get('metric', '').lower().replace(' ', '_')
            if metric in self.METRICS:
                recs.append(self._get_recommendation(metric))

        return recs


def get_benchmark_service(tenant_id: int) -> BenchmarkService:
    """Get benchmark service for a tenant."""
    return BenchmarkService(tenant_id)
