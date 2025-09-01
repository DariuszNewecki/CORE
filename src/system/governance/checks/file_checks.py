# src/system/governance/checks/file_checks.py
"""Audits file existence, syntax validity, and orphan detection for constitutional governance files."""

from __future__ import annotations

from pathlib import Path
from typing import List, Set

from core.validation_pipeline import validate_code
from shared.utils.constitutional_parser import get_all_constitutional_paths
from system.governance.models import AuditFinding, AuditSeverity


# CAPABILITY: audit.check.file_integrity
class FileChecks:
    """Container for file-based constitutional checks."""

    # CAPABILITY: system.governance.checks.initialize
    def __init__(self, context):
        """Initialize with a shared auditor context."""
        self.context = context
        self.intent_dir: Path = context.intent_dir
        self.repo_root: Path = context.repo_root
        # Load the new audit ignore policy at initialization.
        self.audit_ignore_policy = self.context.load_config(
            self.context.intent_dir / "policies" / "audit_ignore.yaml"
        )

    # CAPABILITY: audit.check.required_files
    def check_required_files(self) -> List[AuditFinding]:
        """Verify that all files declared in meta.yaml exist on disk."""
        findings: List[AuditFinding] = []
        check_name = "Required Intent File Existence"

        required_files = self._get_known_files_from_meta()

        if not required_files:
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.WARNING,
                    message="meta.yaml is empty or missing; cannot check for required files.",
                    check_name=check_name,
                )
            )
            return findings

        missing_count = 0
        for file_rel_path in sorted(required_files):
            full_path = self.repo_root / file_rel_path
            if not full_path.exists():
                missing_count += 1
                findings.append(
                    AuditFinding(
                        severity=AuditSeverity.ERROR,
                        message=f"Missing constitutionally-required file: '{file_rel_path}'",
                        check_name=check_name,
                    )
                )

        if missing_count == 0:
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.SUCCESS,
                    message=f"All {len(required_files)} constitutionally-required files are present.",
                    check_name=check_name,
                )
            )

        return findings

    # CAPABILITY: audit.check.syntax
    def check_syntax(self) -> List[AuditFinding]:
        """Validate syntax of all .intent YAML/JSON files (including proposals)."""
        findings: List[AuditFinding] = []
        check_name = "YAML/JSON Syntax Validity"

        files_to_check = [
            *self.intent_dir.rglob("*.yaml"),
            *self.intent_dir.rglob("*.json"),
        ]

        error_findings = []
        for file_path in files_to_check:
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                result = validate_code(str(file_path), content, quiet=True)
                if result["status"] == "dirty":
                    for violation in result["violations"]:
                        error_findings.append(
                            AuditFinding(
                                severity=AuditSeverity.ERROR,
                                message=f"Syntax Error: {violation['message']}",
                                check_name=check_name,
                                file_path=str(file_path.relative_to(self.repo_root)),
                            )
                        )
            except UnicodeDecodeError:
                error_findings.append(
                    AuditFinding(
                        severity=AuditSeverity.ERROR,
                        message=f"Unable to read file '{file_path.name}' due to encoding issues",
                        check_name=check_name,
                        file_path=str(file_path.relative_to(self.repo_root)),
                    )
                )

        if not error_findings:
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.SUCCESS,
                    message=f"Validated syntax for {len(files_to_check)} YAML/JSON files.",
                    check_name=check_name,
                )
            )
        findings.extend(error_findings)
        return findings

    # CAPABILITY: audit.check.orphaned_intent_files
    def check_for_orphaned_intent_files(self) -> List[AuditFinding]:
        """Find .intent files not referenced in meta.yaml."""
        findings: List[AuditFinding] = []
        check_name = "Orphaned Intent Files"
        known_files = self._get_known_files_from_meta()

        if not known_files:
            return findings

        # Combine hardcoded ignores with policy-driven ignores
        policy_ignores = set(self.audit_ignore_policy.get("ignore_patterns", []))
        runtime_ignores = {
            "proposals",  # The whole directory is handled by proposal checks
            "knowledge_graph.json",  # It's a generated artifact
        }
        ignore_patterns = policy_ignores.union(runtime_ignores)

        physical_files = {
            str(p.relative_to(self.repo_root)).replace("\\", "/")
            for p in self.intent_dir.rglob("*")
            if p.is_file() and not any(pat in str(p) for pat in ignore_patterns)
        }

        orphaned_files = sorted(physical_files - known_files)

        if orphaned_files:
            for orphan in orphaned_files:
                findings.append(
                    AuditFinding(
                        severity=AuditSeverity.WARNING,
                        message=f"Orphaned intent file: '{orphan}' is not a recognized system file.",
                        check_name=check_name,
                    )
                )
        else:
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.SUCCESS,
                    message="No orphaned or unrecognized intent files found.",
                    check_name=check_name,
                )
            )
        return findings

    # CAPABILITY: system.governance.discover_known_files
    def _get_known_files_from_meta(self) -> Set[str]:
        """Build a set of known intent files by delegating to the shared constitutional parser."""
        known = get_all_constitutional_paths(self.intent_dir)
        # Add files that are constitutionally significant but not listed in meta.yaml
        known.add(".intent/project_manifest.yaml")
        return known
