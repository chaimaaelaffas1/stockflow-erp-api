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
