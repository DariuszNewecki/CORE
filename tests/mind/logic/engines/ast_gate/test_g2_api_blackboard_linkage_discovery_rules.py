# tests/mind/logic/engines/ast_gate/test_g2_api_blackboard_linkage_discovery_rules.py

"""#842 Unit M: 8 AST rules spanning API-auth boundary, blackboard SQL guards,
linkage, artifact discovery, and the action-command pattern.

Every per-file check goes through the real ASTGateEngine.verify() with real
params loaded from the live .intent/enforcement/mappings/ YAML, against a
source file written at a tmp_path-relative location matching the rule's own
applies_to glob. linkage.duplicate_ids is corpus-level (dispatches through
verify_context, not verify()) and already has a dedicated, thorough fixture
pair in test_duplicate_ids_check.py -- cited directly in the registry rather
than duplicated here.

The blackboard SQL-guard fixtures mirror the real guarded idiom read from
src/body/services/blackboard_service/blackboard_proposal_service.py:
revive_findings_for_failed_proposal's WHERE-clause `resolution_mechanism =
'reaudit'` guard (both checks' guard regexes search the full SQL literal, not
just the SET clause, so a WHERE-clause guard is a legitimate pass) and the
SET-clause `resolution_mechanism = 'human'` co-assignment used throughout
mark_indeterminate/update_entry_status's UPDATE statements.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mind.logic.engines.ast_gate.engine import ASTGateEngine
from shared.path_resolver import PathResolver


_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
_MAPPINGS = _REPO_ROOT / ".intent" / "enforcement" / "mappings"


def _load_rule_params(mapping_rel: str, rule_id: str) -> dict:
    path = _MAPPINGS / mapping_rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["mappings"][rule_id]["params"]


async def _verify(tmp_path: Path, rel_path: str, content: str, params: dict):
    engine = ASTGateEngine(path_resolver=PathResolver(repo_root=tmp_path))
    target = tmp_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return await engine.verify(target, params)


# ---------------------------------------------------------------------------
# architecture.api.route_module_must_declare_exposure
# ---------------------------------------------------------------------------


async def test_route_module_must_declare_exposure_fires_when_absent(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/api_auth_boundary.yaml",
        "architecture.api.route_module_must_declare_exposure",
    )
    result = await _verify(
        tmp_path,
        "src/api/v1/widgets_routes.py",
        "from fastapi import APIRouter\n\nrouter = APIRouter(prefix='/widgets')\n",
        params,
    )
    assert not result.ok
    assert any("ROUTER_EXPOSURE" in v for v in result.violations)


async def test_route_module_must_declare_exposure_passes_when_declared(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/api_auth_boundary.yaml",
        "architecture.api.route_module_must_declare_exposure",
    )
    result = await _verify(
        tmp_path,
        "src/api/v1/widgets_routes.py",
        "from fastapi import APIRouter\n\n"
        "ROUTER_EXPOSURE = 'user-facing'\n"
        "router = APIRouter(prefix='/widgets')\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.api.router_exposure_must_match_dependencies
# ---------------------------------------------------------------------------


async def test_router_exposure_enforcement_fires_when_governor_only_ungated(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/api_auth_boundary.yaml",
        "architecture.api.router_exposure_must_match_dependencies",
    )
    result = await _verify(
        tmp_path,
        "src/api/v1/widgets_routes.py",
        "from fastapi import APIRouter\n\n"
        "ROUTER_EXPOSURE = 'governor-only'\n"
        "router = APIRouter(prefix='/widgets')\n",
        params,
    )
    assert not result.ok
    assert any("require_governor" in v for v in result.violations)


async def test_router_exposure_enforcement_passes_when_governor_only_gated(
    tmp_path: Path,
) -> None:
    """Real production idiom (src/api/v1/proposals_routes.py): a governor-only
    router carries require_governor in its APIRouter() dependencies list."""
    params = _load_rule_params(
        "architecture/api_auth_boundary.yaml",
        "architecture.api.router_exposure_must_match_dependencies",
    )
    result = await _verify(
        tmp_path,
        "src/api/v1/widgets_routes.py",
        "from fastapi import APIRouter\n"
        "from api.dependencies import require_governor\n\n"
        "ROUTER_EXPOSURE = 'governor-only'\n"
        "router = APIRouter(prefix='/widgets', dependencies=[require_governor])\n",
        params,
    )
    assert result.ok
    assert result.violations == []


async def test_router_exposure_enforcement_fires_when_user_facing_router_carries_gate(
    tmp_path: Path,
) -> None:
    """The inverse direction: a user-facing PRIMARY router must NOT carry the
    constructor-level gate (per-route gates are the correct mechanism there)."""
    params = _load_rule_params(
        "architecture/api_auth_boundary.yaml",
        "architecture.api.router_exposure_must_match_dependencies",
    )
    result = await _verify(
        tmp_path,
        "src/api/v1/widgets_routes.py",
        "from fastapi import APIRouter\n"
        "from api.dependencies import require_governor\n\n"
        "ROUTER_EXPOSURE = 'user-facing'\n"
        "router = APIRouter(prefix='/widgets', dependencies=[require_governor])\n",
        params,
    )
    assert not result.ok
    assert any("router" in v for v in result.violations)


# ---------------------------------------------------------------------------
# architecture.blackboard.reaudit_requires_reaudit_mechanism
# ---------------------------------------------------------------------------


async def test_reaudit_guard_fires_when_mechanism_predicate_absent(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/blackboard.yaml",
        "architecture.blackboard.reaudit_requires_reaudit_mechanism",
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from sqlalchemy import text\n\n"
        "async def revive(session, entry_id):\n"
        "    return await session.execute(\n"
        "        text(\n"
        "            \"UPDATE core.blackboard_entries \"\n"
        "            \"SET status = 'awaiting_reaudit' \"\n"
        "            \"WHERE id = :entry_id\"\n"
        "        ),\n"
        "        {'entry_id': entry_id},\n"
        "    )\n",
        params,
    )
    assert not result.ok
    assert any("awaiting_reaudit" in v for v in result.violations)


async def test_reaudit_guard_passes_with_where_clause_mechanism_predicate(
    tmp_path: Path,
) -> None:
    """Mirrors the real guard in
    blackboard_proposal_service.py::revive_findings_for_failed_proposal --
    the guard predicate lives in the WHERE clause, not the SET clause, and
    the check's regex searches the full SQL literal so this is a legitimate
    pass, not a gap in the check's reach."""
    params = _load_rule_params(
        "architecture/blackboard.yaml",
        "architecture.blackboard.reaudit_requires_reaudit_mechanism",
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from sqlalchemy import text\n\n"
        "async def revive(session, proposal_id):\n"
        "    return await session.execute(\n"
        "        text(\n"
        "            \"UPDATE core.blackboard_entries \"\n"
        "            \"SET status = 'awaiting_reaudit', updated_at = now() \"\n"
        "            \"WHERE entry_type = 'finding' \"\n"
        "            \"AND resolution_mechanism = 'reaudit' \"\n"
        "            \"AND payload->>'proposal_id' = :proposal_id\"\n"
        "        ),\n"
        "        {'proposal_id': proposal_id},\n"
        "    )\n",
        params,
    )
    assert result.ok
    assert result.violations == []


