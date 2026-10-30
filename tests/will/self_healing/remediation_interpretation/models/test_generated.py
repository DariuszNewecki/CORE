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
