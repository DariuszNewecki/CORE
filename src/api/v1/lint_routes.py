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

from shared.logger import getLogger
from will.governance.lint_runner import run_lint


logger = getLogger(__name__)


router = APIRouter(prefix="/lint")


@router.post("")
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
