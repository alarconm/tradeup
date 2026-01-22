"""
Standardized error response utilities for TradeUp API.

Provides consistent error response format across all endpoints:
{
    "error": {
        "message": "User-friendly error message",
        "code": "ERROR_CODE"
    }
}

Usage:
    from app.utils.errors import error_response, ErrorCode

    return error_response("Member not found", ErrorCode.NOT_FOUND, 404)
"""
import logging
from enum import Enum
from flask import jsonify
from typing import Optional

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Authentication & Authorization (401, 403)
    AUTH_REQUIRED = "AUTH_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SUBSCRIPTION_REQUIRED = "SUBSCRIPTION_REQUIRED"

    # Validation Errors (400)
    INVALID_REQUEST = "INVALID_REQUEST"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FIELD = "INVALID_FIELD"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Not Found (404)
    NOT_FOUND = "NOT_FOUND"
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    TIER_NOT_FOUND = "TIER_NOT_FOUND"
    BATCH_NOT_FOUND = "BATCH_NOT_FOUND"
    SHOP_NOT_FOUND = "SHOP_NOT_FOUND"
    ITEM_NOT_FOUND = "ITEM_NOT_FOUND"

    # Conflict (409)
    ALREADY_EXISTS = "ALREADY_EXISTS"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    STATE_CONFLICT = "STATE_CONFLICT"

    # Business Logic Errors (400, 422)
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    INVALID_STATUS = "INVALID_STATUS"
    OPERATION_FAILED = "OPERATION_FAILED"

    # External Service Errors (502, 503)
    SHOPIFY_ERROR = "SHOPIFY_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"

    # Server Errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"


def error_response(
    message: str,
    code: ErrorCode = ErrorCode.INTERNAL_ERROR,
    status_code: int = 500,
    log_error: bool = True,
    details: Optional[dict] = None
) -> tuple:
    """
    Create a standardized error response.

    Args:
        message: User-friendly error message
        code: Error code from ErrorCode enum
        status_code: HTTP status code
        log_error: Whether to log the error (default True for 500s)
        details: Optional additional details (only logged, not returned to user)

    Returns:
        Tuple of (response, status_code) for Flask
    """
    # Log errors for debugging (500s always logged, others optional)
    if log_error and status_code >= 500:
        logger.error(f"API Error [{code}]: {message}", extra={"details": details})
    elif log_error and status_code >= 400:
        logger.warning(f"API Error [{code}]: {message}", extra={"details": details})

    response = {
        "error": {
            "message": message,
            "code": code.value if isinstance(code, ErrorCode) else code
        }
    }

    return jsonify(response), status_code


# Convenience functions for common error types
def bad_request(message: str, code: ErrorCode = ErrorCode.INVALID_REQUEST) -> tuple:
    """400 Bad Request error."""
    return error_response(message, code, 400, log_error=False)


def unauthorized(message: str = "Authentication required", code: ErrorCode = ErrorCode.AUTH_REQUIRED) -> tuple:
    """401 Unauthorized error."""
    return error_response(message, code, 401, log_error=False)


def forbidden(message: str = "Permission denied", code: ErrorCode = ErrorCode.PERMISSION_DENIED) -> tuple:
    """403 Forbidden error."""
    return error_response(message, code, 403, log_error=False)


def not_found(message: str, code: ErrorCode = ErrorCode.NOT_FOUND) -> tuple:
    """404 Not Found error."""
    return error_response(message, code, 404, log_error=False)


def conflict(message: str, code: ErrorCode = ErrorCode.STATE_CONFLICT) -> tuple:
    """409 Conflict error."""
    return error_response(message, code, 409, log_error=False)


def internal_error(message: str = "An unexpected error occurred", details: Optional[dict] = None) -> tuple:
    """500 Internal Server Error."""
    return error_response(message, ErrorCode.INTERNAL_ERROR, 500, log_error=True, details=details)
