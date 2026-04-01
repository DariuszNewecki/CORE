# src/will/workers/intent_inspector.py
# ID: will.workers.intent_inspector
"""
IntentInspector - Constitutional Quality Sensing Worker.

Responsibility: Inspect the quality of .intent/ itself. Runs three passes:
  1. Structural  — pure Python, no LLM. Every document has $schema, required
                   fields, non-empty mandatory values.
  2. Coherence   — per-document LLM analysis. Is the narrative clear and
                   internally consistent? Does the description match what is
                   actually declared?
  3. Alignment   — cross-document LLM analysis. Conflicts between rules,
                   orphaned worker declarations, enforcement rules pointing
                   at non-existent files or roles.

Constitutional standing:
- Declaration:      .intent/workers/intent_inspector.yaml
- Class:            sensing
- Phase:            runtime
- Permitted tools:  llm.local (LocalCoder / Ollama — qwen2.5:7b recommended)
- Approval:         false — findings are observations only

LAYER: will/workers — sensing worker. Reads .intent/ and posts findings.
No writes to .intent/ or src/ under any circumstances.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# Subjects used for blackboard deduplication
_SUBJECT_STRUCTURAL = "intent_inspector.structural"
_SUBJECT_COHERENCE = "intent_inspector.coherence"
_SUBJECT_ALIGNMENT = "intent_inspector.alignment"

# Fields every governed .intent/ document must declare
_REQUIRED_TOP_LEVEL_FIELDS = ("kind", "metadata")
_REQUIRED_METADATA_FIELDS = ("id", "title", "version", "authority", "status")

# Directories that are operational/stateful or have a format the LLM
# cannot coherently analyse — skip LLM passes for these subtrees.
#
# "enforcement" is excluded because enforcement mapping files use a
# specialised {engine, params, scope} format that differs from governed
# documents (kind/metadata/rules). The LLM has no schema for them and
# produces noise findings about missing fields that don't exist in the
# mapping format. Structural integrity of enforcement mappings is
# validated by EnforcementMappingLoader at load time instead.
_SKIP_DIRS = {"runtime", "mind_export", "keys", "enforcement"}

# Maximum number of documents fed to the alignment pass in one LLM call
_ALIGNMENT_BATCH = 20

# Tokens the LLM uses to signal a clean pass — no findings to report.
# Any response that, when stripped and uppercased, equals or starts with one
# of these tokens is treated as a clean pass and produces zero findings.
_CLEAN_PASS_TOKENS = (
    "NO_FINDINGS",
    "NO FINDINGS",
    "NONE",
    "OK",
    "PASS",
    "CLEAN",
    "NO ISSUES",
    "NO ISSUES FOUND",
    "NO PROBLEMS",
    "LOOKS GOOD",
    "ALL GOOD",
)


# ID: f1e2d3c4-b5a6-7890-fedc-ba9876543210
class IntentInspector(Worker):
    """
    Sensing worker. Inspects .intent/ constitutional quality across three
    passes and posts all findings to the blackboard.

    Does not modify any files. approval_required: false.
    """

    declaration_name = "intent_inspector"

    def __init__(self, core_context: Any) -> None:
        """
        Args:
            core_context: Initialized CoreContext. Provides access to
                          git_service.repo_path and cognitive_service.
        """
        super().__init__()
        self._core_context = core_context

    # -------------------------------------------------------------------------
    # Entry point
    # -------------------------------------------------------------------------

    # ID: a1b2c3d4-e5f6-7890-abcd-111111111111
    async def run(self) -> None:
        """
        Execute all three inspection passes and post findings + final report.
        """
        await self.post_heartbeat()

        intent_root = self._resolve_intent_root()
        if not intent_root.exists():
            await self.post_report(
                subject="intent_inspector.run.complete",
                payload={"error": f".intent/ not found at {intent_root}"},
            )
            return

        documents = self._load_all_documents(intent_root)
        logger.info(
            "IntentInspector: loaded %d documents from .intent/", len(documents)
        )

        # --- Pass 1: Structural (pure Python, no LLM) ---
        # Fetch existing open structural subjects once to avoid re-posting the
        # same "missing $schema" warning every cycle for files that will never
        # resolve automatically (e.g. config files, workflow stages).
        existing_structural = await self._fetch_existing_subjects(_SUBJECT_STRUCTURAL)
        structural_findings = self._pass_structural(documents)
        structural_posted = 0
        structural_skipped = 0
        for finding in structural_findings:
            subject = f"{_SUBJECT_STRUCTURAL}::{finding['path']}"
            if subject in existing_structural:
                structural_skipped += 1
                continue
            await self.post_finding(subject=subject, payload=finding)
            structural_posted += 1

        if structural_skipped:
            logger.debug(
                "IntentInspector: structural pass — %d already open, skipped.",
                structural_skipped,
            )

        # --- Pass 2: Coherence (per-document LLM) ---
        coherence_posted = await self._pass_coherence(documents)

        # --- Pass 3: Alignment (cross-document LLM) ---
        alignment_posted = await self._pass_alignment(documents, intent_root)

        await self.post_report(
            subject="intent_inspector.run.complete",
            payload={
                "documents_scanned": len(documents),
                "structural_findings": structural_posted,
                "coherence_findings": coherence_posted,
                "alignment_findings": alignment_posted,
                "message": (
                    f"Inspection complete. "
                    f"{structural_posted} structural, "
                    f"{coherence_posted} coherence, "
                    f"{alignment_posted} alignment findings."
                ),
            },
        )

        logger.info(
            "IntentInspector: done. structural=%d coherence=%d alignment=%d",
            structural_posted,
            coherence_posted,
            alignment_posted,
        )

    # -------------------------------------------------------------------------
    # Pass 1 — Structural (pure Python)
    # -------------------------------------------------------------------------

    # ID: b2c3d4e5-f6a7-8901-bcde-222222222222
    def _pass_structural(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Check every loaded document for required fields and non-empty values.
        Returns a list of finding payloads (no blackboard I/O here).
        """
        findings = []

        for doc in documents:
            path = doc["path"]
            data = doc["data"]
            issues = []

            # Must have $schema.
            # If absent, the file is not a governed artifact — it may be a
            # workflow stage definition, schema file, or other non-document
            # YAML with its own format. Flag only the missing $schema and
            # skip all downstream checks: kind, metadata, status etc. are
            # only meaningful once we know what document type is declared.
            if not data.get("$schema"):
                issues.append("missing $schema reference")
                findings.append(
                    {
                        "pass": "structural",
                        "path": path,
                        "issues": issues,
                        "severity": "warning",
                    }
                )
                continue

            # Must have top-level required fields
            for field in _REQUIRED_TOP_LEVEL_FIELDS:
                if field not in data:
                    issues.append(f"missing top-level field: '{field}'")

            # Metadata sub-fields
            metadata = data.get("metadata", {})
            if isinstance(metadata, dict):
                for field in _REQUIRED_METADATA_FIELDS:
                    val = metadata.get(field)
                    if not val:
                        issues.append(f"missing or empty metadata.{field}")
                    elif isinstance(val, str) and not val.strip():
                        issues.append(f"whitespace-only metadata.{field}")

            # Status must be known
            status = (
                (metadata.get("status") or "") if isinstance(metadata, dict) else ""
            )
            if status and status not in ("active", "draft", "deprecated"):
                issues.append(f"unknown metadata.status value: '{status}'")

            if issues:
                findings.append(
                    {
                        "pass": "structural",
                        "path": path,
                        "issues": issues,
                        "severity": "error",
                    }
                )

        return findings

    # -------------------------------------------------------------------------
    # Pass 2 — Coherence (per-document LLM)
    # -------------------------------------------------------------------------

    # ID: c3d4e5f6-a7b8-9012-cdef-333333333333
    async def _pass_coherence(self, documents: list[dict[str, Any]]) -> int:
        """
        For each document, ask the LLM whether the narrative is clear and
        internally consistent. Posts findings. Returns count posted.
        """
        try:
            prompt_model = PromptModel.load("intent_inspector_coherence")
            client = await self._core_context.cognitive_service.aget_client_for_role(
                "LocalReasoner"
            )
        except Exception as e:
            logger.error("IntentInspector: cannot load coherence PromptModel — %s", e)
            await self.post_finding(
                subject=f"{_SUBJECT_COHERENCE}::setup_error",
                payload={"error": str(e), "pass": "coherence"},
            )
            return 1

        existing_coherence = await self._fetch_existing_subjects(_SUBJECT_COHERENCE)
        posted = 0
        skipped = 0

        for doc in documents:
            if doc.get("skip_llm"):
                continue

            raw_yaml = doc.get("raw", "")
            if not raw_yaml.strip():
                continue

            subject = f"{_SUBJECT_COHERENCE}::{doc['path']}"
            if subject in existing_coherence:
                skipped += 1
                continue

            try:
                response = await prompt_model.invoke(
                    context={
                        "document_path": doc["path"],
                        "document_yaml": raw_yaml,
                    },
                    client=client,
                    user_id="intent_inspector",
                )
            except Exception as e:
                logger.warning(
                    "IntentInspector coherence: LLM failed for %s — %s", doc["path"], e
                )
                continue

            findings = self._parse_llm_findings(response, doc["path"], "coherence")
            if findings:
                existing_coherence.add(subject)
                for finding in findings:
                    await self.post_finding(subject=subject, payload=finding)
                    posted += 1

            # Yield control between documents — this is a long-running worker
            await asyncio.sleep(0)

        if skipped:
            logger.debug(
                "IntentInspector: coherence pass — %d already open, skipped.", skipped
            )

        return posted

    # -------------------------------------------------------------------------
    # Pass 3 — Alignment (cross-document LLM)
    # -------------------------------------------------------------------------

    # ID: d4e5f6a7-b8c9-0123-defa-444444444444
    async def _pass_alignment(
        self, documents: list[dict[str, Any]], intent_root: Path
    ) -> int:
        """
        Feed all documents to the LLM in batches and ask for cross-document
        conflicts, orphaned declarations, and misaligned enforcement rules.
        Returns count of findings posted.
        """
        try:
            prompt_model = PromptModel.load("intent_inspector_alignment")
            client = await self._core_context.cognitive_service.aget_client_for_role(
                "LocalReasoner"
            )
        except Exception as e:
            logger.error("IntentInspector: cannot load alignment PromptModel — %s", e)
            await self.post_finding(
                subject=f"{_SUBJECT_ALIGNMENT}::setup_error",
                payload={"error": str(e), "pass": "alignment"},
            )
            return 1

        # Build a compact manifest of all documents for the LLM
        llm_docs = documents[:_ALIGNMENT_BATCH]
        manifest_text = self._build_alignment_manifest(llm_docs)

        # List of worker declaration names vs implementation modules for orphan check
        worker_names = [d["path"] for d in documents if "/workers/" in d["path"]]

        posted = 0
        try:
            response = await prompt_model.invoke(
                context={
                    "intent_manifest": manifest_text,
                    "worker_list": "\n".join(worker_names) or "(none)",
                    "document_count": str(len(documents)),
                },
                client=client,
                user_id="intent_inspector",
            )
        except Exception as e:
            logger.error("IntentInspector alignment: LLM failed — %s", e)
            return 0

        existing_alignment = await self._fetch_existing_subjects(_SUBJECT_ALIGNMENT)
        findings = self._parse_llm_findings(response, "cross-document", "alignment")
        for finding in findings:
            subject = f"{_SUBJECT_ALIGNMENT}::{finding.get('path', 'cross-document')}"
            if subject in existing_alignment:
                continue
            existing_alignment.add(subject)
            await self.post_finding(subject=subject, payload=finding)
            posted += 1

        return posted

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    # ID: e5f6a7b8-c9d0-1e2f-3a4b-555555555555
    def _resolve_intent_root(self) -> Path:
        """Resolve .intent/ path from core_context."""
        repo_path = Path(self._core_context.git_service.repo_path)
        return repo_path / ".intent"

    # ID: f6a7b8c9-d0e1-2f3a-4b5c-666666666666
    def _load_all_documents(self, intent_root: Path) -> list[dict[str, Any]]:
        """
        Load all YAML documents from .intent/, excluding operational subtrees.
        Returns list of dicts with keys: path, data, raw, skip_llm.
        """
        documents = []
        seen: set[Path] = set()

        for pattern in ("**/*.yaml", "**/*.yml"):
            for file_path in sorted(intent_root.glob(pattern)):
                if file_path in seen:
                    continue
                seen.add(file_path)

                rel = file_path.relative_to(intent_root).as_posix()

                # Skip operational/stateful subtrees
                skip_llm = any(rel.startswith(d + "/") for d in _SKIP_DIRS)

                try:
                    raw = file_path.read_text(encoding="utf-8")
                    data = yaml.safe_load(raw) or {}
                except Exception as e:
                    logger.warning("IntentInspector: cannot load %s — %s", rel, e)
                    data = {}
                    raw = ""

                documents.append(
                    {
                        "path": rel,
                        "data": data if isinstance(data, dict) else {},
                        "raw": raw,
                        "skip_llm": skip_llm,
                    }
                )

        return documents

    # ID: a7b8c9d0-e1f2-3a4b-5c6d-777777777777
    def _build_alignment_manifest(self, documents: list[dict[str, Any]]) -> str:
        """
        Build a compact text summary of all documents for the alignment LLM pass.
        Avoids sending full YAML — sends path + kind + id + responsibility/statement.
        """
        lines = []
        for doc in documents:
            data = doc["data"]
            kind = data.get("kind", "unknown")
            doc_id = (data.get("metadata") or {}).get("id", "?")
            responsibility = (
                (data.get("mandate") or {}).get("responsibility", "")
                or (data.get("rules") or {})
                or ""
            )
            if isinstance(responsibility, dict):
                responsibility = f"rules: {list(responsibility.keys())}"
            summary = str(responsibility)[:200].replace("\n", " ").strip()
            lines.append(f"[{doc['path']}] kind={kind} id={doc_id} — {summary}")
        return "\n".join(lines)

    # ID: b8c9d0e1-f2a3-4b5c-6d7e-888888888888
    def _parse_llm_findings(
        self, response: str, path: str, pass_name: str
    ) -> list[dict[str, Any]]:
        """
        Parse LLM response into structured findings.

        Expected LLM format (line-based):
            FINDING: <short description>
            PATH: <optional specific path>
            SEVERITY: warning|error|info
            ---

        Clean pass signals:
            If the LLM response (stripped, uppercased) matches or starts with
            a known clean-pass token (NO_FINDINGS, OK, PASS, etc.), return an
            empty list. A clean pass must not produce a blackboard finding.

        Gracefully handles free-form text — wraps it as a single finding only
        when the response is not a clean pass and contains no parseable structure.
        """
        if not response or not response.strip():
            return []

        # Check for clean pass signal before any parsing.
        # The LLM signals "nothing wrong" with tokens like NO_FINDINGS or OK.
        # These must produce zero findings — not an info-level finding.
        normalized = response.strip().upper()
        for token in _CLEAN_PASS_TOKENS:
            if (
                normalized == token
                or normalized.startswith(token + "\n")
                or normalized.startswith(token + " ")
                or normalized.startswith(token + ".")
            ):
                logger.debug(
                    "IntentInspector %s: clean pass for %s ('%s')",
                    pass_name,
                    path,
                    response.strip()[:40],
                )
                return []

        findings = []
        current: dict[str, Any] = {}

        for line in response.splitlines():
            line = line.strip()
            if not line or line == "---":
                if current.get("description"):
                    findings.append(
                        {
                            "pass": pass_name,
                            "path": current.get("path", path),
                            "description": current["description"],
                            "severity": current.get("severity", "warning"),
                        }
                    )
                current = {}
                continue

            if line.upper().startswith("FINDING:"):
                current["description"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("PATH:"):
                current["path"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("SEVERITY:"):
                current["severity"] = line.split(":", 1)[1].strip().lower()

        # Flush last finding if no trailing ---
        if current.get("description"):
            findings.append(
                {
                    "pass": pass_name,
                    "path": current.get("path", path),
                    "description": current["description"],
                    "severity": current.get("severity", "warning"),
                }
            )

        # Fallback: LLM returned free-form text with no parseable structure.
        # Only wrap as a finding if the response is not a clean pass.
        # (Clean pass check above already handled the NO_FINDINGS case.)
        if not findings and response.strip():
            findings.append(
                {
                    "pass": pass_name,
                    "path": path,
                    "description": response.strip()[:1000],
                    "severity": "info",
                }
            )

        return findings

    async def _fetch_existing_subjects(self, subject_prefix: str) -> set[str]:
        """
        Query the blackboard for all already-open findings under a subject
        prefix, regardless of which worker posted them.

        Intentionally does NOT filter by worker_uuid. Deduplication must be
        by subject content, not by poster identity. This prevents different
        daemon generations from re-posting the same finding when their UUIDs
        differ across restarts.
        """
        svc = await self._core_context.registry.get_blackboard_service()
        return await svc.fetch_open_finding_subjects_by_prefix(f"{subject_prefix}::%")
