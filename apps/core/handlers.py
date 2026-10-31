from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):

    # Case 1: Resource is protected by another model
    if isinstance(exc, ProtectedError):
        return Response(
            {
                "error": {
                    "code": "resource_in_use",
                    "message": ("This resource is referenced and cannot be deleted."),
                    "details": {},
                }
            },
            status=status.HTTP_409_CONFLICT,
        )

    # Case 2: Let DRF handle standard exceptions
    response = exception_handler(exc, context)

    # Case 3: Unknown exception
    if response is None:
        return None

    # Case 4: Validation errors
    if isinstance(exc, ValidationError):
        code = "validation_error"
        message = "Validation failed."

    else:
        code = getattr(
            exc,
            "default_code",
            "request_error",
        )

        message = "Request failed."

    # Keep original error details
    details = response.data

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }

    return response
