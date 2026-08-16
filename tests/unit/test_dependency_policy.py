"""Tests for the supply-chain policy declared in pixi.toml."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

# conda-forge builds PyYAML against libyaml. The C loader parses the 270 KB lock
# file in ~16 ms against ~113 ms for the pure-Python one; the fallback keeps the
# test working in an environment built without libyaml. Typed `Any` because the
# two loaders are unrelated classes in the PyYAML stubs, so a conditional import
# is an assignment error under strict mypy.
LockLoader: Any = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

REPO_ROOT = Path(__file__).resolve().parents[2]
PIXI_MANIFEST = REPO_ROOT / "pixi.toml"
PIXI_LOCK = REPO_ROOT / "pixi.lock"
DEVELOPMENT_DOCS = REPO_ROOT / "docs" / "development.md"

# The project's own editable install is not a supply-chain exception -- it is
# how the source tree reaches the environment. Every other entry is.
OWN_PACKAGE = "django-15-factor-base"

# The one permitted package-index source: the repository root, installed
# editable. Anything else under a `pypi:` key in the lock is a third-party
# package resolving from the index, which is what AC #1 closes.
OWN_PACKAGE_SOURCE = "."

# The single audited channel (FR-49), by name.
#
# Deliberately not a URL. This accelerator is used where conda-forge and PyPI are
# served from a private mirror -- JFrog Artifactory, say -- rather than from
# conda.anaconda.org and pypi.org, and a test that pinned those hosts would fail
# there while the supply chain was in fact exactly as declared. What the policy
# is about is channel *identity* and which table a dependency is declared in,
# both of which are host-agnostic, so that is what these assertions read.
CONDA_FORGE = "conda-forge"

# Declarations whose presence is not self-evident from the name, so the reason
# has to be recorded beside them (AC #3; spine "reasoning lives beside the
# configuration it constrains"). Every dependency pinned `"*"` joins this set
# automatically -- see test_non_obvious_declarations_carry_rationale -- so a new
# unpinned dependency cannot land without a reason. The names below are the ones
# that carry a version range and still need explaining: they are here because
# something else needs them, because an optional import turns out to be required
# in practice, or because they are a C library the application would otherwise
# assume the host provides.
RATIONALE_REQUIRED = frozenset(
    {
        "cron-descriptor",
        "django-timezone-field",
        "hatch-vcs",
        "hatchling",
        "hiredis",
        "libpq",
        "opentelemetry-instrumentation-asgi",
        "python-crontab",
    }
)

# A comment that calls a declaration an exception has to say what retires it.
EXCEPTION_WORD = "exception"
EXIT_CONDITION_PHRASE = "exit condition"

# R-1's `django-storages` fitness spike (Story 1.8, FR-50). The package is
# staged in a feature of its own rather than declared as a runtime dependency,
# because FR-50's rule is that fitness is proven *before* a feature is committed
# to and a runtime declaration is that commitment.
SPIKE_PACKAGE = "django-storages"
SPIKE_FEATURE = "spike-storage"
SPIKE_ENVIRONMENT = "spike-storage"
SPIKE_ENVIRONMENT_FEATURES = ["dev", "spike-storage"]
SHARED_SOLVE_GROUP = "default"

# The three verdicts the spike may record, and no fourth, softer one. Ordered
# longest-first because "proven with a stated bound" contains "proven": a reader
# that matched the shorter string first would read a bounded verdict as an
# unbounded one, which is exactly the overstatement CG-2 forbids.
# `test_the_verdict_reader_does_not_read_a_bound_as_full_coverage` pins that.
VERDICTS = ("proven with a stated bound", "proven", "failed")
VERDICT_PREFIX = "verdict:"

# What the spike actually recorded on 2026-08-16. Restated here rather than
# merely parsed, so the manifest cannot be edited to a different verdict without
# this file being edited to agree with it.
RECORDED_VERDICT = "proven with a stated bound"

# The bounded verdict has to say what the bound *is*. These are the words that
# make it a bound rather than a hedge: which leg did not run, and what would
# make it run.
BOUND_PHRASES = ("bound", "round-trip", "spike_storage_round_trip", "aws_s3_endpoint_url")

# The heading the same verdict is repeated under in `docs/development.md`. Two
# copies exist because a reader who never opens `pixi.toml` still has to be able
# to find the verdict, and two copies drift: when the bound is later closed, the
# manifest and this module move together by design while the docs are free to
# keep saying "proven with a stated bound". The reader the docs copy exists for
# is exactly the reader who would then get the stale answer, so the two are
# reconciled -- see `test_the_docs_copy_of_the_verdict_matches_the_manifest`.
DOCS_VERDICT_HEADING = "### Object storage fitness (R-1)"

# The line in the verdict block that names the runtime the verdict is a
# statement about, and the packages it must name. The spike asserts the same
# four against the *installed* distributions, but the spike runs in no automated
# path -- `.github/workflows/ci.yml` pins `environments: dev`, and `pixi run ci`
# never reaches the spike-storage environment. So a Django bump could be solved
# into `pixi.lock` with the gate green while the manifest still certified a
# verdict against a Django nobody re-ran the spike on, and Epic 7 Story 7.5 is
# instructed to act on that verdict. This is the gate-side half: the versions the
# comment names are reconciled against what the lock actually resolved.
TESTED_AGAINST_PREFIX = "tested against:"
VERDICT_VERSION_PACKAGES = frozenset({"django-storages", "django", "python", "boto3"})

# `name version` pairs inside the "Tested against:" listing. Names are matched
# lowercase, so `Django 6.0` and `Python 3.14` are found as readily as
# `django-storages 1.14.6`.
TESTED_AGAINST_ENTRY = re.compile(r"([a-z0-9][a-z0-9._-]*)\s+(\d[\w.]*)")

# `[dependencies]`, `[pypi-dependencies]`, and their per-feature and per-target
# variants. Anything else in pixi.toml -- tasks, environments, activation -- is
# not a dependency declaration and is not scanned.
DEPENDENCY_TABLE = re.compile(
    r"^\[(?:feature\.[A-Za-z0-9._-]+\.)?(?:target\.[A-Za-z0-9._-]+\.)?(?:pypi-)?dependencies\]$"
)
TABLE_HEADER = re.compile(r"^\[.+\]$")
DECLARATION = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)\s*=\s*(?P<value>.+)$")


class UnsupportedSpecifierError(TypeError):
    """A dependency specifier is neither a version string nor a table carrying one."""

    def __init__(self, specifier: object) -> None:
        super().__init__(f"Unsupported dependency specifier: {specifier!r}")


class UnrecognisedConstraintError(ValueError):
    """A version constraint uses an operator this module does not know how to check.

    Raised rather than skipped: an unparsed constraint would leave a dependency
    unverified while the suite still reported success.
    """

    def __init__(self, clause: str, constraint: str) -> None:
        super().__init__(f"Unrecognised version constraint {clause!r} in {constraint!r}")


class UndefinedFeatureError(KeyError):
    """An environment names a feature that ``pixi.toml`` does not define."""

    def __init__(self, feature: str) -> None:
        super().__init__(f"Environment references feature {feature!r}, which pixi.toml does not define")


@dataclass(frozen=True)
class Declaration:
    """One ``name = spec`` line inside a dependency table of ``pixi.toml``.

    Attributes:
        name: The package name to the left of the ``=``.
        table: The table header the declaration sits under, e.g. ``[dependencies]``.
        index: Zero-based index of the line in the manifest.
        trailing_comment: Text after a ``#`` on the declaration's own line, if any.
    """

    name: str
    table: str
    index: int
    trailing_comment: str | None


def _trailing_comment(value: str) -> str | None:
    """Return the comment following a declaration's value, ignoring ``#`` inside quotes.

    Args:
        value: Everything to the right of the ``=`` on a declaration line.

    Returns:
        The comment text with its ``#`` stripped, or None when there is none.
    """
    quote = ""
    for index, char in enumerate(value):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            return value[index + 1 :].strip()
    return None


def _declarations(lines: list[str]) -> list[Declaration]:
    """Return every dependency declaration in the manifest, in file order.

    Args:
        lines: The manifest read as text, one entry per line.

    Returns:
        A Declaration for each ``name = spec`` line inside a dependency table.
    """
    found: list[Declaration] = []
    table = ""
    for index, line in enumerate(lines):
        stripped = line.strip()
        if TABLE_HEADER.match(stripped):
            table = stripped if DEPENDENCY_TABLE.match(stripped) else ""
            continue
        if not table:
            continue
        match = DECLARATION.match(stripped)
        if match is not None:
            found.append(Declaration(match["name"], table, index, _trailing_comment(match["value"])))
    return found


def _rationale(declaration: Declaration, lines: list[str]) -> str | None:
    """Return the reasoning recorded beside a declaration, or None if there is none.

    Two forms count, and both are collected when both are present:

    1. A trailing ``#`` comment on the declaration's own line, e.g.
       ``cron-descriptor = ">=1.4,<2"   # django-celery-beat requires <2.0.0``.
    2. The contiguous ``#`` comment block on the lines *immediately above* the
       declaration.

    Adjacency is the whole rule, and it is deliberately unforgiving. An earlier
    version of this helper stepped backwards over uncommented declarations so
    that one block could head a run of related lines. That credited 22 of the
    manifest's 67 declarations with a comment written about some other package
    -- ``celery`` inherited libpq's note about the PostgreSQL server version,
    ``mypy`` inherited git-cliff's -- and, worse, let a *new* dependency
    inserted anywhere inside such a run pass the AC #3 check having recorded no
    reason at all. Since both dependency tables are alphabetically ordered, that
    is where a new name normally lands, so the guard would have been defeated by
    the ordinary case rather than an exotic one.

    The cost of adjacency is that a block heading several related lines only
    covers the first of them; each of the others states its own reason, however
    briefly. That is the intended reading of the spine's "reasoning lives beside
    the configuration it constrains" -- beside *this* line, not near it.

    Args:
        declaration: The declaration to look up.
        lines: The manifest read as text, one entry per line.

    Returns:
        The recorded reasoning as a single string, or None when nothing is recorded.
    """
    parts: list[str] = []
    if declaration.trailing_comment is not None:
        parts.append(declaration.trailing_comment)
    block: list[str] = []
    cursor = declaration.index - 1
    while cursor >= 0 and lines[cursor].strip().startswith("#"):
        block.append(lines[cursor].strip().lstrip("#").strip())
        cursor -= 1
    parts.extend(reversed(block))
    return " ".join(part for part in parts if part) or None


def _version_spec(specifier: Any) -> str:
    """Return the version constraint from a dependency specifier in either legal form.

    pixi accepts both ``foo = ">=1,<2"`` and the table form
    ``foo = { version = ">=1,<2", channel = "..." }``. Every rule in this module
    reads the constraint through here, so the table form cannot be used to slip
    a wildcard -- or a second channel -- past a check written for the string.

    Args:
        specifier: The right-hand side of a dependency declaration.

    Returns:
        The version constraint. Empty when the table form omits ``version``.

    Raises:
        UnsupportedSpecifierError: If the specifier is neither a string nor a
            table carrying a string ``version``.
    """
    if isinstance(specifier, str):
        return specifier
    if isinstance(specifier, dict):
        version = specifier.get("version", "")
        if not isinstance(version, str):
            raise UnsupportedSpecifierError(specifier)
        return version
    raise UnsupportedSpecifierError(specifier)


def _version_key(version: str) -> tuple[object, ...]:
    """Return a comparable key for a conda version string.

    Splits on ``.`` and separates any trailing letter suffix, so ``0.65b0`` sorts
    below ``0.65`` the way a pre-release should, and ``3.2.10`` sorts above
    ``3.2.9`` rather than lexically below it.

    Args:
        version: A concrete version, e.g. ``3.2.10`` or ``0.65b0``.

    Returns:
        A tuple of (number, suffix) pairs, comparable against another such key.
    """
    key: list[object] = []
    for part in version.split("."):
        match = re.fullmatch(r"(\d*)(.*)", part)
        assert match is not None  # the pattern matches every string
        number, suffix = match.groups()
        # A bare number outranks the same number with a pre-release suffix, so an
        # absent suffix sorts last: "" would otherwise sort first.
        key.append((int(number or 0), suffix or "￿"))
    return tuple(key)


def _satisfies(version: str, specifier: Any) -> bool:
    """Report whether a resolved version satisfies a declared specifier.

    Handles the forms pixi manifests actually use: ``*``, a glob such as
    ``3.14.*``, and a comma-separated list of ``>=`` / ``>`` / ``<=`` / ``<`` /
    ``==`` / ``!=`` constraints.

    Args:
        version: The concrete version the lock resolved.
        specifier: The declared specifier, in string or table form.

    Returns:
        True when the version satisfies every constraint.

    Raises:
        UnrecognisedConstraintError: If a constraint form is not recognised.
    """
    constraint = _version_spec(specifier).strip()
    if constraint in ("", "*"):
        return True
    for clause in (part.strip() for part in constraint.split(",")):
        if clause.endswith(".*"):
            if not (version + ".").startswith(clause[:-1]):
                return False
            continue
        match = re.fullmatch(r"(>=|<=|==|!=|>|<)\s*(.+)", clause)
        if match is None:
            raise UnrecognisedConstraintError(clause, constraint)
        operator, bound = match.groups()
        left, right = _version_key(version), _version_key(bound.strip())
        satisfied = {
            ">=": left >= right,
            "<=": left <= right,
            "==": left == right,
            "!=": left != right,
            ">": left > right,
            "<": left < right,
        }[operator]
        if not satisfied:
            return False
    return True


def _feature_dependencies(manifest: dict[str, Any]) -> dict[str, dict[str | None, dict[str, Any]]]:
    """Map each pixi feature to the conda dependencies it contributes.

    Args:
        manifest: The parsed pixi manifest.

    Returns:
        feature name -> platform (None for every platform) -> {package: specifier}.
    """
    features: dict[str, dict[str | None, dict[str, Any]]] = {}
    default: dict[str | None, dict[str, Any]] = {None: dict(manifest.get("dependencies", {}))}
    for platform, table in manifest.get("target", {}).items():
        if "dependencies" in table:
            default[platform] = dict(table["dependencies"])
    features["default"] = default
    for name, table in manifest.get("feature", {}).items():
        entry: dict[str | None, dict[str, Any]] = {}
        if "dependencies" in table:
            entry[None] = dict(table["dependencies"])
        for platform, sub_table in table.get("target", {}).items():
            if "dependencies" in sub_table:
                entry[platform] = dict(sub_table["dependencies"])
        features[name] = entry
    return features


def _environment_features(manifest: dict[str, Any]) -> dict[str, list[str]]:
    """Map each declared environment to the features it is built from.

    The `default` feature is implicit in every environment. Read from the
    manifest rather than hard-coded, so the six-environment matrix Epic 8
    introduces is covered without touching these tests (AD-3).

    Args:
        manifest: The parsed pixi manifest.

    Returns:
        environment name -> feature names, `default` first.
    """
    environments: dict[str, list[str]] = {}
    for name, spec in manifest.get("environments", {}).items():
        declared = list(spec) if isinstance(spec, list) else list(spec.get("features", []))
        environments[name] = ["default", *declared]
    return environments


def _conda_package(url: str) -> tuple[str, str]:
    """Split a conda artifact URL into its package name and resolved version.

    The lock records conda packages by URL alone; the name and version are the
    filename's own fields, so `redis-py-8.1.0-pyhd8ed1ab_0.conda` is the package
    `redis-py` at `8.1.0`, exactly as `pixi.toml` spells it.

    Args:
        url: The artifact URL from a lock entry.

    Returns:
        A (name, version) pair.

    Raises:
        ValueError: If the filename is not `name-version-build` -- better to
            fail loudly than to skip a package the assertions should cover.
    """
    stem = url.rsplit("/", 1)[-1]
    for suffix in (".conda", ".tar.bz2"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    name, version, _build = stem.rsplit("-", 2)
    return name, version


def _resolved_packages(lock: dict[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    """Map every environment and platform in the lock to its resolved conda packages.

    Args:
        lock: The parsed lock file.

    Returns:
        environment -> platform -> {package name: resolved version}.
    """
    resolved: dict[str, dict[str, dict[str, str]]] = {}
    for name, environment in lock["environments"].items():
        resolved[name] = {}
        for platform, entries in environment["packages"].items():
            packages: dict[str, str] = {}
            for entry in entries:
                url = entry.get("conda")
                if url is not None:
                    package, version = _conda_package(url)
                    packages[package] = version
            resolved[name][platform] = packages
    return resolved


def _expected_packages(manifest: dict[str, Any], features: list[str], platform: str) -> dict[str, Any]:
    """Return the conda packages an environment must resolve on one platform.

    Args:
        manifest: The parsed pixi manifest.
        features: The feature names the environment is built from.
        platform: The platform being checked.

    Returns:
        {package: specifier} for every dependency that applies there.
    """
    contributions = _feature_dependencies(manifest)
    expected: dict[str, Any] = {}
    for feature in features:
        if feature not in contributions:
            # A misspelled feature name in [environments] would otherwise drop
            # that feature's whole dependency set from every check silently.
            raise UndefinedFeatureError(feature)
        for scope, specifiers in contributions[feature].items():
            if scope in (None, platform):
                expected.update(specifiers)
    return expected


def _is_conda_forge(url: str) -> bool:
    """Report whether a conda artifact or channel URL serves the audited channel.

    Containment, not a host prefix and not path-segment equality. This
    accelerator is used where conda-forge is fronted by a private mirror, and
    such a mirror neither preserves the host nor necessarily exposes
    ``conda-forge`` as a path segment of its own -- a real one looks like
    ``https://artifactory.example.com/artifactory/api/conda/conda-forge-remote/``.
    What it does preserve is the channel's name somewhere in the URL, so that is
    what is matched. A genuinely different channel does not contain it.

    Args:
        url: A conda artifact URL or a channel URL from the lock.

    Returns:
        True when the URL names the audited channel.
    """
    return CONDA_FORGE in url


def _offending_sources(entry: dict[str, Any], where: str) -> list[str]:
    """Return the sources in one lock entry that are not the audited channel.

    Args:
        entry: A single `packages:` list item from an environment.
        where: Human-readable location, used in the failure message.

    Returns:
        One description per offending source; empty when the entry is clean.
    """
    offenders: list[str] = []
    for kind, location in entry.items():
        if kind == "conda":
            if not _is_conda_forge(location):
                # Report the URL rather than re-parsing it for a package name: a
                # foreign channel need not use conda's name-version-build
                # filename, and _conda_package raises on one that does not, which
                # would replace this assertion's message with a ValueError.
                offenders.append(f"conda package resolves from {location} ({where})")
        elif kind == "pypi":
            if location != OWN_PACKAGE_SOURCE:
                offenders.append(f"package-index entry {location!r} ({where})")
        else:
            offenders.append(f"unrecognised source {kind}={location!r} ({where})")
    return offenders


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    """Return the parsed pixi manifest."""
    with PIXI_MANIFEST.open("rb") as handle:
        parsed: dict[str, Any] = tomllib.load(handle)
    return parsed


@pytest.fixture(scope="module")
def manifest_lines() -> list[str]:
    """Return the manifest as text lines, because tomllib discards the comments AC #3 is about."""
    return PIXI_MANIFEST.read_text(encoding="utf-8").splitlines()


