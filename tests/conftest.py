"""Fixtures shared by the unit suite and the integration suite.

`no_network` lives here rather than in `tests/unit/conftest.py` because both
halves of FR-23 need it: the boot assertions are unit tests and the persona
seeding assertion is an integration test against a real database.
"""

from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import TYPE_CHECKING
from typing import Any
from typing import Final
from typing import NoReturn

import pytest

from tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django_service.users.models import User


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db) -> User:
    return UserFactory.create()


class NetworkAccessAttempted(BaseException):
    """Something running under `no_network` tried to open an outbound connection.

    Narrow and named rather than a bare `RuntimeError`, so a test that fails
    because the code under test reached the network is distinguishable at a
    glance from a test that failed for any other reason.

    Derived from `BaseException` rather than `Exception` so that it cannot be
    swallowed. Boot-time code that wraps a call in `except Exception` would
    otherwise absorb the refusal, boot would complete, and every negative
    assertion in `tests/unit/test_no_network_at_boot.py` would pass while boot
    actually reached the network -- the one failure mode a guard like this must
    not have.

    Named for what happened rather than with the `Error` suffix ruff's N818
    prefers, matching `config/authorization/exceptions.py`: what a reader needs
    from the name is the event, and "an access was attempted" is the finding.
    """


#: The methods on `socket.socket` the guard replaces. Both are *inherited* from
#: `_socket.socket` rather than defined on `socket.socket`, which is why the
#: guard below restores them by hand: `monkeypatch.setattr` would record the
#: inherited implementation and "undo" by binding it as an own attribute of the
#: subclass -- leaving the class in a state it was never in.
_GUARDED_SOCKET_METHODS: Final = ("connect", "connect_ex")

#: The module-level `socket` functions the guard replaces. `create_connection`
#: is the connect chokepoint; `getaddrinfo` and `gethostbyname` are the resolver
#: chokepoints, and a hostname lookup is a network round trip that reaches no
#: `socket.socket` at all.
_GUARDED_SOCKET_FUNCTIONS: Final = ("create_connection", "getaddrinfo", "gethostbyname")

#: Distinguishes "the class had no own attribute of that name" from "it had one
#: whose value happened to be None". `delattr` is the correct teardown for the
#: first; `setattr` is the correct teardown for the second.
_ABSENT: Final = object()


def _refuse(address: object) -> NoReturn:
    """Refuse one outbound connection, naming where it was headed.

    Args:
        address: Whatever the caller passed as the destination.

    Raises:
        NetworkAccessAttempted: Always. The address is in the message because
            "something opened a socket" is not a finding a reader can act on,
            and the host it was opened to usually is.

    """
    message = f"a network connection to {address!r} was attempted while the no_network guard was installed"
    raise NetworkAccessAttempted(message)


def _refuse_socket_method(_self: socket.socket, address: object, *_args: Any, **_kwargs: Any) -> NoReturn:
    """Stand in for `socket.socket.connect` and `socket.socket.connect_ex`."""
    _refuse(address)


def _refuse_socket_function(address: object, *_args: Any, **_kwargs: Any) -> NoReturn:
    """Stand in for the module-level `socket` functions, whose first argument is the destination."""
    _refuse(address)


@contextmanager
def _network_guard() -> Iterator[None]:
    """Install the refusals, then restore exactly what was installed.

    Each replacement is recorded only once it has actually been made, and the
    restore walks that record rather than the declared name lists -- so a
    failure part-way through installation leaves nothing behind process-wide.

    Yields:
        None. The guard is the effect.

    """
    saved_methods: dict[str, Any] = {}
    saved_functions: dict[str, Any] = {}
    try:
        for name in _GUARDED_SOCKET_METHODS:
            original = socket.socket.__dict__.get(name, _ABSENT)
            setattr(socket.socket, name, _refuse_socket_method)
            saved_methods[name] = original
        for name in _GUARDED_SOCKET_FUNCTIONS:
            original = getattr(socket, name)
            setattr(socket, name, _refuse_socket_function)
            saved_functions[name] = original
        yield
    finally:
        for name, original in saved_methods.items():
            if original is _ABSENT:
                delattr(socket.socket, name)
            else:
                setattr(socket.socket, name, original)
        for name, original in saved_functions.items():
            setattr(socket, name, original)


@pytest.fixture
def no_network() -> Iterator[None]:
    """Fail the test, loudly and by address, if anything opens a socket.

    Guarded at the socket layer rather than at `requests`, `urllib` or `httpx`:
    a guard installed on one library proves nothing about the library the code
    actually reached for, and OpenTelemetry's exporters, allauth and PyJWT do
    not all use the same one. `socket.socket.connect`, `socket.socket.connect_ex`,
    `socket.create_connection`, `socket.getaddrinfo` and `socket.gethostbyname`
    are the chokepoints every one of them goes through.

    **What it cannot see.** Connectionless UDP -- `sendto` and `sendmsg` on an
    unconnected socket -- is not guarded, because nothing in this stack sends
    UDP. Network I/O performed inside a C extension is outside its reach
    altogether: libpq above all does its own socket work in C and never touches
    Python's `socket` module, so a PostgreSQL connection is invisible here.

    **Never autouse.** `tests/integration/test_import_resolution.py` opens real
    `AF_INET` sockets to find a free port and to wait for a served subprocess to
    accept connections; a global guard would fail those outright, and blocking a
    test's own infrastructure masks a real dependency rather than asserting one.
    Loopback is blocked along with everything else, and nothing that requests
    this fixture needs an exemption: the Django test client opens no socket, and
    sqlite opens no socket.

    Yields:
        None. The guard is the effect.

    """
    with _network_guard():
        yield
