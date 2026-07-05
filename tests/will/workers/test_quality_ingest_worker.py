# tests/will/workers/test_quality_ingest_worker.py
"""Tests for QualityIngestWorker (ADR-098 D5 / closes #605).

Covers:
- run() posts heartbeat unconditionally.
- run() short-circuits with a report when no rules are enabled.
- run() posts report when audit returns no quality findings.
- _apply_cap() orders by issue_count descending and caps per rule.
- run() deduplicates against existing blackboard subjects.
- run() posts findings for all enabled rules (multi-rule path).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.workers.quality_ingest_worker import QualityIngestWorker


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_worker() -> QualityIngestWorker:
    ctx = MagicMock()
    worker = QualityIngestWorker(core_context=ctx)
    worker.post_heartbeat = AsyncMock()
    worker.post_finding = AsyncMock()
    worker.post_report = AsyncMock()
    return worker


def _make_finding(
    rule_id: str,
    file_path: str,
    issue_count: int = 1,
    tool: str = "mypy",
) -> dict:
    return {
        "check_id": rule_id,
        "file_path": file_path,
        "message": f"{issue_count} issue(s) in {file_path}",
        "context": {
            "issue_count": issue_count,
            "sample_issues": [],
            "tool": tool,
        },
    }


def _patch_config(enabled_rules: list, cap: int = 25):
    from shared.infrastructure.intent.audit_ingest_config import AuditIngestConfig

    cfg = AuditIngestConfig(quality_ingest_cap=cap, enabled_rules=enabled_rules)
    return patch(
        "will.workers.quality_ingest_worker.load_audit_ingest_config",
        return_value=cfg,
    )


def _patch_auditor(findings: list):
    mock_auditor = MagicMock()
    mock_auditor.run_full_audit_async = AsyncMock(
        return_value={"findings": findings, "stats": {}, "verdict": "PASS"}
    )
    mock_cls = MagicMock(return_value=mock_auditor)
    return patch("mind.governance.auditor.ConstitutionalAuditor", mock_cls)


async def _empty_subjects(*_args, **_kwargs) -> set:
    return set()


# ── Tests ─────────────────────────────────────────────────────────────────────


# ID: 7a2e81a2-5739-4844-8a89-993348f59a74
@pytest.mark.asyncio
async def test_run_posts_heartbeat_unconditionally() -> None:
    """Heartbeat must be posted regardless of config or audit outcome."""
    worker = _make_worker()
    with _patch_config(enabled_rules=[]):
        await worker.run()
    worker.post_heartbeat.assert_awaited_once()


# ID: ff6c599f-7aab-48da-808c-8e4190a12f8d
@pytest.mark.asyncio
async def test_run_short_circuits_when_no_rules_enabled() -> None:
    """With enabled_rules=[], post one report and no findings."""
    worker = _make_worker()
    with _patch_config(enabled_rules=[]):
        await worker.run()
    worker.post_finding.assert_not_awaited()
    worker.post_report.assert_awaited_once()
    _subject, payload = worker.post_report.call_args[0]
    assert payload["posted"] == 0
    assert payload["enabled_rules"] == []


# ID: 5f34ad3d-8630-4c2a-b6f2-5f8db3c9dc81
@pytest.mark.asyncio
async def test_run_reports_no_findings_when_audit_clean() -> None:
    """Audit with no quality violations → report posted, no findings."""
    worker = _make_worker()
    with (
        _patch_config(enabled_rules=["quality.security_audit"]),
        patch(
            "will.workers.quality_ingest_worker.QualityIngestWorker._run_audit",
            new=AsyncMock(return_value={}),
        ),
    ):
        await worker.run()

    worker.post_finding.assert_not_awaited()
    worker.post_report.assert_awaited_once()
    _subject, payload = worker.post_report.call_args[0]
    assert payload["posted"] == 0


# ID: c1115d3f-9b25-4fd6-8b56-1184e0ed3c1e
@pytest.mark.asyncio
async def test_apply_cap_orders_by_issue_count_descending() -> None:
    """_apply_cap selects top-N by issue_count, highest first."""
    from shared.infrastructure.intent.audit_ingest_config import AuditIngestConfig

    worker = _make_worker()
    grouped = {
        "quality.type_safety": [
            {"file_path": "a.py", "message": "m", "issue_count": 3, "tool": "mypy"},
            {"file_path": "b.py", "message": "m", "issue_count": 10, "tool": "mypy"},
            {"file_path": "c.py", "message": "m", "issue_count": 1, "tool": "mypy"},
        ]
    }
    config = AuditIngestConfig(
        quality_ingest_cap=2, enabled_rules=["quality.type_safety"]
    )
    capped = worker._apply_cap(grouped, config)

    assert len(capped["quality.type_safety"]) == 2
    assert capped["quality.type_safety"][0]["file_path"] == "b.py"
    assert capped["quality.type_safety"][1]["file_path"] == "a.py"


# ID: c7f7eb81-c6c5-42e5-bc4e-d0c3b4a5d387
@pytest.mark.asyncio
async def test_run_deduplicates_against_existing_subjects() -> None:
    """Already-posted subjects are skipped; only new ones are posted."""
    worker = _make_worker()

    existing = {"audit.violation::quality.security_audit::pyproject.toml"}
    findings_by_rule = {
        "quality.security_audit": [
            {
                "file_path": "pyproject.toml",
                "message": "1 vuln",
                "issue_count": 1,
                "sample_issues": [],
                "tool": "pip_audit",
            }
        ]
    }

    with (
        _patch_config(enabled_rules=["quality.security_audit"]),
        patch(
            "will.workers.quality_ingest_worker.QualityIngestWorker._run_audit",
            new=AsyncMock(return_value=findings_by_rule),
        ),
        patch(
            "will.workers.quality_ingest_worker.QualityIngestWorker._fetch_existing_subjects",
            new=AsyncMock(return_value=existing),
        ),
    ):
        await worker.run()

    worker.post_finding.assert_not_awaited()
    _subject, payload = worker.post_report.call_args[0]
    assert payload["skipped_duplicate"] == 1
    assert payload["posted"] == 0


# ID: f736f430-cade-4a1c-b324-cbd06d49b2dc
@pytest.mark.asyncio
async def test_run_posts_findings_for_enabled_rules() -> None:
    """New findings for enabled rules are posted with correct subject format."""
    worker = _make_worker()

    findings_by_rule = {
        "quality.security_audit": [
            {
                "file_path": "pyproject.toml",
                "message": "2 vulns",
                "issue_count": 2,
                "sample_issues": ["CVE-1", "CVE-2"],
                "tool": "pip_audit",
            }
        ]
    }

    with (
        _patch_config(enabled_rules=["quality.security_audit"]),
        patch(
            "will.workers.quality_ingest_worker.QualityIngestWorker._run_audit",
            new=AsyncMock(return_value=findings_by_rule),
        ),
        patch(
            "will.workers.quality_ingest_worker.QualityIngestWorker._fetch_existing_subjects",
            new=AsyncMock(return_value=set()),
        ),
    ):
        await worker.run()

    worker.post_finding.assert_awaited_once()
    subject, payload = worker.post_finding.call_args[0]
    assert subject == "audit.violation::quality.security_audit::pyproject.toml"
    assert payload["rule"] == "quality.security_audit"
    assert payload["issue_count"] == 2
    assert payload["tool"] == "pip_audit"


# ID: 415d2201-3c2c-4e14-93f4-1406e990e708
@pytest.mark.asyncio
async def test_run_respects_cap_per_rule() -> None:
    """With cap=1, only the highest issue_count finding per rule is posted."""
    worker = _make_worker()

    findings_by_rule = {
        "quality.test_integrity": [
            {
                "file_path": "tests/test_a.py",
                "message": "5 errors",
                "issue_count": 5,
                "sample_issues": [],
                "tool": "pytest_collection",
            },
            {
                "file_path": "tests/test_b.py",
                "message": "1 error",
                "issue_count": 1,
                "sample_issues": [],
                "tool": "pytest_collection",
            },
        ]
    }

    with (
        _patch_config(enabled_rules=["quality.test_integrity"], cap=1),
        patch(
            "will.workers.quality_ingest_worker.QualityIngestWorker._run_audit",
            new=AsyncMock(return_value=findings_by_rule),
        ),
        patch(
            "will.workers.quality_ingest_worker.QualityIngestWorker._fetch_existing_subjects",
            new=AsyncMock(return_value=set()),
        ),
    ):
        await worker.run()

    assert worker.post_finding.await_count == 1
    subject, _payload = worker.post_finding.call_args[0]
    assert subject == "audit.violation::quality.test_integrity::tests/test_a.py"

    _subject, report_payload = worker.post_report.call_args[0]
    assert report_payload["skipped_cap"] == 1