@pytest.fixture(scope="module")
def docs() -> str:
    """Return `docs/development.md` as text, for the second copy of the R-1 verdict."""
    return DEVELOPMENT_DOCS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def lock() -> dict[str, Any]:
    """Return the parsed pixi lock file, read once for the module."""
    with PIXI_LOCK.open("rb") as handle:
        # S506: LockLoader is CSafeLoader, or SafeLoader when libyaml is absent.
        # Both are safe; ruff cannot see that through the getattr above.
        parsed: dict[str, Any] = yaml.load(handle, Loader=LockLoader)  # noqa: S506
    return parsed


def test_manifest_is_present() -> None:
    """The manifest resolves from the test file, so the paths below mean something."""
    assert PIXI_MANIFEST.is_file()


def test_lock_is_present() -> None:
    """The lock resolves too, so a missing one is one named failure rather than several fixture errors."""
    assert PIXI_LOCK.is_file(), (
        f"{PIXI_LOCK} does not exist. Nothing is lock-pinned without it (AC #4); run `pixi install`."
    )


def test_no_third_party_package_index_dependencies(manifest: dict[str, Any]) -> None:
    """conda-forge is the only source of third-party runtime packages.

    A package added to ``[pypi-dependencies]`` is a supply-chain exception. The
    project currently carries none, and this test is what keeps that true: the
    single documented exception, ``django-celery-beat``, was resolved upstream
    and moved to ``[dependencies]``. Adding another should be a deliberate act
    with its reasoning and exit condition recorded, not something that lands
    because it was the quickest way to unblock an install.
    """
    declared = set(manifest.get("pypi-dependencies", {}))
    assert declared == {OWN_PACKAGE}, (
        f"Unexpected package-index dependencies: {sorted(declared - {OWN_PACKAGE})}. "
        "Every third-party package must resolve from conda-forge; see the note "
        "above [pypi-dependencies] in pixi.toml."
    )


