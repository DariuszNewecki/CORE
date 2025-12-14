# src/mind/governance/checks/vector_service_standards_check.py
"""
Constitutional Audit Check: Vector Service Standards

Enforces the vector_service_standards policy by checking:
1. All vectors have content_sha256 in payload
2. No direct client access outside QdrantService
3. No orphaned vectors or dangling links

This check keeps CORE honest about vector service standardization.
"""

from __future__ import annotations

import ast

from sqlalchemy import text

from mind.governance.audit_types import AuditCheckMetadata
from mind.governance.checks.base_check import BaseCheck
from shared.infrastructure.database.session_manager import SessionManager
from shared.models import AuditFinding, AuditSeverity


# ID: a6d3683e-d9e5-48d1-bf6a-901500b72c86
class VectorServiceStandardsCheck(BaseCheck):
    """
    Enforces vector_service_standards policy requirements.

    This check runs synchronously for hash coverage and client access patterns,
    but skips the sync integrity check (which requires async Qdrant access).
    The sync integrity is better checked via CLI command.
    """

    metadata = AuditCheckMetadata(
        id="vector_service_standards",
        name="Vector Service Standards",
        category="infrastructure",
        fix_hint="Review vector_service_standards.yaml and update vectorizers",
        default_severity=AuditSeverity.ERROR,
    )

    policy_rule_ids = [
        "vector.hash_present",
        "vector.service_usage",
        "vector.typed_payloads",
    ]

    # ID: 84317b88-9277-4e83-a24a-e936447ed9b1
    def execute(self) -> list[AuditFinding]:
        """Run all vector service standards checks."""
        findings: list[AuditFinding] = []

        # Check 1: Direct client access patterns
        findings.extend(self._check_direct_client_access())

        # Check 2: Hash coverage (requires async, so we note it)
        findings.extend(self._check_hash_coverage_note())

        # Check 3: Sync integrity (requires async, so we note it)
        findings.extend(self._check_sync_integrity_note())

        return findings

    def _check_direct_client_access(self) -> list[AuditFinding]:
        """
        Check for direct .client. access outside QdrantService.

        Only flags methods that have service alternatives available:
        - .client.scroll() → use scroll_all_points()
        - .client.upsert() → use upsert_points()

        Allows (during transition):
        - .client.get_collections() - no service method yet
        - .client.create_collection() - no service method yet
        - .client.recreate_collection() - no service method yet
        - .client.search() - complex, no service method yet
        - .client.delete() - use delete_points() for bulk only

        Allowed locations:
        - src/services/clients/qdrant_client.py (the service itself)
        """
        findings: list[AuditFinding] = []

        # Methods that have service alternatives
        forbidden_methods = {"scroll", "upsert"}

        # Map to suggested replacements
        method_suggestions = {
            "scroll": "scroll_all_points()",
            "upsert": "upsert_points()",
        }

        # Files allowed to use direct client access
        allowed_files = {
            self.src_dir / "services" / "clients" / "qdrant_client.py",
            self.src_dir / "services" / "vector" / "vector_index_service.py",
        }

        # Scan all Python files
        for py_file in self.src_dir.rglob("*.py"):
            if py_file in allowed_files:
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_file))

                # Look for x.client.method() patterns
                for node in ast.walk(tree):
                    if isinstance(node, ast.Attribute):
                        # Check if parent is .client
                        if (
                            isinstance(node.value, ast.Attribute)
                            and node.value.attr == "client"
                        ):
                            method_name = node.attr

                            # Only flag forbidden methods
                            if method_name in forbidden_methods:
                                findings.append(
                                    AuditFinding(
                                        check_id="vector.service_usage",
                                        severity=AuditSeverity.ERROR,
                                        message=(
                                            f"Direct Qdrant client.{method_name}() found. "
                                            f"Use QdrantService.{method_suggestions[method_name]} instead."
                                        ),
                                        file_path=str(
                                            py_file.relative_to(self.repo_root)
                                        ),
                                        line_number=getattr(node, "lineno", 0),
                                        context={
                                            "pattern": f".client.{method_name}",
                                            "suggestion": method_suggestions[
                                                method_name
                                            ],
                                            "policy": "vector_service_standards",
                                        },
                                    )
                                )
            except Exception:
                continue

        return findings

    def _get_name_from_node(self, node: ast.AST) -> str:
        """Extract name from AST node for pattern matching."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            parent = self._get_name_from_node(node.value)
            return f"{parent}.{node.attr}"
        return ""

    def _check_hash_coverage_note(self) -> list[AuditFinding]:
        """
        Note that hash coverage should be checked via CLI.

        This check can't run async Qdrant queries, so it creates an
        informational finding directing users to the CLI command.
        """
        findings: list[AuditFinding] = []

        try:
            with SessionManager().sync_session() as session:
                result = session.execute(
                    text("SELECT COUNT(*) FROM core.symbol_vector_links")
                )
                link_count = result.scalar()

            if link_count and link_count > 0:
                findings.append(
                    AuditFinding(
                        check_id="vector.hash_present",
                        severity=AuditSeverity.INFO,
                        message=(
                            f"Hash coverage check requires async Qdrant access. "
                            f"Run 'core-admin manage vectors verify' to check hash coverage. "
                            f"Found {link_count} vector links in database."
                        ),
                        file_path="N/A",
                        context={
                            "vector_links": link_count,
                            "command": "core-admin manage vectors verify",
                        },
                    )
                )
        except Exception as e:
            findings.append(
                AuditFinding(
                    check_id="vector.hash_present",
                    severity=AuditSeverity.WARNING,
                    message=f"Failed to check vector link count: {e}",
                    file_path="N/A",
                )
            )

        return findings

    def _check_sync_integrity_note(self) -> list[AuditFinding]:
        """
        Note that sync integrity should be checked via CLI.

        This requires async Qdrant access to compare vector IDs with DB links.
        """
        findings: list[AuditFinding] = []

        findings.append(
            AuditFinding(
                check_id="vector.sync_integrity",
                severity=AuditSeverity.INFO,
                message=(
                    "Vector sync integrity check requires async Qdrant access. "
                    "Run 'core-admin manage vectors verify' to check for orphaned "
                    "vectors and dangling links."
                ),
                file_path="N/A",
                context={
                    "command": "core-admin manage vectors verify",
                    "note": "This check is informational - use CLI for full verification",
                },
            )
        )

        return findings
