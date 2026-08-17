"""Tests for the settings modules themselves.

Each test imports a settings module fresh so its module-level environment
reads are re-evaluated. `config.settings.base` is evicted alongside the target
because the ``from .base import *`` in each module would otherwise reuse the
already-imported copy. Django's active settings are unaffected: they were
materialised at startup and hold no reference to these fresh module objects.
"""

from __future__ import annotations

import importlib
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

# AD-23's declared windows, in seconds, and the values the environment-driven
# case overrides them with. Named rather than written at the assertion so the
# numbers read as the policy they are.
DEFAULT_JWKS_TTL_SECONDS = 3600.0
DEFAULT_JWKS_MIN_REFETCH_SECONDS = 60.0
OVERRIDDEN_JWKS_TTL_SECONDS = 900.0
OVERRIDDEN_JWKS_MIN_REFETCH_SECONDS = 30.0

# The floors both windows are clamped to. A zero or negative refetch window makes
# `now - last_attempt < window` false for every caller, which disables the rate
# limit outright -- so the floor is enforced rather than documented as advice.
FLOOR_JWKS_TTL_SECONDS = 60.0
FLOOR_JWKS_MIN_REFETCH_SECONDS = 1.0

# Clock-skew tolerance ships at zero: the lever is added, the posture is not
# moved. Anything above zero accepts a token past its own `exp` by that much.
DEFAULT_OIDC_LEEWAY_SECONDS = 0.0
OVERRIDDEN_OIDC_LEEWAY_SECONDS = 5.0

BASE = "config.settings.base"
LOCAL = "config.settings.local"
PRODUCTION = "config.settings.production"


@pytest.fixture(autouse=True)
def _evict_settings_modules():
    """Drop freshly imported settings modules before and after each test."""
    for name in (BASE, LOCAL, PRODUCTION):
        sys.modules.pop(name, None)
    yield
    for name in (BASE, LOCAL, PRODUCTION):
        sys.modules.pop(name, None)


@pytest.fixture
def no_database_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)


