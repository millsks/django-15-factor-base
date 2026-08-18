"""Stage 2 of the refusal contract: the checks that evaluate at process startup.

Invoked from the `AppConfig.ready()` of one named immovable-core app inside
`django_service` (AD-26). `ready()` runs inside `django.setup()`, so this fires
under gunicorn and uvicorn exactly as it does under a management command --
there is no serving-process-only hook to miss, and no `sys.argv` sniffing
anywhere (AD-13 forbids it outright).

`django_service` is `core` in its entirety (AD-29), so the owner travels in all
six combinations by construction and no adopted application can displace it. No
adopted application may precede it in `INSTALLED_APPS` either;
`tests/unit/startup/test_installed_apps_ordering.py` is the gate on that.

Whatever runs here runs at boot, so FR-23 and NFR-1 bind it: no network call,
and no query beyond migration state. `tests/unit/test_no_network_at_boot.py`
enforces the network half by booting this component with every socket refused.

**The sentinel is set first, before the locality check.** What AC #3 asserts is
that the invocation point fires at all under a serving process. Every developer
and CI path runs local (AD-13), so a record written after the `is_deployed()`
early return would never be observed and the test that reads it would assert
nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Final

from config.locality import is_deployed

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "STAGE_TWO_OWNER_APP_LABEL",
    "run_stage_two",
    "stage_two_has_run",
]

#: The app label of the immovable-core application that owns the stage-2
#: invocation. One declaration site (AD-1); Epic 7 adds a mirror of it in
#: `accelerator.toml` with a gate test asserting the two are equal, and
#: `src/config/startup/` stays the authoritative copy (AD-26).
STAGE_TWO_OWNER_APP_LABEL: Final[str] = "users"

#: Whether `run_stage_two()` has been entered in this interpreter.
#:
#: A mutable record rather than a rebound module global, because ruff `PLW0603`
#: forbids the `global` statement -- and read through `stage_two_has_run()`
#: rather than directly, because `SLF001` forbids the cross-module private read
#: and a direct `from ... import` would bind a copy of the boolean at import
#: time and never observe the later write.
_STAGE_TWO_RAN: Final[dict[str, bool]] = {"entered": False}

#: The stage-2 conditions, in evaluation order. Empty here: this story delivers
#: the frame and no condition. Story 4.3 appends to this tuple, and owns which
#: of its conditions additionally gate on `config.locality.is_serving_process()`
#: -- the migrations refusal is the one R-3 is about.
_STAGE_TWO: Final[tuple[Callable[[], None], ...]] = ()


def stage_two_has_run() -> bool:
    """Report whether `run_stage_two()` has been entered in this interpreter.

    The public reader for the boot sentinel. It says the invocation point fired,
    not that any condition evaluated: the record is written before the locality
    check, which is the only point at which a local process can observe it.

    Returns:
        True once `run_stage_two()` has been entered.

    """
    return _STAGE_TWO_RAN["entered"]


def run_stage_two() -> None:
    """Evaluate every stage-2 condition at serving-process startup.

    Raises:
        ImproperlyConfigured: When any condition finds a forbidden state. No
            condition exists yet; the type is fixed here so that CG-3's "never
            a warning, never a log-and-continue" holds from the first one.

    """
    _STAGE_TWO_RAN["entered"] = True

    if not is_deployed():
        return

    for condition in _STAGE_TWO:
        condition()
