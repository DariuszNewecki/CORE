from __future__ import annotations

from mind.governance.entry_point_policy import EntryPointAllowList


# ID: 7e0f04fa-3b16-4aac-b4cf-a02332687901
def test_EntryPointAllowList_default():
    instance = EntryPointAllowList.default()

    assert isinstance(instance, EntryPointAllowList)
    assert isinstance(instance.allowed, set)

    expected_types = {
        "data_model",
        "enum",
        "magic_method",
        "visitor_method",
        "base_class",
        "boilerplate_method",
        "cli_command",
        "cli_wrapper",
        "registry_accessor",
        "orchestrator",
        "factory",
        "provider_method",
        "client_surface",
        "client_adapter",
        "io_handler",
        "git_adapter",
        "utility_function",
        "knowledge_core",
        "governance_check",
        "auditor_pipeline",
        "capability",
    }
    assert instance.allowed == expected_types
    assert "capability" in instance.allowed