@pytest.fixture
def no_claims_contract_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the four contract variables so the developer's shell cannot leak in."""
    for name in (
        "COMPONENT_IDENTITY_CLAIM",
        "COMPONENT_GROUP_CLAIM",
        "COMPONENT_STAFF_GROUP",
        "COMPONENT_SUPERUSER_GROUP",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def no_oidc_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the provider variables so the developer's shell cannot leak in."""
    for name in (
        "COMPONENT_OIDC_ISSUER",
        "COMPONENT_OIDC_CLIENT_ID",
        "COMPONENT_OIDC_CLIENT_SECRET",
        "COMPONENT_OIDC_PROVIDER_ID",
        "COMPONENT_OIDC_PROVIDER_NAME",
        "COMPONENT_OIDC_JWKS_URL",
        "COMPONENT_OIDC_AUDIENCE",
        "COMPONENT_OIDC_ALGORITHMS",
        "COMPONENT_JWKS_TTL_SECONDS",
        "COMPONENT_JWKS_MIN_REFETCH_SECONDS",
        "COMPONENT_OIDC_LEEWAY_SECONDS",
        "COMPONENT_SITE_DOMAIN",
        "COMPONENT_SITE_NAME",
        "DJANGO_ADMIN_FORCE_ALLAUTH",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 50)
    monkeypatch.setenv("DJANGO_ADMIN_URL", "admin/")


@pytest.mark.usefixtures("no_database_env")
def test_dot_env_file_is_read_when_enabled(monkeypatch: pytest.MonkeyPatch):
    """DJANGO_READ_DOT_ENV_FILE toggles the .env read in base.py."""
    monkeypatch.setenv("DJANGO_READ_DOT_ENV_FILE", "True")
    base = importlib.import_module(BASE)
    assert base.READ_DOT_ENV_FILE is True


@pytest.mark.usefixtures("no_database_env")
def test_debug_apps_are_off_by_default(monkeypatch: pytest.MonkeyPatch):
    """The runtime environment lacks debug_toolbar, so local must not require it."""
    monkeypatch.delenv("DJANGO_DEBUG_APPS", raising=False)
    local = importlib.import_module(LOCAL)
    assert local.DEBUG_APPS is False
    assert "debug_toolbar" not in local.INSTALLED_APPS
    assert "django_extensions" not in local.INSTALLED_APPS
    assert not any("debug_toolbar" in mw for mw in local.MIDDLEWARE)


@pytest.mark.usefixtures("no_database_env")
def test_debug_apps_can_be_enabled(monkeypatch: pytest.MonkeyPatch):
    """The dev environment sets DJANGO_DEBUG_APPS, which wires the toolbar in."""
    monkeypatch.setenv("DJANGO_DEBUG_APPS", "True")
    local = importlib.import_module(LOCAL)
    assert local.DEBUG_APPS is True
    assert "debug_toolbar" in local.INSTALLED_APPS
    assert "django_extensions" in local.INSTALLED_APPS
    assert any("debug_toolbar" in mw for mw in local.MIDDLEWARE)


@pytest.mark.usefixtures("no_database_env")
def test_local_falls_back_to_sqlite():
    local = importlib.import_module(LOCAL)
    assert local.DATABASES["default"]["ENGINE"].endswith("sqlite3")
    assert local.DEBUG is True


def test_postgres_env_selects_postgres(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_DB", "app")
    monkeypatch.setenv("POSTGRES_USER", "app")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    base = importlib.import_module(BASE)
    assert base.DATABASES["default"]["ENGINE"].endswith("postgresql")
    assert base.DATABASES["default"]["NAME"] == "app"


@pytest.mark.usefixtures("no_database_env", "no_claims_contract_env")
def test_base_imports_cleanly_with_an_unconfigured_contract():
    """Importing base with no COMPONENT_ variables set must not raise.

    The refusal to start on an unusable claims contract is Epic 4's, gated on a
    locality signal that does not exist yet. A raise here would fire during the
    test suite and during every management command. What base owes today is an
    unconfigured contract that reports itself as one, with nothing defaulted.
    """
    base = importlib.import_module(BASE)
    contract = base.CLAIMS_CONTRACT
    assert contract.is_configured is False
    assert contract.identity_key_claim == ""
    assert contract.group_claim == ""
    assert contract.staff_group == ""
    assert contract.superuser_group == ""


@pytest.mark.usefixtures("no_database_env")
def test_base_reads_a_configured_contract_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    """The four variables reach `settings.CLAIMS_CONTRACT`, not just the loader.

    Without this the settings line could be replaced by a hardcoded empty
    contract and nothing would fail: every deployment silently unconfigured.
    """
    monkeypatch.setenv("COMPONENT_IDENTITY_CLAIM", "oid")
    monkeypatch.setenv("COMPONENT_GROUP_CLAIM", "realm_access.roles")
    monkeypatch.setenv("COMPONENT_STAFF_GROUP", "ops-staff")
    monkeypatch.setenv("COMPONENT_SUPERUSER_GROUP", "ops-admin")

    base = importlib.import_module(BASE)
    contract = base.CLAIMS_CONTRACT

    assert contract.identity_key_claim == "oid"
    assert contract.group_claim == "realm_access.roles"
    assert contract.staff_group == "ops-staff"
    assert contract.superuser_group == "ops-admin"
    assert contract.is_configured is True


def _oidc_app(base: object) -> dict[str, object]:
    """Return the single provider app `SOCIALACCOUNT_PROVIDERS` declares."""
    apps = base.SOCIALACCOUNT_PROVIDERS["openid_connect"]["APPS"]  # type: ignore[attr-defined]
    assert len(apps) == 1, "one provider app: a second is what makes allauth's get_app ambiguous"
    return apps[0]  # type: ignore[no-any-return]


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_oidc_provider_ships_with_the_installed_allauth():
    """AC #2: allauth's own provider, and no second OIDC framework beside it."""
    base = importlib.import_module(BASE)

    assert "allauth.socialaccount.providers.openid_connect" in base.INSTALLED_APPS
    # The entry sits with allauth's own apps rather than being appended to the
    # end, and it is never guarded (AD-24): no conditional import, no
    # settings-module inheritance, no try/except ImportError.
    assert base.INSTALLED_APPS.index("allauth.socialaccount.providers.openid_connect") == (
        base.INSTALLED_APPS.index("allauth.socialaccount") + 1
    )


@pytest.mark.usefixtures("no_database_env")
def test_the_provider_is_configured_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    """AC #4: from `SOCIALACCOUNT_PROVIDERS`, populated from the environment."""
    monkeypatch.setenv("COMPONENT_OIDC_ISSUER", "https://idp.example.test/realms/component")
    monkeypatch.setenv("COMPONENT_OIDC_CLIENT_ID", "component-web")
    monkeypatch.setenv("COMPONENT_OIDC_CLIENT_SECRET", "s3cret")
    monkeypatch.setenv("COMPONENT_OIDC_PROVIDER_ID", "realm")
    monkeypatch.setenv("COMPONENT_OIDC_PROVIDER_NAME", "Component Realm")

    app = _oidc_app(importlib.import_module(BASE))

    assert app["settings"]["server_url"] == "https://idp.example.test/realms/component"  # type: ignore[index]
    assert app["client_id"] == "component-web"
    assert app["secret"] == "s3cret"  # noqa: S105 - a test fixture, not a credential
    assert app["provider_id"] == "realm"
    assert app["name"] == "Component Realm"


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_provider_reads_but_never_defaults_the_issuer():
    """An unconfigured IdP imports cleanly; refusing it is Epic 4's stage 1, not this module's."""
    app = _oidc_app(importlib.import_module(BASE))

    assert app["settings"]["server_url"] == ""  # type: ignore[index]
    assert app["client_id"] == ""


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_pkce_is_enabled_on_the_provider():
    """FR-4 specifies Authorization Code with PKCE; allauth's default without this key is off."""
    app = _oidc_app(importlib.import_module(BASE))

    assert app["settings"]["oauth_pkce_enabled"] is True  # type: ignore[index]


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_email_is_never_an_authentication_key():
    """AD-11: `idp_subject` is the sole identity key, so a matching address may not sign anyone in."""
    base = importlib.import_module(BASE)

    assert base.SOCIALACCOUNT_EMAIL_AUTHENTICATION is False


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_social_adapter_is_the_one_that_calls_the_mapper():
    base = importlib.import_module(BASE)

    assert base.SOCIALACCOUNT_ADAPTER == "config.authorization.adapters.OIDCSocialAccountAdapter"


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_login_url_is_the_provider_route_rather_than_the_local_form():
    """AC #1: an unauthenticated request lands on the IdP redirect, never on allauth's form."""
    base = importlib.import_module(BASE)

    login_url = str(base.LOGIN_URL)

    assert login_url.endswith("/oidc/oidc/login/")
    assert login_url != "/accounts/login/"


@pytest.mark.usefixtures("no_database_env")
def test_the_login_url_follows_the_configured_provider_id(monkeypatch: pytest.MonkeyPatch):
    """One variable, one meaning: the route and the provider app read the same name."""
    monkeypatch.setenv("COMPONENT_OIDC_PROVIDER_ID", "realm")

    base = importlib.import_module(BASE)

    assert str(base.LOGIN_URL).endswith("/realm/login/")
    assert _oidc_app(base)["provider_id"] == "realm"


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_admin_is_forced_through_allauth_by_default():
    """FR-7 / AC #6: true with the variable unset. It shipped false, which was the defect."""
    base = importlib.import_module(BASE)

    assert base.DJANGO_ADMIN_FORCE_ALLAUTH is True


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_site_domain_defaults_to_localhost_rather_than_a_repository_domain():
    base = importlib.import_module(BASE)

    assert base.SITE_DOMAIN == "localhost"
    assert base.SITE_NAME == "localhost"


@pytest.mark.usefixtures("no_database_env")
def test_the_site_domain_is_environment_driven(monkeypatch: pytest.MonkeyPatch):
    """AC #5: the domain comes from the environment, never from a data migration."""
    monkeypatch.setenv("COMPONENT_SITE_DOMAIN", "component.example.test")
    monkeypatch.setenv("COMPONENT_SITE_NAME", "Component")

    base = importlib.import_module(BASE)

    assert base.SITE_DOMAIN == "component.example.test"
    assert base.SITE_NAME == "Component"


@pytest.mark.usefixtures("no_database_env", "production_env")
def test_production_refuses_sqlite():
    with pytest.raises(ImproperlyConfigured, match="requires a real database"):
        importlib.import_module(PRODUCTION)


@pytest.mark.usefixtures("production_env")
def test_production_accepts_a_real_database(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pw@db:5432/app")
    production = importlib.import_module(PRODUCTION)
    assert production.DATABASES["default"]["ENGINE"].endswith("postgresql")
    assert production.DEBUG is False


# ---------------------------------------------------------------------------
# Story 2.7 -- the Bearer credential's wiring and its configuration.
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_bearer_class_is_asked_before_the_session():
    """AC #1 / Task 4: a request carrying both credentials is decided by the Bearer one.

    Order is the assertion, not membership. The class returns None rather than
    raising when no Bearer header is present, so placing it first costs a
    session-authenticated request nothing -- while placing it *after*
    `SessionAuthentication` would mean a stale session cookie decided a request
    that presented a fresh token.
    """
    base = importlib.import_module(BASE)

    classes = list(base.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"])

    assert classes[0] == "config.authorization.authentication.OIDCBearerAuthentication"
    assert classes.index("rest_framework.authentication.SessionAuthentication") > 0


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_old_token_credential_is_still_installed():
    """Removing `TokenAuthentication` is Story 2.8's, deliberately after this one.

    The readiness assessment records the ordering as load-bearing: 2.6 and 2.7
    precede 2.8 so the replacement credential paths exist before the old ones
    are deleted.
    """
    base = importlib.import_module(BASE)

    assert "rest_framework.authentication.TokenAuthentication" in base.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_rest_framework_block_keeps_everything_else_it_declared():
    """The permission default and the schema class are not this story's to move."""
    base = importlib.import_module(BASE)

    assert base.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == ("rest_framework.permissions.IsAuthenticated",)
    assert base.REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] == "drf_spectacular.openapi.AutoSchema"
    assert base.CORS_URLS_REGEX == r"^/api/.*$"


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_bearer_configuration_defaults_are_the_declared_ones():
    """AD-23's windows, and an algorithm allowlist that never comes from the token."""
    base = importlib.import_module(BASE)

    assert base.OIDC_ALGORITHMS == ["RS256"]
    assert base.JWKS_TTL_SECONDS == DEFAULT_JWKS_TTL_SECONDS
    assert base.JWKS_MIN_REFETCH_SECONDS == DEFAULT_JWKS_MIN_REFETCH_SECONDS
    # The clock-skew lever ships pulled all the way back. A default above zero
    # would be a change to the verification posture wearing a setting's clothes.
    assert base.OIDC_LEEWAY_SECONDS == DEFAULT_OIDC_LEEWAY_SECONDS
    # Unset means unconfigured, which refuses every token. It is never defaulted
    # to a conventional issuer or to "any audience".
    assert base.OIDC_ISSUER == ""
    assert base.OIDC_AUDIENCE == ""
    assert base.OIDC_JWKS_URL == ""


@pytest.mark.usefixtures("no_database_env")
def test_there_is_one_issuer_variable_and_both_consumers_read_it(monkeypatch: pytest.MonkeyPatch):
    """AD-23: the trust anchor is single, so the provider and the Bearer path read one name."""
    monkeypatch.setenv("COMPONENT_OIDC_ISSUER", "https://idp.example.test/realms/component")

    base = importlib.import_module(BASE)

    assert base.OIDC_ISSUER == "https://idp.example.test/realms/component"
    assert _oidc_app(base)["settings"]["server_url"] == base.OIDC_ISSUER  # type: ignore[index]


@pytest.mark.usefixtures("no_database_env")
def test_the_audience_falls_back_to_the_client_id(monkeypatch: pytest.MonkeyPatch):
    """An IdP issuing tokens for this component's own client puts the client id in `aud`."""
    monkeypatch.delenv("COMPONENT_OIDC_AUDIENCE", raising=False)
    monkeypatch.setenv("COMPONENT_OIDC_CLIENT_ID", "component-web")

    base = importlib.import_module(BASE)

    assert base.OIDC_AUDIENCE == "component-web"


@pytest.mark.usefixtures("no_database_env")
def test_an_explicit_audience_wins_over_the_client_id(monkeypatch: pytest.MonkeyPatch):
    """A deployment whose IdP names a separate resource server sets the variable."""
    monkeypatch.setenv("COMPONENT_OIDC_CLIENT_ID", "component-web")
    monkeypatch.setenv("COMPONENT_OIDC_AUDIENCE", "component-api")

    base = importlib.import_module(BASE)

    assert base.OIDC_AUDIENCE == "component-api"


@pytest.mark.usefixtures("no_database_env")
def test_the_jwks_windows_are_environment_driven(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COMPONENT_JWKS_TTL_SECONDS", "900")
    monkeypatch.setenv("COMPONENT_JWKS_MIN_REFETCH_SECONDS", "30")
    monkeypatch.setenv("COMPONENT_OIDC_ALGORITHMS", "RS256,ES256")

    base = importlib.import_module(BASE)

    assert base.JWKS_TTL_SECONDS == OVERRIDDEN_JWKS_TTL_SECONDS
    assert base.JWKS_MIN_REFETCH_SECONDS == OVERRIDDEN_JWKS_MIN_REFETCH_SECONDS
    assert base.OIDC_ALGORITHMS == ["RS256", "ES256"]


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
@pytest.mark.parametrize("configured", ["0", "-1", "-3600"])
def test_a_zero_or_negative_refetch_window_is_clamped_rather_than_honoured(
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
):
    """A window at or below zero disables the rate limit outright.

    `now - last_attempt < window` is false for every caller once the window is
    zero or negative, so each unmatched `kid` produces an outbound fetch -- which
    is precisely the amplification against the IdP's JWKS endpoint that AD-23
    built this module to prevent, re-armed by one environment variable. It is
    clamped rather than refused at startup because a running component with a
    slightly-too-short window is strictly better than one that will not boot,
    and clamped rather than trusted because the value arrives from a deployment
    environment nobody reviews line by line.
    """
    monkeypatch.setenv("COMPONENT_JWKS_MIN_REFETCH_SECONDS", configured)

    base = importlib.import_module(BASE)

    assert base.JWKS_MIN_REFETCH_SECONDS == FLOOR_JWKS_MIN_REFETCH_SECONDS


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
@pytest.mark.parametrize("configured", ["0", "-1"])
def test_a_zero_or_negative_cache_lifetime_is_clamped_rather_than_honoured(
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
):
    """At or below zero every lookup sees the cache as expired, so nothing is ever cached."""
    monkeypatch.setenv("COMPONENT_JWKS_TTL_SECONDS", configured)

    base = importlib.import_module(BASE)

    assert base.JWKS_TTL_SECONDS == FLOOR_JWKS_TTL_SECONDS


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_the_clock_skew_tolerance_is_environment_driven(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COMPONENT_OIDC_LEEWAY_SECONDS", "5")

    base = importlib.import_module(BASE)

    assert base.OIDC_LEEWAY_SECONDS == OVERRIDDEN_OIDC_LEEWAY_SECONDS


@pytest.mark.usefixtures("no_database_env", "no_oidc_env")
def test_a_negative_clock_skew_tolerance_is_clamped_to_zero(monkeypatch: pytest.MonkeyPatch):
    """PyJWT takes `leeway` as a magnitude, so a negative value is a nonsense the reader owns."""
    monkeypatch.setenv("COMPONENT_OIDC_LEEWAY_SECONDS", "-30")

    base = importlib.import_module(BASE)

    assert base.OIDC_LEEWAY_SECONDS == DEFAULT_OIDC_LEEWAY_SECONDS
