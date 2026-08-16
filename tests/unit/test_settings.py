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
