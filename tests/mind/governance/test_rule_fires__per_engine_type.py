"""End-to-end rule-fires tests — one per engine type.

External review finding: no test instantiated a real `.intent/` rule, ran it
against a violating source snippet, and asserted a blocking finding. This file
closes that gap.

Each test:
  1. Loads params from the actual `.intent/enforcement/mappings/` YAML.
  2. Instantiates the engine the rule maps to.
  3. Writes a temp file containing a deliberate violation.
  4. Calls engine.verify() with the real params.
  5. Asserts at least one violation is returned.

Engines covered: ast_gate (x2), glob_gate (x2), regex_gate (x1).
runtime_gate and llm_gate are covered by their own per-engine suites and
require live runtime data / LLM availability respectively.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml

from mind.logic.engines.ast_gate.engine import ASTGateEngine
from mind.logic.engines.glob_gate import GlobGateEngine
from mind.logic.engines.regex_gate import RegexGateEngine
from shared.path_resolver import PathResolver


_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_MAPPINGS = _REPO_ROOT / ".intent" / "enforcement" / "mappings"


def _load_rule_params(mapping_rel: str, rule_id: str) -> dict:
    """Read the engine params for rule_id from a mappings YAML."""
    path = _MAPPINGS / mapping_rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg = data["mappings"][rule_id]
    return cfg["params"]


@pytest.fixture
def tmp_py(tmp_path: Path) -> Path:
    """Temp Python file under var/tmp/ (CLAUDE.md prohibits /tmp/)."""
    dest = _REPO_ROOT / "var" / "tmp" / f"rule_fires_{uuid.uuid4().hex}.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    yield dest
    dest.unlink(missing_ok=True)


@pytest.fixture
def path_resolver() -> PathResolver:
    return PathResolver(repo_root=_REPO_ROOT)


# ---------------------------------------------------------------------------
# ast_gate
# ---------------------------------------------------------------------------


# ID: e1e9f0dc-11c5-48fb-8805-05d81949fde0
async def test_ast_gate_fires_on_print_statement(
    tmp_py: Path, path_resolver: PathResolver
) -> None:
    """architecture.channels.logic_logger_only — print() in logic code is a violation.

    Rule params loaded from the live enforcement mapping so this test breaks
    if someone changes the rule without updating the engine dispatch.
    """
    params = _load_rule_params(
        "architecture/channels.yaml", "architecture.channels.logic_logger_only"
    )
    tmp_py.write_text(
        'from __future__ import annotations\n\nprint("hello")\n', encoding="utf-8"
    )

    engine = ASTGateEngine(path_resolver=path_resolver)
    result = await engine.verify(tmp_py, params)

    assert result.violations, (
        f"Expected violation for print() under rule "
        f"architecture.channels.logic_logger_only; got none. "
        f"engine_result={result}"
    )


# ID: 9fed9fc8-f0fc-412e-a105-5444d25f29c0
async def test_ast_gate_fires_on_asyncio_run(
    tmp_py: Path, path_resolver: PathResolver
) -> None:
    """async.no_manual_loop_run — asyncio.run() in logic code is a violation.

    The forbidden_calls list in the mapping must include 'asyncio.run';
    if it drifts or the engine dispatch breaks, this test catches it.
    """
    params = _load_rule_params(
        "architecture/async_logic.yaml", "async.no_manual_loop_run"
    )
    tmp_py.write_text(
        "from __future__ import annotations\nimport asyncio\n\nasyncio.run(main())\n",
        encoding="utf-8",
    )

    engine = ASTGateEngine(path_resolver=path_resolver)
    result = await engine.verify(tmp_py, params)

    assert result.violations, (
        f"Expected violation for asyncio.run() under rule "
        f"async.no_manual_loop_run; got none. engine_result={result}"
    )


# ---------------------------------------------------------------------------
# regex_gate
# ---------------------------------------------------------------------------


# ID: 829bf654-d41f-4055-a9b9-ffb9cb93f9f8
async def test_regex_gate_fires_on_hardcoded_runtime_dir(tmp_py: Path) -> None:
    """architecture.path_access.no_hardcoded_runtime_dirs — string literal 'reports/' is a violation.

    Patterns are loaded from the live enforcement mapping; drift between the
    pattern list and the engine's regex engine is caught immediately.
    """
    params = _load_rule_params(
        "architecture/path_access.yaml",
        "architecture.path_access.no_hardcoded_runtime_dirs",
    )
    tmp_py.write_text(
        'from __future__ import annotations\n\npath = base / "reports"\n',
        encoding="utf-8",
    )

    engine = RegexGateEngine()
    result = await engine.verify(tmp_py, params)

    assert result.violations, (
        f"Expected violation for hardcoded 'reports/' path under rule "
        f"architecture.path_access.no_hardcoded_runtime_dirs; got none. "
        f"engine_result={result}"
    )


# ---------------------------------------------------------------------------
# glob_gate
# ---------------------------------------------------------------------------


# ID: 199ab82c-7f11-4670-bc35-74975210a3b8
async def test_glob_gate_fires_on_prohibited_constitution_path() -> None:
    """architecture.constitution_read_only — a path inside .intent/constitution/ is prohibited.

    GlobGateEngine.verify() takes a file_path; we pass a path that matches the
    patterns_prohibited glob without creating an actual file.
    """
    params = _load_rule_params(
        "architecture/core_safety.yaml", "architecture.constitution_read_only"
    )
    violating_path = Path(".intent/constitution/governance_frame.yaml")

    engine = GlobGateEngine()
    result = await engine.verify(violating_path, params)

    assert result.violations, (
        f"Expected violation for path inside .intent/constitution/ under rule "
        f"architecture.constitution_read_only; got none. engine_result={result}"
    )


# ID: c06394e9-08b6-4934-a284-631536cc0b70
async def test_glob_gate_fires_on_layer_exclusivity_violation() -> None:
    """architecture.layer_exclusivity — a source file outside the declared layers is a violation.

    A file at src/experimental/new_thing.py does not match any allowed
    top-level pattern (src/mind/**, src/body/**, src/will/**, etc.).
    """
    params = _load_rule_params(
        "architecture/layer_separation.yaml", "architecture.layer_exclusivity"
    )
    violating_path = Path("src/experimental/new_thing.py")

    engine = GlobGateEngine()
    result = await engine.verify(violating_path, params)

    assert result.violations, (
        f"Expected violation for src/experimental/ path under rule "
        f"architecture.layer_exclusivity; got none. engine_result={result}"
    )
