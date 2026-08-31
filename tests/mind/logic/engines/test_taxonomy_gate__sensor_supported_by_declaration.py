# tests/mind/logic/engines/test_taxonomy_gate__sensor_supported_by_declaration.py

"""#842 Unit J: governance.taxonomy.sensor_supported_by_declaration.

ADR-091 D4 — the authored set (each artifact_type's ``supported_sensors``)
and the introspected set (sensor worker declarations carrying
``mandate.scope.artifact_type``) must be equal. Real
``TaxonomyGateEngine.verify_context`` dispatch against an isolated
``.intent/workers/`` tree under ``tmp_path`` for the introspected side.
The authored side reads through the global ``get_intent_repository()``
singleton (``TaxonomyGateEngine._build_sensor_support_findings``), which
is not filesystem-isolatable via ``tmp_path`` alone — patched at its
import site in ``mind.logic.engines.taxonomy_gate`` with a fake carrying
a controlled ``list_artifact_types()`` return, the injected-fake-session
counterpart for this engine's non-DB external dependency.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mind.logic.engines.taxonomy_gate import TaxonomyGateEngine
from shared.path_resolver import PathResolver


_CHECK_TYPE = "sensor_supported_by_declaration"


def _fake_context(repo_root: Path) -> SimpleNamespace:
    return SimpleNamespace(repo_path=repo_root)


def _engine(repo: Path) -> TaxonomyGateEngine:
    return TaxonomyGateEngine(path_resolver=PathResolver(repo_root=repo))


def _write_sensor(
    workers_dir: Path, stem: str, artifact_types: list[str]
) -> None:
    workers_dir.mkdir(parents=True, exist_ok=True)
    (workers_dir / f"{stem}.yaml").write_text(
        "identity:\n  class: sensing\n"
        "mandate:\n  scope:\n    artifact_type: "
        + repr(artifact_types).replace("'", '"')
        + "\n",
        encoding="utf-8",
    )


def _fake_intent_repo(artifact_type_refs: list[SimpleNamespace]) -> MagicMock:
    repo = MagicMock()
    repo.initialize = MagicMock()
    repo.list_artifact_types = MagicMock(return_value=artifact_type_refs)
    return repo


def test_is_context_level_for_sensor_support_check() -> None:
    assert TaxonomyGateEngine.is_context_level_for(_CHECK_TYPE) is True


async def test_matching_authored_and_introspected_yields_no_findings(
    tmp_path: Path,
) -> None:
    """A sensor declaring artifact_type 'docs', authored in that
    artifact_type's supported_sensors -> zero findings."""
    _write_sensor(tmp_path / ".intent" / "workers", "audit_sensor_docs", ["docs"])
    fake_repo = _fake_intent_repo(
        [SimpleNamespace(id="docs", content={"supported_sensors": ["audit_sensor_docs"]})]
    )
    with patch(
        "mind.logic.engines.taxonomy_gate.get_intent_repository",
        return_value=fake_repo,
    ):
        findings = await _engine(tmp_path).verify_context(
            _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
        )
    assert findings == []


async def test_introspected_sensor_not_authored_flags_finding(tmp_path: Path) -> None:
    """A sensor declares artifact_type 'docs' but 'docs' authored
    supported_sensors is empty -> one introspected_not_authored finding."""
    _write_sensor(tmp_path / ".intent" / "workers", "audit_sensor_docs", ["docs"])
    fake_repo = _fake_intent_repo(
        [SimpleNamespace(id="docs", content={"supported_sensors": []})]
    )
    with patch(
        "mind.logic.engines.taxonomy_gate.get_intent_repository",
        return_value=fake_repo,
    ):
        findings = await _engine(tmp_path).verify_context(
            _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
        )
    assert len(findings) == 1
    f = findings[0]
    assert f.check_id == "governance.taxonomy.sensor_supported_by_declaration"
    assert f.context["direction"] == "introspected_not_authored"
    assert f.context["sensor_id"] == "audit_sensor_docs"
    assert f.context["artifact_type_id"] == "docs"


async def test_authored_sensor_not_introspected_flags_finding(tmp_path: Path) -> None:
    """artifact_type 'docs' authors 'phantom_sensor' in supported_sensors
    but no worker declaration backs it -> one authored_not_introspected
    finding. No sensor declarations at all under .intent/workers/."""
    (tmp_path / ".intent" / "workers").mkdir(parents=True)
    fake_repo = _fake_intent_repo(
        [SimpleNamespace(id="docs", content={"supported_sensors": ["phantom_sensor"]})]
    )
    with patch(
        "mind.logic.engines.taxonomy_gate.get_intent_repository",
        return_value=fake_repo,
    ):
        findings = await _engine(tmp_path).verify_context(
            _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
        )
    assert len(findings) == 1
    f = findings[0]
    assert f.context["direction"] == "authored_not_introspected"
    assert f.context["sensor_id"] == "phantom_sensor"


async def test_intent_repository_initialize_failure_is_fail_closed_block(
    tmp_path: Path,
) -> None:
    """If get_intent_repository().initialize() raises, the check must not
    silently return zero findings -- it emits a distinct BLOCK finding.
    Evidence source unavailable never counts as compliant."""
    (tmp_path / ".intent" / "workers").mkdir(parents=True)
    fake_repo = MagicMock()
    fake_repo.initialize = MagicMock(side_effect=RuntimeError("intent repo boom"))
    with patch(
        "mind.logic.engines.taxonomy_gate.get_intent_repository",
        return_value=fake_repo,
    ):
        findings = await _engine(tmp_path).verify_context(
            _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
        )
    assert len(findings) == 1
    f = findings[0]
    assert f.check_id == (
        "governance.taxonomy.sensor_supported_by_declaration.load_failed"
    )
    assert f.severity.name == "BLOCK"
