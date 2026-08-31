# tests/mind/logic/engines/ast_gate/test_g2_runtime_import_boundary_rules.py

"""#842 Unit K: the 8 runtime_import_boundary blocking rules.

All 8 dispatch to the same ast_gate check_type, RuntimeImportBoundaryCheck
(src/mind/logic/engines/ast_gate/checks/runtime_import_boundary.py), via
the real ASTGateEngine.verify() -- the exact per-file dispatch path a live
audit takes for this check_type. Every pair here loads real params from
the live .intent/enforcement/mappings/ YAML and writes real source files
under an isolated tmp_path tree at a relative path matching the rule's
own applies_to glob, so the fixture is what a real audit would actually
see at that location (not an arbitrary path).

architecture.boundary.embedding_access already has a thorough real-
dispatch violating+compliant pair in
test_engine__ASTGateEngine.py::test_embedding_access_rule_catches_direct_import
-- not duplicated here.

architecture.boundary.llm_client_access's dead excludes (all four
reference a pre-ADR-050 src/body/cli/ layout that no longer exists, plus
a non-existent llm_gate/ package directory) are filed as #857 -- the
rule's own forbidden/applies_to enforcement is unaffected and verified
below; only the mapping's excludes are stale.
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
    """Write `content` at `rel_path` under an isolated tmp_path repo root
    (matching the rule's own applies_to shape) and run it through the
    real ASTGateEngine.verify()."""
    engine = ASTGateEngine(path_resolver=PathResolver(repo_root=tmp_path))
    target = tmp_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return await engine.verify(target, params)


# ---------------------------------------------------------------------------
# architecture.boundary.database_session_access
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# architecture.boundary.embedding_access -- already has a thorough combined
# violating+compliant test in
# test_engine__ASTGateEngine.py::test_embedding_access_rule_catches_direct_import;
# these two add dedicated single-assertion named functions for the registry
# citation, per this unit's "dedicated named fixture functions" requirement.
# ---------------------------------------------------------------------------


async def test_embedding_access_fires_on_embedding_service_import(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml", "architecture.boundary.embedding_access"
    )
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "from shared.utils.embedding_utils import EmbeddingService\n",
        params,
    )
    assert not result.ok
    assert any("EmbeddingService" in v for v in result.violations)


async def test_embedding_access_passes_via_cognitive_adapter(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml", "architecture.boundary.embedding_access"
    )
    result = await _verify(
        tmp_path,
        "src/body/atomic/example2.py",
        "from shared.infrastructure.vector.cognitive_adapter import CognitiveEmbedderAdapter\n",
        params,
    )
    assert result.ok
    assert result.violations == []


async def test_database_session_access_fires_on_get_session_import(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml",
        "architecture.boundary.database_session_access",
    )
    result = await _verify(
        tmp_path,
        "src/mind/logic/engines/example.py",
        "from shared.infrastructure.database.session_manager import get_session\n",
        params,
    )
    assert not result.ok
    assert any("get_session" in v for v in result.violations)


async def test_database_session_access_fires_on_async_session_import(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml",
        "architecture.boundary.database_session_access",
    )
    result = await _verify(
        tmp_path,
        "src/will/agents/example.py",
        "from sqlalchemy.ext.asyncio import AsyncSession\n",
        params,
    )
    assert not result.ok
    assert any("AsyncSession" in v for v in result.violations)


async def test_database_session_access_passes_for_di_only_reference(
    tmp_path: Path,
) -> None:
    """Referencing the session-manager module without importing get_session
    or AsyncSession itself (e.g. DI-supplied session type) is clean."""
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml",
        "architecture.boundary.database_session_access",
    )
    result = await _verify(
        tmp_path,
        "src/mind/logic/engines/example2.py",
        "def run(session):\n    return session\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.boundary.settings_access
# ---------------------------------------------------------------------------


async def test_settings_access_fires_on_settings_import(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml", "architecture.boundary.settings_access"
    )
    result = await _verify(
        tmp_path,
        "src/mind/governance/example.py",
        "from shared.config import Settings\n",
        params,
    )
    assert not result.ok
    assert any("Settings" in v for v in result.violations)


async def test_settings_access_fires_on_settings_instance_import(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml", "architecture.boundary.settings_access"
    )
    result = await _verify(
        tmp_path,
        "src/will/autonomy/example.py",
        "from shared.config import settings\n",
        params,
    )
    assert not result.ok
    assert any("settings" in v for v in result.violations)


async def test_settings_access_passes_without_direct_import(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml", "architecture.boundary.settings_access"
    )
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "def run(config):\n    return config\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.boundary.file_handler_access
# ---------------------------------------------------------------------------


async def test_file_handler_access_fires_on_direct_import(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml",
        "architecture.boundary.file_handler_access",
    )
    result = await _verify(
        tmp_path,
        "src/mind/logic/example.py",
        "from shared.infrastructure.storage.file_handler import FileHandler\n",
        params,
    )
    assert not result.ok
    assert any("FileHandler" in v for v in result.violations)


async def test_file_handler_access_passes_without_direct_instantiation(
    tmp_path: Path,
) -> None:
    """Mind/Will delegate file I/O to Body -- a file with no FileHandler
    import is clean."""
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml",
        "architecture.boundary.file_handler_access",
    )
    result = await _verify(
        tmp_path,
        "src/will/autonomy/example.py",
        "def run():\n    pass\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.boundary.llm_client_access
# ---------------------------------------------------------------------------


async def test_llm_client_access_fires_on_will_agents_import(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml", "architecture.boundary.llm_client_access"
    )
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "from will.agents.coder_agent import CoderAgent\n",
        params,
    )
    assert not result.ok
    assert any("will.agents" in v for v in result.violations)


async def test_llm_client_access_fires_on_llm_client_import(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml", "architecture.boundary.llm_client_access"
    )
    result = await _verify(
        tmp_path,
        "src/mind/logic/engines/example.py",
        "from shared.infrastructure.llm.client import LLMClient\n",
        params,
    )
    assert not result.ok
    assert any("shared.infrastructure.llm.client" in v for v in result.violations)


async def test_llm_client_access_passes_without_ai_invocation(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml", "architecture.boundary.llm_client_access"
    )
    result = await _verify(
        tmp_path,
        "src/body/atomic/example2.py",
        "def run():\n    pass\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.boundary.remediation_write_access
# ---------------------------------------------------------------------------


async def test_remediation_write_access_fires_on_git_service_import(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml",
        "architecture.boundary.remediation_write_access",
    )
    result = await _verify(
        tmp_path,
        "src/will/remediation/example.py",
        "from shared.infrastructure.git_service import GitService\n",
        params,
    )
    assert not result.ok
    assert any("GitService" in v for v in result.violations)


async def test_remediation_write_access_passes_without_git_import(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/privileged_boundaries.yaml",
        "architecture.boundary.remediation_write_access",
    )
    result = await _verify(
        tmp_path,
        "src/will/remediation/example2.py",
        "def run():\n    pass\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.shared.no_layer_imports
# ---------------------------------------------------------------------------


async def test_no_layer_imports_fires_on_mind_import(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/layer_separation.yaml", "architecture.shared.no_layer_imports"
    )
    result = await _verify(
        tmp_path,
        "src/shared/infrastructure/example.py",
        "from mind.governance import audit_context\n",
        params,
    )
    assert not result.ok
    assert any("mind" in v for v in result.violations)


async def test_no_layer_imports_fires_on_will_import(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/layer_separation.yaml", "architecture.shared.no_layer_imports"
    )
    result = await _verify(
        tmp_path,
        "src/shared/infrastructure/example2.py",
        "import will.agents\n",
        params,
    )
    assert not result.ok
    assert any("will" in v for v in result.violations)


async def test_no_layer_imports_passes_for_shared_only_reference(tmp_path: Path) -> None:
    """shared/ is admitted to import shared/ and third-party/stdlib -- not
    mind/body/will."""
    params = _load_rule_params(
        "architecture/layer_separation.yaml", "architecture.shared.no_layer_imports"
    )
    result = await _verify(
        tmp_path,
        "src/shared/infrastructure/example3.py",
        "import shared.logger\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.workers.no_direct_worker_import
# ---------------------------------------------------------------------------


async def test_no_direct_worker_import_fires_on_sibling_worker_import(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/layer_separation.yaml", "architecture.workers.no_direct_worker_import"
    )
    result = await _verify(
        tmp_path,
        "src/will/workers/example.py",
        "from will.workers.other_worker import OtherWorker\n",
        params,
    )
    assert not result.ok
    assert any("will.workers" in v for v in result.violations)


async def test_no_direct_worker_import_passes_via_blackboard_only(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/layer_separation.yaml", "architecture.workers.no_direct_worker_import"
    )
    result = await _verify(
        tmp_path,
        "src/body/workers/example.py",
        "async def run(self):\n    await self.post_finding('x', {})\n",
        params,
    )
    assert result.ok
    assert result.violations == []


async def test_no_direct_worker_import_type_checking_exempt_is_live(
    tmp_path: Path,
) -> None:
    """The rule's own type_checking_exempt: true param is not dead --
    an import inside `if TYPE_CHECKING:` is erased at runtime and does
    not trip the check, confirmed against the real declared value (not
    just the check's own default)."""
    params = _load_rule_params(
        "architecture/layer_separation.yaml", "architecture.workers.no_direct_worker_import"
    )
    assert params.get("type_checking_exempt") is True
    result = await _verify(
        tmp_path,
        "src/will/workers/example2.py",
        (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from will.workers.other_worker import OtherWorker\n"
        ),
        params,
    )
    assert result.ok
    assert result.violations == []
