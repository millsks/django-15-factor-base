# Development

## Environment

Dependencies are declared in `pixi.toml` and resolved from **conda-forge**.
`pyproject.toml` carries build metadata and tool configuration only — it does
not declare dependencies.

The build backend is **hatchling**, with **hatch-vcs** deriving the version
from git tags. `[project]` therefore declares `dynamic = ["version"]` and has
no hardcoded version; `django_service.__version__` reads it back from the
installed distribution metadata. With no tag reachable the version resolves to
a development version such as `0.0.1.dev6+g<sha>`; tag a release (`v0.1.0`) to
get a clean one. `fallback-version` covers shallow CI clones with no tags at
all.

```sh
pixi install         # create the runtime environment
pixi install -e dev  # add the development toolchain
pixi run bootstrap   # install the git hooks
```

There are three environments. **`default`** holds runtime dependencies only —
Django, Celery, uvicorn and so on — and is what a production image would
install. **`dev`** layers the toolchain (ruff, mypy, pytest, mkdocs, git-cliff)
on top. **`spike-storage`** is `dev` plus `django-storages`, and exists only to
run R-1's fitness spike — see [Object storage fitness (R-1)](#object-storage-fitness-r-1);
it goes away when Epic 7 has acted on the verdict. All three share a
solve-group, so packages common to them resolve to identical versions.

**You never need `-e` for a task.** `pixi run <task>` resolves without a flag
and without prompting. `pixi task list` shows each task with its description.

Two different mechanisms deliver that, and the difference matters as soon as a
new environment is added:

- **Every task that declares a `cmd` pins `default-environment`.** That is what
  keeps it unambiguous however many environments carry the feature declaring it.
  `tests/unit/test_gate_contract.py::test_every_task_with_a_command_pins_its_environment`
  holds it for all of them, not just the ones the gate runs.
- **`ci` cannot pin one, and does not.** pixi rejects `default-environment` on a
  task that declares only `depends-on`. So `ci` stays unambiguous the only other
  way available: the feature that declares it — the dependency-free `gate`
  feature — belongs to **exactly one** environment. That rule is written beside
  `[feature.gate.tasks]` in `pixi.toml` and asserted by
  `test_the_gate_task_is_reachable_from_exactly_one_environment`.

The second rule is not decoration. `spike-storage` layers the `dev` *feature*,
which made `ci` visible from two environments and aborted `pixi run ci` with
`the task 'ci' is ambiguous` before a single step ran. Epic 8's six-environment
matrix is the same change six times over, so a new environment that carries the
`dev` toolchain must not also carry `gate`.

Operational commands — `manage`, `migrate`, `collectstatic`, `createsuperuser`,
`serve` — run in `default`, because a deployment runs them too. Development-only
commands — `runserver`, `serve-reload`, `makemigrations` — and the whole quality
harness run in `dev`.

An *ad-hoc* command still needs the flag: `pixi run -- pytest` would use
`default` and fail on the missing test dependencies. Use `pixi run -e dev --`.

### Debug apps

`django-debug-toolbar` and `django-extensions` ship only in the `dev` feature,
so `config/settings/local.py` gates them behind `DJANGO_DEBUG_APPS`:

```python
DEBUG_APPS = env.bool("DJANGO_DEBUG_APPS", default=False)
```

`[feature.dev.activation.env]` sets it to `True`, so the toolbar is on in `dev`
and absent everywhere else. Without this gate the local settings import
`debug_toolbar` unconditionally and Django cannot start in the runtime
environment at all.

`hatchling` and `hatch-vcs` are the exception — they sit in `[dependencies]`
rather than the dev feature, because `[pypi-options] no-build-isolation`
requires the build backend in whichever environment installs the editable
package, including the runtime-only `default`.

The project pins **pixi 0.70.2**: `requires-pixi = ">=0.70.2"` in `pixi.toml`
sets the local floor, and every workflow passes `pixi-version: v0.70.2` to
`setup-pixi`. `pixi.lock` is lock-file format v7, which pixi 0.67.x cannot
read at all, so the floor is a hard requirement rather than a preference.

