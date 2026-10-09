"""FR-48: the deployed settings degrade on a cache outage *and* log it.

`tests/integration/test_cache_degradation.py` proves the mechanism against an
unreachable Redis; this module pins the three production values that switch it
on. All three together are the requirement: `IGNORE_EXCEPTIONS` alone is the
silent swallow the project standard forbids, and the logging flag without it
would turn a cache outage into an outage.

This module is `feature:redis`, as is its integration sibling. The values live in
`config/settings/production.py`'s `CACHES` block, which is the Redis feature's
region there; `tests/unit/test_settings.py` is `core` and would need region
markers to hold them.

`config.settings.production` is imported fresh, as a deployment loads it: the
locality variable deleted, the stage-1 roster supplied, every other `DJANGO_*`
and `COMPONENT_*` variable cleared so a developer's shell cannot change the
answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Final

import pytest

from config.locality import RUNTIME_ENV_VAR
from tests.settings_import import PRODUCTION_SETTINGS
from tests.settings_import import evicted_settings_modules
from tests.settings_import import import_settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

CACHE_LOGGER: Final[str] = "django_service.cache"
PARENT_LOGGER: Final[str] = "django_service"

#: What a deployed `production.py` import needs: the stage-1 roster plus the two
#: values the module reads directly. The same set
#: `tests/unit/test_payload_properties.py` declares; `.invalid` resolves nowhere.
DEPLOYED_ENVIRONMENT: Final[dict[str, str]] = {
    "DJANGO_SECRET_KEY": "x" * 50,
    "DJANGO_ADMIN_URL": "admin/",
    "DATABASE_URL": "postgres://user:pw@db:5432/app",
    "COMPONENT_OIDC_ISSUER": "https://idp.example.invalid/realms/component",
    "COMPONENT_IDENTITY_CLAIM": "sub",
    "COMPONENT_GROUP_CLAIM": "groups",
    "COMPONENT_STAFF_GROUP": "platform-staff",
    "COMPONENT_SUPERUSER_GROUP": "platform-superuser",
}


@pytest.fixture(autouse=True)
def _evict_settings_modules() -> Iterator[None]:
    """Drop freshly imported settings modules around each case, and restore structlog.

    Yields:
        Control to the test.

    """
    yield from evicted_settings_modules()


@pytest.fixture
def production(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Import `config.settings.production` fresh, deployed.

    Args:
        monkeypatch: The environment is set through it, so it is restored.

    Returns:
        The freshly imported module.

    """
    return import_settings(
        PRODUCTION_SETTINGS,
        monkeypatch,
        environment=DEPLOYED_ENVIRONMENT,
        runtime_variable=RUNTIME_ENV_VAR,
        runtime=None,
    )


def test_a_cache_outage_is_still_ignored(production: ModuleType) -> None:
    """AC #1: removing this would turn a cache outage into a component outage."""
    assert production.CACHES["default"]["BACKEND"] == "django_redis.cache.RedisCache"
    assert production.CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] is True


def test_every_ignored_failure_is_logged(production: ModuleType) -> None:
    """AC #2: without this flag django-redis returns the fallback and logs nothing."""
    assert production.DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS is True


def test_the_failure_is_logged_on_the_components_own_logger(production: ModuleType) -> None:
    """AC #2: a child of `django_service`, so it is levelled and correlated with it."""
    assert production.DJANGO_REDIS_LOGGER == CACHE_LOGGER


def test_the_parent_logger_is_declared_so_the_child_inherits_its_level(production: ModuleType) -> None:
    """`django_service.cache` needs no declaration of its own because its parent has one.

    The record still reaches the root `console` handler by propagation, so it is
    rendered by the same `structured` formatter -- and the same
    `foreign_pre_chain` -- as every other line.
    """
    loggers = production.LOGGING["loggers"]
    assert PARENT_LOGGER in loggers
    assert CACHE_LOGGER not in loggers
    assert loggers[PARENT_LOGGER].get("propagate", True) is True
    assert production.LOGGING["root"]["handlers"] == ["console"]
    assert production.LOGGING["handlers"]["console"]["formatter"] == "structured"
