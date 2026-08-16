from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Default custom user model for Django 15-Factor Application Accelerator.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    # The identity key (AD-11): unique, indexed, nullable, and the sole store.
    # `unique=True` already creates the index -- Django's schema editor emits an
    # explicit one only for `db_index and not unique` -- so no `db_index=True`.
    # Nullable because existing rows carry no key until their next
    # authentication; both PostgreSQL and SQLite allow repeated NULLs under a
    # UNIQUE constraint, which is what makes that work without a backfill.
    idp_subject = CharField(
        _("IdP subject"),
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        default=None,
    )
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"username": self.username})
