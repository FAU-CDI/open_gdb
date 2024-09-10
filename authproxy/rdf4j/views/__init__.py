from typing import Any
from django.http import JsonResponse
from . import sparql


DEBUG = True
if DEBUG:
    import traceback


class ErrorResponse(JsonResponse):

    def __init__(
        self, message: str = None, error: Exception = None, **kwargs: Any
    ) -> None:
        data = {}
        if error:
            data["error"] = str(error)
        if message:
            data["message"] = message
        if DEBUG:
            data["error"] = {
                "message": str(error),
                "cls": error.__class__.__name__,
                "trace": traceback.format_exc(),
            }
        super().__init__(data, **kwargs)