Every dependency resolves from conda-forge. `pixi.lock` holds exactly one
package-index entry — the editable install of this project itself. See
[Supply chain](#supply-chain) below.

## Supply chain

**conda-forge is the single channel.** `[workspace] channels` names it and
nothing else, and every third-party package the environment installs comes from
there. Adding a second channel changes what the project trusts, so it is a
deliberate change rather than one more word in a list.

**`[pypi-dependencies]` carries the editable self-install and nothing else.**
The one entry, `django-15-factor-base = { path = ".", editable = true }`, is how
the source tree reaches the environment — it is not a supply-chain exception. A
third-party package appearing there *is* one, and it needs its reasoning and an
exit condition recorded beside it in `pixi.toml`. The project carries **zero**
exceptions today: the one it used to have, `django-celery-beat`, was fixed
upstream and now resolves from conda-forge like everything else.

**Transitive availability is not declaration.** A package the code imports
directly is declared directly, even when something else already pulls it in.
`django-timezone-field`, `python-crontab` and `cron-descriptor` are declared
although `django-celery-beat` requires them; `pyyaml` is declared although it
already reaches the environment behind pre-commit. Otherwise the dependency
survives only for as long as the other package happens to want it.

**Reasoning lives beside the configuration it constrains.** A declaration whose
presence is not obvious from its name — anything pinned `"*"`, anything present
because a *different* package needs it, anything that is a C library rather than
a Python one — carries a `#` comment saying why, either directly above it or
after the version specifier. Directly is meant literally: a comment heading a
group covers only the line immediately beneath it, so a new declaration cannot
inherit a reason written about its neighbour.

**A reusable app must reach conda-forge before a component may depend on it.**
The channel is a precondition, not a step to work around by reaching for the
package index.

**Channel presence alone is not fitness — and this is a standing rule, not an
observation.** FR-50: before any feature is committed to, confirm **both**
channel availability **and** fitness against the pinned runtime. Presence
answers *where a package comes from*, not *whether it works here*. Presence
alone is explicitly insufficient.

The failure mode is concrete rather than theoretical, and it has a name in this
repository. `django-storages` **is** on conda-forge, which is the availability
test, and its 1.14.6 release (2025-04-02) declares support for neither Django
6.0 nor Python 3.14. Availability passed; fitness was unknown. That gap is risk
**R-1**, and closing it is what [Object storage fitness
(R-1)](#object-storage-fitness-r-1) below records.

Committing to a feature means declaring its package in `[dependencies]`, so the
way to obey the rule is to stage the package somewhere else first — a pixi
feature of its own, sharing the solve-group — prove it there, record the
verdict beside the declaration, and only then move it. That is exactly the shape
`[feature.spike-storage]` has in `pixi.toml`.

**This half of the rule is a documented obligation, not an automated
assertion.** There is no mechanical test for "a future feature was proposed", so
nothing in the suite can fail when someone skips the fitness check. What *is*
asserted is the outcome of the check that was run: that the spiked package stays
out of the runtime set, that its environment shares the solve-group, and that a
verdict from the closed set of three is recorded beside the declaration
(`tests/unit/test_dependency_policy.py`). Saying so plainly is better than
writing a test that appears to enforce the rule and does not.

`tests/unit/test_dependency_policy.py` asserts all of this against `pixi.toml`
and `pixi.lock`: the channel list, the single package-index entry, the rationale
comments, the exit-condition rule, and that every declared dependency resolves
in the lock to a concrete version *satisfying* what the manifest declares, for
every environment and every platform `[workspace] platforms` names. `libpq` —
the C library `psycopg` links against, and the one the application would
otherwise assume the host provides — is asserted individually. The rest of the C
surface is not enumerated; the general rule is the declaration policy above, not
a test that knows every library by name.

`pixi.lock` is generated. Re-solve it with `pixi install`; never hand-edit it.

### Object storage fitness (R-1)

FR-25's object storage attaches an S3-compatible backend through
`django-storages` and `boto3`. It appears in three of the six selectable
combinations and is expected to be selected by most components, so dropping it
was never an available answer — the risk had to be carried rather than avoided.
Hence the spike, run in Epic 1 rather than in Epic 7, on FR-50's own rule that
fitness is proven before a feature is committed to.

**Verdict: proven with a stated bound.** Recorded 2026-08-16, against
`django-storages` 1.14.6, `boto3` 1.43.65, Django 6.0 and Python 3.14 — the
versions the spike reads back from the installed distributions and asserts, so a
bump to any of them invalidates this verdict rather than inheriting it.

The spike itself runs in no automated path: `.github/workflows/ci.yml` pins
`environments: dev`, and nothing in `pixi run ci` reaches the `spike-storage`
environment. So the version assertion inside the spike is not what holds this
verdict to its runtime — `pixi run ci` is. The gate reads those four versions
back out of the comment in `pixi.toml` and reconciles them against `pixi.lock`
(`test_the_recorded_verdict_names_the_versions_the_lock_resolves`), which is
what fails when a bump is solved but never re-spiked.

What the spike proved, all without a network:

- `storages.backends.s3.S3Storage` imports and instantiates. The legacy
  `storages.backends.s3boto3.S3Boto3Storage` also ships in 1.14.6 and is a
  subclass of it; Epic 7 names the former.
- `STORAGES["default"]` resolves through both
  `django.core.files.storage.storages["default"]` and `default_storage`.
- `save`, `open`, `exists`, `delete`, `url`, `size`, `listdir` and
  `get_available_name` are all present, and each accepts the positional call
  Django 6.0's `Storage` base declares — the minimal one and the maximal one.
  The two keyword calls Django actually makes — `save(…, max_length=…)` from
  `django/db/models/fields/files.py` and `get_available_name(…, max_length=…)`
  from `django/core/files/storage/base.py` — bind as well.
- The private hooks behind the two inherited methods, `_save` and `_open`,
  accept the two-argument call Django's own base class makes to them.
- `boto3` builds its session, resolves the endpoint and assembles a client,
  offline, against the configured `endpoint_url`.
- No `DeprecationWarning` and no `RemovedInDjango*Warning` on import or
  instantiation, checked against freshly re-imported `storages`, `boto3` and
  `botocore`.

**Two of those eight methods say nothing about `django-storages`, and the
verdict says so.** `S3Storage.save` and `S3Storage.open` are the *identical
function objects* as Django 6.0's `Storage.save` and `Storage.open` — the
package overrides `_save` and `_open`, not the public methods. A signature check
of those two therefore compares Django with itself and cannot fail. The set of
inherited methods is frozen in the spike, and the overrides where the real
behaviour lives are checked separately, which is what keeps the remaining six
meaningful.

**`run_checks()` is a weak signal, not proof.** Django does not instantiate a
storage backend during system checks. Setting `STORAGES["default"]["BACKEND"]`
to a module that does not exist and calling `run_checks()` returns an empty
list — verified rather than reasoned about; the only check that reads `STORAGES`
is `staticfiles.checks.check_storages`, and it inspects the `staticfiles` alias.
The leg is kept because the spec mandates it, and it shows that configuring the
backend introduces no *other* check error. It does not show the backend is
check-clean.

**FR-38 is the application's job, and this is the finding Epic 7 Story 7.5 has
to act on.** `django-storages` 1.14.6 reads only two of the five values from the
process environment on its own — `access_key` and `secret_key`, via its internal
`lookup_env` on `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. `endpoint_url`,
`region_name` and `bucket_name` come from **Django settings alone**. The spike
proves it by withholding each option in turn and watching those three come back
`None`, and by putting a value in `settings.AWS_STORAGE_BUCKET_NAME` and
watching it arrive. So "configured from environment variables alone" is
something the *settings module* delivers, by routing those three from
`os.environ` into `STORAGES["default"]["OPTIONS"]` — not something the package
delivers for free. Story 7.5 reproduces that routing, and raises
`django.core.exceptions.ImproperlyConfigured` naming the missing variable rather
than the bare `KeyError` the spike's own helper raises.

**The bound — what is *not* proven.** The round-trip leg (`save` → `exists` →
`open` → `size` → `url` → `delete` against a live S3-compatible endpoint) did
not run. It is armed by `SPIKE_STORAGE_ROUND_TRIP` and no endpoint was stood up.
So the wire protocol against a real bucket is unproven. Set
`SPIKE_STORAGE_ROUND_TRIP=1` together with `AWS_S3_ENDPOINT_URL` and the four
other `AWS_*` variables pointing at a MinIO or S3 endpoint you are willing to
have written to, then re-run `pixi run spike-storage` to close it.

The opt-in is deliberate and it is not a formality. Without it the spike ignores
ambient `AWS_*` values entirely and uses unreachable `.invalid` fallbacks, so
running the documented command cannot reach a bucket a developer's shell or AWS
profile happens to name. When it *is* armed, the leg writes one object under a
key carrying a fresh UUID, having first asserted that key is free, with
`file_overwrite` disabled so a collision is renamed rather than silently
overwritten; teardown deletes both the key it meant to write and whatever name
`save()` returned, so an object created by a `save()` that then raised is still
removed. It touches nothing it did not create. That — rather than "it deletes
what it creates" — is what "leaves the bucket as it found it" means here.

**One divergence, recorded rather than hidden.** `S3Storage` spells Django's
`Storage.listdir(self, path)` as `listdir(self, name)`. It is harmless because
`listdir` is not one of the methods Django calls by keyword — *not* because
Django calls positionally only, which is false: the two `max_length=` call sites
above are keyword calls into this same contract. A rename touching `save`,
`get_available_name` or either `max_length` parameter would break Django itself.
`listdir(path=...)` still raises `TypeError`. The spike freezes the set of such
renames, so a second one fails instead of passing unremarked.

**The escalation ladder, in R-1's own order.** It is written down whether or not
it is triggered, so that the next person meets the order rather than inventing
one:

1. **Spike `1.14.6` against the locked Django and Python** — first, because
   `django-storages` is a thin wrapper over a `boto3` already in the lock and
   Django's `Storage` API has been stable. *This is the step that ran, and it
   passed.*
2. **If that fails, push the conda-forge feedstock**, as was done for
   `django-celery-beat`, under a **time-boxed** package-index exception whose
   exit condition is that build landing. Not triggered.
3. **A component-owned S3 backend** against `django.core.files.storage.Storage`
   is the **last resort**, because a platform product owning its own storage
   backend is a permanent maintenance and security cost. Not triggered.

**A permanent supply-chain exception is not on the list.** Steps 2 and 3 are not
interchangeable and step 2 is not skippable: reaching for a component-owned
backend without first attempting the feedstock push takes on permanent
maintenance to avoid a temporary one.

**Where the verdict lives.** Beside the declaration, in `pixi.toml` under
`[feature.spike-storage.dependencies]`, which is what AC #1 means by "recorded
where the dependency is declared" and what lets Epic 7 Story 7.5 act on it
without re-deriving anything. `django-storages` is deliberately **not** in
`[dependencies]`: a passing verdict authorises Story 7.5 to build the feature,
and moving the declaration into the runtime set is that story's act.

**Removing it, and what that costs.** Epic 7 Story 7.5 moves the
`django-storages` declaration and its verdict comment into the `storage`
feature; Epic 8 Story 8.1 then deletes `[feature.spike-storage]` and the
`spike-storage` environment with it. That deletion is not a one-line edit. Nine
assertions across three test modules name this feature, this directory or this
task and have to move in the same change: six in
`tests/unit/test_dependency_policy.py` (staging, single-table declaration,
solve-group, verdict recorded beside the declaration, verdict-versus-lock
versions, docs-versus-manifest verdict), three in
`tests/unit/test_gate_contract.py` (not a gate step, the task's target file
exists, the gate cannot collect the spike — which asserts `tests/spikes/`
exists), plus the `RECORDED_EXEMPTIONS` entry in
`tests/unit/test_suite_policy.py`, which fails both when its `pytest.skip`
disappears and when a second one appears. The same list is recorded beside the
declaration in `pixi.toml`, which is where the person doing the removal will be
looking.

**Running it.** `pixi run spike-storage`. The spike is not part of the gate — it
needs the `spike-storage` environment, which `pixi run ci` does not use. It
stays out of collection by name: its module is `tests/spikes/spike_*.py`, which
`[tool.pytest.ini_options] python_files` does not match, so the `pytest tests/`
the gate runs never reaches it while a command line that names the file does.
The alternative — `-m "not spike"` on `test-cov` — is closed by AD-20, which
bans narrowing flags on the floor-carrying task.

## Running with no external services

Nothing has to be running alongside the application to develop against it — no
database server, no cache, no broker, no collector. Every deployed dependency
has a local stand-in, and each one is a deliberate choice rather than a default
that happens to work:

| Deployed | Local | Set by |
| --- | --- | --- |
| PostgreSQL | sqlite at `db.sqlite3` | `config/settings/base.py`, when no `DATABASE_URL` or `POSTGRES_DB` is set |
| Redis cache | `LocMemCache` | `config/settings/local.py` |
| Celery and its broker | eager, in-process execution | `CELERY_TASK_ALWAYS_EAGER` in `config/settings/local.py` |

Observability is the exception: it is not substituted at all. The tracer
provider, the instrumentors and the structlog pipeline run locally exactly as
they run deployed — only the export step is absent, so spans are discarded when
they end. See [Observability](observability.md).

Each stand-in trades away something real. sqlite accepts schemas and queries
PostgreSQL rejects; `LocMemCache` never evicts or shares state across
processes; eager Celery never exercises delivery, retries, or argument
serialization. Local success is not by itself evidence that a change works
deployed.

## Database

`config/settings/base.py` selects a backend in this order:

1. `DATABASE_URL`, if set
2. `POSTGRES_DB` (with `POSTGRES_USER`, `POSTGRES_PASSWORD`, and optional
   `POSTGRES_HOST` / `POSTGRES_PORT`)
3. sqlite at `db.sqlite3` in the repository root

`config/settings/production.py` raises `ImproperlyConfigured` if step 3 is
reached in production, so a deployment can never silently come up on sqlite.
Point `DATABASE_URL` at a real PostgreSQL instance whenever you need to check
behaviour the sqlite backend cannot show you.

### The parity gap between local runs and the gate

Local runs use sqlite. **The gate uses PostgreSQL** — `.github/workflows/ci.yml`
declares a `postgres:17` service on the `gate` job and sets `DATABASE_URL` at
job level, so all five steps of `pixi run ci` see it. Nothing in the settings
selects the backend beyond that URL.

That divergence is deliberate. It is risk **R-5** — *local development proves
less than running suggests* — a knowingly traded gap, not a defect. sqlite
accepts schemas and queries PostgreSQL rejects, so a green local suite is
weaker evidence than the same suite green in CI.

The consequence is worth stating plainly: **a failure that reproduces only in
CI is the expected behaviour of this trade.** It is fixed at its source — the
model, the view, the form, or a new migration — never by narrowing the gate.
Skipping such a test, marking it `xfail`, or branching on the engine inside it
would convert a refusal into a warning, which the project forbids.

To reproduce a CI-only failure, run the suite against a real PostgreSQL. The
host port is deliberately not 5432 — that one is often already taken by a local
PostgreSQL — and `--rm` means the container disposes of itself on stop:

```sh
docker rm -f pg-local >/dev/null 2>&1 || true
docker run -d --rm --name pg-local -e POSTGRES_USER=gateuser \
  -e POSTGRES_PASSWORD=gatepass -e POSTGRES_DB=gatedb -p 55432:5432 postgres:17

ready=""
for _ in $(seq 30); do
  docker exec pg-local pg_isready -h localhost -U gateuser -d gatedb && { ready=1; break; }
  sleep 1
done

if [ -n "$ready" ]; then
  DATABASE_URL=postgres://gateuser:gatepass@localhost:55432/gatedb pixi run test-cov
  status=$?
else
  echo "pg-local never became ready; see 'docker logs pg-local'" >&2
  status=1
fi

docker stop pg-local >/dev/null 2>&1
echo "exit status: $status"
```

Three details are load-bearing, and each is there because its absence bites in
the failing case — which is the only case this recipe exists for:

- **The readiness loop records whether it succeeded.** Falling out of it after 30
  seconds and running anyway would test against a database that never came up,
  producing a connection-refused failure that looks nothing like the one you came
  to reproduce.
- **The container is stopped explicitly, on both paths, and nothing calls
  `exit`.** A `trap … EXIT` is wrong here: pasted into an interactive shell it
  fires when the *shell* exits rather than when the run finishes, so it leaves
  the container holding port 55432 for the rest of the session — and leaves the
  trap installed too. A bare `exit` is wrong for the mirror-image reason: it
  would close the shell you pasted into.
- **`pg_isready -h localhost` rather than the bare form**, for the same reason
  the gate uses it: the postgres image's init phase runs a socket-only server
  that answers the bare check while TCP is still closed.

The recipe runs `pixi run test-cov`, not `pixi run ci`. The database behaviour
is what you are reproducing, and `test-cov` is the gate step that exercises it;
the gate's first step is `pre-commit run --all-files`, which reformats and
auto-fixes your working tree, which is not something a debugging recipe should
do behind your back. Run the full `pixi run ci` against the same URL when you
want the gate itself.

`--reuse-db` is set in `pyproject.toml`, which is right for a CI service
container recreated on every run but hides schema drift across repeated local
runs. **After changing a migration, rebuild the test database** rather than
reusing it:

```sh
DATABASE_URL=postgres://gateuser:gatepass@localhost:55432/gatedb \
  pixi run test-cov --create-db
```

Every command here goes through `pixi run`; invoking `pytest` directly picks up
a different environment than the gate uses.

## Tasks

| Task | What it does |
| --- | --- |
| `pixi run runserver` | Django development server |
| `pixi run serve` | Production-like ASGI server (uvicorn, all platforms) |
| `pixi run serve-reload` | The same with autoreload |
| `pixi run migrate` | Apply migrations |
| `pixi run makemigrations` | Generate migrations |
| `pixi run createsuperuser` | Create an admin user |
| `pixi run collectstatic` | Collect static files into `staticfiles/` |
| `pixi run format` | `ruff format` |
| `pixi run lint` | `ruff check` |
| `pixi run typecheck` | `mypy src/` |
| `pixi run test` | Unit tests only (fast) |
| `pixi run test-integration` | Integration tests only |
| `pixi run test-cov` | Full suite, fails under 90% coverage |
| `pixi run spike-storage` | R-1's `django-storages` fitness spike — not part of the gate |
| `pixi run build` | Build the wheel and sdist |
| `pixi run docs` | Build the documentation (`--strict`) |
| `pixi run docs-serve` | Serve the documentation with live reload |
| `pixi run changelog` | Regenerate `CHANGELOG.md` with git-cliff |
| `pixi run ci` | The gate — see below |

`pixi task list` prints this table straight from `pixi.toml`, so it cannot
drift from the manifest.

## The gate

`pixi run ci` is the single entry point to the quality gate. It runs five steps
in this order, stopping at the first failure:

| # | Step | What it checks |
| --- | --- | --- |
| 1 | `precommit` | `ruff format`, `ruff check --fix` and `mypy` over every file |
| 2 | `build` | the package is distributable — catches import and packaging errors |
| 3 | `typecheck` | `mypy` over the whole `src/` tree with the strict `pyproject.toml` settings |
| 4 | `lint` | `ruff` over everything, zero findings |
| 5 | `test-cov` | the full suite, coverage at or above 90% including templates |

The order is fast-fail-first: the static checks run before the suite, so a type
or lint error surfaces without paying to run the tests.

**CI runs exactly this task and nothing else.** The `gate` job in
`.github/workflows/ci.yml` invokes `pixi run ci` and no other step, so the
sequence a developer runs locally and the sequence the pipeline runs are the
same sequence — no step exists only in one of them. No other workflow may run a
gate step on its own: `sonarqube.yml` consumes the gate's `coverage.xml` rather
than measuring the suite again, and `release.yml` runs no quality checks because
the commit it releases has already passed the gate on `main`.

`tests/unit/test_gate_contract.py` asserts all of this against `pixi.toml` and
the workflow files, so the contract fails the build rather than drifting.

The gate job declares a `postgres:17` service and runs against it, so the five
steps above execute against the database the immovable core actually names —
see [the parity gap](#the-parity-gap-between-local-runs-and-the-gate).

A second job in `ci.yml` runs `pixi run test` and then `pixi run test-integration`
across ubuntu, windows and macos. That job claims the reference application runs
on all three platforms; it is not a second gate, and it stays on the sqlite
substitution. The integration leg is there because the unit tests never open a
database connection at all — once the gate moved to PostgreSQL, that leg became
the only place in CI where sqlite is actually exercised rather than merely
configured. The gate itself is ubuntu-only because GitHub Actions `services:`
containers — which the PostgreSQL gate needs — run only on Linux runners, so the
database could not exist on two of that matrix's three legs.

`pixi run ci` must exit 0 before any change is considered done.

## Logging and tracing

Logs are structured via structlog and carry `request_id`, `user_id` and
`trace_id`; OpenTelemetry traces requests, Celery tasks, queries and cache
calls. Both are always on. Use `structlog.get_logger(__name__)` and pass data
as keyword arguments — never the standard library's `logging`.

See [Observability](observability.md) for the environment variables and for how
export behaves without a collector.

## Tests

- `tests/unit/` — no database or network access, and no filesystem access
  beyond reading the repository's own checked-in configuration (`pyproject.toml`,
  `pixi.toml`, `sonar-project.properties` and the like), which several tests
  assert against directly.
- `tests/integration/` — everything else. `tests/integration/conftest.py`
  applies the `integration` marker automatically, so
  `pytest -m "not integration"` selects the fast suite.
- `tests/spikes/` — fitness probes, not part of the suite. Modules are named
  `spike_*.py` so `pytest tests/` does not collect them, each runs in a pixi
  environment of its own, and each is deleted once its question stops
  mattering. There is one today: [Object storage fitness
  (R-1)](#object-storage-fitness-r-1). Its disposition is `machinery` — a spike
  is accelerator work and never travels to a component.

Shared fixtures live in `tests/conftest.py`; `UserFactory` lives in
`tests/factories.py`.

## Serving the application

`runserver` is Django's development server. `pixi run serve` runs uvicorn
against `config.asgi:application`, which is closer to production and works on
Linux, macOS and Windows alike.

Production uses gunicorn with the uvicorn worker class. gunicorn is POSIX-only
and has no conda-forge win-64 build, so `gunicorn` and `uvicorn-worker` are
declared under `[target.linux-64.dependencies]` and
`[target.osx-arm64.dependencies]` rather than in `[dependencies]`. Windows
developers get uvicorn instead; it speaks the same ASGI application, so the
only thing that differs locally is the process manager. If you ever need
multi-worker parity on Windows, `hypercorn` and `granian` are both on
conda-forge and cross-platform.

## Protocols below the URL resolver

`config/asgi.py` exposes Django's ASGI application directly. There is no
scope-dispatching wrapper in front of it, and no protocol handler sits below
Django's URL resolver. That is deliberate, not an omission.

A handler reached beneath the resolver is invisible to any policy expressed
over the URLconf — the allowlist resolves the URLconf and refuses routes by
view callable, and nothing below the resolver can be named that way. An
inherited `websocket_application` that accepted every connection unauthenticated
is exactly the surface this rule exists to prevent.

**The middleware chain is the standing exception, and none of it is a protocol
handler.** Any middleware may answer from `__call__` or `process_request` and
return without calling the rest of the chain, and a response produced that way
never reaches the URL resolver. Four entries in the `MIDDLEWARE` declared in
`config/settings/base.py` can do it:

- `django.middleware.security.SecurityMiddleware` returns an SSL redirect from
  `process_request` when `SECURE_SSL_REDIRECT` is on — it is on in
  `config/settings/production.py`;
- `corsheaders.middleware.CorsMiddleware` answers a CORS preflight `OPTIONS`
  from `check_preflight()` with a bare 200. The short circuit is decided by
  `CORS_URLS_REGEX` (`^/api/.*$`) and the request method alone — not by the
  request's origin, and not by whether the path is a route. The configured
  origin policy is applied *afterwards*, by omitting
  `access-control-allow-origin` from a response that ships either way. So every
  path under `/api/` answers a preflight, including paths the URLconf does not
  define;
- `whitenoise.middleware.WhiteNoiseMiddleware` serves collected static assets
  from `STATIC_ROOT` under a single known prefix;
- `django.middleware.common.CommonMiddleware` raises `PermissionDenied` for a
  `DISALLOWED_USER_AGENTS` match and returns a redirect when `PREPEND_WWW` is
  set, both from `process_request`. Neither setting is set here, so it is inert
  today — but it is armed by a settings change, not by a change to `MIDDLEWARE`.

All four are accepted: they hold no credential or application state and serve no
application data. But they are served surfaces the URLconf does not describe, so
the list has **two** triggers for re-checking it, not one. `MIDDLEWARE` itself
can grow — `config/settings/local.py` already appends
`debug_toolbar.middleware.DebugToolbarMiddleware`, which was checked and does
not short-circuit — and the settings that arm an entry already in the list can
be set without the list changing at all. Any story that claims the URLconf is a
*complete* description of the network surface has to address these explicitly
rather than inherit the claim from this section.

The criterion above is *answering before the resolver runs*. Middleware that
replaces a response after resolution is a different shape and is deliberately
not listed: `allauth.account.middleware.AccountMiddleware`, for one, turns the
resolver's 404 on `/accounts/` into a redirect to the login route. It reaches
the resolver first, so what it acted on is still something the allowlist can
name.

So if this accelerator ever needs a protocol handled below the URL resolver —
WebSockets, raw TCP, a long-lived stream — it arrives as a **designed feature**,
never as an inherited handler:

- it carries its own authentication story, written down, not borrowed from
  Django's session middleware by accident;
- it carries its own entry in the carrier — `accelerator.toml`, the file that
  declares every path's disposition — so the surface is declared where the rest
  of the surface is declared;
- until both exist, `asgi.py` binds exactly one ASGI callable, and it is
  Django's own application, unwrapped.

## Coverage

The gate measures Python **and Django templates** under `src/`, via
`django_coverage_plugin`. Two things are required for template measurement and
both are configured:

- `TEMPLATES[0]["OPTIONS"]["debug"] = True`, set in `config/settings/test.py`.
- `COVERAGE_CORE=ctrace`, set in `[activation.env]` in `pixi.toml`. The plugin
  is a *dynamic* file tracer, which needs `sys.settrace`. On Python 3.12+
  coverage defaults to the `sysmon` core, which does not support such plugins —
  templates are discovered but never traced and silently report 0%.

`template_extensions` is narrowed to `html`; the plugin's default also includes
`txt`, which makes coverage treat stray text files as templates.

Deployment entrypoints (`wsgi.py`, `asgi.py`) are excluded — they carry no
application logic, only the process wiring the WSGI/ASGI server runs before the
first request. This sentence is a third carrier of the exclusion list, after
`[tool.coverage.run] omit` in `pyproject.toml` and `sonar.coverage.exclusions`
in `sonar-project.properties`; `tests/unit/test_asgi_surface.py` asserts that
the three agree, so an entry deleted from one cannot survive here.

Templates are covered by `tests/integration/test_template_rendering.py`, which
drives the real test client. `RequestFactory`-based view tests never render a
response, so without those tests the templates report 0% even though the views
pass.

## Pre-commit

Every hook is `repo: local` and runs the tools from the pixi `dev` feature — all
of them conda-forge packages — so pre-commit can never disagree with
`pixi run lint` / `pixi run typecheck` about versions, and no hook environments are
downloaded or built.

Commit messages are validated by `conventional-commit-hook` at the `commit-msg`
stage, which is what lets git-cliff build the changelog.
