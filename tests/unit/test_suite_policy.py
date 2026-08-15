"""Tests for the policy the test suite itself must obey.

Story 1.2 moved the gate onto PostgreSQL (FR-32). Its AC #2 has two halves. The
first -- "every failure arising from sqlite-permissive behaviour is fixed at its
source" -- was vacuous when the story ran, because PostgreSQL surfaced no
failures at all. The second half is not vacuous, and it is not about that run:
no failure may be *dodged* rather than fixed, ever. That obligation was checked
once, by hand, with grep. This file is what keeps it checked.

The forms banned here are the ones a developer reaches for when a test fails
only in CI: skipping it, marking it `xfail`, or branching on the connection's
vendor so the assertion applies on one backend and not the other. Each converts
a refusal into a warning, which CG-3 forbids, and each would make the gate's
move to PostgreSQL cosmetic.

Matched on the parsed syntax tree rather than by text search. Prose about the
prohibition -- which this module and `tests/integration/test_postgres_schema.py`
both contain -- is then not itself an offence, and `assert connection.vendor ==
expected` (an assertion, the opposite of an evasion) is distinguished from
`if connection.vendor == ...` (a branch), which a grep cannot do.

This is a unit test: it reads repository files and parses them, and opens no
network or database connection.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parents[1]

# Marker attributes that suppress a test outright. `skipif` is included because
# the condition it takes is exactly where "unless we are on sqlite" would go.
BANNED_MARKERS = frozenset({"skip", "skipif", "xfail"})

# Imperative equivalents of the same three, plus `importorskip`, which turns a
# missing driver into a silent pass rather than a failure.
BANNED_CALLS = frozenset({"pytest.skip", "pytest.xfail", "pytest.importorskip"})

# Attribute whose appearance in a branch condition means the test is deciding
# what to assert based on which backend it landed on.
VENDOR_ATTRIBUTE = "vendor"

# Narrowing `django_db` to a subset of configured databases is the same evasion
# expressed as configuration; Task 3 names it alongside the others.
DB_MARKER = "pytest.mark.django_db"


def _dotted_name(node: ast.expr) -> str:
    """Return the dotted source spelling of an attribute or name expression."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _test_modules() -> list[Path]:
    """Return every test module in the suite, unit and integration alike."""
    return sorted(TESTS_ROOT.rglob("test_*.py")) + sorted(TESTS_ROOT.rglob("conftest.py"))


def _evasions(path: Path) -> list[str]:
    """Return every gate evasion in one module, as `line: description` strings."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in BANNED_MARKERS:
            dotted = _dotted_name(node)
            if dotted.startswith("pytest.mark."):
                found.append(f"{node.lineno}: @{dotted}")
        elif isinstance(node, ast.Call):
            dotted = _dotted_name(node.func)
            if dotted in BANNED_CALLS:
                found.append(f"{node.lineno}: {dotted}(...)")
            elif dotted == DB_MARKER and any(keyword.arg == "databases" for keyword in node.keywords):
                found.append(f"{node.lineno}: {dotted}(databases=...)")
        elif isinstance(node, ast.If | ast.IfExp) and _branches_on_vendor(node.test):
            found.append(f"{node.lineno}: branch on the backend vendor")
    return found


def _branches_on_vendor(test: ast.expr) -> bool:
    """Report whether a branch condition inspects the connection's vendor."""
    return any(isinstance(child, ast.Attribute) and child.attr == VENDOR_ATTRIBUTE for child in ast.walk(test))


def test_the_suite_has_test_modules_to_check() -> None:
    """The scan below means nothing if its glob resolves to nothing."""
    modules = _test_modules()
    assert len(modules) > 1, f"expected the suite to be discoverable under {TESTS_ROOT}, found {modules}"


@pytest.mark.parametrize("path", _test_modules(), ids=lambda path: str(path.relative_to(TESTS_ROOT)))
def test_no_test_dodges_the_postgresql_gate(path: Path) -> None:
    """AC #2: a PostgreSQL failure is fixed at its source, never suppressed.

    Parameterized per module so a violation names the file that introduced it
    rather than reporting the whole suite as broken.

    If one of these ever needs to be legitimate -- a genuinely
    platform-specific test, say -- that is a deliberate decision to record in
    the story that makes it, not a line to add quietly while a CI-only failure
    is in front of you. The point of the check is that it is in the way at
    exactly that moment.
    """
    evasions = _evasions(path)
    assert evasions == [], f"{path.relative_to(TESTS_ROOT)} dodges the gate rather than failing on it: {evasions}"
