"""Tests for the supply-chain policy declared in pixi.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

PIXI_MANIFEST = Path(__file__).resolve().parents[2] / "pixi.toml"

# The project's own editable install is not a supply-chain exception -- it is
# how the source tree reaches the environment. Every other entry is.
OWN_PACKAGE = "django-15-factor-base"


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    """Return the parsed pixi manifest."""
    with PIXI_MANIFEST.open("rb") as handle:
        parsed: dict[str, Any] = tomllib.load(handle)
    return parsed


def test_manifest_is_present() -> None:
    """The manifest resolves from the test file, so the paths below mean something."""
    assert PIXI_MANIFEST.is_file()


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
    """
    assert "django-celery-beat" in manifest["dependencies"]
