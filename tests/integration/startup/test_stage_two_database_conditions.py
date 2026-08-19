"""The two stage-2 conditions that read a database, against real connections.

Condition 7 -- unapplied migrations on a serving process -- and the stage-2 half
of condition 5, a designated group absent from the database (AD-27). Both need a
live connection, which is what puts them here rather than beside the URLconf
conditions in `tests/unit/startup/test_stage_two_urlconf.py`.

**Both are serving-process-only, and that is the property most of these cases
turn on.** AD-13 makes process type fail *open*: `COMPONENT_PROCESS` absent means
this is not a serving process. `manage.py migrate` is the one action that clears
the migrations condition, so a refusal that fired on management commands would
deadlock the FR-41 release stage against a state nothing could resolve (AD-22).
Every case here declares the variable deliberately, and one case asserts what
happens when it is not declared -- which is the exemption itself, and R-3's
recorded price.

**AC #6, and why the fault is always on the second alias.** Stage 1's sqlite
refusal and stage 2's migrations refusal both iterate *every* configured
database, which is only reachable because stage 1 runs after the AD-8
composition step. A test whose fault sits on `default` cannot tell an
implementation that iterates from one that reads `DATABASES["default"]` and
stops, so the second alias is where every fault here is placed.

**Nothing is left behind, and every clause of that is load-bearing.** The second
alias is an in-memory sqlite database that ceases to exist when its connection
closes, and the connection handler is restored to the mapping it held before.
No case here creates a `Group`; three *delete* one, inside `django_db`'s
transaction, which rolls the deletion back -- never `TransactionTestCase`
semantics, which would commit it and leave the rest of the session short a row
that `users.0003_provision_designated_groups` put there.

`default` is the pytest-django test database in every case, including the two
that take `django_db_blocker` rather than the `django_db` marker. Those two
request `django_db_setup` explicitly for that reason: the blocker lifts the
connection guard but rebinds nothing, so a case that took it alone would run
`_refuse_unapplied_migrations` -- which iterates every alias, `default` first --
against the repository's own `db.sqlite3`, passing or failing on whatever state
a developer's local artifact happened to be in.

`tests/integration/conftest.py` marks everything under `tests/integration/` as an
integration test; the marker is not re-applied by hand.
"""

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test import override_settings

from config.locality import LOCAL
from config.locality import PROCESS_ENV_VAR
from config.locality import RUNTIME_ENV_VAR
from config.observability.telemetry import OTEL_SDK_DISABLED_ENV_VAR
from config.startup import run_stage_one
from config.startup import run_stage_two
from tests.conftest import deployed_url_patterns
from tests.conftest import temporary_root_urlconf
from tests.conftest import valid_deployed_settings_namespace
from tests.integration.startup.conftest import BOOT_PROBE_TIMEOUT_SECONDS
from tests.integration.startup.conftest import REPO_ROOT
from tests.integration.startup.conftest import subprocess_env

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from pytest_django.plugin import DjangoDbBlocker

# The alias every fault below is configured under. Never `default`: an
# implementation that read only `DATABASES["default"]` would pass a test whose
# fault sat there, which is the whole of what AC #6 is about.
SECOND_ALIAS = "reporting"

# The engine the second alias runs. sqlite in memory, because the fault being
# constructed is "this schema was never migrated" and an empty database is the
# purest form of it -- and because an in-memory database is gone the moment its
# connection closes, so this file leaves no artifact anywhere.
SQLITE_ENGINE = "django.db.backends.sqlite3"

# One of the pending migrations the refusal message has to name. `contenttypes`
# rather than a `users` migration because it is the first thing any Django
# schema needs, so it is pending on any database that was never migrated at all.
A_PENDING_MIGRATION = "contenttypes.0001_initial"

# A serving process type. Any member of `config.locality.SERVING_PROCESSES` does;
# `web` is the one that serves HTTP and therefore the one the conditions exist
# for.
SERVING_PROCESS = "web"


