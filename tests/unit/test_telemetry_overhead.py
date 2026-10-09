"""Tests for the NFR-6 measurement harness's pure half.

`tools/telemetry_overhead.py` is a script, not a package, so it is loaded by
file path: `tools/` is not an import root and must not become one (AD-7). Only
the statistics reduction, the arm schedule, the kill-switch refusal and the
child-environment scrub are exercised -- nothing here spawns a process or boots
Django, which is the half that produces the number rather than the half that
reduces it.
"""

from __future__ import annotations

import sys
from importlib.util import module_from_spec
from importlib.util import spec_from_file_location
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import pytest
import structlog

from config.observability import telemetry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

HARNESS = Path(__file__).resolve().parents[2] / "tools" / "telemetry_overhead.py"


@pytest.fixture(scope="module")
def harness() -> Iterator[ModuleType]:
    """Load the harness by path, registered only for the life of this module.

    Registration is needed because `dataclasses` resolves a class's module
    through `sys.modules`; it is removed afterwards so nothing else in the
    session can import the script by accident.
    """
    name = "_telemetry_overhead_under_test"
    spec = spec_from_file_location(name, HARNESS)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        del sys.modules[name]


def _samples(count: int, value: int = 1000) -> list[int]:
    return [value] * count


class TestSummarize:
    def test_median_and_p95(self, harness: Any):
        samples = list(range(1, 101))
        assert harness.summarize(samples) == harness.Summary(count=100, median_ns=50.5, p95_ns=95.0)

    def test_order_does_not_matter(self, harness: Any):
        samples = list(range(100, 0, -1))
        assert harness.summarize(samples) == harness.summarize(sorted(samples))

    def test_too_few_samples_is_an_error(self, harness: Any):
        """Below the floor the 95th percentile is the maximum, a different statistic."""
        with pytest.raises(ValueError, match="at least 20 samples"):
            harness.summarize(_samples(harness.MIN_SAMPLES - 1))

    def test_the_floor_itself_is_accepted(self, harness: Any):
        assert harness.summarize(_samples(harness.MIN_SAMPLES)).count == harness.MIN_SAMPLES


class TestPercentile:
    @pytest.mark.parametrize(("fraction", "expected"), [(0.5, 2.0), (1.0, 4.0), (0.01, 1.0)])
    def test_nearest_rank(self, harness: Any, fraction: float, expected: float):
        assert harness.percentile([4, 1, 3, 2], fraction) == expected

    def test_empty_is_an_error(self, harness: Any):
        with pytest.raises(ValueError, match="empty"):
            harness.percentile([], 0.5)

    @pytest.mark.parametrize("fraction", [0, -0.1, 1.5])
    def test_fraction_out_of_range_is_an_error(self, harness: Any, fraction: float):
        with pytest.raises(ValueError, match="fraction"):
            harness.percentile([1, 2], fraction)


class TestDelta:
    def test_absolute_and_relative(self, harness: Any):
        baseline = harness.Summary(count=100, median_ns=1000.0, p95_ns=2000.0)
        instrumented = harness.Summary(count=100, median_ns=1100.0, p95_ns=2500.0)
        assert harness.delta(baseline, instrumented) == harness.Delta(
            median_ns=100.0,
            median_pct=pytest.approx(10.0),
            p95_ns=500.0,
            p95_pct=pytest.approx(25.0),
        )

    def test_a_faster_instrumented_arm_is_a_negative_delta(self, harness: Any):
        """Noise can invert the sign; the harness reports it rather than clamping."""
        baseline = harness.Summary(count=100, median_ns=1000.0, p95_ns=1000.0)
        instrumented = harness.Summary(count=100, median_ns=900.0, p95_ns=1000.0)
        assert harness.delta(baseline, instrumented) == harness.Delta(
            median_ns=-100.0,
            median_pct=pytest.approx(-10.0),
            p95_ns=0.0,
            p95_pct=0.0,
        )

    def test_zero_baseline_has_no_percentage(self, harness: Any):
        baseline = harness.Summary(count=100, median_ns=0.0, p95_ns=0.0)
        instrumented = harness.Summary(count=100, median_ns=5.0, p95_ns=7.0)
        assert harness.delta(baseline, instrumented) == harness.Delta(
            median_ns=5.0,
            median_pct=None,
            p95_ns=7.0,
            p95_pct=None,
        )


class TestArmSchedule:
    def test_alternates_which_arm_goes_first(self, harness: Any):
        assert harness.arm_schedule(3) == [
            (0, "instrumented"),
            (0, "baseline"),
            (1, "baseline"),
            (1, "instrumented"),
            (2, "instrumented"),
            (2, "baseline"),
        ]

    def test_every_round_runs_both_arms(self, harness: Any):
        schedule = harness.arm_schedule(4)
        assert sorted(arm for _, arm in schedule) == ["baseline"] * 4 + ["instrumented"] * 4

    def test_zero_rounds_is_an_error(self, harness: Any):
        with pytest.raises(ValueError, match="rounds"):
            harness.arm_schedule(0)


