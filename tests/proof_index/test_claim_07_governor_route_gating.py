# tests/proof_index/test_claim_07_governor_route_gating.py
"""Proof Index claim 7: governor-only routes carry the enforcement hook, rule-enforced.

Standing regression check for docs/proof-index.md claim 7 (#798), post-correction.
`require_governor` is live (ADR-132 D10.3 as amended): it passes only for the
bound governor on CORE's Unix socket. Its placement on every sensitive route is
rule-enforced. Behaviour is proven in tests/api/test_dependencies_require_governor.py.
"""

from __future__ import annotations

import json
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEPS = _REPO_ROOT / "src/api/dependencies.py"
_PROPOSALS = _REPO_ROOT / "src/api/v1/proposals_routes.py"
_LAYER_RULES = _REPO_ROOT / ".intent/rules/architecture/layer_separation.json"


def test_require_governor_is_the_live_gate() -> None:
    source = _DEPS.read_text(encoding="utf-8")
    assert "require_governor = Depends(get_governor)" in source
    assert "_oss_passthrough" not in source


def test_require_governor_hook_wired_on_proposal_mutations() -> None:
    assert "dependencies=[require_governor]" in _PROPOSALS.read_text(encoding="utf-8")


def test_governor_route_placement_rules_present() -> None:
    ids = {
        r["id"] for r in json.loads(_LAYER_RULES.read_text(encoding="utf-8"))["rules"]
    }
    assert "architecture.api.router_exposure_must_match_dependencies" in ids
    assert "architecture.api.sensitive_route_must_be_gated" in ids
