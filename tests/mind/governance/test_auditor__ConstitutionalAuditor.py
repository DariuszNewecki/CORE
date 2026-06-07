"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/auditor.py
- Symbol: ConstitutionalAuditor
- Generated: 2026-01-11 01:48:04
- 2026-06-07 (#572 Cat B batch 16):

  All three original tests asserted on an API that no longer exists on
  ``ConstitutionalAuditor``:
    * ``self.fs`` — a FileHandler attribute the class used to expose
    * ``_write_findings(...)`` — a persistence method
    * ``_write_audit_evidence(...)`` — a persistence method
    * Module-level ``FileHandler``, ``REPORTS_DIR``, ``FINDINGS_FILENAME``,
      ``AUDIT_EVIDENCE_DIR``, ``AUDIT_EVIDENCE_FILENAME``, ``_repo_rel``,
      ``_utc_now_iso`` — none of these are exported by the current
      ``mind.governance.auditor`` module.

  The current ``ConstitutionalAuditor`` is leaner: source's own
  docstring states "Returns structured data for the Body layer to report
  or persist." The persistence side moved out of the Mind layer and the
  artifact-writing primitives went with it. The only public method is
  ``run_full_audit_async``; the only documented behaviour on __init__ is
  storing ``self.context``.

  Replaced the obsolete tests with two shape tests that exercise the
  current contract. Filed as deferred-coverage note for #572 (no
  separate issue — the persistence path lives on the Body side now and
  has its own surfaces to test).
"""

from unittest.mock import Mock

from mind.governance.auditor import ConstitutionalAuditor


class TestConstitutionalAuditor:
    def test_init_stores_context(self):
        """__init__ binds the AuditorContext to ``self.context`` and does
        nothing else — directory provisioning happens elsewhere now."""
        mock_context = Mock()
        auditor = ConstitutionalAuditor(mock_context)
        assert auditor.context is mock_context

    def test_public_surface_is_run_full_audit_async_only(self):
        """The class deliberately exposes only ``run_full_audit_async``.
        Anchoring this in a test makes any accidental re-introduction of
        ``self.fs`` / ``_write_findings`` / ``_write_audit_evidence`` (the
        autogen-era persistence surface that source intentionally stripped)
        visible immediately."""
        public = {n for n in dir(ConstitutionalAuditor) if not n.startswith("_")}
        assert public == {"run_full_audit_async"}