async def test_reaudit_guard_ignores_unrelated_status_transitions(
    tmp_path: Path,
) -> None:
    """A blackboard_entries UPDATE that never transitions to awaiting_reaudit
    doesn't trip the check at all -- proves the check discriminates on the
    actual target status, not merely on UPDATE-statement presence."""
    params = _load_rule_params(
        "architecture/blackboard.yaml",
        "architecture.blackboard.reaudit_requires_reaudit_mechanism",
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from sqlalchemy import text\n\n"
        "async def close(session, entry_id):\n"
        "    return await session.execute(\n"
        "        text(\"UPDATE core.blackboard_entries SET status = 'resolved' \"\n"
        "             \"WHERE id = :entry_id\"),\n"
        "        {'entry_id': entry_id},\n"
        "    )\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.blackboard.indeterminate_requires_human_mechanism
# ---------------------------------------------------------------------------


async def test_indeterminate_guard_fires_when_human_mechanism_missing(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/blackboard.yaml",
        "architecture.blackboard.indeterminate_requires_human_mechanism",
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from sqlalchemy import text\n\n"
        "async def defer(session, entry_id):\n"
        "    return await session.execute(\n"
        "        text(\n"
        "            \"UPDATE core.blackboard_entries \"\n"
        "            \"SET status = 'indeterminate', updated_at = now() \"\n"
        "            \"WHERE id = :entry_id\"\n"
        "        ),\n"
        "        {'entry_id': entry_id},\n"
        "    )\n",
        params,
    )
    assert not result.ok
    assert any("indeterminate" in v for v in result.violations)


async def test_indeterminate_guard_passes_with_set_clause_human_coassignment(
    tmp_path: Path,
) -> None:
    """Mirrors the real production idiom in
    blackboard_proposal_service.py (mark_indeterminate / update_entry_status):
    `SET status = 'indeterminate', resolution_mechanism = 'human'`."""
    params = _load_rule_params(
        "architecture/blackboard.yaml",
        "architecture.blackboard.indeterminate_requires_human_mechanism",
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from sqlalchemy import text\n\n"
        "async def defer(session, entry_id):\n"
        "    return await session.execute(\n"
        "        text(\n"
        "            \"UPDATE core.blackboard_entries \"\n"
        "            \"SET status = 'indeterminate', \"\n"
        "            \"resolution_mechanism = 'human', updated_at = now() \"\n"
        "            \"WHERE id = :entry_id\"\n"
        "        ),\n"
        "        {'entry_id': entry_id},\n"
        "    )\n",
        params,
    )
    assert result.ok
    assert result.violations == []


async def test_indeterminate_guard_ignores_where_clause_only_filter(
    tmp_path: Path,
) -> None:
    """A statement that merely FILTERS on status='indeterminate' in its WHERE
    clause (not a SET-body transition) must not be flagged -- proves the
    check's SET-body scoping, not just token presence anywhere in the SQL."""
    params = _load_rule_params(
        "architecture/blackboard.yaml",
        "architecture.blackboard.indeterminate_requires_human_mechanism",
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from sqlalchemy import text\n\n"
        "async def resolve(session, entry_id):\n"
        "    return await session.execute(\n"
        "        text(\n"
        "            \"UPDATE core.blackboard_entries \"\n"
        "            \"SET status = 'resolved', updated_at = now() \"\n"
        "            \"WHERE id = :entry_id AND status = 'indeterminate'\"\n"
        "        ),\n"
        "        {'entry_id': entry_id},\n"
        "    )\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# linkage.assign_ids
# ---------------------------------------------------------------------------


async def test_assign_ids_fires_on_public_symbol_without_anchor(
    tmp_path: Path,
) -> None:
    params = _load_rule_params("code/linkage.yaml", "linkage.assign_ids")
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "def public_function():\n    pass\n",
        params,
    )
    assert not result.ok
    assert any("public_function" in v for v in result.violations)


async def test_assign_ids_passes_with_id_anchor(tmp_path: Path) -> None:
    params = _load_rule_params("code/linkage.yaml", "linkage.assign_ids")
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "# ID: 12345678-1234-4123-8123-123456789abc\n"
        "def public_function():\n    pass\n",
        params,
    )
    assert result.ok
    assert result.violations == []


