from django.utils.deprecation import MiddlewareMixin

from loans.models import AuditLog


class AuditLogMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            actor = "anonymous"
            if hasattr(request, "user") and getattr(request.user, "is_authenticated", False):
                actor = str(request.user)
            AuditLog.objects.create(
                actor=actor,
                action=f"{request.method} {request.path}",
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                metadata={"query": request.META.get("QUERY_STRING", "")},
            )
        return response
