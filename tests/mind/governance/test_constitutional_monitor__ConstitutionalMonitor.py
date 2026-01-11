"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/constitutional_monitor.py
- Symbol: ConstitutionalMonitor
- Status: 12 tests passed, some failed
- Passing tests: test_audit_headers_no_python_files, test_audit_headers_compliant_file, test_audit_headers_all_violations, test_audit_headers_partial_violations, test_remediate_violations_empty_report, test_remediate_violations_successful_fix, test_remediate_violations_unknown_handler, test_remediate_violations_with_knowledge_builder, test_remediate_violations_no_knowledge_builder, test_remediate_violations_file_not_found, test_audit_headers_multiple_files_mixed_compliance, test_init_with_string_path
- Generated: 2026-01-11 01:23:01
"""

import pytest
from pathlib import Path
from mind.governance.constitutional_monitor import ConstitutionalMonitor

@pytest.mark.asyncio
async def test_audit_headers_no_python_files(tmp_path):
    """Test audit_headers when no Python files exist."""
    monitor = ConstitutionalMonitor(tmp_path)
    report = monitor.audit_headers()
    assert report.policy_category == 'header_compliance'
    assert report.violations == []
    assert report.total_files_scanned == 0
    assert report.compliant_files == 0

@pytest.mark.asyncio
async def test_audit_headers_compliant_file(tmp_path):
    """Test audit_headers with a fully compliant Python file."""
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    file_path = src_dir / 'test_module.py'
    compliant_content = '# src/test_module.py\n"""Provides functionality for the test_module module."""\nfrom __future__ import annotations\n\ndef some_function():\n    pass\n'
    file_path.write_text(compliant_content, encoding='utf-8')
    monitor = ConstitutionalMonitor(tmp_path)
    report = monitor.audit_headers()
    assert report.policy_category == 'header_compliance'
    assert report.violations == []
    assert report.total_files_scanned == 1
    assert report.compliant_files == 1

@pytest.mark.asyncio
async def test_audit_headers_all_violations(tmp_path):
    """Test audit_headers with all possible violations."""
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    file_path = src_dir / 'bad_module.py'
    non_compliant_content = 'def bad_function():\n    pass\n'
    file_path.write_text(non_compliant_content, encoding='utf-8')
    monitor = ConstitutionalMonitor(tmp_path)
    report = monitor.audit_headers()
    assert report.policy_category == 'header_compliance'
    assert len(report.violations) == 1
    assert report.total_files_scanned == 1
    assert report.compliant_files == 0
    violation = report.violations[0]
    assert violation.file_path == 'src/bad_module.py'
    assert violation.policy_id == 'header_compliance'
    assert violation.severity == 'medium'
    assert violation.remediation_handler == 'fix_header'
    assert 'incorrect file location comment' in violation.description
    assert 'missing module docstring' in violation.description
    assert 'missing __future__ import' in violation.description

@pytest.mark.asyncio
async def test_audit_headers_partial_violations(tmp_path):
    """Test audit_headers with only some violations."""
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    file_path = src_dir / 'partial_module.py'
    partial_content = '# src/partial_module.py\n\ndef some_function():\n    pass\n'
    file_path.write_text(partial_content, encoding='utf-8')
    monitor = ConstitutionalMonitor(tmp_path)
    report = monitor.audit_headers()
    assert len(report.violations) == 1
    violation = report.violations[0]
    assert 'missing module docstring' in violation.description
    assert 'missing __future__ import' in violation.description
    assert 'incorrect file location comment' not in violation.description

@pytest.mark.asyncio
async def test_remediate_violations_empty_report(tmp_path):
    """Test remediate_violations with empty audit report."""
    monitor = ConstitutionalMonitor(tmp_path)
    from mind.governance.constitutional_monitor import AuditReport, Violation
    empty_report = AuditReport(policy_category='header_compliance', violations=[], total_files_scanned=0, compliant_files=0)
    result = await monitor.remediate_violations(empty_report)
    assert result.success == True
    assert result.fixed_count == 0
    assert result.failed_count == 0
    assert result.error is None

@pytest.mark.asyncio
async def test_remediate_violations_successful_fix(tmp_path):
    """Test successful remediation of header violations."""
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    file_path = src_dir / 'test.py'
    original_content = 'def test():\n    pass\n'
    file_path.write_text(original_content, encoding='utf-8')
    monitor = ConstitutionalMonitor(tmp_path)
    report = monitor.audit_headers()
    assert len(report.violations) == 1
    result = await monitor.remediate_violations(report)
    assert result.success == True
    assert result.fixed_count == 1
    assert result.failed_count == 0
    assert result.error is None
    fixed_content = file_path.read_text(encoding='utf-8')
    assert '# src/test.py' in fixed_content
    assert '"""Provides functionality for the test module."""' in fixed_content
    assert 'from __future__ import' in fixed_content

@pytest.mark.asyncio
async def test_remediate_violations_unknown_handler(tmp_path):
    """Test remediation with unknown handler type."""
    monitor = ConstitutionalMonitor(tmp_path)
    from mind.governance.constitutional_monitor import AuditReport, Violation
    report = AuditReport(policy_category='test', violations=[Violation(file_path='test.py', policy_id='unknown', description='test', severity='low', remediation_handler='unknown_handler')], total_files_scanned=1, compliant_files=0)
    result = await monitor.remediate_violations(report)
    assert result.success == False
    assert result.fixed_count == 0
    assert result.failed_count == 1
    assert result.error == '1 violations failed'

@pytest.mark.asyncio
async def test_remediate_violations_with_knowledge_builder(tmp_path, mocker):
    """Test remediation triggers knowledge builder rebuild when fixes occur."""
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    file_path = src_dir / 'test.py'
    file_path.write_text('def test(): pass', encoding='utf-8')
    mock_builder = mocker.AsyncMock()
    monitor = ConstitutionalMonitor(tmp_path, knowledge_builder=mock_builder)
    report = monitor.audit_headers()
    result = await monitor.remediate_violations(report)
    assert result.fixed_count == 1
    mock_builder.build_and_sync.assert_called_once()

@pytest.mark.asyncio
async def test_remediate_violations_no_knowledge_builder(tmp_path):
    """Test remediation without knowledge builder doesn't crash."""
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    file_path = src_dir / 'test.py'
    file_path.write_text('def test(): pass', encoding='utf-8')
    monitor = ConstitutionalMonitor(tmp_path, knowledge_builder=None)
    report = monitor.audit_headers()
    result = await monitor.remediate_violations(report)
    assert result.fixed_count == 1
    assert result.success == True

