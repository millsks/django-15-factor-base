"""Tests for the allauth account adapters.

These exercise adapter behaviour against unsaved User instances, so they need
no database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pytest
from allauth.socialaccount.models import SocialLogin
from django.test import RequestFactory

from django_service.users.adapters import AccountAdapter
from django_service.users.adapters import SocialAccountAdapter
from django_service.users.models import User

if TYPE_CHECKING:
    from django.http import HttpRequest


@pytest.fixture
def http_request() -> HttpRequest:
    return RequestFactory().get("/")


class TestAccountAdapter:
    def test_open_for_signup_by_default(self, http_request: HttpRequest):
        assert AccountAdapter().is_open_for_signup(http_request) is True

    def test_registration_can_be_disabled(self, settings, http_request: HttpRequest):
        settings.ACCOUNT_ALLOW_REGISTRATION = False
        assert AccountAdapter().is_open_for_signup(http_request) is False


class TestSocialAccountAdapter:
    def test_open_for_signup_by_default(self, http_request: HttpRequest):
        sociallogin = SocialLogin(user=User())
        adapter = SocialAccountAdapter()
        assert adapter.is_open_for_signup(http_request, sociallogin) is True

    def test_registration_can_be_disabled(self, settings, http_request: HttpRequest):
        settings.ACCOUNT_ALLOW_REGISTRATION = False
        sociallogin = SocialLogin(user=User())
        adapter = SocialAccountAdapter()
        assert adapter.is_open_for_signup(http_request, sociallogin) is False

    @pytest.mark.parametrize(
        ("data", "expected_name"),
        [
            ({"name": "Ada Lovelace"}, "Ada Lovelace"),
            ({"first_name": "Ada"}, "Ada"),
            ({"first_name": "Ada", "last_name": "Lovelace"}, "Ada Lovelace"),
            ({}, ""),
        ],
    )
    def test_populate_user_derives_name(
        self,
        http_request: HttpRequest,
        data: dict[str, Any],
        expected_name: str,
    ):
        sociallogin = SocialLogin(user=User())
        user = SocialAccountAdapter().populate_user(http_request, sociallogin, data)
        assert user.name == expected_name

    def test_populate_user_keeps_existing_name(self, http_request: HttpRequest):
        sociallogin = SocialLogin(user=User(name="Grace Hopper"))
        user = SocialAccountAdapter().populate_user(
            http_request,
            sociallogin,
            {"name": "Ada Lovelace"},
        )
        assert user.name == "Grace Hopper"
