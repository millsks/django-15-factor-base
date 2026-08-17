from .base import *  # noqa: F403
from .base import INSTALLED_APPS
from .base import MIDDLEWARE
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="TpqsnxPtcoMqj8iXZe7QEHO0LZWjP29KXCIowsta3qyXh17qbe90bYcsELUoVeJo",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]  # noqa: S104

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
# One of FR-18's five substitutions: with no Redis running, the cache is the
# in-process one. What makes it a substitution rather than a different feature is
# that the cache *API* is preserved -- `django.core.cache.cache` behaves the same
# here as it does against the Redis backend production.py configures, so no call
# site may branch on which backend is active. The moment one does, this stops
# being a stand-in and becomes a second code path that local runs never exercise.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    },
}

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

# WhiteNoise
# ------------------------------------------------------------------------------
# http://whitenoise.evans.io/en/latest/django.html#using-whitenoise-in-development
INSTALLED_APPS = ["whitenoise.runserver_nostatic", *INSTALLED_APPS]


# DEBUG APPS
# ------------------------------------------------------------------------------
# django-debug-toolbar and django-extensions are development tooling and ship
# only in the pixi `dev` feature, so they are absent from the runtime
# environment. Importing them unconditionally makes these settings unusable
# there -- Django aborts with ModuleNotFoundError before it can start.
#
# The dev environment sets DJANGO_DEBUG_APPS=True for you (see
# [feature.dev.activation.env] in pixi.toml); everywhere else it defaults off.
DEBUG_APPS = env.bool("DJANGO_DEBUG_APPS", default=False)

if DEBUG_APPS:
    # django-debug-toolbar
    # https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#prerequisites
    INSTALLED_APPS += ["debug_toolbar"]
    # https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#middleware
    MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
    # https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#debug-toolbar-config
    DEBUG_TOOLBAR_CONFIG = {
        "DISABLE_PANELS": [
            "debug_toolbar.panels.redirects.RedirectsPanel",
            # Disable profiling panel due to an issue with Python 3.12+:
            # https://github.com/jazzband/django-debug-toolbar/issues/1875
            "debug_toolbar.panels.profiling.ProfilingPanel",
        ],
        "SHOW_TEMPLATE_CONTEXT": True,
    }
    # https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
    INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]

    # django-extensions
    # https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
    INSTALLED_APPS += ["django_extensions"]
# Celery
# ------------------------------------------------------------------------------
# FR-18's task substitution, and it holds in **all six** valid combinations
# locally -- including the two that selected background task processing. FR-22's
# broker constraint is a statement about *deployment* only: nothing has to be
# running here, because the task body executes in the calling process.
#
# Deployed, the same absence is a conditional refusal (FR-14, Epic 4): a
# component that selected background task processing and came up with no broker
# is misconfigured, not conveniently eager.
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-always-eager
CELERY_TASK_ALWAYS_EAGER = True
# Eager on its own captures a raised exception into the result object, where a
# caller that never inspects `.result` will not see it -- so a task body that
# fails locally would look like one that passed. Propagating is what re-raises it
# in the caller, which is what makes "task bodies are invoked synchronously"
# mean the same thing for failures as it does for successes.
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-eager-propagates
CELERY_TASK_EAGER_PROPAGATES = True
# Your stuff...
# ------------------------------------------------------------------------------
