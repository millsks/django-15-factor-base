# Django 15-Factor Base

A Django application accelerator template built on 15-factor application principles.

## Layout

```text
manage.py
pixi.toml            # dependencies (conda-forge) and tasks
pyproject.toml       # build metadata and tool configuration
src/                 # import root -- on sys.path, not a package
  config/            # settings, urls, wsgi/asgi, celery
  django_service/    # the application package
    users/           # the users app
    templates/
    static/
tests/
  unit/              # no database, no network, no filesystem
  integration/       # marked `integration`, exercises real resources
docs/                # this documentation (mkdocs)
```

`src/` is deliberately **not** a package. It is placed on `sys.path` so that
`config` and `django_service` import as top-level packages.

## Quick start

```sh
pixi install
pixi run migrate
pixi run runserver
```

The application boots against sqlite by default. See
[Development](development.md) for the database configuration and the full task
list.
