from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

    from django_service.users.models import User


# django-allauth ships no `py.typed` marker and no stub package exists for it on
# conda-forge, so `ignore_missing_imports` resolves every allauth name to `Any`
# and strict mode refuses the subclass. The base classes are real; only their
# types are missing upstream. `warn_unused_ignores` removes these the moment
# allauth starts publishing types.
class AccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        """Report whether self-service registration is permitted.

        Args:
            request: The request asking to sign up.

        Returns:
            The value of the ``ACCOUNT_ALLOW_REGISTRATION`` setting.

        """
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)


class SocialAccountAdapter(DefaultSocialAccountAdapter):  # type: ignore[misc]
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        """Report whether registration through a social provider is permitted.

        Args:
            request: The request asking to sign up.
            sociallogin: The provider login being completed.

        Returns:
            The value of the ``ACCOUNT_ALLOW_REGISTRATION`` setting.

        """
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populates user information from social provider info.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        # Declared, not inferred: the untyped allauth base returns `Any`, and
        # returning `Any` from a function annotated `-> User` is what
        # `warn_return_any` exists to catch.
        user: User = super().populate_user(request, sociallogin, data)
        if not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"
        return user
