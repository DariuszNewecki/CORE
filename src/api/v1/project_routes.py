# src/api/v1/project_routes.py

"""Project management routes — docs generation and BYOR onboarding (ADR-146 D2).

Exposes:
- POST /project/docs           — generate capability reference documentation
- POST /project/onboard        — deliver machinery floor to an external repo (BYOR Phase A)
- POST /project/onboard/promote — promote a staged machinery floor to target

Scout route (POST /project/scout) lives in scout_routes.py — split for modularity.

CONSTITUTIONAL:
- Session acquired through api.dependencies only.
- CoreContext provided via request.app.state.core_context.
- body.introspection and cli.logic.byor access is the composition-root pattern;
  architecture.api.no_body_bypass is [r].
- No settings imports.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)

ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/project", tags=["Project"])


# ID: 99f391a1-4bc9-4bad-898a-5038b5645f8e
class DocsRequest(BaseModel):
    output: str = "docs/10_CAPABILITY_REFERENCE.md"


# ID: 7325157d-3e9f-4448-8053-6f23261438eb
class OnboardRequest(BaseModel):
    path: str
    write: bool = False
    stage: bool = False


# ID: beb108ad-659a-4928-8a52-84f81e144dd1
class PromoteRequest(BaseModel):
    path: str


@router.post("/docs", summary="Generate capability reference documentation")
# ID: 3891de91-00a6-4067-9702-4eef4159d27e
async def generate_docs(
    body: DocsRequest,
    request: Request,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Generate the canonical Capability Reference from the knowledge graph.

    Fetches public capabilities from core.knowledge_graph and writes
    docs/10_CAPABILITY_REFERENCE.md via FileHandler. The `output` parameter
    is accepted for forward compatibility; the current implementation writes
    to the fixed path docs/10_CAPABILITY_REFERENCE.md.
    """
    from body.introspection.generate_capability_docs import main as _gen_docs

    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    try:
        await _gen_docs(session=session, repo_root=repo_root)
    except Exception as exc:
        logger.error("generate_docs failed: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Doc generation failed: {exc}"
        ) from exc
    return {"output": "docs/10_CAPABILITY_REFERENCE.md", "generated": True}


@router.post("/onboard", summary="Deliver BYOR machinery floor to an external repo")
# ID: dd315c9c-2767-4e95-a350-ee73b04402b0
async def onboard_project(body: OnboardRequest, request: Request) -> dict:
    """Deliver the CORE machinery floor into an external repository (BYOR Phase A).

    Copies META schemas, taxonomies, constitution stub, and enforcement/config
    from examples/starter-intent/.intent/ into <path>/.intent/. Dry-run by default.
    Pass write=true to apply; pass stage=true with write=true to stage for inspection.

    Assumes the CORE API and the caller share the same filesystem.
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
    except SystemExit as exc:
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


@router.post("/onboard/promote", summary="Promote a staged machinery floor to target")
# ID: 940ac03d-68ef-416f-a39a-dc53e868b4e1
async def promote_onboard(body: PromoteRequest, request: Request) -> dict:
    """Promote a staged machinery floor into the target repository (ADR-123 D2).

    Reads from work/staged/<name>/.intent/ and writes to <path>/.intent/.
    Run POST /project/onboard with write=true and stage=true first.
    """
    from cli.logic.byor import promote_staged

    core_context: CoreContext = request.app.state.core_context
    target_path = Path(body.path).resolve()
    try:
        await promote_staged(context=core_context, path=target_path)
    except SystemExit as exc:
        raise HTTPException(
            status_code=400, detail="Promote failed — check CORE logs."
        ) from exc
    except Exception as exc:
        logger.error("promote_onboard failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": str(target_path), "promoted": True}


# Scout endpoint lives in scout_routes.py (split for modularity — ADR-146 D2).
