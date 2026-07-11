# src/api/v1/project_routes.py

"""Project management routes — docs generation, BYOR onboarding, Scout (ADR-146 D2).

Exposes:
- POST /project/docs           — generate capability reference documentation
- POST /project/onboard        — deliver machinery floor to an external repo (BYOR Phase A)
- POST /project/onboard/promote — promote a staged machinery floor to target
- POST /project/scout          — detect signals + induce candidate governance rules (ADR-119 D2)

CONSTITUTIONAL:
- Session acquired through api.dependencies only.
- CoreContext provided via request.app.state.core_context.
- body.introspection, cli.logic.byor, and mind.logic.scout_inducer access is the
  composition-root pattern; architecture.api.no_body_bypass is [r].
- No settings imports.
"""

from __future__ import annotations

from pathlib import Path

import typer
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
    except typer.Exit as exc:
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
    except typer.Exit as exc:
        raise HTTPException(
            status_code=400, detail="Promote failed — check CORE logs."
        ) from exc
    except Exception as exc:
        logger.error("promote_onboard failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": str(target_path), "promoted": True}


# ID: b365f5de-d890-4bea-9a3e-85eb9286a4eb
class ScoutRequest(BaseModel):
    path: str
    reset: bool = False


@router.post("/scout", summary="Detect signals and induce candidate governance rules")
# ID: 9ce3a06c-2789-44df-9adb-97a39ebde632
async def scout_project(body: ScoutRequest, request: Request) -> dict:
    """Detect, suggest, and catalog-match candidate governance rules for a target repo.

    Phase B of ADR-119 (rule induction). Returns ScoutObservations and a list of
    RuleCandidate dicts for the caller to ratify. Does NOT write .intent/ files —
    the caller (CLI) handles interactive ratification and writes using its local
    filesystem access.

    Steps performed by this route:
    1. Extract aggregate AST signals from <path> (ScoutAnalyzer — PARSE phase).
    2. Call ScoutInducer (Mind) via injected cognitive_service to get LLM candidates.
       Falls back to the embedded 4-rule universal menu if LLM is unavailable.
    3. Match each candidate against the enforcement catalog (engine + params + scope).

    Returns {"path": ..., "signals": {...}, "candidates": [...]} where each candidate
    includes rule_id, statement, enforcement, rationale, and optional engine/params/scope
    fields when a catalog match exists.

    Requires Phase A (project onboard) to have delivered .intent/ to the target.
    """
    from body.analyzers.scout_analyzer import ScoutAnalyzer
    from cli.logic.scout import (
        _load_enforcement_catalog,
        _load_fallback_candidates,
        _match_enforcement,
    )

    target_path = Path(body.path).resolve()

    if not (target_path / ".intent").exists():
        raise HTTPException(
            status_code=400,
            detail=(
                f"No .intent/ found at {target_path}. "
                "Run POST /project/onboard with write=true first (Phase A)."
            ),
        )

    inducted_path = target_path / ".intent" / "rules" / "scout_inducted.json"
    if inducted_path.exists() and not body.reset:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Scout-inducted rules already exist at {inducted_path}. "
                "Pass reset=true to re-run Scout."
            ),
        )

    core_context: CoreContext = request.app.state.core_context
    core_root = core_context.git_service.repo_path.resolve()

    # ── 1. Detect ─────────────────────────────────────────────────────────────
    analyzer = ScoutAnalyzer()
    analysis = await analyzer.execute(repo_path=target_path)
    if not analysis.ok:
        raise HTTPException(
            status_code=500,
            detail=f"Signal extraction failed: {analysis.data.get('error')}",
        )

    signals_text: str = analysis.data["signals_text"]
    signals_raw: dict = analysis.data["signals_raw"]

    # ── 2. Suggest ────────────────────────────────────────────────────────────
    candidates: list[dict] = []
    cognitive_service = getattr(core_context, "cognitive_service", None)
    if cognitive_service is not None:
        try:
            from shared.ai.prompt_model import PromptModel
            from shared.path_resolver import PathResolver

            _scout_model = PromptModel.load(
                "scout_rule_inducer",
                prompts_root=PathResolver(core_root).prompts_dir,
            )
            llm_client = await cognitive_service.aget_client_for_role(
                _scout_model.manifest.role
            )
            from mind.logic.scout_inducer import ScoutInducer

            inducer = ScoutInducer(llm_client=llm_client)
            candidates = await inducer.propose(code_signals=signals_text)
        except Exception as exc:
            logger.warning(
                "scout_project: LLM induction failed (%s) — falling back to universal menu.",
                exc,
            )

    if not candidates:
        candidates = _load_fallback_candidates(core_root)

    if not candidates:
        raise HTTPException(
            status_code=500,
            detail="No candidate rules available — LLM unavailable and fallback empty.",
        )

    # ── 3. Match ──────────────────────────────────────────────────────────────
    catalog = _load_enforcement_catalog(core_root)
    candidates = [_match_enforcement(c, catalog) for c in candidates]

    return {
        "path": str(target_path),
        "signals": signals_raw,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "matched": sum(1 for c in candidates if c.get("enforcement_matched")),
    }
