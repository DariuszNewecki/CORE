# src/will/governance/integrity_runner.py

"""
Integrity runner facade — Will-layer entry point for the /integrity API
(ADR-055 D6 follow-up — closes #353).

The API layer must not import shared.infrastructure.* by constitutional
rule. This module is the sanctioned bridge: it wraps IntegrityService and
exposes plain functions the API can call with a CoreContext.

Two entry points — both synchronous, both filesystem-only:

* `create_baseline`   — SHA256-fingerprint every src/*.py and write
  var/integrity/baseline_{label}.json. Returns repo-relative path and
  file count.
* `verify_integrity`  — compare current src/ state against a saved
  baseline. Returns ok / errors / checked_at.

Operations are fast (single-digit seconds) and self-contained — no
core.integrity_runs persistence, no background-task plumbing. Closest
in-repo precedent for the synchronous facade shape is the IR scaffold
path used by POST /fix/ir.
"""

from __future__ import annotations

import json
from typing import Any

from shared.context import CoreContext
from shared.infrastructure.storage.integrity_service import IntegrityService


__all__ = ["create_baseline", "verify_integrity"]


# ID: 6fd65584-baae-48da-9fa3-eb596b16c821
def create_baseline(context: CoreContext, label: str) -> dict[str, Any]:
    """Create a SHA256 baseline of src/ and return path + file count."""
    repo_root = context.git_service.repo_path
    service = IntegrityService(repo_root)
    path = service.create_baseline(label)

    manifest = json.loads(path.read_text(encoding="utf-8"))
    files_hashed = len(manifest.get("files", {}))
    rel_path = str(path.relative_to(repo_root))

    return {
        "label": label,
        "path": rel_path,
        "files_hashed": files_hashed,
    }


# ID: 533749f5-106f-4f57-9a1a-ab553f4f28ee
def verify_integrity(context: CoreContext, label: str) -> dict[str, Any]:
    """Verify src/ against the named baseline and return ok / errors."""
    service = IntegrityService(context.git_service.repo_path)
    result = service.verify_integrity(label)

    return {
        "label": label,
        "ok": result.ok,
        "errors": list(result.errors),
        "checked_at": (result.metadata or {}).get("checked_at"),
    }
