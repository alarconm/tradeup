"""
Judge.me Integration Service for TradeUp.

Awards loyalty points when customers leave product reviews.
Supports different point amounts for text, photo, and video reviews.

API Documentation: https://judge.me/
"""

import requests
import hmac
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from flask import current_app

from ..extensions import db
from ..models.member import Member
from ..models.tenant import Tenant


class JudgeMeService:
    """
    Judge.me product review integration.

    Awards points when customers submit reviews, with bonuses
    for photo and video reviews.

    Usage:
        service = JudgeMeService(tenant_id)
        result = service.handle_review_created(review_data)
    """

    BASE_URL = "https://judge.me/api/v1"

    # Default points configuration
    DEFAULT_POINTS_TEXT_REVIEW = 50
    DEFAULT_POINTS_PHOTO_REVIEW = 100
    DEFAULT_POINTS_VIDEO_REVIEW = 200
    DEFAULT_MAX_REVIEWS_PER_DAY = 3

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._tenant = None
        self._settings = None
        self._api_token = None
        self._shop_domain = None

    @property
    def tenant(self) -> Tenant:
        if self._tenant is None:
            self._tenant = Tenant.query.get(self.tenant_id)
        return self._tenant

    @property
    def settings(self) -> Dict[str, Any]:
        if self._settings is None:
            self._settings = {}
            if self.tenant and self.tenant.settings:
                integrations = self.tenant.settings.get('integrations', {})
                self._settings = integrations.get('judgeme', {})
        return self._settings

    @property
    def api_token(self) -> Optional[str]:
        if self._api_token is None:
            self._api_token = self.settings.get('api_token')
        return self._api_token

    @property
    def shop_domain(self) -> Optional[str]:
        if self._shop_domain is None:
            self._shop_domain = self.settings.get('shop_domain') or (
                self.tenant.shop_domain if self.tenant else None
            )
        return self._shop_domain

    def is_enabled(self) -> bool:
        """Check if Judge.me integration is enabled."""
        return bool(self.settings.get('enabled') and self.api_token)

    def get_points_config(self) -> Dict[str, int]:
        """Get points configuration for reviews."""
        return {
            'text_review': self.settings.get('points_per_review', self.DEFAULT_POINTS_TEXT_REVIEW),
            'photo_review': self.settings.get('points_per_photo_review', self.DEFAULT_POINTS_PHOTO_REVIEW),
            'video_review': self.settings.get('points_per_video_review', self.DEFAULT_POINTS_VIDEO_REVIEW),
            'max_per_day': self.settings.get('max_reviews_per_day', self.DEFAULT_MAX_REVIEWS_PER_DAY)
        }

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> Dict[str, Any]:
        """Test the Judge.me API connection."""
        if not self.api_token or not self.shop_domain:
            return {'success': False, 'error': 'API token or shop domain not configured'}

        try:
            response = requests.get(
                f'{self.BASE_URL}/widgets/product_review',
                params={
                    'api_token': self.api_token,
                    'shop_domain': self.shop_domain
                },
                timeout=10
            )

            if response.status_code == 200:
                return {
                    'success': True,
                    'message': 'Connection successful'
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Judge.me connection test failed: {e}")
            return {'success': False, 'error': str(e)}

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Verify Judge.me webhook signature.

        Args:
            payload: Raw request body
            signature: X-Judge-Me-Signature header value

        Returns:
            True if signature is valid
        """
        webhook_secret = self.settings.get('webhook_secret')
        if not webhook_secret:
            return False

        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    def handle_review_created(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a new review from Judge.me webhook.

        Awards points to the reviewer based on review type.

        Args:
            review_data: Review data from webhook

        Returns:
            Dict with processing result
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Judge.me not enabled'}

        reviewer_email = review_data.get('reviewer', {}).get('email')
        if not reviewer_email:
            return {'success': False, 'error': 'No reviewer email in review data'}

        # Find member
        member = Member.query.filter_by(
            tenant_id=self.tenant_id,
            email=reviewer_email
        ).first()

        if not member:
            return {
                'success': False,
                'error': 'Reviewer is not a member',
                'email': reviewer_email
            }

        # Check daily limit
        if not self._check_daily_limit(member.id):
            return {
                'success': False,
                'error': 'Daily review limit reached',
                'member_id': member.id
            }

        # Determine review type and points
        points_config = self.get_points_config()
        has_video = bool(review_data.get('video_url'))
        has_photos = bool(review_data.get('pictures') and len(review_data.get('pictures', [])) > 0)

        if has_video:
            points = points_config['video_review']
            review_type = 'video'
        elif has_photos:
            points = points_config['photo_review']
            review_type = 'photo'
        else:
            points = points_config['text_review']
            review_type = 'text'

        # Award points
        result = self._award_review_points(
            member=member,
            points=points,
            review_type=review_type,
            review_data=review_data
        )

        return result

    def _check_daily_limit(self, member_id: int) -> bool:
        """Check if member has exceeded daily review limit."""
        from ..models.loyalty_points import PointsLedger, PointsEarnSource

        points_config = self.get_points_config()
        max_per_day = points_config['max_per_day']

        # Count reviews today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        today_reviews = PointsLedger.query.filter(
            PointsLedger.member_id == member_id,
            PointsLedger.source == PointsEarnSource.REVIEW.value,
            PointsLedger.created_at >= today_start
        ).count()

        return today_reviews < max_per_day

    def _award_review_points(
        self,
        member: Member,
        points: int,
        review_type: str,
        review_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Award points for a review."""
        try:
            from ..services.points_service import get_points_service

            points_service = get_points_service(self.tenant_id)

            # Build description
            product_title = review_data.get('product', {}).get('title', 'a product')
            description = f'Points for {review_type} review of {product_title}'

            # Award points
            result = points_service.award_points(
                member_id=member.id,
                points=points,
                source='review',
                source_id=str(review_data.get('id', '')),
                description=description,
                metadata={
                    'review_type': review_type,
                    'product_id': review_data.get('product', {}).get('id'),
                    'rating': review_data.get('rating')
                }
            )

            if result.get('success'):
                # Track for analytics
                self._track_review_points(member.id, points, review_type)

            return {
                'success': result.get('success', False),
                'points_awarded': points,
                'review_type': review_type,
                'member_id': member.id,
                'new_balance': result.get('new_balance', 0)
            }

        except Exception as e:
            current_app.logger.error(f"Failed to award review points: {e}")
            return {'success': False, 'error': str(e)}

    def _track_review_points(self, member_id: int, points: int, review_type: str):
        """Track review points for analytics."""
        # This could be expanded to track in a dedicated table
        current_app.logger.info(
            f"Review points awarded: member={member_id}, points={points}, type={review_type}"
        )

    def get_member_reviews(self, member_id: int) -> List[Dict[str, Any]]:
        """
        Get reviews by a member.

        Args:
            member_id: Member ID

        Returns:
            List of review point entries
        """
        from ..models.loyalty_points import PointsLedger, PointsEarnSource

        entries = PointsLedger.query.filter(
            PointsLedger.member_id == member_id,
            PointsLedger.source == PointsEarnSource.REVIEW.value
        ).order_by(PointsLedger.created_at.desc()).limit(50).all()

        return [{
            'id': entry.id,
            'points': entry.points,
            'description': entry.description,
            'created_at': entry.created_at.isoformat() if entry.created_at else None,
            'metadata': entry.metadata
        } for entry in entries]

    def get_review_stats(self) -> Dict[str, Any]:
        """Get review points statistics for the tenant."""
        from ..models.loyalty_points import PointsLedger, PointsEarnSource
        from sqlalchemy import func

        # Total points awarded for reviews
        total_points = db.session.query(
            func.sum(PointsLedger.points)
        ).filter(
            PointsLedger.tenant_id == self.tenant_id,
            PointsLedger.source == PointsEarnSource.REVIEW.value
        ).scalar() or 0

        # Total reviews rewarded
        total_reviews = PointsLedger.query.filter(
            PointsLedger.tenant_id == self.tenant_id,
            PointsLedger.source == PointsEarnSource.REVIEW.value
        ).count()

        # Unique reviewers
        unique_reviewers = db.session.query(
            func.count(func.distinct(PointsLedger.member_id))
        ).filter(
            PointsLedger.tenant_id == self.tenant_id,
            PointsLedger.source == PointsEarnSource.REVIEW.value
        ).scalar() or 0

        return {
            'total_points_awarded': int(total_points),
            'total_reviews_rewarded': total_reviews,
            'unique_reviewers': unique_reviewers,
            'avg_points_per_review': int(total_points / total_reviews) if total_reviews > 0 else 0
        }


def get_judgeme_service(tenant_id: int) -> JudgeMeService:
    """Get Judge.me service for a tenant."""
    return JudgeMeService(tenant_id)
