"""The mapper's one refusal signal.

FR-8 puts every authorization decision behind one mapper, and AD-4 keeps that
mapper free of any protocol. A refusal therefore has to leave here as a plain
Python exception: the DRF Bearer class (Story 2.7) turns it into DRF's 401, the
allauth adapter (Story 2.6) turns it into allauth's, and Epic 3's local sign-in
route turns it into a form error. None of those translations can live in the
mapper without pinning it to one caller, which is why nothing in this package
imports `rest_framework` or raises `AuthenticationFailed`.

One exception type, not a hierarchy. The callers do not branch on the *kind* of
refusal -- every one of them answers 401 -- so a hierarchy would be structure
nothing reads. `reason` carries the detail instead, and it is the string the
caller logs.
"""

from __future__ import annotations

__all__ = ["ClaimsRejected"]


class ClaimsRejected(Exception):  # noqa: N818
    """A set of claims cannot be mapped onto a user.

    Named for what happened rather than with the `Error` suffix ruff's N818
    prefers: this is the refusal half of an authorization decision, and callers
    read it as "these claims were rejected". The suffix would make it look like
    a fault in the component when it is a verdict about the token.

    Attributes:
        reason: Why the claims were refused, in a form fit for a log event. It
            never carries a claim *value* -- an identity key or an email in a
            refusal message is the token leaking into the log.

    """

    def __init__(self, reason: str) -> None:
        """Record the reason and pass it to `Exception` as the message.

        Args:
            reason: Why the claims were refused.

        """
        super().__init__(reason)
        self.reason = reason
