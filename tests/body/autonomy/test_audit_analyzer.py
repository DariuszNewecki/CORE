# tests/body/autonomy/test_audit_analyzer.py

"""#842 Unit C: autonomy.remediation.min_confidence_floor fixture pair.

Depth-verifies the passive_gate Class A mapping in
.intent/enforcement/mappings/will/autonomy.yaml, which names
body.autonomy.audit_analyzer.AuditAnalyzer as enforced_by: "RemediationMap
MUST NOT dispatch entries below confidence 0.80." No prior test exercised
this class at all.

Uses the real AuditAnalyzer.analyze_findings() dispatch logic (the
confidence comparison, fixable/not_fixable bucketing) against a synthetic
remediation map and findings file -- only the remediation-map *source* is
substituted (via the documented _get_remediation_map seam), not the
comparison logic itself, so this is a real test of the real gate, not a
mock of the behavior under test. _min_confidence is pinned explicitly so
the fixture stays deterministic regardless of what
governance_paths.yaml's real threshold happens to be at any given time.
"""

from __future__ import annotations

import json
from pathlib import Path

from body.autonomy.audit_analyzer import AuditAnalyzer


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _analyzer(monkeypatch, *, confidence: float) -> AuditAnalyzer:
    analyzer = AuditAnalyzer(repo_root=_REPO_ROOT)
    monkeypatch.setattr(analyzer, "_min_confidence", 0.80)
    monkeypatch.setattr(
        analyzer,
        "_get_remediation_map",
        lambda: {
            "test.synthetic.rule": {
                "action": "fix.synthetic",
                "flow": None,
                "ref_id": "fix.synthetic",
                "ref_kind": "action",
                "confidence": confidence,
                "description": "synthetic fixture entry",
                "status": "ACTIVE",
            }
        },
    )
    return analyzer


def _write_findings(tmp_path: Path) -> Path:
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps([{"check_id": "test.synthetic.rule", "file_path": "src/foo.py"}])
    )
    return findings_path


def test_below_confidence_floor_excluded_from_fixable(tmp_path, monkeypatch) -> None:
    """A remediation entry below the 0.80 floor is not dispatched -- it
    lands in not_fixable, not fixable_by_action."""
    analyzer = _analyzer(monkeypatch, confidence=0.50)
    findings_path = _write_findings(tmp_path)

    result = analyzer.analyze_findings(findings_path=findings_path)

    assert result["status"] == "success"
    assert result["auto_fixable_count"] == 0
    assert result["fixable_by_action"] == {}
    assert len(result["not_fixable"]) == 1
    assert result["not_fixable"][0]["check_id"] == "test.synthetic.rule"


def test_at_or_above_confidence_floor_included_in_fixable(
    tmp_path, monkeypatch
) -> None:
    """A remediation entry at or above the 0.80 floor is dispatched --
    it lands in fixable_by_action, keyed by its action id."""
    analyzer = _analyzer(monkeypatch, confidence=0.90)
    findings_path = _write_findings(tmp_path)

    result = analyzer.analyze_findings(findings_path=findings_path)

    assert result["status"] == "success"
    assert result["auto_fixable_count"] == 1
    assert "fix.synthetic" in result["fixable_by_action"]
    assert result["fixable_by_action"]["fix.synthetic"][0]["check_id"] == (
        "test.synthetic.rule"
    )
    assert result["not_fixable"] == []
