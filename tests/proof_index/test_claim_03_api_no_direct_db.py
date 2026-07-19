# tests/proof_index/test_claim_03_api_no_direct_db.py
"""Proof Index claim 3: the API layer holds no direct database imports.

Standing regression check for docs/proof-index.md claim 3 (#798). Thin
"rule-is-mapped-and-would-fire" assertion: the constitutional rule
`architecture.api.no_direct_database_access` is mapped to the `ast_gate` engine,
forbids the direct session-manager imports, and is scoped to `src/api/`. If the
mapping is deleted or weakened, the claim silently becomes unenforced — this
catches that.
"""

from __future__ import annotations

from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAPPING = _REPO_ROOT / ".intent/enforcement/mappings/architecture/layer_separation.yaml"


def test_api_no_direct_db_rule_is_mapped_and_scoped() -> None:
    mappings = yaml.safe_load(_MAPPING.read_text(encoding="utf-8"))["mappings"]
    rule = mappings["architecture.api.no_direct_database_access"]

    assert rule["engine"] == "ast_gate"
    forbidden = rule["params"]["forbidden"]
    assert any("get_session" in f for f in forbidden), forbidden
    applies_to = rule["scope"]["applies_to"]
    assert any(p.startswith("src/api") for p in applies_to), applies_to