def test_own_package_is_an_editable_path_install(manifest: dict[str, Any]) -> None:
    """The one permitted entry points at the source tree, not at a published release."""
    own = manifest["pypi-dependencies"][OWN_PACKAGE]
    assert own == {"path": ".", "editable": True}


def test_celery_beat_resolves_from_conda_forge(manifest: dict[str, Any]) -> None:
    """django-celery-beat is a conda dependency.

    Builds before ``2.9.0 pyhcf101f3_1`` applied upstream's
    ``importlib-metadata<5.0`` cap unconditionally, having dropped the
    ``python_version < "3.8"`` marker, which made it irreconcilable with
    ``opentelemetry-api``. The corrected build removed the cap. The solver
    enforces the floor without help -- an older build cannot satisfy both
    constraints -- so this test asserts only where the package comes from.

    AC #2 has an absence half as well: having moved, it must not reappear in
    ``[pypi-dependencies]`` the next time an install needs unblocking.
    """
    assert "django-celery-beat" in manifest["dependencies"], (
        "django-celery-beat must be declared in [dependencies] so it resolves from conda-forge."
    )
    assert "django-celery-beat" not in manifest.get("pypi-dependencies", {}), (
        "django-celery-beat is back in [pypi-dependencies]. It was the project's one "
        "supply-chain exception and it was retired upstream; re-adding it here needs the "
        "reasoning and an exit condition recorded beside it."
    )


