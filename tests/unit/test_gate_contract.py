"""Tests for the gate contract: one task, one invocation, one place it runs.

AD-18 requires that a single workflow invokes `pixi run ci`, and that the gate
runs pre-commit, build, check, lint and cov in that order. These tests read the
manifests rather than executing the gate, so they are unit tests: no I/O beyond
reading repository files, no network, no database.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

Workflows = dict[str, dict[str, Any]]

REPO_ROOT = Path(__file__).resolve().parents[2]
PIXI_MANIFEST = REPO_ROOT / "pixi.toml"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# The five gate steps in the order AD-18 fixes. These are this repository's task
# identifiers, which differ from the global standard's fmt/check/cov names; the
# AD names the steps, not the identifiers, and renaming them would break
# .pre-commit-config.yaml, release.yml and sonarqube.yml in the same change.
GATE_SEQUENCE = ["precommit", "build", "typecheck", "lint", "test-cov"]

# Gate steps that must not be invoked by any workflow other than the gate job.
# `build` also has its own narrower check for cron specifically
# (test_no_scheduled_workflow_invokes_build), which AC #3 asks for by name;
# it is included here too so the exclusivity guarantee matches AC #5's full
# intent -- "no step exists only in CI or only locally" -- rather than only
# the schedule-triggered case.
GATE_ONLY_TASKS = ["precommit", "build", "test-cov", "lint", "typecheck"]

THREE_OS_RUNNERS = {"ubuntu-latest", "windows-latest", "macos-latest"}

# FR-32: the gate runs against the database the immovable core names.
#
# Only the family is asserted here, not the tag. Nothing in the repository can
# fix the server major version: `libpq` in pixi.toml is the *client* library and
# a libpq 18 client connects happily to an older server, so a `libpq` pin is not
# a server pin and must not be described as one. The tag in ci.yml is a choice
# made to match that client, and it is the workflow's comment -- not a test --
# that carries the reason.
POSTGRES_IMAGE_PREFIX = "postgres:"

# The scheme half of the gate's DATABASE_URL. `django-environ` accepts both
# spellings for PostgreSQL, and `config/settings/base.py:57` branches on the
# variable being truthy, so an empty or sqlite URL would revert the whole gate
# to the substitution while every other assertion in this file still passed.
POSTGRES_URL_SCHEMES = ("postgres://", "postgresql://")


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    """Return the parsed pixi manifest."""
    with PIXI_MANIFEST.open("rb") as handle:
        parsed: dict[str, Any] = tomllib.load(handle)
    return parsed


@pytest.fixture(scope="module")
def workflows() -> Workflows:
    """Return every parsed workflow file, keyed by filename."""
    parsed: dict[str, dict[str, Any]] = {}
    paths = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            parsed[path.name] = yaml.safe_load(handle)
    return parsed


def _all_tasks(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return every task definition, whether it sits in [tasks] or a feature."""
    tasks: dict[str, Any] = dict(manifest.get("tasks", {}))
    for feature in manifest.get("feature", {}).values():
        tasks.update(feature.get("tasks", {}))
    return tasks


def _run_steps(workflow: dict[str, Any]) -> list[str]:
    """Return the `run` body of every step in every job of a workflow."""
    steps: list[str] = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            run = step.get("run")
            if isinstance(run, str):
                steps.append(run)
    return steps


def _invokes(run_body: str, task: str) -> bool:
    """Report whether a step body invokes `pixi run <task>`.

    Matches on token boundaries so that `pixi run test-cov` is not read as an
    invocation of `pixi run test`.
    """
    needle = f"pixi run {task}"
    for line in run_body.splitlines():
        stripped = line.strip()
        if stripped == needle or stripped.startswith(f"{needle} "):
            return True
    return False


def _is_scheduled(workflow: dict[str, Any]) -> bool:
    """Report whether a workflow has a cron trigger.

    PyYAML parses the unquoted key `on` as the boolean True, so both spellings
    are checked rather than assuming either.
    """
    triggers = workflow.get("on", workflow.get(True, {}))
    return isinstance(triggers, dict) and "schedule" in triggers


