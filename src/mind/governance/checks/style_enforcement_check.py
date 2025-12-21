# src/mind/governance/checks/style_enforcement_check.py
# ID: model.mind.governance.checks.style_enforcement_check
"""
Constitutional check for Code Style rules.

Uses RuleEnforcementCheck template to verify:
- style.formatter_required
- style.linter_required
- style.fail_on_style_in_ci

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.checks.rule_enforcement_check import RuleEnforcementCheck
from mind.governance.enforcement_methods import EnforcementMethod
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)

CODE_STANDARDS_POLICY = Path(".intent/charter/standards/code_standards.json")
PYPROJECT = Path("pyproject.toml")
RUFF_TOML = Path("ruff.toml")
WORKFLOWS_DIR = Path(".github/workflows")


def _run_cmd(args: list[str]) -> tuple[bool, str]:
    """
    Runs a command with a short timeout.
    Returns (ok, stderr_or_reason).
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, ""
        msg = (result.stderr or result.stdout or "").strip()
        return False, msg or "non-zero exit"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        return False, "not found"
    except Exception as exc:
        return False, str(exc)


# ID: formatter-tool-enforcement
# ID: a0cc860c-0286-4a89-8f24-cc0d9ab35ad2
class FormatterToolEnforcement(EnforcementMethod):
    """
    Verifies that Black formatter is configured and executable.
    """

    # ID: e1da3b80-df64-4221-aedb-b3175d47c544
    def verify(self, context, rule_data: dict[str, Any]) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        pyproject_path = context.repo_path / PYPROJECT
        rel_pyproject = str(PYPROJECT).replace("\\", "/")

        # 1) Check configuration presence
        if not pyproject_path.exists():
            findings.append(
                self._create_finding(
                    "pyproject.toml missing - required for Black configuration",
                    file_path=rel_pyproject,
                )
            )
            return findings

        try:
            content = pyproject_path.read_text(encoding="utf-8")
        except Exception as exc:
            findings.append(
                self._create_finding(
                    f"Failed to read pyproject.toml: {exc}",
                    file_path=rel_pyproject,
                )
            )
            return findings

        if "[tool.black]" not in content:
            findings.append(
                self._create_finding(
                    "Black formatter not configured in pyproject.toml ([tool.black] missing)",
                    file_path=rel_pyproject,
                )
            )

        # 2) Verify Black is executable
        ok, reason = _run_cmd(["black", "--version"])
        if not ok:
            findings.append(
                self._create_finding(
                    f"Black formatter not installed or not executable ({reason})",
                    file_path="env:PATH",
                )
            )

        return findings


# ID: linter-tool-enforcement
# ID: 992dcf4b-25d1-41a0-8a7d-b6fc0787d4d5
class LinterToolEnforcement(EnforcementMethod):
    """
    Verifies that Ruff linter is configured and executable.
    """

    # ID: 703c5894-8fe1-4b93-ac02-7d1d520c2a63
    def verify(self, context, rule_data: dict[str, Any]) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        pyproject_path = context.repo_path / PYPROJECT
        ruff_toml_path = context.repo_path / RUFF_TOML

        rel_pyproject = str(PYPROJECT).replace("\\", "/")
        rel_ruff_toml = str(RUFF_TOML).replace("\\", "/")

        # 1) Check configuration presence (either pyproject or ruff.toml)
        has_config = False

        if ruff_toml_path.exists():
            has_config = True

        if pyproject_path.exists():
            try:
                content = pyproject_path.read_text(encoding="utf-8")
                if "[tool.ruff]" in content:
                    has_config = True
            except Exception as exc:
                logger.debug("Failed to read %s: %s", rel_pyproject, exc)

        if not has_config:
            findings.append(
                self._create_finding(
                    "Ruff linter not configured (need [tool.ruff] in pyproject.toml or ruff.toml)",
                    file_path=(
                        rel_pyproject if pyproject_path.exists() else rel_ruff_toml
                    ),
                )
            )

        # 2) Verify Ruff is executable
        ok, reason = _run_cmd(["ruff", "--version"])
        if not ok:
            findings.append(
                self._create_finding(
                    f"Ruff linter not installed or not executable ({reason})",
                    file_path="env:PATH",
                )
            )

        return findings


# ID: ci-style-gate-enforcement
# ID: d594012f-7d9b-4cbb-9a28-0bffe5386f48
class CIStyleGateEnforcement(EnforcementMethod):
    """
    Verifies that CI pipeline fails on style violations.
    Checks GitHub Actions workflow presence and references to style tools.
    """

    # ID: 24a8cb0c-2d05-4094-b593-1f469e07d7e4
    def verify(self, context, rule_data: dict[str, Any]) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        workflows_dir = context.repo_path / WORKFLOWS_DIR
        rel_workflows = str(WORKFLOWS_DIR).replace("\\", "/") + "/"

        if not workflows_dir.exists():
            findings.append(
                self._create_finding(
                    "No CI workflows found (.github/workflows/) - cannot enforce style in CI",
                    file_path=rel_workflows,
                )
            )
            return findings

        has_style_check = False
        for workflow_file in workflows_dir.glob("*.yml"):
            rel_file = str(workflow_file.relative_to(context.repo_path)).replace(
                "\\", "/"
            )
            try:
                content = workflow_file.read_text(encoding="utf-8").lower()
            except Exception as exc:
                logger.debug("Failed to read workflow %s: %s", rel_file, exc)
                continue

            if any(
                keyword in content for keyword in ("black", "ruff", "lint", "format")
            ):
                has_style_check = True
                break

        if not has_style_check:
            findings.append(
                self._create_finding(
                    "No style checks found in CI workflows - style violations won't block merges",
                    file_path=rel_workflows,
                )
            )

        return findings


# ID: style-enforcement-check
# ID: efd8f172-8d8c-41f2-8455-20a3eec71576
class StyleEnforcementCheck(RuleEnforcementCheck):
    """
    Verifies that Code Style standards are enforced with tooling.

    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "style.formatter_required",
        "style.linter_required",
        "style.fail_on_style_in_ci",
    ]
    id: ClassVar[str] = "style_enforcement"

    policy_file: ClassVar[Path] = CODE_STANDARDS_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        FormatterToolEnforcement(rule_id="style.formatter_required"),
        LinterToolEnforcement(rule_id="style.linter_required"),
        CIStyleGateEnforcement(rule_id="style.fail_on_style_in_ci"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