def test_channels_are_conda_forge_only(manifest: dict[str, Any]) -> None:
    """conda-forge is the single audited channel (FR-49).

    A second channel changes what the project trusts, so it fails the gate
    rather than arriving as one word in a list.
    """
    channels = manifest["workspace"]["channels"]
    assert channels == [CONDA_FORGE], (
        f"Unexpected channels: {channels}. Only {CONDA_FORGE!r} may appear in "
        "[workspace] channels; adding another is a supply-chain change."
    )

    # [workspace] is not the only way in. A feature may declare its own channel
    # list, and a single dependency may name one in its table form -- both would
    # add a source while the workspace list still reads conda-forge only.
    feature_channels = sorted(
        f"[feature.{name}] channels = {table['channels']}"
        for name, table in manifest.get("feature", {}).items()
        if table.get("channels", [CONDA_FORGE]) != [CONDA_FORGE]
    )
    assert not feature_channels, (
        f"These features declare their own channels: {feature_channels}. "
        f"Every feature must resolve from {CONDA_FORGE!r} alone."
    )

    per_dependency = sorted(
        f"{name} = {specifier}"
        for scopes in _feature_dependencies(manifest).values()
        for specifiers in scopes.values()
        for name, specifier in specifiers.items()
        if isinstance(specifier, dict) and specifier.get("channel", CONDA_FORGE) != CONDA_FORGE
    )
    assert not per_dependency, (
        f"These dependencies name a channel of their own: {per_dependency}. "
        "A per-dependency channel is a second source and must be declared as a supply-chain exception."
    )


def test_non_obvious_declarations_carry_rationale(manifest: dict[str, Any], manifest_lines: list[str]) -> None:
    """Every declaration whose presence is not obvious records why it is there.

    The required set is ``RATIONALE_REQUIRED`` plus every dependency pinned
    ``"*"``, computed from the manifest rather than listed, so a new unpinned
    dependency joins it on the day it is added.

    A declaration counts as explained when it has a trailing ``#`` comment or a
    ``#`` comment block immediately above it -- see ``_rationale``, which reads
    adjacency strictly so that a new line cannot borrow its neighbour's reason.
    """
    declarations = {declaration.name: declaration for declaration in _declarations(manifest_lines)}
    unpinned = {
        name
        for scopes in _feature_dependencies(manifest).values()
        for specifiers in scopes.values()
        for name, specifier in specifiers.items()
        if _version_spec(specifier).strip() in ("", "*")
    }
    required = RATIONALE_REQUIRED | unpinned

    undeclared = sorted(name for name in required if name not in declarations)
    assert not undeclared, (
        f"RATIONALE_REQUIRED names packages pixi.toml no longer declares: {undeclared}. "
        "Remove them from the set in this module in the same change that removes the dependency."
    )

    unexplained = sorted(name for name in required if _rationale(declarations[name], manifest_lines) is None)
    assert not unexplained, (
        f"These declarations record no reason for being there: {unexplained}. "
        "Write the reason as a `#` comment above the declaration, or on the same "
        "line after the version specifier, in pixi.toml."
    )


def test_declared_exceptions_carry_an_exit_condition(manifest_lines: list[str]) -> None:
    """A supply-chain exception also documents what retires it.

    An exception is identified two ways, because prose alone is too easy to
    route around -- a carve-out worded "temporary, no conda-forge build yet"
    never says "exception" and would escape a purely textual rule:

    1. **By location.** Any third-party key under a ``[pypi-dependencies]``
       table is an exception by definition; that is what the policy comment
       above the table in ``pixi.toml`` says. This is the load-bearing half.
    2. **By prose.** Any declaration whose rationale calls itself an exception.

    Neither fires today -- the project carries zero exceptions -- so the guard
    below fails if the parser stops finding comments at all, which is what would
    otherwise let this pass for the wrong reason.
    """
    declarations = _declarations(manifest_lines)
    documented = {
        declaration.name: rationale
        for declaration in declarations
        if (rationale := _rationale(declaration, manifest_lines)) is not None
    }
    assert documented, (
        "No rationale comment was found beside any declaration in pixi.toml. "
        "That is a parser failure in this module, not a manifest without comments."
    )

    exceptions = {
        declaration.name
        for declaration in declarations
        if declaration.table.endswith("pypi-dependencies]") and declaration.name != OWN_PACKAGE
    }
    exceptions |= {name for name, rationale in documented.items() if EXCEPTION_WORD in rationale.lower()}

    offenders = sorted(name for name in exceptions if EXIT_CONDITION_PHRASE not in documented.get(name, "").lower())
    assert not offenders, (
        f"These declarations are supply-chain exceptions but record no exit condition: {offenders}. "
        f"Say what retires the exception, using the words {EXIT_CONDITION_PHRASE!r}, in a comment beside it."
    )


def test_lock_file_resolves_every_declared_dependency(manifest: dict[str, Any], lock: dict[str, Any]) -> None:
    """Every declared dependency is pinned to a concrete version in pixi.lock (NFR-5).

    Nothing is left for the solver to decide at install time, so the same lock
    file produces the same environment. Platform-scoped declarations are checked
    only on the platform that declares them; feature dependencies only in the
    environments that include the feature.

    The resolved version must also *satisfy* the declared specifier, not merely
    exist. Presence alone would let the manifest be edited without re-solving --
    widening `libpq` to `>=18,<19` against a lock holding 17.11 is exactly the
    edit the comment beside it invites a future contributor to make -- leaving
    the manifest and the lock disagreeing while this test still passed.
    """
    resolved = _resolved_packages(lock)
    assert resolved, "pixi.lock declares no environments; it has not been solved."
    declared_platforms = set(manifest["workspace"]["platforms"])

    unresolved: list[str] = []
    stale: list[str] = []
    for environment, features in _environment_features(manifest).items():
        assert environment in resolved, (
            f"Environment {environment!r} is declared in pixi.toml but absent from pixi.lock. Run `pixi install`."
        )
        missing_platforms = sorted(declared_platforms - set(resolved[environment]))
        assert not missing_platforms, (
            f"Environment {environment!r} resolves no packages for {missing_platforms} in pixi.lock, "
            "though pixi.toml declares those platforms. Run `pixi install`."
        )
        for platform, packages in resolved[environment].items():
            assert packages, f"Environment {environment!r} resolves no packages at all on {platform!r} in pixi.lock."
            for package, specifier in _expected_packages(manifest, features, platform).items():
                where = f"(environment {environment}, platform {platform})"
                version = packages.get(package)
                if not version:
                    unresolved.append(f"{package} {where}")
                elif not _satisfies(version, specifier):
                    stale.append(f"{package} declared {_version_spec(specifier)!r}, locked {version} {where}")

    assert not unresolved, (
        f"These declared dependencies do not resolve to a version in pixi.lock: {sorted(set(unresolved))}. "
        "Re-solve the environment with `pixi install` rather than editing pixi.lock."
    )
    assert not stale, (
        f"The lock disagrees with the manifest for: {sorted(set(stale))}. "
        "Re-solve with `pixi install` so the lock matches what pixi.toml declares."
    )