def test_ci_task_reaches_every_gate_step(manifest: dict[str, Any]) -> None:
    """`pixi run ci` must reach all five steps AD-18 names."""
    ci = _all_tasks(manifest)["ci"]
    assert ci.get("depends-on") is not None, "ci must declare its steps via depends-on"
    assert set(ci["depends-on"]) == set(GATE_SEQUENCE)


def test_ci_task_runs_the_gate_steps_in_order(manifest: dict[str, Any]) -> None:
    """The executed order must be pre-commit, build, check, lint, cov.

    pixi executes `depends-on` sequentially in declaration order and stops at
    the first failure, so the list order is the executed order.
    """
    ci = _all_tasks(manifest)["ci"]
    assert ci["depends-on"] == GATE_SEQUENCE


def test_every_gate_step_pins_its_environment(manifest: dict[str, Any]) -> None:
    """`pixi run ci` must never prompt for an environment.

    pixi rejects `default-environment` on a task that only declares
    `depends-on`, so `ci` cannot pin one itself. What makes the gate
    non-interactive is that every step it depends on pins `dev`.
    """
    tasks = _all_tasks(manifest)
    unpinned = [step for step in GATE_SEQUENCE if tasks[step].get("default-environment") != "dev"]
    assert unpinned == [], f"these steps would prompt for an environment: {unpinned}"


def test_exactly_one_workflow_invokes_the_gate(workflows: Workflows) -> None:
    """AD-18: a single workflow invokes `pixi run ci`."""
    invoking = [
        name for name, workflow in workflows.items() if any(_invokes(step, "ci") for step in _run_steps(workflow))
    ]
    assert invoking == ["ci.yml"], f"only ci.yml may invoke the gate, got {invoking}"


def test_no_scheduled_workflow_invokes_build(workflows: Workflows) -> None:
    """AD-18: `build` comes off its fortnightly cron and onto the gate."""
    offenders = [
        name
        for name, workflow in workflows.items()
        if _is_scheduled(workflow) and any(_invokes(step, "build") for step in _run_steps(workflow))
    ]
    assert offenders == [], f"a cron must not invoke build: {offenders}"


@pytest.mark.parametrize("task", GATE_ONLY_TASKS)
def test_gate_steps_run_only_inside_the_gate(task: str, workflows: Workflows) -> None:
    """No workflow other than the gate may run a gate step on its own.

    This is what keeps AC #5 true: a step that exists only in one workflow is a
    step a developer cannot reproduce with `pixi run ci`.
    """
    offenders = [
        name
        for name, workflow in workflows.items()
        if name != "ci.yml" and any(_invokes(step, task) for step in _run_steps(workflow))
    ]
    assert offenders == [], f"{task} must run only in the gate, found in {offenders}"


def _postgres_service(workflows: Workflows) -> dict[str, Any]:
    """Return the gate job's PostgreSQL service definition."""
    services = workflows["ci.yml"]["jobs"]["gate"].get("services", {})
    for service in services.values():
        if str(service.get("image", "")).startswith(POSTGRES_IMAGE_PREFIX):
            return service
    return {}


def test_the_gate_declares_a_postgresql_service(workflows: Workflows) -> None:
    """FR-32: CI declares a PostgreSQL service, which no workflow did before."""
    services = workflows["ci.yml"]["jobs"]["gate"].get("services", {})
    images = [service.get("image", "") for service in services.values()]
    assert any(image.startswith(POSTGRES_IMAGE_PREFIX) for image in images), (
        f"the gate job declares no postgres service, got images {images}"
    )


def test_the_postgresql_service_is_health_gated_and_reachable(workflows: Workflows) -> None:
    """The service must be ready before a step runs, and be published to the runner.

    Without the health check the gate starts `pixi run ci` against a database
    still coming up, which fails as connection-refused on a change that has
    nothing to do with the database. Without the port mapping the URL below
    resolves to nothing on `localhost`. Both are silent-in-review, loud-at-3am.
    """
    service = _postgres_service(workflows)
    options = str(service.get("options", ""))
    assert "pg_isready" in options, f"the postgres service must health-check with pg_isready, got {options!r}"

    ports = [str(port) for port in service.get("ports", [])]
    assert any(port.endswith(":5432") for port in ports), f"the postgres service must publish 5432, got {ports}"


