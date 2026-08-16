"""
ASGI config for Django 15-Factor Application Accelerator project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/asgi/

"""

import os

from django.core.asgi import get_asgi_application

# If DJANGO_SETTINGS_MODULE is unset, default to the local settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

# Deliberately below the settings default above: importing this module reads
# DJANGO_SETTINGS_MODULE. The `# noqa: E402` that used to sit here went with the
# `sys.path` insert, whose `SRC_DIR = ...` assignment was what tripped the rule --
# ruff tolerates several things before an import (a docstring, `__future__`,
# conditional blocks, and mutations of `os.environ` *and* `sys.path`), so lint is
# not what would catch a re-added insert. tests/unit/test_import_roots.py is.
from config.observability import configure_observability

configure_observability()

# This application object is used by any ASGI server configured to use this file.
# Django's own handler, exposed directly: every request it serves is resolved by
# the URL resolver, so nothing reaches the network that the route allowlist
# cannot see. See docs/development.md, "Protocols below the URL resolver".
application = get_asgi_application()