async def test_assign_ids_ignores_private_symbols(tmp_path: Path) -> None:
    """A leading-underscore symbol carries no anchor obligation -- proves the
    check discriminates public/private, not merely 'anchor present or not'."""
    params = _load_rule_params("code/linkage.yaml", "linkage.assign_ids")
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "def _private_helper():\n    pass\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.artifact_discovery_through_registry
# ---------------------------------------------------------------------------


async def test_artifact_discovery_fires_on_hardcoded_extension_glob(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/artifact_discovery.yaml",
        "architecture.artifact_discovery_through_registry",
    )
    result = await _verify(
        tmp_path,
        "src/will/workers/example_worker.py",
        "from pathlib import Path\n\n"
        "def scan(root):\n    return list(Path(root).glob('*.yaml'))\n",
        params,
    )
    assert not result.ok
    assert any("registry" in v for v in result.violations)


async def test_artifact_discovery_passes_when_registry_consulted(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/artifact_discovery.yaml",
        "architecture.artifact_discovery_through_registry",
    )
    result = await _verify(
        tmp_path,
        "src/will/workers/example_worker.py",
        "from pathlib import Path\n"
        "from shared.infrastructure.intent.intent_repository import get_intent_repository\n\n"
        "def scan(root):\n"
        "    types = get_intent_repository().list_artifact_types()\n"
        "    return [p for p in Path(root).glob('*') if p.suffix.lstrip('.') in types]\n",
        params,
    )
    assert result.ok
    assert result.violations == []


async def test_artifact_discovery_ignores_out_of_pipeline_file(
    tmp_path: Path,
) -> None:
    """A file outside the artifact-pipeline prefixes (will/workers,
    mind/governance, mind/coherence, body/services/crawl_service) passes
    trivially via Gate 1 -- location non-applicability, not registry
    compliance. Not cited as the rule's compliant fixture; the dedicated
    registry-consultation test above is."""
    params = _load_rule_params(
        "architecture/artifact_discovery.yaml",
        "architecture.artifact_discovery_through_registry",
    )
    result = await _verify(
        tmp_path,
        "src/cli/commands/example.py",
        "from pathlib import Path\n\n"
        "def scan(root):\n    return list(Path(root).glob('*.yaml'))\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.patterns.action_pattern
# ---------------------------------------------------------------------------


async def test_action_pattern_fires_when_register_action_lacks_atomic_action(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/patterns.yaml", "architecture.patterns.action_pattern"
    )
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "@register_action('example.action')\n"
        "async def example_action(write: bool = False, **kwargs):\n"
        "    pass\n",
        params,
    )
    assert not result.ok
    assert any("atomic_action" in v for v in result.violations)


async def test_action_pattern_fires_when_write_param_defaults_true(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/patterns.yaml", "architecture.patterns.action_pattern"
    )
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "@register_action('example.action')\n"
        "@atomic_action(action_id='example.action', intent='x', impact='WRITE_CODE', policies=[])\n"
        "async def example_action(write: bool = True, **kwargs):\n"
        "    pass\n",
        params,
    )
    assert not result.ok
    assert any("does not default to False" in v for v in result.violations)


async def test_action_pattern_passes_for_correctly_decorated_action(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/patterns.yaml", "architecture.patterns.action_pattern"
    )
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "@register_action('example.action')\n"
        "@atomic_action(action_id='example.action', intent='x', impact='WRITE_CODE', policies=[])\n"
        "async def example_action(write: bool = False, **kwargs):\n"
        "    pass\n",
        params,
    )
    assert result.ok
    assert result.violations == []
