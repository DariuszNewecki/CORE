# src/system/governance/checks/file_integrity.py
"""
Auditor checks related to file existence, format, and structure.
"""
from pathlib import Path
from system.governance.models import AuditSeverity
from core.validation_pipeline import validate_code

class FileIntegrityChecks:
    """Container for file-based constitutional checks."""
    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context

    # CAPABILITY: audit.check.required_files
    def check_required_files(self):
        """Verifies the existence of critical .intent files."""
        # ... (Implementation is the same, but uses self.context instead of self)
        # ... and returns a list of findings instead of calling _add_finding
        
    # CAPABILITY: audit.check.syntax
    def check_syntax(self):
        """Validates the syntax of all .intent YAML/JSON files."""
        # ...

    # CAPABILITY: audit.check.orphaned_intent_files
    def check_for_orphaned_intent_files(self):
        """Finds .intent files that are not referenced in meta.yaml."""
        # ...