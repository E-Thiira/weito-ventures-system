import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'weito_backend.settings')

app = Celery('weito_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