@pytest.mark.asyncio
async def test_remediate_violations_file_not_found(tmp_path):
    """Test remediation when violation file doesn't exist."""
    monitor = ConstitutionalMonitor(tmp_path)
    from mind.governance.constitutional_monitor import AuditReport, Violation
    report = AuditReport(policy_category='header_compliance', violations=[Violation(file_path='nonexistent.py', policy_id='header_compliance', description='Header violations: incorrect file location comment, missing module docstring, missing __future__ import', severity='medium', remediation_handler='fix_header')], total_files_scanned=1, compliant_files=0)
    result = await monitor.remediate_violations(report)
    assert result.success == False
    assert result.fixed_count == 0
    assert result.failed_count == 1

@pytest.mark.asyncio
async def test_audit_headers_multiple_files_mixed_compliance(tmp_path):
    """Test audit_headers with multiple files having mixed compliance."""
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    files = {'compliant.py': '# src/compliant.py\n"""Docstring."""\nfrom __future__ import annotations\n\npass\n', 'no_future.py': '# src/no_future.py\n"""Docstring."""\n\npass\n', 'no_docstring.py': '# src/no_docstring.py\nfrom __future__ import annotations\n\npass\n'}
    for filename, content in files.items():
        (src_dir / filename).write_text(content, encoding='utf-8')
    monitor = ConstitutionalMonitor(tmp_path)
    report = monitor.audit_headers()
    assert report.total_files_scanned == 3
    assert len(report.violations) == 2
    assert report.compliant_files == 1
    violation_files = {v.file_path for v in report.violations}
    assert 'src/no_future.py' in violation_files
    assert 'src/no_docstring.py' in violation_files
    assert 'src/compliant.py' not in violation_files

@pytest.mark.asyncio
async def test_init_with_string_path(tmp_path):
    """Test ConstitutionalMonitor can be initialized with string path."""
    monitor = ConstitutionalMonitor(str(tmp_path))
    assert monitor.repo_path == tmp_path
    assert isinstance(monitor.repo_path, Path)
