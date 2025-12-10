# src/shared/infrastructure/context/redactor.py

"""Provides functionality for the redactor module."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
# ID: 3df1f51b-2647-4409-bfb4-9fc2f2e5c324
class RedactionEvent:
    kind: str
    path: str | None
    reason: str
    detail: str | None = None


@dataclass
# ID: 4c2af27e-20b3-4f51-8bd0-268fd67e7e7e
class RedactionReport:
    applied: list[RedactionEvent] = field(default_factory=list)

    # ID: 9b3765f9-84ef-49a3-81c9-d1ddecd0548a
    def add(self, event: RedactionEvent) -> None:
        self.applied.append(event)

    @property
    # ID: ada22ab0-bd08-4838-96a9-e709a0b8fb56
    def touched_sensitive(self) -> bool:
        return any(
            e.kind in ("content_masked", "content_removed", "path_removed")
            for e in self.applied
        )


DEFAULT_FORBIDDEN_PATHS = [
    ".env",  # Root .env
    ".env.*",
    "**/.env",  # Nested .env
    "**/.env.*",
    "**/env/**",
    "**/secrets/**",
    "**/credentials/**",
]


def _should_remove_path(path: str, forbidden_globs: list[str]) -> bool:
    p = Path(path)
    return any(p.match(glob) for glob in forbidden_globs)


# ID: 870efb24-abf2-4c34-8749-55d68289de8b
def redact_packet(
    packet: dict[str, Any], policy: dict[str, Any] | None = None
) -> tuple[dict[str, Any], RedactionReport]:
    policy = policy or {}
    red_cfg = policy.get("redaction", {})
    forbidden_paths = red_cfg.get("forbidden_paths") or DEFAULT_FORBIDDEN_PATHS

    pkt = copy.deepcopy(packet)
    report = RedactionReport()
    items: list[dict[str, Any]] = pkt.get("items", [])

    kept = []
    for it in items:
        path = it.get("path") or ""
        if path and _should_remove_path(path, forbidden_paths):
            report.add(RedactionEvent("path_removed", path, "forbidden_path"))
            continue
        kept.append(it)
    pkt["items"] = kept

    header = pkt.setdefault("header", {})
    pol = header.setdefault("policy", {})
    pol["redactions_applied"] = [
        {"kind": e.kind, "path": e.path, "reason": e.reason} for e in report.applied
    ]
    if report.touched_sensitive:
        header.setdefault("privacy", {})["remote_allowed"] = False

    return pkt, report


# ID: 303c0595-07f9-42ae-bf86-5ba9f00fd376
class ContextRedactor:
    def __init__(self, policy: dict[str, Any] | None = None):
        self.policy = policy or {}

    # ID: 7c58f81a-bcc7-4459-bed7-13a0e69b2fa5
    def redact(self, packet: dict[str, Any]) -> dict[str, Any]:
        pkt, _ = redact_packet(packet, self.policy)
        return pkt
