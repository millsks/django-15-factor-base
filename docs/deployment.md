# Deployment

What a deployment repository needs to know about this component, and where the
component says it.

## The two declarations

Two files describe this project, and they are not interchangeable.

**`component.toml` is the component's statement about itself.** It is `core`: it
ships in the reference application and in every component materialized from it,
so a component always has it. It carries

- `adopted_apps` — the reusable applications this component has adopted, in the
  order the settings composition applies them;
- `selected_features` — which of `celery`, `redis` and `storage` this
  combination selected;
- `[[databases]]` — per alias, whether the database is required and which
  release-stage migration steps to run before new pods serve;
- `[[processes]]` — the process group, with each process's replica count and
  replacement strategy;
- `[[admin_processes]]` — administrative processes, which are deliberately
  *outside* the process group and never declare `COMPONENT_PROCESS`.

**`accelerator.toml` is the accelerator's knowledge about all components.** It is
`machinery`: it stays in this repository and never travels. It carries feature
surfaces, input dispositions, parameter sites, presets, the closed contributable
surface and the pinned verification subset.

The rule for placing anything new:

> A rule the component must obey at **runtime or deploy time** goes in
> `component.toml`. A rule **only the materializer needs** goes in
> `accelerator.toml`.

The reason is not tidiness. `accelerator.toml` does not travel, so a runtime rule
written there is a rule a materialized component cannot read — it would be unable
to adopt a reusable app, declare an extra migration step, or state that a
database is optional, because every one of those rules lived in a file it does
not have. Conversely, a disposition or a preset written into `component.toml`
would ship a materializer concern to every component and give the accelerator two
places to look.

`tests/unit/test_component_declaration.py` enforces the split mechanically: the
top-level key set of `component.toml` must be a subset of `component`,
`adopted_apps`, `selected_features`, `databases`, `processes` and
`admin_processes`. Anything else fails the gate.

`selected_features` is the one entry that looks like an accelerator concern and
is not. The accelerator declares what each feature *is*; `component.toml`
declares which ones *this component has*, and it is the only declaration of that
present when settings are imported in both the reference application and a
materialized component.

## Process model

The component's process types are **pixi tasks**. The deployment repository
invokes them directly:

```sh
pixi run web      # gunicorn + the uvicorn worker class
pixi run worker   # the Celery worker  (only where `celery` is selected)
pixi run beat     # the Celery scheduler (only where `celery` is selected)
```

and enumerates the set with `pixi task list`, which prints each one beside its
description. **There is no Procfile, and none will be added** — a Procfile is a
file the deployment repository may not read, and it would be a second place the
process model is written. Materialized components ship no Dockerfile either, so
`pixi run <process>` against the golden base *is* the invocation path.

`web` exists in all six combinations. `worker` and `beat` exist only where
background task processing is selected, so in `pixi.toml` they sit inside paired
`# feature:celery` / `# /feature:celery` line comments and are removed with the
feature — rather than surviving into a component with no broker that the
deployment repository would then try to run.

Replica counts and replacement strategy are **not** in `pixi.toml`; a task cannot
express them. They are in `component.toml`, one `[[processes]]` entry per process
type:

| Process | Replicas | Replacement |
|---|---|---|
| `web` | the platform's to choose | `rolling` |
| `worker` | the platform's to choose | `rolling` |
| `beat` | exactly `1` | `stop-before-start` |

`beat` is the one that constrains the platform. Its schedule lives in
PostgreSQL, so it is replaceable but never duplicable: a second scheduler
double-enqueues every periodic task, and a default rolling update produces
exactly that second scheduler for the length of the overlap. The replica count
and the replacement strategy are therefore one decision, not two.

`tests/unit/test_process_model.py` reconciles the two files in **both**
directions: every process type `component.toml` names has a matching task, and
every task in the process group is named by `component.toml`. Membership in the
process group is structural — a task is in it when its `env` declares
`COMPONENT_PROCESS`, whatever the task is called.

### The two variables, and which way each one fails

A process task declares `COMPONENT_PROCESS` in its own `env` and declares **no**
`COMPONENT_RUNTIME`, thereby inheriting *deployed*. The two variables fail in
opposite directions, deliberately:

- **Locality fails closed.** An absent or unrecognized `COMPONENT_RUNTIME` means
  *deployed*, so a declaration lost between the manifest and production leaves
  every refusal armed rather than disarmed.
- **Process type fails open.** An absent `COMPONENT_PROCESS` means *not a serving
  process*. Failing it closed would make every command that ran without it a
  serving process — `pixi run migrate` included, which is a release-stage step —
  and it would then refuse on the unapplied-migrations condition and deadlock the
  release. The accepted price is that a serving process started outside the `web`
  task does not fire that refusal.

This is also why `COMPONENT_PROCESS` may not appear in any pixi activation env,
feature-scoped ones included: the golden base runs pixi, so activation env
reaches production, and one placed there would produce that deadlock on every
release.

