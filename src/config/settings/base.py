# ruff: noqa: ERA001
"""Base settings to build other settings files upon."""

import os
import ssl
from pathlib import Path
from typing import Any

import environ
from django.urls import reverse_lazy

from config.authorization.claims import load_claims_contract
from config.observability.logging import build_logging_config
from config.observability.logging import configure_structlog

# Repository root (holds manage.py, pyproject.toml, .env).
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent.parent
# The django_service package: holds the apps, templates, static and media.
# src/ itself is the import root and is deliberately not a package.
APPS_DIR = BASE_DIR / "src" / "django_service"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "UTC"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#languages
# from django.utils.translation import gettext_lazy as _
# LANGUAGES = [
#     ('en', _('English')),
#     ('fr-fr', _('French')),
#     ('pt-br', _('Portuguese')),
# ]
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
# Kept, and the `sites` app with it. allauth resolves a provider app through
# `SocialApp.objects.on_site(request)` on every lookup, so the table has to
# exist even though AD-31 forbids a row ever being the provider's source.
SITE_ID = 1
# The `Site` domain, environment-driven (AD-31). The data migration that used to
# write it into the database is retired -- see
# django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py --
# because a baked-in domain travels into every deployed component and decides
# what callback URL it advertises. Nothing writes these values to the `Site`
# row: NFR-1 keeps startup free of queries beyond migration state and AD-22
# forbids a boot-time write, so these settings are the source of truth and the
# table exists only for allauth's `on_site` lookup.
SITE_DOMAIN = env.str("COMPONENT_SITE_DOMAIN", default="localhost")
SITE_NAME = env.str("COMPONENT_SITE_NAME", default="localhost")
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

if os.getenv("DATABASE_URL", default=None):
    DATABASES = {"default": env.db("DATABASE_URL")}
elif os.getenv("POSTGRES_DB", default=None):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.str("POSTGRES_DB"),
            "USER": env.str("POSTGRES_USER"),
            "PASSWORD": env.str("POSTGRES_PASSWORD"),
            "HOST": env.str("POSTGRES_HOST", default="postgres"),
            "PORT": env.str("POSTGRES_PORT", default="5432"),
        },
    }
else:
    # Local-development fallback until Postgres is provisioned. Production
    # refuses to boot on sqlite -- see config/settings/production.py.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        },
    }

DATABASES["default"]["ATOMIC_REQUESTS"] = True
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "django.contrib.humanize", # Handy template tags
    "django.contrib.admin",
    "django.forms",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # The OIDC provider that ships with the installed django-allauth
    # distribution (AD-31, FR-4). No second OIDC framework is added, and this
    # entry is never guarded behind an availability check -- AD-24 permits no
    # conditional import, no settings-module inheritance and no
    # `try`/`except ImportError` as a removal mechanism.
    "allauth.socialaccount.providers.openid_connect",
    "django_celery_beat",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "drf_spectacular",
    "django_structlog",
]

LOCAL_APPS = [
    "django_service.users",
    # Your stuff: custom apps go here
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "django_service.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "users:redirect"
# The id the OIDC app is registered under, read here rather than beside
# `SOCIALACCOUNT_PROVIDERS` below because `LOGIN_URL` is built from it. One
# variable, one meaning: the provider block reads this same name.
OIDC_PROVIDER_ID = env.str("COMPONENT_OIDC_PROVIDER_ID", default="oidc")
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
# FR-4 / AC #1: an unauthenticated request to an authenticated page redirects to
# the IdP, never to allauth's local credential form. `reverse_lazy` rather than
# `reverse` because a module-level reverse in a settings file runs before the
# URLconf is loaded. The local account routes are deliberately still installed
# -- deleting them is Story 2.8's, and refusing them at startup is Epic 4's.
LOGIN_URL = reverse_lazy("openid_connect_login", kwargs={"provider_id": OIDC_PROVIDER_ID})
# The claims contract (FR-10, AD-11, AD-12): the identity-key claim, the group
# claim, and the staff- and superuser-conferring groups, each read from a
# COMPONENT_-prefixed variable with no default. Unset stays unset -- an empty
# field means unconfigured, which is what Epic 4's startup check refuses on.
# See config/authorization/claims.py and docs/authentication.md.
CLAIMS_CONTRACT = load_claims_contract(env)

# PASSWORDS
# ------------------------------------------------------------------------------
# PASSWORD_HASHERS is deliberately unset. Authentication is delegated to an
# OpenID Connect provider, so a component never issues or verifies a local
# password and has no reason to prefer one hasher over another -- Django's
# defaults stand. Dropping the Argon2 entry is what lets argon2-cffi leave the
# dependency set.
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # After AuthenticationMiddleware so request.user is resolved and can be
    # bound onto the log context as user_id.
    "django_structlog.middlewares.RequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": [str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "django_service.users.context_processors.allauth_settings",
            ],
        },
    },
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = ['"Kevin Samuel Mills" <millsks@gmail.com>']
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS
# https://cookiecutter-django.readthedocs.io/en/latest/settings.html#other-environment-settings
# Force the `admin` sign in process to go through the `django-allauth` workflow.
# FR-7: this defaults *true*. It arrived from cookiecutter-django defaulting
# false, which left `/admin/` serving Django's own credential form through
# `ModelBackend` with the IdP never involved. The mechanism is unchanged --
# `django_service/users/admin.py` already wraps `admin.site.login` in allauth's
# `secure_admin_login`, which redirects at `LOGIN_URL`; only the default was
# wrong.
DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=True)

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# Everything -- ours, Django's, allauth's, Celery's -- renders through structlog.
# See config/observability/logging.py.
DJANGO_LOG_LEVEL = env.str("DJANGO_LOG_LEVEL", default="INFO")
DJANGO_LOG_FORMAT = env.str("DJANGO_LOG_FORMAT", default="")