def test_lock_file_has_no_non_conda_forge_source(lock: dict[str, Any]) -> None:
    """Nothing in the lock resolves from anywhere but conda-forge, bar the editable self-install.

    This is AC #1 asserted against what was actually solved rather than against
    what was declared: a package reaching the environment from the index shows up
    here even if `[pypi-dependencies]` looks clean.

    Channels are matched by name, not by host, so a private mirror serving
    conda-forge passes and a genuinely different channel does not. The package
    index is deliberately not policed by URL for the same reason -- the invariant
    that matters is that nothing but the editable self-install resolves from an
    index at all, which the `pypi:` check below asserts directly.
    """
    offenders: list[str] = []
    for name, environment in lock["environments"].items():
        offenders.extend(
            f"channel {channel.get('url', '')!r} (environment {name})"
            for channel in environment.get("channels", [])
            if not _is_conda_forge(channel.get("url", ""))
        )
        for platform, entries in environment["packages"].items():
            for entry in entries:
                offenders.extend(_offending_sources(entry, f"environment {name}, platform {platform}"))

    index_packages = {package.get("name") for package in lock["packages"] if "pypi" in package}
    offenders.extend(
        f"package-index package {package!r} in the lock's package list"
        for package in sorted(index_packages - {OWN_PACKAGE})
    )

    assert not offenders, (
        f"These lock entries do not come from conda-forge: {sorted(set(offenders))}. "
        f"Only {OWN_PACKAGE!r} may resolve from the package index, and only as the editable path install."
    )


def test_libpq_is_declared_rather_than_assumed(manifest: dict[str, Any], lock: dict[str, Any]) -> None:
    """The PostgreSQL client library is a declared conda package, not a host package (AC #4).

    "Nothing relies on a system package" is asserted structurally: `libpq` is the
    C library the application actually needs, and it is declared and locked like
    any other dependency instead of being assumed present on the machine. The
    host OS is deliberately not introspected -- that assertion would not hold
    across the three-platform matrix.
    """
    specifier = manifest["dependencies"].get("libpq")
    assert specifier is not None, (
        "libpq is not declared in [dependencies]. psycopg links against it, so leaving it "
        "out makes the environment depend on whatever the host happens to provide."
    )
    constraint = _version_spec(specifier).strip()
    assert constraint not in ("", "*"), (
        f"libpq is declared as {specifier!r}; it must carry a version range, not a wildcard. "
        "The range is what keeps it paired with the psycopg build that links the same libpq major."
    )

    missing = sorted(
        f"environment {environment}, platform {platform}"
        for environment, platforms in _resolved_packages(lock).items()
        for platform, packages in platforms.items()
        if "libpq" not in packages
    )
    assert not missing, f"libpq is not resolved in pixi.lock for: {missing}."


def _recorded_verdict(rationale: str) -> str | None:
    """Return the R-1 verdict a rationale records, or None when it records none.

    Matched against the closed set of three, longest first, so that "proven with
    a stated bound" is never read as the unbounded "proven".

    Args:
        rationale: The comment text recorded beside a declaration.

    Returns:
        The verdict as one of `VERDICTS`, or None.
    """
    lowered = " ".join(rationale.lower().split())
    for verdict in VERDICTS:
        if f"{VERDICT_PREFIX} {verdict}" in lowered:
            return verdict
    return None


def _tested_against(rationale: str) -> dict[str, str]:
    """Return the ``name -> version`` pairs the verdict's "Tested against:" line names.

    Read out of the comment rather than restated in this module, because the
    comment is what a reader of `pixi.toml` believes and therefore what has to be
    reconciled against the lock. Everything after the first ``--`` is prose about
    the list and is not scanned.

    Args:
        rationale: The comment text recorded beside the declaration.

    Returns:
        Lowercased package name to the version the verdict claims, empty when the
        rationale carries no such line.
    """
    collapsed = " ".join(rationale.lower().split())
    _head, separator, tail = collapsed.partition(TESTED_AGAINST_PREFIX)
    if not separator:
        return {}
    return dict(TESTED_AGAINST_ENTRY.findall(tail.split("--", 1)[0]))


def _is_same_release_line(locked: str, named: str) -> bool:
    """Report whether a locked version is the one a verdict names, at the verdict's precision.

    A verdict says "Django 6.0", and the lock says `6.0.8`. That is the same
    release line and the spike's conclusions carry; `6.1.0` is not, and they do
    not. Comparison is therefore component-prefixed rather than string-prefixed,
    so `3.14` does not match `3.140`.

    Args:
        locked: The concrete version `pixi.lock` resolved.
        named: The version the verdict names, at whatever precision it names it.

    Returns:
        True when the locked version lies inside the named release line.
    """
    return locked == named or locked.startswith(f"{named}.")


def _verdict_drift(named: dict[str, str], platforms: dict[str, dict[str, str]]) -> list[str]:
    """Return every place the lock has moved off a version the verdict names.

    Split out from its test so that it can be exercised against a synthetic lock:
    `pixi run` re-solves and rewrites `pixi.lock` before a task starts, so a
    mutated lock file cannot survive long enough for a test to read it, and this
    rule would otherwise be unverifiable by mutation.

    Args:
        named: Package name to the version the verdict claims.
        platforms: platform -> {package: resolved version}, for one environment.

    Returns:
        One description per drift, empty when the lock still holds the verdict's
        runtime.
    """
    drifted: list[str] = []
    for platform, packages in sorted(platforms.items()):
        for package, version in sorted(named.items()):
            locked = packages.get(package)
            if locked is None:
                drifted.append(f"{package} is named by the verdict but resolves nowhere on {platform}")
            elif not _is_same_release_line(locked, version):
                drifted.append(f"{package}: verdict says {version}, lock resolves {locked} on {platform}")
    return drifted


def _cross_environment_divergences(resolved: dict[str, dict[str, dict[str, str]]]) -> list[str]:
    """Return every package resolving to more than one version across environments.

    Grouped per platform, because two platforms resolving different versions of
    the same package is ordinary and not what the shared solve-group is about.

    Split out from its test for the same reason as `_verdict_drift`: the lock
    cannot be mutated in place under `pixi run`.

    Args:
        resolved: environment -> platform -> {package: resolved version}.

    Returns:
        One description per divergence, sorted; empty when every shared package
        agrees.
    """
    versions: dict[tuple[str, str], dict[str, str]] = {}
    for environment, platforms in resolved.items():
        for platform, packages in platforms.items():
            for package, version in packages.items():
                versions.setdefault((platform, package), {})[environment] = version
    return sorted(
        f"{package} on {platform}: {found}"
        for (platform, package), found in versions.items()
        if len(set(found.values())) > 1
    )


def _docs_section(text: str, heading: str) -> str:
    """Return the body of one markdown section, up to the next heading of the same level or higher.

    Args:
        text: The whole document.
        heading: The exact heading line to start from.

    Returns:
        The section body, empty when the heading is absent.
    """
    lines = text.splitlines()
    if heading not in lines:
        return ""
    body: list[str] = []
    for line in lines[lines.index(heading) + 1 :]:
        if re.match(r"^#{1,3} ", line):
            break
        body.append(line)
    return " ".join(body)