def test_the_gate_sets_the_database_url_for_the_whole_job(workflows: Workflows) -> None:
    """FR-32: the gate run is pointed at that service.

    The variable must sit on the job's own `env`, not on a step's: `pixi run ci`
    runs five steps and every one of them has to see the same database.
    """
    gate = workflows["ci.yml"]["jobs"]["gate"]
    assert "DATABASE_URL" in gate.get("env", {}), "DATABASE_URL must be set at job level on the gate"


def test_the_database_url_names_the_declared_postgresql_service(workflows: Workflows) -> None:
    """The URL's *value* is the mechanism, so the value is what must be asserted.

    Asserting only that the key exists lets `DATABASE_URL: ""` -- or a sqlite
    URL -- pass this file while reverting the gate to the substitution, because
    `config/settings/base.py:57` tests the variable for truthiness. That is the
    one edit that would make FR-32 false with a green suite, so it is pinned to
    the credentials of the service declared a few lines above it in ci.yml.
    """
    url = str(workflows["ci.yml"]["jobs"]["gate"]["env"]["DATABASE_URL"])
    assert url.startswith(POSTGRES_URL_SCHEMES), f"the gate's DATABASE_URL must name PostgreSQL, got {url!r}"

    service_env = _postgres_service(workflows).get("env", {})
    for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        value = str(service_env[key])
        assert value in url, f"the gate's DATABASE_URL does not carry the service's {key}: {url!r}"
    assert url.rstrip("/").endswith(f"/{service_env['POSTGRES_DB']}"), (
        f"the gate's DATABASE_URL must select the service's database, got {url!r}"
    )


def test_no_other_job_declares_a_database_service(workflows: Workflows) -> None:
    """The three-OS matrix stays on the sqlite substitution.

    GitHub Actions `services:` containers run only on Linux runners, so a
    database attached to that matrix could not work on two of its three legs.

    Scoped to *database* services on purpose: a future non-database service --
    a Redis for Celery integration tests, say -- is legitimate work that this
    check has no business blocking, and the Linux-runner reasoning above does
    not extend to it.
    """
    offenders = [
        f"{name}:{job_name}"
        for name, workflow in workflows.items()
        for job_name, job in workflow.get("jobs", {}).items()
        if not (name == "ci.yml" and job_name == "gate")
        for service in job.get("services", {}).values()
        if str(service.get("image", "")).startswith(POSTGRES_IMAGE_PREFIX)
    ]
    assert offenders == [], f"only the gate job may declare a database service: {offenders}"


def test_no_other_job_points_itself_at_a_database(workflows: Workflows) -> None:
    """A `DATABASE_URL` elsewhere would move a job off sqlite without a service.

    The sibling check above bans the service; this one bans the other half of
    the same mistake. A matrix leg that set `DATABASE_URL` with no service to
    back it would fail on connection rather than run on the substitution, and
    the three-OS claim in ci.yml's comment would quietly stop being true.
    """
    offenders = [
        f"{name}:{job_name}"
        for name, workflow in workflows.items()
        for job_name, job in workflow.get("jobs", {}).items()
        if "DATABASE_URL" in job.get("env", {}) and not (name == "ci.yml" and job_name == "gate")
    ]
    assert offenders == [], f"only the gate job may set DATABASE_URL: {offenders}"


def test_reference_application_keeps_its_three_os_matrix(workflows: Workflows) -> None:
    """AC #4: the three-OS matrix stays on the reference application.

    The PostgreSQL gate cannot join it, because GitHub Actions `services:`
    containers run only on Linux runners.
    """
    jobs = workflows["ci.yml"]["jobs"]
    matrices = [job.get("strategy", {}).get("matrix", {}).get("os", []) for job in jobs.values()]
    assert any(THREE_OS_RUNNERS.issubset(set(os_list)) for os_list in matrices), (
        f"no job declares all of {sorted(THREE_OS_RUNNERS)}"
    )
