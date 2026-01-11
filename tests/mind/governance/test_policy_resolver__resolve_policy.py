"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/policy_resolver.py
- Symbol: resolve_policy
- Status: 4 tests passed, some failed
- Passing tests: test_resolve_policy_by_filename, test_resolve_policy_by_filename_basename_only, test_resolve_policy_by_id, test_resolve_policy_not_found
- Generated: 2026-01-11 02:11:54
"""

import pytest
from mind.governance.policy_resolver import resolve_policy
import os
import tempfile
import yaml

def test_resolve_policy_by_filename():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file_path = os.path.join(tmpdir, 'test_policy.yaml')
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write('id: dummy_id\n')
        original_root = None
        try:
            from mind.governance import policy_resolver
            original_root = policy_resolver.POLICY_ROOT
            policy_resolver.POLICY_ROOT = tmpdir
            result = resolve_policy(filename=test_file_path)
            assert result == test_file_path
        finally:
            if original_root is not None:
                policy_resolver.POLICY_ROOT = original_root

def test_resolve_policy_by_filename_basename_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file_path = os.path.join(tmpdir, 'test_policy.yaml')
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write('id: dummy_id\n')
        original_root = None
        try:
            from mind.governance import policy_resolver
            original_root = policy_resolver.POLICY_ROOT
            policy_resolver.POLICY_ROOT = tmpdir
            result = resolve_policy(filename='test_policy.yaml')
            assert result == test_file_path
        finally:
            if original_root is not None:
                policy_resolver.POLICY_ROOT = original_root

def test_resolve_policy_by_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file_path = os.path.join(tmpdir, 'some_policy.yaml')
        with open(test_file_path, 'w', encoding='utf-8') as f:
            yaml.dump({'id': 'test-policy-123'}, f)
        original_root = None
        try:
            from mind.governance import policy_resolver
            original_root = policy_resolver.POLICY_ROOT
            policy_resolver.POLICY_ROOT = tmpdir
            result = resolve_policy(policy_id='test-policy-123')
            assert result == test_file_path
        finally:
            if original_root is not None:
                policy_resolver.POLICY_ROOT = original_root

def test_resolve_policy_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        original_root = None
        try:
            from mind.governance import policy_resolver
            original_root = policy_resolver.POLICY_ROOT
            policy_resolver.POLICY_ROOT = tmpdir
            with pytest.raises(ValueError) as exc_info:
                resolve_policy(filename='ghost.yaml', policy_id='ghost-id')
            assert 'ghost.yaml' in str(exc_info.value)
            assert 'ghost-id' in str(exc_info.value)
            assert tmpdir in str(exc_info.value)
        finally:
            if original_root is not None:
                policy_resolver.POLICY_ROOT = original_root
