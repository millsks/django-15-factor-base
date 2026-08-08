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

There are two environments. **`default`** holds runtime dependencies only —
Django, Celery, uvicorn and so on — and is what a production image would
install. **`dev`** layers the toolchain (ruff, mypy, pytest, mkdocs, git-cliff)
on top. They share a solve-group, so packages common to both resolve to
identical versions.

**You never need `-e` for a task.** Every task declares `default-environment`,
so `pixi run <task>` resolves without a flag and without prompting. `pixi task
list` shows each task with its description.

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

Every dependency resolves from conda-forge. The only PyPI entry in
`pixi.lock` is the editable install of this project itself.

## Database

`config/settings/base.py` selects a backend in this order:

1. `DATABASE_URL`, if set
2. `POSTGRES_DB` (with `POSTGRES_USER`, `POSTGRES_PASSWORD`, and optional
   `POSTGRES_HOST` / `POSTGRES_PORT`)
3. sqlite at `db.sqlite3` in the repository root

Step 3 is a local-development convenience. `config/settings/production.py`
raises `ImproperlyConfigured` if it is reached in production, so a deployment
can never silently come up on sqlite.

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
| `pixi run build` | Build the wheel and sdist |
| `pixi run docs` | Build the documentation (`--strict`) |
| `pixi run docs-serve` | Serve the documentation with live reload |
| `pixi run changelog` | Regenerate `CHANGELOG.md` with git-cliff |
| `pixi run ci` | The gate: test-cov, lint, typecheck, build |

`pixi task list` prints this table straight from `pixi.toml`, so it cannot
drift from the manifest.

`pixi run ci` must exit 0 before any change is considered done.

## Tests

- `tests/unit/` — no database, network, or filesystem access.
- `tests/integration/` — everything else. `tests/integration/conftest.py`
  applies the `integration` marker automatically, so
  `pytest -m "not integration"` selects the fast suite.

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

Deployment entrypoints (`wsgi.py`, `asgi.py`, `websocket.py`) are excluded —
they contain no logic.

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
