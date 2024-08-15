from django.apps import AppConfig


class Rdf4JConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rdf4j"

    def ready(self) -> None:
        # register the signal handlers
        import rdf4j.signals.handlers  # pylint: disable=unused-import, import-outside-toplevel
