from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from cli.resources.code.audit import audit_command


# ID: c088569a-e80d-4f96-b44d-99f4b891f3b6
async def test_audit_command():
    """Test happy path: online audit with no findings, using mocks."""
    mock_ctx = MagicMock()

    mock_client = AsyncMock()
    mock_client.audit.return_value = {
        "passed": True,
        "verdict": "pass",
        "duration_sec": 1.5,
        "stats": {
            "total_executable_rules": 10,
            "executed_dynamic_rules": 8,
            "coverage_percent": 80.0,
            "total_declared_rules": 12,
            "crashed_rules": 0,
            "unmapped_rules": 1,
            "effective_coverage_percent": 75.0,
            "context_level_rules": 3,
            "per_file_rules": 5,
        },
        "findings": [],
    }

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_coherence_service = MagicMock()
    mock_representation_service = MagicMock()

    with (
        patch("cli.resources.code.audit.CoreApiClient", return_value=mock_client),
        patch("cli.resources.code.audit.get_session", return_value=mock_session),
        patch(
            "cli.resources.code.audit.CoherenceService",
            return_value=mock_coherence_service,
        ),
        patch(
            "cli.resources.code.audit.RepresentationCoherenceService",
            return_value=mock_representation_service,
        ),
        patch("cli.resources.code.audit.render_overview") as mock_render,
        patch("cli.resources.code.audit.to_audit_finding") as mock_to_finding,
        patch("cli.resources.code.audit.AuditStats") as mock_audit_stats,
        patch("cli.resources.code.audit.parse_min_severity") as mock_parse_severity,
        patch("cli.resources.code.audit.print_hidden_findings_hint") as mock_print_hint,
    ):
        mock_parse_severity.return_value = 2  # SEVERITY for "high"
        mock_to_finding.return_value = (
            MagicMock()
        )  # no actual findings, so return value unused
        mock_audit_stats.return_value = MagicMock()

        # Call the function
        await audit_command(
            ctx=mock_ctx,
            severity="high",
            rule=[],
            policy=[],
            files=[],
            verbose=False,
            classify=False,
            force_llm=False,
            offline=False,
            target=None,
            output_format="text",
        )

        # Assertions
        mock_parse_severity.assert_called_once_with("high")
        mock_client.audit.assert_awaited_once_with(
            rule_ids=[],
            policy_ids=[],
            files=[],
            force_llm=False,
            source="manual",
        )
        mock_render.assert_called_once()
        mock_print_hint.assert_called_once()
        assert mock_session.__aenter__.await_count == 2
        assert mock_session.__aexit__.await_count == 2
