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
from urllib.parse import urlsplit

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

# URL schemes that select PostgreSQL, as `urlsplit().scheme` reports them.
# `django-environ` accepts both spellings, and `config/settings/base.py:57`
# branches on the variable being truthy, so an empty or sqlite URL would revert
# the whole gate to the substitution while every other assertion here passed.
POSTGRES_URL_SCHEMES = frozenset({"postgres", "postgresql"})

# Image families that constitute "a database service" for the exclusivity checks
# below. Broader than POSTGRES_IMAGE_PREFIX on purpose: the reason the matrix
# may not have a database is that GitHub Actions `services:` containers are
# Linux-only, and that reason does not care which database it is. Matched on the
# repository segment so a registry-qualified or untagged image cannot slip past.
DATABASE_IMAGE_NAMES = frozenset({"postgres", "postgis", "mysql", "mariadb"})


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


def _is_database_image(image: str) -> bool:
    """Report whether a service image is a database, registry prefix or not.

    Matched on the repository segment rather than a string prefix so that
    `ghcr.io/example/postgres:18` and an untagged `postgres` are both caught.
    """
    repository = image.split("@", 1)[0].rsplit(":", 1)[0]
    return repository.rsplit("/", 1)[-1].lower() in DATABASE_IMAGE_NAMES


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


def _published_host_port(service: dict[str, Any]) -> str:
    """Return the host side of the service's `host:container` port mapping."""
    for port in service.get("ports", []):
        host, _, container = str(port).partition(":")
        if container == "5432":
            return host
    return ""


def test_the_postgresql_service_is_health_gated_and_reachable(workflows: Workflows) -> None:
    """The service must be ready before a step runs, and be published to the runner.

    Without the health check the gate starts `pixi run ci` against a database
    still coming up, which fails as connection-refused on a change that has
    nothing to do with the database. Without the port mapping the URL below
    resolves to nothing on `localhost`. Both are silent-in-review, loud-at-3am.

    The health command must reach the server over TCP, not the local socket.
    The postgres image runs initdb against a temporary server with
    `listen_addresses=''`, so a socket-scoped `pg_isready` reports ready while
    the port the runner uses is still closed -- a health gate that opens early
    is barely better than none.
    """
    service = _postgres_service(workflows)
    options = str(service.get("options", ""))
    assert "pg_isready" in options, f"the postgres service must health-check with pg_isready, got {options!r}"
    assert "-h localhost" in options, f"the health check must probe TCP, not the unix socket, got {options!r}"

    ports = [str(port) for port in service.get("ports", [])]
    assert any(port.endswith(":5432") for port in ports), f"the postgres service must publish 5432, got {ports}"


def test_the_gate_sets_the_database_url_for_the_whole_job(workflows: Workflows) -> None:
    """FR-32: the gate run is pointed at that service.

    The variable must sit on the job's own `env`, not on a step's, so that no
    step of `pixi run ci` can be reordered or added into a position where the
    database-touching ones no longer see it.
    """
    gate = workflows["ci.yml"]["jobs"]["gate"]
    assert "DATABASE_URL" in gate.get("env", {}), "DATABASE_URL must be set at job level on the gate"


def test_the_database_url_names_the_declared_postgresql_service(workflows: Workflows) -> None:
    """The URL's *value* is the mechanism, so the value is what must be asserted.

    Asserting only that the key exists lets `DATABASE_URL: ""` -- or a sqlite
    URL -- pass this file while reverting the gate to the substitution, because
    `config/settings/base.py:57` tests the variable for truthiness. That is the
    one edit that would make FR-32 false with a green suite, so it is pinned to
    the service declared a few lines above it in ci.yml.

    The URL is parsed rather than substring-searched. Containment would accept
    a credential that merely appears somewhere in the string (`POSTGRES_DB:
    user` is "in" `gateuser`), would break on a legitimate `?sslmode=` query
    parameter, and above all would not notice the host and port -- the halves
    that decide whether the URL reaches the declared service at all. A
    `ports: ["55432:5432"]` edit passed every previous assertion here and left
    the gate connection-refused.
    """
    url = str(workflows["ci.yml"]["jobs"]["gate"]["env"]["DATABASE_URL"])
    parsed = urlsplit(url)
    assert parsed.scheme in POSTGRES_URL_SCHEMES, f"the gate's DATABASE_URL must name PostgreSQL, got {url!r}"

    service = _postgres_service(workflows)
    service_env = service.get("env", {})
    missing = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"} - service_env.keys()
    assert not missing, f"the postgres service must declare its own credentials, missing {sorted(missing)}"

    assert parsed.username == str(service_env["POSTGRES_USER"]), (
        f"the gate's DATABASE_URL user is not the service's POSTGRES_USER: {url!r}"
    )
    assert parsed.password == str(service_env["POSTGRES_PASSWORD"]), (
        f"the gate's DATABASE_URL password is not the service's POSTGRES_PASSWORD: {url!r}"
    )
    assert parsed.path.rstrip("/") == f"/{service_env['POSTGRES_DB']}", (
        f"the gate's DATABASE_URL must select the service's database, got {url!r}"
    )

    # The runner reaches a service container through the port it publishes on
    # the host, so the URL's host and port are as load-bearing as the password.
    assert parsed.hostname == "localhost", f"a service container is reached on localhost, got {url!r}"
    published = _published_host_port(service)
    assert str(parsed.port) == published, (
        f"the gate's DATABASE_URL port {parsed.port} is not the service's published port {published!r}"
    )


