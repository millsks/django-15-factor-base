# Development

## Environment

Dependencies are declared in `pixi.toml` and resolved from **conda-forge**.
`pyproject.toml` carries build metadata and tool configuration only — it does
not declare dependencies.

```sh
pixi install     # create the environment
pixi run bootstrap   # install the git hooks
```

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
| `pixi run migrate` | Apply migrations |
| `pixi run makemigrations` | Generate migrations |
| `pixi run createsuperuser` | Create an admin user |
| `pixi run collectstatic` | Collect static files into `staticfiles/` |
| `pixi run fmt` | `ruff format` |
| `pixi run lint` | `ruff check` |
| `pixi run check` | `mypy src/` |
| `pixi run test` | Unit tests only (fast) |
| `pixi run test-integration` | Integration tests only |
| `pixi run cov` | Full suite, fails under 90% coverage |
| `pixi run build` | Build the wheel and sdist |
| `pixi run docs` | Build the documentation (`--strict`) |
| `pixi run docs-serve` | Serve the documentation with live reload |
| `pixi run changelog` | Regenerate `CHANGELOG.md` with git-cliff |
| `pixi run ci` | The full gate: precommit, build, check, lint, cov |

`pixi run ci` must exit 0 before any change is considered done.

## Tests

- `tests/unit/` — no database, network, or filesystem access.
- `tests/integration/` — everything else. `tests/integration/conftest.py`
  applies the `integration` marker automatically, so
  `pytest -m "not integration"` selects the fast suite.

Shared fixtures live in `tests/conftest.py`; `UserFactory` lives in
`tests/factories.py`.

## Coverage

The gate measures Python under `src/`. Deployment entrypoints (`wsgi.py`,
`asgi.py`, `websocket.py`) are excluded — they contain no logic. Django
template coverage is available via `django_coverage_plugin`; add it back to
`[tool.coverage.run] plugins` in `pyproject.toml` to enable it.

## Pre-commit

Every hook is `repo: local` and runs the tools from the pixi `dev` feature — all
of them conda-forge packages — so pre-commit can never disagree with
`pixi run lint` / `pixi run check` about versions, and no hook environments are
downloaded or built.

Commit messages are validated by `conventional-commit-hook` at the `commit-msg`
stage, which is what lets git-cliff build the changelog.