@pytest.fixture(autouse=True)
def _deployed_serving_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare a deployed serving process, which is what both conditions require.

    Deployed because every condition is deployed-only, and a serving process
    because these two are the only conditions in the contract that additionally
    gate on process type. `OTEL_SDK_DISABLED` is deleted because the AC #6 case
    runs stage 1 as well, and condition 3 reads it off the environment.
    """
    monkeypatch.delenv(RUNTIME_ENV_VAR, raising=False)
    monkeypatch.delenv(OTEL_SDK_DISABLED_ENV_VAR, raising=False)
    monkeypatch.setenv(PROCESS_ENV_VAR, SERVING_PROCESS)


@contextmanager
def _second_configured_database() -> Iterator[None]:
    """Configure a second, never-migrated database alias for the duration of a block.

    `override_settings(DATABASES=...)` alone is not enough, and the gap is worth
    stating because it is silent: `django.db.connections` caches the mapping it
    was configured with, and no `setting_changed` receiver refreshes it. So the
    override makes `settings.DATABASES` name two aliases while
    `connections["reporting"]` still raises `ConnectionDoesNotExist` -- a state
    in which this file's subject could not be exercised at all. The handler is
    reconfigured through its own public `configure_settings`, and restored to the
    exact mapping it held before.

    Yields:
        None. The configuration is the effect.

    """
    databases = {
        **settings.DATABASES,
        SECOND_ALIAS: {"ENGINE": SQLITE_ENGINE, "NAME": ":memory:"},
    }
    with override_settings(DATABASES=databases):
        restored = connections.__dict__.get("settings")
        connections.settings = connections.configure_settings(dict(databases))
        # Materialized here rather than on first use so that teardown always has
        # a connection to close, whether or not the case under test opened one.
        second = connections[SECOND_ALIAS]
        try:
            yield
        finally:
            second.close()
            del connections[SECOND_ALIAS]
            connections.__dict__.pop("settings", None)
            if restored is not None:
                connections.settings = restored


def _refusal() -> str:
    """Run stage 2 over a URL configuration a deployed component would serve.

    The URL configuration is overridden rather than inherited because the suite
    runs local, so `config/urls.py` mounts the local persona sign-in route and
    the second stage-2 condition would refuse before either database condition
    was reached -- a refusal, but not the one under test.

    Returns:
        The refusal message, for the caller to assert its distinguishing
        substring on.

    Raises:
        Failed: Through `pytest.raises`, when stage 2 accepted the state.

    """
    with temporary_root_urlconf(*deployed_url_patterns()), pytest.raises(ImproperlyConfigured) as refused:
        run_stage_two()
    return str(refused.value)


def _accepted() -> None:
    """Run stage 2 over the same configuration and require it to pass."""
    with temporary_root_urlconf(*deployed_url_patterns()):
        run_stage_two()


def test_unapplied_migrations_on_a_second_alias_refuse(django_db_blocker: DjangoDbBlocker) -> None:
    """AC #4: a serving process never starts against an unrecognized schema.

    The fault is on `reporting` while `default` is fully migrated, so an
    implementation that inspected only the default alias would find nothing and
    let the process serve.

    `django_db_blocker` rather than the `django_db` marker, and the difference is
    not stylistic. The marker wraps the case in a `TestCase`, which forbids every
    alias it was not told about at class setup -- and `reporting` cannot be
    declared there, because it does not exist until this body configures it. The
    blocker lifts pytest-django's global connection guard and nothing else, which
    is exactly what a condition that opens its own connections needs. Nothing is
    written: the condition reads migration state and the second database is in
    memory.
    """
    with django_db_blocker.unblock(), _second_configured_database():
        message = _refusal()

    assert f"DATABASES[{SECOND_ALIAS!r}]" in message
    assert A_PENDING_MIGRATION in message


@pytest.mark.django_db
def test_a_process_that_is_not_a_serving_process_is_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC #4's second half: `manage.py migrate` is not forbidden by the condition it clears.

    The same state as the case above -- migrations genuinely pending on a
    configured alias -- with `COMPONENT_PROCESS` absent. AD-13 makes absence mean
    *not a serving process*, and this is the exemption that keeps the FR-41
    release stage from deadlocking against a refusal only `migrate` could
    resolve. R-3 is the recorded price: a serving process started outside the
    Epic 5 tasks does not fire this refusal either.
    """
    monkeypatch.delenv(PROCESS_ENV_VAR, raising=False)

    with _second_configured_database():
        _accepted()


