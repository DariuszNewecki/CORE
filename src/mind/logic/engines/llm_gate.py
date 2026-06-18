# src/mind/logic/engines/llm_gate.py

"""
Semantic Reasoning Auditor.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to natively async to satisfy the BaseEngine contract.
- Prevents thread-blocking during long-running LLM API calls.
- Complies with ASYNC230 by offloading blocking file reads to threads.

HARDENING (V2.7):
- Uses Protocols to avoid Mind -> Body leakage (P2.2).
- Handles AI failures as 'UNAVAILABLE' for audit truthfulness (P1.3).
- Prompts governed via var/prompts/llm_gate/ PromptModel artifact.

ADR-044 — Incremental LLM-gate verdict cache:
- Before dispatching to Ollama, checks core.llm_gate_verdicts for a row
  keyed on (rule_id, file_path, file_content_hash, rule_content_hash).
- On hit: reconstructs EngineResult from the stored verdict + findings;
  emits one INFO line and returns without calling the LLM.
- On miss: invokes the LLM as before, upserts the verdict row, returns.
- file_content_hash is sourced from core.repo_artifacts.content_hash when
  the crawler's last_crawled_at is fresher than the staleness threshold;
  otherwise recomputed inline from file bytes.
- The previous in-process LRU cache (ADR-043 D5) is subsumed: the DB cache
  provides the same dedup with cross-process and cross-run scope.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger

from .base import BaseEngine, EngineResult, EvidenceClass


if TYPE_CHECKING:
    from shared.path_resolver import PathResolver
    from shared.protocols.llm import LLMClientProtocol


logger = getLogger(__name__)


# ADR-044 defaults — read at staleness/TTL check time, overridable via
# operational_config once Step 6 wires the canonical config surface.
_DEFAULT_STALENESS_THRESHOLD_SECONDS = 3600


# ID: 8df9b4cd-934a-4115-8e51-2a57833a77d2
class LLMGateEngine(BaseEngine):
    """
    Semantic Reasoning Auditor.

    Uses LLM reasoning to verify abstract rules (Spirit of the Law).
    Decoupled from the Body layer via LLMClientProtocol.
    Prompts governed via var/prompts/llm_gate/ PromptModel artifact.
    """

    engine_id = "llm_gate"
    evidence_class = EvidenceClass.JUDGED  # ADR-113: AI/semantic verdict

    def __init__(
        self,
        path_resolver: PathResolver,
        llm_client: LLMClientProtocol,
    ):
        self._paths = path_resolver
        self.llm = llm_client
        self._prompt_model = PromptModel.load("llm_gate")
        self._audit_prompt_model = PromptModel.load("llm_gate_audit_prompt")

    # ID: 66b7f4b7-72a8-43b9-af11-787c58e20524
    async def verify(
        self,
        file_path: Path,
        params: dict[str, Any],
    ) -> EngineResult:
        """
        Natively async verification.

        Performs semantic analysis via LLM without blocking the event loop.
        """

        instruction = params.get("instruction")
        rationale = params.get("rationale", "No rationale provided.")
        rule_id: str | None = params.get("_rule_id")
        rule_content_hash: str = params.get("_rule_content_hash") or ""
        force_llm: bool = bool(params.get("_force_llm"))

        # 1. Read file content safely (ASYNC230 compliant)
        try:
            content = await asyncio.to_thread(
                file_path.read_text,
                encoding="utf-8",
            )
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"IO Error: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        try:
            rel_path = str(file_path.relative_to(self._paths.repo_root))
        except ValueError:
            rel_path = str(file_path)

        # ADR-044: cache layer. Skipped when rule identity isn't plumbed
        # (defensive — keeps the engine functional even if a caller bypasses
        # rule_executor), when the operator forced a fresh evaluation, or
        # when the audit driver did not inject a DB session (Mind layer
        # cannot open sessions itself — see audit_context.db_session).
        auditor_context = params.get("_context")
        session = getattr(auditor_context, "db_session", None)
        cache_eligible = bool(rule_id and rule_content_hash and session is not None)
        file_content_hash: str | None = None

        if cache_eligible:
            file_content_hash = await _resolve_file_content_hash(
                session, rel_path, content
            )

            if not force_llm:
                cached = await _read_cached_verdict(
                    session,
                    rule_id=rule_id,
                    file_path=rel_path,
                    file_content_hash=file_content_hash,
                    rule_content_hash=rule_content_hash,
                )
                if cached is not None:
                    logger.info("llm_gate cache hit: %s %s", rule_id, rel_path)
                    return cached

        # 2. Invoke via PromptModel (cache miss or cache-disabled path)
        try:
            response_text = await self._audit_prompt_model.invoke(
                context={
                    "instruction": instruction,
                    "rationale": rationale,
                    "content": content,
                },
                client=self.llm,
                user_id="llm_gate_engine",
            )

            result_data = json.loads(response_text)

            is_ok = not result_data.get("violation", False)

            message = (
                "Semantic adherence verified."
                if is_ok
                else f"Semantic Violation: {result_data.get('reasoning')}"
            )

            violations = (
                [result_data.get("finding")]
                if not is_ok and result_data.get("finding")
                else []
            )

            final_result = EngineResult(
                ok=is_ok,
                message=message,
                violations=violations,
                engine_id=self.engine_id,
            )
            verdict_label = "PASS" if is_ok else "FAIL"

        except Exception as e:
            # P1.3 HARDENING:
            # If the AI fails, enforcement is unavailable (truthful audit result)
            final_result = EngineResult(
                ok=False,
                message=f"ENFORCEMENT_UNAVAILABLE: LLM Reasoning Failed: {e}",
                violations=["SYSTEM_ERROR_AI_OFFLINE"],
                engine_id=self.engine_id,
            )
            verdict_label = "ERROR"

        # 3. Persist verdict to the ADR-044 DB cache. Skipped for ERROR
        # verdicts (transient infra failures, not a stable judgement) and
        # when rule identity / session aren't plumbed.
        if cache_eligible and verdict_label != "ERROR":
            assert file_content_hash is not None
            await _write_cached_verdict(
                session,
                rule_id=rule_id,
                file_path=rel_path,
                file_content_hash=file_content_hash,
                rule_content_hash=rule_content_hash,
                verdict=verdict_label,
                findings=final_result.violations,
            )

        return final_result


# ----------------------------------------------------------------------
# ADR-044 cache helpers — file-content hash resolution, read, write.
# Module-level so they remain testable independently of LLMGateEngine
# construction.
# ----------------------------------------------------------------------


# ID: 5a8e3f4d-7c1b-49a2-b603-9d2f8a1c4e5f
async def _resolve_file_content_hash(session: Any, rel_path: str, content: str) -> str:
    """Return SHA-256 of file content for cache keying.

    Tries the crawler-maintained core.repo_artifacts.content_hash first.
    Falls back to inline hashing when:
      - the file has no repo_artifacts row (never crawled),
      - the row's last_crawled_at is older than the staleness threshold,
      - or the DB lookup fails for any reason.

    Inline hashing matches CrawlService._sha256: SHA-256 of the file's
    UTF-8 byte content. The session is injected by the audit driver
    (Mind layer cannot open sessions itself); callers that pass None
    fall through to the inline hash.
    """
    inline = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if session is None:
        return inline

    threshold = _DEFAULT_STALENESS_THRESHOLD_SECONDS
    try:
        from shared.infrastructure.intent.operational_config import (
            load_operational_config,
        )

        cfg = load_operational_config()
        threshold = int(
            getattr(
                getattr(cfg, "audit", object()),
                "llm_gate_cache_staleness_threshold_seconds",
                threshold,
            )
        )
    except Exception:
        pass

    try:
        from sqlalchemy import text

        result = await session.execute(
            text(
                """
                SELECT content_hash,
                       EXTRACT(EPOCH FROM (NOW() - last_crawled_at))::int
                            AS age_seconds
                FROM core.repo_artifacts
                WHERE file_path = :file_path
                """
            ),
            {"file_path": rel_path},
        )
        row = result.fetchone()
        if row is None:
            return inline
        stored_hash, age_seconds = row[0], row[1]
        if age_seconds is None or age_seconds > threshold:
            return inline
        return stored_hash or inline
    except Exception as exc:
        logger.debug(
            "llm_gate: file_content_hash lookup failed for %s (%s); using inline hash",
            rel_path,
            exc,
        )
        return inline


# ID: 6c9d4e8a-2b7f-4a13-8e6c-1d5f9a3b8c7e
async def _read_cached_verdict(
    session: Any,
    *,
    rule_id: str,
    file_path: str,
    file_content_hash: str,
    rule_content_hash: str,
) -> EngineResult | None:
    """Return cached EngineResult for the given key, or None on miss/failure.

    Cache failures (DB unavailable, schema drift) return None — the engine
    then falls through to the live LLM call. Cache correctness is bounded
    by the unique-constraint on (rule_id, file_path, file_content_hash,
    rule_content_hash); we never serve a stale hash combination.
    """
    if session is None:
        return None
    try:
        from sqlalchemy import text

        result = await session.execute(
            text(
                """
                SELECT verdict, findings_json
                FROM core.llm_gate_verdicts
                WHERE rule_id = :rule_id
                  AND file_path = :file_path
                  AND file_content_hash = :fch
                  AND rule_content_hash = :rch
                LIMIT 1
                """
            ),
            {
                "rule_id": rule_id,
                "file_path": file_path,
                "fch": file_content_hash,
                "rch": rule_content_hash,
            },
        )
        row = result.fetchone()
        if row is None:
            return None
        verdict, findings_json = row[0], row[1]
        findings = findings_json if isinstance(findings_json, list) else []
        ok = verdict == "PASS"
        message = (
            "Semantic adherence verified (cached)."
            if ok
            else "Semantic Violation (cached)."
        )
        return EngineResult(
            ok=ok,
            message=message,
            violations=findings,
            engine_id="llm_gate",
        )
    except Exception as exc:
        logger.debug(
            "llm_gate: cache read failed for %s/%s (%s)",
            rule_id,
            file_path,
            exc,
        )
        return None


# ID: 4f7b2c8d-9e1a-43f5-a04c-7b8d3e6f1a2c
async def _write_cached_verdict(
    session: Any,
    *,
    rule_id: str,
    file_path: str,
    file_content_hash: str,
    rule_content_hash: str,
    verdict: str,
    findings: list[str | dict[str, Any]],
) -> None:
    """Upsert a verdict row. Failures are logged and swallowed.

    Uses ON CONFLICT on the cache-key unique constraint so concurrent
    daemon + manual-audit writers converge on a single row per key
    rather than racing. Session is injected by the audit driver; a None
    session no-ops the write (cache stays empty rather than the Mind
    layer reaching into Body to acquire one).
    """
    if session is None:
        return
    try:
        from sqlalchemy import text

        await session.execute(
            text(
                """
                INSERT INTO core.llm_gate_verdicts
                    (rule_id, file_path, file_content_hash,
                     rule_content_hash, verdict, findings_json,
                     evaluated_at)
                VALUES
                    (:rule_id, :file_path, :fch, :rch, :verdict,
                     CAST(:findings AS jsonb), now())
                ON CONFLICT (rule_id, file_path, file_content_hash,
                             rule_content_hash)
                DO UPDATE SET
                    verdict = EXCLUDED.verdict,
                    findings_json = EXCLUDED.findings_json,
                    evaluated_at = EXCLUDED.evaluated_at
                """
            ),
            {
                "rule_id": rule_id,
                "file_path": file_path,
                "fch": file_content_hash,
                "rch": rule_content_hash,
                "verdict": verdict,
                "findings": json.dumps(findings),
            },
        )
        await session.commit()
    except Exception as exc:
        logger.warning(
            "llm_gate: cache write failed for %s/%s (%s) — verdict not persisted",
            rule_id,
            file_path,
            exc,
        )
