# tests/mind/logic/engines/ast_gate/test_g2_ssot_mutation_surface_modularity_rules.py

"""#842 Unit N: data-SSOT, mutation-surface, modularity, and metadata-decorator
blocking rules.

Every check goes through the real ASTGateEngine.verify() with real params
loaded from the live .intent/enforcement/mappings/ YAML, against a source
file written at a tmp_path-relative location matching the rule's own
applies_to glob.

governance.logic_mutation.governed and governance.mutation_surface.filehandler_required
share one check_type (no_direct_writes) but are two independent rules with
their own scope/excludes -- each gets its own dedicated fixture pair loaded
from its own mapping file, per the same discipline Unit K applied to the
shared runtime_import_boundary check_type. Both mapping files' excludes were
compared row-for-row while writing this unit: governance.logic_mutation.governed
excludes "src/mind/governance/runtime_validator.py", a path that no longer
exists (the file moved to src/body/governance/runtime_validator.py) and is
absent from filehandler_required's excludes list. Confirmed harmless by
direct invocation of the real check against the real file at its current
path with no exclude applied at all (zero violations -- its two write calls
are `fs.write(...)` / `file_service.write(...)`, a bare `.write` attribute
name that has no entry, leaf or qualified, in the filesystem_operations.yaml
taxonomy) -- filed as #860, same stale-exclude-but-harmless shape as
#857/#859, not a defect in either rule's own verified enforcement.
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
# data.ssot.database_primacy
# ---------------------------------------------------------------------------


async def test_database_primacy_fires_on_hardcoded_llm_models(tmp_path: Path) -> None:
    params = _load_rule_params("data/governance.yaml", "data.ssot.database_primacy")
    result = await _verify(
        tmp_path,
        "src/shared/example.py",
        "LLM_MODELS = {'claude': 'claude-sonnet-5'}\n",
        params,
    )
    assert not result.ok
    assert any("LLM_MODELS" in v for v in result.violations)


async def test_database_primacy_passes_for_unrelated_constant(tmp_path: Path) -> None:
    params = _load_rule_params("data/governance.yaml", "data.ssot.database_primacy")
    result = await _verify(
        tmp_path,
        "src/shared/example.py",
        "DEFAULT_TIMEOUT_SECONDS = 30\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# governance.logic_mutation.governed
# ---------------------------------------------------------------------------


async def test_logic_mutation_governed_fires_on_direct_write_text(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/governance_basics.yaml", "governance.logic_mutation.governed"
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from pathlib import Path\n\n"
        "def save(content):\n    Path('out.txt').write_text(content)\n",
        params,
    )
    assert not result.ok
    assert any("write_text" in v for v in result.violations)


async def test_logic_mutation_governed_passes_via_file_handler(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/governance_basics.yaml", "governance.logic_mutation.governed"
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from body.infrastructure.storage.file_handler import FileHandler\n\n"
        "def save(repo_root, content):\n"
        "    FileHandler(str(repo_root)).write_runtime_text('out.txt', content)\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# governance.mutation_surface.filehandler_required
# ---------------------------------------------------------------------------


async def test_filehandler_required_fires_on_direct_write_bytes(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/mutation_surface.yaml",
        "governance.mutation_surface.filehandler_required",
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from pathlib import Path\n\n"
        "def save(content):\n    Path('out.bin').write_bytes(content)\n",
        params,
    )
    assert not result.ok
    assert any("write_bytes" in v for v in result.violations)


async def test_filehandler_required_passes_via_file_handler(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/mutation_surface.yaml",
        "governance.mutation_surface.filehandler_required",
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "from body.infrastructure.storage.file_handler import FileHandler\n\n"
        "def save(repo_root, content):\n"
        "    FileHandler(str(repo_root)).write_runtime_text('out.txt', content)\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# modularity.needs_refactor
# ---------------------------------------------------------------------------


async def test_needs_refactor_fires_when_four_concerns_present(tmp_path: Path) -> None:
    """4 concern areas (database, web, testing, cli) exceeds max_concerns=3."""
    params = _load_rule_params(
        "code/modularity.yaml", "modularity.needs_refactor"
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_mixed_service.py",
        "import sqlalchemy\n"
        "import fastapi\n"
        "import pytest\n"
        "import typer\n\n"
        "def handler():\n    pass\n",
        params,
    )
    assert not result.ok
    assert any("concern" in v["message"] for v in result.violations)


async def test_needs_refactor_passes_with_single_concern(tmp_path: Path) -> None:
    params = _load_rule_params(
        "code/modularity.yaml", "modularity.needs_refactor"
    )
    result = await _verify(
        tmp_path,
        "src/body/services/example_single_concern_service.py",
        "import fastapi\n\ndef handler():\n    pass\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# purity.no_metadata_decorators
# ---------------------------------------------------------------------------


async def test_no_metadata_decorators_fires_on_capability_decorator(
    tmp_path: Path,
) -> None:
    """The bare-decorator form matches the rule statement's own literal
    examples ("@capability, @meta, or @owner", purity.json) and the
    check's real matching: ``full_attr_name`` resolves ast.Name/Attribute
    chains only, so a call-form decorator (``@capability("id")``) would
    not be caught -- the documented and tested forbidden shape is bare."""
    params = _load_rule_params("code/purity.yaml", "purity.no_metadata_decorators")
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "@capability\ndef handler():\n    pass\n",
        params,
    )
    assert not result.ok
    assert any("capability" in v for v in result.violations)


async def test_no_metadata_decorators_passes_without_forbidden_decorator(
    tmp_path: Path,
) -> None:
    params = _load_rule_params("code/purity.yaml", "purity.no_metadata_decorators")
    result = await _verify(
        tmp_path,
        "src/body/services/example_service.py",
        "def handler():\n    pass\n",
        params,
    )
    assert result.ok
    assert result.violations == []
