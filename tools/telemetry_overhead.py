# ruff: noqa: INP001 - a script run by path, not a package; tools/ has no __init__.py on purpose
"""Measure the per-request cost of always-on instrumentation (NFR-6).

Run it as `pixi run bench-telemetry`. The parent process spawns one child per
arm per round -- `sys.executable` re-running this file with `--child` -- and
alternates which arm goes first in each round, so ordering, cache warmth and
thermal drift are spread across both arms rather than charged to one. Each
child boots Django, applies its arm, serves a warm-up window of
`GET reverse("account_login")` through Django's test client, then times each of
the next N requests with `time.perf_counter_ns`. The parent pools each arm's
samples and reports median and p95 per arm and the delta between them.

**Instrumented arm.** Exactly what every process runs: the four instrumentors
installed by `configure_observability()`, with export disabled -- no
`OTEL_EXPORTER_OTLP_ENDPOINT`, no `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and no
`OTEL_TRACES_EXPORTER`, so `resolve_traces_exporter()` answers `none` and no
span processor is attached. Spans are still created and ended; only the
network is missing, which is the cost NFR-6 asks to isolate. The child asserts
both facts rather than trusting the scrubbed environment.

**Baseline arm, and why not `OTEL_SDK_DISABLED`.** The kill switch would be the
obvious way to get an uninstrumented process, and it is the wrong one. Setting
it is stage-1 unconditional refusal condition 3: once the refusal contract
applies, a settings import with it set raises `ImproperlyConfigured`, so a
benchmark built on it works only until the guarantee it measures is enforced.
The harness therefore refuses to run at all when the variable is present, with
any value, rather than reinterpret it.

**Baseline arm, and why uninstrument rather than skip the call.** Skipping
`configure_observability()` is not possible without editing production code:
`config/__init__.py` imports `config.celery_app`, which calls it, so any import
of the `config` package -- settings included -- installs instrumentation. The
baseline child instead calls `.uninstrument()` on every instrumentor
`config.observability.telemetry` imports, after `django.setup()` and before the
first request, and checks that each reports `is_instrumented_by_opentelemetry`
false and that the OpenTelemetry middleware has left `settings.MIDDLEWARE`.
`BaseInstrumentor` is a singleton, so a fresh instance is the installed one.
Two things stay in both arms and are therefore not in the delta: the tracer
provider (`trace.set_tracer_provider` is set-once) and the log processors that
read the current span.

**Database.** The route is served against a throwaway sqlite file the harness
creates and migrates in a temporary directory per child; `DATABASE_URL` is set
in the child environment so neither a developer's `db.sqlite3` nor any
configured server is opened. `DJANGO_READ_DOT_ENV_FILE` is removed for the same
reason -- a `.env` could otherwise reintroduce an exporter or a database.

Results are emitted as one structlog event and, with `--json-out`, written as
JSON. The statistics reduction is pure and importable with only the standard
library and structlog, so `tests/unit/test_telemetry_overhead.py` covers it
without spawning a process or booting Django.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Mapping
    from collections.abc import Sequence

INSTRUMENTED = "instrumented"
BASELINE = "baseline"
ARMS = (INSTRUMENTED, BASELINE)

#: Spelled once in `config.observability.telemetry`; repeated here only because
#: this module may import nothing outside the standard library and structlog at
#: module scope. `tests/unit/test_telemetry_overhead.py` asserts the two agree.
OTEL_SDK_DISABLED_ENV_VAR = "OTEL_SDK_DISABLED"

#: The exit status of a refused run, distinct from a child's failure.
REFUSED_EXIT_CODE = 2

#: Removed from every child's environment: these select an exporter, and the
#: measurement is of instrumentation with export disabled.
EXPORTER_ENV_VARS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_TRACES_EXPORTER",
)

#: Removed too: a `.env` read at boot could put an exporter or a database back.
DOT_ENV_SWITCH = "DJANGO_READ_DOT_ENV_FILE"

DEFAULT_SETTINGS = "config.settings.test"
DEFAULT_ROUNDS = 10
DEFAULT_REQUESTS = 1000
DEFAULT_WARMUP = 200

#: The smallest pool a p95 is reported from. Below twenty samples the 95th
#: percentile is the maximum, which is a different statistic.
MIN_SAMPLES = 20

ROUTE_NAME = "account_login"

#: A child that has not finished by then is hung (a lock, a blocked request), not slow.
CHILD_TIMEOUT_S = 900

#: The child-report fields that must agree across every round of one arm.
CONSISTENT_FIELDS = ("instrumentors", "middleware_present", "db_vendor", "url")

REPO_ROOT = Path(__file__).resolve().parents[1]

logger: structlog.stdlib.BoundLogger = structlog.get_logger("tools.telemetry_overhead")


@dataclass(frozen=True)
class Summary:
    """Per-request wall time for one arm.

    Attributes:
        count: Number of measured samples.
        median_ns: Median request time in nanoseconds.
        p95_ns: Nearest-rank 95th percentile in nanoseconds.

    """

    count: int
    median_ns: float
    p95_ns: float


@dataclass(frozen=True)
class Delta:
    """The instrumented arm's cost over the baseline.

    Attributes:
        median_ns: Absolute median difference in nanoseconds.
        median_pct: Median difference as a percentage of the baseline median,
            or None when the baseline is zero.
        p95_ns: Absolute p95 difference in nanoseconds.
        p95_pct: p95 difference as a percentage of the baseline p95, or None
            when the baseline is zero.

    """

    median_ns: float
    median_pct: float | None
    p95_ns: float
    p95_pct: float | None


def percentile(samples: Sequence[int], fraction: float) -> float:
    """Return the nearest-rank percentile of `samples`.

    Args:
        samples: Measured values; need not be sorted.
        fraction: The percentile as a fraction in (0, 1].

    Returns:
        The smallest sample at or above `fraction` of the ordered pool.

    Raises:
        ValueError: When `samples` is empty or `fraction` is out of range.

    """
    if not samples:
        msg = "percentile of an empty sample"
        raise ValueError(msg)
    if not 0 < fraction <= 1:
        msg = f"fraction must be in (0, 1], got {fraction}"
        raise ValueError(msg)
    ordered = sorted(samples)
    rank = math.ceil(fraction * len(ordered))
    return float(ordered[rank - 1])


def summarize(samples: Sequence[int]) -> Summary:
    """Reduce one arm's samples to median and p95.

    Args:
        samples: Per-request wall times in nanoseconds.

    Returns:
        The arm's summary.

    Raises:
        ValueError: When fewer than `MIN_SAMPLES` samples are given.

    """
    if len(samples) < MIN_SAMPLES:
        msg = f"need at least {MIN_SAMPLES} samples for a p95, got {len(samples)}"
        raise ValueError(msg)
    return Summary(
        count=len(samples),
        median_ns=float(statistics.median(samples)),
        p95_ns=percentile(samples, 0.95),
    )


def _pct(difference: float, base: float) -> float | None:
    """Express `difference` as a percentage of `base`, or None for a zero base."""
    if base == 0:
        return None
    return difference / base * 100


def delta(baseline: Summary, instrumented: Summary) -> Delta:
    """Compute the instrumented arm's overhead over the baseline.

    Args:
        baseline: The uninstrumented arm.
        instrumented: The instrumented arm.

    Returns:
        Absolute and relative differences for the median and the p95.

    """
    median_diff = instrumented.median_ns - baseline.median_ns
    p95_diff = instrumented.p95_ns - baseline.p95_ns
    return Delta(
        median_ns=median_diff,
        median_pct=_pct(median_diff, baseline.median_ns),
        p95_ns=p95_diff,
        p95_pct=_pct(p95_diff, baseline.p95_ns),
    )


def arm_schedule(rounds: int) -> list[tuple[int, str]]:
    """Order the children: both arms every round, alternating which goes first.

    Args:
        rounds: Number of rounds; each runs one child per arm.

    Returns:
        `(round, arm)` pairs in execution order.

    Raises:
        ValueError: When `rounds` is less than one.

    """
    if rounds < 1:
        msg = f"rounds must be at least 1, got {rounds}"
        raise ValueError(msg)
    schedule: list[tuple[int, str]] = []
    for index in range(rounds):
        order = ARMS if index % 2 == 0 else tuple(reversed(ARMS))
        schedule.extend((index, arm) for arm in order)
    return schedule


def refuse_if_sdk_disabled(environ: Mapping[str, str]) -> None:
    """Refuse to measure when the OpenTelemetry kill switch is present at all.

    Any value is refused, `false` included: the harness does not decide what
    the operator meant, and a baseline built on the kill switch is exactly what
    this harness is designed not to be.

    Args:
        environ: The environment the harness was started with.

    Raises:
        SystemExit: When `OTEL_SDK_DISABLED` is set.

    """
    if OTEL_SDK_DISABLED_ENV_VAR in environ:
        logger.error(
            "telemetry_overhead.refused",
            reason="kill switch present; unset it -- the baseline is obtained by uninstrumenting, never by it",
            variable=OTEL_SDK_DISABLED_ENV_VAR,
            value=environ[OTEL_SDK_DISABLED_ENV_VAR],
        )
        raise SystemExit(REFUSED_EXIT_CODE)


def child_environment(environ: Mapping[str, str], *, settings_module: str, database_path: Path) -> dict[str, str]:
    """Build a child's environment from the parent's.

    Args:
        environ: The parent environment.
        settings_module: The Django settings module the child boots.
        database_path: The throwaway sqlite file the child migrates and serves from.

    Returns:
        A copy of `environ` with the exporter variables and the `.env` switch
        removed, and the settings module and database pinned.

    """
    scrubbed = {key: value for key, value in environ.items() if key not in (*EXPORTER_ENV_VARS, DOT_ENV_SWITCH)}
    scrubbed["DJANGO_SETTINGS_MODULE"] = settings_module
    scrubbed["DATABASE_URL"] = f"sqlite:///{database_path}"
    return scrubbed


def pinned_otel_range(manifest: Path) -> dict[str, str]:
    """Read the OpenTelemetry pins from the unconditional pixi dependencies.

    Args:
        manifest: Path to `pixi.toml`.

    Returns:
        Package name to version specifier, for every `opentelemetry-*` entry.

    """
    with manifest.open("rb") as handle:
        dependencies: dict[str, Any] = tomllib.load(handle).get("dependencies", {})
    return {name: str(spec) for name, spec in sorted(dependencies.items()) if name.startswith("opentelemetry-")}


def _version(distribution: str) -> str:
    """Return an installed distribution's version, or `absent`."""
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "absent"


