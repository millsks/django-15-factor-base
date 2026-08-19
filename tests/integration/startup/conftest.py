"""What the startup boot probes share: where the repository is, how long to wait, what to inherit.

Two modules in this package drive a fresh interpreter through `config.asgi` --
`test_stage_two_fires.py` proves the stage-2 hook fires on a served path, and
`test_stage_two_database_conditions.py` drives every stage-2 condition from a
process that has served one. Both need the same three facts, and they lived in
the first of those two modules until the second imported them from it.

That direction of import is what this file exists to remove. A collected test
module is not a helper library: importing one from another makes a collection
error in the first surface as an import error in the second, ties the two files'
collection order together, and hands the importer whatever fixtures and
module-scope state the imported file happens to carry. The same changeset that
introduced the cross-import also moved two URLconf builders into
`tests/conftest.py` for precisely the "shared helpers need a shared home"
reason; this is that answer applied consistently.

`tests/integration/conftest.py` is what marks everything beneath it as an
integration test, so nothing here re-applies the marker.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

#: The repository root, the working directory every boot probe is launched from.
#: Four parents up: `conftest.py` -> `startup` -> `integration` -> `tests`.
REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

#: Generous rather than tight: a cold Django start pays for app loading and four
#: OpenTelemetry instrumentors, and overshooting costs nothing when boot is quick.
BOOT_PROBE_TIMEOUT_SECONDS: Final[float] = 180.0


def subprocess_env() -> dict[str, str]:
    """Return an environment in which only the editable install can resolve `src/`.

    `PYTHONSAFEPATH` keeps the interpreter from prepending the working directory
    to `sys.path` for `-c`, and `PYTHONPATH` is dropped outright, so the child
    resolves `config` the way a deployed process does.

    `DJANGO_SETTINGS_MODULE` is dropped because it is the variable under test:
    pytest-django set it to `config.settings.test` in this process from the
    `--ds` in `addopts`, and a child that inherited it would never exercise the
    `os.environ.setdefault` in `config/asgi.py` that a server process relies on.

    `COMPONENT_RUNTIME` is inherited, so the child boots local exactly as a
    developer's `pixi run web` would -- which is why the sentinel is written
    before the locality check rather than after it. A probe that needs a deployed
    run drops the variable *after* boot rather than before it, so that the boot
    itself is still the one a developer performs.

    Returns:
        A copy of the current environment with those adjustments.

    """
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("DJANGO_SETTINGS_MODULE", None)
    # The database-selection variables are dropped for the same reason
    # `DJANGO_SETTINGS_MODULE` is: the probe supplies its own throwaway database
    # and must boot the same way whatever the developer's shell holds. Inherited,
    # a `DATABASE_URL` pointing at PostgreSQL makes `base.py` select the postgres
    # engine, and the probe's sqlite *filename* is then handed to it as a
    # database NAME -- which fails on PostgreSQL's 63-character limit rather than
    # on anything this test is about. The suite passed only on machines with no
    # database configured.
    for name in ("DATABASE_URL", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"):
        env.pop(name, None)
    env["PYTHONSAFEPATH"] = "1"
    return env
