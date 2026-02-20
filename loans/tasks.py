import logging
from datetime import timedelta

from celery import shared_task
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import AuditLog, Loan, LoanReminderLog, NotificationLog, Payment
from .services.credit import recompute_client_credit
from .services.sms import send_with_fallback

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_payment_confirmation_sms(self, payment_id: int):
    try:
        payment = Payment.objects.select_related("loan", "loan__client").get(id=payment_id)
    except Payment.DoesNotExist:
        logger.warning("Payment %s not found for SMS confirmation", payment_id)
        return

    message = (
        f"Payment received: KES {payment.amount} for Loan #{payment.loan_id}. "
        f"Receipt: {payment.mpesa_receipt}."
    )
    sent = send_with_fallback(payment.phone, message)
    if not sent:
        raise RuntimeError(f"Payment confirmation failed for {payment.phone}")


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_due_soon_reminders(self):
    target_date = timezone.localdate() + timedelta(days=1)
    loans = Loan.objects.select_related("client").filter(
        status=Loan.Status.ACTIVE,
        due_date=target_date,
    )

    for loan in loans:
        loan.refresh_status(commit=True)
        if loan.status != Loan.Status.ACTIVE:
            continue

        try:
            with transaction.atomic():
                reminder, created = LoanReminderLog.objects.get_or_create(
                    loan=loan,
                    reminder_type=LoanReminderLog.ReminderType.DUE_SOON,
                )
            if not created:
                continue

            message = (
                f"Reminder: Loan #{loan.id} of KES {loan.amount} is due tomorrow "
                f"({loan.due_date}). Please pay to avoid penalties."
            )
            sent = send_with_fallback(loan.client.phone_number, message)
            if not sent:
                reminder.delete()
                raise RuntimeError(f"Due-soon reminder failed for loan {loan.id}")
        except IntegrityError:
            continue
        except Exception:
            logger.exception("Failed due-soon reminder for loan %s", loan.id)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_overdue_reminders(self):
    today = timezone.localdate()
    loans = Loan.objects.select_related("client").filter(due_date__lt=today).exclude(status=Loan.Status.PAID)

    for loan in loans:
        loan.refresh_status(commit=True)
        if loan.status != Loan.Status.OVERDUE:
            continue

        try:
            with transaction.atomic():
                reminder, created = LoanReminderLog.objects.get_or_create(
                    loan=loan,
                    reminder_type=LoanReminderLog.ReminderType.OVERDUE,
                )
            if not created:
                continue

            message = (
                f"Overdue alert: Loan #{loan.id} of KES {loan.amount} was due on "
                f"{loan.due_date}. Please clear payment immediately."
            )
            sent = send_with_fallback(loan.client.phone_number, message)
            if not sent:
                reminder.delete()
                raise RuntimeError(f"Overdue reminder failed for loan {loan.id}")
        except IntegrityError:
            continue
        except Exception:
            logger.exception("Failed overdue reminder for loan %s", loan.id)


@shared_task
def recompute_credit_scores_task():
    for loan in Loan.objects.select_related("client").all().only("client"):
        recompute_client_credit(loan.client)


@shared_task
def reconcile_transactions():
    for loan in Loan.objects.select_related("client").all():
        previous_status = loan.status
        loan.refresh_status(commit=True)
        if previous_status != loan.status:
            AuditLog.objects.create(
                actor="system",
                action="reconcile_status",
                endpoint="system/reconcile",
                method="SYSTEM",
                status_code=200,
                metadata={"loan_id": loan.id, "from": previous_status, "to": loan.status},
            )


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def retry_failed_notifications(self):
    failures = NotificationLog.objects.filter(success=False).order_by("created_at")[:50]
    for failure in failures:
        sent = send_with_fallback(failure.phone_number, failure.message)
        failure.attempts += 1
        failure.success = sent
        failure.error_message = "" if sent else failure.error_message
        failure.save(update_fields=["attempts", "success", "error_message"])


@shared_task
def run_daily_backup():
    call_command("backup_db")
