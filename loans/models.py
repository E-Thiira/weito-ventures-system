import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from decimal import Decimal

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Max, Sum
from django.utils import timezone

User = get_user_model()


def _fernet_instance() -> Fernet:
	key = settings.FIELD_ENCRYPTION_KEY
	if not key:
		fallback = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
		key = base64.urlsafe_b64encode(fallback).decode("utf-8")
	return Fernet(key.encode("utf-8"))


def hash_value(value: str) -> str:
	digest = hashlib.sha256()
	digest.update(settings.DATA_HASH_SALT.encode("utf-8"))
	digest.update(value.encode("utf-8"))
	return digest.hexdigest()


def encrypt_value(value: str) -> str:
	return _fernet_instance().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str) -> str:
	try:
		return _fernet_instance().decrypt(value.encode("utf-8")).decode("utf-8")
	except (InvalidToken, ValueError, TypeError):
		return ""


class Client(models.Model):
	name = models.CharField(max_length=255)
	phone_number = models.CharField(max_length=20, unique=True, db_index=True)
	id_number_encrypted = models.TextField(blank=True, default="")
	id_number_hash = models.CharField(max_length=64, unique=True, db_index=True, null=True, blank=True)
	credit_score = models.PositiveSmallIntegerField(default=0, db_index=True)
	max_loan_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("5000.00"))
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		indexes = [
			models.Index(fields=["name"]),
			models.Index(fields=["phone_number", "credit_score"]),
		]

	def __str__(self) -> str:
		return f"{self.name} ({self.phone_number})"

	@property
	def id_number(self) -> str:
		return decrypt_value(self.id_number_encrypted)

	def set_id_number(self, plain_id_number: str):
		normalized = plain_id_number.strip()
		self.id_number_encrypted = encrypt_value(normalized)
		self.id_number_hash = hash_value(normalized)


class Loan(models.Model):
	class Status(models.TextChoices):
		ACTIVE = "ACTIVE", "Active"
		PAID = "PAID", "Paid"
		OVERDUE = "OVERDUE", "Overdue"

	class ApprovalStatus(models.TextChoices):
		PENDING = "PENDING", "Pending"
		APPROVED = "APPROVED", "Approved"
		REJECTED = "REJECTED", "Rejected"

	client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="loans")
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	status = models.CharField(
		max_length=10,
		choices=Status.choices,
		default=Status.ACTIVE,
		db_index=True,
		editable=False,
	)
	approval_status = models.CharField(
		max_length=10,
		choices=ApprovalStatus.choices,
		default=ApprovalStatus.PENDING,
		db_index=True,
	)
	approved_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		related_name="approved_loans",
		null=True,
		blank=True,
	)
	approved_at = models.DateTimeField(null=True, blank=True)
	due_date = models.DateField(db_index=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)

	class Meta:
		permissions = [
			("can_approve_loan", "Can approve loan"),
		]
		indexes = [
			models.Index(fields=["status", "due_date"]),
			models.Index(fields=["client", "status"]),
			models.Index(fields=["created_at", "status"]),
			models.Index(fields=["approval_status", "created_at"]),
		]

	def __str__(self) -> str:
		return f"Loan #{self.pk} - {self.client.name}"

	@property
	def total_paid(self) -> Decimal:
		if not self.pk:
			return Decimal("0.00")
		aggregate = self.payments.aggregate(total=Sum("amount"))
		return aggregate["total"] or Decimal("0.00")

	@property
	def balance(self) -> Decimal:
		remaining = self.amount - self.total_paid
		return remaining if remaining > Decimal("0.00") else Decimal("0.00")

	@property
	def latest_payment_at(self):
		return self.payments.aggregate(last=Max("paid_at"))["last"]

	def calculate_status(self) -> str:
		today = timezone.localdate()
		if self.total_paid >= self.amount:
			return self.Status.PAID
		if self.due_date < today:
			return self.Status.OVERDUE
		return self.Status.ACTIVE

	def refresh_status(self, commit: bool = True) -> str:
		computed_status = self.calculate_status()
		if self.status != computed_status:
			self.status = computed_status
			if commit:
				self.save(update_fields=["status"], automation_update=True)
		return self.status

	def save(self, *args, **kwargs):
		kwargs.pop("automation_update", None)
		self.status = self.calculate_status()
		super().save(*args, **kwargs)


