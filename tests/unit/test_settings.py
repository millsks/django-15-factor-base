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
