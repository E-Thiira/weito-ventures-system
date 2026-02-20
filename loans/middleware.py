import logging
import time

from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import APIException

from loans.models import AuditLog

logger = logging.getLogger(__name__)


class AuditLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._request_start_time = time.perf_counter()

    def process_exception(self, request, exception):
        if isinstance(exception, (PermissionDenied, APIException)):
            return None
        logger.exception("Unhandled exception on %s %s", request.method, request.path, exc_info=exception)

    def process_response(self, request, response):
        if request.path.startswith("/api/"):
            actor = "anonymous"
            if hasattr(request, "user") and getattr(request.user, "is_authenticated", False):
                actor = str(request.user)

            start = getattr(request, "_request_start_time", None)
            duration_ms = None
            if start:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)

            AuditLog.objects.create(
                actor=actor,
                action=f"{request.method} {request.path}",
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                metadata={
                    "query": request.META.get("QUERY_STRING", ""),
                    "duration_ms": duration_ms,
                    "status_code": response.status_code,
                },
            )
        return response
