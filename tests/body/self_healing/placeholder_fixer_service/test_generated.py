from __future__ import annotations

from body.self_healing.placeholder_fixer_service import fix_placeholders_in_content


# ID: 3b6f360a-cbce-4047-b5cd-a8c9c0a43449
class TestFixPlaceholdersInContent:
    """Comprehensive tests for fix_placeholders_in_content function."""

    # ID: 8aa5b4ba-845c-4bf6-ab6e-01e0517431a6
    def test_returns_string_when_no_placeholders(self):
        """Should return the input string unchanged when no placeholders exist."""
        content = "This is a normal string without any placeholders."
        result = fix_placeholders_in_content(content)
        assert result == content

    # ID: a11b2f8f-b227-4c1f-987a-da9597a6420b
    def test_replaces_todo_with_future(self):
        """Should replace TODO with FUTURE."""
        content = "TODO: implement this feature"
        result = fix_placeholders_in_content(content)
        assert "FUTURE: implement this feature" == result

    # ID: 662cb20b-261e-4940-93a6-d500bf266815
    def test_replaces_fixme_with_pending(self):
        """Should replace FIXME with PENDING."""
        content = "FIXME: bug to fix"
        result = fix_placeholders_in_content(content)
        assert "PENDING: bug to fix" == result

    # ID: d9bff89d-c26a-45e4-bfe9-cec2b7f625b3
    def test_replaces_tbd_with_pending(self):
        """Should replace TBD with pending (lowercase)."""
        content = "TBD: decision needed"
        result = fix_placeholders_in_content(content)
        assert "pending: decision needed" == result

    # ID: f1dbb5a4-d65a-4fad-997c-d515738318cd
    def test_replaces_placeholder_with_template_value(self):
        """Should replace PLACEHOLDER with template_value."""
        content = "PLACEHOLDER: needs filling"
        result = fix_placeholders_in_content(content)
        assert "template_value: needs filling" == result

    # ID: 77ca7e7f-dc95-4945-9a89-ddd8907fd97e
    def test_replaces_na_with_none(self):
        """Should replace N/A with none."""
        content = "Value is N/A"
        result = fix_placeholders_in_content(content)
        assert "Value is none" == result

    # ID: 2aae100d-196b-413f-b42c-f9877cf6b8c6
    def test_replaces_file_path_none_variants(self):
        """Should replace file_path='none' and file_path=\"none\" with file_path=\"none\"."""
        content_single = "config(file_path='none')"
        content_double = 'config(file_path="none")'
        result_single = fix_placeholders_in_content(content_single)
        result_double = fix_placeholders_in_content(content_double)
        expected = 'config(file_path="none")'
        assert result_single == expected
        assert result_double == expected

    # ID: 6528a28c-6e98-4ecf-9103-227eb9f6f5d3
    def test_replaces_multiple_different_placeholders(self):
        """Should replace all types of placeholders in a single string."""
        content = "TODO: fix FIXME, then handle TBD and PLACEHOLDER; N/A is not set"
        result = fix_placeholders_in_content(content)
        assert (
            "FUTURE: fix PENDING, then handle pending and template_value; none is not set"
            == result
        )

    # ID: 7fe48697-3996-402b-9e7a-3c226bac79fc
    def test_replaces_multiple_occurrences_same_placeholder(self):
        """Should replace multiple occurrences of the same placeholder."""
        content = "TODO: first task, TODO: second task"
        result = fix_placeholders_in_content(content)
        assert "FUTURE: first task, FUTURE: second task" == result

    # ID: 46f687c5-c5c8-4703-a167-4b49bcaee6b0
    def test_word_boundary_enforcement(self):
        """Should only replace whole words due to \\b boundaries."""
        content = "TODOLIST will not be replaced"
        result = fix_placeholders_in_content(content)
        assert result == content

    # ID: 14ae8fd9-93bb-4118-a9de-e7ce0209a783
    def test_case_sensitivity_for_standardized_replacements(self):
        """Should replace uppercase placeholders but not lowercase variants (except N/A)."""
        content = "todo fixme tbd placeholder n/a"
        # None of these are uppercase, so they should be unchanged.
        result = fix_placeholders_in_content(content)
        assert "todo" in result
        assert "fixme" in result
        assert "tbd" in result
        assert "placeholder" in result
        # N/A includes slash so pattern is different. lowercase 'n/a' also contains slash, but pattern is \bN/A\b
        # So 'n/a' will not be replaced.
        assert "n/a" in result

    # ID: 208ac3d8-b884-4c25-8dcf-b3f217075d4d
    def test_empty_string(self):
        """Should handle empty string input."""
        content = ""
        result = fix_placeholders_in_content(content)
        assert result == ""

    # ID: acfdb15b-dede-4585-85dd-1872b74a3c0a
    def test_string_with_only_placeholders(self):
        """Should replace when the entire string is a placeholder."""
        content = "TODO"
        result = fix_placeholders_in_content(content)
        assert result == "FUTURE"

    # ID: 59934609-0709-4637-b8fb-93ca9b30968c
    def test_file_path_none_with_spaces(self):
        """Should replace file_path = 'none' with file_path=\"none\"."""
        content = "file_path = 'none'"
        result = fix_placeholders_in_content(content)
        assert result == 'file_path="none"'
