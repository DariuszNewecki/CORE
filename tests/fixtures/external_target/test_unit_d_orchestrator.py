"""Focused tests for Unit D's deterministic support code.

These test the runner's OWN logic (hashing, name validation, secret
scanning, violation setup, result shaping) against real files and a real
materialized target where relevant. They do not run the live
Proposal/worker scenario or provision a database -- that is the live run,
executed once, separately, against real components (see the Unit D final
report).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_provisioning import (
    DatabaseNameError,
    validate_disposable_container_name,
    validate_disposable_db_name,
)
from materialize import materialize_external_target
from unit_d_orchestrator import (
    _CANARY_RELATIVE_PATHS,
    _TARGET_FILE,
    _VIOLATION_INTRODUCED,
    _VIOLATION_ORIGINAL,
    ScenarioResult,
    disable_incidental_caches_env,
    hash_tree,
    introduce_violation,
    run_external_verify_precheck,
    run_formatter_check,
    run_native_tests,
    scan_for_secrets,
    sha256_file,
)


class TestDisposableNameValidation:
    def test_accepts_well_formed_db_name(self) -> None:
        validate_disposable_db_name("core_unitd_0123456789abcdef")

    def test_accepts_well_formed_container_name(self) -> None:
        validate_disposable_container_name("core_unitd_pg_0123456789abcdef")

    @pytest.mark.parametrize(
        "name",
        [
            "core",
            "core_test",
            "core_unitd_",
            "core_unitd_ZZZZZZZZZZZZZZZZ",
            "core_unitd_0123456789abcde",  # 15 hex chars, one short
            "'; DROP DATABASE core_test; --",
        ],
    )
    def test_rejects_non_conforming_db_names(self, name: str) -> None:
        with pytest.raises(DatabaseNameError):
            validate_disposable_db_name(name)

    def test_rejects_db_name_pattern_for_container_check(self) -> None:
        with pytest.raises(DatabaseNameError):
            validate_disposable_container_name("core_unitd_0123456789abcdef")


class TestSecretScanning:
    def test_clean_text_passes(self) -> None:
        assert (
            scan_for_secrets("Target: /tmp/x\nVERIFIED — no mutation executed") is True
        )

    def test_none_values_are_skipped(self) -> None:
        assert scan_for_secrets(None, "clean") is True

    def test_postgres_dsn_with_credentials_is_flagged(self) -> None:
        leaked = "using postgresql+asyncpg://user:hunter2@host:5432/db"
        assert scan_for_secrets(leaked) is False

    def test_asyncpg_dsn_shape_is_flagged(self) -> None:
        leaked = "asyncpg://admin:secret@127.0.0.1:5432/core_unitd_x"
        assert scan_for_secrets(leaked) is False

    def test_sanitized_database_identity_is_not_flagged(self) -> None:
        # cli.runtime_external_verify's own sanitized form: host/dbname only.
        assert (
            scan_for_secrets("Database:       nonexistent-host.invalid:5432/db") is True
        )


class TestHashing:
    def test_sha256_file_is_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("hello\n")
        assert sha256_file(f) == sha256_file(f)

    def test_sha256_file_changes_with_content(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("hello\n")
        before = sha256_file(f)
        f.write_text("goodbye\n")
        assert sha256_file(f) != before

    def test_hash_tree_excludes_git_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        (tmp_path / "real.py").write_text("x = 1\n")
        result = hash_tree(tmp_path)
        assert "real.py" in result
        assert not any(k.startswith(".git") for k in result)

    def test_hash_tree_excludes_symlinks(self, tmp_path: Path) -> None:
        (tmp_path / "real.py").write_text("x = 1\n")
        (tmp_path / "link.py").symlink_to(tmp_path / "real.py")
        result = hash_tree(tmp_path)
        assert "real.py" in result
        assert "link.py" not in result


class TestScenarioResultShape:
    def test_to_dict_contains_required_fields(self) -> None:
        result = ScenarioResult(
            target="/tmp/x", pristine_commit="a" * 40, pristine_tree="b" * 40
        )
        d = result.to_dict()
        required = {
            "target",
            "pristine_commit",
            "pristine_tree",
            "violation_commit",
            "violation_tree",
            "repair_commit",
            "repair_tree",
            "proposal_id",
            "lifecycle_states",
            "executed_action_id",
            "changed_paths",
            "native_tests",
            "formatter_check",
            "blackboard_report_present",
            "root_agreement_ok",
            "secret_scan_clean",
            "checks",
            "blockers",
            "verdict",
        }
        assert required.issubset(d.keys())

    def test_default_verdict_is_fail(self) -> None:
        assert ScenarioResult(
            target="x", pristine_commit="a", pristine_tree="b"
        ).verdict == ("FAIL")


class TestDisableIncidentalCaches:
    def test_returns_expected_keys(self) -> None:
        env = disable_incidental_caches_env()
        assert env["PYTHONDONTWRITEBYTECODE"] == "1"
        assert "PYTHONPYCACHEPREFIX" in env
        assert "RUFF_CACHE_DIR" in env
        assert env["PYTHONPYCACHEPREFIX"] not in ("", None)


@pytest.fixture
def real_target(tmp_path: Path):
    materialized = materialize_external_target(tmp_path / "target")
    return materialized


class TestIntroduceViolation:
    def test_changes_exactly_the_target_file(self, real_target) -> None:
        root = real_target.root
        before = {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        introduce_violation(root)
        after = {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        changed = {k for k in before if before[k] != after.get(k)}
        assert changed == {_TARGET_FILE}

    def test_commits_as_synthetic_operator_commit(self, real_target) -> None:
        root = real_target.root
        introduce_violation(root)
        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert log == "test operator: introduce formatting violation"

    def test_worktree_clean_after_violation_commit(self, real_target) -> None:
        root = real_target.root
        introduce_violation(root)
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert status == ""

    def test_violation_is_single_quote_for_double_quote(self, real_target) -> None:
        root = real_target.root
        before = (root / _TARGET_FILE).read_text("utf-8")
        assert _VIOLATION_ORIGINAL in before
        introduce_violation(root)
        after = (root / _TARGET_FILE).read_text("utf-8")
        assert _VIOLATION_INTRODUCED in after
        assert _VIOLATION_ORIGINAL not in after

    def test_raises_if_template_drifted(self, real_target) -> None:
        root = real_target.root
        (root / _TARGET_FILE).write_text("nothing to match here\n")
        with pytest.raises(RuntimeError):
            introduce_violation(root)


class TestFormatterAndNativeTestChecks:
    def test_pristine_target_passes_formatter_and_native_tests(
        self, real_target
    ) -> None:
        root = real_target.root
        env: dict[str, str] = {}
        assert run_formatter_check(root, env) is True
        assert run_native_tests(root, env) is True

    def test_violated_target_fails_formatter_but_keeps_native_tests(
        self, real_target
    ) -> None:
        root = real_target.root
        introduce_violation(root)
        env: dict[str, str] = {}
        assert run_formatter_check(root, env) is False
        assert run_native_tests(root, env) is True


class TestExternalVerifyPrecheck:
    def test_succeeds_and_never_leaks_the_unreachable_dsn(self, real_target) -> None:
        ok, output = run_external_verify_precheck(real_target.root)
        assert ok is True
        assert scan_for_secrets(output) is True


def test_canary_paths_exist_in_a_freshly_materialized_target(real_target) -> None:
    root = real_target.root
    for rel in _CANARY_RELATIVE_PATHS:
        assert (root / rel).is_file(), f"missing canary path: {rel}"
