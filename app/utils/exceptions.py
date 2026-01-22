"""
Custom exceptions for TradeUp business logic.

These exceptions provide more specific error handling than generic Exception,
allowing for better error messages and appropriate HTTP status codes.
"""


class TradeUpError(Exception):
    """Base exception for all TradeUp business logic errors."""

    def __init__(self, message: str, code: str = "TRADEUP_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(TradeUpError):
    """Resource not found."""

    def __init__(self, resource: str, identifier=None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with ID {identifier} not found"
        super().__init__(message, f"{resource.upper()}_NOT_FOUND")


class MemberNotFoundError(NotFoundError):
    """Member not found."""

    def __init__(self, identifier=None):
        super().__init__("Member", identifier)


class TierNotFoundError(NotFoundError):
    """Tier not found."""

    def __init__(self, identifier=None):
        super().__init__("Tier", identifier)


class ValidationError(TradeUpError):
    """Invalid input data."""

    def __init__(self, message: str, field: str = None):
        self.field = field
        code = f"INVALID_{field.upper()}" if field else "VALIDATION_ERROR"
        super().__init__(message, code)


class InsufficientBalanceError(TradeUpError):
    """Not enough balance for the operation."""

    def __init__(self, current: float, required: float, currency: str = "credits"):
        self.current = current
        self.required = required
        message = f"Insufficient {currency}. Current: {current}, Required: {required}"
        super().__init__(message, "INSUFFICIENT_BALANCE")


class InsufficientPointsError(InsufficientBalanceError):
    """Not enough points for the operation."""

    def __init__(self, current: int, required: int):
        super().__init__(float(current), float(required), "points")
        self.code = "INSUFFICIENT_POINTS"


class LimitExceededError(TradeUpError):
    """Resource limit exceeded (e.g., member count, tier count)."""

    def __init__(self, resource: str, limit: int, current: int):
        self.limit = limit
        self.current = current
        message = f"{resource} limit exceeded. Limit: {limit}, Current: {current}"
        super().__init__(message, f"{resource.upper()}_LIMIT_EXCEEDED")


class InvalidStatusTransitionError(TradeUpError):
    """Invalid status transition for a resource."""

    def __init__(self, resource: str, from_status: str, to_status: str):
        self.from_status = from_status
        self.to_status = to_status
        message = f"Cannot change {resource} status from '{from_status}' to '{to_status}'"
        super().__init__(message, "INVALID_STATUS_TRANSITION")


class ShopifyError(TradeUpError):
    """Error communicating with Shopify API."""

    def __init__(self, message: str, original_error: Exception = None):
        self.original_error = original_error
        super().__init__(message, "SHOPIFY_ERROR")


class DuplicateError(TradeUpError):
    """Resource already exists."""

    def __init__(self, resource: str, identifier=None):
        message = f"{resource} already exists"
        if identifier:
            message = f"{resource} with {identifier} already exists"
        super().__init__(message, "DUPLICATE_ENTRY")


class AuthorizationError(TradeUpError):
    """User not authorized for this operation."""

    def __init__(self, message: str = "Not authorized for this operation"):
        super().__init__(message, "AUTHORIZATION_ERROR")


class ConfigurationError(TradeUpError):
    """Application configuration error."""

    def __init__(self, message: str):
        super().__init__(message, "CONFIGURATION_ERROR")