def test_both_stages_iterate_every_configured_database(django_db_blocker: DjangoDbBlocker) -> None:
    """AC #6: neither stage reads `DATABASES["default"]` alone.

    One test rather than two, because the claim is about the pair. Stage 1's
    sqlite condition and stage 2's migrations condition are handed the same
    shape of fault -- two aliases configured, the second one wrong -- and both
    have to find it. Stage 1 reads a settings namespace still being composed,
    stage 2 reads live connections, so the two cannot share an implementation
    and could drift apart without this.
    """
    namespace = valid_deployed_settings_namespace()
    namespace.DATABASES = {
        **namespace.DATABASES,
        SECOND_ALIAS: {"ENGINE": SQLITE_ENGINE, "NAME": "/srv/reporting.sqlite3"},
    }

    with pytest.raises(ImproperlyConfigured) as stage_one_refusal:
        run_stage_one(namespace)

    assert f"DATABASES[{SECOND_ALIAS!r}]" in str(stage_one_refusal.value)

    with django_db_blocker.unblock(), _second_configured_database():
        stage_two_message = _refusal()

    assert f"DATABASES[{SECOND_ALIAS!r}]" in stage_two_message


@pytest.mark.django_db
def test_the_designated_staff_group_absent_refuses() -> None:
    """AC #5, first half: the misconfiguration surfaces as a configuration error.

    Deleted inside `django_db`'s transaction, so the row is restored by the
    rollback and the rest of the session sees the database it expected.
    """
    staff_group = settings.CLAIMS_CONTRACT.staff_group
    Group.objects.filter(name=staff_group).delete()

    message = _refusal()

    assert repr(staff_group) in message
    assert repr(settings.CLAIMS_CONTRACT.superuser_group) not in message
    assert "AD-27" in message


@pytest.mark.django_db
def test_the_designated_superuser_group_absent_refuses() -> None:
    """AC #5, second half, asserted separately because it is a separate forbidden state.

    FR-16 requires each state to be testable on its own, and the two are fixed in
    different places: one is the group that confers `is_staff`, the other the
    group that confers `is_superuser`.
    """
    superuser_group = settings.CLAIMS_CONTRACT.superuser_group
    Group.objects.filter(name=superuser_group).delete()

    message = _refusal()

    assert repr(superuser_group) in message
    assert repr(settings.CLAIMS_CONTRACT.staff_group) not in message


@pytest.mark.django_db
def test_both_designated_groups_present_is_accepted() -> None:
    """The pass case, without which a condition that refused unconditionally would pass every case above.

    The rows are the ones `users.0003_provision_designated_groups` created from
    the claims contract when the test database was built -- the same mechanism a
    deployed component's release stage runs, rather than rows this test seeded
    for itself.
    """
    designated = {settings.CLAIMS_CONTRACT.staff_group, settings.CLAIMS_CONTRACT.superuser_group}

    assert set(Group.objects.filter(name__in=designated).values_list("name", flat=True)) == designated

    _accepted()


@pytest.mark.django_db
def test_the_refusal_creates_no_group() -> None:
    """AD-27's mechanism is a data migration, and a refusal never repairs.

    A condition that created the missing group would report a healthy component
    and hide the state it exists to report -- and would put a second group-
    creating mechanism beside `django_service.users.provisioning`, which is the
    duplication AD-27 forbids outright.
    """
    staff_group = settings.CLAIMS_CONTRACT.staff_group
    Group.objects.filter(name=staff_group).delete()

    _refusal()

    assert not Group.objects.filter(name=staff_group).exists()


