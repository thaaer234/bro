from django.apps import AppConfig


class EmployConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'employ'

    def ready(self):
        from .scheduler import start_biometric_scheduler
        start_biometric_scheduler()
