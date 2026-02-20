from django.contrib import admin

from .models import (
	AuditLog,
	Client,
	ClientAccessToken,
	ClientOTP,
	Loan,
	LoanReminderLog,
	NotificationLog,
	Payment,
	SuspiciousActivityLog,
)


class ReadOnlyAdmin(admin.ModelAdmin):
	def has_add_permission(self, request):
		return False

	def has_change_permission(self, request, obj=None):
		return False

	def has_delete_permission(self, request, obj=None):
		return False


@admin.register(Client)
class ClientAdmin(ReadOnlyAdmin):
	list_display = ("id", "name", "phone_number", "credit_score", "max_loan_limit", "created_at")
	search_fields = ("name", "phone_number", "id_number_hash")
	readonly_fields = (
		"name",
		"phone_number",
		"id_number_hash",
		"credit_score",
		"max_loan_limit",
		"created_at",
		"updated_at",
	)


@admin.register(Loan)
class LoanAdmin(ReadOnlyAdmin):
	list_display = (
		"id",
		"client",
		"amount",
		"status",
		"approval_status",
		"due_date",
		"created_at",
	)
	list_filter = ("status", "approval_status", "due_date")
	search_fields = ("client__name", "client__phone_number", "client__id_number_hash")
	readonly_fields = (
		"client",
		"amount",
		"status",
		"approval_status",
		"approved_by",
		"approved_at",
		"due_date",
		"created_at",
	)


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdmin):
	list_display = ("id", "loan", "amount", "mpesa_receipt", "phone", "paid_at")
	list_filter = ("paid_at",)
	search_fields = ("mpesa_receipt", "phone", "loan__client__name")
	readonly_fields = (
		"loan",
		"amount",
		"mpesa_receipt",
		"phone",
		"paid_at",
		"raw_payload",
		"raw_payload_encrypted",
	)


@admin.register(LoanReminderLog)
class LoanReminderLogAdmin(ReadOnlyAdmin):
	list_display = ("id", "loan", "reminder_type", "sent_at")
	list_filter = ("reminder_type", "sent_at")
	readonly_fields = ("loan", "reminder_type", "sent_at")


@admin.register(ClientOTP)
class ClientOTPAdmin(ReadOnlyAdmin):
	list_display = ("id", "phone_number", "expires_at", "attempts", "verified_at", "created_at")
	readonly_fields = ("phone_number", "otp_hash", "expires_at", "attempts", "verified_at", "created_at")


@admin.register(ClientAccessToken)
class ClientAccessTokenAdmin(ReadOnlyAdmin):
	list_display = ("id", "client", "expires_at", "created_at", "last_used_at", "revoked_at")
	readonly_fields = ("client", "token_hash", "expires_at", "created_at", "last_used_at", "revoked_at")


@admin.register(NotificationLog)
class NotificationLogAdmin(ReadOnlyAdmin):
	list_display = ("id", "phone_number", "channel", "success", "attempts", "created_at")
	list_filter = ("channel", "success", "created_at")
	readonly_fields = ("phone_number", "channel", "message", "success", "attempts", "error_message", "created_at")


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
	list_display = ("id", "actor", "method", "endpoint", "status_code", "created_at")
	list_filter = ("method", "status_code", "created_at")
	readonly_fields = ("actor", "action", "endpoint", "method", "status_code", "metadata", "created_at")


@admin.register(SuspiciousActivityLog)
class SuspiciousActivityLogAdmin(ReadOnlyAdmin):
	list_display = ("id", "category", "reference", "severity", "resolved", "created_at")
	list_filter = ("category", "severity", "resolved", "created_at")
	readonly_fields = ("category", "reference", "severity", "details", "resolved", "created_at")
