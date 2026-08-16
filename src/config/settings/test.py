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
