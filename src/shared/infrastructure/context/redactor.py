# src/shared/infrastructure/context/redactor.py

"""Context packet redaction utilities."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
# ID: 217da260-f777-4fa1-a29b-da690f973cd6
class RedactionEvent:
    kind: str
    path: str | None
    reason: str
    detail: str | None = None


@dataclass
# ID: fe03be1b-2d23-4707-8428-8c5f7cc1be3b
class RedactionReport:
    applied: list[RedactionEvent] = field(default_factory=list)

    # ID: 402fe6fa-d954-4108-afd3-c6a498efb5e8
    def add(self, event: RedactionEvent) -> None:
        self.applied.append(event)

    @property
    # ID: ea34d53e-e4da-4a60-b834-9935fcdf2b0a
    def touched_sensitive(self) -> bool:
        return any(
            event.kind in {"content_masked", "content_removed", "path_removed"}
            for event in self.applied
        )


DEFAULT_FORBIDDEN_PATHS = [
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    "**/env/**",
    "**/secrets/**",
    "**/credentials/**",
]


def _should_remove_path(path: str, forbidden_globs: list[str]) -> bool:
    p = Path(path)
    return any(p.match(glob) for glob in forbidden_globs)


# ID: 2ba5eab5-8e98-4093-9395-6d6fa01db53e
def redact_packet(
    packet: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], RedactionReport]:
    policy = policy or {}
    red_cfg = policy.get("redaction", {})
    forbidden_paths = red_cfg.get("forbidden_paths") or DEFAULT_FORBIDDEN_PATHS

    pkt = copy.deepcopy(packet)
    report = RedactionReport()

    evidence = pkt.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    kept: list[dict[str, Any]] = []
    for item in evidence:
        path = item.get("path") or ""
        if path and _should_remove_path(path, forbidden_paths):
            report.add(RedactionEvent("path_removed", path, "forbidden_path"))
            continue
        kept.append(item)

    pkt["evidence"] = kept

    provenance = pkt.setdefault("provenance", {})
    provenance["redactions_applied"] = [
        {
            "kind": event.kind,
            "path": event.path,
            "reason": event.reason,
            "detail": event.detail,
        }
        for event in report.applied
    ]
    provenance["sensitive_content_touched"] = report.touched_sensitive

    header = pkt.setdefault("header", {})
    if report.touched_sensitive:
        header["privacy"] = "local_only"

    return pkt, report


# ID: 66112a36-f621-4c79-b299-f92ea0d6de5e
class ContextRedactor:
    def __init__(self, policy: dict[str, Any] | None = None) -> None:
        self.policy = policy or {}

    # ID: 99f8c335-34c5-4bc8-b883-15121dcf55bc
    def redact(self, packet: dict[str, Any]) -> dict[str, Any]:
        pkt, _ = redact_packet(packet, self.policy)
        return pkt
