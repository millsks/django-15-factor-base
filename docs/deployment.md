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
