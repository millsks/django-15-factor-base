"""Both stages issue zero queries against a real connection (AC #7, NFR-1).

The counterpart to `tests/unit/startup/test_no_network_no_queries.py`, which
asserts the same claim through `connection.execute_wrapper` -- a recorder that
installs without opening a connection, and therefore holds in a unit test that
touches no database at all. This module makes the assertion the way NFR-1's
budget is actually measured: `django.test.utils.CaptureQueriesContext` against a
live connection, counting what the backend logged.

Both are kept. The unit form proves nothing reached the cursor and runs in
milliseconds with no database; this form proves the count is zero on a
connection that was genuinely opened, which is the form Story 4.3 will have to
amend when its migration-state read lands. `CaptureQueriesContext` cannot run as
a unit test -- its `__enter__` calls `ensure_connection()`, which pytest-django
blocks outside `django_db` -- so the split is where the database boundary is,
not a duplication of convenience.

**Zero, not "the migration-state read".** This story delivers no condition that
reads the database. Story 4.3's migration-state read and the designated-group
existence read each have to amend this number visibly rather than being absorbed
into a pre-widened allowance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

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

    Deployed rather than local, because every condition is deployed-only and the
    local path would return before reaching any of them -- leaving the count
    below a statement about code that never ran.

    **Valid means fully valid, not merely bare.** A bare `ModuleType` satisfied
    every condition stage 1 held when this module was written; against the six it
    holds now it refuses on the first one, before any query could have been
    issued, and the count below would be zero for the wrong reason. The builder
    is `tests/conftest.py`'s so that this module and its unit counterpart cannot
    disagree about what a valid deployed namespace is, and `OTEL_SDK_DISABLED` is
    deleted because condition 3 reads the environment rather than the namespace.

    Returns:
        A namespace no stage-1 condition objects to.

    """
    monkeypatch.delenv(RUNTIME_ENV_VAR, raising=False)
    monkeypatch.delenv(OTEL_SDK_DISABLED_ENV_VAR, raising=False)
    return valid_deployed_settings_namespace()


@pytest.mark.django_db
def test_neither_stage_issues_a_query(deployed_settings_namespace: ModuleType) -> None:
    """AC #7: no query beyond migration state, and there is no migration state read yet."""
    with CaptureQueriesContext(connection) as captured:
        run_stage_one(deployed_settings_namespace)
        run_stage_two()

    assert list(captured.captured_queries) == []
