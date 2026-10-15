# src/shared/infrastructure/law_venv.py
"""Is core-law's venv the live release's wheel? (#1018)

``sudo -u core-law /opt/core-law/venv/bin/core-admin law apply`` runs this
venv. On 2026-10-15 it was core_runtime 2.14.2 from PyPI, older than the
durable ledger, and law 0035's ledger line went to the wrong place without
anything noticing. A version string cannot tell: SHA-deployed releases all
report the same version. The wheel hash can.

Compares, read-only:
- the live SHA (core-pipeline's status.json ``live``) and that release's
  ``venv/core-release.json`` (sha, wheel_sha256),
- with ``/opt/core-law/venv/core-release.json`` and the wheel hash pip
  recorded for core-runtime in the venv (``direct_url.json``).

On a host without the runtime (no status.json) there is nothing to compare:
the check does not apply. Anything else that cannot be read is a problem.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PIPELINE_STATUS = Path("/var/lib/core-pipeline/status.json")
RELEASES = Path("/opt/core/releases")
LAW_VENV = Path("/opt/core-law/venv")


@dataclass(frozen=True)
# ID: 0c5baeac-2a87-4514-ab85-02a7d9b1fe4c
class LawVenvState:
    """The comparison's outcome: ``applies`` False on a host without the runtime."""

    applies: bool
    problem: str | None = None
    live_sha: str | None = None
    venv_sha: str | None = None


def _json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def _venv_wheel_hash(venv: Path) -> str | None:
    for record in sorted(
        venv.glob("lib/python*/site-packages/core_runtime-*.dist-info/direct_url.json")
    ):
        info = _json(record).get("archive_info") or {}
        hashes = info.get("hashes") or {}
        if hashes.get("sha256"):
            return str(hashes["sha256"])
        legacy = str(info.get("hash") or "")
        if legacy.startswith("sha256="):
            return legacy.removeprefix("sha256=")
    return None


# ID: 78253b95-b9be-45e1-8d63-3f2460d8b5ff
def check_law_venv(
    status_path: Path = PIPELINE_STATUS,
    releases: Path = RELEASES,
    venv: Path = LAW_VENV,
) -> LawVenvState:
    """Compare core-law's venv with the live release; never raises."""
    if not status_path.exists():
        return LawVenvState(applies=False)
    try:
        live = str(_json(status_path).get("live") or "")
        if not live:
            return LawVenvState(True, "core-pipeline reports no live release")
        release = _json(releases / live / "venv" / "core-release.json")
    except (OSError, ValueError) as exc:
        return LawVenvState(True, f"live release record unreadable: {exc}")
    try:
        record = _json(venv / "core-release.json")
        installed = _venv_wheel_hash(venv)
    except (OSError, ValueError) as exc:
        return LawVenvState(True, f"core-law venv unreadable: {exc}", live_sha=live)
    venv_sha = str(record.get("sha") or "")
    wanted = str(release.get("wheel_sha256") or "")
    if installed is None:
        return LawVenvState(
            True,
            "core-law venv has no recorded core-runtime wheel hash",
            live,
            venv_sha,
        )
    if installed != wanted or str(record.get("wheel_sha256") or "") != wanted:
        return LawVenvState(
            True,
            f"core-law venv runs release {venv_sha[:12] or 'unknown'} (wheel "
            f"{installed[:12]}), the live release is {live[:12]} (wheel {wanted[:12]})",
            live,
            venv_sha,
        )
    return LawVenvState(True, None, live, venv_sha)
