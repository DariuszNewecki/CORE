# src/api/v1/scout_routes.py

"""Scout Phase B HTTP route — rule induction for a target repo (ADR-119 / ADR-146 D2).

Exposes:
- POST /project/scout — detect signals + induce candidate governance rules

CONSTITUTIONAL:
- CoreContext provided via request.app.state.core_context.
- body.analyzers.scout_analyzer and mind.logic.scout_inducer accessed as
  composition-root imports; architecture.api.no_body_bypass is [r].
- No settings imports.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)

ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/project", tags=["Project"])


# ID: a1b808e0-9e6b-490f-ad22-468369f92cdb
class ScoutRequest(BaseModel):
    path: str
    reset: bool = False


@router.post("/scout", summary="Detect signals and induce candidate governance rules")
# ID: 8bfc1844-6f15-42d2-aae7-d98090598702
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
