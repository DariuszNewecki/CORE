"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/audit_postprocessor.py
- Symbol: EntryPointAllowList
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:03:30
"""

import pytest
from mind.governance.audit_postprocessor import EntryPointAllowList

# EntryPointAllowList.__contains__ returns bool (detected from signature)


def test_constructor_with_valid_types():
    """Test initialization with various valid input formats."""
    # Test with list
    allow_list1 = EntryPointAllowList(["data_model", "enum", "cli_command"])
    assert allow_list1.allowed == {"data_model", "enum", "cli_command"}

    # Test with set
    allow_list2 = EntryPointAllowList({"factory", "provider_method"})
    assert allow_list2.allowed == {"factory", "provider_method"}

    # Test with tuple
    allow_list3 = EntryPointAllowList(("orchestrator", "client_adapter"))
    assert allow_list3.allowed == {"orchestrator", "client_adapter"}


def test_constructor_strips_whitespace():
    """Test that whitespace is stripped from type names."""
    allow_list = EntryPointAllowList(["  data_model  ", "\tenum\t", "cli_command\n"])
    assert allow_list.allowed == {"data_model", "enum", "cli_command"}


def test_constructor_filters_empty_and_blank():
    """Test that empty strings and whitespace-only strings are filtered out."""
    allow_list = EntryPointAllowList(["data_model", "", "   ", "\t\n", "enum"])
    assert allow_list.allowed == {"data_model", "enum"}


def test_default_contains_all_expected_types():
    """Test that default() contains all documented entry point types."""
    default_list = EntryPointAllowList.default()

    expected_types = {
        "data_model", "enum", "magic_method", "visitor_method", "base_class",
        "boilerplate_method", "cli_command", "cli_wrapper", "registry_accessor",
        "orchestrator", "factory", "provider_method", "client_surface",
        "client_adapter", "io_handler", "git_adapter", "utility_function",
        "knowledge_core", "governance_check", "auditor_pipeline", "capability"
    }

    assert default_list.allowed == expected_types


def test_contains_with_allowed_types():
    """Test __contains__ with types that are in the allow list."""
    allow_list = EntryPointAllowList(["data_model", "enum", "cli_command"])

    assert "data_model" in allow_list
    assert "enum" in allow_list
    assert "cli_command" in allow_list


def test_contains_with_disallowed_types():
    """Test __contains__ with types that are NOT in the allow list."""
    allow_list = EntryPointAllowList(["data_model", "enum"])

    assert "cli_command" not in allow_list
    assert "factory" not in allow_list
    assert "unknown_type" not in allow_list


def test_contains_with_none_and_empty():
    """Test __contains__ with None and empty string."""
    allow_list = EntryPointAllowList(["data_model", "enum"])

    # None should always return False
    assert None not in allow_list

    # Empty string should always return False
    assert "" not in allow_list
    assert "   " not in allow_list


def test_contains_is_case_sensitive():
    """Test that type matching is case-sensitive."""
    allow_list = EntryPointAllowList(["Data_Model", "ENUM"])

    assert "Data_Model" in allow_list
    assert "data_model" not in allow_list
    assert "ENUM" in allow_list
    assert "enum" not in allow_list


def test_default_instance_is_correct_type():
    """Test that default() returns an instance of EntryPointAllowList."""
    default_instance = EntryPointAllowList.default()
    assert isinstance(default_instance, EntryPointAllowList)


def test_allow_list_is_mutable():
    """Test that the internal set can be modified after creation."""
    allow_list = EntryPointAllowList(["data_model"])
    assert "enum" not in allow_list

    # Modify the internal set
    allow_list.allowed.add("enum")
    assert "enum" in allow_list


def test_constructor_with_duplicates():
    """Test that duplicates are removed during initialization."""
    allow_list = EntryPointAllowList(["data_model", "data_model", "enum", "enum"])
    assert allow_list.allowed == {"data_model", "enum"}
    assert len(allow_list.allowed) == 2
