from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from loans.models import Client, Loan, LoanReminderLog, Payment, SuspiciousActivityLog
from loans.tasks import send_due_soon_reminders


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True, CELERY_TASK_STORE_EAGER_RESULT=False)
class LoanAutomationIntegrationTests(APITestCase):
	def setUp(self):
		self.client_record = Client(name="John Doe", phone_number="254700000001")
		self.client_record.set_id_number("12345678")
		self.client_record.save()

	def create_loan(self, amount="1000.00", due_date=None):
		due = due_date or (timezone.localdate() + timedelta(days=7))
		return Loan.objects.create(client=self.client_record, amount=Decimal(amount), due_date=due)

	def test_loan_creation_sets_automated_active_status(self):
		loan = self.create_loan()
		self.assertEqual(loan.status, Loan.Status.ACTIVE)

	@override_settings(MPESA_CALLBACK_TOKEN="test-token", MPESA_WEBHOOK_SECRET="")
	@patch("loans.signals.send_payment_confirmation_sms.delay")
	def test_payment_webhook_creates_payment_and_marks_loan_paid(self, _mock_delay):
		loan = self.create_loan(amount="1000.00")
		url = reverse("mpesa-callback", kwargs={"token": "test-token", "loan_id": loan.id})
		payload = {
			"Body": {
				"stkCallback": {
					"ResultCode": 0,
					"CallbackMetadata": {
						"Item": [
							{"Name": "Amount", "Value": 1000},
							{"Name": "MpesaReceiptNumber", "Value": "ABC123XYZ"},
							{"Name": "PhoneNumber", "Value": 254700000001},
						]
					},
				}
			}
		}

		response = self.client.post(url, payload, format="json")
		loan.refresh_from_db()

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(Payment.objects.filter(loan=loan).count(), 1)
		self.assertEqual(loan.status, Loan.Status.PAID)

	@override_settings(MPESA_CALLBACK_TOKEN="test-token", MPESA_WEBHOOK_SECRET="")
	@patch("loans.signals.send_payment_confirmation_sms.delay")
	def test_duplicate_webhook_receipt_is_ignored(self, _mock_delay):
		loan = self.create_loan(amount="500.00")
		url = reverse("mpesa-callback", kwargs={"token": "test-token", "loan_id": loan.id})
		payload = {
			"Body": {
				"stkCallback": {
					"ResultCode": 0,
					"CallbackMetadata": {
						"Item": [
							{"Name": "Amount", "Value": 500},
							{"Name": "MpesaReceiptNumber", "Value": "DUPL111"},
							{"Name": "PhoneNumber", "Value": 254700000001},
						]
					},
				}
			}
		}

		self.client.post(url, payload, format="json")
		self.client.post(url, payload, format="json")

		self.assertEqual(Payment.objects.filter(loan=loan, mpesa_receipt="DUPL111").count(), 1)
		self.assertTrue(
			SuspiciousActivityLog.objects.filter(reference=f"loan:{loan.id}", category="OVERPAYMENT_ATTEMPT").exists()
			or SuspiciousActivityLog.objects.filter(category="DUPLICATE_RECEIPT", reference="DUPL111").exists()
		)

	@override_settings(MPESA_CALLBACK_TOKEN="test-token", MPESA_WEBHOOK_SECRET="")
	@patch("loans.signals.send_payment_confirmation_sms.delay")
	def test_overpayment_attempt_is_blocked_and_logged(self, _mock_delay):
		loan = self.create_loan(amount="500.00")
		url = reverse("mpesa-callback", kwargs={"token": "test-token", "loan_id": loan.id})
		payload = {
			"Body": {
				"stkCallback": {
					"ResultCode": 0,
					"CallbackMetadata": {
						"Item": [
							{"Name": "Amount", "Value": 800},
							{"Name": "MpesaReceiptNumber", "Value": "OVERP1"},
							{"Name": "PhoneNumber", "Value": 254700000001},
						]
					},
				}
			}
		}

		response = self.client.post(url, payload, format="json")
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertFalse(Payment.objects.filter(mpesa_receipt="OVERP1").exists())
		self.assertTrue(
			SuspiciousActivityLog.objects.filter(category="OVERPAYMENT_ATTEMPT", reference=f"loan:{loan.id}").exists()
		)

	@patch("loans.signals.send_payment_confirmation_sms.delay")
	@patch("loans.tasks.send_with_fallback", return_value=True)
	def test_due_soon_reminder_schedules_once_and_skips_paid_loans(self, _mock_notify, _mock_delay):
		due_soon_loan = self.create_loan(amount="1000.00", due_date=timezone.localdate() + timedelta(days=1))
		paid_loan = self.create_loan(amount="1000.00", due_date=timezone.localdate() + timedelta(days=1))

		Payment.objects.create(
			loan=paid_loan,
			amount=Decimal("1000.00"),
			mpesa_receipt="PAIDRCP1",
			phone=self.client_record.phone_number,
			raw_payload={},
		)
		paid_loan.refresh_from_db()
		self.assertEqual(paid_loan.status, Loan.Status.PAID)

		send_due_soon_reminders()
		send_due_soon_reminders()

		self.assertEqual(
			LoanReminderLog.objects.filter(
				loan=due_soon_loan,
				reminder_type=LoanReminderLog.ReminderType.DUE_SOON,
			).count(),
			1,
		)
		self.assertFalse(
			LoanReminderLog.objects.filter(
				loan=paid_loan,
				reminder_type=LoanReminderLog.ReminderType.DUE_SOON,
			).exists()
		)
