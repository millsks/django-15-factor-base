"""
ASGI config for Django 15-Factor Application Accelerator project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/asgi/

"""

import os
import sys
from pathlib import Path

from django.core.asgi import get_asgi_application

# src/ is the import root: config, users and contrib are top-level packages.
SRC_DIR = Path(__file__).resolve(strict=True).parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# If DJANGO_SETTINGS_MODULE is unset, default to the local settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

from config.observability import configure_observability  # noqa: E402

configure_observability()

# This application object is used by any ASGI server configured to use this file.
# Django's own handler, exposed directly: every request it serves is resolved by
# the URL resolver, so nothing reaches the network that the route allowlist
# cannot see. See docs/development.md, "Protocols below the URL resolver".
application = get_asgi_application()
