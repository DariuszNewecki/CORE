# tests/mind/logic/engines/ast_gate/test_g2_call_execution_discipline_rules.py

"""#842 Unit L: the 8 AST call/execution-discipline blocking rules.

Every pair goes through the real ASTGateEngine.verify() with real params
loaded from the live .intent/enforcement/mappings/ YAML, against a source
file written at a tmp_path-relative location matching the rule's own
applies_to glob.

Two rules (ai.prompt.output_validation_required, planning.trace_mandatory)
dispatch through the shared generic_primitive/required_calls harness
(selector + requirement). Their compliant fixtures deliberately include a
function whose name matches the rule's own selector regex -- a fixture
with NO matching function would trivially "pass" with zero violations
because the selector never fired, not because it satisfies the
requirement (selector non-applicability is not compliance). A dedicated
test for each proves the distinction directly: a file with no selector-
matching function passes, and is asserted to NOT be evidence of the
requirement being satisfied.

Both rules' compliant fixtures also deliberately use the "assign the
required call's result to a variable, then bare-return the variable"
idiom rather than `return required_call(...)` directly -- the latter is
mishandled by the check's path-sensitive Return handling (a call
embedded directly in a return expression is invisible to it) and
produces a false-positive violation on genuinely compliant code. Filed
as #858 (a regression against #118's original fix, not something to work
around here); the idiom used below matches the real production code in
src/shared/ai/prompt_model.py::PromptModel.invoke, confirmed by reading
the source before writing this fixture.

ai.prompt.model_required's, architecture.channels.logic_logger_only's,
and async.no_manual_loop_run's stale excludes are a separate, filed
hygiene issue (#859, same shape as #857) -- confirmed harmless via a
full real-engine sweep of the actual src/ tree; not a defect in the
enforcement mechanism these fixtures verify.
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
# ai.prompt.model_required
# ---------------------------------------------------------------------------


async def test_model_required_fires_on_direct_make_request_call(
    tmp_path: Path,
) -> None:
    params = _load_rule_params("ai/prompt_governance.yaml", "ai.prompt.model_required")
    result = await _verify(
        tmp_path,
        "src/body/atomic/example.py",
        "class X:\n    def go(self):\n        return self.client.make_request_async('x')\n",
        params,
    )
    assert not result.ok
    assert any("make_request_async" in v for v in result.violations)


async def test_model_required_passes_via_prompt_model_invoke(tmp_path: Path) -> None:
    params = _load_rule_params("ai/prompt_governance.yaml", "ai.prompt.model_required")
    result = await _verify(
        tmp_path,
        "src/body/atomic/example2.py",
        "class X:\n    def go(self):\n        return self.model.invoke('x')\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# ai.prompt.output_validation_required
# ---------------------------------------------------------------------------


async def test_output_validation_required_fires_when_invoke_skips_validation(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "ai/prompt_governance.yaml", "ai.prompt.output_validation_required"
    )
    result = await _verify(
        tmp_path,
        "src/shared/ai/prompt_model.py",
        "class PromptModel:\n    def invoke(self, x):\n        return self._call_llm(x)\n",
        params,
    )
    assert not result.ok
    assert any("_validate_output" in v for v in result.violations)


async def test_output_validation_required_passes_when_invoke_validates(
    tmp_path: Path,
) -> None:
    """Mirrors the real idiom in src/shared/ai/prompt_model.py::invoke --
    assign then bare-return, not `return self._validate_output(...)`
    directly (see module docstring / #858)."""
    params = _load_rule_params(
        "ai/prompt_governance.yaml", "ai.prompt.output_validation_required"
    )
    result = await _verify(
        tmp_path,
        "src/shared/ai/prompt_model.py",
        (
            "class PromptModel:\n"
            "    def invoke(self, x):\n"
            "        out = self._call_llm(x)\n"
            "        validated = self._validate_output(out)\n"
            "        return validated\n"
        ),
        params,
    )
    assert result.ok
    assert result.violations == []


async def test_output_validation_required_selector_non_match_is_not_compliance(
    tmp_path: Path,
) -> None:
    """A file with no function named 'invoke' passes trivially -- the
    selector (name_regex: ^invoke$) never fires, so validate_requirement
    is never called. This is selector non-applicability, not proof the
    output-validation requirement is satisfied -- must not be cited as a
    compliant fixture for the rule."""
    params = _load_rule_params(
        "ai/prompt_governance.yaml", "ai.prompt.output_validation_required"
    )
    result = await _verify(
        tmp_path,
        "src/shared/ai/prompt_model.py",
        "class PromptModel:\n    def other_method(self, x):\n        return 1\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.channels.api_structured_output_only
# ---------------------------------------------------------------------------


async def test_api_structured_output_only_fires_on_rich_console(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/channels.yaml", "architecture.channels.api_structured_output_only"
    )
    result = await _verify(
        tmp_path,
        "src/api/v1/example.py",
        "from rich.console import Console\nconsole = Console()\nconsole.print('hi')\n",
        params,
    )
    assert not result.ok
    assert len(result.violations) >= 2


async def test_api_structured_output_only_passes_via_logger(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/channels.yaml", "architecture.channels.api_structured_output_only"
    )
    result = await _verify(
        tmp_path,
        "src/api/v1/example2.py",
        "from shared.logger import getLogger\nlogger = getLogger(__name__)\nlogger.info('hi')\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.channels.logic_logger_only
# ---------------------------------------------------------------------------


async def test_logic_logger_only_fires_on_print(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/channels.yaml", "architecture.channels.logic_logger_only"
    )
    result = await _verify(
        tmp_path, "src/mind/logic/example.py", "print('hi')\n", params
    )
    assert not result.ok
    assert any("print" in v for v in result.violations)


async def test_logic_logger_only_passes_via_logger(tmp_path: Path) -> None:
    params = _load_rule_params(
        "architecture/channels.yaml", "architecture.channels.logic_logger_only"
    )
    result = await _verify(
        tmp_path,
        "src/mind/logic/example2.py",
        "from shared.logger import getLogger\nlogger = getLogger(__name__)\nlogger.info('hi')\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# architecture.no_module_async_engine
# ---------------------------------------------------------------------------


async def test_no_module_async_engine_fires_on_module_level_creation(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/core_safety.yaml", "architecture.no_module_async_engine"
    )
    result = await _verify(
        tmp_path,
        "src/body/infrastructure/example.py",
        (
            "from sqlalchemy.ext.asyncio import create_async_engine\n"
            "engine = create_async_engine('postgresql://x')\n"
        ),
        params,
    )
    assert not result.ok
    assert any("create_async_engine" in v for v in result.violations)


async def test_no_module_async_engine_passes_for_lazy_function_scoped_creation(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/core_safety.yaml", "architecture.no_module_async_engine"
    )
    result = await _verify(
        tmp_path,
        "src/body/infrastructure/example2.py",
        (
            "from sqlalchemy.ext.asyncio import create_async_engine\n"
            "def build_engine():\n"
            "    return create_async_engine('postgresql://x')\n"
        ),
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# async.no_manual_loop_run
# ---------------------------------------------------------------------------


async def test_no_manual_loop_run_fires_on_unguarded_asyncio_run(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "architecture/async_logic.yaml", "async.no_manual_loop_run"
    )
    result = await _verify(
        tmp_path,
        "src/mind/logic/example.py",
        "import asyncio\ndef run():\n    asyncio.run(main())\n",
        params,
    )
    assert not result.ok
    assert any("asyncio.run" in v for v in result.violations)


async def test_no_manual_loop_run_passes_for_defensively_guarded_call(
    tmp_path: Path,
) -> None:
    """The check itself (not the mapping's excludes) recognises the
    get_running_loop + is_running defensive pattern as legitimate --
    the same idiom the real src/cli/resources/context/search.py and
    src/cli/logic/demo/scenario_runner.py entry points use."""
    params = _load_rule_params(
        "architecture/async_logic.yaml", "async.no_manual_loop_run"
    )
    result = await _verify(
        tmp_path,
        "src/mind/logic/example2.py",
        (
            "import asyncio\n"
            "def run():\n"
            "    try:\n"
            "        loop = asyncio.get_running_loop()\n"
            "    except RuntimeError:\n"
            "        loop = None\n"
            "    if loop and loop.is_running():\n"
            "        return\n"
            "    asyncio.run(main())\n"
        ),
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# planning.trace_mandatory
# ---------------------------------------------------------------------------


async def test_trace_mandatory_fires_when_create_method_skips_tracer(
    tmp_path: Path,
) -> None:
    params = _load_rule_params("will/planning.yaml", "planning.trace_mandatory")
    result = await _verify(
        tmp_path,
        "src/will/agents/planner_agent.py",
        "class PlannerAgent:\n    def create_plan(self, x):\n        return x\n",
        params,
    )
    assert not result.ok
    assert any("tracer.record" in v for v in result.violations)


async def test_trace_mandatory_passes_when_create_method_traces(
    tmp_path: Path,
) -> None:
    params = _load_rule_params("will/planning.yaml", "planning.trace_mandatory")
    result = await _verify(
        tmp_path,
        "src/will/agents/planner_agent.py",
        (
            "class PlannerAgent:\n"
            "    def create_plan(self, x):\n"
            "        self.tracer.record('start')\n"
            "        return x\n"
        ),
        params,
    )
    assert result.ok
    assert result.violations == []


async def test_trace_mandatory_selector_non_match_is_not_compliance(
    tmp_path: Path,
) -> None:
    """A file with no create_/execute_/elaborate_-prefixed method passes
    trivially -- selector non-applicability, not proof tracing is
    present. Must not be cited as a compliant fixture for the rule."""
    params = _load_rule_params("will/planning.yaml", "planning.trace_mandatory")
    result = await _verify(
        tmp_path,
        "src/will/agents/planner_agent.py",
        "class PlannerAgent:\n    def helper_method(self, x):\n        return x\n",
        params,
    )
    assert result.ok
    assert result.violations == []


# ---------------------------------------------------------------------------
# purity.tempfile_default_dir
# ---------------------------------------------------------------------------


async def test_tempfile_default_dir_fires_on_missing_dir_kwarg(tmp_path: Path) -> None:
    params = _load_rule_params("code/purity.yaml", "purity.tempfile_default_dir")
    result = await _verify(
        tmp_path,
        "src/body/infrastructure/example.py",
        "import tempfile\np = tempfile.mkdtemp()\n",
        params,
    )
    assert not result.ok
    assert any("dir=" in v for v in result.violations)


async def test_tempfile_default_dir_passes_with_explicit_dir_kwarg(
    tmp_path: Path,
) -> None:
    params = _load_rule_params("code/purity.yaml", "purity.tempfile_default_dir")
    result = await _verify(
        tmp_path,
        "src/body/infrastructure/example2.py",
        "import tempfile\np = tempfile.mkdtemp(dir='var/tmp')\n",
        params,
    )
    assert result.ok
    assert result.violations == []
