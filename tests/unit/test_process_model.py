"""Tests for the process model AD-14 declares across `pixi.toml` and `component.toml`.

The process model is two halves of one fact held in two files. `pixi.toml` says
how each process type is *run* -- `web`, `worker` and `beat` are pixi tasks, so
the deployment repository invokes `pixi run <process>` and enumerates the set
with `pixi task list`, and there is no Procfile. `component.toml` says what each
process type *needs* -- replica counts and replacement strategy, which no task
can express and no deployment repository can infer.

The halves drift silently, which is why the gate on them is **two-way**: every
process type the declaration names has a matching task, *and* every task in the
process group is named by the declaration. One direction alone is not enough.
A declaration naming a task nobody wrote gives the deployment repository a
process it cannot start; a `worker` task surviving into a component with no
Celery gives it a process it should never have started, which is the failure
AD-14 names.

Membership in the process group is **structural, not nominal** (AD-26): the group
is exactly the set of tasks whose `env` declares `COMPONENT_PROCESS`. Deriving it
from a name, a prefix or a comment is the failure mode AD-26 names for
predicates, and it applies here for the same reason -- a task called `web-2` is
in the group if it declares the variable and out of it if it does not, whatever
its name suggests.

Two neighbouring facts are asserted elsewhere and deliberately not repeated here:

* `tests/unit/test_locality_declaration.py::test_only_serving_process_tasks_declare_a_process_type`
  and `::test_serving_process_tasks_declare_no_runtime` own the other half of
  AD-13's task-`env` contract. Both were written to pass vacuously until this
  story landed the tasks; they go live with it rather than being duplicated here.
* `::test_component_process_absent_from_every_activation_env` owns the absolute
  prohibition on `COMPONENT_PROCESS` in an activation env. Why that one is fatal
  is worth restating even where it is not asserted: the golden base runs pixi, so
  an activation env reaches production, and `COMPONENT_PROCESS` placed in one
  would make *every* management command declare itself a serving process --
  `pixi run migrate` included, a release-stage step, which then refuses on the
  unapplied-migrations condition and deadlocks the release.

Two variances are recorded rather than worked around. The six-combination
`[environments]` matrix does not exist yet (Epic 8, Story 8.1), so AC #4's "any
of the six combinations" and AC #5's "a combination without background task
processing" are asserted here *structurally* -- `web` outside any region,
`worker` and `beat` inside the `celery` region -- and per combination in Epic 8,
which extends both these assertions and the activation-env ones over each
*materialized* `pixi.toml`. And `accelerator.toml` does not exist, so the AD-24
region placed in `pixi.toml` here is declared in Epic 7; the markers are the
whole mechanism until then.

These read the manifests rather than executing the gate, so they are unit tests:
no I/O beyond reading repository files, no network, no database.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any
from typing import Final

import pytest

from config.component import ComponentDeclaration
from config.component import load_component_declaration
from config.locality import PROCESS_ENV_VAR
from config.locality import RUNTIME_ENV_VAR
from config.locality import SERVING_PROCESSES

REPO_ROOT = Path(__file__).resolve().parents[2]
PIXI_MANIFEST = REPO_ROOT / "pixi.toml"

# pixi's implicit feature. The unscoped `[tasks]` table belongs to it, and the
# walk below treats it as one feature scope among the rest so that a task
# declared under `[feature.<name>.tasks]` is read exactly like an unscoped one.
DEFAULT_FEATURE: Final[str] = "default"

# The one process type that exists in all six combinations (AC #4). It is `core`:
# it sits outside every region, which is what "unconditional" means in a file
# whose feature-owned lines are removed by marker.
CORE_PROCESS: Final[str] = "web"

# What serving `web` means, as fragments of its command rather than as the whole
# string. The `--bind` value and any worker count are deliberately *not* pinned:
# AD-22 gives the grace period to the deployment repository and gunicorn's own
# `GUNICORN_CMD_ARGS` is the injection point for all of it, so a component-side
# flag is not the contract. The server and the worker class are: the spine keeps
# `-k uvicorn_worker.UvicornWorker` explicitly, because gunicorn 26 ships a
# native `asgi` worker and dropping `uvicorn-worker` for it is a spike, not a
# decision already taken.
WEB_SERVER: Final[str] = "gunicorn"
# The component's own worker class, not the stock one. Story 5.4: uvicorn's
# `Server.capture_signals()` replaces the SIGTERM handler `config.asgi`
# installed, so the drain flip never ran in `web`; `config.workers` subclasses
# the server to flip readiness before shutting down. Asserting the component's
# class rather than merely "some uvicorn worker" is what keeps a well-meaning
# revert to the stock worker a gate failure instead of a silent regression.
WEB_WORKER_CLASS: Final[str] = "-k config.workers.DrainingUvicornWorker"

# The AD-24 region in `pixi.toml`, and the process-to-feature mapping that makes
# a half-stripped region visible.
#
# This mapping is declared once, here, because this module is where the process
# names are authoritative. `component.toml` carries two independent
# `# feature:celery` regions -- the `selected_features` entry and the
# `[[processes]]` pair -- and `pixi.toml` now carries a third, in `[tasks]`.
# Each was validated in isolation, so a strip that removed one and left the
# others loaded clean; the cross-region check below is what closes that.
CELERY_FEATURE: Final[str] = "celery"
CELERY_PROCESSES: Final[tuple[str, ...]] = ("worker", "beat")

# The Celery process whose shutdown semantics AC #2 of Story 5.4 depends on, and
# the flags that would change them. Named here for the same reason the process
# names are: this module is where the process model is authoritative.
#
# Spelled in both of Celery's accepted forms. `--pool=solo` and `--pool solo` are
# the same option and only one of them is a substring of the other, so checking
# one spelling would leave the other free to land.
WORKER_PROCESS: Final[str] = "worker"
SHUTDOWN_ALTERING_WORKER_FLAGS: Final[tuple[str, ...]] = (
    "--pool=solo",
    "--pool solo",
    "-P solo",
    "-P=solo",
    "-Ofair",
    "-O fair",
)
FEATURE_MARKERS: Final[tuple[str, str]] = (f"# feature:{CELERY_FEATURE}", f"# /feature:{CELERY_FEATURE}")

# A task assignment as `pixi.toml` writes one: `name = { cmd = ... }`. Used only
# to read task names back out of a *region*, which is a span of lines and not
# something the parsed TOML preserves. Every assertion about a task's content
# goes through `tomllib`.
TASK_ASSIGNMENT = re.compile(r"^(?P<name>[A-Za-z0-9_-]+) = \{")


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    """Return the parsed pixi manifest.

    Returns:
        The manifest, parsed from TOML.
    """
    with PIXI_MANIFEST.open("rb") as handle:
        parsed: dict[str, Any] = tomllib.load(handle)
    return parsed


@pytest.fixture(scope="module")
def declaration() -> ComponentDeclaration:
    """Return the repository's own component declaration.

    Read through the loader rather than with a second `tomllib.load`, so this
    module asserts against the records every other consumer sees -- including the
    loader's own refusals, which a raw parse would step around.

    Returns:
        The parsed and validated declaration.
    """
    return load_component_declaration()


def _feature_scopes(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return every feature scope in the manifest, including the implicit default one.

    Args:
        manifest: The parsed pixi manifest.

    Returns:
        Feature name -> the table that scopes it. The unscoped root is returned
        under `default`, which is the feature it belongs to.
    """
    scopes: dict[str, dict[str, Any]] = {DEFAULT_FEATURE: manifest}
    for name, feature in manifest.get("feature", {}).items():
        if isinstance(feature, dict):
            scopes[str(name)] = feature
    return scopes


