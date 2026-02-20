# Celery + Celery Beat Production Deployment

## Required Services

- Redis instance for broker/result backend
- Web process (Django/Gunicorn)
- Celery worker process
- Celery beat scheduler process

## Environment Variables

- `CELERY_BROKER_URL=redis://...`
- `CELERY_RESULT_BACKEND=redis://...`
- `DJANGO_ENV=production`
- `DJANGO_SECRET_KEY`, `DATABASE_URL`

## Auto-start Processes

- Procfile includes:
  - `worker: celery -A weito_backend worker --loglevel=info`
  - `beat: celery -A weito_backend beat --loglevel=info`
- `render.yaml` includes dedicated worker and beat services.

## Retry Logic Already Enabled

- Payment confirmations, reminder sends, and notification retries use Celery autoretry/backoff.
- Failed notifications are re-processed by scheduled task `retry_failed_notifications`.

## Scheduled Tasks

Configured in `CELERY_BEAT_SCHEDULE`:

- Due-soon reminders
- Overdue reminders
- Credit score recalculation
- Daily backups
- Reconciliation
- Retry failed notifications