The grace period is not the component's to state. `web`'s command encodes no
timeout and no port — `GUNICORN_CMD_ARGS` is gunicorn's own injection point for
`--bind`, worker counts and the graceful-shutdown timeout, so the deployment
repository sets them without a component-side flag.

### The deployment platform must set `DJANGO_SETTINGS_MODULE`

It is not optional, and the failure when it is missing is loud rather than
subtle. `config/asgi.py` falls back to `config.settings.local`, and stage-1
condition 1 (`_refuse_the_local_settings_module`) refuses a *deployed* process
that loaded the local settings module. So a platform that forgets the variable
gets a refusal at settings import, not a component quietly serving with
`DEBUG=True`. That is why the entrypoint's fallback is left as it is: it already
fails closed.

`pixi run serve` is **not** a process type. It is the cross-platform local ASGI
server — uvicorn directly, because gunicorn has no conda-forge win-64 build —
and it is invoked as `pixi run -e dev serve`. A deployment runs `web`.

## Reading the declaration

`config.component.load_component_declaration()` parses the file into frozen
records and refuses anything malformed with `ImproperlyConfigured`. It resolves
`component.toml` from its own location rather than from a setting, and imports no
Django settings module, because the settings composition itself is one of its
callers.

The resolution walks up from the loader module — `component/` → `config/` →
`src/` → the directory holding `component.toml`. That holds in the source tree
and in the editable install the component runs from under `pixi run`, which is
where every consumer reads it today. It does **not** hold in a non-editable
install: the wheel is built with `only-include = ["src"]` and the sdist does not
list `component.toml` either, so a component installed from a built distribution
has nothing at that path and the loader raises its ordinary missing-file refusal.
Packaging the declaration into a built distribution is Story 5.6's call — the
component is a payload there — and it is deliberately not settled here.

```python
from config.component import load_component_declaration

declaration = load_component_declaration()
declaration.selected_features  # frozenset({"celery", "redis", "storage"})
declaration.databases[0].migrate  # ("migrate --database default --noinput",)
```

Because `component.toml` is a `core` file that carries lines belonging to a
single feature — the `worker` and `beat` processes exist only where `celery` is
selected — those lines sit inside paired `# feature:celery` / `# /feature:celery`
line comments. That is the only mechanism permitted for removing part of a `core`
file, and it is what keeps the process declarations in step with the pixi tasks
in every combination — `pixi.toml` carries the matching `# feature:celery` region
around its own `worker` and `beat` tasks.

