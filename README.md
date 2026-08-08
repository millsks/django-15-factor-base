# django-15-factor-base

A Django application accelerator template based on 15 factor application principles.

## Requirements

[pixi](https://pixi.sh) is the only prerequisite. It provisions Python and every
dependency from conda-forge.

## Quick start

```sh
pixi install         # runtime environment
pixi install -e dev  # development toolchain
pixi run bootstrap   # install the git hooks
pixi run migrate     # apply migrations (sqlite by default)
pixi run runserver   # http://127.0.0.1:8000/
```

## Layout

`src/` is the import root — it is on `sys.path` and is deliberately *not* a
package, so `config` and `django_service` import as top-level packages.

```text
src/config/          # settings, urls, wsgi/asgi, celery
src/django_service/  # the application package (users app, templates, static)
tests/unit/          # no database, network, or filesystem
tests/integration/   # marked `integration`
docs/                # mkdocs documentation
```

## Development

```sh
pixi run test              # unit tests (fast)
pixi run test-integration  # integration tests
pixi run test-cov          # full suite, 90% coverage gate
pixi run ci                # the full gate -- must pass before any change is done
pixi run docs-serve        # documentation with live reload
```

Dependencies live in `pixi.toml` and come from conda-forge; `pyproject.toml`
holds build metadata and tool configuration only. The `default` environment
carries runtime dependencies only; `dev` layers the toolchain on top. Tasks
resolve to whichever environment defines them, so `-e` is rarely needed.

See `docs/development.md` for the database configuration and the full task list.

## License

MIT — see [LICENSE](LICENSE).