class TestRefusal:
    def test_the_variable_name_matches_the_one_telemetry_reads(self, harness: Any):
        """The harness repeats the name rather than importing it; the two must agree."""
        assert harness.OTEL_SDK_DISABLED_ENV_VAR == telemetry.OTEL_SDK_DISABLED_ENV_VAR

    @pytest.mark.parametrize("value", ["true", "false", "0", ""])
    def test_refuses_when_the_kill_switch_is_present_with_any_value(
        self,
        harness: Any,
        value: str,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Even `false`: the harness does not reinterpret the operator's intent.

        A fresh logger proxy is installed first: structlog caches a logger on
        first use, and one frozen against an earlier case's capture would leave
        this one's `capture_logs` blind.
        """
        monkeypatch.setattr(harness, "logger", structlog.get_logger("tools.telemetry_overhead"))
        with structlog.testing.capture_logs() as captured, pytest.raises(SystemExit) as raised:
            harness.refuse_if_sdk_disabled({"OTEL_SDK_DISABLED": value})
        assert raised.value.code == harness.REFUSED_EXIT_CODE
        assert [event["event"] for event in captured] == ["telemetry_overhead.refused"]
        assert captured[0]["log_level"] == "error"
        assert captured[0]["variable"] == "OTEL_SDK_DISABLED"

    def test_runs_when_the_kill_switch_is_absent(self, harness: Any):
        harness.refuse_if_sdk_disabled({"PATH": "/usr/bin"})


class TestChildEnvironment:
    def test_scrubs_exporters_and_pins_settings_and_database(self, harness: Any, tmp_path: Path):
        parent = {
            "PATH": "/usr/bin",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://collector:4318/v1/traces",
            "OTEL_TRACES_EXPORTER": "console",
            "DJANGO_READ_DOT_ENV_FILE": "true",
            "DATABASE_URL": "postgres://developer@localhost/real",
            "DJANGO_SETTINGS_MODULE": "config.settings.local",
            "OTEL_SERVICE_NAME": "kept",
        }
        database = tmp_path / "bench.sqlite3"
        env = harness.child_environment(parent, settings_module="config.settings.test", database_path=database)

        for name in (*harness.EXPORTER_ENV_VARS, "DJANGO_READ_DOT_ENV_FILE"):
            assert name not in env
        assert env["DJANGO_SETTINGS_MODULE"] == "config.settings.test"
        assert env["DATABASE_URL"] == f"sqlite:///{database}"
        assert env["PATH"] == "/usr/bin"
        assert env["OTEL_SERVICE_NAME"] == "kept"

    def test_does_not_mutate_the_parent(self, harness: Any, tmp_path: Path):
        parent = {"OTEL_TRACES_EXPORTER": "console"}
        harness.child_environment(parent, settings_module="x", database_path=tmp_path / "db")
        assert parent == {"OTEL_TRACES_EXPORTER": "console"}


class TestPinnedOtelRange:
    def test_reads_only_opentelemetry_dependencies(self, harness: Any, tmp_path: Path):
        manifest = tmp_path / "pixi.toml"
        manifest.write_text(
            '[dependencies]\ndjango = ">=5.2,<5.3"\nopentelemetry-sdk = ">=1.44,<2"\nopentelemetry-api = ">=1.44,<2"\n',
        )
        assert harness.pinned_otel_range(manifest) == {
            "opentelemetry-api": ">=1.44,<2",
            "opentelemetry-sdk": ">=1.44,<2",
        }


class TestValidateArguments:
    @pytest.mark.parametrize(
        "argv",
        [
            ["--child"],
            ["--child", "--arm", "baseline"],
            ["--requests", "0"],
            ["--warmup", "-1"],
            ["--rounds", "0"],
            ["--rounds", "1", "--requests", "19"],
            ["--json-out", "/nonexistent-bench-dir/result.json"],
        ],
    )
    def test_rejects_arguments_that_would_fail_after_the_run(self, harness: Any, argv: list[str]):
        parser = harness.build_parser()

        with pytest.raises(SystemExit):
            harness.validate_arguments(parser, parser.parse_args(argv))

    def test_accepts_the_defaults_and_a_complete_child_invocation(self, harness: Any, tmp_path: Path):
        parser = harness.build_parser()

        harness.validate_arguments(parser, parser.parse_args([]))
        harness.validate_arguments(
            parser, parser.parse_args(["--child", "--arm", "baseline", "--requests", "1", "--out", str(tmp_path / "o")])
        )
