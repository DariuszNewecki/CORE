# src/system/governance/checks/quality_checks.py
"""Auditor checks related to code quality and conventions."""

from system.governance.models import AuditFinding, AuditSeverity

class QualityChecks:
    """Container for code quality constitutional checks."""
    
    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context

    # CAPABILITY: audit.check.docstrings
    def check_docstrings_and_intents(self) -> list[AuditFinding]:
        """Finds symbols missing docstrings or having generic intents."""
        findings = []
        check_name = "Docstring & Intent Presence"
        warnings_found = False
        for entry in self.context.symbols_list:
            if entry.get("type") != "ClassDef" and not entry.get("docstring"):
                warnings_found = True
                findings.append(AuditFinding(AuditSeverity.WARNING, f"Missing Docstring in '{entry.get('file')}': Symbol '{entry.get('name')}'", check_name))
            if "Provides functionality for the" in entry.get("intent", ""):
                 warnings_found = True
                 findings.append(AuditFinding(AuditSeverity.WARNING, f"Generic Intent in '{entry.get('file')}': Symbol '{entry.get('name')}' has a weak intent statement.", check_name))
        if not warnings_found:
            findings.append(AuditFinding(AuditSeverity.SUCCESS, "All symbols have docstrings and specific intents.", check_name))
        return findings

    # CAPABILITY: audit.check.dead_code
    def check_for_dead_code(self) -> list[AuditFinding]:
        """Detects unreferenced public symbols."""
        findings = []
        check_name = "Dead Code (Unreferenced Symbols)"
        all_called_symbols = set()
        for symbol in self.context.symbols_list:
            all_called_symbols.update(symbol.get("calls", []))
        
        warnings_found = False
        for symbol in self.context.symbols_list:
            name = symbol["name"]
            if name.startswith(('_', 'test_')): continue
            if name in all_called_symbols: continue
            if symbol.get("entry_point_type"): continue
            warnings_found = True
            findings.append(AuditFinding(AuditSeverity.WARNING, f"Potentially dead code: Symbol '{name}' in '{symbol['file']}' is unreferenced.", check_name))
            
        if not warnings_found:
            findings.append(AuditFinding(AuditSeverity.SUCCESS, "No unreferenced public symbols found.", check_name))
        return findings