# src/system/governance/checks/structure_checks.py
"""Auditor checks related to the system's declared structure and relationships."""

from shared.schemas.manifest_validator import validate_manifest_entry
from shared.utils.import_scanner import scan_imports_for_file
from system.governance.models import AuditFinding, AuditSeverity


class StructureChecks:
    """Container for structural constitutional checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context

    # CAPABILITY: audit.check.project_manifest
    def check_project_manifest(self) -> list[AuditFinding]:
        """Validates the integrity of project_manifest.yaml."""
        findings = []
        check_name = "Project Manifest Integrity"
        required_keys = ["name", "intent", "required_capabilities", "active_agents"]
        errors_found = False
        for key in required_keys:
            if key not in self.context.project_manifest:
                errors_found = True
                findings.append(
                    AuditFinding(
                        AuditSeverity.ERROR,
                        f"project_manifest.yaml missing required key: '{key}'",
                        check_name,
                    )
                )
        if not errors_found:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "project_manifest.yaml contains all required keys.",
                    check_name,
                )
            )
        return findings

    # CAPABILITY: audit.check.capability_coverage
    def check_capability_coverage(self) -> list[AuditFinding]:
        """Ensures all required capabilities are implemented."""
        findings = []
        check_name = "Capability Coverage"
        required_caps = set(
            self.context.project_manifest.get("required_capabilities", [])
        )
        implemented_caps = {
            f.get("capability")
            for f in self.context.symbols_list
            if f.get("capability") != "unassigned"
        }
        missing = sorted(list(required_caps - implemented_caps))

        for cap in missing:
            findings.append(
                AuditFinding(
                    AuditSeverity.ERROR,
                    f"Missing capability implementation for: {cap}",
                    check_name,
                )
            )

        if not missing:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "All required capabilities are implemented.",
                    check_name,
                )
            )
        return findings

    # CAPABILITY: audit.check.capability_definitions
    def check_capability_definitions(self) -> list[AuditFinding]:
        """Ensures all implemented capabilities are valid."""
        findings = []
        check_name = "Capability Definitions"
        capability_tags_path = (
            self.context.intent_dir / "knowledge" / "capability_tags.yaml"
        )
        defined_tags_data = self.context.load_config(capability_tags_path, "yaml")
        defined_tags = {tag["name"] for tag in defined_tags_data.get("tags", [])}

        implemented_caps = {
            f.get("capability")
            for f in self.context.symbols_list
            if f.get("capability") != "unassigned"
        }

        undefined = sorted(list(implemented_caps - defined_tags))
        for cap in undefined:
            findings.append(
                AuditFinding(
                    AuditSeverity.ERROR,
                    f"Unconstitutional capability: '{cap}' is implemented in the code but not defined in capability_tags.yaml.",
                    check_name,
                )
            )

        if not undefined:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "All implemented capabilities are constitutionally defined.",
                    check_name,
                )
            )
        return findings

    # CAPABILITY: audit.check.knowledge_graph_schema
    def check_knowledge_graph_schema(self) -> list[AuditFinding]:
        """Validates all knowledge graph symbols against the schema."""
        findings = []
        check_name = "Knowledge Graph Schema Compliance"
        error_count = 0
        for key, entry in self.context.symbols_map.items():
            is_valid, validation_errors = validate_manifest_entry(
                entry, "knowledge_graph_entry.schema.json"
            )
            if not is_valid:
                error_count += 1
                for err in validation_errors:
                    findings.append(
                        AuditFinding(
                            AuditSeverity.ERROR,
                            f"Knowledge Graph entry '{key}' schema error: {err}",
                            check_name,
                        )
                    )
        if error_count == 0:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    f"All {len(self.context.symbols_map)} symbols in knowledge graph pass schema validation.",
                    check_name,
                )
            )
        return findings

    # --- THIS IS THE FIX ---
    # Restore the missing capability tag.
    # CAPABILITY: audit.check.domain_integrity
    def check_domain_integrity(self) -> list[AuditFinding]:
        """Checks for domain mismatches and illegal imports."""
        findings = []
        check_name = "Domain Integrity (Location & Imports)"
        errors_found = False
        for entry in self.context.symbols_list:
            file_path = self.context.repo_root / entry.get("file", "")
            if not file_path.exists():
                findings.append(
                    AuditFinding(
                        AuditSeverity.WARNING,
                        f"File '{entry.get('file')}' from knowledge graph not found on disk.",
                        check_name,
                    )
                )
                continue
            declared_domain = entry.get("domain")
            actual_domain = self.context.intent_model.resolve_domain_for_path(
                file_path.relative_to(self.context.repo_root)
            )
            if declared_domain != actual_domain:
                errors_found = True
                findings.append(
                    AuditFinding(
                        AuditSeverity.ERROR,
                        f"Domain Mismatch for '{entry.get('key')}': Declared='{declared_domain}', Actual='{actual_domain}'",
                        check_name,
                    )
                )

            allowed = set(
                self.context.intent_model.get_domain_permissions(actual_domain)
            ) | {actual_domain}
            imports = scan_imports_for_file(file_path)
            for imp in imports:
                if imp.startswith("src."):
                    imp = imp[4:]
                if imp.startswith(("core.", "shared.", "system.", "agents.")):
                    imp_path_parts = imp.split(".")
                    potential_path = self.context.src_dir.joinpath(*imp_path_parts)
                    check_path = potential_path.with_suffix(".py")
                    if not check_path.exists():
                        check_path = potential_path
                    imp_domain = self.context.intent_model.resolve_domain_for_path(
                        check_path
                    )
                    if imp_domain and imp_domain not in allowed:
                        errors_found = True
                        findings.append(
                            AuditFinding(
                                AuditSeverity.ERROR,
                                f"Forbidden Import in '{entry.get('file')}': Domain '{actual_domain}' cannot import '{imp}' from forbidden domain '{imp_domain}'",
                                check_name,
                            )
                        )
        if not errors_found:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "Domain locations and import boundaries are valid.",
                    check_name,
                )
            )
        return findings
