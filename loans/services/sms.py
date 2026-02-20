import logging

from django.conf import settings
from twilio.rest import Client as TwilioClient

from loans.models import NotificationLog

logger = logging.getLogger(__name__)


def _twilio_client():
    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN]):
        return None
    return TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_sms(phone_number: str, message: str) -> bool:
    provider = settings.SMS_PROVIDER.lower()
    if provider != "twilio":
        logger.warning("Unsupported SMS provider '%s'; SMS skipped for %s", provider, phone_number)
        NotificationLog.objects.create(
            phone_number=phone_number,
            channel=NotificationLog.Channel.SMS,
            message=message,
            success=False,
            error_message=f"Unsupported provider: {provider}",
        )
        return False

    twilio_client = _twilio_client()
    if not twilio_client or not settings.TWILIO_FROM_NUMBER:
        NotificationLog.objects.create(
            phone_number=phone_number,
            channel=NotificationLog.Channel.SMS,
            message=message,
            success=False,
            error_message="Twilio SMS config missing",
        )
        return False

    try:
        twilio_client.messages.create(body=message, from_=settings.TWILIO_FROM_NUMBER, to=phone_number)
        NotificationLog.objects.create(
            phone_number=phone_number,
            channel=NotificationLog.Channel.SMS,
            message=message,
            success=True,
        )
        return True
    except Exception as exc:
        NotificationLog.objects.create(
            phone_number=phone_number,
            channel=NotificationLog.Channel.SMS,
            message=message,
            success=False,
            error_message=str(exc),
        )
        return False


def send_whatsapp(phone_number: str, message: str) -> bool:
    if not settings.ENABLE_WHATSAPP_REMINDERS:
        return False

    twilio_client = _twilio_client()
    if not twilio_client or not settings.TWILIO_WHATSAPP_FROM_NUMBER:
        return False

    try:
        twilio_client.messages.create(
            body=message,
            from_=settings.TWILIO_WHATSAPP_FROM_NUMBER,
            to=f"whatsapp:{phone_number}",
        )
        NotificationLog.objects.create(
            phone_number=phone_number,
            channel=NotificationLog.Channel.WHATSAPP,
            message=message,
            success=True,
        )
        return True
    except Exception as exc:
        NotificationLog.objects.create(
            phone_number=phone_number,
            channel=NotificationLog.Channel.WHATSAPP,
            message=message,
            success=False,
            error_message=str(exc),
        )
        return False


def send_with_fallback(phone_number: str, message: str) -> bool:
    if send_whatsapp(phone_number, message):
        return True
    return send_sms(phone_number, message)
