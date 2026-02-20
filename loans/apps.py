from django.apps import AppConfig


class LoansConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loans'

    def ready(self):
        from . import schema  # noqa: F401
        from . import signals  # noqa: F401
