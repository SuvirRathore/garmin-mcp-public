"""Garmin session handling with automatic recovery from a stale OAuth2 token.

garth.resume() loads tokens once at import time. A long-lived process (the MCP
server under Claude Desktop) therefore keeps an OAuth2 token in memory well past
its expiry, and the refresh path fails with a bare HTTP 400. Routing every call
through call() re-reads the token directory and forces a refresh before retrying.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, TypeVar

import garth
from garth.exc import GarthHTTPError

TOKEN_DIR = Path.home() / ".garth"

log = logging.getLogger(__name__)

T = TypeVar("T")

REAUTH_HINT = (
    f"Garmin tokens in {TOKEN_DIR} are no longer usable. "
    "Run `uv run auth_setup.py`, then quit and reopen Claude Desktop."
)


class GarminAuthError(RuntimeError):
    """The stored tokens cannot be recovered; interactive re-auth is required."""


def resume() -> None:
    """Load tokens from disk into the process-wide garth client."""
    garth.resume(str(TOKEN_DIR))


def call(fn: Callable[[], T]) -> T:
    """Run fn, recovering once from an expired in-memory OAuth2 token."""
    try:
        return fn()
    except GarthHTTPError as first:
        log.warning("Garmin call failed (%s); reloading tokens and retrying", first)

    try:
        resume()
        garth.client.refresh_oauth2()
    except (GarthHTTPError, FileNotFoundError) as exc:
        raise GarminAuthError(REAUTH_HINT) from exc

    try:
        return fn()
    except GarthHTTPError as exc:
        raise GarminAuthError(REAUTH_HINT) from exc