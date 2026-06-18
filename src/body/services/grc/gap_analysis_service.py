# src/body/services/grc/gap_analysis_service.py
"""GRC gap-analysis service (Scenario 4).

Drives the constitutional engine over an (Intent, Artifact) pair where the two
live in different places:

- **Intent** — a maintained catalog of checkable compliance requirements,
  expressed as ``ExecutableRule``s (each bound to a verification engine).
- **Artifact** — a folder of the customer's documents (the corpus).

Each requirement runs through the real ``execute_rule`` path, so findings carry
their ADR-113 ``evidence_class`` (proven / judged / attested) with no audit-loop
duplication. The corpus is read by a purpose-built context whose ``get_files``
globs the corpus directly — the standard ``AuditorContext`` derives its file walk
from the *loaded* intent's rule scopes, which would not see an external corpus.

The catalog here is a small demo (``load_demo_catalog``). The maintained,
regulation-derived catalog — the product — is a later build (the RegTech work);
this proves the engine shape on documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import execute_rule
from shared.logger import getLogger
from shared.models import AuditFinding, EvidenceClass


logger = getLogger(__name__)


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


@dataclass
# ID: b8fdcb87-2b2d-4425-8b25-301295aa84b7
class RequirementResult:
    """One requirement's gap-analysis outcome, with its honesty label."""

    rule: ExecutableRule
    evidence_class: EvidenceClass
    findings: list[AuditFinding]
    status: str  # "gap" | "met" | "needs_human" | "pending_ai"

    @property
    # ID: bbb2aaa4-d607-4191-8d54-06dc5b2470e3
    def requirement_id(self) -> str:
        return self.rule.rule_id

    @property
    # ID: 8683f78b-0711-479a-ad33-dc0e833319b7
    def statement(self) -> str:
        return self.rule.statement


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
            engine="llm_gate",
            params={
                "check_type": "semantic_requirement",
                "requirement": (
                    "The access-control policy requires multi-factor "
                    "authentication for all remote access."
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


# ID: fcf7ed3d-ea95-43c6-8333-ca0555387217
class GRCGapAnalysisService:
    """Runs a requirements catalog against a document corpus → gap report.

    Read-only: it reads the corpus and reports gaps; it never modifies the
    customer's documents (the GRC autonomy ceiling, CORE-BYOR §5 parameter 3).
    """

    # ID: 40434806-a71e-45cf-912f-762db4613c65
    def __init__(self, llm_client: Any | None = None) -> None:
        # When an LLM client is wired, the judged requirement produces a real
        # AI verdict; without one it degrades honestly to "pending_ai".
        self._llm_client = llm_client

    # ID: 483bbcf4-2f5f-4dea-9542-2b18689adf33
    async def run(
        self, corpus_root: Path, catalog: list[ExecutableRule] | None = None
    ) -> list[RequirementResult]:
        """Evaluate every requirement against the corpus.

        Args:
            corpus_root: folder holding the customer's documents (the Artifact).
            catalog: the requirements to check (the Intent). Defaults to the
                demo catalog.

        Returns one ``RequirementResult`` per requirement, each carrying its
        findings and an honest status.
        """
        from mind.logic.engines.registry import EngineRegistry
        from shared.config import settings

        # Engine internals (e.g. llm_gate prompts under var/prompts/) resolve
        # against CORE's own root; the corpus is addressed only via the
        # _CorpusContext below. Two independent roots — the Intent/Artifact split.
        EngineRegistry.initialize(settings.paths, llm_client=self._llm_client)

        context = _CorpusContext(corpus_root)
        results: list[RequirementResult] = []
        for rule in catalog or load_demo_catalog():
            findings = await execute_rule(rule, context)  # type: ignore[arg-type]
            results.append(self._classify(rule, findings))
        return results

    # ID: ece0623b-502c-41e0-9cd6-1f8dfd7fe69b
    def _classify(
        self, rule: ExecutableRule, findings: list[AuditFinding]
    ) -> RequirementResult:
        """Derive the requirement's status + its declared evidence class.

        The declared class comes from the producing engine (proven/judged/
        attested). A judged requirement whose AI pass did not run (llm_gate fell
        back to the stub, no client wired) is reported honestly as ``pending_ai``
        — never as met and never as a real judged verdict.
        """
        from mind.logic.engines.registry import EngineRegistry

        engine = EngineRegistry.get(rule.engine)
        declared = getattr(engine, "evidence_class", EvidenceClass.ATTESTED)

        is_stub = any(f.context.get("stub") for f in findings)
        if declared is EvidenceClass.ATTESTED:
            status = "needs_human"
        elif is_stub:
            status = "pending_ai"
        elif findings:
            status = "gap"
        else:
            status = "met"

        return RequirementResult(
            rule=rule,
            evidence_class=declared,
            findings=findings,
            status=status,
        )
