"""
Benchmark API endpoints for TradeUp.

Provides industry benchmarks and store comparison data.
Helps merchants understand how their loyalty program performs.
"""

from flask import Blueprint, request, jsonify, g
from ..middleware.shopify_auth import require_shopify_auth
from ..services.benchmark_service import get_benchmark_service

benchmarks_bp = Blueprint('benchmarks', __name__)


@benchmarks_bp.route('/', methods=['GET'])
@require_shopify_auth
def get_all_benchmarks():
    """
    Get all industry benchmarks with store comparison.

    Query params:
    - category: Industry category for segmentation (optional)
                Options: sports_cards, pokemon, mtg, collectibles, etc.

    Returns:
        benchmarks: Dict of all metrics with percentile data
        your_value: This store's value for each metric
        your_percentile: Where this store ranks
    """
    try:
        category = request.args.get('category')

        service = get_benchmark_service(g.tenant_id)
        result = service.get_industry_benchmarks(category)

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@benchmarks_bp.route('/metric/<metric>', methods=['GET'])
@require_shopify_auth
def get_metric_benchmark(metric):
    """
    Get benchmark data for a specific metric.

    Path params:
    - metric: The metric key to check

    Returns:
        metric_info: Description and unit
        your_value: This store's value
        percentile: Where this store ranks (0-99)
        interpretation: Human-readable assessment
        benchmarks: Percentile breakpoints (p25, p50, p75, p90)
    """
    try:
        service = get_benchmark_service(g.tenant_id)
        result = service.get_store_percentile(metric)

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@benchmarks_bp.route('/report', methods=['GET'])
@require_shopify_auth
def get_comparison_report():
    """
    Get comprehensive benchmark comparison report.

    Returns:
        overall_score: Average percentile across all metrics
        overall_grade: Letter grade (A+ to F)
        metrics: All metrics with values and percentiles
        strengths: Top 3 performing areas
        opportunities: Top 3 areas for improvement
        recommendations: Actionable improvement suggestions
    """
    try:
        service = get_benchmark_service(g.tenant_id)
        result = service.get_comparison_report()

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@benchmarks_bp.route('/categories', methods=['GET'])
@require_shopify_auth
def get_categories():
    """
    Get available industry categories for benchmarking.

    Returns:
        categories: List of available category options
    """
    from ..services.benchmark_service import BenchmarkService

    return jsonify({
        'success': True,
        'categories': [
            {'id': 'sports_cards', 'name': 'Sports Cards'},
            {'id': 'pokemon', 'name': 'Pokemon TCG'},
            {'id': 'mtg', 'name': 'Magic: The Gathering'},
            {'id': 'collectibles', 'name': 'General Collectibles'},
            {'id': 'comics', 'name': 'Comics & Manga'},
            {'id': 'toys', 'name': 'Toys & Figures'},
            {'id': 'vintage', 'name': 'Vintage & Antiques'},
            {'id': 'general_retail', 'name': 'General Retail'}
        ]
    })


@benchmarks_bp.route('/metrics', methods=['GET'])
@require_shopify_auth
def get_available_metrics():
    """
    Get list of available benchmark metrics with descriptions.

    Returns:
        metrics: Dict of metric keys with name, description, unit
    """
    from ..services.benchmark_service import BenchmarkService

    return jsonify({
        'success': True,
        'metrics': BenchmarkService.METRICS
    })
