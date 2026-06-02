"""Unit tests for ``TaxonomyGateEngine`` per ADR-079 D9.

The engine enforces the phantom-decoration invariant: every capability
id in ``operational_capabilities.yaml`` must be backed by an
``@atomic_action(action_id="<id>")`` decoration in ``src/``. These
tests pin:

  - context-level dispatch is True for the one check_type it owns;
  - clean tree (no phantoms) → ok=True, no violations;
  - one phantom → ok=False, one violation naming the cap_id and citing
    ADR-079 D9 Shape 1 / Shape 2;
  - taxonomy load failure surfaces as engine-not-ok (not a phantom);
  - unparseable .py file is logged and skipped, audit continues;
  - decoration with non-literal action_id is NOT counted as backing
    (intentional — too rare to grant credit, the phantom finding's
    resolution prompt handles the path forward);
  - unknown check_type returns a clear ok=False marker.

These exercise the helper functions ``_collect_atomic_action_ids`` and
``_extract_action_id`` indirectly through ``verify`` — the engine's
public surface — rather than testing the helpers in isolation.
"""

from __future__ import annotations

import textwrap
from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace

import pytest

from mind.logic.engines.taxonomy_gate import TaxonomyGateEngine
from shared.path_resolver import PathResolver


_DECORATOR_BACKING_CHECK = "operational_capabilities_decorator_backing"


def _fake_context(repo_root: Path) -> SimpleNamespace:
    """Minimal AuditorContext stand-in carrying only ``repo_path`` — the
    only attribute taxonomy_gate's verify_context reads. SimpleNamespace
    avoids constructing a real AuditorContext (which would bring in the
    full PathResolver + EnforcementMappingLoader + IntentRepository
    bootstrap unrelated to this engine's surface)."""
    return SimpleNamespace(repo_path=repo_root)


# ---------------------------------------------------------------------------
# Fixtures: minimal repo skeleton (YAML + src/) under a tmp_path
# ---------------------------------------------------------------------------


def _write_repo_skeleton(
    repo: Path,
    *,
    capability_ids: Iterable[str],
    decoration_sources: dict[str, str] | None = None,
) -> None:
    """Lay down a minimal repo: enums.json + action_risk.yaml +
    operational_capabilities.yaml + src/ with the given decoration sources.

    ``decoration_sources`` maps relative paths under ``src/`` to file content.
    Each capability id in ``capability_ids`` is declared in the YAML with a
    minimal valid fs_profile (all four op-classes present, all empty).
    """
    (repo / ".intent" / "META").mkdir(parents=True)
    (repo / ".intent" / "enforcement" / "config").mkdir(parents=True)
    (repo / ".intent" / "taxonomies").mkdir(parents=True)
    (repo / "src").mkdir()

    # enums.json — fs_operation_class + operational_mode
    (repo / ".intent" / "META" / "enums.json").write_text(
        '{"definitions": {'
        '"fs_operation_class": {"enum": ["read", "create", "modify", "delete"]}, '
        '"operational_mode": {"enum": ["dev", "live"]}'
        "}}",
        encoding="utf-8",
    )

    # action_risk.yaml — every capability_id must appear here per ADR-078 D3
    risk_block = "\n".join(f"  {cid}: safe" for cid in capability_ids)
    (repo / ".intent" / "enforcement" / "config" / "action_risk.yaml").write_text(
        f"actions:\n{risk_block}\n",
        encoding="utf-8",
    )

    # operational_capabilities.yaml
    cap_entries = []
    for cid in capability_ids:
        cap_entries.append(
            textwrap.indent(
                textwrap.dedent(
                    f"""\
                    {cid}:
                      description: fixture
                      risk: safe
                      fs_profile:
                        read: []
                        create: []
                        modify: []
                        delete: []
                    """
                ),
                "  ",
            )
        )
    (repo / ".intent" / "taxonomies" / "operational_capabilities.yaml").write_text(
        "capabilities:\n" + "".join(cap_entries),
        encoding="utf-8",
    )

    # src/ files
    for rel_path, content in (decoration_sources or {}).items():
        target = repo / "src" / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _engine(repo: Path) -> TaxonomyGateEngine:
    return TaxonomyGateEngine(path_resolver=PathResolver(repo_root=repo))


# ---------------------------------------------------------------------------
# Context-level dispatch
# ---------------------------------------------------------------------------


def test_is_context_level_true_for_decorator_backing_check_type() -> None:
    assert TaxonomyGateEngine.is_context_level_for(_DECORATOR_BACKING_CHECK) is True


def test_is_context_level_false_for_unknown_check_type() -> None:
    assert TaxonomyGateEngine.is_context_level_for("something_else") is False
    assert TaxonomyGateEngine.is_context_level_for(None) is False


# ---------------------------------------------------------------------------
# Decorator-backing semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clean_tree_yields_no_findings(tmp_path: Path) -> None:
    """Every YAML id has a matching @atomic_action(action_id=...) → empty list."""
    _write_repo_skeleton(
        tmp_path,
        capability_ids=["fix.format", "check.imports"],
        decoration_sources={
            "fixers/format.py": textwrap.dedent(
                """
                from shared.atomic_action import atomic_action

                @atomic_action(action_id="fix.format")
                async def fix_format(**kwargs):
                    pass

                @atomic_action(action_id="check.imports")
                async def check_imports(**kwargs):
                    pass
                """
            ),
        },
    )
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _DECORATOR_BACKING_CHECK}
    )
    assert findings == []


