# tests/mind/logic/engines/cli_gate/engine/test_g2_cli_gate_engine_rules.py

"""#842 Unit H: all 6 cli_gate blocking-rule fixture pairs.

Every cli_gate check_type is context-level (BaseEngine.is_context_level_for
returns True for all eight), so the real dispatch chain a live audit takes
is ``CliGateEngine.verify_context`` -> ``self._walk_registry()`` ->
``CliCheck.verify(commands, params)`` -- not the per-file ``verify()``.
Each pair here goes through the real ``CliGateEngine.verify_context``, with
real params loaded from the live ``.intent/enforcement/mappings/`` YAML
(the same source ``EnforcementMappingLoader`` reads in production), against
an isolated synthetic command tree substituted for ``_walk_registry`` --
never against the real Typer app, which would pull in the whole CLI import
graph as a side effect. Every fixture pair here was verified against the
live engine in a standalone script before being written into this file.

Three of the six (cli.dangerous_explicit, cli.no_layer_exposure,
cli.discovery_strict) already have thorough violating+compliant pairs
directly against their CliCheck subclasses (same check_type dispatch,
same class object CliGateEngine.__init__ constructs) in this package's
sibling ``checks/*/test_generated.py`` files -- those satisfy #842's
"directly exercise that symbol" bar already and are cited as-is in the
registry rather than duplicated. This file adds one more pair per rule
that proves the full engine-level dispatch chain, and supplies the three
rules (cli.resource_first, cli.async_execution, cli.command.no_duplicates)
that had zero prior fixture coverage of any kind.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from cli.utils.decorators import COMMAND_REGISTRY, core_command
from mind.governance.audit_context import AuditorContext
from mind.logic.engines.cli_gate.engine import CliGateEngine


_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
_MAPPINGS = _REPO_ROOT / ".intent" / "enforcement" / "mappings"


def _load_rule_params(mapping_rel: str, rule_id: str) -> dict:
    """Read the engine params for rule_id from a mappings YAML."""
    path = _MAPPINGS / mapping_rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["mappings"][rule_id]["params"]


async def _run(
    params: dict, commands: list[dict], repo_root: Path | None = None
) -> list:
    """Drive the real CliGateEngine.verify_context against an isolated
    synthetic command tree -- _walk_registry is the only substitution,
    so check_type dispatch, error handling, and the check's own verify()
    all run for real."""
    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root or _REPO_ROOT
    engine = CliGateEngine(path_resolver=path_resolver)
    engine._walk_registry = MagicMock(return_value=commands)
    context = AuditorContext(repo_path=_REPO_ROOT)
    return await engine.verify_context(context, params)


# ---------------------------------------------------------------------------
# cli.resource_first -- zero prior fixture coverage
# ---------------------------------------------------------------------------


async def test_resource_first_fires_on_depth_one_command() -> None:
    params = _load_rule_params("cli/interface_design.yaml", "cli.resource_first")
    findings = await _run(params, [{"name": "orphan", "file_path": "x.py"}])
    assert len(findings) == 1
    assert findings[0].check_id == "cli_gate.resource_first"
    assert "depth 1" in findings[0].message


async def test_resource_first_passes_for_depth_two_command() -> None:
    params = _load_rule_params("cli/interface_design.yaml", "cli.resource_first")
    findings = await _run(params, [{"name": "safe.action", "file_path": "x.py"}])
    assert findings == []


# ---------------------------------------------------------------------------
# cli.no_layer_exposure -- also exercised directly at check-class level in
# checks/no_layer_exposure/test_generated.py; this adds the engine-dispatch
# proof with the rule's real forbidden_resources list from the live YAML.
# ---------------------------------------------------------------------------


async def test_no_layer_exposure_fires_via_engine_dispatch() -> None:
    params = _load_rule_params("cli/interface_design.yaml", "cli.no_layer_exposure")
    findings = await _run(
        params, [{"name": "mind.internal.peek", "file_path": "x.py"}]
    )
    assert len(findings) == 1
    assert findings[0].check_id == "cli_gate.no_layer_exposure"
    assert findings[0].context["resource"] == "mind"


async def test_no_layer_exposure_passes_for_permitted_resource() -> None:
    params = _load_rule_params("cli/interface_design.yaml", "cli.no_layer_exposure")
    findings = await _run(
        params, [{"name": "audit.rules.check", "file_path": "x.py"}]
    )
    assert findings == []


# ---------------------------------------------------------------------------
# cli.dangerous_explicit -- also exercised directly at check-class level in
# checks/dangerous_explicit/test_generated.py; engine-dispatch proof here.
# ---------------------------------------------------------------------------


async def test_dangerous_explicit_fires_via_engine_dispatch() -> None:
    params = _load_rule_params("cli/interface_design.yaml", "cli.dangerous_explicit")
    findings = await _run(
        params,
        [
            {
                "behavior": "mutate",
                "name": "risky",
                "dangerous": False,
                "params_list": [],
                "file_path": "x.py",
            }
        ],
    )
    assert len(findings) == 2
    assert {f.check_id for f in findings} == {"cli_gate.dangerous_explicit"}


async def test_dangerous_explicit_passes_for_compliant_mutate_command() -> None:
    params = _load_rule_params("cli/interface_design.yaml", "cli.dangerous_explicit")
    findings = await _run(
        params,
        [
            {
                "behavior": "mutate",
                "name": "safe",
                "dangerous": True,
                "params_list": ["write"],
                "file_path": "x.py",
            }
        ],
    )
    assert findings == []


# ---------------------------------------------------------------------------
# cli.async_execution -- zero prior fixture coverage. Real @core_command
# decoration is used rather than a synthetic stand-in: the decorator
# rewraps an async callback into a *sync* wrapper (functools.wraps
# preserves __name__) and records the name in the real COMMAND_REGISTRY --
# that sync-wrapper shape is exactly what Typer, and therefore
# walk_typer_app, actually sees for a correctly-decorated command.
# ---------------------------------------------------------------------------


async def _bare_async_cmd(ctx: object) -> None:
    """Never decorated -- simulates a command that forgot @core_command."""


@core_command(dangerous=False, requires_context=True)
async def _wrapped_async_cmd(ctx: object) -> None:
    """Real @core_command decoration; registers 'wrapped_async_cmd' below."""


async def test_async_execution_fires_on_undecorated_coroutine() -> None:
    params = _load_rule_params("cli/interface_design.yaml", "cli.async_execution")
    findings = await _run(
        params,
        [{"name": "bare.async", "callback": _bare_async_cmd, "file_path": "x.py"}],
    )
    assert len(findings) == 1
    assert findings[0].check_id == "cli_gate.async_execution"
    assert findings[0].context["callback_name"] == "_bare_async_cmd"


async def test_async_execution_passes_for_core_command_wrapper() -> None:
    """The real @core_command wrapper is sync (asyncio.iscoroutinefunction
    is False), which is what Typer registers -- the check's coroutine
    guard correctly skips it."""
    assert asyncio.iscoroutinefunction(_wrapped_async_cmd) is False
    params = _load_rule_params("cli/interface_design.yaml", "cli.async_execution")
    findings = await _run(
        params,
        [
            {
                "name": "wrapped.async",
                "callback": _wrapped_async_cmd,
                "file_path": "x.py",
            }
        ],
    )
    assert findings == []


async def test_async_execution_passes_for_registered_raw_coroutine() -> None:
    """functools.wraps sets __wrapped__ to the original coroutine function;
    its __name__ was registered in COMMAND_REGISTRY at decoration time, so
    the check's 'already registered' branch is reachable and real."""
    raw = _wrapped_async_cmd.__wrapped__
    assert asyncio.iscoroutinefunction(raw) is True
    assert raw.__name__ in COMMAND_REGISTRY
    params = _load_rule_params("cli/interface_design.yaml", "cli.async_execution")
    findings = await _run(
        params, [{"name": "registered.raw", "callback": raw, "file_path": "x.py"}]
    )
    assert findings == []


