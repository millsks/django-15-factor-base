"""The FR-17 authentication allowlist: the authoritative declaration site.

The nine refusal conditions are a denylist -- refuse these known-bad states --
and a denylist cannot by construction catch a credential path invented next
year. FR-17 inverts that: the component's authentication surface must match an
approved set *exactly*, so a path added later fails the build until somebody
adds it deliberately, which is the moment a human decides whether it belongs.

Three surfaces, one declaration each:

* `ALLOWED_AUTHENTICATION_BACKENDS` -- what `AUTHENTICATION_BACKENDS` may hold.
* `ALLOWED_API_AUTHENTICATION_CLASSES` -- what DRF's default authentication
  classes may hold.
* `ALLOWED_AUTHENTICATION_ROUTE_PREFIXES` -- the route prefixes the component
  itself owns for authentication, admin login and token issuance. Deliberately
  *not* every route: an allowlist covering business routes would break the build
  on the first feature anyone wrote, and would be deleted within a week.

The two class rosters hold **objects, not dotted strings** (AD-26): a string
comparison passes against a name that no longer resolves, and the point of the
check is what the component actually loads.

This module lives here rather than beside the settings it constrains because
AD-26 makes the allowlist part of the refusal contract: an allowlist maintained
apart from the conditions it backstops is the failure FR-17 is a response to.
It is also one declaration with AD-8's contributable-configuration surface,
never two lists kept in step by hand. Epic 7 adds a *mirror* of it in
`accelerator.toml` plus a gate test asserting equality; the carrier is
`machinery` and never travels, so it cannot be the runtime authority for a rule
that executes inside a materialized component.

Empty until Story 4.6 fills it. Created here so that AC #1 -- one module
containing both stages and the allowlist -- is true from the start rather than
from three stories later.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "ALLOWED_API_AUTHENTICATION_CLASSES",
    "ALLOWED_AUTHENTICATION_BACKENDS",
    "ALLOWED_AUTHENTICATION_ROUTE_PREFIXES",
]

#: The authentication backends this component is permitted to install.
ALLOWED_AUTHENTICATION_BACKENDS: Final[tuple[type[object], ...]] = ()

#: The DRF authentication classes this component is permitted to install.
ALLOWED_API_AUTHENTICATION_CLASSES: Final[tuple[type[object], ...]] = ()

#: The route prefixes that make up the component's own authentication surface.
ALLOWED_AUTHENTICATION_ROUTE_PREFIXES: Final[tuple[str, ...]] = ()
