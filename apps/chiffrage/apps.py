from django.apps import AppConfig


class ChiffrageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.chiffrage'
    verbose_name = 'Chiffrage'

    def ready(self):
        import apps.chiffrage.signals  # noqa
