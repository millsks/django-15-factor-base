"""Neither stage reaches the network or the database (AC #7, NFR-1).

NFR-1: "the nine checks are settings and URL-configuration inspection with no
network call and no query beyond the migration state, so their cost is
irrelevant to startup time." Both stages run at boot -- stage 1 while the
settings module is still executing, stage 2 inside `django.setup()` -- so a
condition that resolved a JWKS document or counted rows would put a network
round trip and a query on the critical path of every process this component
starts, including `pixi run migrate`.

**No wall-clock assertion.** NFR-1's own `[ASSUMPTION]` records that no platform
startup-time budget exists, so there is no threshold to assert against. The cost
is bounded by asserting the two things that could make it unbounded.

**Zero queries, not "the migration-state read".** This story delivers no
condition that reads the database. The migration-state read arrives with Story
4.3 and the designated-group existence read with it, and each will have to amend
this assertion as it lands. Asserting zero now is what makes those two additions
visible in a diff instead of absorbed into a pre-widened allowance.

The query half is asserted with `connection.execute_wrapper`, which installs a
recorder without opening a connection -- so this stays a unit test, touching no
database at all, and the assertion is the stronger one: not merely that no query
was counted, but that nothing even reached the cursor.
`tests/integration/startup/test_no_queries.py` makes the same claim through
`django.test.utils.CaptureQueriesContext` against a real connection.

The network half reuses the delivered `no_network` fixture rather than patching
`socket.socket` by hand: that guard already covers `connect`, `connect_ex`,
`create_connection`, `getaddrinfo` and `gethostbyname`, and raises a
`BaseException` subclass so a stray `except Exception:` inside a condition
cannot swallow the refusal and report a clean run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.db import connection

from config.locality import RUNTIME_ENV_VAR
from config.observability.telemetry import OTEL_SDK_DISABLED_ENV_VAR
from config.startup import run_stage_one
from config.startup import run_stage_two
from tests.conftest import valid_deployed_settings_namespace

if TYPE_CHECKING:
    from types import ModuleType


@pytest.fixture
def deployed_settings_namespace(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """A valid deployed configuration: deployed locality, deployed settings module.

    Deployed rather than local on purpose -- every condition is deployed-only,
    so the local path would return before reaching any of them and the
    assertions below would hold over code that never ran.

    **Valid means fully valid, not merely bare.** A bare `ModuleType` was enough
    while stage 1 held one condition; it is not enough now. Every one of the six
    would refuse it -- no `DATABASES`, no claims contract, no issuer -- and each
    refusal would be raised *before* the socket or the cursor could be reached,
    so both assertions below would pass over conditions that never ran. The
    namespace is built by `tests/conftest.py`, which
    `tests/integration/startup/test_no_queries.py` shares, and
    `OTEL_SDK_DISABLED` is deleted here because condition 3 reads the
    environment rather than the namespace.

    Returns:
        A namespace no stage-1 condition objects to.

    """
    monkeypatch.delenv(RUNTIME_ENV_VAR, raising=False)
    monkeypatch.delenv(OTEL_SDK_DISABLED_ENV_VAR, raising=False)
    return valid_deployed_settings_namespace()


def test_neither_stage_opens_a_socket(
    no_network: None,
    deployed_settings_namespace: ModuleType,
) -> None:
    """AC #7, first half: no network call, with every chokepoint refusing."""
    run_stage_one(deployed_settings_namespace)
    run_stage_two()


def test_neither_stage_reaches_the_database_cursor(
    deployed_settings_namespace: ModuleType,
) -> None:
    """AC #7, second half: zero queries, and no connection attempted either.

    `execute_wrapper` records at the cursor rather than at the connection, so a
    condition that opened a connection and issued nothing would still pass this
    -- which is why the integration counterpart asserts the count against a real
    connection as well.
    """
    executed: list[str] = []

    # Django fixes this signature, `many` included -- which is why it carries no
    # annotations here: writing `many: bool` would trip ruff `FBT001` on a
    # parameter list this file does not own.
    def _record(execute, sql, params, many, context):
        executed.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(_record):
        run_stage_one(deployed_settings_namespace)
        run_stage_two()

    assert executed == []
