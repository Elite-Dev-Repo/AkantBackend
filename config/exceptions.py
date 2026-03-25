from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns consistent error response shapes.
    {
        "success": false,
        "message": "Human-readable summary",
        "errors": { ... }   # field-level detail when available
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            "success": False,
            "message": _extract_message(response.data),
            "errors": response.data,
        }
        response.data = error_data
    else:
        # Unhandled exception — log and return 500
        logger.exception("Unhandled exception in %s", context.get("view"))
        return Response(
            {
                "success": False,
                "message": "An unexpected error occurred. Please try again.",
                "errors": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response


def _extract_message(data):
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        # grab first field error
        for key, value in data.items():
            if isinstance(value, list) and value:
                return f"{key}: {value[0]}"
            if isinstance(value, str):
                return f"{key}: {value}"
        return "Validation failed."
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data)
