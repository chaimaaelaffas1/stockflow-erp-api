class BusinessRuleError(Exception):
    """
    Base exception for business rule errors.
    """

    code = "business_rule_violation"

    def __init__(self, message="", details=None):
        super().__init__(message)

        self.message = message
        self.details = details or {}


class InvalidTransition(BusinessRuleError):
    """
    Raised when a business object
    cannot change to the requested state.
    """

    code = "invalid_transition"


class InsufficientStock(BusinessRuleError):
    """
    Raised when available stock is insufficient.
    """

    code = "insufficient_stock"


class OverReceipt(BusinessRuleError):
    """
    Raised when received quantity exceeds ordered quantity.
    """

    code = "over_receipt"


class EmptyOrder(BusinessRuleError):
    """
    Raised when trying to place an order without lines.
    """

    code = "empty_order"


class IdempotencyConflict(BusinessRuleError):
    """
    Raised when an idempotency key is reused with another payload.
    """

    code = "idempotency_conflict"