class Payment(models.Model):
	loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="payments")
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	mpesa_receipt = models.CharField(max_length=50, unique=True, db_index=True)
	phone = models.CharField(max_length=20, db_index=True)
	paid_at = models.DateTimeField(default=timezone.now, db_index=True)
	raw_payload = models.JSONField(default=dict, blank=True)
	raw_payload_encrypted = models.TextField(blank=True, default="")

	class Meta:
		indexes = [
			models.Index(fields=["loan", "paid_at"]),
			models.Index(fields=["phone", "paid_at"]),
			models.Index(fields=["mpesa_receipt", "paid_at"]),
		]

	def __str__(self) -> str:
		return f"Payment {self.mpesa_receipt} - Loan #{self.loan_id}"

	def save(self, *args, **kwargs):
		if self.raw_payload:
			self.raw_payload_encrypted = encrypt_value(json.dumps(self.raw_payload, separators=(",", ":")))
		super().save(*args, **kwargs)


class LoanReminderLog(models.Model):
	class ReminderType(models.TextChoices):
		DUE_SOON = "DUE_SOON", "Due Soon"
		OVERDUE = "OVERDUE", "Overdue"

	loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="reminder_logs")
	reminder_type = models.CharField(max_length=12, choices=ReminderType.choices)
	sent_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["loan", "reminder_type"],
				name="unique_loan_reminder_type",
			)
		]
		indexes = [
			models.Index(fields=["reminder_type", "sent_at"]),
			models.Index(fields=["loan", "sent_at"]),
		]

	def __str__(self) -> str:
		return f"{self.loan_id} - {self.reminder_type}"


class ClientOTP(models.Model):
	phone_number = models.CharField(max_length=20, db_index=True)
	otp_hash = models.CharField(max_length=64)
	expires_at = models.DateTimeField(db_index=True)
	attempts = models.PositiveSmallIntegerField(default=0)
	verified_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		indexes = [
			models.Index(fields=["phone_number", "created_at"]),
		]

	@classmethod
	def issue_for_phone(cls, phone_number: str):
		otp = f"{secrets.randbelow(900000) + 100000}"
		instance = cls.objects.create(
			phone_number=phone_number,
			otp_hash=hash_value(otp),
			expires_at=timezone.now() + timedelta(minutes=5),
		)
		return instance, otp

	def verify(self, otp: str) -> bool:
		if self.verified_at:
			return False
		if timezone.now() > self.expires_at or self.attempts >= 5:
			return False
		self.attempts += 1
		if hmac.compare_digest(self.otp_hash, hash_value(otp)):
			self.verified_at = timezone.now()
			self.save(update_fields=["attempts", "verified_at"])
			return True
		self.save(update_fields=["attempts"])
		return False


class ClientAccessToken(models.Model):
	client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="access_tokens")
	token_hash = models.CharField(max_length=64, unique=True, db_index=True)
	expires_at = models.DateTimeField(db_index=True)
	created_at = models.DateTimeField(auto_now_add=True)
	last_used_at = models.DateTimeField(null=True, blank=True)
	revoked_at = models.DateTimeField(null=True, blank=True)

	@classmethod
	def create_token(cls, client: Client):
		raw_token = secrets.token_urlsafe(32)
		token = cls.objects.create(
			client=client,
			token_hash=hash_value(raw_token),
			expires_at=timezone.now() + timedelta(hours=24),
		)
		return token, raw_token

	def is_active(self) -> bool:
		return self.revoked_at is None and self.expires_at > timezone.now()


class NotificationLog(models.Model):
	class Channel(models.TextChoices):
		WHATSAPP = "WHATSAPP", "WhatsApp"
		SMS = "SMS", "SMS"

	phone_number = models.CharField(max_length=20, db_index=True)
	channel = models.CharField(max_length=10, choices=Channel.choices)
	message = models.TextField()
	success = models.BooleanField(default=False)
	attempts = models.PositiveSmallIntegerField(default=1)
	error_message = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		indexes = [models.Index(fields=["success", "created_at"]), models.Index(fields=["phone_number", "created_at"])]


class AuditLog(models.Model):
	actor = models.CharField(max_length=120, db_index=True)
	action = models.CharField(max_length=255)
	endpoint = models.CharField(max_length=255)
	method = models.CharField(max_length=10)
	status_code = models.PositiveSmallIntegerField()
	metadata = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)

	class Meta:
		indexes = [models.Index(fields=["created_at", "status_code"]), models.Index(fields=["actor", "created_at"])]
