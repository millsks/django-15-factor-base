"""Stage 1 of the refusal contract: the checks that evaluate at settings import.

Called as the last statement of every leaf settings module, with that module's
own namespace as its argument. The namespace is passed rather than read off
`django.conf.settings` because `django.conf.settings` is not yet populated while
a settings module is still executing -- the module object is the only place the
composed values exist at that moment. Conditions read candidate names off it
with `getattr(module, name, default)`.

Every condition is deployed-only, so the whole stage returns before any of them
runs when `is_deployed()` is false. That is what keeps the entire developer and
CI surface -- all of which run local (AD-13) -- from refusing the moment this
contract lands.

A condition raises `django.core.exceptions.ImproperlyConfigured` and nothing
else. Never `warnings.warn`, never a log-and-continue branch: CG-3 exists
because a refusal softened into a warning makes deployment smoother and puts
local credentials into production.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Final

from django.core.exceptions import ImproperlyConfigured

from config.locality import LOCAL
from config.locality import RUNTIME_ENV_VAR
from config.locality import is_deployed

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

__all__ = [
    "LOCAL_SETTINGS_MODULE",
    "PRODUCTION_SETTINGS_MODULE",
    "run_stage_one",
]

#: The settings module a deployed process must never load, and the one it should
#: load instead. Spelled once each, because both appear in the refusal message
#: and in the condition that raises it.
LOCAL_SETTINGS_MODULE: Final[str] = "config.settings.local"
PRODUCTION_SETTINGS_MODULE: Final[str] = "config.settings.production"

#: The variable Django reads the settings module from. Named here only to write
#: the resolution into the message; the condition below never reads it, because
#: a process can set it to one value and import another.
SETTINGS_MODULE_ENV_VAR: Final[str] = "DJANGO_SETTINGS_MODULE"


def _refuse_the_local_settings_module(settings_module: ModuleType) -> None:
    """Refuse a deployed process that loaded the local settings module (FR-12).

    The escape route this whole contract is built around: a deployed component
    whose `DJANGO_SETTINGS_MODULE` points at `config.settings.local` gets the
    development secret key, `DEBUG=True`, the console email backend and the
    locally minted signing keypair -- and nothing inside `local.py` could
    object, because `local.py` is the thing that would have to object.

    The module's own `__name__` is what is compared, taken from the object that
    is actually executing. `os.environ["DJANGO_SETTINGS_MODULE"]` is not read:
    a process can set that variable to one module and import another, and the
    module that ran is the one whose values are live.

    Args:
        settings_module: The settings module currently being composed.

    Raises:
        ImproperlyConfigured: When a deployed process loaded `local.py`. The
            message states both resolutions, because the right one depends on
            which half is wrong and the reader is the only one who knows.

    """
    if settings_module.__name__ != LOCAL_SETTINGS_MODULE:
        return

    message = (
        f"{LOCAL_SETTINGS_MODULE} was loaded by a deployed component. "
        f"Set {RUNTIME_ENV_VAR}={LOCAL} if this is local development, "
        f"or point {SETTINGS_MODULE_ENV_VAR} at {PRODUCTION_SETTINGS_MODULE} if it is a deployment."
    )
    raise ImproperlyConfigured(message)


#: The stage-1 conditions, in evaluation order. Stories 4.2 and 4.4 append to
#: this tuple rather than adding a call into `run_stage_one`, so that the
#: dispatch has one shape and the roster has one declaration site (AD-1).
_STAGE_ONE: Final[tuple[Callable[[ModuleType], None], ...]] = (_refuse_the_local_settings_module,)


def run_stage_one(settings_module: ModuleType, /) -> None:
    """Evaluate every stage-1 condition against a settings module being composed.

    Called as `run_stage_one(sys.modules[__name__])`, as the last statement of
    every leaf settings module. The parameter is required and positional-only
    on purpose: every call site passes it, so a default would only ever mask a
    call site that forgot, and a keyword catch-all would silently absorb a
    future condition's misrouted argument instead of failing on it.

    Args:
        settings_module: The module whose namespace the conditions inspect.

    Raises:
        ImproperlyConfigured: When any condition finds a forbidden state.

    """
    if not is_deployed():
        return

    for condition in _STAGE_ONE:
        condition(settings_module)
