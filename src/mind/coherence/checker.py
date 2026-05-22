# src/mind/coherence/checker.py

"""
CoherenceChecker — Mind-layer instrument for the Constitutional Coherence Checker.

Governing paper: .specs/papers/CORE-ConstitutionalCoherenceChecker.md
Governing ADR:   .specs/decisions/ADR-067-constitutional-coherence-checker.md

Constitutional Compliance:
- Mind layer cognitive instrument; reads constitutional documents and invokes
  the LLM as a candidate-finder only.
- LLM has no enforcement power — every output is a candidate for human triage.
- No direct database access from this module: writes route through
  CoherenceService (body layer).
- No file mutations — read-only.
- .intent/ rule files are accessed via IntentRepository (the canonical
  gateway). .specs/ artifacts (ADRs, northstar) are read directly — there is
  no governance gateway for .specs/, and .specs/ has no analogue of the
  rules.architecture.intent_access constraint.
- aget_client_for_role() is called with model.manifest.role (no hardcoded
  role strings) per ai.cognitive_role.no_hardcoded_string.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger


if TYPE_CHECKING:
    from body.services.coherence_service import CoherenceService


logger = getLogger(__name__)

__all__ = ["CoherenceChecker"]


_R1_DESCRIPTION = (
    "R1 — ADR-vs-ADR coherence. Look for ADRs that contradict each other, "
    "implicitly supersede one another without declaring it, or address the "
    "same governance concern without cross-referencing."
)
_R2_DESCRIPTION = (
    "R2 — Rule-vs-northstar coherence. Look for rule domains with no traceable "
    "connection to any northstar requirement, or northstar requirements that "
    "have no corresponding rule enforcement."
)
_R3_DESCRIPTION = (
    "R3 — Rule-vs-ADR coherence. Look for rule domains whose enforcement "
    "behaviour appears to have drifted from the specification of their "
    "governing ADR."
)

_R1_BATCH_SIZE = 2
_LLM_CALL_TIMEOUT = 480
_FUZZY_MIN_TOKEN_LEN = 4
_USER_ID = "coherence_checker"


# ID: 73a23100-c107-4205-9313-0318dca1143b
class CoherenceChecker:
    """
    Constitutional Coherence Checker — mind-layer instrument that scans
    constitutional documents for candidate contradictions, gaps, and drift.

    Produces candidates only. No verdicts, no enforcement actions, no
    constitutional amendments. All human triage runs through
    ``core-admin coherence triage``.
    """

    def __init__(
        self,
        cognitive_service: Any,
        coherence_service: CoherenceService,
        repo_root: Path,
    ):
        self._cognitive_service = cognitive_service
        self._coherence_service = coherence_service
        self._repo_root = Path(repo_root)
        # Per-run state — set by run(). _rule_paths_cache holds the (possibly
        # sampled) rule path list so R2 and R3 see the same set even when
        # sampling is in effect.
        self._sample_rules: int | None = None
        self._rule_paths_cache: list[Path] | None = None

    # ID: 2e4a95a7-fdac-427a-94eb-ed20ce2930c9
    async def run(self, full: bool = False, sample_rules: int | None = None) -> str:
        """
        Execute one CCC pass over R1, R2, and R3. Returns the new run_id.

        With ``full=False``, the run's trigger is inferred from the most
        recent run's input_manifest: a higher ADR count yields ``adr_added``;
        any changed northstar SHA-256 yields ``northstar_changed``; otherwise
        ``manual``. With ``full=True`` the trigger is always ``manual``.

        ``sample_rules`` randomly samples N rule files for R2/R3 (R1 still
        scans all ADRs). Use for narrow exploratory runs. When None or >=
        total rule count, all rules are evaluated.
        """
        # Per-run cache reset — see __init__ docstring.
        self._sample_rules = sample_rules
        self._rule_paths_cache = None

        trigger = await self._detect_trigger(full=full)
        manifest = self._build_input_manifest()
        run_id = await self._coherence_service.create_run(trigger)

        await self._run_r1(run_id, manifest)
        await self._run_r2(run_id, manifest)
        await self._run_r3(run_id, manifest)

        await self._coherence_service.update_manifest(run_id, manifest)
        logger.info(
            "Coherence run %s complete (trigger=%s, %d manifest entries)",
            run_id,
            trigger,
            len(manifest),
        )
        return run_id

    # ------------------------------------------------------------------ #
    # Trigger detection
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
                current_hash = self._sha256(path)
            except OSError:
                return "northstar_changed"
            rel = self._rel(path)
            if last_northstar_hashes.get(rel) != current_hash:
                return "northstar_changed"

        return "manual"

    # ------------------------------------------------------------------ #
    # Manifest construction
    # ------------------------------------------------------------------ #

    def _build_input_manifest(self) -> list[dict]:
        manifest: list[dict] = []
        for path in self._adr_paths():
            manifest.append(self._manifest_entry(path, "adr"))
        for ref_path in self._rule_paths():
            manifest.append(self._manifest_entry(ref_path, "rule"))
        for path in self._northstar_paths():
            manifest.append(self._manifest_entry(path, "northstar"))
        return manifest

    def _manifest_entry(self, path: Path, domain: str) -> dict:
        rel = self._rel(path)
        try:
            sha = self._sha256(path)
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
    # Relation runners
    # ------------------------------------------------------------------ #

    async def _run_r1(self, run_id: str, manifest: list[dict]) -> None:
        adr_paths = self._adr_paths()
        if not adr_paths:
            return
        # ADR filenames carry no YYYY-MM prefix in this repo, so the
        # month-clustering preference (paper §3, ADR-067 D3) falls back to
        # the sequential ordering by ADR number.
        for i in range(0, len(adr_paths), _R1_BATCH_SIZE):
            cluster = adr_paths[i : i + _R1_BATCH_SIZE]
            await self._llm_call(
                run_id=run_id,
                relation="R1",
                relation_description=_R1_DESCRIPTION,
                document_paths=cluster,
                manifest=manifest,
            )

    async def _run_r2(self, run_id: str, manifest: list[dict]) -> None:
        rule_paths = self._rule_paths()
        northstar_paths = self._northstar_paths()
        if not rule_paths or not northstar_paths:
            return
        for rule_path in rule_paths:
            await self._llm_call(
                run_id=run_id,
                relation="R2",
                relation_description=_R2_DESCRIPTION,
                document_paths=[*northstar_paths, rule_path],
                manifest=manifest,
                focal_document_path=rule_path,
            )

    async def _run_r3(self, run_id: str, manifest: list[dict]) -> None:
        rule_paths = self._rule_paths()
        adr_paths = self._adr_paths()
        for rule_path in rule_paths:
            rule_id = self._load_rule_id(rule_path)
            if rule_id is None:
                self._mark_skipped(manifest, self._rel(rule_path), "file_read_failure")
                continue

            matched_adrs = self._match_adrs_to_rule(rule_id, adr_paths)
            if not matched_adrs:
                await self._coherence_service.add_candidate(
                    run_id=run_id,
                    relation="R3",
                    documents=[self._rel(rule_path)],
                    claim=f"No governing ADR found for rule domain {rule_id}",
                    rationale=(
                        "Heuristic keyword match against ADR filenames produced "
                        "no hits. Either the rule domain genuinely lacks a "
                        "governing ADR (constitutional gap) or the ADR exists "
                        "under a name the heuristic does not detect. Governor "
                        "triage required."
                    ),
                )
                continue

            await self._llm_call(
                run_id=run_id,
                relation="R3",
                relation_description=_R3_DESCRIPTION,
                document_paths=[rule_path, *matched_adrs],
                manifest=manifest,
            )

    # ------------------------------------------------------------------ #
    # LLM invocation
    # ------------------------------------------------------------------ #

    async def _llm_call(
        self,
        run_id: str,
        relation: str,
        relation_description: str,
        document_paths: list[Path],
        manifest: list[dict],
        focal_document_path: Path | None = None,
    ) -> None:
        """
        Load documents, invoke the LLM, parse JSON, store candidates.

        All failure modes are non-fatal. Per ADR-067 D3:
          - file_read_failure → that file's manifest entry is marked skipped.
          - llm_call_failure / llm_parse_failure / llm_schema_failure → every
            readable file in this call is marked skipped with the call-level
            reason (last write wins if the same file appears in multiple
            calls).
        """
        # Lazy import — keeps the mind/shared coupling local to the call site,
        # matches the Section 4 spec.
        from shared.ai.prompt_model import PromptModel

        text_parts: list[str] = []
        readable_rels: list[str] = []
        for path in document_paths:
            rel = self._rel(path)
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("CCC: failed to read %s: %s", rel, exc)
                self._mark_skipped(manifest, rel, "file_read_failure")
                continue
            if focal_document_path is not None:
                if path == focal_document_path:
                    text_parts.append(
                        f"RULE DOMAIN UNDER EVALUATION:\n=== {rel} ===\n{content}\n\n"
                    )
                else:
                    text_parts.append(
                        f"NORTHSTAR DOCUMENTS FOR COMPARISON:\n"
                        f"=== {rel} ===\n{content}\n\n"
                    )
            else:
                text_parts.append(f"=== {rel} ===\n{content}\n\n")
            readable_rels.append(rel)

        if not readable_rels:
            return

        documents_text = "".join(text_parts)

        try:
            model = PromptModel.load("constitutional_coherence_analyst")
            client = await self._cognitive_service.aget_client_for_role(
                model.manifest.role
            )
            raw = await asyncio.wait_for(
                model.invoke(
                    context={
                        "relation_description": relation_description,
                        "documents_text": documents_text,
                    },
                    client=client,
                    user_id=_USER_ID,
                ),
                timeout=_LLM_CALL_TIMEOUT,
            )
        except TimeoutError:
            logger.warning(
                "CCC: LLM call timed out after %ds for relation %s",
                _LLM_CALL_TIMEOUT,
                relation,
            )
            for rel in readable_rels:
                self._mark_skipped(manifest, rel, "call_timeout")
            return
        except Exception as exc:
            logger.warning("CCC: LLM call failed for relation %s: %s", relation, exc)
            for rel in readable_rels:
                self._mark_skipped(manifest, rel, "llm_call_failure")
            return

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("expected top-level JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "CCC: LLM output parse failure for relation %s: %s",
                relation,
                exc,
            )
            for rel in readable_rels:
                self._mark_skipped(manifest, rel, "llm_parse_failure")
            return

        for candidate in parsed:
            if not _is_valid_candidate(candidate):
                logger.warning(
                    "CCC: skipping invalid candidate in relation %s: %r",
                    relation,
                    candidate,
                )
                for rel in readable_rels:
                    self._mark_skipped(manifest, rel, "llm_schema_failure")
                return
            # The call-level relation is authoritative — the LLM's `relation`
            # field is not trusted, since the call boundary already fixes it.
            await self._coherence_service.add_candidate(
                run_id=run_id,
                relation=relation,
                documents=candidate["documents"],
                claim=candidate["claim"],
                rationale=candidate["rationale"],
            )

    # ------------------------------------------------------------------ #
    # Input enumeration
    # ------------------------------------------------------------------ #

    def _adr_paths(self) -> list[Path]:
        decisions_dir = self._repo_root / ".specs" / "decisions"
        if not decisions_dir.exists():
            return []
        return sorted(decisions_dir.glob("ADR-*.md"))

    def _northstar_paths(self) -> list[Path]:
        northstar_dir = self._repo_root / ".specs" / "northstar"
        if not northstar_dir.exists():
            return []
        return sorted(northstar_dir.glob("*.md"))

    def _rule_paths(self) -> list[Path]:
        """
        Return the rule path list for the current run. Cached so R2 and R3
        see the same set when ``--sample`` is in effect.
        """
        if self._rule_paths_cache is None:
            self._rule_paths_cache = self._discover_rule_paths(self._sample_rules)
        return self._rule_paths_cache

    def _discover_rule_paths(self, sample: int | None) -> list[Path]:
        """
        Discover rule documents via IntentRepository (the sanctioned gateway
        for .intent/ — rules.architecture.intent_access). Optionally subsample.
        """
        repo = get_intent_repository()
        repo.initialize()
        all_rule_paths = sorted(ref.path for ref in repo.list_policies())
        if sample is not None and 0 < sample < len(all_rule_paths):
            chosen = sorted(random.sample(all_rule_paths, sample))
            logger.info(
                "CCC: sampling %d of %d rule files for R2/R3",
                sample,
                len(all_rule_paths),
            )
            return chosen
        return all_rule_paths

    def _load_rule_id(self, rule_path: Path) -> str | None:
        try:
            repo = get_intent_repository()
            data = repo.load_document(rule_path)
            return data.get("metadata", {}).get("id") or None
        except Exception as exc:
            logger.warning("CCC: failed to load rule id from %s: %s", rule_path, exc)
            return None

    # ------------------------------------------------------------------ #
    # ADR ↔ rule fuzzy matching (R3)
    # ------------------------------------------------------------------ #

    def _match_adrs_to_rule(self, rule_id: str, adr_paths: list[Path]) -> list[Path]:
        last_segment = rule_id.split(".")[-1] if rule_id else ""
        tokens = [
            t.lower()
            for t in re.split(r"[_.-]", last_segment)
            if len(t) >= _FUZZY_MIN_TOKEN_LEN
        ]
        if not tokens:
            return []
        matched: list[Path] = []
        for adr_path in adr_paths:
            stem_lower = adr_path.stem.lower()
            if any(t in stem_lower for t in tokens):
                matched.append(adr_path)
        return matched

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self._repo_root))
        except ValueError:
            return str(path)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _mark_skipped(manifest: list[dict], rel_path: str, reason: str) -> None:
        for entry in manifest:
            if entry["path"] == rel_path:
                entry["status"] = "skipped"
                entry["skipped_reason"] = reason
                return


def _is_valid_candidate(candidate: Any) -> bool:
    if not isinstance(candidate, dict):
        return False
    if not all(k in candidate for k in ("relation", "documents", "claim", "rationale")):
        return False
    if not isinstance(candidate["documents"], list):
        return False
    if not all(isinstance(d, str) for d in candidate["documents"]):
        return False
    if not isinstance(candidate["claim"], str):
        return False
    if not isinstance(candidate["rationale"], str):
        return False
    return True
