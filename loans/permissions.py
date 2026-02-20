from rest_framework.permissions import BasePermission


class IsLoanOfficer(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.has_perm("loans.can_approve_loan"))
        )


class IsSystemAutomation(BasePermission):
    def has_permission(self, request, view):
        token = request.headers.get("X-System-Token", "")
        from django.conf import settings

        return bool(token and token == settings.SYSTEM_AUTOMATION_TOKEN)


class IsClientAuthenticated(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and hasattr(user, "phone_number"))
