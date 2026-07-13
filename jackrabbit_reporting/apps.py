from django.apps import AppConfig


class JackrabbitReportingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "jackrabbit_reporting"
    verbose_name = "Jackrabbit reporting"

    def ready(self):
        from . import checks  # noqa: F401