def test_the_storage_spike_is_staged_rather_than_committed_to(manifest: dict[str, Any]) -> None:
    """R-1: `django-storages` is declared in the spike feature and nowhere else.

    This assertion encodes the recorded verdict, which is **proven with a stated
    bound** -- not *failed*. Two consequences, and both are asserted:

    * AC #3's branch is *not* taken. A failed verdict would have added a
      time-boxed `[pypi-dependencies]` entry with its exit condition beside it,
      pending a conda-forge feedstock push. The package resolves from
      conda-forge as it stands, so no such entry exists and none may appear.
    * AC #2's branch is taken, but not by this story. A passing verdict lets
      Epic 7 Story 7.5 build object storage on the channel build; it does not by
      itself move the declaration into `[dependencies]`. Until Story 7.5 does
      that, a `django-storages` in the runtime set is a feature committed to
      without the feature existing, which is what FR-50 exists to prevent.

    If Story 7.5 moves it, this test moves with it -- it becomes an assertion
    that the package sits in the `storage` feature. It does not get deleted.

    "Nowhere else" is checked against **every** dependency table, not the two at
    the top level. `[feature.dev.dependencies]` is a declaration site exactly as
    real as `[dependencies]`, and putting the package there would place it in the
    environment the entire product test suite runs in -- a commitment in all but
    name, and one the earlier two-table form of this test passed cleanly.
    `DEPENDENCY_TABLE` above already knows the per-feature and per-target
    variants, so the scan reads every table the manifest can declare into.
    """
    spike_dependencies = manifest["feature"][SPIKE_FEATURE]["dependencies"]
    assert SPIKE_PACKAGE in spike_dependencies, (
        f"{SPIKE_PACKAGE} must be declared in [feature.{SPIKE_FEATURE}.dependencies]; "
        "that declaration is what R-1's spike runs against."
    )
    assert SPIKE_PACKAGE not in manifest["dependencies"], (
        f"{SPIKE_PACKAGE} is in [dependencies]. The recorded verdict permits Epic 7 Story 7.5 to build "
        "object storage; moving the declaration into the runtime set is that story's act, not this one's."
    )
    assert SPIKE_PACKAGE not in manifest.get("pypi-dependencies", {}), (
        f"{SPIKE_PACKAGE} is in [pypi-dependencies]. R-1's escalation permits a time-boxed package-index "
        "exception only on a *failed* verdict, and the recorded verdict is not failed."
    )


def test_the_storage_spike_is_declared_in_no_other_dependency_table(manifest_lines: list[str]) -> None:
    """R-1: the staging is only staging if `django-storages` is declared in exactly one table.

    The sibling above checks the two tables a commitment would most obviously use.
    This checks all of them -- `[feature.<name>.dependencies]`,
    `[feature.<name>.pypi-dependencies]` and the `[target.<platform>....]`
    variants -- because the point of FR-50's staging is that the package reaches
    one deliberately isolated environment and no other. A `django-storages` in
    `[feature.dev.dependencies]` would reach the environment `pixi run ci` uses,
    which is the commitment this story exists to withhold.
    """
    tables = sorted(
        declaration.table for declaration in _declarations(manifest_lines) if declaration.name == SPIKE_PACKAGE
    )
    expected = [f"[feature.{SPIKE_FEATURE}.dependencies]"]
    assert tables == expected, (
        f"{SPIKE_PACKAGE} is declared in {tables}; it may be declared in {expected} and nowhere else until "
        "Epic 7 Story 7.5 moves it into the `storage` feature. Any other table puts the package into an "
        "environment the spike's verdict says nothing about."
    )


def test_the_spike_environment_shares_the_solve_group(manifest: dict[str, Any]) -> None:
    """AD-3: the spike must exercise the Django the product ships, not one of its own.

    Without the shared solve-group the spike environment resolves independently
    and could pick a different Django, at which point the verdict is a statement
    about a runtime nothing runs. That would be a verdict that looks like
    evidence and is not.
    """
    environment = manifest["environments"][SPIKE_ENVIRONMENT]
    assert environment.get("solve-group") == SHARED_SOLVE_GROUP, (
        f"environment {SPIKE_ENVIRONMENT!r} declares solve-group {environment.get('solve-group')!r}, "
        f"not {SHARED_SOLVE_GROUP!r}; it would then test a different Django from the one the product ships."
    )
    assert environment.get("features") == SPIKE_ENVIRONMENT_FEATURES, (
        f"environment {SPIKE_ENVIRONMENT!r} is built from {environment.get('features')}, not "
        f"{SPIKE_ENVIRONMENT_FEATURES}; it needs `dev` for pytest and `{SPIKE_FEATURE}` for the package."
    )


def test_the_spike_verdict_is_recorded_beside_the_declaration(manifest_lines: list[str]) -> None:
    """AC #1: "the result is recorded where the dependency is declared".

    The record is a comment block beside the declaration, so it is read as text
    -- `tomllib` discards exactly the thing this asserts. Three properties, and
    each of them is a way the record could be present and useless:

    1. There is a verdict at all, and it is one of the closed set of three. A
       fourth, softer outcome ("mostly works", "no blockers found") is what a
       spike degrades into when nobody is holding it to a vocabulary.
    2. It is the verdict this suite records. The manifest and this file have to
       be edited together, so a verdict cannot be upgraded in a comment alone.
    3. A bounded verdict names its bound. "Proven with a stated bound" without
       the stated bound is just "proven" with a disclaimer, which is the
       silently narrowed claim CG-2 calls worse than a bounded one.
    4. The staging says what retires it. `[feature.spike-storage]` is temporary
       by construction, and Task 1 required its reasoning and exit condition to
       be recorded beside the declaration -- which means *below* the table
       header, where `_rationale` can reach it. Written above the header they
       were invisible to every assertion in this file and could have been
       deleted with the suite green.
    """
    declarations = {declaration.name: declaration for declaration in _declarations(manifest_lines)}
    assert SPIKE_PACKAGE in declarations, f"{SPIKE_PACKAGE} is not declared in pixi.toml at all"

    rationale = _rationale(declarations[SPIKE_PACKAGE], manifest_lines)
    assert rationale is not None, (
        f"no comment block sits beside the {SPIKE_PACKAGE} declaration. AC #1 requires the spike's verdict "
        "to be recorded where the dependency is declared, and `_rationale` reads adjacency strictly -- the "
        "block must be on the lines immediately above the declaration, below the table header."
    )

    verdict = _recorded_verdict(rationale)
    assert verdict is not None, (
        f"the comment beside {SPIKE_PACKAGE} records no verdict. Write `Verdict: <one of {list(VERDICTS)}>`; "
        "a fourth, softer outcome is not available."
    )
    assert verdict == RECORDED_VERDICT, (
        f"pixi.toml records the verdict {verdict!r} and this suite records {RECORDED_VERDICT!r}. "
        "Re-run `pixi run spike-storage` and change both together, or neither."
    )

    lowered = rationale.lower()
    missing = sorted(phrase for phrase in BOUND_PHRASES if phrase not in lowered)
    assert not missing, (
        f"the verdict is bounded but does not state the bound: {missing} appear nowhere beside the "
        f"{SPIKE_PACKAGE} declaration. Say which leg did not run and what would make it run."
    )

    assert EXIT_CONDITION_PHRASE in lowered, (
        f"the comment beside {SPIKE_PACKAGE} records no exit condition. [feature.{SPIKE_FEATURE}] is "
        "temporary staging, not a home; say what retires it, below the table header where this reader can "
        f"see it, using the words {EXIT_CONDITION_PHRASE!r}."
    )


