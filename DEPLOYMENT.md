# Deployment Pipeline (Render / Railway Ready)

## Backend Web Process

- `gunicorn weito_backend.wsgi:application --log-file -`
- Procfile included for PaaS process detection.

## Required Environment Variables

- `DJANGO_ENV=production`
- `DJANGO_SECRET_KEY`
- `DATABASE_URL` (PostgreSQL URL)
- `CELERY_BROKER_URL` and optionally `CELERY_RESULT_BACKEND`
- M-Pesa, Twilio, and encryption secrets from `.env.example`

## Build Steps

1. `pip install -r requirements.txt`
2. `python manage.py migrate`
3. `python manage.py collectstatic --noinput`

## Static Files

- Served by WhiteNoise via Django (`CompressedManifestStaticFilesStorage`).

## PostgreSQL

- Enabled through `DATABASE_URL` using `dj-database-url` and `psycopg2-binary`.

## Celery Processes

- Worker: `celery -A weito_backend worker --loglevel=info`
- Beat: `celery -A weito_backend beat --loglevel=info`

`render.yaml` included with web + worker + beat process definitions.
