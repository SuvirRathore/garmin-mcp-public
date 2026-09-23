"""Garmin session handling that keeps the tokens in ~/.garth current.

garth-ng refreshes an expired OAuth2 access token in memory, but a session
loaded with garth.resume() never writes the refreshed token back to disk. Each
refresh issues a new refresh token, so after the first one the copy in ~/.garth
is superseded, and Garmin rejects it. The next time Claude Desktop starts the
server it loads that superseded token, and every call fails with
"DI-OAuth2 exchange failed: HTTP Error 400".

call() saves the token whenever it changes. On an auth failure it also reloads
~/.garth and retries once, so a fresh run of auth_setup.py is picked up by the
running server without a restart.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import garth
from garth.exc import GarthException, GarthHTTPError

TOKEN_DIR = Path.home() / ".garth"

log = logging.getLogger(__name__)

T = TypeVar("T")

REAUTH_HINT = (
    f"Garmin tokens in {TOKEN_DIR} are no longer usable. "
    "Run `uv run auth_setup.py` in the repo, then retry; no restart is needed."
)

# garth-ng raises plain GarthException for these, so the message is the only signal.
_AUTH_MESSAGES = ("No valid OAuth2 token", "No token files found", "Legacy OAuth1 tokens")


class GarminAuthError(RuntimeError):
    """The stored tokens cannot be recovered; interactive re-auth is required."""


def resume() -> None:
    """Load tokens from disk into the process-wide garth client."""
    garth.resume(str(TOKEN_DIR))


def call(fn: Callable[[], T]) -> T:
    """Run fn against Garmin, reloading tokens from disk and retrying once on auth failure."""
    try:
        return _run(fn)
    except GarthException as exc:
        if not _is_auth_failure(exc):
            raise
        log.warning("Garmin auth failed (%s); reloading %s and retrying", exc, TOKEN_DIR)

    try:
        resume()
        return _run(fn)
    except GarthException as exc:
        if _is_auth_failure(exc):
            raise GarminAuthError(REAUTH_HINT) from exc
        raise


def _run(fn: Callable[[], T]) -> T:
    """Refresh up front if expired, run fn, and persist the token if it changed."""
    before = garth.client.oauth2_token
    try:
        # Refreshing here, single-threaded, stops DailySummary.list's worker
        # threads from each refreshing with the same refresh token.
        token = garth.client.oauth2_token
        if token is not None and token.expired and not token.refresh_expired:
            garth.client.refresh_token()
        return fn()
    finally:
        if garth.client.oauth2_token is not before:
            garth.save(str(TOKEN_DIR))


def _is_auth_failure(exc: GarthException) -> bool:
    if isinstance(exc, GarthHTTPError):
        status = getattr(getattr(exc.error, "response", None), "status_code", None)
        return exc.msg == "DI-OAuth2 exchange failed" or status == 401
    return exc.msg.startswith(_AUTH_MESSAGES)
