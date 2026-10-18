# tests/mind/logic/engines/ast_gate/test_layer_separation_rules.py
"""Mind/Body/Will layer separation (.intent/rules/architecture/layer_separation.json):
one violating and one compliant fixture per rule, made blocking 2026-10-18.

Every check goes through the real engine (ASTGateEngine, GlobGateEngine for
layer_exclusivity) with the rule's live params from
.intent/enforcement/mappings/architecture/layer_separation.yaml, against a
source file at a path the rule's applies_to covers.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mind.logic.engines.ast_gate.engine import ASTGateEngine
from mind.logic.engines.glob_gate import GlobGateEngine
from shared.path_resolver import PathResolver


_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
_MAPPING = (
    _REPO_ROOT
    / ".intent"
    / "enforcement"
    / "mappings"
    / "architecture"
    / "layer_separation.yaml"
)


def _params(rule_id: str) -> dict:
    return yaml.safe_load(_MAPPING.read_text(encoding="utf-8"))["mappings"][rule_id][
        "params"
    ]


async def _verify(tmp_path: Path, rule_id: str, rel_path: str, content: str):
    engine = ASTGateEngine(path_resolver=PathResolver(repo_root=tmp_path))
    target = tmp_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "from __future__ import annotations\n\n" + content, encoding="utf-8"
    )
    return await engine.verify(target, _params(rule_id))


async def test_layer_exclusivity_fires_outside_the_layers() -> None:
    result = await GlobGateEngine().verify(
        Path("src/experimental/x.py"), _params("architecture.layer_exclusivity")
    )
    assert result.violations


async def test_layer_exclusivity_is_clean_inside_a_layer() -> None:
    result = await GlobGateEngine().verify(
        Path("src/body/x.py"), _params("architecture.layer_exclusivity")
    )
    assert not result.violations


async def test_mind_no_database_access_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.mind.no_database_access",
        "src/mind/x.py",
        "from shared.infrastructure.database.session_manager import get_session\n",
    )
    assert not result.ok and result.violations


async def test_mind_no_database_access_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.mind.no_database_access",
        "src/mind/x.py",
        "from shared.config import settings\n",
    )
    assert result.ok, result.violations


async def test_mind_no_filesystem_writes_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.mind.no_filesystem_writes",
        "src/mind/x.py",
        "from pathlib import Path\n\n\ndef f() -> None:\n    Path('x').write_text('y')\n",
    )
    assert not result.ok and result.violations


async def test_mind_no_filesystem_writes_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.mind.no_filesystem_writes",
        "src/mind/x.py",
        "from pathlib import Path\n\n\ndef f() -> str:\n    return Path('x').read_text()\n",
    )
    assert result.ok, result.violations


async def test_mind_no_body_invocation_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.mind.no_body_invocation",
        "src/mind/x.py",
        "import body.services.promotion\n",
    )
    assert not result.ok and result.violations


async def test_mind_no_body_invocation_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.mind.no_body_invocation",
        "src/mind/x.py",
        "import shared.config\n",
    )
    assert result.ok, result.violations


async def test_mind_no_will_invocation_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.mind.no_will_invocation",
        "src/mind/x.py",
        "from will.agents import x\n",
    )
    assert not result.ok and result.violations


async def test_mind_no_will_invocation_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.mind.no_will_invocation",
        "src/mind/x.py",
        "from shared.config import settings\n",
    )
    assert result.ok, result.violations


async def test_body_no_rule_evaluation_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.body.no_rule_evaluation",
        "src/body/services/x.py",
        "import mind.logic.engines\n",
    )
    assert not result.ok and result.violations


async def test_body_no_rule_evaluation_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.body.no_rule_evaluation",
        "src/body/services/x.py",
        "import mind.governance\n",
    )
    assert result.ok, result.violations


async def test_will_no_direct_database_access_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.will.no_direct_database_access",
        "src/will/x.py",
        "from shared.infrastructure.database.session_manager import get_session\n",
    )
    assert not result.ok and result.violations


async def test_will_no_direct_database_access_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.will.no_direct_database_access",
        "src/will/x.py",
        "from shared.config import settings\n",
    )
    assert result.ok, result.violations


async def test_will_no_filesystem_operations_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.will.no_filesystem_operations",
        "src/will/x.py",
        "from pathlib import Path\n\n\ndef f() -> None:\n    Path('x').write_text('y')\n",
    )
    assert not result.ok and result.violations


async def test_will_no_filesystem_operations_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.will.no_filesystem_operations",
        "src/will/x.py",
        "from pathlib import Path\n\n\ndef f() -> str:\n    return Path('x').read_text()\n",
    )
    assert result.ok, result.violations


async def test_api_no_direct_database_access_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.api.no_direct_database_access",
        "src/api/v1/x_routes.py",
        "from shared.infrastructure.database.session_manager import get_session\n",
    )
    assert not result.ok and result.violations


async def test_api_no_direct_database_access_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.api.no_direct_database_access",
        "src/api/v1/x_routes.py",
        "from api.dependencies import get_db\n",
    )
    assert result.ok, result.violations


async def test_api_no_body_bypass_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.api.no_body_bypass",
        "src/api/v1/x_routes.py",
        "from body.services.promotion import risk_class\n",
    )
    assert not result.ok and result.violations


async def test_api_no_body_bypass_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.api.no_body_bypass",
        "src/api/v1/x_routes.py",
        "from shared.config import settings\n",
    )
    assert result.ok, result.violations


async def test_body_no_will_import_fires(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.layers.no_body_to_will",
        "src/body/services/x.py",
        "import will.agents\n",
    )
    assert not result.ok and result.violations


async def test_body_no_will_import_is_clean(tmp_path: Path) -> None:
    result = await _verify(
        tmp_path,
        "architecture.layers.no_body_to_will",
        "src/body/services/x.py",
        "import shared.config\n",
    )
    assert result.ok, result.violations
