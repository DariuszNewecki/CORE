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
