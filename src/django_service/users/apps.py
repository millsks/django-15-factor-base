from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    name = "django_service.users"
    verbose_name = _("Users")

    def ready(self) -> None:
        """
        Override this method in subclasses to run code when Django starts.
        """
        # Empty. Whatever goes here runs inside `django.setup()`, which is boot,
        # so FR-23 and NFR-1 apply: no network call, and no query beyond
        # migration state. `tests/unit/test_no_network_at_boot.py` enforces the
        # network half, booting this component with every socket refused.
