# src/api/cli/coverage_client.py

"""Coverage namespace sub-client for CoreApiClient (issue #360).

Covers /v1/coverage/* and /v1/tests/interactive. Accessed via the
facade as `core_api_client.coverage`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: c7b169d0-f461-4e65-9633-f7b1becce3f6
class CoverageClient:
    """Sub-client for /coverage/* and /tests/interactive endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP and `self._facade._poll_at_path`
    for polling.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 6b94383f-e5df-426d-bffc-dda33108f230
    async def coverage_check(self) -> dict:
        """GET /v1/coverage/check — constitutional coverage compliance check."""
        return await self._facade._request("GET", "/v1/coverage/check", timeout=300.0)

    # ID: 73677021-be1c-4add-b812-6b0191954bcd
    async def coverage_report(
        self, show_missing: bool = False, output_format: str = "text"
    ) -> dict:
        """GET /v1/coverage/report — pytest --cov report.

        `output_format='text'` (default) returns the term report shape;
        `output_format='html'` triggers `--cov-report=html` and returns
        the `htmlcov/` path in `html_path` (#358).
        """
        return await self._facade._request(
            "GET",
            "/v1/coverage/report",
            params={"show_missing": show_missing, "format": output_format},
            timeout=300.0,
        )

    # ID: 31762641-5b13-47a0-bf1a-68dc14d0c603
    async def coverage_targets(self) -> dict:
        """GET /v1/coverage/targets — constitutional coverage targets."""
        return await self._facade._request("GET", "/v1/coverage/targets")

    # ID: 26fa1d84-8625-4f2b-a72f-ecf08157fc1d
    async def coverage_gaps(self, threshold: float = 75.0, limit: int = 20) -> dict:
        """GET /v1/coverage/gaps — modules below threshold, ranked by deficit."""
        return await self._facade._request(
            "GET",
            "/v1/coverage/gaps",
            params={"threshold": threshold, "limit": limit},
            timeout=300.0,
        )

    # ID: 56ae27a0-5c75-4e23-9537-7c68c34d6795
    async def coverage_history(self, limit: int = 30) -> dict:
        """GET /v1/coverage/history — recent coverage measurements."""
        return await self._facade._request(
            "GET", "/v1/coverage/history", params={"limit": limit}
        )

    # ID: 63eeb7eb-27c0-4cbd-a546-bb563dc4310c
    async def coverage_methods(self) -> dict:
        """GET /v1/coverage/methods — coverage method comparison descriptor."""
        return await self._facade._request("GET", "/v1/coverage/methods")

    # ID: 2f221d29-5a39-4466-b5a7-ad68565e6153
    async def coverage_generate(self, target_file: str, write: bool = False) -> dict:
        """POST /v1/coverage/generate — single-file adaptive test generation."""
        return await self._facade._request(
            "POST",
            "/v1/coverage/generate",
            json={"target_file": target_file, "write": write},
        )

    # ID: 988d0251-117b-4938-86b8-ea0c8ad4956f
    async def coverage_generate_batch(
        self, priority: str = "all", write: bool = False
    ) -> dict:
        """POST /v1/coverage/generate:batch — prioritised batch generation."""
        return await self._facade._request(
            "POST",
            "/v1/coverage/generate:batch",
            json={"priority": priority, "write": write},
        )

    # ID: d58f2fe7-c58b-442c-9f92-4a7ca0bf3aab
    async def get_coverage_run(self, run_id: str) -> dict:
        """GET /v1/coverage/runs/{run_id} — fetch a coverage_runs row."""
        return await self._facade._request("GET", f"/v1/coverage/runs/{run_id}")

    # ID: 11e4f088-509b-4421-8eca-3a079dff76fe
    async def poll_coverage_run(
        self, run_id: str, timeout_seconds: float = 600.0
    ) -> dict:
        """Poll a coverage run until terminal. Test generation can be slow."""
        return await self._facade._poll_at_path(
            f"/v1/coverage/runs/{run_id}", timeout_seconds=timeout_seconds
        )

    # ID: 2100735d-c584-4296-a71a-49c08e26c0f1
    async def tests_interactive(self, target_file: str | None = None) -> dict:
        """POST /v1/tests/interactive — sync interactive test generation."""
        return await self._facade._request(
            "POST",
            "/v1/tests/interactive",
            json={"target_file": target_file},
            timeout=600.0,
        )