def test_the_recorded_verdict_names_the_versions_the_lock_resolves(
    manifest_lines: list[str],
    lock: dict[str, Any],
) -> None:
    """A verdict is a statement about specific versions, so the lock must still hold them.

    The spike asserts the same four versions against the installed distributions,
    but the spike runs in no automated path: `.github/workflows/ci.yml` pins
    `environments: dev`, and nothing in `pixi run ci` reaches the `spike-storage`
    environment. Meanwhile `django = ">=6.0,<7"` admits 6.1 on a re-solve and
    `boto3` is transitive and floats freely, so the whole of this could happen
    with a green gate: someone bumps Django, `pixi install` re-solves, and
    `pixi.toml` goes on certifying a verdict against a runtime nobody re-spiked
    -- which Epic 7 Story 7.5 is instructed to act on.

    This is what closes that. The versions are read out of the comment a reader
    actually believes and reconciled, per platform, against what `pixi.lock`
    resolved for the environment the spike runs in. Matching is at the verdict's
    own precision: "Django 6.0" is satisfied by a locked `6.0.8` and not by
    `6.1.0`.
    """
    declarations = {declaration.name: declaration for declaration in _declarations(manifest_lines)}
    rationale = _rationale(declarations[SPIKE_PACKAGE], manifest_lines)
    assert rationale is not None, f"no comment block sits beside the {SPIKE_PACKAGE} declaration"

    named = _tested_against(rationale)
    assert set(named) == VERDICT_VERSION_PACKAGES, (
        f"the verdict's 'Tested against:' line names {sorted(named)}, and the versions a verdict about "
        f"{SPIKE_PACKAGE} has to pin are {sorted(VERDICT_VERSION_PACKAGES)}. A name dropped from that line "
        "is a version this test stops reconciling against the lock."
    )

    resolved = _resolved_packages(lock)
    assert SPIKE_ENVIRONMENT in resolved, (
        f"environment {SPIKE_ENVIRONMENT!r} is absent from pixi.lock, so the verdict's versions cannot be "
        "reconciled against anything. Run `pixi install`."
    )

    drifted = _verdict_drift(named, resolved[SPIKE_ENVIRONMENT])
    assert not drifted, (
        f"the lock has moved off the runtime the R-1 verdict is a statement about: {sorted(set(drifted))}. "
        "Re-run `pixi run spike-storage` against the new versions and re-record the verdict in pixi.toml "
        "and docs/development.md; a verdict is not inherited across a version bump."
    )


def test_every_shared_package_resolves_to_one_version_across_environments(lock: dict[str, Any]) -> None:
    """AD-3's shared solve-group, asserted against what was solved rather than what was declared.

    `test_the_spike_environment_shares_the_solve_group` reads the manifest, and
    its docstring names the stake: without the shared group the spike resolves
    its own Django and the verdict is a statement about a runtime nothing runs.
    Nothing checked that the lock actually delivered it.
    `test_lock_file_resolves_every_declared_dependency` cannot -- it checks each
    environment against the declared *range* independently, so `django 6.0.8` in
    `dev` and `6.1.0` in `spike-storage` would both satisfy `>=6.0,<7` and both
    pass.

    Grouped per platform, because two platforms resolving different builds of the
    same package is ordinary and not what this is about.
    """
    resolved = _resolved_packages(lock)
    assert resolved, "pixi.lock declares no environments; it has not been solved."

    divergent = _cross_environment_divergences(resolved)
    assert not divergent, (
        f"these packages resolve to different versions in different environments: {divergent}. "
        'Every environment declares `solve-group = "default"` so that the environments a spike or a '
        "matrix leg runs in exercise the versions the product ships; re-solve with `pixi install`."
    )


def test_the_docs_copy_of_the_verdict_matches_the_manifest(manifest_lines: list[str], docs: str) -> None:
    """The verdict is recorded twice, so the two copies are reconciled.

    `docs/development.md` carries the verdict for "a reader who never opens
    `pixi.toml`" -- which is exactly the reader a stale copy misleads. When the
    bound is later closed, `pixi.toml` and this module move together by design,
    and nothing would have made the docs move with them.
    """
    declarations = {declaration.name: declaration for declaration in _declarations(manifest_lines)}
    rationale = _rationale(declarations[SPIKE_PACKAGE], manifest_lines)
    assert rationale is not None, f"no comment block sits beside the {SPIKE_PACKAGE} declaration"

    section = _docs_section(docs, DOCS_VERDICT_HEADING)
    assert section, (
        f"{DEVELOPMENT_DOCS.name} has no {DOCS_VERDICT_HEADING!r} section. Task 3 requires the verdict to be "
        "readable without opening pixi.toml."
    )

    documented = _recorded_verdict(section)
    assert documented == _recorded_verdict(rationale) == RECORDED_VERDICT, (
        f"{DEVELOPMENT_DOCS.name} records the verdict {documented!r}, pixi.toml records "
        f"{_recorded_verdict(rationale)!r} and this suite records {RECORDED_VERDICT!r}. All three move "
        "together or none of them do."
    )

    lowered = section.lower()
    missing = sorted(phrase for phrase in BOUND_PHRASES if phrase not in lowered)
    assert not missing, (
        f"the docs copy of the verdict is bounded but does not state the bound: {missing} appear nowhere "
        f"under {DOCS_VERDICT_HEADING!r}. The bound has to survive the second copy, not only the first."
    )


# The rules above are only as good as the helpers underneath them, and those
# helpers are not covered by anything else -- `--cov=src` does not measure this
# module. The two tests below pin the properties whose absence would let a rule
# pass while enforcing nothing.


def test_rationale_does_not_borrow_a_neighbours_comment() -> None:
    """An uncommented declaration is unexplained wherever it sits in the table.

    This is the regression test for the rule this module originally shipped
    with, which walked backwards over uncommented declarations and so credited a
    new dependency with whichever comment happened to head its run.
    """
    manifest_text = [
        "[dependencies]",
        "# libpq is held at 17 to match the server the gate runs against.",
        'libpq = ">=17,<18"',
        'appended = "*"',
        'trailing = "*"   # explained on its own line',
        "# A block of its own.",
        'blocked = "*"',
    ]
    found = {declaration.name: declaration for declaration in _declarations(manifest_text)}

    assert _rationale(found["libpq"], manifest_text) is not None
    assert _rationale(found["trailing"], manifest_text) is not None
    assert _rationale(found["blocked"], manifest_text) is not None
    assert _rationale(found["appended"], manifest_text) is None, (
        "A declaration with no comment of its own was credited with a neighbour's rationale. "
        "The backward walk must stop at the first line that is not a comment."
    )


def test_channel_is_identified_by_name_not_by_host() -> None:
    """conda-forge served from a private mirror is still conda-forge.

    Enterprise deployments front the channel with a mirror such as JFrog
    Artifactory. An assertion pinned to ``conda.anaconda.org`` would report a
    supply-chain violation where there is none; so would one requiring
    ``conda-forge`` to be a path segment of its own, since a mirror is free to
    name the repository ``conda-forge-remote``. A genuinely different channel
    still fails, which is the property that has to survive.
    """
    artifact = "/linux-64/redis-py-8.1.0-pyhd8ed1ab_0.conda"
    upstream = f"https://conda.anaconda.org/conda-forge{artifact}"
    mirrored = f"https://artifactory.example.com/artifactory/api/conda/conda-forge-remote{artifact}"
    foreign = f"https://conda.anaconda.org/bioconda{artifact}"

    assert _is_conda_forge(upstream)
    assert _is_conda_forge(mirrored)
    assert _is_conda_forge("https://artifactory.example.com/artifactory/api/conda/conda-forge-remote/")
    assert not _is_conda_forge(foreign)

    assert not _offending_sources({"conda": mirrored}, "mirror")
    assert _offending_sources({"conda": foreign}, "foreign")