The rule for the process group is that each member declares `COMPONENT_PROCESS`
through the pixi task its `task` field names, which is what
[Process model](#process-model) above describes and what
`tests/unit/test_process_model.py` reconciles in both directions.

## Health endpoints

Two routes, at the root of the component, reachable with no credential:

| Path | Wire it to | Answers |
|---|---|---|
| `/livez` | the **liveness** probe | `200` with a plain-text body while the process is running |
| `/readyz` | the **readiness** probe | `200` with `{"status": "ready", …}` when the process should be routed to, `503` with `{"status": "unready", …}` when it should not |

Both accept `GET` and `HEAD`, answer `405` to anything else, and carry no-cache
headers so nothing between the probe and the process answers on its behalf.

### They are not interchangeable, and swapping them causes an outage

**Wire liveness to the liveness probe and readiness to the readiness probe, never
the reverse.** The two mean deliberately different things, and the platform's
reactions to them are deliberately different too.

`/livez` checks **nothing external**. It opens no database connection, reads no
cache, resolves no user and makes no network call. The process either answers it
or it does not, and "it does not" is the only signal a liveness probe is entitled
to act on — because the action it takes is to *kill the process*. This is why the
endpoint is so aggressively empty: a liveness check that touched the database
would turn a thirty-second database outage into every replica of every component
being restarted at once, which is the failure the split exists to prevent.

`/readyz` checks that **every required database answers**. Failing it removes the
pod from the load balancer's pool and *leaves the process alive*, which is the
correct response to a dependency being briefly unavailable: the component
degrades and then recovers on its own, instead of crash-looping.

Point the liveness probe at `/readyz` and you have built exactly the outage the
two endpoints exist to avoid — the database blinks, every replica fails its
liveness check, and the platform restarts the entire estate.

### Readiness is non-200 from process start until first contact

A process that has booted but has not yet successfully reached its databases
answers `503`. That is a deliberate property, not a startup race: a replica is
not ready because it started, it is ready because it has proved it can talk to
what it needs. The flag is per-process and lives in process memory, so a restart
does not inherit another replica's proof — and nothing about it is shared across
replicas or written to disk.

Give the readiness probe a `failureThreshold` and `initialDelaySeconds` that
tolerate this, and expect the first probe after a start to fail.

A process that has begun shutting down also answers `503`, before it looks at any
database, so that it leaves the routing pool before it finishes its in-flight
work.

### Readiness deliberately does not re-check migrations

`/readyz` opens a cursor on each required alias and issues `SELECT 1`. It does
**not** compare the migration graph against `django_migrations`, run
`migrate --check`, or ask any other question about the schema, and that is a
decision rather than an omission.

During a rolling deploy the release stage migrates *first* and new pods start
*after*, so for the length of the rollout every still-serving replica of the old
generation is running against a newer schema and sees migrations it has not
applied. That state is legitimate — it is precisely what backwards-compatible
migrations are for. A readiness check that compared migration state would report
every one of those replicas unready, drain the whole old generation at once, and
turn a routine migration into an outage.

Migration state *is* checked, once, at process start, by the startup refusal
contract. It is not re-asked on every probe.
`tests/integration/test_health.py` asserts that readiness still answers `200`
with an unapplied migration present, so this cannot regress quietly.

### Which required means what

An alias is required unless `component.toml` declares `required = false` for it
— see [The two declarations](#the-two-declarations). An alias that
`DATABASES` configures and `component.toml` does not declare at all is treated as
required and logged by name; it is never silently skipped.

The response body names every alias it asked:

```json
{"status": "ready", "databases": {"default": "ok"}}
```

### The `Host` header is the deployment repository's to get right

Platform probes commonly send the **pod IP** as the `Host` header rather than a
service name. `ALLOWED_HOSTS` is environment-driven —
`DJANGO_ALLOWED_HOSTS`, read in `config/settings/production.py` — and Django
rejects a request whose `Host` is not in it with `400`, before any view runs. A
probe that gets a `400` reads it as a failure.

So the deployment repository must do one of two things:

- set an explicit `Host` header (or `httpHeaders`) on both probes to a value
  `DJANGO_ALLOWED_HOSTS` contains; or
- include the pod IP range in `DJANGO_ALLOWED_HOSTS`.

**Do not weaken `ALLOWED_HOSTS` in the component to work around this.** A
wildcard baked into the component travels into every component materialized from
it and disables Django's host validation everywhere, in exchange for saving one
line in one manifest.

## Shutdown

On `SIGTERM` the component flips readiness first, and only then drains.

1. The process marks itself draining. `/readyz` answers `503` from that moment
   on, before it looks at any database.
2. The load balancer sees the first `503` and removes the replica from its pool,
   so no new request is routed here.
3. The server stops accepting connections, finishes the requests already in
   flight, and exits.

A Celery worker does the same thing in its own terms: it stops consuming new
messages and finishes the task it is holding.

**The component owns the ordering; the grace period value is the deployment
repository's setting.** The ordering is the half that cannot be configured from
outside — it is what stops the process finishing in-flight work while traffic is
still arriving — and it ships with the component. The two knobs that decide how
long the drain is allowed to take are yours:

| Knob | Where it lives | What it bounds |
|---|---|---|
| the platform's termination grace period | your deployment manifest (`terminationGracePeriodSeconds` on Kubernetes) | how long after `SIGTERM` the platform waits before `SIGKILL` |
| `GUNICORN_CMD_ARGS` | the process environment you set for the `web` process | gunicorn's own `--graceful-timeout`, alongside `--bind` and worker counts |

Set the platform's grace period *longer* than gunicorn's graceful timeout. The
other way round, `SIGKILL` arrives while requests are still being finished and
the drain buys nothing.

### The platform must keep probing readiness during the drain

The flip is only useful if something reads it. A readiness probe whose interval
is longer than the grace period may never run between the `SIGTERM` and the
process exiting, in which case the load balancer removes the replica because it
stopped answering rather than because it said it was draining — which is the
dropped-request window the flip exists to close. Keep `periodSeconds` well
inside the grace period, and let the load balancer deregister on the first `503`
rather than after a failure threshold, so the pool is updated once and early.

### A second `SIGTERM` is a cold shutdown, and that is your choice

Celery treats a second `SIGTERM` as a *cold* shutdown: it stops waiting for the
running task and terminates. The component neither sends that second signal nor
prevents it. Whether one is sent — and how long the platform waits before
sending it — is a deployment-repository decision, made with the same grace period
above, and it is the point at which unfinished work is deliberately abandoned.

### What the component does not decide

The grace period value, the probe interval, and the load balancer's
deregistration behaviour are all outside this repository. Nothing in
`component.toml` or `pixi.toml` states them: `component.toml` carries replica
counts and replacement strategy, `pixi.toml` carries the commands, and neither
carries a timeout. The `web` command encodes no `--graceful-timeout` and the
`worker` command encodes no flag that alters Celery's warm shutdown — no
`--pool=solo`, no `-Ofair` — because both would take the decision away from you.
`tests/unit/test_process_model.py` holds that.
