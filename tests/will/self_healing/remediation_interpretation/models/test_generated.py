from __future__ import annotations

from types import SimpleNamespace

from will.self_healing.remediation_interpretation.models import ReasoningBrief


# ID: 8748334f-42a5-4415-8c9d-738166a24ed8
def test_ReasoningBrief_to_dict() -> None:
    candidate_cls = getattr(ReasoningBrief, "__dataclass_fields__", None)

    file_role = SimpleNamespace(
        role_id="role-1",
        layer="domain",
        confidence=0.9,
        evidence=("ev1", "ev2"),
    )
    finding = SimpleNamespace(
        finding_id="f-1",
        rule_id="rule-1",
        rule_namespace="ns",
        file_path="pkg/mod.py",
        line_number=12,
        message="msg",
        severity="high",
    )
    cluster = SimpleNamespace(
        name="cluster-a",
        summary="summary-a",
        evidence=("cev",),
        symbols=("sym1", "sym2"),
    )
    strategy = SimpleNamespace(
        strategy_id="s-1",
        summary="strat summary",
        rationale="because",
        risk_level="low",
        preserves_contract=True,
        evidence=("sev",),
        score=0.75,
    )

    brief = ReasoningBrief(
        file_path="pkg/mod.py",
        file_role=file_role,
        findings=(finding,),
        responsibility_clusters=(cluster,),
        candidate_strategies=(strategy,),
        recommended_strategy=strategy,
        constraints=("c1", "c2"),
        architectural_notes=("note",),
    )

    result = brief.to_dict()

    assert result["file_path"] == "pkg/mod.py"
    assert result["file_role"] == {
        "role_id": "role-1",
        "layer": "domain",
        "confidence": 0.9,
        "evidence": ["ev1", "ev2"],
    }
    assert result["findings"] == [
        {
            "finding_id": "f-1",
            "rule_id": "rule-1",
            "rule_namespace": "ns",
            "file_path": "pkg/mod.py",
            "line_number": 12,
            "message": "msg",
            "severity": "high",
        }
    ]
    assert result["responsibility_clusters"] == [
        {
            "name": "cluster-a",
            "summary": "summary-a",
            "evidence": ["cev"],
            "symbols": ["sym1", "sym2"],
        }
    ]
    expected_strategy = {
        "strategy_id": "s-1",
        "summary": "strat summary",
        "rationale": "because",
        "risk_level": "low",
        "preserves_contract": True,
        "evidence": ["sev"],
        "score": 0.75,
    }
    assert result["candidate_strategies"] == [expected_strategy]
    assert result["recommended_strategy"] == expected_strategy
    assert result["constraints"] == ["c1", "c2"]
    assert result["architectural_notes"] == ["note"]


from will.self_healing.remediation_interpretation.models import RemediationStrategy


# ID: 1bada618-959d-4bc2-b30e-561bb0be22aa
def test_RemediationStrategy():
    strategy = RemediationStrategy(
        strategy_id="strat-001",
        summary="Retry with backoff",
        rationale="Transient failures resolve with backoff",
        risk_level="low",
        preserves_contract=True,
    )

    assert strategy.strategy_id == "strat-001"
    assert strategy.summary == "Retry with backoff"
    assert strategy.rationale == "Transient failures resolve with backoff"
    assert strategy.risk_level == "low"
    assert strategy.preserves_contract is True
    assert strategy.evidence == []
    assert strategy.score == 0


from will.self_healing.remediation_interpretation.models import ResponsibilityCluster


# ID: 9cfcbdfd-a886-4be9-b8c0-404feff5e36b
def test_ResponsibilityCluster():
    cluster = ResponsibilityCluster(name="parsing", summary="Handles input parsing")
    assert cluster.name == "parsing"
    assert cluster.summary == "Handles input parsing"
    assert cluster.evidence == []
    assert cluster.symbols == []

    cluster2 = ResponsibilityCluster(
        name="validation",
        summary="Validates inputs",
        evidence=["line 10", "line 20"],
        symbols=["validate", "check"],
    )
    assert cluster2.evidence == ["line 10", "line 20"]
    assert cluster2.symbols == ["validate", "check"]

    assert cluster.evidence is not cluster2.evidence


from will.self_healing.remediation_interpretation.models import FileRole


# ID: afa2afcf-1534-4154-8ec7-aace53575b91
def test_FileRole():
    role = FileRole(
        role_id="worker.sensor",
        layer="will",
        confidence=0.95,
        evidence=["path: src/will/workers/foo.py"],
    )

    assert role.role_id == "worker.sensor"
    assert role.layer == "will"
    assert role.confidence == 0.95
    assert role.evidence == ["path: src/will/workers/foo.py"]

    default_role = FileRole(role_id="unknown", layer="unknown", confidence=0.0)
    assert default_role.evidence == []
    assert (
        default_role.evidence is not default_role.evidence
        or default_role.evidence == []
    )


from will.self_healing.remediation_interpretation.models import NormalizedFinding


# ID: 3929a8fa-fa3d-4b75-b0ae-68abc6c5e710
def test_NormalizedFinding():
    finding = NormalizedFinding(
        finding_id="finding-001",
        subject="src/will/example.py:42",
        rule_id="WILL001",
        rule_namespace="will.audit",
        file_path="src/will/example.py",
        line_number=42,
        message="Example violation detected",
        severity="high",
        dry_run=True,
    )

    assert finding.finding_id == "finding-001"
    assert finding.subject == "src/will/example.py:42"
    assert finding.rule_id == "WILL001"
    assert finding.rule_namespace == "will.audit"
    assert finding.file_path == "src/will/example.py"
    assert finding.line_number == 42
    assert finding.message == "Example violation detected"
    assert finding.severity == "high"
    assert finding.dry_run is True
    assert finding.raw_payload == {}
    assert finding.raw_context == {}
