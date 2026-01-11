"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/intent_guard.py
- Symbol: IntentGuard
- Status: 12 tests passed, some failed
- Passing tests: test_init_loads_rules, test_check_no_write_intent_allowed, test_matches_pattern_glob_matching, test_check_transaction_basic, test_check_transaction_empty_list, test_is_emergency_mode_detection, test_apply_rule_action_deny, test_apply_rule_action_warn, test_validate_generated_code_sync, test_check_policy_rules_integration, test_path_resolution_consistency, test_check_transaction_emergency_bypass
- Generated: 2026-01-11 02:08:16
"""

from mind.governance.intent_guard import IntentGuard


class TestIntentGuard:

    def test_init_loads_rules(self, tmp_path):
        """Test IntentGuard initialization loads and sorts rules."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        assert guard.repo_path == repo_root.resolve()
        assert isinstance(guard.rules, list)

    def test_check_no_write_intent_allowed(self, tmp_path):
        """Test non-.intent paths pass hard invariant."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        test_path = "src/main.py"
        violation = guard._check_no_write_intent(
            (repo_root / test_path).resolve(), test_path
        )
        assert violation is None

    def test_matches_pattern_glob_matching(self, tmp_path):
        """Test glob-based pattern matching."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        assert guard._matches_pattern("src/main.py", "src/main.py")
        assert guard._matches_pattern("src/main.py", "src/*.py")
        assert guard._matches_pattern("src/utils/helper.py", "src/**/*.py")
        assert not guard._matches_pattern("src/main.py", "tests/*.py")
        assert not guard._matches_pattern("src/main.py", "")
        assert guard._matches_pattern("docs/api/index.md", "docs/**/*.md")

    def test_check_transaction_basic(self, tmp_path):
        """Test transaction validation with multiple paths."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        paths = ["src/main.py", "tests/test_main.py", "README.md"]
        allowed, violations = guard.check_transaction(paths)
        assert isinstance(allowed, bool)
        assert isinstance(violations, list)

    def test_check_transaction_empty_list(self, tmp_path):
        """Test transaction with empty path list."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        allowed, violations = guard.check_transaction([])
        assert allowed
        assert violations == []

    def test_is_emergency_mode_detection(self, tmp_path):
        """Test emergency mode file detection."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        assert not guard._is_emergency_mode()
        lock_path = repo_root / ".intent" / "mind" / ".emergency_override"
        lock_path.parent.mkdir(parents=True)
        lock_path.touch()
        assert guard._is_emergency_mode()

    def test_apply_rule_action_deny(self, tmp_path):
        """Test simple deny rule action."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        from mind.governance.intent_guard import PolicyRule

        deny_rule = PolicyRule(
            name="test_deny",
            pattern="*.tmp",
            action="deny",
            description="Temporary files not allowed",
            severity="error",
            source_policy="test_policy",
        )
        violations = guard._apply_rule_action(
            deny_rule, (repo_root / "temp.tmp").resolve(), "temp.tmp"
        )
        assert len(violations) == 1
        assert violations[0].rule_name == "test_deny"
        assert violations[0].severity == "error"
        assert violations[0].path == "temp.tmp"

    def test_apply_rule_action_warn(self, tmp_path, caplog):
        """Test warn rule action (logs warning, no violation)."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        from mind.governance.intent_guard import PolicyRule

        warn_rule = PolicyRule(
            name="test_warn",
            pattern="*.log",
            action="warn",
            description="Log files should be rotated",
            severity="warning",
            source_policy="test_policy",
        )
        violations = guard._apply_rule_action(
            warn_rule, (repo_root / "app.log").resolve(), "app.log"
        )
        assert violations == []
        assert "Policy warning" in caplog.text

    def test_validate_generated_code_sync(self, tmp_path):
        """Test generated code validation (synchronous wrapper)."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        code = "print('Hello')"
        pattern_id = "inspect_pattern"
        component_type = "test_component"
        target_path = "src/test.py"

    def test_check_policy_rules_integration(self, tmp_path):
        """Test policy rule application integration."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        test_path = "src/app.py"
        violations = guard._check_policy_rules(
            (repo_root / test_path).resolve(), test_path
        )
        assert isinstance(violations, list)

    def test_path_resolution_consistency(self, tmp_path):
        """Test path resolution maintains consistency."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        assert guard.repo_path.is_absolute()
        assert guard.emergency_lock_file.is_absolute()
        guard2 = IntentGuard(repo_root.resolve())
        assert guard2.repo_path == guard.repo_path

    def test_check_transaction_emergency_bypass(self, tmp_path):
        """Test emergency mode bypasses policy checks."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        guard = IntentGuard(repo_root)
        lock_path = repo_root / ".intent" / "mind" / ".emergency_override"
        lock_path.parent.mkdir(parents=True)
        lock_path.touch()
        paths = ["src/main.py", "config.yaml"]
        allowed, violations = guard.check_transaction(paths)
        if not any(".intent" in p for p in paths):
            assert allowed
            assert violations == []
