"""
With these settings, tests run faster.
"""

from config.authorization.claims import ClaimsContract
from config.observability.logging import build_logging_config

from .base import *  # noqa: F403
from .base import TEMPLATES
from .base import env

# LOGGING
# ------------------------------------------------------------------------------
# Console rendering at WARNING so the suite's output stays readable; the
# structlog pipeline itself is still exercised.
LOGGING = build_logging_config(debug=False, log_level="WARNING", log_format="console")

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="sYhAdglZfspXonZpMsZIqpgElwZB1hBExBi9le7qOtuacFm2NEYKIjZL7r3eHz45",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# CACHES
# ------------------------------------------------------------------------------
# Declared rather than inherited. Django's own default is already LocMemCache and
# base.py sets no `CACHES` at all, so leaving this out would give the suite the
# right backend for the wrong reason -- an implicit framework default that no
# assertion can distinguish from a deliberate substitution, and that a future
# `CACHES` key in base.py would silently replace.
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    },
}

# Celery
# ------------------------------------------------------------------------------
# The same substitution local.py declares, for the same reason and stated in the
# same place: the suite runs with no broker, and a task's body is expected to run
# in the calling process and to raise into it. Neither of these changes the
# suite's behaviour today -- pytest-django loads these settings and the one task
# test already forces eager execution itself -- which is the point: they make the
# substitution visible to a reader and assertable by a test.
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-always-eager
CELERY_TASK_ALWAYS_EAGER = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-eager-propagates
CELERY_TASK_EAGER_PROPAGATES = True

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# AUTHENTICATION
# ------------------------------------------------------------------------------
# Test fixtures, not defaults. The suite runs against a *configured* contract so
# that it exercises the mapping rather than the unconfigured case, and it does so
# independently of whatever COMPONENT_ variables a developer's shell happens to
# hold. base.py defaults none of these -- see config/authorization/claims.py.
CLAIMS_CONTRACT = ClaimsContract(
    identity_key_claim="sub",
    group_claim="groups",
    staff_group="platform-staff",
    superuser_group="platform-superuser",
)

# DEBUGGING FOR TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore[index]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "http://media.testserver/"
# Your stuff...
# ------------------------------------------------------------------------------