def _apply_arm(arm: str) -> tuple[dict[str, bool], bool]:
    """Put this booted process into `arm`'s state and prove it is there.

    The instrumentor names are read from `config.observability.telemetry`'s
    namespace -- the same introspection the instrumentation-set pin in
    `tests/unit/test_telemetry.py` uses -- so a component that pruned a feature's
    instrumentor measures what it carries.

    Args:
        arm: `instrumented` or `baseline`.

    Returns:
        Each instrumentor's `is_instrumented_by_opentelemetry`, and whether the
        OpenTelemetry middleware is in `settings.MIDDLEWARE`.

    Raises:
        RuntimeError: When the arm is not in the state it claims to measure.

    """
    from django.conf import settings  # noqa: PLC0415
    from opentelemetry import trace  # noqa: PLC0415
    from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415

    from config.observability import telemetry  # noqa: PLC0415

    names = sorted(name for name in dir(telemetry) if name.endswith("Instrumentor"))
    instrumentors: dict[str, Any] = {name: getattr(telemetry, name)() for name in names}
    if arm == BASELINE:
        for instrumentor in instrumentors.values():
            instrumentor.uninstrument()

    state = {name: bool(instrumentor.is_instrumented_by_opentelemetry) for name, instrumentor in instrumentors.items()}
    middleware_present = any("opentelemetry" in entry for entry in settings.MIDDLEWARE)

    if arm == BASELINE:
        if any(state.values()) or middleware_present:
            msg = f"baseline is still instrumented: {state}, middleware present={middleware_present}"
            raise RuntimeError(msg)
        return state, middleware_present

    provider = trace.get_tracer_provider()
    if telemetry.resolve_traces_exporter() != telemetry.NONE:
        msg = "export is not disabled in the instrumented arm"
        raise RuntimeError(msg)
    if not isinstance(provider, TracerProvider) or telemetry.has_span_processor(provider):
        msg = "the instrumented arm needs an SDK provider with no span processor"
        raise RuntimeError(msg)
    if not all(state.values()) or not middleware_present:
        msg = f"instrumented arm is not fully instrumented: {state}, middleware present={middleware_present}"
        raise RuntimeError(msg)
    return state, middleware_present


