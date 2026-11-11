import logging

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.core.exceptions import BusinessRuleError

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    # Case 1: Database foreign key protection
    if isinstance(exc, ProtectedError):
        logger.warning("Resource deletion blocked by a protected relation.")
        return Response(
            {
                "error": {
                    "code": "resource_in_use",
                    "message": "This resource is referenced and cannot be deleted.",
                    "details": {},
                }
            },
            status=status.HTTP_409_CONFLICT,
        )

    # Case 2: Custom business rule violations
    if isinstance(exc, BusinessRuleError):
        logger.warning(
            "Business rule violation: %s",
            exc.code,
        )
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
            status=status.HTTP_409_CONFLICT,
        )

    # Case 3: Standard DRF exceptions
    response = exception_handler(exc, context)

    # Case 4: Unhandled server errors (500)
    if response is None:
        logger.error(
            "Unhandled API exception",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return None

    # Case 5: Format standard DRF error responses
    if isinstance(exc, ValidationError):
        code = "validation_error"
        message = "Validation failed."
    else:
        code = getattr(exc, "default_code", "request_error")
        message = "Request failed."

    details = response.data
    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }

    return response
