"""Read-only client for CapsPlan's data in the user's private iCloud database.

Uses CloudKit Web Services. Every request carries the container's API token
and the user's web auth token. CloudKit answers each request with a new web
auth token and the previous one stops working, so the client always keeps
(and reports) the latest one.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession

from .const import CONTAINER, ENVIRONMENT, SYNC_ZONE

BASE_URL = f"https://api.apple-cloudkit.com/database/1/{CONTAINER}/{ENVIRONMENT}/private"
TOKEN_HEADER = "X-Apple-CloudKit-Web-Auth-Token"
AUTH_ERRORS = {"AUTHENTICATION_REQUIRED", "AUTHENTICATION_FAILED", "ACCESS_DENIED"}


class CapsPlanError(Exception):
    """iCloud could not be reached or answered with an error."""


class CapsPlanAuthError(CapsPlanError):
    """The sign-in is no longer valid; the user has to sign in again."""


class CapsPlanClient:
    """Talks to CloudKit for one signed-in user."""

    def __init__(
        self,
        session: ClientSession,
        api_token: str,
        web_auth_token: str,
        on_token: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> None:
        self._session = session
        self._api_token = api_token
        self.web_auth_token = web_auth_token
        self._on_token = on_token
        # One request at a time: each one replaces the token.
        self._lock = asyncio.Lock()

    async def _request(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            url = (
                f"{BASE_URL}/{path}?ckAPIToken={quote(self._api_token, safe='')}"
                f"&ckWebAuthToken={quote(self.web_auth_token, safe='')}"
            )
            try:
                if body is None:
                    resp = await self._session.get(url, timeout=30)
                else:
                    resp = await self._session.post(url, json=body, timeout=30)
                async with resp:
                    data = await resp.json(content_type=None)
                    new_token = resp.headers.get(TOKEN_HEADER) or (
                        data.get("ckWebAuthToken") if isinstance(data, dict) else None
                    )
                    status = resp.status
            except (TimeoutError, ClientError, ValueError) as err:
                # Never the exception text: some aiohttp errors contain the
                # request URL, and with it the sign-in token.
                raise CapsPlanError(f"iCloud not reachable ({type(err).__name__})") from None

            if new_token and new_token != self.web_auth_token:
                self.web_auth_token = new_token
                if self._on_token is not None:
                    result = self._on_token(new_token)
                    if asyncio.iscoroutine(result):
                        await result

            if not isinstance(data, dict):
                raise CapsPlanError(f"Unexpected answer from iCloud (HTTP {status})")
            code = data.get("serverErrorCode")
            if status == 421 or code in AUTH_ERRORS:
                raise CapsPlanAuthError(data.get("reason") or code or "sign-in expired")
            if code:
                raise CapsPlanError(f"{code}: {data.get('reason', '')}")
            if status >= 400:
                raise CapsPlanError(f"HTTP {status}")
            return data

    async def current_user(self) -> str:
        """The signed-in user's record name (checks the sign-in)."""
        data = await self._request("users/current")
        return data.get("userRecordName", "")

    async def zone_changes(self, sync_token: str | None) -> tuple[list[dict[str, Any]], str | None]:
        """All records changed since ``sync_token`` (all records when None)
        and the token to continue from next time."""
        records: list[dict[str, Any]] = []
        token = sync_token
        for _ in range(200):  # safety net against an endless "moreComing"
            zone: dict[str, Any] = {"zoneID": {"zoneName": SYNC_ZONE}}
            if token:
                zone["syncToken"] = token
            data = await self._request("changes/zone", {"zones": [zone]})
            zones = data.get("zones") or []
            if not zones:
                break
            result = zones[0]
            code = result.get("serverErrorCode")
            if code == "ZONE_NOT_FOUND":
                # Sync was never switched on for this Apple ID.
                return [], None
            if code in AUTH_ERRORS:
                raise CapsPlanAuthError(result.get("reason") or code)
            if code:
                raise CapsPlanError(f"{code}: {result.get('reason', '')}")
            records.extend(result.get("records") or [])
            token = result.get("syncToken") or token
            if not result.get("moreComing"):
                break
        return records, token