LOGGING = build_logging_config(
    debug=DEBUG,
    log_level=DJANGO_LOG_LEVEL,
    log_format=DJANGO_LOG_FORMAT,
)

configure_structlog()

# django-structlog binds request_id and user_id for the life of a request and
# carries request_id into the Celery tasks a request enqueues.
DJANGO_STRUCTLOG_CELERY_ENABLED = True

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
REDIS_SSL = REDIS_URL.startswith("rediss://")

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = REDIS_URL
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#redis-backend-use-ssl
CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE} if REDIS_SSL else None
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_backend
CELERY_RESULT_BACKEND = REDIS_URL
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#redis-backend-use-ssl
CELERY_REDIS_BACKEND_USE_SSL = CELERY_BROKER_USE_SSL
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ["json"]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_TIME_LIMIT = 5 * 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-soft-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_SOFT_TIME_LIMIT = 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-scheduler
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-send-task-events
CELERY_WORKER_SEND_TASK_EVENTS = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_send_sent_event
CELERY_TASK_SEND_SENT_EVENT = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-hijack-root-logger
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_LOGIN_METHODS = {"username"}
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_ADAPTER = "django_service.users.adapters.AccountAdapter"
# https://docs.allauth.org/en/latest/account/forms.html
ACCOUNT_FORMS = {"signup": "django_service.users.forms.UserSignupForm"}
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
# The adapter lives in `config.authorization` beside the mapper it calls. AD-4
# permits `config` to import `django_service` and forbids the reverse, so an
# adapter that has to reach the mapper cannot stay in `django_service`.
SOCIALACCOUNT_ADAPTER = "config.authorization.adapters.OIDCSocialAccountAdapter"
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
SOCIALACCOUNT_FORMS = {"signup": "django_service.users.forms.UserSocialSignupForm"}
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
# Already allauth's default, and stated anyway: with it on, a provider asserting
# a verified address that matches a local row signs that row's owner in. AD-11
# makes `idp_subject` the sole identity key and forbids email standing in for
# it, so this being explicit is what stops a later edit turning email into a
# resolution key without anyone noticing the rule it broke.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
# The OIDC provider, configured from the environment (AD-31, AC #4). Never from
# database-resident `SocialApp` rows: a component forbidden to migrate itself
# could not create one, and configuring the same provider in both places makes
# allauth's `get_app` raise `MultipleObjectsReturned` at login. So nothing in
# this repository creates such a row, and no fixture or instruction asks anyone
# to.
#
# `server_url` is required -- allauth reads `app.settings["server_url"]` with a
# bare subscript, so a missing one is a `KeyError` rather than a graceful
# degradation. Every value is read with `default=""` all the same: an
# unconfigured IdP is refused at startup by Epic 4's stage 1, not by a settings
# module that cannot be imported to be inspected.
#
# `COMPONENT_OIDC_ISSUER` is the single trust anchor (AD-23). Story 2.7 derives
# the JWKS location from this same variable -- there is no second issuer
# setting, and adding one would give the component two answers to "who signs
# these tokens".
#
# Discovery is a *request*-time fetch inside allauth (`openid_config`), which is
# what keeps NFR-1's "startup makes no network call" true with this block
# present. Nothing here, in an `AppConfig.ready()` or in a system check may
# fetch the discovery document.
SOCIALACCOUNT_PROVIDERS = {
    "openid_connect": {
        "APPS": [
            {
                "provider_id": OIDC_PROVIDER_ID,
                "name": env.str("COMPONENT_OIDC_PROVIDER_NAME", default=""),
                "client_id": env.str("COMPONENT_OIDC_CLIENT_ID", default=""),
                "secret": env.str("COMPONENT_OIDC_CLIENT_SECRET", default=""),
                "settings": {
                    "server_url": env.str("COMPONENT_OIDC_ISSUER", default=""),
                    # FR-4 specifies Authorization Code with PKCE. allauth reads
                    # exactly this key (`oauth2.provider.get_pkce_params`) and
                    # falls back to the provider default, which is False --
                    # without the key there is no PKCE.
                    "oauth_pkce_enabled": True,
                },
            },
        ],
    },
}

# django-rest-framework
# -------------------------------------------------------------------------------
# django-rest-framework - https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# django-cors-headers - https://github.com/adamchainz/django-cors-headers#setup
CORS_URLS_REGEX = r"^/api/.*$"

# By Default swagger ui is available only to admin user(s). You can change permission classes to change that
# See more configuration options at https://drf-spectacular.readthedocs.io/en/latest/settings.html#settings
# Annotated because production.py adds a "SERVERS" list of dicts, which a
# value-inferred dict type would reject.
SPECTACULAR_SETTINGS: dict[str, Any] = {
    "TITLE": "Django 15-Factor Application Accelerator API",
    "DESCRIPTION": "Documentation of API endpoints of Django 15-Factor Application Accelerator",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "SCHEMA_PATH_PREFIX": "/api/",
}
# Your stuff...
# ------------------------------------------------------------------------------
