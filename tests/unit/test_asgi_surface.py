"""Tests that `config.asgi` exposes Django's application and nothing else.

AD-16: `asgi.py` exposes Django's ASGI application directly. The scope
dispatcher, `config/websocket.py` and the module's coverage-exclusion entries
are all deleted together, so a surface that the route allowlist cannot see
cannot come back one file at a time.

This module reads `src/config/asgi.py` rather than importing it. Importing it
runs `configure_observability()` for real, which instruments Django, Celery,
psycopg and redis process-wide and -- when `OTEL_EXPORTER_OTLP_ENDPOINT` is set
-- attaches a `BatchSpanProcessor` that exports over the network. That is the
invariant `tests/unit/test_telemetry.py` already states, and `pixi.toml`
advertises this suite as unit tests with no I/O. The runtime identity of the
callable is asserted in `tests/integration/test_asgi_request_path.py`, which
imports the module legitimately.
"""

from __future__ import annotations

import ast
import importlib.util
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
SONAR_PROPERTIES = REPO_ROOT / "sonar-project.properties"
ASGI_SOURCE = REPO_ROOT / "src" / "config" / "asgi.py"


def _asgi_module() -> ast.Module:
    """Parse `src/config/asgi.py` without importing it.

    Returns:
        The parsed module, for structural assertions about the ASGI surface.

    """
    return ast.parse(ASGI_SOURCE.read_text(encoding="utf-8"))


def _omit_entries() -> list[str]:
    """Return the `[tool.coverage.run] omit` list as written in pyproject.toml.

    Returns:
        Every path pattern declared in the coverage omit list.

    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    omit = data["tool"]["coverage"]["run"]["omit"]
    return list(omit)


def _sonar_coverage_exclusions() -> list[str]:
    """Return `sonar.coverage.exclusions` as written in sonar-project.properties.

    Returns:
        Every path pattern excluded from SonarCloud coverage.

    """
    for line in SONAR_PROPERTIES.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "sonar.coverage.exclusions":
            return [entry.strip() for entry in value.split(",") if entry.strip()]
    message = "sonar-project.properties declares no sonar.coverage.exclusions"
    raise AssertionError(message)


class TestAsgiApplication:
    """The module-level callable is Django's handler, not a wrapper."""

    def test_application_is_assigned_from_get_asgi_application(self):
        """`application = get_asgi_application()`, with nothing wrapping it."""
        assignments = [
            node
            for node in _asgi_module().body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "application" for target in node.targets)
        ]

        assert len(assignments) == 1, "expected exactly one module-level `application` assignment"
        value = assignments[0].value
        assert isinstance(value, ast.Call), "`application` must be the result of a call"
        assert isinstance(value.func, ast.Name)
        assert value.func.id == "get_asgi_application"
        assert value.args == [], "Django's handler is exposed unwrapped"
        assert value.keywords == [], "Django's handler is exposed unconfigured"

    def test_no_function_named_application_is_defined(self):
        """The deleted scope dispatcher was `async def application(...)`."""
        definitions = [
            node.name
            for node in _asgi_module().body
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name == "application"
        ]

        assert definitions == []

    def test_no_other_name_is_bound_to_an_asgi_callable(self):
        """`django_application` was the dispatcher's inner handle; it is gone."""
        bound = {
            target.id
            for node in _asgi_module().body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }

        assert bound == {"SRC_DIR", "application"}


class TestWebsocketModuleIsGone:
    """The module is deleted, not merely unreferenced."""

    def test_the_module_cannot_be_found(self):
        assert importlib.util.find_spec("config.websocket") is None

    def test_the_source_file_does_not_exist(self):
        assert not (REPO_ROOT / "src" / "config" / "websocket.py").exists()

    def test_asgi_does_not_import_it(self):
        """The wrapper's import carried a `# noqa: E402` and a rationale comment."""
        imported = {
            alias.name
            for node in ast.walk(_asgi_module())
            if isinstance(node, ast.ImportFrom | ast.Import)
            for alias in node.names
        } | {node.module or "" for node in ast.walk(_asgi_module()) if isinstance(node, ast.ImportFrom)}

        assert [name for name in imported if "websocket" in name] == []


class TestCoverageExclusionsAreClosed:
    """AD-16 deletes the coverage exclusions in the same change as the module.

    There are two carriers, not one: `[tool.coverage.run] omit` drives the gate
    and `sonar.coverage.exclusions` drives SonarCloud. A module excluded in
    either is a module whose coverage nobody reads, so both are asserted here.
    """

    def test_no_omit_entry_mentions_websocket(self):
        assert [entry for entry in _omit_entries() if "websocket" in entry] == []

    def test_no_sonar_exclusion_mentions_websocket(self):
        assert [entry for entry in _sonar_coverage_exclusions() if "websocket" in entry] == []

    def test_the_deployment_entrypoints_are_still_omitted(self):
        """Story 1.5 declares these two; only the websocket entry goes."""
        omit = _omit_entries()
        assert "src/config/wsgi.py" in omit
        assert "src/config/asgi.py" in omit

    def test_every_excluded_source_path_still_exists(self):
        """An exclusion naming a deleted file is residue; that is how this one survived."""
        declared = _omit_entries() + _sonar_coverage_exclusions()
        candidates = [entry for entry in declared if entry.startswith("src/") and "*" not in entry]

        assert candidates, "expected at least one literal src/ exclusion to check"
        assert [entry for entry in candidates if not (REPO_ROOT / entry).exists()] == []
