web: gunicorn weito_backend.wsgi:application --log-file -
worker: celery -A weito_backend worker --loglevel=info
beat: celery -A weito_backend beat --loglevel=info