def test_satisfies_compares_versions_rather_than_strings() -> None:
    """A locked version is checked against the declared range, numerically.

    Without the numeric comparison, `3.2.10` reads as older than `3.2.9` and the
    manifest could drift from the lock unnoticed.
    """
    assert _satisfies("17.11", ">=17,<18")
    assert not _satisfies("18.4", ">=17,<18")
    assert _satisfies("3.2.10", ">=3.2.4,<3.2.11")
    assert not _satisfies("3.2.11", ">=3.2.4,<3.2.11")
    assert _satisfies("3.14.2", "3.14.*")
    assert not _satisfies("3.13.9", "3.14.*")
    assert _satisfies("0.66b0", ">=0.65b0")
    assert not _satisfies("0.64b0", ">=0.65b0")
    assert _satisfies("1.2.3", "*")
    assert _satisfies("1.2.3", {"version": "*"})

    with pytest.raises(UnrecognisedConstraintError, match="Unrecognised version constraint"):
        _satisfies("1.2.3", "~=1.2")


def test_the_verdict_reader_does_not_read_a_bound_as_full_coverage() -> None:
    """A bounded verdict must not be readable as an unbounded one.

    "proven with a stated bound" contains "proven". A reader that scanned the
    shorter string first would report the strongest of the three verdicts for a
    record that says the opposite -- and it would do it silently, on a green
    suite, which is the exact failure mode CG-2 names. The ordering of `VERDICTS`
    is what prevents it, and this is what holds the ordering.
    """
    assert _recorded_verdict("Verdict: proven with a stated bound.") == "proven with a stated bound"
    assert _recorded_verdict("Verdict: proven.") == "proven"
    assert _recorded_verdict("Verdict: failed.") == "failed"
    assert _recorded_verdict("# Verdict:  proven  with a stated  bound") == "proven with a stated bound"
    assert _recorded_verdict("the spike has proven nothing yet") is None
    assert _recorded_verdict("Verdict: mostly fine") is None


def test_the_tested_against_reader_finds_every_named_version() -> None:
    """The versions reconciled against the lock are parsed, so the parser is pinned.

    A parser that silently returned fewer pairs than the comment names would
    reduce `test_the_recorded_verdict_names_the_versions_the_lock_resolves` to
    checking whatever it happened to find -- and the set assertion there is what
    stops that, so this holds the parser up from underneath.
    """
    rationale = (
        "Verdict: proven with a stated bound. Tested against: django-storages 1.14.6, Django 6.0, "
        "Python 3.14, boto3 1.43.65 -- the versions the spine's Stack table names, read back from the "
        "installed distribution rather than assumed. Bound: the round-trip leg did not run."
    )
    assert _tested_against(rationale) == {
        "django-storages": "1.14.6",
        "django": "6.0",
        "python": "3.14",
        "boto3": "1.43.65",
    }
    assert _tested_against("Verdict: proven. No versions recorded.") == {}


def test_a_named_release_line_does_not_match_a_neighbouring_one() -> None:
    """ "Django 6.0" covers 6.0.8 and does not cover 6.1.0 or 6.01.

    Component-prefixed rather than string-prefixed: a plain `startswith` would
    read `3.140` as inside `3.14`, and the whole point of the reconciliation is
    that a version bump invalidates the verdict rather than sliding under it.
    """
    assert _is_same_release_line("6.0.8", "6.0")
    assert _is_same_release_line("6.0", "6.0")
    assert _is_same_release_line("3.14.6", "3.14")
    assert not _is_same_release_line("6.1.0", "6.0")
    assert not _is_same_release_line("3.140.1", "3.14")
    assert not _is_same_release_line("1.14.6", "1.14.7")


def test_a_lock_that_moved_off_the_verdicts_runtime_is_reported() -> None:
    """The verdict-versus-lock rule is verified against a synthetic lock, not a mutated one.

    It cannot be verified against a mutated `pixi.lock`: `pixi run` re-solves and
    rewrites the lock before a task starts, so an edited one is restored before
    pytest ever opens it. The rule is therefore exercised here, on data shaped
    exactly as `_resolved_packages` returns it.

    Three cases, because each is a different way a verdict outlives its runtime:
    the lock agrees, the lock has moved to a neighbouring release line, and the
    package has left the environment altogether.
    """
    named = {"django": "6.0", "python": "3.14", "django-storages": "1.14.6"}
    agreeing = {"linux-64": {"django": "6.0.8", "python": "3.14.6", "django-storages": "1.14.6"}}
    assert _verdict_drift(named, agreeing) == []

    bumped = {"linux-64": {"django": "6.1.0", "python": "3.14.6", "django-storages": "1.14.6"}}
    assert _verdict_drift(named, bumped) == ["django: verdict says 6.0, lock resolves 6.1.0 on linux-64"]

    absent = {"linux-64": {"django": "6.0.8", "python": "3.14.6"}}
    assert _verdict_drift(named, absent) == ["django-storages is named by the verdict but resolves nowhere on linux-64"]


def test_one_environment_resolving_its_own_django_is_reported() -> None:
    """The shared-solve-group rule, verified the same way and for the same reason.

    This is the failure AD-3's solve-group exists to prevent, and the one
    `test_lock_file_resolves_every_declared_dependency` cannot see: both versions
    below satisfy `django = ">=6.0,<7"`, so checking each environment against the
    declared range independently passes while the spike proves nothing about the
    Django the product ships. A per-platform difference is left alone, because
    that is ordinary.
    """
    agreeing = {
        "dev": {"linux-64": {"django": "6.0.8"}},
        "spike-storage": {"linux-64": {"django": "6.0.8"}},
    }
    assert _cross_environment_divergences(agreeing) == []

    divergent = {
        "dev": {"linux-64": {"django": "6.0.8"}},
        "spike-storage": {"linux-64": {"django": "6.1.0"}},
    }
    assert _cross_environment_divergences(divergent) == [
        "django on linux-64: {'dev': '6.0.8', 'spike-storage': '6.1.0'}"
    ]

    per_platform = {
        "dev": {"linux-64": {"libpq": "17.11"}, "win-64": {"libpq": "17.10"}},
        "spike-storage": {"linux-64": {"libpq": "17.11"}, "win-64": {"libpq": "17.10"}},
    }
    assert _cross_environment_divergences(per_platform) == []


def test_a_docs_section_stops_at_the_next_heading() -> None:
    """The docs copy of the verdict is read by section, so the section boundary is pinned.

    A reader that ran past the next heading would find the word "proven"
    somewhere later in the file and report a verdict the section does not carry.
    """
    document = (
        "## Supply chain\n"
        "preamble\n"
        "### Object storage fitness (R-1)\n"
        "Verdict: proven with a stated bound.\n"
        "\n"
        "## Running with no external services\n"
        "Verdict: failed."
    )
    section = _docs_section(document, "### Object storage fitness (R-1)")
    assert _recorded_verdict(section) == "proven with a stated bound"
    assert "failed" not in section
    assert _docs_section(document, "### No Such Heading") == ""
