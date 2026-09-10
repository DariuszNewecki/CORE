"""Authority tests for the external-target safe auto-approval envelope
(Unit C, Governor-authorized external-target safety package; Governor
ruling 2026-09-06 -- ADR-159 Notes).

Every check below calls the real envelope loader
(``shared.infrastructure.intent.action_risk.load_safe_auto_approval_envelope``)
and the real validation function
(``will.autonomy.safe_auto_approval_envelope.validate_envelope``), plus the
real, unmodified ``ActionExecutor._validate_policies`` for the two
policy-resolution checks -- never a reimplementation. Every check that
touches ``get_intent_repository()`` (i.e. all of them) runs in a fresh
subprocess (see ``_probe.py``) so CORE's own already-initialized
IntentRepository singleton in this pytest session can never leak in.

No proposal, action, or worker is ever executed. No mutation is made to
the pristine materialized fixture -- variant/broken ``.intent/`` copies
used by the "fails closed" tests are separate scratch trees, never the
committed baseline.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parent))

from materialize import (
    REPO_ROOT,
    git_snapshot,
    materialize_external_target,
)


_PROBE = Path(__file__).resolve().parent / "_probe.py"


def _run_probe(
    intent_root: Path,
    repo_root_for_env: Path,
    mode: str,
    payload: dict | None = None,
) -> dict:
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "REPO_PATH": str(repo_root_for_env),
        "MIND": str(intent_root),
    }
    result = subprocess.run(
        [sys.executable, str(_PROBE), mode],
        input=json.dumps(payload) if payload is not None else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"probe {mode!r} failed (exit {result.returncode}):\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    return json.loads(result.stdout)


def _validate(
    intent_root: Path, repo_root: Path, file_path: str, action_id: str = "fix.format"
) -> dict:
    return _run_probe(
        intent_root,
        repo_root,
        "validate",
        {
            "actions": [
                {"action_id": action_id, "parameters": {"file_path": file_path}}
            ],
            "scope": {"files": [file_path]},
        },
    )


@pytest.fixture(scope="module")
def pristine_target(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("external_target_authority") / "target"
    materialized = materialize_external_target(dest)
    return materialized.root


@pytest.fixture(scope="module", autouse=True)
def _pristine_target_never_mutated(pristine_target: Path):
    before = git_snapshot(pristine_target)
    yield
    after = git_snapshot(pristine_target)
    assert before == after, (
        "an authority test mutated the pristine materialized fixture's "
        f"Git state: before={before!r} after={after!r}"
    )


class TestEnvelopeLoadsFromTargetNotCore:
    def test_loads_from_fixtures_intent_not_core(self, pristine_target: Path) -> None:
        result = _run_probe(pristine_target / ".intent", pristine_target, "root")
        assert result["intent_root"] == str(pristine_target / ".intent")
        assert result["intent_root"] != str(REPO_ROOT / ".intent")

    def test_envelope_content_matches_the_ratified_values(
        self, pristine_target: Path
    ) -> None:
        result = _run_probe(pristine_target / ".intent", pristine_target, "envelope")
        assert result == {
            "authorized_actions": ["fix.format"],
            "authorized_path_prefixes": ["package/"],
            "authorized_extensions": [".py"],
        }


class TestEligibleTargets:
    def test_fix_format_on_package_example_is_eligible(
        self, pristine_target: Path
    ) -> None:
        result = _validate(
            pristine_target / ".intent", pristine_target, "package/example.py"
        )
        assert result == {"ok": True}

    def test_fix_format_on_nested_package_file_is_eligible(
        self, pristine_target: Path
    ) -> None:
        result = _validate(
            pristine_target / ".intent", pristine_target, "package/sub/nested.py"
        )
        assert result == {"ok": True}


class TestActionIdDenials:
    def test_fix_imports_on_same_file_is_denied(self, pristine_target: Path) -> None:
        result = _validate(
            pristine_target / ".intent",
            pristine_target,
            "package/example.py",
            action_id="fix.imports",
        )
        assert result["ok"] is False

    def test_every_other_known_safe_action_is_denied(
        self, pristine_target: Path
    ) -> None:
        floor_actions = yaml.safe_load(
            (pristine_target / ".intent/enforcement/config/action_risk.yaml").read_text(
                "utf-8"
            )
        )["actions"]
        other_safe_actions = [
            action_id
            for action_id, level in floor_actions.items()
            if level == "safe" and action_id != "fix.format"
        ]
        assert len(other_safe_actions) >= 5, "sanity check on the fixture data itself"
        for action_id in other_safe_actions:
            result = _validate(
                pristine_target / ".intent",
                pristine_target,
                "package/example.py",
                action_id=action_id,
            )
            assert result["ok"] is False, f"{action_id} should be denied"


class TestPathBoundaryDenials:
    def test_fix_format_on_scripts_outside_is_denied(
        self, pristine_target: Path
    ) -> None:
        result = _validate(
            pristine_target / ".intent", pristine_target, "scripts/outside.py"
        )
        assert result["ok"] is False

    def test_fix_format_on_tests_path_is_denied(self, pristine_target: Path) -> None:
        result = _validate(
            pristine_target / ".intent", pristine_target, "tests/test_example.py"
        )
        assert result["ok"] is False

    def test_fix_format_on_dot_intent_path_is_denied(
        self, pristine_target: Path
    ) -> None:
        result = _validate(
            pristine_target / ".intent",
            pristine_target,
            ".intent/enforcement/config/action_risk.yaml",
        )
        assert result["ok"] is False

    def test_fix_format_on_repository_root_file_is_denied(
        self, pristine_target: Path
    ) -> None:
        result = _validate(pristine_target / ".intent", pristine_target, "setup.py")
        assert result["ok"] is False

    def test_fix_format_on_non_python_file_under_package_is_denied(
        self, pristine_target: Path
    ) -> None:
        result = _validate(
            pristine_target / ".intent", pristine_target, "package/data.json"
        )
        assert result["ok"] is False


class TestMalformedPathDenials:
    """Absolute, traversal, and malformed shapes -- all denied by the real,
    lexical-only `_validate_target_path`. Confirmed empirically before
    writing this class (direct probe of the real function)."""

    @pytest.mark.parametrize(
        "file_path",
        [
            "/etc/passwd",
            "package/../secret.py",
            "package//example.py",
            "package/./example.py",
            "package/..",
        ],
    )
    def test_denied(self, pristine_target: Path, file_path: str) -> None:
        result = _validate(pristine_target / ".intent", pristine_target, file_path)
        assert result["ok"] is False

    def test_lexical_layer_alone_still_does_not_resolve_symlinks(
        self, pristine_target: Path
    ) -> None:
        """The lexical layer's own scope, confirmed rather than assumed:
        `validate_envelope`/`_validate_target_path` remain exactly as they
        were -- "lexical only -- no filesystem access" per their own
        docstring, unchanged by Unit C.1. A lexically clean string like
        "package/escape/evil.py" still passes `validate_envelope` even
        when "package/escape" is, on disk, a symlink pointing outside the
        repository. This is expected and no longer a gap: physical
        containment is enforced separately, at dispatch time, by
        `body.atomic.executor._check_physical_containment` -- proven in
        `TestPhysicalContainment` below and in
        `tests/body/atomic/test_executor_physical_containment.py`. See
        ADR-159 Notes and the Unit C.1 commit for the full boundary.
        """
        escape_target = pristine_target / "package" / "escape"
        outside = pristine_target.parent / "outside_package_root"
        outside.mkdir(exist_ok=True)
        escape_target.symlink_to(outside, target_is_directory=True)
        try:
            result = _validate(
                pristine_target / ".intent",
                pristine_target,
                "package/escape/evil.py",
            )
            assert result == {"ok": True}
        finally:
            escape_target.unlink()


def _check_containment(target: Path, file_path: str) -> dict:
    return _run_probe(
        target / ".intent", target, "physical_containment", {"file_path": file_path}
    )


class TestPhysicalContainment:
    """Unit C.1: the real physical-containment enforcement point
    (`body.atomic.executor._check_physical_containment`), called through
    the fixture's own real, isolated-subprocess `.intent/` -- no mocked
    envelope anywhere in this class. Converts Unit C's known-gap test into
    a genuine refusal: none of these symlink escapes are accepted here.

    Every symlink scenario builds its own scratch copy of the pristine
    target (never mutates the module-scoped `pristine_target` itself, so
    the module's autouse git-invariant fixture stays meaningful).
    """

    @pytest.fixture
    def scratch(self, pristine_target: Path, tmp_path: Path) -> Path:
        dest = tmp_path / "scratch"
        shutil.copytree(pristine_target, dest)
        return dest

    def test_normal_file_remains_authorized(self, pristine_target: Path) -> None:
        result = _check_containment(pristine_target, "package/example.py")
        assert result == {"denied": False, "reason": None}

    def test_nested_normal_file_remains_authorized(self, pristine_target: Path) -> None:
        result = _check_containment(pristine_target, "package/sub/nested.py")
        assert result == {"denied": False, "reason": None}

    def test_symlinked_file_pointing_outside_repo_is_denied(
        self, scratch: Path
    ) -> None:
        outside = scratch.parent / "outside_repo.py"
        outside.write_text("stolen = True\n")
        (scratch / "package" / "link.py").symlink_to(outside)

        result = _check_containment(scratch, "package/link.py")
        assert result["denied"] is True
        assert "symbolic link" in result["reason"]

    def test_symlinked_directory_under_package_leading_outside_is_denied(
        self, scratch: Path
    ) -> None:
        outside_dir = scratch.parent / "outside_dir"
        outside_dir.mkdir()
        (outside_dir / "evil.py").write_text("evil = True\n")
        (scratch / "package" / "linkdir").symlink_to(
            outside_dir, target_is_directory=True
        )

        result = _check_containment(scratch, "package/linkdir/evil.py")
        assert result["denied"] is True
        assert "symbolic link" in result["reason"]

    def test_symlink_to_another_location_inside_package_is_denied(
        self, scratch: Path
    ) -> None:
        (scratch / "package" / "link.py").symlink_to(scratch / "package" / "example.py")

        result = _check_containment(scratch, "package/link.py")
        assert result["denied"] is True
        assert "symbolic link" in result["reason"]

    def test_symlink_to_elsewhere_inside_repo_outside_package_is_denied(
        self, scratch: Path
    ) -> None:
        (scratch / "package" / "link.py").symlink_to(scratch / "scripts" / "outside.py")

        result = _check_containment(scratch, "package/link.py")
        assert result["denied"] is True
        assert "symbolic link" in result["reason"]

    def test_dangling_symlink_is_denied(self, scratch: Path) -> None:
        (scratch / "package" / "dangling.py").symlink_to(
            scratch.parent / "does-not-exist.py"
        )

        result = _check_containment(scratch, "package/dangling.py")
        assert result["denied"] is True
        assert "symbolic link" in result["reason"]

    def test_symlinked_prefix_directory_itself_is_denied(self, scratch: Path) -> None:
        real_package = scratch / "package"
        moved = scratch.parent / "package_real"
        real_package.rename(moved)
        real_package.symlink_to(moved, target_is_directory=True)

        result = _check_containment(scratch, "package/example.py")
        assert result["denied"] is True
        assert "authorized prefix directory is a symbolic link" in result["reason"]

    def test_normalization_variants_cannot_bypass_the_combined_pipeline(
        self, scratch: Path
    ) -> None:
        """Lexical validation still rejects '.'/'..' segments (unchanged);
        physical containment rejects any symlink component regardless of
        spelling. Together, no normalization variant of a symlink escape
        gets through either layer."""
        outside = scratch.parent / "outside_repo2.py"
        outside.write_text("stolen = True\n")
        (scratch / "package" / "link.py").symlink_to(outside)

        # Lexical layer denies the '.'-bearing spelling outright.
        lexical = _validate(scratch / ".intent", scratch, "package/./link.py")
        assert lexical["ok"] is False

        # Physical layer denies the clean spelling of the same symlink.
        physical = _check_containment(scratch, "package/link.py")
        assert physical["denied"] is True

    def test_independent_of_process_cwd(
        self, scratch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outside = scratch.parent / "outside_repo3.py"
        outside.write_text("stolen = True\n")
        (scratch / "package" / "link.py").symlink_to(outside)

        elsewhere = tmp_path / "unrelated_cwd"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        result = _check_containment(scratch, "package/link.py")
        assert result["denied"] is True


class TestScopeConsistency:
    def test_scope_files_must_exactly_equal_action_targets(
        self, pristine_target: Path
    ) -> None:
        result = _run_probe(
            pristine_target / ".intent",
            pristine_target,
            "validate",
            {
                "actions": [
                    {
                        "action_id": "fix.format",
                        "parameters": {"file_path": "package/example.py"},
                    }
                ],
                # scope declares an extra file no action targets
                "scope": {"files": ["package/example.py", "package/sub/nested.py"]},
            },
        )
        assert result["ok"] is False


class TestEnvelopeFailsClosed:
    def _variant_intent(self, pristine_target: Path, tmp_path: Path, mutate) -> Path:
        variant_root = tmp_path / "variant"
        shutil.copytree(pristine_target, variant_root)
        action_risk_path = (
            variant_root / ".intent" / "enforcement" / "config" / "action_risk.yaml"
        )
        config = yaml.safe_load(action_risk_path.read_text("utf-8"))
        mutate(config)
        action_risk_path.write_text(yaml.safe_dump(config, sort_keys=False), "utf-8")
        return variant_root

    def test_missing_envelope_configuration_fails_closed(
        self, pristine_target: Path, tmp_path: Path
    ) -> None:
        variant = self._variant_intent(
            pristine_target,
            tmp_path,
            lambda cfg: cfg.pop("safe_auto_approval_envelope"),
        )
        result = _run_probe(variant / ".intent", variant, "envelope")
        assert result.get("_error") is True

    def test_malformed_envelope_configuration_fails_closed(
        self, pristine_target: Path, tmp_path: Path
    ) -> None:
        variant = self._variant_intent(
            pristine_target,
            tmp_path,
            lambda cfg: cfg["safe_auto_approval_envelope"].update(
                authorized_actions=[]
            ),
        )
        result = _run_probe(variant / ".intent", variant, "envelope")
        assert result.get("_error") is True


class TestPolicyResolution:
    def test_required_fix_format_policies_resolve(self, pristine_target: Path) -> None:
        result = _run_probe(
            pristine_target / ".intent", pristine_target, "policy_resolve"
        )
        assert result == {"ok": True, "policies": ["rules/code/purity"], "missing": []}

    def test_removing_required_policy_causes_refusal(
        self, pristine_target: Path, tmp_path: Path
    ) -> None:
        variant_root = tmp_path / "variant_missing_policy"
        shutil.copytree(pristine_target, variant_root)
        (variant_root / ".intent" / "rules" / "code" / "purity.json").unlink()

        result = _run_probe(variant_root / ".intent", variant_root, "policy_resolve")
        assert result["ok"] is False
        assert "rules/code/purity" in result["missing"]