@pytest.mark.asyncio
async def test_phantom_yields_one_finding_with_resolution_prompt(
    tmp_path: Path,
) -> None:
    """A YAML id with no backing decoration is reported with both Shape 1/2 paths."""
    _write_repo_skeleton(
        tmp_path,
        capability_ids=["fix.format", "secrets.set"],  # secrets.set has no decoration
        decoration_sources={
            "fixers/format.py": textwrap.dedent(
                """
                from shared.atomic_action import atomic_action

                @atomic_action(action_id="fix.format")
                async def fix_format(**kwargs):
                    pass
                """
            ),
        },
    )
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _DECORATOR_BACKING_CHECK}
    )
    assert len(findings) == 1
    finding = findings[0]
    assert (
        finding.check_id
        == "governance.taxonomy.operational_capabilities_decorator_backing"
    )
    assert finding.file_path == ".intent/taxonomies/operational_capabilities.yaml"
    assert finding.context == {"capability_id": "secrets.set"}
    assert "secrets.set" in finding.message
    assert "Shape 1" in finding.message and "Shape 2" in finding.message
    assert "ADR-079 D9" in finding.message


@pytest.mark.asyncio
async def test_multiple_phantoms_one_finding_each_sorted(tmp_path: Path) -> None:
    """Phantoms are reported sorted by cap_id so the output is stable."""
    _write_repo_skeleton(
        tmp_path,
        capability_ids=["z.last", "a.first", "m.middle"],
        decoration_sources={},  # zero decorations → all three are phantoms
    )
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _DECORATOR_BACKING_CHECK}
    )
    assert len(findings) == 3
    cap_ids = [f.context["capability_id"] for f in findings]
    assert cap_ids == ["a.first", "m.middle", "z.last"]


@pytest.mark.asyncio
async def test_attribute_access_decoration_counts_as_backing(tmp_path: Path) -> None:
    """``@module.atomic_action(action_id=...)`` is also valid backing."""
    _write_repo_skeleton(
        tmp_path,
        capability_ids=["fix.format"],
        decoration_sources={
            "fixers/format.py": textwrap.dedent(
                """
                import shared.atomic_action as atomic_module

                @atomic_module.atomic_action(action_id="fix.format")
                async def fix_format(**kwargs):
                    pass
                """
            ),
        },
    )
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _DECORATOR_BACKING_CHECK}
    )
    assert findings == []


@pytest.mark.asyncio
async def test_non_literal_action_id_is_not_counted_as_backing(
    tmp_path: Path,
) -> None:
    """A decoration whose action_id is a variable (not a string literal) does
    NOT grant backing — the phantom-class definition requires a static
    YAML-vs-source match."""
    _write_repo_skeleton(
        tmp_path,
        capability_ids=["fix.format"],
        decoration_sources={
            "fixers/format.py": textwrap.dedent(
                """
                from shared.atomic_action import atomic_action

                MY_ID = "fix.format"

                @atomic_action(action_id=MY_ID)
                async def fix_format(**kwargs):
                    pass
                """
            ),
        },
    )
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _DECORATOR_BACKING_CHECK}
    )
    assert len(findings) == 1
    assert findings[0].context["capability_id"] == "fix.format"


@pytest.mark.asyncio
async def test_unparseable_python_file_is_skipped(tmp_path: Path) -> None:
    """A SyntaxError in one file must not crash the audit — the engine logs
    and continues. Other files' decorations are still collected."""
    _write_repo_skeleton(
        tmp_path,
        capability_ids=["fix.format"],
        decoration_sources={
            "broken/syntax.py": "this is not (valid python\n",
            "fixers/format.py": textwrap.dedent(
                """
                from shared.atomic_action import atomic_action

                @atomic_action(action_id="fix.format")
                async def fix_format(**kwargs):
                    pass
                """
            ),
        },
    )
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _DECORATOR_BACKING_CHECK}
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Degraded-instrument and unknown-check_type surfaces
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_taxonomy_load_failure_surfaces_under_distinct_check_id(
    tmp_path: Path,
) -> None:
    """If the YAML loader raises, the engine emits one BLOCK finding under
    a distinct check_id so the operator sees the underlying YAML defect
    rather than a phantom-shaped misattribution."""
    # No skeleton written → loader fails (taxonomy file missing).
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _DECORATOR_BACKING_CHECK}
    )
    assert len(findings) == 1
    assert findings[0].check_id.endswith(".load_failed")
    assert "cannot load" in findings[0].message


@pytest.mark.asyncio
async def test_unknown_check_type_in_verify_context_returns_block(
    tmp_path: Path,
) -> None:
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": "something_else"}
    )
    assert len(findings) == 1
    assert findings[0].check_id == "taxonomy_gate.unknown_check_type"
    assert "unknown check_type" in findings[0].message


@pytest.mark.asyncio
async def test_verify_per_file_returns_not_ok_marker(tmp_path: Path) -> None:
    """The per-file verify path is only reachable on misconfiguration —
    surface that as engine-not-ok rather than silently producing nothing."""
    result = await _engine(tmp_path).verify(
        Path("ignored"), {"check_type": _DECORATOR_BACKING_CHECK}
    )
    assert result.ok is False
    assert "context-level" in result.message
