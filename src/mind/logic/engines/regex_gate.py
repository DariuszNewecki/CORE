# src/mind/logic/engines/regex_gate.py

"""
Pattern-Based Governance Auditor.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to natively async to satisfy the BaseEngine contract.
- Complies with ASYNC230 by offloading blocking file reads to threads.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from mind.logic.record_contract import (
    RecordFinding,
    RulePart,
    engine_part,
    record_items,
)

from .base import CONTENT_NOT_EVALUATED, BaseEngine, EngineResult, EvidenceClass


def _pattern_lists(params: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The forbidden and required patterns of a rule's params."""
    forbidden = params.get("forbidden_patterns") or params.get("patterns", [])
    if isinstance(forbidden, str):
        forbidden = [forbidden]
    required = params.get("required_patterns", [])
    if isinstance(required, str):
        required = [required]
    return forbidden, required


def _content_violations(
    content: str, forbidden: list[str], required: list[str]
) -> list[str]:
    """The content check, separate from reading a file (ADR-173 D10)."""
    violations: list[str] = []
    # Forbidden patterns (negative check, e.g. secrets, PII)
    for pattern in forbidden:
        for match in re.finditer(pattern, content, re.MULTILINE):
            line_no = content.count("\n", 0, match.start()) + 1
            violations.append(
                f"Forbidden Content [Line {line_no}]: Matched restricted regex '{pattern}'"
            )
    # Required patterns (positive check, e.g. file headers)
    for pattern in required:
        if not re.search(pattern, content, re.MULTILINE):
            violations.append(
                f"Missing Required Content: Could not find pattern '{pattern}' in file."
            )
    return violations


def _decode_text(data: bytes) -> str | None:
    """The file's text, or None when it is not UTF-8 text (a NUL byte, or
    bytes that do not decode)."""
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


# ID: 76df2589-c0fd-48e3-b359-7c58e1c5ff71
class RegexGateEngine(BaseEngine):
    """
    Pattern-Based Governance Auditor.
    Enforces naming conventions and scans for forbidden patterns (secrets, syntax drift).
    """

    engine_id = "regex_gate"
    evidence_class = EvidenceClass.PROVEN  # ADR-113: deterministic verdict
    supports_records: ClassVar[bool] = True  # ADR-173 D10

    # ID: 53cc3e25-0d0c-41a7-8ad3-32f8e6963a1a
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Natively async verification.
        Matches the BaseEngine contract to prevent loop-hijacking in orchestrators.
        """
        violations: list[str | dict[str, Any]] = []

        # FACT 1: Check Filename Naming Conventions
        name_pattern = params.get("naming_pattern")
        if name_pattern:
            if not re.match(name_pattern, file_path.name):
                violations.append(
                    f"Naming Violation: File '{file_path.name}' does not match pattern '{name_pattern}'"
                )

        # FACT 2: Check Content
        try:
            # Use to_thread to prevent blocking the event loop during file I/O.
            data = await asyncio.to_thread(file_path.read_bytes)
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"IO Error: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        forbidden, required = _pattern_lists(params)

        content = _decode_text(data)
        if content is None:
            # #1050: a binary or non-UTF-8 file has no text to match. Its
            # content is not evaluated (reported by the executor), which is
            # neither a pass nor a failure; the naming check above still holds.
            return EngineResult(
                ok=not violations,
                message="Content not evaluated: not UTF-8 text.",
                violations=violations,
                engine_id=self.engine_id,
                extra=(
                    {CONTENT_NOT_EVALUATED: "not UTF-8 text"}
                    if forbidden or required
                    else {}
                ),
            )

        violations.extend(_content_violations(content, forbidden, required))

        if not violations:
            return EngineResult(
                ok=True,
                message="Pattern compliance verified.",
                violations=[],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=False,
            message=f"Constitutional Violation: {len(violations)} pattern mismatches found.",
            violations=violations,
            engine_id=self.engine_id,
        )

    # ID: 4b79424c-6e37-4b8b-81d7-2ab6e09777d5
    async def evaluate_record(
        self, record: Mapping[str, Any], rule: str, params: dict[str, Any]
    ) -> RulePart:
        """The pattern check over one string field of each item (ADR-173 D10).

        Params: ``field`` (the item key to read, default ``value``),
        ``item_types`` (only items of these types; default all), and the same
        ``forbidden_patterns`` / ``required_patterns`` as for files. An item
        whose field is missing or not a string is not checked.
        """
        field_name = params.get("field", "value")
        forbidden, required = _pattern_lists(params)
        findings = []
        for item_id, item in record_items(record, params.get("item_types")):
            content = item.get(field_name)
            if not isinstance(content, str):
                continue
            for message in _content_violations(content, forbidden, required):
                findings.append(
                    RecordFinding(
                        rule=rule,
                        message=f"{item_id}.{field_name}: {message}",
                        blocking=True,
                        item=item_id,
                    )
                )
        return engine_part(self, rule, findings)
