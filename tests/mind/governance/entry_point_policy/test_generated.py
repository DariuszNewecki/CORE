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


# ID: 72cbf3b4-393e-40d8-9831-fec40824ae9d
def test_EntryPointAllowList():
    # Direct construction with a custom set of allowed types
    allow_list = EntryPointAllowList(["cli_command", "  factory  ", "", None])
    assert "cli_command" in allow_list
    assert "factory" in allow_list
    assert "" not in allow_list
    assert None not in allow_list
    assert "unknown_type" not in allow_list

    # Default allow-list exposes CORE's architectural patterns
    default_list = EntryPointAllowList.default()
    assert isinstance(default_list, EntryPointAllowList)
    assert "data_model" in default_list
    assert "cli_command" in default_list
    assert "governance_check" in default_list
    assert "capability" in default_list
    assert "not_a_real_entry_point" not in default_list
    assert None not in default_list
