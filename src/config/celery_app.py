import os
from typing import Any

from celery import Celery
from celery.signals import setup_logging
from django_structlog.celery.steps import DjangoStructLogInitStep

from config.observability import configure_observability

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

configure_observability()

app = Celery("django_service")

# Carries request_id from the request that enqueued a task into the task's own
# log context, so a task's logs point back at the request that caused it.
app.steps["worker"].add(DjangoStructLogInitStep)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")


# celery ships no `py.typed` marker and conda-forge carries no stub package for
# it, so `ignore_missing_imports` resolves `setup_logging` to `Any` and strict
# mode reports that the decorator erases the annotated signature below.
# `warn_unused_ignores` removes the marker when celery starts publishing types.
@setup_logging.connect  # type: ignore[untyped-decorator]
def config_loggers(*args: Any, **kwargs: Any) -> None:
    """Install Django's LOGGING dict as the worker's logging configuration.

    Celery otherwise replaces it with its own, which would drop the structlog
    processor chain the rest of the application logs through.

    Args:
        *args: Signal arguments, unused.
        **kwargs: Signal keyword arguments, unused.

    """
    from logging.config import dictConfig  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415

    dictConfig(settings.LOGGING)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