# Boot this component the way a server does, serve one request through the
# callable that produced, and only then evaluate every stage-2 condition from
# inside that same process. Story 4.5 owns the audit that each condition is
# reachable on a served path rather than only under `manage.py`; this is the
# evidence it will read.
#
# A string on purpose: nothing here executes in the test process, so the
# deferred imports and the `print`-free file handoff need no ruff exemptions.
_CONDITIONS_PROBE_SOURCE = '''
"""Serve one request through the ASGI callable, then exercise every stage-2 condition."""

import asyncio
import json
import os
import sys
from pathlib import Path
from types import ModuleType

# The import that boots: `config/asgi.py` sets DJANGO_SETTINGS_MODULE by
# setdefault and calls `get_asgi_application()`, which runs `django.setup()` and
# with it every AppConfig.ready().
from config.asgi import application

PROBE_PATH = "/__stage-two-conditions-probe__/"
SERVE_TIMEOUT_SECONDS = 60.0

SCOPE = {
    "type": "http",
    "asgi": {"version": "3.0", "spec_version": "2.3"},
    "http_version": "1.1",
    "method": "GET",
    "scheme": "http",
    "path": PROBE_PATH,
    "raw_path": PROBE_PATH.encode("ascii"),
    "query_string": b"",
    "root_path": "",
    "headers": [(b"host", b"localhost")],
    "client": ("127.0.0.1", 54321),
    "server": ("localhost", 80),
}


async def _serve_one_request():
    """Drive one HTTP request through the ASGI callable and collect what it sent."""
    sent = []
    body_delivered = False
    never = asyncio.Event()

    async def receive():
        nonlocal body_delivered
        if not body_delivered:
            body_delivered = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await never.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await asyncio.wait_for(application(SCOPE, receive, send), SERVE_TIMEOUT_SECONDS)
    return sent


messages = asyncio.run(_serve_one_request())

# Everything from here runs in a process that has served a request. The locality
# declaration is dropped and a serving process declared, which is the state every
# stage-2 condition evaluates in.
os.environ.pop("COMPONENT_RUNTIME", None)
os.environ["COMPONENT_PROCESS"] = "web"

from contextlib import contextmanager

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import connections
from django.test import override_settings
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from config.authorization.claims import ClaimsContract
from config.local_dev import views as local_dev_views
from config.startup import run_stage_two
from django_service.users.provisioning import provision_designated_groups

SCRATCH = Path(sys.argv[2])

UNCONFIGURED_CONTRACT = ClaimsContract("", "", "", "")
CONFIGURED_CONTRACT = ClaimsContract(
    identity_key_claim="sub",
    group_claim="groups",
    staff_group="probe-staff",
    superuser_group="probe-superuser",
)


def install_urlconf(name, patterns):
    """Register a throwaway root URL configuration and return its dotted name."""
    module = ModuleType(name)
    module.urlpatterns = patterns
    sys.modules[name] = module
    return name


CLEAN = install_urlconf("probe_clean_urlconf", [path("admin/", admin.site.urls)])
TOKEN = install_urlconf(
    "probe_token_urlconf",
    [path("api/auth-token/", obtain_auth_token, name="obtain_auth_token")],
)
LOCAL = install_urlconf(
    "probe_local_sign_in_urlconf",
    [path("accounts/local-sign-in/", local_dev_views.persona_signin, name="local_persona_login")],
)


@contextmanager
def scratch_database():
    """Point the default alias at a throwaway sqlite file under the scratch directory.

    The probe boots on the local settings module, whose default database is a
    file in the repository root. Overriding it before anything connects is what
    keeps this test from creating one.
    """
    # The engine is named rather than inherited from the live configuration. A
    # spread of `settings.DATABASES["default"]` carries whatever engine the boot
    # selected, and pairing a postgres engine with this sqlite *filename* fails
    # on PostgreSQL's 63-character NAME limit instead of on anything this probe
    # is about.
    databases = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(SCRATCH / "probe.sqlite3"),
        },
    }
    with override_settings(DATABASES=databases):
        restored = connections.__dict__.get("settings")
        # Serving the request above materialized the default connection wrapper
        # from the settings that were live then, and replacing the handler's
        # mapping does not reconfigure a wrapper that already exists. Without
        # dropping it first, every query below would go to the local settings
        # module's own database file in the repository root -- which is the one
        # thing this probe must not touch.
        previous = connections["default"]
        previous.close()
        del connections["default"]
        connections.settings = connections.configure_settings(dict(databases))
        try:
            yield
        finally:
            connections["default"].close()
            del connections["default"]
            connections.__dict__.pop("settings", None)
            if restored is not None:
                connections.settings = restored
            connections["default"] = previous


def outcome(**overrides):
    """Run stage 2 under the given setting overrides and report what it did."""
    try:
        with override_settings(**overrides):
            run_stage_two()
    except ImproperlyConfigured as refusal:
        return str(refusal)
    return None


report = {
    "response_statuses": [m["status"] for m in messages if m["type"] == "http.response.start"],
    "credential_minting_route": outcome(ROOT_URLCONF=TOKEN),
    "local_sign_in_route": outcome(ROOT_URLCONF=LOCAL),
}

with scratch_database():
    report["database_in_use"] = connections["default"].settings_dict["NAME"]

    # Nothing has been migrated into the scratch database yet, so every
    # migration is pending on it.
    os.environ.pop("COMPONENT_PROCESS", None)
    report["migrations_pending_off_a_serving_process"] = outcome(ROOT_URLCONF=CLEAN)
    os.environ["COMPONENT_PROCESS"] = "web"
    report["unapplied_migrations"] = outcome(ROOT_URLCONF=CLEAN)

    # Migrated with an unconfigured contract, so the data migration provisions
    # nothing and the designated groups are genuinely absent afterwards.
    with override_settings(CLAIMS_CONTRACT=UNCONFIGURED_CONTRACT):
        call_command("migrate", verbosity=0)

    report["missing_designated_groups"] = outcome(
        ROOT_URLCONF=CLEAN,
        CLAIMS_CONTRACT=CONFIGURED_CONTRACT,
    )

    with override_settings(CLAIMS_CONTRACT=CONFIGURED_CONTRACT):
        provision_designated_groups()
        report["everything_satisfied"] = outcome(
            ROOT_URLCONF=CLEAN,
            CLAIMS_CONTRACT=CONFIGURED_CONTRACT,
        )

Path(sys.argv[1]).write_text(json.dumps(report), encoding="utf-8")
'''