# ---------------------------------------------------------------------------
# cli.discovery_strict -- also exercised directly at check-class level in
# checks/discovery_strict/test_generated.py; engine-dispatch proof here
# against an isolated tmp_path loader (never the real admin_cli.py).
# ---------------------------------------------------------------------------


async def test_discovery_strict_fires_via_engine_dispatch(tmp_path: Path) -> None:
    params = _load_rule_params("cli/interface_design.yaml", "cli.discovery_strict")
    params = {**params, "loader": "loader.py"}
    (tmp_path / "loader.py").write_text(
        "try:\n    import cli.commands\nexcept ImportError:\n    pass\n",
        encoding="utf-8",
    )
    findings = await _run(params, [], repo_root=tmp_path)
    assert len(findings) == 1
    assert findings[0].check_id == "cli_gate.discovery_strict"


async def test_discovery_strict_passes_for_top_level_import(tmp_path: Path) -> None:
    params = _load_rule_params("cli/interface_design.yaml", "cli.discovery_strict")
    params = {**params, "loader": "loader.py"}
    (tmp_path / "loader.py").write_text("import cli.commands\n", encoding="utf-8")
    findings = await _run(params, [], repo_root=tmp_path)
    assert findings == []


# ---------------------------------------------------------------------------
# cli.command.no_duplicates -- zero prior fixture coverage. Mapped from
# infrastructure/cli_commands.yaml, not cli/interface_design.yaml.
# ---------------------------------------------------------------------------


async def test_no_duplicates_fires_on_repeated_canonical_name() -> None:
    params = _load_rule_params(
        "infrastructure/cli_commands.yaml", "cli.command.no_duplicates"
    )
    findings = await _run(
        params,
        [
            {"name": "dup.cmd", "file_path": "a.py", "entrypoint": "a"},
            {"name": "dup.cmd", "file_path": "b.py", "entrypoint": "b"},
        ],
    )
    assert len(findings) == 1
    assert findings[0].check_id == "cli_gate.no_duplicates"
    assert findings[0].context["registration_count"] == 2


async def test_no_duplicates_passes_for_unique_canonical_names() -> None:
    params = _load_rule_params(
        "infrastructure/cli_commands.yaml", "cli.command.no_duplicates"
    )
    findings = await _run(
        params,
        [
            {"name": "uniq.cmd1", "file_path": "a.py", "entrypoint": "a"},
            {"name": "uniq.cmd2", "file_path": "b.py", "entrypoint": "b"},
        ],
    )
    assert findings == []
