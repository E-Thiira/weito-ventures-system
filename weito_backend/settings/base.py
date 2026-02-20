import os
from pathlib import Path

import dj_database_url
from celery.schedules import crontab
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY is required")

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "loans.apps.LoansConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "loans.middleware.AuditLogMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "weito_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "weito_backend.wsgi.application"
ASGI_APPLICATION = "weito_backend.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Weito Ventures API",
    "DESCRIPTION": "Microfinance backend APIs for loans, payments, reminders, and automation.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox").lower()
MPESA_BASE_URL = (
    "https://sandbox.safaricom.co.ke"
    if MPESA_ENVIRONMENT == "sandbox"
    else "https://api.safaricom.co.ke"
)
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "")
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE", "")
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "")
MPESA_CALLBACK_BASE_URL = os.getenv("MPESA_CALLBACK_BASE_URL", "http://127.0.0.1:8000")
MPESA_CALLBACK_TOKEN = os.getenv("MPESA_CALLBACK_TOKEN", "")
MPESA_WEBHOOK_SECRET = os.getenv("MPESA_WEBHOOK_SECRET", "")
MPESA_CALLBACK_ALLOWED_IPS = [
    ip.strip() for ip in os.getenv("MPESA_CALLBACK_ALLOWED_IPS", "").split(",") if ip.strip()
]

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "twilio")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
TWILIO_WHATSAPP_FROM_NUMBER = os.getenv("TWILIO_WHATSAPP_FROM_NUMBER", "")
ENABLE_WHATSAPP_REMINDERS = os.getenv("ENABLE_WHATSAPP_REMINDERS", "False").lower() == "true"

FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "")
DATA_HASH_SALT = os.getenv("DATA_HASH_SALT", SECRET_KEY)
SYSTEM_AUTOMATION_TOKEN = os.getenv("SYSTEM_AUTOMATION_TOKEN", "")
DB_BACKUP_DIR = os.getenv("DB_BACKUP_DIR", str(BASE_DIR / "backups"))

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "weito-backend-cache",
        "TIMEOUT": 300,
    }
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    "send-due-soon-reminders-daily": {
        "task": "loans.tasks.send_due_soon_reminders",
        "schedule": crontab(hour=8, minute=0),
    },
    "send-overdue-reminders-daily": {
        "task": "loans.tasks.send_overdue_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    "recompute-credit-scores-nightly": {
        "task": "loans.tasks.recompute_credit_scores_task",
        "schedule": crontab(hour=1, minute=0),
    },
    "daily-database-backup": {
        "task": "loans.tasks.run_daily_backup",
        "schedule": crontab(hour=2, minute=0),
    },
    "daily-reconciliation": {
        "task": "loans.tasks.reconcile_transactions",
        "schedule": crontab(hour=3, minute=0),
    },
    "retry-failed-notifications": {
        "task": "loans.tasks.retry_failed_notifications",
        "schedule": crontab(minute="*/30"),
    },
}