def test_every_stage_two_condition_is_reachable_on_a_served_request_path(tmp_path: Path) -> None:
    """Each condition fires in a process that boots and serves the way a server does.

    Reuses Story 4.1's ASGI-driven probe rather than starting a server: the same
    `config.asgi` import gunicorn and uvicorn perform, the same
    `get_asgi_application()` that runs `django.setup()` and every
    `AppConfig.ready()`, and one request driven through the callable that import
    produced. `tests/integration/test_import_resolution.py` is what proves those
    two runtimes resolve the module identically, so this drives the callable
    directly rather than standing up a third and fourth server.

    The conditions are then evaluated from inside that process, which is the
    claim worth making: not that they refuse somewhere, but that they refuse in a
    process that has served traffic. The probe writes a JSON report to a file
    named on its command line rather than to stdout, because Django's logging
    configuration also writes to stdout.

    Everything the probe touches lives in `tmp_path`: the scratch database is
    created there and the local settings module's own database file is never
    connected to.
    """
    report_path = tmp_path / "stage-two-conditions.json"
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    # The autouse fixture above declared this process deployed and serving, and a
    # child inherits `os.environ`. Boot has to happen *local*: `config/asgi.py`
    # selects `config.settings.local`, and stage 1's FR-12 escape route refuses
    # that module the moment the run is deployed -- so an inherited declaration
    # would abort the child during `django.setup()` and every assertion below
    # would be about a component that never started. The probe flips to deployed
    # and serving itself, after it has served, which is the state these
    # conditions evaluate in.
    env = subprocess_env()
    env[RUNTIME_ENV_VAR] = LOCAL
    env.pop(PROCESS_ENV_VAR, None)

    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _CONDITIONS_PROBE_SOURCE, str(report_path), str(scratch)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=BOOT_PROBE_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode == 0, (
        f"the stage-two conditions probe exited {completed.returncode}\n"
        f"--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["response_statuses"], "the probe never served a request, so nothing below is about serving"
    assert report["database_in_use"].startswith(str(scratch)), (
        "the probe migrated something other than its own scratch database, so it did not leave the tree as found"
    )
    assert "rest_framework.authtoken" in (report["credential_minting_route"] or "")
    assert "config.local_dev" in (report["local_sign_in_route"] or "")
    assert "unapplied migrations" in (report["unapplied_migrations"] or "")
    assert report["migrations_pending_off_a_serving_process"] is None, (
        "the migrations condition fired on a process that declared no serving type (AD-13)"
    )
    assert "probe-staff" in (report["missing_designated_groups"] or "")
    assert report["everything_satisfied"] is None, (
        "a fully satisfied component was refused, so every refusal above proves nothing"
    )
