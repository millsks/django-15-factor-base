"""Tests for the Celery application module."""

from __future__ import annotations

import logging

from config.celery_app import app
from config.celery_app import config_loggers


def test_celery_app_is_named_for_the_service():
    assert app.main == "django_service"


def test_config_loggers_applies_the_django_logging_config():
    """The setup_logging receiver hands Django's LOGGING dict to dictConfig.

    Celery otherwise installs its own logging config and Django's is ignored.
    """
    config_loggers()
    assert logging.getLogger("django").handlers
