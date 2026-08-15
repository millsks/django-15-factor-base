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
