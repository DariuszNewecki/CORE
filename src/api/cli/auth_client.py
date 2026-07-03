# src/api/cli/auth_client.py
"""Auth sub-client for CoreApiClient (ADR-132).

Handles login, logout, and identity queries against /auth/* endpoints.
On a successful login the core_access and core_refresh cookies are
extracted from the Set-Cookie response headers and written to the
persistent CLI session store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from shared.infrastructure.cli_session import clear_session, save_session


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: dafcc5ff-3dfd-4486-a618-cd9ceb8fce79
class AuthClient:
    """Namespace sub-client for /auth endpoints."""

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 5e9df25d-00ce-410d-8624-c82340329059
    async def login(self, email: str, password: str) -> dict[str, Any]:
        """POST /auth/login — obtain tokens and persist to session file."""
        url = f"{self._facade.base_url}/auth/login"
        async with httpx.AsyncClient(timeout=self._facade.timeout) as client:
            response = await client.post(
                url, json={"email": email, "password": password}
            )
            response.raise_for_status()
            access_token = response.cookies.get("core_access", "")
            refresh_token = response.cookies.get("core_refresh", "")
            if access_token:
                save_session(access_token, refresh_token or "")
            return response.json()

    # ID: 209ef33f-414e-4795-8ddb-dc3a36f2c91f
    async def logout(self) -> dict[str, Any]:
        """POST /auth/logout — revoke server-side refresh token and clear local session."""
        session = __import__(
            "shared.infrastructure.cli_session", fromlist=["load_session"]
        ).load_session()
        cookies: dict[str, str] = {}
        if session:
            cookies["core_access"] = session["access_token"]
            if session.get("refresh_token"):
                cookies["core_refresh"] = session["refresh_token"]
        url = f"{self._facade.base_url}/auth/logout"
        async with httpx.AsyncClient(timeout=self._facade.timeout) as client:
            response = await client.post(url, cookies=cookies)
        clear_session()
        try:
            return response.json()
        except Exception:
            return {"message": "Logged out."}

    # ID: a75b94ff-9cdb-417f-a43c-5f5dffc3010f
    async def whoami(self) -> dict[str, Any]:
        """GET /auth/me — return current user identity from JWT."""
        return await self._facade._request("GET", "/auth/me")

    # ID: 9fdbdef4-8734-4029-a169-1032dd426c92
    async def change_password(
        self, current_password: str, new_password: str
    ) -> dict[str, Any]:
        """POST /auth/change-password — set a new password using the current session."""
        return await self._facade._request(
            "POST",
            "/auth/change-password",
            json={"current_password": current_password, "new_password": new_password},
        )