def _task_tables(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return every task table in the manifest, keyed by where it lives.

    `[tasks]`, each `[feature.<name>.tasks]`, and the platform-scoped variants of
    both. Four unscoped-or-feature tables exist today and the platform-scoped
    ones hold nothing; they are read anyway, because a `worker` declared under
    `[target.linux-64.tasks]` is as real as any other and would otherwise escape
    the reverse direction entirely.

    The idiom is `tests/unit/test_locality_declaration.py`'s, mirrored rather
    than reinvented: the two modules assert complementary halves of one contract
    over the same tables, and a second shape would let a task be in scope for one
    and out of scope for the other.

    Args:
        manifest: The parsed pixi manifest.

    Returns:
        Table location -> {task name: task definition}.
    """
    tables: dict[str, dict[str, Any]] = {}
    for feature, scope in _feature_scopes(manifest).items():
        prefix = "" if feature == DEFAULT_FEATURE else f"feature.{feature}."
        tasks = scope.get("tasks")
        if isinstance(tasks, dict):
            tables[f"[{prefix}tasks]"] = tasks
        for platform, target in scope.get("target", {}).items():
            platform_tasks = target.get("tasks")
            if isinstance(platform_tasks, dict):
                tables[f"[{prefix}target.{platform}.tasks]"] = platform_tasks
    return tables


def _tasks(manifest: dict[str, Any]) -> list[tuple[str, str, Any]]:
    """Return every task in the manifest as (table location, name, definition).

    A list rather than a name-keyed mapping: keying by name lets a task declared
    in two tables overwrite its twin, and a shadowed `worker` declaring a
    different `COMPONENT_PROCESS` would then pass both directions of the gate
    while the manifest contained a task neither direction had seen.

    Args:
        manifest: The parsed pixi manifest.

    Returns:
        One entry per declaration, in manifest order.
    """
    return [
        (table, str(name), definition)
        for table, tasks in _task_tables(manifest).items()
        for name, definition in tasks.items()
    ]


def _task_env(definition: Any) -> dict[str, Any]:
    """Return the `env` table a task definition declares, or an empty one.

    A task written as a bare command string declares no `env` at all, which is
    the right answer here: absent process type means *not a serving process*
    (process type fails open), and absent locality means *deployed* (locality
    fails closed). The pair of directions is deliberate -- failing process type
    closed would make every management command a serving process and deadlock
    the release stage on the migrations refusal.

    Args:
        definition: One task's definition, in either legal form.

    Returns:
        The declared environment, or `{}` when the task declares none.
    """
    if not isinstance(definition, dict):
        return {}
    env = definition.get("env")
    return env if isinstance(env, dict) else {}


def _task_command(definition: Any) -> str:
    """Return the command a task runs, in either form the manifest permits.

    Args:
        definition: One task's definition.

    Returns:
        The command string, or an empty string for a task that declares only
        `depends-on`.
    """
    if isinstance(definition, str):
        return definition
    if isinstance(definition, dict):
        command = definition.get("cmd")
        if isinstance(command, str):
            return command
    return ""


def _process_group(manifest: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return the process group as (table location, task name, declared process type).

    The group is defined by what a task *declares*, not by what it is called
    (AD-26). A task is in it when its own `env` carries `COMPONENT_PROCESS`, and
    out of it otherwise, whatever its name suggests.

    Args:
        manifest: The parsed pixi manifest.

    Returns:
        One entry per task declaring a process type, in manifest order.
    """
    return [
        (table, name, str(env[PROCESS_ENV_VAR]))
        for table, name, definition in _tasks(manifest)
        for env in [_task_env(definition)]
        if PROCESS_ENV_VAR in env
    ]


def _tasks_named(manifest: dict[str, Any], name: str) -> list[tuple[str, str, Any]]:
    """Return every declaration of one task name, across every table.

    Args:
        manifest: The parsed pixi manifest.
        name: The task name to look for.

    Returns:
        The matching declarations, empty when the manifest declares no such task.
    """
    return [entry for entry in _tasks(manifest) if entry[1] == name]


def _manifest_lines() -> list[str]:
    """Return the manifest's lines, stripped, for the positional region assertions.

    A region is a span of lines. `tomllib` does not preserve one, and neither
    does it preserve comments, so the marker assertions read text -- and only the
    marker assertions do.

    Returns:
        Every line of `pixi.toml`, with surrounding whitespace removed.
    """
    return [line.strip() for line in PIXI_MANIFEST.read_text(encoding="utf-8").splitlines()]


def _lines_declare_task(lines: list[str], name: str) -> bool:
    """Report whether the manifest text assigns a task of this name anywhere.

    Read from text rather than from the parsed TOML because the caller is asking
    about a *stripped* manifest, where the question is whether a line survived a
    region removal rather than what the resulting table means.

    Args:
        lines: The stripped manifest lines.
        name: The task name to look for.

    Returns:
        True when some line assigns a task of that name.
    """
    return any((match := TASK_ASSIGNMENT.match(line)) and match["name"] == name for line in lines)


def _celery_region_bounds(lines: list[str]) -> tuple[int, int, int] | None:
    """Locate the `celery` region inside `[tasks]`, or report that it is absent.

    `None` is a legitimate answer rather than a failure. This module is `core`
    and runs unchanged in all six combinations, and in the four that do not
    select background task processing the materializer has removed this region
    -- markers included. A helper that raised there would make the module fail
    in the combinations it exists to keep honest, so absence is returned and the
    caller decides what it means.

    Args:
        lines: The stripped manifest lines.

    Returns:
        (opening marker index, closing marker index, index of the next table
        header after `[tasks]`), or `None` when the region is not in `[tasks]`.
    """
    opening, closing = FEATURE_MARKERS
    tasks_header = lines.index("[tasks]")
    next_header = next(index for index, line in enumerate(lines) if index > tasks_header and line.startswith("["))
    within = lines[tasks_header:next_header]
    if opening not in within or closing not in within:
        return None
    start = lines.index(opening, tasks_header)
    end = lines.index(closing, start)
    return start, end, next_header


def test_the_manifests_are_present() -> None:
    """Both halves of the process model resolve from this file, so the assertions mean something."""
    assert PIXI_MANIFEST.is_file()


def test_the_scanners_see_the_manifest_they_claim_to(
    manifest: dict[str, Any], declaration: ComponentDeclaration
) -> None:
    """The readers find the tables and records this file is written against.

    The two-way gate is a pair of set comparisons, and a reader that silently
    found nothing would satisfy both by comparing an empty set with an empty set
    -- green, while reconciling nothing at all. This is the non-vacuity guard for
    the file, and it is the assertion that fails first if a future manifest moves
    the tasks somewhere the walk does not look.
    """
    assert "[tasks]" in _task_tables(manifest)
    assert len(_task_tables(manifest)) > 1, "the feature-scoped task tables are not being read"
    assert _process_group(manifest), "no task declares a process type, so both directions below are vacuous"
    assert declaration.processes, "component.toml declares no process, so both directions below are vacuous"


def test_every_declared_process_names_a_task_that_declares_it(
    manifest: dict[str, Any], declaration: ComponentDeclaration
) -> None:
    """Forward direction: the declaration never promises a process nobody can run (AC #6).

    A `[[processes]]` entry is an instruction to a deployment repository that
    cannot read this source tree: it will invoke `pixi run <task>` and expect a
    process. An entry naming a task that does not exist, or one that exists but
    declares a different process type, is a component that fails on the platform
    rather than in the gate.
    """
    offenders: list[str] = []
    for process in declaration.processes:
        declarations = _tasks_named(manifest, process.task)
        if not declarations:
            offenders.append(f"{process.name!r} names task {process.task!r}, which pixi.toml does not declare")
            continue
        offenders.extend(
            f"{process.name!r} names task {process.task!r} in {table}, whose "
            f"{PROCESS_ENV_VAR} is {_task_env(definition).get(PROCESS_ENV_VAR)!r}"
            for table, _name, definition in declarations
            if _task_env(definition).get(PROCESS_ENV_VAR) != process.name
        )

    assert not offenders, (
        f"these [[processes]] entries do not reconcile with pixi.toml: {sorted(offenders)}. "
        f"AD-14's gate is two-way -- every process type the declaration names has a matching task, and the "
        f"task declares that same type in its own `env`."
    )


def test_every_task_in_the_process_group_is_named_by_the_declaration(
    manifest: dict[str, Any], declaration: ComponentDeclaration
) -> None:
    """Reverse direction: no runnable process type is undeclared (AC #6).

    The half AD-14 exists for. A `worker` task surviving into a component with no
    Celery is not a task nobody notices -- it is a process the deployment
    repository enumerates with `pixi task list` and then tries to run, against a
    component with no broker. The declaration is the only place its replica count
    and replacement strategy could have come from, so a task the declaration does
    not name is a process the platform would run blind.
    """
    declared = {process.name: process.task for process in declaration.processes}
    offenders: list[str] = []
    for table, name, process_type in _process_group(manifest):
        if process_type not in declared:
            offenders.append(f"task {name!r} in {table} declares {process_type!r}, which component.toml does not")
        elif declared[process_type] != name:
            offenders.append(
                f"task {name!r} in {table} declares {process_type!r}, but component.toml routes that process "
                f"to task {declared[process_type]!r}"
            )

    assert not offenders, (
        f"these tasks are in the process group but not reconciled by component.toml: {sorted(offenders)}. "
        f"Membership is structural -- a task declaring {PROCESS_ENV_VAR} is a serving process (AD-26) -- so a "
        f"task added without a [[processes]] entry is one the deployment repository would run with no declared "
        f"replica count or replacement strategy."
    )


def test_no_task_in_the_process_group_declares_a_runtime(manifest: dict[str, Any]) -> None:
    """A serving process inherits *deployed* and declares only its process type (AC #2).

    Locality is declared once, in `[feature.dev.activation.env]` (AD-13 as
    amended). A task `env` *overrides* the caller's, so a `COMPONENT_RUNTIME` on
    `web` could not be corrected by the deployment platform's configmap: the
    deployed process would read whatever the manifest froze into it and skip
    every stage-1 refusal built on locality. Absence is what makes the default
    fail closed, so absence is what is asserted.
    """
    offenders = sorted(
        f"{name} = {env[RUNTIME_ENV_VAR]!r} in {table}"
        for table, name, definition in _tasks(manifest)
        for env in [_task_env(definition)]
        if PROCESS_ENV_VAR in env and RUNTIME_ENV_VAR in env
    )
    assert not offenders, (
        f"these serving-process tasks declare a runtime: {offenders}. "
        f"A process task sets {PROCESS_ENV_VAR} and nothing else (AD-13); declaring {RUNTIME_ENV_VAR} inverts "
        f"the fail-closed locality default and takes the deployment platform out of the loop."
    )


def test_the_web_process_is_unconditional_and_served_by_gunicorn(manifest: dict[str, Any]) -> None:
    """`web` is in the process group in every combination, with the pinned worker class (AC #4).

    It is the one process type present in all six combinations, which in a
    marker-stripped file means it must sit outside every region -- asserted
    positionally below, and asserted here as the fact that it is in the group at
    all. The worker class is pinned because the spine pins it: gunicorn 26 ships
    a native `asgi` worker, and dropping `uvicorn-worker` for it is a spike
    rather than a decision, so a silent swap must fail here.
    """
    declarations = [(table, name, definition) for table, name, definition in _tasks(manifest) if name == CORE_PROCESS]
    assert declarations, f"pixi.toml declares no {CORE_PROCESS!r} task; it is core and exists in all six combinations"

    offenders = sorted(
        f"{name} in {table}: env={_task_env(definition).get(PROCESS_ENV_VAR)!r}, cmd={_task_command(definition)!r}"
        for table, name, definition in declarations
        if _task_env(definition).get(PROCESS_ENV_VAR) != CORE_PROCESS
        or WEB_SERVER not in _task_command(definition)
        or WEB_WORKER_CLASS not in _task_command(definition)
    )
    assert not offenders, (
        f"these {CORE_PROCESS!r} declarations do not serve the component as AD-14 requires: {offenders}. "
        f"It must declare {PROCESS_ENV_VAR} = {CORE_PROCESS!r} and run {WEB_SERVER} with {WEB_WORKER_CLASS!r}."
    )


def test_every_declared_process_is_a_process_type_the_locality_module_recognizes(
    declaration: ComponentDeclaration,
) -> None:
    """The two declaration sites agree on what the process types are called (AD-1).

    `config.locality.SERVING_PROCESSES` is the single declaration site for the
    names, and it is imported here rather than re-spelled -- a test that restated
    the three literals would pass while the module and the manifest disagreed.

    A **subset**, not an equality: a combination without background task
    processing declares `web` alone, while the locality module still recognizes
    all three because it is `core` and is not stripped per combination.
    """
    offenders = sorted(process.name for process in declaration.processes if process.name not in SERVING_PROCESSES)
    assert not offenders, (
        f"component.toml declares these process types, which config.locality does not recognize: {offenders}. "
        f"The recognized set is {sorted(SERVING_PROCESSES)}, declared once in src/config/locality.py (AD-1); a "
        f"process type outside it would set {PROCESS_ENV_VAR} to a value no reader treats as a serving process."
    )


def test_no_administrative_process_runs_a_task_that_declares_a_process_type(
    manifest: dict[str, Any], declaration: ComponentDeclaration
) -> None:
    """An admin process is outside the process group and must stay there (AD-13).

    `prune` is a one-off maintenance run, not a serving process. A task that
    declared `COMPONENT_PROCESS` would fire the serving-process refusals on the
    very maintenance it was invoked to do -- the same shape of failure AD-13
    attributes to a `COMPONENT_PROCESS` in `[activation.env]`, where `pixi run
    migrate` refuses on the unapplied-migrations condition and deadlocks the
    release stage.

    Deliberately *not* asserted: that the task exists. `component.toml` declares
    `prune` and no `prune` task is written until the session-pruning story lands,
    which is a forward reference rather than a defect. The admin half of the
    manifest therefore has no forward direction; it has only this prohibition.
    """
    offenders = sorted(
        f"admin process {admin.name!r} runs task {admin.task!r} in {table}, which declares "
        f"{PROCESS_ENV_VAR} = {_task_env(definition).get(PROCESS_ENV_VAR)!r}"
        for admin in declaration.admin_processes
        for table, _name, definition in _tasks_named(manifest, admin.task)
        if PROCESS_ENV_VAR in _task_env(definition)
    )
    assert not offenders, (
        f"these administrative processes declare themselves serving processes: {offenders}. "
        f"An admin process is outside the process group (AD-13) and never sets {PROCESS_ENV_VAR}."
    )


def test_the_celery_process_tasks_sit_inside_a_marker_pair() -> None:
    """AD-24: `worker` and `beat` exist in two of the six combinations (AC #5).

    They are removed as a feature-owned region rather than surviving into a
    component the deployment repository would then try to run, and a region is
    the only sub-file removal mechanism AD-24 permits. Markers are matched as
    whole lines, in TOML's own comment syntax, because prose *about* a marker is
    not one -- and this file's comments discuss the region at length.

    Both bounds are asserted and the upper one is load-bearing. A region that
    merely *contains* `worker` and `beat` is satisfied by a closing marker moved
    down the table, and a materializer stripping that region in a non-Celery
    combination would then silently delete `seed-personas` or `mint-token`, which
    are `core` and have nothing to do with Celery.

    In the four combinations where the region has been stripped there is nothing
    to bound, so the case asserts the complement instead: no Celery process task
    survived the strip. This module is `core` and runs in all six combinations,
    so it is written to hold in each rather than to describe the reference
    application. Whether *absence here* agrees with absence in `component.toml`
    is the next case's question, not this one's.
    """
    lines = _manifest_lines()
    bounds = _celery_region_bounds(lines)
    if bounds is None:
        survivors = sorted(name for name in CELERY_PROCESSES if _lines_declare_task(lines, name))
        assert not survivors, (
            f"the {FEATURE_MARKERS[0]} region is gone from [tasks] but {survivors} survived it. "
            f"A Celery process task in a component with no broker is a process the deployment "
            f"repository would try to run (AD-14)."
        )
        return

    start, end, next_header = bounds
    region = lines[start + 1 : end]

    # Lower bound: both Celery processes are inside, and they are the only tasks
    # inside -- an exact list, not a containment check.
    matches = [match["name"] for line in region if (match := TASK_ASSIGNMENT.match(line))]
    assert matches == list(CELERY_PROCESSES), (
        f"the {FEATURE_MARKERS[0]} region in [tasks] holds tasks {matches}, not {list(CELERY_PROCESSES)}. "
        f"Only the Celery process tasks belong inside it; anything else is deleted with them in the four "
        f"combinations that do not select the feature."
    )

    # Upper bound: `web` is core and is declared before the region opens, and the
    # region closes before the next table begins.
    web_line = next(
        index for index, line in enumerate(lines) if TASK_ASSIGNMENT.match(line) and line.startswith(f"{CORE_PROCESS} ")
    )
    assert web_line < start, (
        f"the {CORE_PROCESS!r} task is inside the {CELERY_FEATURE!r} region and would be stripped with it"
    )
    assert end < next_header, f"the {FEATURE_MARKERS[1]} marker sits past the end of [tasks]"


def test_the_celery_feature_its_processes_and_its_task_region_are_present_or_absent_together() -> None:
    """A half-stripped `celery` region fails here rather than loading clean (AC #5).

    Three independent regions carry the one feature: `selected_features` and the
    `[[processes]]` pair in `component.toml`, and the `[tasks]` region added
    here. Each is validated in isolation by its own file's loader, so a strip
    that removed one and left another produced a declaration that parsed --
    `celery` deselected while `worker` and `beat` were still declared and still
    runnable, or the reverse.

    The mapping that makes this checkable, `{"worker", "beat"} implies celery`,
    is declared once at the top of this module because this is where the process
    names are authoritative. Epic 8 owns the strip itself and re-runs these
    assertions per materialized combination; what this case guarantees is that a
    combination reaching the gate half-stripped fails on the inconsistency rather
    than on whatever it breaks three steps later.
    """
    lines = _manifest_lines()
    opening, closing = FEATURE_MARKERS
    tasks_header = lines.index("[tasks]")
    region_present = opening in lines[tasks_header:] and closing in lines[tasks_header:]

    declared = load_component_declaration()
    with PIXI_MANIFEST.open("rb") as handle:
        parsed: dict[str, Any] = tomllib.load(handle)
    declared_processes = {process.name for process in declared.processes}
    group = {name for _table, name, _process_type in _process_group(parsed)}

    signals = {
        f"component.toml selected_features declares {CELERY_FEATURE!r}": CELERY_FEATURE in declared.selected_features,
        f"pixi.toml [tasks] carries the {opening!r} region": region_present,
    }
    for process in CELERY_PROCESSES:
        signals[f"component.toml declares the {process!r} process"] = process in declared_processes
        signals[f"pixi.toml declares the {process!r} task"] = process in group

    present = sorted(signal for signal, held in signals.items() if held)
    absent = sorted(signal for signal, held in signals.items() if not held)
    assert not (present and absent), (
        f"the {CELERY_FEATURE!r} regions disagree -- present: {present}; absent: {absent}. "
        f"The feature selection, the [[processes]] entries and the [tasks] region are one decision written in "
        f"three places (AD-24), and a strip that took some of them leaves a component whose declaration and "
        f"whose runnable tasks describe different components."
    )


def test_the_worker_command_carries_no_shutdown_altering_flag(manifest: dict[str, Any]) -> None:
    """AD-22 relies on Celery's *default* warm shutdown, so nothing may change it.

    One `SIGTERM` to a Celery worker stops it consuming new messages and lets it
    finish the tasks it already holds. That is AC #2 in full, and Story 5.4's
    obligation is to keep it true rather than to reimplement it -- the drain
    handler flips readiness and hands the signal straight back to Celery's own.
    A component-side flag is the one thing in this repository that can quietly
    withdraw the behaviour underneath it:

    * `--pool=solo` runs tasks in the main thread, where the signal interrupts
      the task rather than being handled after it, so the in-flight task is lost
      -- the precise failure AC #2 names.
    * `-Ofair` changes prefetch behaviour, and with it how much acknowledged work
      a worker is holding when the signal arrives.

    Read from the manifest rather than asserted as prose beside the task, because
    the comment inside the `celery` region says the same thing and a comment is
    not a gate. Vacuous in the four combinations where the region has been
    stripped, which is correct: a component with no `worker` task has no worker
    shutdown semantics to alter.
    """
    assert WORKER_PROCESS in CELERY_PROCESSES, (
        "the worker task was renamed and this case would have gone vacuous rather than failing"
    )
    offenders = sorted(
        f"{table}.{name} carries {flag!r}"
        for table, name, definition in _tasks_named(manifest, WORKER_PROCESS)
        for flag in SHUTDOWN_ALTERING_WORKER_FLAGS
        if flag in _task_command(definition)
    )

    assert not offenders, (
        f"these worker tasks alter Celery's shutdown semantics: {offenders}. AD-22 gives the drain "
        f"ordering to the component and the grace-period value to the deployment repository; neither "
        f"is a flag on this command, and Story 5.4's handler delegates to Celery's default warm "
        f"shutdown rather than replacing it."
    )
