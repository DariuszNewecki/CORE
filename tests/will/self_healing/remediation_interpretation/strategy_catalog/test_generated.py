from __future__ import annotations

from will.self_healing.remediation_interpretation.strategy_catalog import (
    StrategyCatalog,
)


# ID: 060ff901-6b2b-4b53-8713-c9b8870c3b9b
def test_StrategyCatalog_list_templates():
    catalog = StrategyCatalog()
    templates = catalog.list_templates()

    assert isinstance(templates, list)
    assert len(templates) == 9

    expected_ids = [
        "extract_helper_functions",
        "extract_private_methods",
        "extract_service_collaborator",
        "extract_analysis_service",
        "extract_repository_access",
        "split_module_by_responsibility",
        "reduce_import_surface",
        "preserve_role_extract_helpers_only",
        "defer_structural_split_choose_local_cleanup",
    ]
    assert [t.strategy_id for t in templates] == expected_ids

    for template in templates:
        assert template.summary
        assert template.rationale
        assert template.risk_level in {"low", "medium", "high"}
        assert isinstance(template.preserves_contract, bool)
        assert isinstance(template.preferred_for_roles, tuple)
        assert isinstance(template.preferred_for_rules, tuple)

    by_id = {t.strategy_id: t for t in templates}
    assert by_id["extract_helper_functions"].risk_level == "low"
    assert by_id["extract_service_collaborator"].risk_level == "medium"
    assert "model" in by_id["extract_service_collaborator"].discouraged_for_roles

    # Each call returns a fresh list of templates
    assert catalog.list_templates() is not templates


# ID: 90600c99-6f3b-446b-93c9-c57b2e394c48
def test_StrategyCatalog() -> None:
    catalog = StrategyCatalog()
    templates = catalog.list_templates()

    assert isinstance(templates, list)
    assert len(templates) == 9
    assert templates == catalog.list_templates()

    ids = [t.strategy_id for t in templates]
    assert ids == [
        "extract_helper_functions",
        "extract_private_methods",
        "extract_service_collaborator",
        "extract_analysis_service",
        "extract_repository_access",
        "split_module_by_responsibility",
        "reduce_import_surface",
        "preserve_role_extract_helpers_only",
        "defer_structural_split_choose_local_cleanup",
    ]
    assert len(set(ids)) == len(ids)

    for template in templates:
        assert isinstance(template.summary, str) and template.summary
        assert isinstance(template.rationale, str) and template.rationale
        assert template.risk_level in {"low", "medium"}
        assert template.preserves_contract is True
        assert isinstance(template.preferred_for_roles, tuple)
        assert isinstance(template.preferred_for_rules, tuple)

    by_id = {t.strategy_id: t for t in templates}

    helper = by_id["extract_helper_functions"]
    assert helper.risk_level == "low"
    assert "worker.sensor" in helper.preferred_for_roles
    assert "architecture.max_file_size" in helper.preferred_for_rules

    collaborator = by_id["extract_service_collaborator"]
    assert collaborator.risk_level == "medium"
    assert "model" in collaborator.discouraged_for_roles
    assert "repository" in collaborator.discouraged_for_roles

    defer = by_id["defer_structural_split_choose_local_cleanup"]
    assert "unknown" in defer.preferred_for_roles


from will.self_healing.remediation_interpretation.strategy_catalog import (
    StrategyTemplate,
)


# ID: 32e1fa50-1ec5-4f7c-8743-7e5ca5c7a3fc
def test_StrategyTemplate():
    strategy = StrategyTemplate(
        strategy_id="extract_helper",
        summary="Extract duplicated logic into a shared helper.",
        rationale="Reduces duplication and centralizes behavior.",
        risk_level="low",
        preserves_contract=True,
        preferred_for_roles=("utility", "service"),
        preferred_for_rules=("duplicate_code",),
        discouraged_for_roles=("entrypoint",),
        discouraged_for_rules=("public_api",),
    )

    assert strategy.strategy_id == "extract_helper"
    assert strategy.summary == "Extract duplicated logic into a shared helper."
    assert strategy.rationale == "Reduces duplication and centralizes behavior."
    assert strategy.risk_level == "low"
    assert strategy.preserves_contract is True
    assert strategy.preferred_for_roles == ("utility", "service")
    assert strategy.preferred_for_rules == ("duplicate_code",)
    assert strategy.discouraged_for_roles == ("entrypoint",)
    assert strategy.discouraged_for_rules == ("public_api",)

    minimal = StrategyTemplate(
        strategy_id="rename_symbol",
        summary="Rename symbol for clarity.",
        rationale="Improves readability.",
        risk_level="low",
        preserves_contract=True,
    )

    assert minimal.preferred_for_roles == ()
    assert minimal.preferred_for_rules == ()
    assert minimal.discouraged_for_roles == ()
    assert minimal.discouraged_for_rules == ()
