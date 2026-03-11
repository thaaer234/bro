from django.apps import AppConfig


class MobileConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mobile"

    def ready(self):
        # Register model signals so notifications are created on save events.
        import mobile.signals  # noqa: F401
