# src/mind/coherence/checker.py

"""
CoherenceChecker — Mind-layer orchestrator for the Constitutional Coherence Checker.

Governing paper: .specs/papers/CORE-Governance-Topology.md (the directional grid)
Governing ADR:   .specs/decisions/ADR-073-ccc-scanner-redesign.md
Preserves:       ADR-067 D1 (storage), D2 (CLI), D4 (scheduling), D5 (dashboard).

Per ADR-073 D3, the scanner dispatches to seven check classes covering the
topology paper §10.2 enabled checks and the §10.3 retained/scoped R1. The
legacy R1/R2/R3 emission paths are removed.

Constitutional Compliance:
- Mind layer cognitive instrument; reads constitutional documents and invokes
  the LLM judge only for SAMECONCERN and R1_SCOPED.
- LLM has no enforcement power — every output is a candidate for human triage.
- No direct database access from this module: writes route through
  CoherenceService (body layer).
- Per ADR-073 D4: vector-dependent checks (SAMECONCERN, R1_SCOPED) refuse
  when the governance_claims collection is not seeded by the governor's
  `core-admin coherence seed bootstrap` operation. Structural checks operate
  independently and are unaffected.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger


if TYPE_CHECKING:
    from body.services.coherence_service import CoherenceService
    from body.services.governance_claims_service import GovernanceClaimsService

    from .checks.base import CheckClass


logger = getLogger(__name__)

__all__ = ["CoherenceChecker"]


# ID: 73a23100-c107-4205-9313-0318dca1143b
class CoherenceChecker:
    """Orchestrator for the seven ADR-073 D3 check classes.

    Produces candidates only — no verdicts, no enforcement actions, no
    constitutional amendments. All human triage runs through
    ``core-admin coherence triage``.
    """

    # ID: 5ae048c9-f6c7-4200-a4f1-193cbc82f1b9
    def __init__(
        self,
        cognitive_service: Any,
        coherence_service: CoherenceService,
        repo_root: Path,
        claims_service: GovernanceClaimsService | None = None,
    ):
        self._cognitive_service = cognitive_service
        self._coherence_service = coherence_service
        self._repo_root = Path(repo_root)
        self._claims_service = claims_service

    # ID: 2e4a95a7-fdac-427a-94eb-ed20ce2930c9
    async def run(self, full: bool = False, sample_rules: int | None = None) -> str:
        """Execute one CCC pass over the seven D3 check classes. Returns the new run_id.

        ``sample_rules`` is accepted for back-compat with the ADR-067-era CLI but
        is no longer meaningful — rule-scoped relations (R2, R3) were retired
        per topology §10.3. Set values are logged and ignored.
        """
        if sample_rules is not None:
            logger.info(
                "CCC: sample_rules=%d ignored — R2/R3 retired per ADR-073 D1",
                sample_rules,
            )

        trigger = await self._detect_trigger(full=full)
        manifest = self._build_input_manifest()
        run_id = await self._coherence_service.create_run(trigger)

        check_status = await self._dispatch_checks(run_id)
        manifest.append(
            {
                "domain": "_meta",
                "path": None,
                "type": "check_classes_run",
                "check_status": check_status,
            }
        )
        await self._coherence_service.update_manifest(run_id, manifest)
        # Self-guarded close for zero-candidate scans — the triage-driven
        # auto-close never fires when no candidates exist (issue #458). The
        # service method's WHERE clause makes this a no-op when candidates
        # were added, so the call is unconditional here.
        await self._coherence_service.close_run_if_empty(run_id)

        emitted_total = sum(s.get("emitted", 0) for s in check_status.values())
        logger.info(
            "CCC run %s complete (trigger=%s, %d candidates from %d check classes)",
            run_id,
            trigger,
            emitted_total,
            len(check_status),
        )
        return run_id

    # ------------------------------------------------------------------ #
    # Check-class dispatch
    # ------------------------------------------------------------------ #

    # ID: 43725b56-2fcb-4746-a414-dc57428ff02f
    async def _dispatch_checks(self, run_id: str) -> dict[str, dict]:
        from shared.governance.coherence_harvester import NormativeMarkerRegister
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        from .checks.dispatch_parity import DispatchParityCheck
        from .checks.r1_scoped import R1ScopedCheck
        from .checks.row2_grounding import Row2GroundingCheck
        from .checks.row3_citation import Row3CitationCheck
        from .checks.row4_naming import Row4NamingCheck
        from .checks.sameconcern import SameConcernCheck
        from .checks.specgap import SpecGapCheck
        from .checks.vocabulary import VocabularyCheck

        register = NormativeMarkerRegister.from_intent(get_intent_repository())

        if self._claims_service is None:
            logger.info(
                "CCC: claims_service not injected; SAMECONCERN/R1_SCOPED will skip"
            )

        checks: list[CheckClass] = [
            DispatchParityCheck(self._repo_root, get_intent_repository()),
            Row2GroundingCheck(self._repo_root),
            Row3CitationCheck(self._repo_root, register),
            Row4NamingCheck(self._repo_root),
            VocabularyCheck(self._repo_root),
            SpecGapCheck(self._repo_root, register),
        ]
        if self._claims_service is not None:
            checks.append(
                SameConcernCheck(
                    self._repo_root,
                    register,
                    self._claims_service,
                    self._cognitive_service,
                )
            )
            checks.append(
                R1ScopedCheck(
                    self._repo_root,
                    register,
                    self._claims_service,
                    self._cognitive_service,
                )
            )

        status: dict[str, dict] = {}
        for check in checks:
            try:
                candidates = await check.run()
            except Exception as exc:
                logger.warning(
                    "CCC: check %s failed: %s", check.relation, exc, exc_info=True
                )
                status[check.relation] = {
                    "status": "error",
                    "error": str(exc),
                    "emitted": 0,
                }
                continue
            for candidate in candidates:
                await self._coherence_service.add_candidate(
                    run_id=run_id,
                    relation=candidate.relation,
                    documents=candidate.documents,
                    claim=candidate.claim,
                    rationale=candidate.rationale,
                )
            status[check.relation] = {"status": "ok", "emitted": len(candidates)}
            logger.info(
                "CCC: %s emitted %d candidates", check.relation, len(candidates)
            )
        return status

    # ------------------------------------------------------------------ #
    # Trigger detection (preserved from ADR-067 implementation)
    # ------------------------------------------------------------------ #

    async def _detect_trigger(self, full: bool) -> str:
        if full:
            return "manual"

        latest = await self._coherence_service.get_latest_run()
        if latest is None:
            return "manual"

        last_manifest = latest.get("input_manifest") or []

        last_adr_count = sum(
            1 for entry in last_manifest if entry.get("domain") == "adr"
        )
        current_adr_count = len(self._adr_paths())
        if current_adr_count > last_adr_count:
            return "adr_added"

        last_northstar_hashes = {
            entry.get("path"): entry.get("sha256")
            for entry in last_manifest
            if entry.get("domain") == "northstar"
        }
        for path in self._northstar_paths():
            try:
                current_hash = _sha256(path)
            except OSError:
                return "northstar_changed"
            rel = self._rel(path)
            if last_northstar_hashes.get(rel) != current_hash:
                return "northstar_changed"

        return "manual"

    # ------------------------------------------------------------------ #
    # Manifest construction
    # ------------------------------------------------------------------ #

    # ID: c44f8192-948c-4671-82a1-445dc657ee59
    def _build_input_manifest(self) -> list[dict]:
        """Document the governance inputs consumed by the redesigned scanner.

        ADR-067-era 'rule' entries are no longer emitted — rule-scoped relations
        (R2, R3) were retired per topology §10.3. The new scanner consumes
        ADRs, papers, northstar, phases, and the vocabulary projection.
        """
        manifest: list[dict] = []
        for path in self._adr_paths():
            manifest.append(self._manifest_entry(path, "adr"))
        for path in self._paper_paths():
            manifest.append(self._manifest_entry(path, "paper"))
        for path in self._northstar_paths():
            manifest.append(self._manifest_entry(path, "northstar"))
        for path in self._phase_paths():
            manifest.append(self._manifest_entry(path, "phase"))
        vocab = self._repo_root / ".intent" / "META" / "vocabulary.json"
        if vocab.exists():
            manifest.append(self._manifest_entry(vocab, "vocabulary"))
        return manifest

    # ID: f6ffc21f-e4ef-477c-9bb7-2cdd2d4599c5
    def _manifest_entry(self, path: Path, domain: str) -> dict:
        rel = self._rel(path)
        try:
            sha = _sha256(path)
        except OSError:
            return {
                "path": rel,
                "domain": domain,
                "status": "skipped",
                "skipped_reason": "file_read_failure",
                "sha256": None,
            }
        return {
            "path": rel,
            "domain": domain,
            "status": "checked",
            "skipped_reason": None,
            "sha256": sha,
        }

    # ------------------------------------------------------------------ #
    # Input enumeration
    # ------------------------------------------------------------------ #

    def _adr_paths(self) -> list[Path]:
        # F-42 ADR-091 D5 Phase 4: discovery routes through the spec_markdown
        # artifact-type universe filtered to .specs/decisions/ with the
        # ADR-N name pattern. Behavioural identity preserved: filtered
        # universe == decisions.glob("ADR-*.md") under current layout
        # (decisions/ has no subdirectories).
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        spec_md_globs = repo.get_artifact_type("spec_markdown").content["discovery"]
        universe: set[Path] = set()
        for glob in spec_md_globs:
            universe.update(self._repo_root.glob(glob))
        decisions_dir = self._repo_root / ".specs" / "decisions"
        if not decisions_dir.exists():
            return []
        return sorted(
            p
            for p in universe
            if p.is_relative_to(decisions_dir) and p.name.startswith("ADR-")
        )

    def _paper_paths(self) -> list[Path]:
        # F-41 ADR-090 Phase 4: discovery routes through the spec_markdown
        # artifact-type universe in the registry, filtered to .specs/papers/.
        # Behavioral identity: filtered universe == old papers.glob("*.md")
        # because .specs/papers/ has no subdirectories at present.
        # F-42 (#416) will replace the hardcoded subdir filter with the
        # sub-scope semantics declared on the CCC sensor.
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        spec_md_globs = repo.get_artifact_type("spec_markdown").content["discovery"]
        universe: set[Path] = set()
        for glob in spec_md_globs:
            universe.update(self._repo_root.glob(glob))
        papers_dir = self._repo_root / ".specs" / "papers"
        if not papers_dir.exists():
            return []
        return sorted(p for p in universe if p.is_relative_to(papers_dir))

    def _northstar_paths(self) -> list[Path]:
        # F-42 ADR-091 D5 Phase 4: spec_markdown universe filtered to
        # .specs/northstar/. Behavioural identity preserved under current
        # layout (northstar/ has no subdirectories).
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        spec_md_globs = repo.get_artifact_type("spec_markdown").content["discovery"]
        universe: set[Path] = set()
        for glob in spec_md_globs:
            universe.update(self._repo_root.glob(glob))
        northstar_dir = self._repo_root / ".specs" / "northstar"
        if not northstar_dir.exists():
            return []
        return sorted(p for p in universe if p.is_relative_to(northstar_dir))

    def _phase_paths(self) -> list[Path]:
        # F-42 ADR-091 D5 Phase 4: intent_yaml universe filtered to
        # .intent/phases/. Behavioural identity preserved under current
        # layout (phases/ has no subdirectories).
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        intent_yaml_globs = repo.get_artifact_type("intent_yaml").content["discovery"]
        universe: set[Path] = set()
        for glob in intent_yaml_globs:
            universe.update(self._repo_root.glob(glob))
        phases_dir = self._repo_root / ".intent" / "phases"
        if not phases_dir.exists():
            return []
        return sorted(p for p in universe if p.is_relative_to(phases_dir))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self._repo_root))
        except ValueError:
            return str(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