def test_no_other_job_declares_a_database_service(workflows: Workflows) -> None:
    """The three-OS matrix stays on the sqlite substitution.

    GitHub Actions `services:` containers run only on Linux runners, so a
    database attached to that matrix could not work on two of its three legs.

    Scoped to *database* services on purpose: a future non-database service --
    a Redis for Celery integration tests, say -- is legitimate work that this
    check has no business blocking, and the Linux-runner reasoning above does
    not extend to it. It is not scoped to `postgres:` though: the reason the
    matrix may not have a database does not care which database it is, and a
    `mysql:8` or a registry-qualified `ghcr.io/.../postgresql:18` would break
    the same two legs for the same reason.
    """
    offenders = [
        f"{name}:{job_name}"
        for name, workflow in workflows.items()
        for job_name, job in workflow.get("jobs", {}).items()
        if not (name == "ci.yml" and job_name == "gate")
        for service in job.get("services", {}).values()
        if _is_database_image(str(service.get("image", "")))
    ]
    assert offenders == [], f"only the gate job may declare a database service: {offenders}"


def test_no_other_job_points_itself_at_a_database(workflows: Workflows) -> None:
    """A `DATABASE_URL` elsewhere would move a job off sqlite without a service.

    The sibling check above bans the service; this one bans the other half of
    the same mistake. A matrix leg that set `DATABASE_URL` with no service to
    back it would fail on connection rather than run on the substitution, and
    the three-OS claim in ci.yml's comment would quietly stop being true.

    Step-level `env:` is checked as well as job-level, because the two are
    interchangeable for this purpose and only pinning one of them leaves the
    obvious way in.
    """
    offenders = [
        f"{name}:{job_name}"
        for name, workflow in workflows.items()
        for job_name, job in workflow.get("jobs", {}).items()
        if not (name == "ci.yml" and job_name == "gate")
        if "DATABASE_URL" in job.get("env", {})
        or any("DATABASE_URL" in step.get("env", {}) for step in job.get("steps", []))
    ]
    assert offenders == [], f"only the gate job may set DATABASE_URL: {offenders}"


def test_some_job_still_exercises_the_sqlite_substitution(workflows: Workflows) -> None:
    """AC #4: sqlite is exercised in CI, not merely left configured.

    Once the gate moved onto PostgreSQL this became a real hole rather than a
    theoretical one: the unit tests open no database connection at all, so
    without an integration run somewhere without a `DATABASE_URL`, nothing in
    CI touches sqlite and PostgreSQL-only ORM code passes every job while
    breaking `pixi run ci` for every developer with nothing running.

    The step that closes it lives on the compatibility matrix and was the only
    part of this change with nothing asserting it -- deleting it was silent,
    while its sibling checks above guarded loudly against a database appearing
    where it should not. This is the symmetric half.
    """
    offenders = [
        f"{name}:{job_name}"
        for name, workflow in workflows.items()
        for job_name, job in workflow.get("jobs", {}).items()
        if "DATABASE_URL" not in job.get("env", {})
        if any(_invokes(step.get("run", ""), "test-integration") for step in job.get("steps", []) if step.get("run"))
    ]
    assert offenders != [], "no CI job runs pixi run test-integration without a DATABASE_URL; sqlite is untested"


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
