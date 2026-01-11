"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/audit_postprocessor.py
- Symbol: main
- Status: 3 tests passed, some failed
- Passing tests: test_main_relative_paths, test_main_invalid_findings_not_list, test_main_invalid_symbols_not_dict
- Generated: 2026-01-11 02:05:55
"""

import pytest
import tempfile
import json
import sys
from pathlib import Path
from mind.governance.audit_postprocessor import main

def test_main_relative_paths(tmp_path):
    """Test main with relative paths that get resolved against repo root."""
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    reports_dir = repo_root / 'reports'
    reports_dir.mkdir()
    findings_data = [{'rule_id': 'test', 'severity': 'warn'}]
    symbols_data = {'key': {'type': 'class'}}
    in_file = reports_dir / 'audit_findings.json'
    symbols_file = reports_dir / 'symbol_index.json'
    out_file = reports_dir / 'processed.json'
    in_file.write_text(json.dumps(findings_data))
    symbols_file.write_text(json.dumps(symbols_data))
    argv = ['--repo-root', str(repo_root), '--in', 'reports/audit_findings.json', '--symbols', 'reports/symbol_index.json', '--out', 'reports/processed.json', '--reports', 'reports', '--downgrade-to', 'warn']
    result = main(argv)
    assert result == 0
    assert out_file.exists()

def test_main_invalid_findings_not_list(tmp_path):
    """Test main when findings JSON is not a list."""
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    in_file = tmp_path / 'findings.json'
    symbols_file = tmp_path / 'symbols.json'
    out_file = tmp_path / 'output.json'
    in_file.write_text(json.dumps({'not': 'a list'}))
    symbols_file.write_text(json.dumps({'valid': 'symbols'}))
    argv = ['--repo-root', str(repo_root), '--in', str(in_file), '--symbols', str(symbols_file), '--out', str(out_file)]
    result = main(argv)
    assert result == 2

def test_main_invalid_symbols_not_dict(tmp_path):
    """Test main when symbols JSON is not a dictionary."""
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    in_file = tmp_path / 'findings.json'
    symbols_file = tmp_path / 'symbols.json'
    out_file = tmp_path / 'output.json'
    in_file.write_text(json.dumps([{'valid': 'finding'}]))
    symbols_file.write_text(json.dumps(['not', 'a', 'dict']))
    argv = ['--repo-root', str(repo_root), '--in', str(in_file), '--symbols', str(symbols_file), '--out', str(out_file)]
    result = main(argv)
    assert result == 2
