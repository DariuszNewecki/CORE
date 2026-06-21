# src/body/services/grc/gap_analysis_service.py
"""GRC gap-analysis service (Scenario 4).

Drives the constitutional engine over an (Intent, Artifact) pair where the two
live in different places:

- **Intent** — a maintained catalog of checkable compliance requirements,
  expressed as ``ExecutableRule``s (each bound to a verification engine).
- **Artifact** — a folder of the customer's documents (the corpus).

Each requirement is evaluated corpus-wide and produces one ``RequirementVerdict``
per requirement (ADR-118 D1). Evidence class (proven / judged / attested) is the
engine's declared class; status is the corpus-level outcome (D3). Silence from an
individual document is absence of evidence — not a gap (D4).

The catalog here includes a small demo (``load_demo_catalog``) and the maintained
NIST SP 800-171 catalog. The internal-corpus pipeline (T5d) is a follow-on build;
this proves the engine shape on documents.
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import execute_rule
from shared.logger import getLogger
from shared.models import (
    Applicability,
    ApplicabilityAssessment,
    AuditFinding,
    EvidenceClass,
    EvidenceItem,
    RequirementStatus,
    RequirementVerdict,
)


logger = getLogger(__name__)

# Engines that evaluate the corpus as a whole (one finding per requirement)
# rather than once per file. The catalog loader marks their rules context-level.
_CONTEXT_LEVEL_ENGINES = frozenset({"attestation_gate"})

# Corpus sampling bounds for the applicability gate (ADR-118 D2). The gate needs
# a representative excerpt, not the whole corpus — domain fit is legible from a
# sample, and an excerpt keeps the single pre-scoring AI call cheap.
_SAMPLE_MAX_FILES = 8
_SAMPLE_PER_FILE_CHARS = 2000
_SAMPLE_GLOBS = ("**/*.md", "**/*.txt")

# Marker the grc_judge and llm_gate emit when an LLM call fails for
# infrastructure reasons (timeout, connection error). Not a gap verdict.
_AI_OFFLINE_MARKER = "SYSTEM_ERROR_AI_OFFLINE"


# ID: 5128f744-4412-467e-89a6-d5e9f748ff6e
class _CorpusContext:
    """Minimal context for ``execute_rule`` that reads a document corpus.

    Implements only the surface ``execute_rule`` touches: ``repo_path``,
    ``get_files`` (globs the corpus), and ``force_llm``. Decouples the Artifact
    (corpus) from the Intent (catalog) — the requirement's scope globs the
    corpus directly rather than the loaded-intent-derived walk.
    """

    def __init__(self, corpus_root: Path) -> None:
        self.repo_path = corpus_root.resolve()
        self.force_llm = False

    # ID: ac2dee70-0f89-473a-beac-e46c2a39a0de
    def get_files(self, include: Any, exclude: Any = None) -> list[Path]:
        includes = list(include or [])
        excludes = list(exclude or [])
        out: set[Path] = set()
        for pattern in includes:
            for path in self.repo_path.glob(pattern):
                if not path.is_file():
                    continue
                rel = path.relative_to(self.repo_path).as_posix()
                if any(fnmatch(rel, e) for e in excludes):
                    continue
                out.add(path)
        return sorted(out)


# ID: b4172354-bcf6-4a94-9e36-a78bb47a8c28
def load_demo_catalog() -> list[ExecutableRule]:
    """A 3-requirement demo catalog, one per honesty label.

    Illustrative only — not authored from a real standard. The maintained,
    regulation-derived catalog is the product (a later build).
    """
    return [
        # PROVEN — deterministic: a finalized policy carries no placeholder text.
        ExecutableRule(
            rule_id="grc.demo.policy_is_finalized",
            engine="regex_gate",
            params={
                "forbidden_patterns": [
                    r"\bTBD\b",
                    r"\bTODO\b",
                    r"\bDRAFT\b",
                    r"\bFIXME\b",
                    r"<placeholder>",
                ]
            },
            enforcement="blocking",
            statement=(
                "Compliance policy documents MUST be finalized — no placeholder, "
                "TODO, TBD, DRAFT, or FIXME text."
            ),
            scope=["**/*.md", "**/*.txt"],
        ),
        # JUDGED — semantic: needs an AI reading of the policy text.
        ExecutableRule(
            rule_id="grc.demo.requires_mfa_for_remote_access",
            engine="grc_judge",
            params={
                "instruction": (
                    "Does this document require multi-factor authentication "
                    "for all remote access? Report a gap if remote access is "
                    "described without an MFA requirement, or if the document "
                    "is silent on it."
                ),
                "rationale": (
                    "Demonstration requirement (access control / MFA), "
                    "illustrative — not from a real standard."
                ),
            },
            enforcement="reporting",
            statement=(
                "The access-control policy MUST require multi-factor "
                "authentication for all remote access."
            ),
            scope=["**/*.md", "**/*.txt"],
        ),
        # ATTESTED — irreducibly human: no automated method can settle it.
        ExecutableRule(
            rule_id="grc.demo.controls_appropriate_to_risk",
            engine="attestation_gate",
            params={
                "prompt": (
                    "Confirm that the documented security controls are "
                    "appropriate to the organization's assessed risk profile."
                ),
                "reference": "ISO/IEC 27001:2022 Clauses 6.1.3 / 8.3",
            },
            enforcement="reporting",
            statement=(
                "Security controls MUST be appropriate to the organization's "
                "assessed risk profile."
            ),
            scope=["**/*.md", "**/*.txt"],
            is_context_level=True,
        ),
    ]


# ID: 26b8b9bb-2b52-40c1-a144-c8614394bbf6
def load_catalog(
    name: str = "nist_800_171",
    catalog_root: Path | None = None,
) -> list[ExecutableRule]:
    """Load a maintained, regulation-derived requirements catalog by name.

    Resolves ``<catalog_root>/<tier>/<name>/catalog.yaml`` through
    ``catalog_resolver`` (ADR-116) — the corpus is licensed law-as-data CORE
    consumes, not code it contains — and builds one ``ExecutableRule`` per
    requirement. The YAML is the product surface — versioned, provenance-bearing
    data — so the catalog can be kept current without code changes. Each
    requirement binds a verification engine (regex_gate/llm_gate/attestation_gate);
    its ADR-113 evidence class is the engine's, derived at execution time, not
    declared in the catalog.

    ``catalog_root`` overrides the default ``grc-catalogs/`` root (ADR-121 D3):
    non-GRC domains point at their own catalog tree; ``None`` uses the default.
    """
    from body.services.grc.catalog_resolver import resolve_catalog_path

    path = resolve_catalog_path(name, catalog_root=catalog_root)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    requirements = data.get("requirements") or []
    return [_build_rule(entry) for entry in requirements]


# ID: c4414ad0-33ab-4d27-98b7-965e72496436
def load_catalog_meta(name: str = "nist_800_171") -> dict[str, Any]:
    """Load a catalog's ``catalog:`` metadata block (title / source / authority).

    The applicability gate (ADR-118 D2) needs a description of *what domain the
    framework governs* to judge corpus fit. The existing catalog header already
    carries that (title, source, source_authority) — no new schema field is
    required for the lean gate; richer per-framework domain descriptors are a
    governor-authored catalog-schema follow-up. Returns an empty dict when the
    block is absent so callers degrade gracefully.
    """
    from body.services.grc.catalog_resolver import resolve_catalog_path

    path = resolve_catalog_path(name)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    meta = data.get("catalog")
    return dict(meta) if isinstance(meta, dict) else {}


# ID: 6b67e7de-d1e5-43bc-91c6-176c0ff15872
def build_framework_descriptor(meta: dict[str, Any]) -> str:
    """Render a catalog's metadata into a human-readable framework description.

    Feeds the applicability gate's prompt — what the framework is and what
    domain it governs. Uses only fields already present in the catalog header.
    """
    fields = (
        ("Title", meta.get("title") or meta.get("id")),
        ("Source", meta.get("source")),
        ("Authority", meta.get("source_authority")),
        ("Revision", meta.get("source_revision")),
    )
    lines = [f"{label}: {value}" for label, value in fields if value]
    return "\n".join(lines) or "An unspecified compliance framework."


# ID: dbe15a99-9e83-4423-8725-bb38867d459b
def _build_rule(entry: dict[str, Any]) -> ExecutableRule:
    """Build an ``ExecutableRule`` from one catalog requirement entry."""
    engine = entry["engine"]
    return ExecutableRule(
        rule_id=entry["id"],
        engine=engine,
        params=dict(entry.get("params") or {}),
        enforcement=entry.get("enforcement", "reporting"),
        statement=" ".join(str(entry.get("statement", "")).split()),
        scope=list(entry.get("scope") or ["**/*"]),
        exclusions=list(entry.get("exclusions") or []),
        is_context_level=engine in _CONTEXT_LEVEL_ENGINES,
    )


# ID: fcf7ed3d-ea95-43c6-8333-ca0555387217
class DocumentCorpusAnalysisService:
    """Runs a requirements catalog against a document corpus → gap report.

    Read-only: it reads the corpus and reports gaps; it never modifies the
    customer's documents (the GRC autonomy ceiling, CORE-BYOR §5 parameter 3).
    """

    # ID: 40434806-a71e-45cf-912f-762db4613c65
    def __init__(self, llm_client: Any | None = None) -> None:
        # When an LLM client is wired, the judged requirement produces a real
        # AI verdict; without one it degrades honestly to UNAVAILABLE.
        self._llm_client = llm_client

    # ID: b746e762-1ce6-46e0-8c52-dc676fbbe69c
    async def assess_applicability(
        self,
        corpus_root: Path,
        framework_id: str,
        framework_descriptor: str,
    ) -> ApplicabilityAssessment:
        """Judge whether the framework is in domain for the corpus (ADR-118 D2).

        The "detect" step of the applicability gate: samples the corpus (Body
        I/O) and hands the excerpt to the Mind gate, which reasons via the
        injected LLM client. Without a client wired the verdict degrades to
        ``uncertain`` — CORE never silently assumes domain fit.
        """
        if self._llm_client is None:
            return ApplicabilityAssessment(
                framework_id=framework_id,
                applicability=Applicability.UNCERTAIN,
                evidence_class=EvidenceClass.JUDGED,
                detected_domains=[],
                rationale="No LLM judge wired — domain fit was not assessed.",
            )

        from mind.logic.grc_applicability import GRCApplicabilityGate

        excerpt = self._sample_corpus(corpus_root)
        if not excerpt.strip():
            return ApplicabilityAssessment(
                framework_id=framework_id,
                applicability=Applicability.UNCERTAIN,
                evidence_class=EvidenceClass.JUDGED,
                detected_domains=[],
                rationale="Corpus held no readable text to sample for domain fit.",
            )

        gate = GRCApplicabilityGate(llm_client=self._llm_client)
        return await gate.assess(
            framework_id=framework_id,
            framework_descriptor=framework_descriptor,
            corpus_excerpt=excerpt,
        )

    # ID: 3da2a438-8ac4-4f14-a900-289d0dec5191
    def _sample_corpus(self, corpus_root: Path) -> str:
        """Read a bounded, representative text sample of the corpus.

        Reads up to ``_SAMPLE_MAX_FILES`` documents, truncating each — enough
        for a domain-fit judgment, cheap enough for one pre-scoring AI call.
        """
        root = corpus_root.resolve()
        paths: set[Path] = set()
        for pattern in _SAMPLE_GLOBS:
            for path in root.glob(pattern):
                if path.is_file():
                    paths.add(path)
        chunks: list[str] = []
        for path in sorted(paths)[:_SAMPLE_MAX_FILES]:
            try:
                text = path.read_text(encoding="utf-8")[:_SAMPLE_PER_FILE_CHARS]
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("Skipping unreadable corpus file %s: %s", path, e)
                continue
            rel = path.relative_to(root).as_posix()
            chunks.append(f"### {rel}\n{text}")
        return "\n\n".join(chunks)

    # ID: 483bbcf4-2f5f-4dea-9542-2b18689adf33
    async def run(
        self, corpus_root: Path, catalog: list[ExecutableRule] | None = None
    ) -> list[RequirementVerdict]:
        """Evaluate every requirement against the corpus (ADR-118 D1).

        Args:
            corpus_root: folder holding the customer's documents (the Artifact).
            catalog: the requirements to check (the Intent). Defaults to the
                NIST SP 800-171 catalog.

        Returns one ``RequirementVerdict`` per requirement, each carrying its
        corpus-level status, evidence class, and localized evidence (D1/D3/D5/D6).
        """
        from mind.logic.engines.registry import EngineRegistry
        from shared.config import settings

        # Engine internals (e.g. llm_gate prompts under var/prompts/) resolve
        # against CORE's own root; the corpus is addressed only via the
        # _CorpusContext below. Two independent roots — the Intent/Artifact split.
        EngineRegistry.initialize(settings.paths, llm_client=self._llm_client)

        context = _CorpusContext(corpus_root)
        return [
            await self._evaluate_corpus_requirement(rule, context)
            for rule in (catalog or load_catalog())
        ]

    # ID: 4d2fc2b1-7f46-459c-9f39-0e342eb62785
    async def _evaluate_corpus_requirement(
        self, rule: ExecutableRule, context: _CorpusContext
    ) -> RequirementVerdict:
        """Produce a corpus-level RequirementVerdict for one requirement (ADR-118 D1).

        Dispatches to the right evaluation path per engine type:
        - attestation_gate  → always NEEDS_HUMAN (irreducibly human)
        - grc_judge         → three-way per-file signals → corpus verdict (D4)
        - deterministic     → binary gap/satisfied from execute_rule
        """
        from mind.logic.engines.llm_gate_stub import LLMGateStubEngine
        from mind.logic.engines.registry import EngineRegistry

        engine = EngineRegistry.get(rule.engine)

        if rule.is_context_level:
            # attestation_gate: always NEEDS_HUMAN; attestation_prompt → rationale.
            findings = await execute_rule(rule, context)
            rationale = next(
                (
                    f.context.get("attestation_prompt", "")
                    for f in findings
                    if f.context.get("attestation_prompt")
                ),
                "",
            )
            if not rationale and findings:
                rationale = findings[0].message
            return RequirementVerdict(
                requirement_id=rule.rule_id,
                applicability=Applicability.IN_SCOPE,
                status=RequirementStatus.NEEDS_HUMAN,
                evidence_class=EvidenceClass.ATTESTED,
                rationale=rationale or "Attestation required.",
                statement=rule.statement,
                evidence=[],
            )

        if rule.engine == "grc_judge":
            if isinstance(engine, LLMGateStubEngine):
                return RequirementVerdict(
                    requirement_id=rule.rule_id,
                    applicability=Applicability.IN_SCOPE,
                    status=RequirementStatus.UNAVAILABLE,
                    evidence_class=EvidenceClass.JUDGED,
                    rationale="No LLM judge wired — AI verdict unavailable.",
                    statement=rule.statement,
                    evidence=[],
                )
            return await self._evaluate_judged_requirement(rule, context, engine)

        # Deterministic engines (regex_gate, etc.)
        findings = await execute_rule(rule, context)
        return self._classify_deterministic(rule, findings, engine)

    # ID: 4555210b-5a8c-4031-9063-976e587c7155
    async def _evaluate_judged_requirement(
        self,
        rule: ExecutableRule,
        context: _CorpusContext,
        engine: Any,
    ) -> RequirementVerdict:
        """Three-way corpus evaluation for grc_judge rules (ADR-118 D4).

        Calls the engine per file and collects per-file coverage signals
        (satisfied / gap / silent) from ``EngineResult.extra``. Silence
        contributes nothing to the evidence pool. Corpus verdict emerges from
        the pool (D3 + D4):

        - Empty pool (all silent) → NOT_COVERED
        - All positive, no gaps  → SATISFIED
        - Any gaps               → DEFICIENT (incl. mixed satisfied+gap)

        Transient AI failures are counted but never inflate to NOT_COVERED: if
        every evaluated file failed, the verdict is UNAVAILABLE (honest).
        """
        files = context.get_files(include=rule.scope, exclude=rule.exclusions)

        params = {
            **rule.params,
            "_context": context,
            "_rule_id": rule.rule_id,
            "_rule_content_hash": rule.rule_content_hash,
            "_force_llm": getattr(context, "force_llm", False),
        }

        satisfied_evidence: list[EvidenceItem] = []
        gap_evidence: list[EvidenceItem] = []
        had_transient_failure = False

        for file_path in files:
            try:
                result = await engine.verify(file_path, params)
            except Exception as exc:
                logger.warning("grc_judge crashed on %s: %s", file_path, exc)
                had_transient_failure = True
                continue

            rel = file_path.relative_to(context.repo_path).as_posix()
            extra = result.extra
            coverage = extra.get("coverage", "gap" if not result.ok else "satisfied")
            reasoning = str(extra.get("reasoning") or "").strip()

            if not result.ok and any(
                _AI_OFFLINE_MARKER in str(v) for v in result.violations
            ):
                had_transient_failure = True
                continue

            if coverage == "satisfied":
                satisfied_evidence.append(
                    EvidenceItem(
                        document=rel,
                        relevance=1.0,
                        cite=reasoning[:300] if reasoning else "",
                    )
                )
            elif coverage == "gap":
                find_msg = str(extra.get("finding") or result.message or "").strip()
                gap_evidence.append(
                    EvidenceItem(
                        document=rel,
                        relevance=1.0,
                        cite=find_msg[:300] if find_msg else reasoning[:300],
                    )
                )
            # coverage == "silent": no evidence contribution (ADR-118 D4)

        if had_transient_failure and not satisfied_evidence and not gap_evidence:
            return RequirementVerdict(
                requirement_id=rule.rule_id,
                applicability=Applicability.IN_SCOPE,
                status=RequirementStatus.UNAVAILABLE,
                evidence_class=EvidenceClass.JUDGED,
                rationale="AI verdict unavailable — transient LLM failure during evaluation.",
                statement=rule.statement,
                evidence=[],
            )

        if not satisfied_evidence and not gap_evidence:
            # All files were silent — no document in the corpus addresses this.
            return RequirementVerdict(
                requirement_id=rule.rule_id,
                applicability=Applicability.IN_SCOPE,
                status=RequirementStatus.NOT_COVERED,
                evidence_class=EvidenceClass.JUDGED,
                rationale="No document in the corpus addresses this requirement.",
                statement=rule.statement,
                evidence=[],
            )

        if gap_evidence:
            rationale = (
                gap_evidence[0].cite or "Requirement addressed but not satisfied."
            )
            return RequirementVerdict(
                requirement_id=rule.rule_id,
                applicability=Applicability.IN_SCOPE,
                status=RequirementStatus.DEFICIENT,
                evidence_class=EvidenceClass.JUDGED,
                rationale=rationale,
                statement=rule.statement,
                evidence=gap_evidence + satisfied_evidence,
            )

        return RequirementVerdict(
            requirement_id=rule.rule_id,
            applicability=Applicability.IN_SCOPE,
            status=RequirementStatus.SATISFIED,
            evidence_class=EvidenceClass.JUDGED,
            rationale="Requirement is covered by the corpus.",
            statement=rule.statement,
            evidence=satisfied_evidence,
        )

    # ID: d4e77704-f693-4dcb-b0fb-4330243c40d0
    def _classify_deterministic(
        self,
        rule: ExecutableRule,
        findings: list[AuditFinding],
        engine: Any,
    ) -> RequirementVerdict:
        """Corpus-level verdict for deterministic rules (regex_gate etc.).

        Binary: gap findings present → DEFICIENT (the document contains what it
        must not, or lacks what it must have); no gap findings → SATISFIED.
        NOT_COVERED does not apply to deterministic checks — a regex either
        fires or it doesn't; an empty scope resolves to SATISFIED (vacuous pass).
        """
        declared = getattr(engine, "evidence_class", EvidenceClass.PROVEN)

        _UNAVAILABLE = {"LLM_TRANSIENT_FAILURE", "ENFORCEMENT_FAILURE"}
        real_findings = [
            f for f in findings if f.context.get("finding_type") not in _UNAVAILABLE
        ]
        had_unavailable = any(
            f.context.get("finding_type") in _UNAVAILABLE for f in findings
        )

        if real_findings:
            evidence = [
                EvidenceItem(
                    document=f.file_path or "corpus",
                    relevance=1.0,
                    cite=f.message[:300] if f.message else "",
                )
                for f in real_findings
            ]
            return RequirementVerdict(
                requirement_id=rule.rule_id,
                applicability=Applicability.IN_SCOPE,
                status=RequirementStatus.DEFICIENT,
                evidence_class=declared,
                rationale=real_findings[0].message or "Requirement not satisfied.",
                statement=rule.statement,
                evidence=evidence,
            )

        if had_unavailable:
            return RequirementVerdict(
                requirement_id=rule.rule_id,
                applicability=Applicability.IN_SCOPE,
                status=RequirementStatus.UNAVAILABLE,
                evidence_class=declared,
                rationale="Verdict could not be established (enforcement failure).",
                statement=rule.statement,
                evidence=[],
            )

        return RequirementVerdict(
            requirement_id=rule.rule_id,
            applicability=Applicability.IN_SCOPE,
            status=RequirementStatus.SATISFIED,
            evidence_class=declared,
            rationale="No gap found by the deterministic check.",
            statement=rule.statement,
            evidence=[],
        )


# Backward-compat alias (ADR-121 D7). External callers that imported the
# original name continue to work; new code should use DocumentCorpusAnalysisService.
GRCGapAnalysisService = DocumentCorpusAnalysisService
