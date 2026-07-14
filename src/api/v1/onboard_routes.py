# src/api/v1/onboard_routes.py

"""BYOR onboarding routes — machinery-floor delivery + promotion (ADR-123 D2 / ADR-146 D2).

Exposes:
- POST /project/onboard         — deliver machinery floor to an external repo (BYOR Phase A)
- POST /project/onboard/promote — promote a staged machinery floor to target

Split from project_routes.py for modularity (modularity.needs_refactor, #782):
these two routes are the cohesive BYOR-onboarding concern (cli.logic.byor,
filesystem writes, typer.Exit handling), distinct from the capability-docs
generation concern that remains in project_routes.py. Mirrors the earlier
scout_routes.py extraction from the same file.

CONSTITUTIONAL:
- CoreContext provided via request.app.state.core_context.
- cli.logic.byor accessed as a composition-root import;
  architecture.api.no_body_bypass is [r].
- No settings imports.
"""

from __future__ import annotations

from pathlib import Path

import typer
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.dependencies import require_governor
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)

ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/project", tags=["Project"])


# ID: 7325157d-3e9f-4448-8053-6f23261438eb
class OnboardRequest(BaseModel):
    path: str
    write: bool = False
    stage: bool = False


# ID: beb108ad-659a-4928-8a52-84f81e144dd1
class PromoteRequest(BaseModel):
    path: str


@router.post(
    "/onboard",
    summary="Deliver BYOR machinery floor to an external repo",
    dependencies=[require_governor],
)
# ID: dd315c9c-2767-4e95-a350-ee73b04402b0
async def onboard_project(body: OnboardRequest, request: Request) -> dict:
    """Deliver the CORE machinery floor into an external repository (BYOR Phase A).

    Copies META schemas, taxonomies, constitution stub, and enforcement/config
    from examples/starter-intent/.intent/ into <path>/.intent/. Dry-run by default.
    Pass write=true to apply; pass stage=true with write=true to stage for inspection.

    Requires the caller and the CORE API to be co-located on the same host/
    filesystem: `path` is resolved and written on the API host, not the
    caller's machine. This is not a convenience assumption but a consequence
    of ADR-054 D3 (core-api is loopback-bound, single-operator, no auth) —
    a remote consumer CLI (ADR-146 D2) cannot safely direct writes to an
    arbitrary server-side path without authentication, which loopback-only
    Phase 1 does not provide. See F-1, `.specs/planning/archive/CORE-CLI-2.9.0-Followups.md`.
    """
    from cli.logic.byor import _stage_dir_for, initialize_repository

    core_context: CoreContext = request.app.state.core_context
    target_path = Path(body.path).resolve()

    stage_dir: Path | None = None
    if body.stage and body.write:
        core_root = core_context.git_service.repo_path.resolve()
        stage_dir = _stage_dir_for(core_root, target_path)

    if body.stage and not body.write:
        return {
            "path": str(target_path),
            "mode": "dry-run",
            "note": "--stage has no effect without --write",
        }

    try:
        await initialize_repository(
            context=core_context,
            path=target_path,
            dry_run=not body.write,
            stage_dir=stage_dir,
        )
    except (SystemExit, typer.Exit) as exc:
        # typer.Exit is click.exceptions.Exit -> RuntimeError -> Exception, NOT
        # SystemExit (Typer 0.16), despite the name — byor.py's known failure
        # modes all raise typer.Exit, so catching SystemExit alone here silently
        # let every one of them fall through to the 500 branch below.
        raise HTTPException(
            status_code=400, detail="Onboard failed — check CORE logs."
        ) from exc
    except Exception as exc:
        logger.error("onboard_project failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    mode = "staging" if stage_dir else ("write" if body.write else "dry-run")
    return {
        "path": str(target_path),
        "mode": mode,
        "stage_dir": str(stage_dir) if stage_dir else None,
    }


@router.post(
    "/onboard/promote",
    summary="Promote a staged machinery floor to target",
    dependencies=[require_governor],
)
# ID: 940ac03d-68ef-416f-a39a-dc53e868b4e1
async def promote_onboard(body: PromoteRequest, request: Request) -> dict:
    """Promote a staged machinery floor into the target repository (ADR-123 D2).

    Reads from work/staged/<name>/.intent/ and writes to <path>/.intent/.
    Run POST /project/onboard with write=true and stage=true first.

    Requires the caller and the CORE API to be co-located on the same host/
    filesystem — same constraint as POST /project/onboard; see that docstring
    and F-1 in `.specs/planning/archive/CORE-CLI-2.9.0-Followups.md`.
    """
    from cli.logic.byor import promote_staged

    core_context: CoreContext = request.app.state.core_context
    target_path = Path(body.path).resolve()
    try:
        await promote_staged(context=core_context, path=target_path)
    except (SystemExit, typer.Exit) as exc:
        raise HTTPException(
            status_code=400, detail="Promote failed — check CORE logs."
        ) from exc
    except Exception as exc:
        logger.error("promote_onboard failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": str(target_path), "promoted": True}
