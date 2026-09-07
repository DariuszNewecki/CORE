"""Tests for the Unit D formatter-runtime correction (ADR-159 Notes,
2026-09-07): fix.format's Ruff-format step now runs via
shared.utils.subprocess_utils.run_direct_command instead of
run_poetry_command, so Ruff is resolved from CORE's active runtime and
launched directly -- the governed target need not have Poetry or a
pyproject.toml of its own, and any returned exit code unambiguously
belongs to Ruff (not to Poetry's own project-discovery step).

Two layers:
- TestFormatWithNoPyprojectToml: format_code() called directly against a
  freshly materialized target (no mocks, no ActionExecutor) -- proves the
  runtime-level fix on its own.
- TestSandboxPropagation: the real, unmodified ActionExecutor's sandbox
  path (ADR-071 D2.2), run via a fresh-interpreter probe
  (_probe_sandbox_format.py) so get_intent_repository()'s process-wide
  singleton is never contaminated by CORE's own already-initialized
  .intent/ in this pytest session -- the same isolation technique
  _probe.py (Unit C) already uses. No Proposal, no worker, no database.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from materialize import REPO_ROOT, materialize_external_target
from unit_d_orchestrator import (
    _CANARY_RELATIVE_PATHS,
    _TARGET_FILE,
    disable_incidental_caches_env,
    hash_tree,
    introduce_violation,
    run_formatter_check,
)


_PROBE = Path(__file__).resolve().parent / "_probe_sandbox_format.py"

_FUTURE_IMPORT_LINE = "from __future__ import annotations\n"
_UNUSED_IMPORT_LINE = "import json\n"


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _introduce_unused_import_violation(target_root: Path) -> None:
    """Introduce one deterministic lint (not format) violation: an unused
    top-level import in package/example.py, committed as a synthetic
    operator commit -- mirrors introduce_violation's shape but for a
    violation `ruff format` cannot fix and only `ruff check --fix` can.
    Confirmed empirically: ruff format --check reports the file already
    formatted despite the unused import; ruff check --fix removes it.

    Inserted immediately after the module's `from __future__ import
    annotations` line (never before it -- that import must stay the
    first statement in the module for the file to remain valid Python)."""
    path = target_root / _TARGET_FILE
    content = path.read_text("utf-8")
    if _UNUSED_IMPORT_LINE in content:
        raise RuntimeError(
            f"unused import line {_UNUSED_IMPORT_LINE!r} already present in "
            f"{_TARGET_FILE}; template may have drifted"
        )
    if _FUTURE_IMPORT_LINE not in content:
        raise RuntimeError(
            f"expected {_FUTURE_IMPORT_LINE!r} in {_TARGET_FILE}; "
            "template may have drifted"
        )
    path.write_text(
        content.replace(
            _FUTURE_IMPORT_LINE, _FUTURE_IMPORT_LINE + _UNUSED_IMPORT_LINE
        ),
        "utf-8",
    )

    _run_git(["add", _TARGET_FILE], target_root)
    _run_git(
        ["commit", "-m", "test operator: introduce unused-import violation"],
        target_root,
    )


class TestFormatWithNoPyprojectToml:
    def test_target_has_no_pyproject_toml_anywhere(self, tmp_path: Path) -> None:
        """Precondition this correction exists for: confirm the materialized
        fixture (and every parent up to filesystem root) genuinely has no
        pyproject.toml -- the previous poetry-wrapped path silently failed
        exactly because of this."""
        target = materialize_external_target(tmp_path / "target")
        probe = target.root
        while True:
            assert not (probe / "pyproject.toml").exists()
            if probe.parent == probe:
                break
            probe = probe.parent

    def test_formats_successfully_with_no_pyproject_toml(self, tmp_path: Path) -> None:
        """The real format_code(), called directly (no ActionExecutor, no
        sandbox), against a real materialized repository with no
        pyproject.toml anywhere. Ruff must run and actually reformat the
        file -- not silently no-op."""
        from body.self_healing.code_style_service import format_code

        target = materialize_external_target(tmp_path / "target")
        introduce_violation(target.root)
        assert run_formatter_check(target.root, {}) is False  # violation present

        format_code(path=_TARGET_FILE, write=True, cwd=target.root)

        assert run_formatter_check(target.root, {}) is True  # actually reformatted

    def test_check_fix_genuinely_fixes_a_lint_violation_format_alone_cannot(
        self, tmp_path: Path
    ) -> None:
        """Requirement 3: ruff check --fix must genuinely run and fix a lint
        violation (unused import) that ruff format never touches -- proves
        the check/fix phase, not just the format phase, now actually
        executes against a target with no pyproject.toml."""
        from body.self_healing.code_style_service import format_code

        target = materialize_external_target(tmp_path / "target")
        _introduce_unused_import_violation(target.root)
        content_before = (target.root / _TARGET_FILE).read_text("utf-8")
        assert _UNUSED_IMPORT_LINE in content_before

        # Format alone (no check/fix) must NOT remove the unused import --
        # confirms this is a lint violation, not a formatting one.
        assert run_formatter_check(target.root, {}) is True

        format_code(path=_TARGET_FILE, write=True, cwd=target.root)

        content_after = (target.root / _TARGET_FILE).read_text("utf-8")
        assert _UNUSED_IMPORT_LINE not in content_after


class TestSandboxPropagation:
    """Requirement 6/7: through the real ActionExecutor sandbox path, the
    violation is fixed inside the sandbox, _sandbox_target_paths equals
    only package/example.py, repaired bytes propagate to the external
    target, and no other target path changes."""

    def _run_probe(
        self, target_root: Path, intent_root: Path, extra_env: dict[str, str]
    ) -> dict:
        env = {
            **os.environ,
            **extra_env,
            "PYTHONPATH": str(REPO_ROOT / "src"),
            "REPO_PATH": str(target_root),
            "MIND": str(intent_root),
        }
        result = subprocess.run(
            [sys.executable, str(_PROBE)],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"probe failed (exit {result.returncode}):\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        return json.loads(result.stdout)

    def test_sandbox_executes_and_propagates_exactly_the_target_file(
        self, tmp_path: Path
    ) -> None:
        target = materialize_external_target(tmp_path / "target")
        introduce_violation(target.root)
        # Cache dirs redirected outside the target so ruff's own cache
        # files never pollute the tree-equality comparison below --
        # incidental tooling noise, not a real path change.
        extra_env = disable_incidental_caches_env()

        pre_hashes = hash_tree(target.root)
        canary_pre = {
            rel: pre_hashes[rel] for rel in _CANARY_RELATIVE_PATHS if rel in pre_hashes
        }
        assert run_formatter_check(target.root, extra_env) is False

        probe_result = self._run_probe(target.root, target.intent_root, extra_env)

        # Requirement 6a: the action itself succeeded.
        assert probe_result["ok"] is True

        # Requirement 6b: _sandbox_target_paths is exactly the one target
        # file -- proves the sandbox actually mutated it (not a no-op
        # false success) and nothing else.
        assert probe_result["data"]["_sandbox_target_paths"] == [_TARGET_FILE]

        # Requirement 6c: repaired bytes propagated to the real target.
        assert run_formatter_check(target.root, extra_env) is True

        # Requirement 7: no other target path changed.
        post_hashes = hash_tree(target.root)
        for rel in _CANARY_RELATIVE_PATHS:
            if rel in canary_pre:
                assert post_hashes.get(rel) == canary_pre[rel], (
                    f"canary path changed unexpectedly: {rel}"
                )
        changed = {
            rel
            for rel, digest in post_hashes.items()
            if pre_hashes.get(rel) != digest
        }
        assert changed == {_TARGET_FILE}, f"unexpected path changes: {changed}"

    def test_sandbox_no_op_when_file_already_compliant(self, tmp_path: Path) -> None:
        """No violation introduced -- the sandbox produces no changes, and
        _sandbox_target_paths is empty. Mirrors
        test_executor_worktree_isolation.py's
        test_propagation_no_op_when_sandbox_made_no_changes, exercised
        through the real fix.format action instead of a bare test fixture."""
        target = materialize_external_target(tmp_path / "target")
        extra_env = disable_incidental_caches_env()
        assert run_formatter_check(target.root, extra_env) is True  # already compliant

        probe_result = self._run_probe(target.root, target.intent_root, extra_env)

        assert probe_result["ok"] is True
        assert probe_result["data"]["_sandbox_target_paths"] == []

    def test_sandbox_check_fix_phase_also_propagates(self, tmp_path: Path) -> None:
        """Requirement 5, check/fix phase: through the real ActionExecutor
        sandbox path, a lint (not format) violation -- one only ruff check
        --fix can resolve -- is fixed inside the sandbox and propagates to
        the external target exactly, proving the second Ruff phase's fix
        also survives the full sandbox execute+propagate path, not merely
        format_code() called directly."""
        target = materialize_external_target(tmp_path / "target")
        _introduce_unused_import_violation(target.root)
        extra_env = disable_incidental_caches_env()

        pre_hashes = hash_tree(target.root)
        canary_pre = {
            rel: pre_hashes[rel] for rel in _CANARY_RELATIVE_PATHS if rel in pre_hashes
        }
        content_before = (target.root / _TARGET_FILE).read_text("utf-8")
        assert _UNUSED_IMPORT_LINE in content_before

        probe_result = self._run_probe(target.root, target.intent_root, extra_env)

        assert probe_result["ok"] is True
        assert probe_result["data"]["_sandbox_target_paths"] == [_TARGET_FILE]

        content_after = (target.root / _TARGET_FILE).read_text("utf-8")
        assert _UNUSED_IMPORT_LINE not in content_after

        post_hashes = hash_tree(target.root)
        for rel in _CANARY_RELATIVE_PATHS:
            if rel in canary_pre:
                assert post_hashes.get(rel) == canary_pre[rel], (
                    f"canary path changed unexpectedly: {rel}"
                )
        changed = {
            rel for rel, digest in post_hashes.items() if pre_hashes.get(rel) != digest
        }
        assert changed == {_TARGET_FILE}, f"unexpected path changes: {changed}"