def run_child(arm: str, requests: int, warmup: int, out: Path) -> None:
    """Serve and time requests in this process under one arm.

    Args:
        arm: `instrumented` or `baseline`.
        requests: Number of measured requests.
        warmup: Number of discarded requests served first.
        out: Where the raw samples and the arm's self-check are written.

    Raises:
        RuntimeError: When a request does not answer 200, or the database is not
            the harness's own throwaway file.

    """
    refuse_if_sdk_disabled(os.environ)

    import django  # noqa: PLC0415 - Django is booted only in the child

    django.setup()

    from django.core.management import call_command  # noqa: PLC0415
    from django.db import connection  # noqa: PLC0415
    from django.test import Client  # noqa: PLC0415
    from django.test.utils import setup_test_environment  # noqa: PLC0415
    from django.urls import reverse  # noqa: PLC0415

    # A `--settings` module that ignores `DATABASE_URL` would point `migrate` at
    # a real database; refuse before touching it.
    expected = os.environ.get("DATABASE_URL", "").removeprefix("sqlite:///")
    if connection.vendor != "sqlite" or str(connection.settings_dict["NAME"]) != expected:
        msg = f"refusing to migrate {connection.vendor}:{connection.settings_dict['NAME']}; expected sqlite:{expected}"
        raise RuntimeError(msg)
    call_command("migrate", interactive=False, verbosity=0)
    state, middleware_present = _apply_arm(arm)

    setup_test_environment()
    client = Client()
    url = reverse(ROUTE_NAME)
    samples: list[int] = []
    for index in range(warmup + requests):
        start = time.perf_counter_ns()
        response = client.get(url)
        elapsed = time.perf_counter_ns() - start
        if response.status_code != 200:  # noqa: PLR2004 - HTTP OK
            msg = f"GET {url} answered {response.status_code}"
            raise RuntimeError(msg)
        if index >= warmup:
            samples.append(elapsed)

    out.write_text(
        json.dumps(
            {
                "arm": arm,
                "samples_ns": samples,
                "instrumentors": state,
                "middleware_present": middleware_present,
                "db_vendor": connection.vendor,
                "url": url,
            },
        ),
    )


