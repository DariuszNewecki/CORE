# tests/mind/logic/engines/test_runtime_gate__engine_dispatch.py

"""#842 Unit J: runtime.worker_max_interval_within_observed via the real
RuntimeGateEngine.verify_context dispatch (not just the private
_check_worker_max_interval_within_observed function that
test_runtime_gate__worker_max_interval.py already covers thoroughly).

#856 made the dependency-absence path fail closed: the real dispatch
path now returns an aggregated BLOCK/ENFORCEMENT_UNAVAILABLE finding
instead of an empty (compliant) list when db_session is absent, same as
the private function it wraps. Live mapping params loaded from the real
.intent/enforcement/mappings/ YAML.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import yaml

from mind.logic.engines.runtime_gate import RuntimeGateEngine


_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
_MAPPINGS = _REPO_ROOT / ".intent" / "enforcement" / "mappings"


def _load_rule_params(mapping_rel: str, rule_id: str) -> dict:
    path = _MAPPINGS / mapping_rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["mappings"][rule_id]["params"]


def _write_worker_yaml(
    workers_dir: Path, stem: str, uuid_str: str, max_interval: int
) -> None:
    workers_dir.mkdir(parents=True, exist_ok=True)
    decl: dict[str, Any] = {
        "metadata": {"status": "active"},
        "identity": {"uuid": uuid_str},
        "mandate": {"schedule": {"max_interval": max_interval}},
    }
    (workers_dir / f"{stem}.yaml").write_text(yaml.dump(decl), encoding="utf-8")


def _ctx_with_rows(repo_root: Path, rows: list[Any], db_session: Any = "build") -> Any:
    if db_session == "build":

        async def _execute(*_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(first=lambda: rows.pop(0) if rows else None)

        db_session = SimpleNamespace(execute=AsyncMock(side_effect=_execute))
    return SimpleNamespace(repo_path=repo_root, db_session=db_session)


async def test_engine_dispatch_fires_on_genuine_drift(tmp_path: Path) -> None:
    """Real engine, live mapping params, real BLOCK finding for a worker
    whose observed p95 exceeds configured x 1.1 -- proves the mechanism
    itself is sound."""
    _write_worker_yaml(
        tmp_path / ".intent" / "workers",
        "alpha",
        "11111111-2222-3333-4444-555555555555",
        600,
    )
    params = _load_rule_params(
        "runtime/worker_max_interval.yaml", "runtime.worker_max_interval_within_observed"
    )
    ctx = _ctx_with_rows(tmp_path, [SimpleNamespace(samples=50, p95=900.0)])
    findings = await RuntimeGateEngine().verify_context(ctx, params)
    assert len(findings) == 1
    assert findings[0].check_id == "runtime.worker_max_interval_within_observed"
    assert findings[0].severity.name == "BLOCK"


async def test_engine_dispatch_clean_for_worker_within_threshold(tmp_path: Path) -> None:
    _write_worker_yaml(
        tmp_path / ".intent" / "workers",
        "alpha",
        "11111111-2222-3333-4444-555555555555",
        600,
    )
    params = _load_rule_params(
        "runtime/worker_max_interval.yaml", "runtime.worker_max_interval_within_observed"
    )
    ctx = _ctx_with_rows(tmp_path, [SimpleNamespace(samples=50, p95=620.0)])
    findings = await RuntimeGateEngine().verify_context(ctx, params)
    assert findings == []


async def test_engine_dispatch_surfaces_unavailable_when_db_session_absent(
    tmp_path: Path,
) -> None:
    """#856 -- the real engine's dispatch path fails closed: one
    aggregated BLOCK/ENFORCEMENT_UNAVAILABLE finding for a blocking rule
    when db_session is unavailable, not an empty (compliant) list.
    Mirrors test_runtime_gate__worker_max_interval.py's
    test_db_session_absent_surfaces_unavailable at the
    RuntimeGateEngine.verify_context dispatch layer instead of the
    private function directly."""
    _write_worker_yaml(
        tmp_path / ".intent" / "workers",
        "alpha",
        "11111111-2222-3333-4444-555555555555",
        600,
    )
    params = _load_rule_params(
        "runtime/worker_max_interval.yaml", "runtime.worker_max_interval_within_observed"
    )
    ctx = _ctx_with_rows(tmp_path, [], db_session=None)
    findings = await RuntimeGateEngine().verify_context(ctx, params)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "runtime.worker_max_interval_within_observed"
    assert finding.severity.name == "BLOCK"
    assert finding.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert finding.context["reason"] == "db_session_unavailable"
    assert finding.context["affected_worker_stems"] == ["alpha"]
