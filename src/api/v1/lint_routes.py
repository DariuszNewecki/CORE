# src/api/v1/lint_routes.py

"""
Lint API endpoint (ADR-054 Phase 1).

POST /v1/lint runs `black --check` + `ruff check` against src/ and
tests/ via will.governance.lint_runner. The response always carries
per-tool stdout/stderr so the CLI can render the actual findings
even when the workflow reports non-zero.

CONSTITUTIONAL: no mind.* / body.* / shared.infrastructure.* imports
here; the lint subprocess work lives behind a Will facade.
"""

from __future__ import annotations

from fastapi import APIRouter

from api.v1.schemas import LintResponse
from shared.logger import getLogger
from will.governance.lint_runner import run_lint


logger = getLogger(__name__)


ROUTER_EXPOSURE = "user-facing"
router = APIRouter(
    prefix="/lint",
    # F-40.1: public — lints the governed repository, a consumer operation
    # (ADR-146 amendment 2026-10-03; CORE-OEM-API §3.12).
)

# ADR-132 D9 (#808): routes confirmed intentionally ungated, with rationale.
INTENTIONALLY_UNGATED: dict[str, str] = {
    "lint_endpoint": (
        "Read-shaped: run_lint() calls only `black --check` and `ruff check` "
        "— verified no --fix flag anywhere in lint_runner.py. Pure analysis, "
        "no src/ writes."
    ),
}


@router.post("", response_model=LintResponse)
# ID: 923355cf-ad6d-446a-865f-539025a11428
async def lint_endpoint() -> dict:
    """Run black --check and ruff check on src/ and tests/.

    Returns 200 with the structured result regardless of pass/fail —
    the response's `ok` field carries the verdict, and `tools.*` carry
    per-tool returncodes and captured output. This avoids the
    "lint findings = HTTP error" anti-pattern; a clean lint and a
    dirty lint are both successful API calls.
    """
    return await run_lint()
