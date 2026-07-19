# tests/proof_index/test_claim_07_governor_route_gating.py
"""Proof Index claim 7: governor-only routes carry the enforcement hook, rule-enforced.

Standing regression check for docs/proof-index.md claim 7 (#798), post-correction.
In OSS mode `require_governor` is a trusted-localhost pass-through (not JWT /
platform_admin / 403); its constitutional value is that the hook is present on
every sensitive route and its placement is rule-enforced, so core-platform can
mount a real guard at the same hook in Console mode.
"""

from __future__ import annotations

import json
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEPS = _REPO_ROOT / "src/api/dependencies.py"
_PROPOSALS = _REPO_ROOT / "src/api/v1/proposals_routes.py"
_LAYER_RULES = _REPO_ROOT / ".intent/rules/architecture/layer_separation.json"


def test_oss_require_governor_is_trusted_localhost_passthrough() -> None:
    assert "require_governor = Depends(_oss_passthrough)" in _DEPS.read_text(encoding="utf-8")


def test_require_governor_hook_wired_on_proposal_mutations() -> None:
    assert "dependencies=[require_governor]" in _PROPOSALS.read_text(encoding="utf-8")


def test_governor_route_placement_rules_present() -> None:
    ids = {r["id"] for r in json.loads(_LAYER_RULES.read_text(encoding="utf-8"))["rules"]}
    assert "architecture.api.router_exposure_must_match_dependencies" in ids
    assert "architecture.api.sensitive_route_must_be_gated" in ids