def run_parent(args: argparse.Namespace) -> dict[str, Any]:
    """Spawn every child, pool the samples and report.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The full report, as logged and optionally written to `--json-out`.

    Raises:
        RuntimeError: When a child fails.

    """
    refuse_if_sdk_disabled(os.environ)
    pooled: dict[str, list[int]] = {arm: [] for arm in ARMS}
    child_reports: dict[str, dict[str, Any]] = {}
    script = str(Path(__file__).resolve())

    with tempfile.TemporaryDirectory(prefix="bench-telemetry-") as scratch:
        for round_index, arm in arm_schedule(args.rounds):
            out = Path(scratch) / f"{arm}-{round_index}.json"
            env = child_environment(
                os.environ,
                settings_module=args.settings,
                database_path=Path(scratch) / f"{arm}-{round_index}.sqlite3",
            )
            command = [
                sys.executable,
                script,
                "--child",
                "--arm",
                arm,
                "--requests",
                str(args.requests),
                "--warmup",
                str(args.warmup),
                "--out",
                str(out),
            ]
            logger.info("telemetry_overhead.child_start", round=round_index, arm=arm)
            try:
                completed = subprocess.run(  # noqa: S603 - our own script
                    command, env=env, check=False, cwd=REPO_ROOT, timeout=CHILD_TIMEOUT_S
                )
            except subprocess.TimeoutExpired as exc:
                msg = f"{arm} child in round {round_index} did not finish within {CHILD_TIMEOUT_S}s"
                raise RuntimeError(msg) from exc
            if completed.returncode != 0:
                msg = f"{arm} child in round {round_index} exited {completed.returncode}"
                raise RuntimeError(msg)
            report = json.loads(out.read_text())
            previous = child_reports.get(arm)
            if previous is not None and any(previous[key] != report[key] for key in CONSISTENT_FIELDS):
                msg = f"{arm} child in round {round_index} measured a different state from an earlier round"
                raise RuntimeError(msg)
            pooled[arm].extend(report["samples_ns"])
            child_reports[arm] = report

    baseline = summarize(pooled[BASELINE])
    instrumented = summarize(pooled[INSTRUMENTED])
    result: dict[str, Any] = {
        "date": time.strftime("%Y-%m-%d"),
        "route": child_reports[INSTRUMENTED]["url"],
        "rounds": args.rounds,
        "requests_per_child": args.requests,
        "warmup_per_child": args.warmup,
        "baseline": asdict(baseline),
        "instrumented": asdict(instrumented),
        "delta": asdict(delta(baseline, instrumented)),
        "instrumentation_set": sorted(child_reports[INSTRUMENTED]["instrumentors"]),
        "asgi_instrumentation_present": importlib.util.find_spec("opentelemetry.instrumentation.asgi") is not None,
        "otel_pins": pinned_otel_range(REPO_ROOT / "pixi.toml"),
        "settings_module": args.settings,
        "db_vendor": child_reports[INSTRUMENTED]["db_vendor"],
        "python": platform.python_version(),
        "django": _version("django"),
        "opentelemetry_sdk": _version("opentelemetry-sdk"),
        "opentelemetry_instrumentation_django": _version("opentelemetry-instrumentation-django"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    }
    logger.info("telemetry_overhead.result", **result)
    if args.json_out is not None:
        args.json_out.write_text(json.dumps(result, indent=2) + "\n")
    return result


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        The parser for both the parent and the `--child` invocation.

    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--settings", default=DEFAULT_SETTINGS, help="Django settings module the children boot")
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS, help="rounds; each runs both arms once")
    parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS, help="measured requests per child")
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP, help="discarded requests per child")
    parser.add_argument("--json-out", type=Path, default=None, help="also write the report to this JSON file")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--arm", choices=ARMS, help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    return parser


def validate_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject arguments that would fail only after every child has run.

    Args:
        parser: The parser, whose `error` exits with a usage message.
        args: Parsed command-line arguments.

    """
    if args.child and (args.arm is None or args.out is None):
        parser.error("--child requires --arm and --out")
    if args.requests < 1 or args.warmup < 0 or args.rounds < 1:
        parser.error("--requests and --rounds must be at least 1, --warmup at least 0")
    if not args.child and args.requests * args.rounds < MIN_SAMPLES:
        parser.error(f"--requests x --rounds must give at least {MIN_SAMPLES} samples per arm")
    if args.json_out is not None and not args.json_out.parent.is_dir():
        parser.error(f"--json-out directory does not exist: {args.json_out.parent}")


def main(argv: Sequence[str] | None = None) -> None:
    """Entry point.

    Args:
        argv: Arguments, defaulting to the process's own.

    """
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_arguments(parser, args)
    if args.child:
        run_child(args.arm, args.requests, args.warmup, args.out)
    else:
        run_parent(args)


if __name__ == "__main__":
    main()
