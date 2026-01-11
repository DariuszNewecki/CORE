"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/enforcement_methods.py
- Symbol: KnowledgeSSOTEnforcement
- Status: 8 tests passed, some failed
- Passing tests: test_verify_async_table_empty, test_verify_async_duplicate_primary_keys, test_verify_async_table_check_fails, test_verify_async_session_error, test_verify_async_pk_uniqueness_check_fails, test_verify_async_multiple_tables_mixed_results, test_init_with_custom_severity, test_ssot_tables_structure
- Generated: 2026-01-11 01:43:44
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mind.governance.enforcement_methods import AuditSeverity, KnowledgeSSOTEnforcement


@pytest.mark.asyncio
async def test_verify_async_table_empty():
    """Test verification when a table is empty."""
    enforcement = KnowledgeSSOTEnforcement(rule_id="test.rule")
    context = MagicMock()
    rule_data = {}
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0
    mock_session.execute.return_value = mock_result
    with patch(
        "shared.infrastructure.database.session_manager.get_session"
    ) as mock_get_session:
        mock_get_session.return_value.__aenter__.return_value = mock_session
        findings = await enforcement.verify_async(context, rule_data)
        assert len(findings) > 0
        assert any("is empty" in finding.message for finding in findings)
        assert all(finding.severity == AuditSeverity.ERROR for finding in findings)


@pytest.mark.asyncio
async def test_verify_async_duplicate_primary_keys():
    """Test verification when duplicate primary keys are found."""
    enforcement = KnowledgeSSOTEnforcement(rule_id="test.rule")
    context = MagicMock()
    rule_data = {}
    mock_session = AsyncMock(spec=AsyncSession)
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 5
    mock_dup_result = MagicMock()
    mock_dup_result.fetchall.return_value = [("key1", 2), ("key2", 3)]
    mock_session.execute.side_effect = [mock_count_result, mock_dup_result]
    with patch(
        "shared.infrastructure.database.session_manager.get_session"
    ) as mock_get_session:
        mock_get_session.return_value.__aenter__.return_value = mock_session
        findings = await enforcement.verify_async(context, rule_data)
        assert len(findings) > 0
        assert any("duplicate primary keys" in finding.message for finding in findings)
        assert all(finding.severity == AuditSeverity.ERROR for finding in findings)


@pytest.mark.asyncio
async def test_verify_async_table_check_fails():
    """Test verification when table check fails with exception."""
    enforcement = KnowledgeSSOTEnforcement(rule_id="test.rule")
    context = MagicMock()
    rule_data = {}
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = Exception("Database connection failed")
    with patch(
        "shared.infrastructure.database.session_manager.get_session"
    ) as mock_get_session:
        mock_get_session.return_value.__aenter__.return_value = mock_session
        findings = await enforcement.verify_async(context, rule_data)
        assert len(findings) > 0
        assert any("table check failed" in finding.message for finding in findings)
        assert all(finding.severity == AuditSeverity.ERROR for finding in findings)


@pytest.mark.asyncio
async def test_verify_async_session_error():
    """Test verification when session creation fails."""
    enforcement = KnowledgeSSOTEnforcement(rule_id="test.rule")
    context = MagicMock()
    rule_data = {}
    with patch(
        "shared.infrastructure.database.session_manager.get_session"
    ) as mock_get_session:
        mock_get_session.side_effect = Exception("Session creation failed")
        findings = await enforcement.verify_async(context, rule_data)
        assert len(findings) == 1
        assert "DB SSOT audit failed" in findings[0].message
        assert findings[0].severity == AuditSeverity.ERROR
        assert findings[0].file_path == "DB"


@pytest.mark.asyncio
async def test_verify_async_pk_uniqueness_check_fails():
    """Test verification when PK uniqueness check fails with exception."""
    enforcement = KnowledgeSSOTEnforcement(rule_id="test.rule")
    context = MagicMock()
    rule_data = {}
    mock_session = AsyncMock(spec=AsyncSession)
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 5
    mock_session.execute.side_effect = [
        mock_count_result,
        Exception("Syntax error in PK query"),
    ]
    with patch(
        "shared.infrastructure.database.session_manager.get_session"
    ) as mock_get_session:
        mock_get_session.return_value.__aenter__.return_value = mock_session
        findings = await enforcement.verify_async(context, rule_data)
        assert len(findings) > 0
        assert any(
            "PK uniqueness check failed" in finding.message for finding in findings
        )
        assert all(finding.severity == AuditSeverity.ERROR for finding in findings)


@pytest.mark.asyncio
async def test_verify_async_multiple_tables_mixed_results():
    """Test verification with multiple tables having mixed results."""
    enforcement = KnowledgeSSOTEnforcement(rule_id="test.rule")
    context = MagicMock()
    rule_data = {}
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result1 = MagicMock()
    mock_result1.scalar_one.return_value = 10
    mock_result2 = MagicMock()
    mock_result2.scalar_one.return_value = 0
    mock_result3 = MagicMock()
    mock_result3.scalar_one.return_value = 5
    mock_dup_result3 = MagicMock()
    mock_dup_result3.fetchall.return_value = [("dup_key", 2)]
    mock_result4 = MagicMock()
    mock_result4.scalar_one.side_effect = Exception("Table not found")
    mock_session.execute.side_effect = [
        mock_result1,
        mock_dup_result3,
        mock_result2,
        mock_result3,
        mock_dup_result3,
        mock_result4,
    ]
    with patch(
        "shared.infrastructure.database.session_manager.get_session"
    ) as mock_get_session:
        mock_get_session.return_value.__aenter__.return_value = mock_session
        findings = await enforcement.verify_async(context, rule_data)
        assert len(findings) >= 3
        assert any("is empty" in finding.message for finding in findings)
        assert any("duplicate primary keys" in finding.message for finding in findings)
        assert any("table check failed" in finding.message for finding in findings)


@pytest.mark.asyncio
async def test_init_with_custom_severity():
    """Test initialization with custom severity."""
    enforcement = KnowledgeSSOTEnforcement(
        rule_id="custom.rule", severity=AuditSeverity.WARNING
    )
    assert enforcement.rule_id == "custom.rule"
    assert enforcement.severity == AuditSeverity.WARNING


@pytest.mark.asyncio
async def test_ssot_tables_structure():
    """Test that _SSOT_TABLES has the correct structure."""
    enforcement = KnowledgeSSOTEnforcement(rule_id="test.rule")
    assert len(enforcement._SSOT_TABLES) == 4
    required_keys = {"name", "rule_id", "table", "primary_key"}
    for table_cfg in enforcement._SSOT_TABLES:
        assert set(table_cfg.keys()) == required_keys
        assert all(isinstance(table_cfg[key], str) for key in required_keys)
        assert len(table_cfg["name"]) > 0
        assert len(table_cfg["rule_id"]) > 0
        assert len(table_cfg["table"]) > 0
        assert len(table_cfg["primary_key"]) > 0
