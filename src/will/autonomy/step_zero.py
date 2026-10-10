# src/will/autonomy/step_zero.py
"""Step 0 of the one flow: the four questions asked before anyone approves.

ADR-168 Amendment 2026-10-10 (A2, R4) and the build plan (U3). For a patch and
its producer's ``retires`` claim, CORE answers:

1. *Why does it exist?* — the proposal's anchor (checked at submission).
2. *What does it retire?* — each claim verified against the patch.
3. *Does it already exist?* — existing code that resembles each new public
   symbol, by vector search over the code index.
4. *Was it already decided?* — ADRs that mention the touched files, and ADRs
   cited by the commits that touched them.

Every answer informs the approver; none refuses on its own (R4). A check that
could not run says so ("unavailable" / None) and is never reported as "found
nothing".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.infrastructure.assistant_surface.law_facts import LawFacts
from shared.infrastructure.git_service import GitService
from shared.infrastructure.intent.test_coverage_paths import load_test_coverage_config
from shared.logger import getLogger
from shared.utils.patch_facts import (
    PatchFacts,
    added_symbol_source,
    read_patch,
    verify_retires,
)


logger = getLogger(__name__)

_LOOK_ALIKE_LIMIT = 5


# ID: 8b5057a6-9c8e-42ca-b68a-40f37e015402
async def build_step_zero_report(
    *,
    patch: str,
    retires: list[str],
    repo_root: Path,
    cognitive_service: Any,
) -> dict[str, Any]:
    """Answer questions 2-4 for *patch*; the anchor (question 1) is the
    proposal's own provenance."""
    facts = read_patch(patch)
    retirement = verify_retires(retires, facts)

    touched = [*facts.added, *facts.modified, *facts.deleted]
    mentions = LawFacts(repo_root).decisions_mentioning(touched).as_dict()
    git = GitService(repo_root)
    history = {p: git.adr_refs_in_history(p) for p in [*facts.modified, *facts.deleted]}

    return {
        "patch": {
            "added": facts.added,
            "modified": facts.modified,
            "deleted": facts.deleted,
            "removed_symbols": facts.removed_symbols,
            "new_public_symbols": facts.new_public_symbols,
        },
        "retires": retirement,
        "retires_all_verified": all(bool(r["verified"]) for r in retirement),
        "decisions": {
            "mentions": mentions["answer"]["mentions"],
            "history": history,
            "limits": mentions["limits"],
        },
        "look_alikes": await find_look_alikes(patch, facts, cognitive_service),
    }


# ID: 2978426d-8d05-4eea-8f36-8b64953fe124
async def find_look_alikes(
    patch: str, facts: PatchFacts, cognitive_service: Any
) -> dict[str, Any]:
    """Existing code resembling each new public non-test symbol.

    ``status``: ``ran``, ``nothing_new`` (no new public symbol outside the
    test tree) or ``unavailable`` (embedding or search failed — ``reason``
    says why; no partial result is presented as complete).
    """
    test_prefix = f"{load_test_coverage_config().get('test_root', 'tests')}/"
    targets = [
        (path, name)
        for path, names in sorted(facts.new_public_symbols.items())
        if not path.startswith(test_prefix)
        for name in names
    ]
    if not targets:
        return {"status": "nothing_new", "reason": None, "symbols": []}

    try:
        qdrant = cognitive_service.qdrant_service
        symbols = []
        for path, name in targets:
            source = added_symbol_source(patch, path, name)
            vector = await cognitive_service.get_embedding_for_code(source)
            if not vector:
                raise RuntimeError(f"no embedding returned for {path}::{name}")
            hits = await qdrant.search(
                collection_name=qdrant.collection_name,
                query_vector=list(vector),
                limit=_LOOK_ALIKE_LIMIT,
            )
            symbols.append(
                {
                    "file": path,
                    "symbol": name,
                    "matches": [
                        {
                            "file": (hit.payload or {}).get("file_path"),
                            "symbol": (hit.payload or {}).get("section"),
                            "score": round(float(hit.score), 3),
                        }
                        for hit in hits
                    ],
                }
            )
    except Exception as exc:
        logger.warning("step_zero: look-alike search unavailable: %s", exc)
        return {"status": "unavailable", "reason": str(exc), "symbols": []}
    return {"status": "ran", "reason": None, "symbols": symbols}
