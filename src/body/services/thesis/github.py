# src/body/services/thesis/github.py
"""A small GitHub client for the thesis sensor (REST + GraphQL).

Reads need no token for REST but GitHub's GraphQL API refuses anonymous
calls, and anonymous REST allows 60 calls an hour: without
``CORE_GITHUB_TOKEN`` the measures that need GitHub read as unavailable.
"""

from __future__ import annotations

from typing import Any

import httpx


API = "https://api.github.com"


# ID: 3d919fce-a8ab-4a8b-a0a3-e3dcf26bf581
class GitHubUnavailable(Exception):
    """GitHub could not be asked (no token for GraphQL, or an error)."""


# ID: f6b2d74b-e0a5-47d2-9a8b-1a55ac8f8d10
class GitHub:
    """REST and GraphQL calls against one repository."""

    def __init__(self, repo: str, token: str | None, client: httpx.AsyncClient) -> None:
        self.repo = repo
        self.token = token
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "core-thesis-sensor",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _call(
        self, method: str, url: str, body: dict[str, Any] | None = None
    ) -> httpx.Response:
        try:
            return await self._client.request(
                method, url, headers=self._headers(), json=body, timeout=30
            )
        except httpx.HTTPError as exc:
            raise GitHubUnavailable(f"{method} {url}: {exc}") from exc

    # ID: fd3ba293-7c35-4a4a-9484-9e248914960e
    async def get(self, path: str) -> Any:
        """GET a repository path; raises GitHubUnavailable on any failure."""
        response = await self._call("GET", f"{API}/repos/{self.repo}/{path}")
        if response.status_code != 200:
            raise GitHubUnavailable(f"GET {path}: HTTP {response.status_code}")
        return response.json()

    # ID: c39c1234-ba8f-419f-8c31-b2ad1c98e34d
    async def get_or_none(self, path: str) -> Any:
        """Like get, but a 404 is None (the thing does not exist)."""
        response = await self._call("GET", f"{API}/repos/{self.repo}/{path}")
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise GitHubUnavailable(f"GET {path}: HTTP {response.status_code}")
        return response.json()

    # ID: 5ec61e8a-4754-45f1-a6b7-1788340ab284
    async def get_pages(self, path: str) -> list[Any]:
        """GET a list endpoint, following the Link header to the end."""
        url: str | None = f"{API}/repos/{self.repo}/{path}"
        items: list[Any] = []
        while url:
            response = await self._call("GET", url)
            if response.status_code != 200:
                raise GitHubUnavailable(f"GET {path}: HTTP {response.status_code}")
            items.extend(response.json())
            url = (response.links.get("next") or {}).get("url")
        return items

    # ID: 5430b8b8-f1cb-4ac1-b2fe-f644b8450d5d
    async def send(self, method: str, path: str, body: dict[str, Any]) -> Any:
        """POST or PATCH a repository path (the evidence branch's writes)."""
        if not self.token:
            raise GitHubUnavailable("writing to GitHub needs CORE_GITHUB_TOKEN")
        response = await self._call(method, f"{API}/repos/{self.repo}/{path}", body)
        if response.status_code not in (200, 201):
            raise GitHubUnavailable(
                f"{method} {path}: HTTP {response.status_code} {response.text[:200]}"
            )
        return response.json()

    # ID: 30f0867d-6e1c-42a3-9757-5276ed98dc53
    async def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Run a GraphQL query; GitHub refuses it without a token."""
        if not self.token:
            raise GitHubUnavailable("GitHub's GraphQL API needs CORE_GITHUB_TOKEN")
        response = await self._call(
            "POST", f"{API}/graphql", {"query": query, "variables": variables}
        )
        data = response.json() if response.status_code == 200 else {}
        if response.status_code != 200 or data.get("errors"):
            raise GitHubUnavailable(
                f"GraphQL: HTTP {response.status_code} {data.get('errors')}"
            )
        return data["data"]
