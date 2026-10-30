from __future__ import annotations

from unittest.mock import MagicMock

from will.self_healing.remediation_interpretation.strategy_selector import (
    _CFG,
    StrategySelector,
)


# ID: 88d9f8f3-d63e-4238-a88e-f44900c2b401
def test_StrategySelector_choose_recommended():
    selector = StrategySelector()

    top_strategy = MagicMock()
    top_strategy.score = _CFG.min_recommended_score + 1.0

    other_strategy = MagicMock()
    other_strategy.score = _CFG.min_recommended_score - 1.0

    candidate_strategies = [top_strategy, other_strategy]

    result = selector.choose_recommended(candidate_strategies)

    assert result is top_strategy


# ID: bcb37792-795c-4152-9135-36c1721b729c
def test_StrategySelector_select():
    template_a = MagicMock()
    template_a.strategy_id = "strategy_a"
    template_a.summary = "summary_a"
    template_a.rationale = "rationale_a"
    template_a.risk_level = "low"
    template_a.preserves_contract = True

    template_b = MagicMock()
    template_b.strategy_id = "strategy_b"
    template_b.summary = "summary_b"
    template_b.rationale = "rationale_b"
    template_b.risk_level = "medium"
    template_b.preserves_contract = False

    catalog = MagicMock()
    catalog.list_templates.return_value = [template_a, template_b]

    selector = StrategySelector(strategy_catalog=catalog)

    scores = {id(template_a): (10, ["ev_a"]), id(template_b): (50, ["ev_b"])}

    # ID: 7006f6a1-36ed-4b37-b424-c77ced1635b3
    def fake_score(template, file_role, file_context, responsibility_clusters):
        return scores[id(template)]

    selector._score_template = fake_score

    file_role = MagicMock()
    file_context = {"path": "src/foo.py"}
    responsibility_clusters = [MagicMock(), MagicMock()]

    result = selector.select(
        file_role=file_role,
        file_context=file_context,
        responsibility_clusters=responsibility_clusters,
    )

    catalog.list_templates.assert_called_once()

    assert len(result) == 2
    assert result[0].strategy_id == "strategy_b"
    assert result[0].score == 50
    assert result[0].evidence == ["ev_b"]
    assert result[0].summary == "summary_b"
    assert result[0].risk_level == "medium"
    assert result[0].preserves_contract is False

    assert result[1].strategy_id == "strategy_a"
    assert result[1].score == 10
    assert result[1].evidence == ["ev_a"]
    assert result[1].summary == "summary_a"
    assert result[1].risk_level == "low"
    assert result[1].preserves_contract is True


from unittest.mock import patch


# ID: e061de84-0951-4e50-a34b-985c1023d92e
def test_StrategySelector():
    strategy_selector_module = (
        "will.self_healing.remediation_interpretation.strategy_selector"
    )

    FileRole = MagicMock()
    ResponsibilityCluster = MagicMock()
    StrategyTemplate = MagicMock()
    RemediationStrategy = MagicMock(side_effect=lambda **kwargs: kwargs)

    template = MagicMock()
    template.strategy_id = "extract_helper_functions"
    template.summary = "Extract helper functions"
    template.rationale = "Reduces complexity"
    template.risk_level = "low"
    template.preserves_contract = True
    template.preferred_for_roles = ("service",)
    template.discouraged_for_roles = ()
    template.preferred_for_rules = ()
    template.discouraged_for_rules = ()

    catalog = MagicMock()
    catalog.list_templates.return_value = [template]

    file_role = MagicMock()
    file_role.role_id = "service"
    file_role.layer = "body"

    file_context = {
        "file_metrics": {"line_count": 100},
        "violation_summary": {},
        "role_constraints": [],
    }
    responsibility_clusters = []

    with (
        patch.object(
            StrategySelector,
            "_score_template",
            return_value=(7, ["some evidence"]),
        ) as mock_score,
        patch.object(
            StrategySelector,
            "_dedupe_preserve_order",
            side_effect=lambda items: items,
        ),
        patch(
            f"{strategy_selector_module}.RemediationStrategy",
            RemediationStrategy,
        ),
    ):
        selector = StrategySelector(strategy_catalog=catalog)
        result = selector.select(file_role, file_context, responsibility_clusters)

    assert isinstance(result, list)
    assert len(result) == 1
    mock_score.assert_called_once_with(
        template=template,
        file_role=file_role,
        file_context=file_context,
        responsibility_clusters=responsibility_clusters,
    )
    produced = result[0]
    assert produced["strategy_id"] == "extract_helper_functions"
    assert produced["score"] == 7
    assert produced["evidence"] == ["some evidence"]
    assert produced["risk_level"] == "low"
    assert produced["preserves_contract"] is True
