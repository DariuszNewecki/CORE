# src/will/workers/dead_shim_sensor.py

"""
DeadShimSensor — the ADR-151 dead-shim reaper's detection half.

Posts a python::modernization.dead_shim::<symbol_path> finding for every
public symbol satisfying the D1 conjunction: self-declared deprecated
(state='deprecated', attributed by the sync visitor — which already applies
the property exclusion and dispatch-registration grace) AND zero inbound
call edges outside tests/. The remaining D2 grace — the published __all__
extension contract — is applied here, where the packages are importable.

ADR-091 D2 Revision B resolution classification:
- Subject prefix:        python::modernization.dead_shim::<symbol_path>
- resolution_mechanism:  self_resolve
- Resolver path:         this sensor's own run() method. After the flagging
                         pass, every open finding whose subject is not in
                         this cycle's flagged_subjects set is resolved via
                         BlackboardService.resolve_entries — the finding
                         clears when the symbol is deleted, gains a caller,
                         or loses its deprecation marker.

Enforcement is REPORTING (ADR-151 D3): findings surface; deletion remains a
governed, verify-then-delete act (D4) — the static graph cannot see dynamic
dispatch, so zero-edges is necessary but not sufficient evidence.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.scheduled_worker import ScheduledWorker


logger = getLogger(__name__)

_SUBJECT_PREFIX = "python::modernization.dead_shim"
_CANDIDATE_LIMIT = 200

# ADR-151 D2 dispatch grace, path half: the visitor's decorator detection
# cannot see PROGRAMMATIC registration (measured: register_drift_commands
# wires "DEPRECATED alias" Typer commands with no decorator on the handler).
# These namespaces ARE the dispatch surfaces (ADR-146 split), so symbols
# under them are graced by path. Over-grace is the safe direction (a missed
# finding, never a false reap). cli/logic/ is deliberately NOT graced —
# helpers there are ordinary symbols (the day-one catch lives there).
_DISPATCH_PATH_PREFIXES = ("src/cli/commands/", "src/api/v1/")


def _published_contract_names() -> set[tuple[str, str]]:
    """(package_root, name) pairs from the top-level __all__ contracts.

    F-48.4 keeps these deliberately minimal (currently 5 in shared + 1 in
    mind). Matching is by (root, name) — over-grace on a name collision is
    the safe direction (a missed finding, never a false reap).
    """
    graced: set[tuple[str, str]] = set()
    for package_root in ("shared", "mind", "api", "body", "cli", "will"):
        try:
            pkg = __import__(package_root)
        except Exception:  # pragma: no cover - import environment issue
            continue
        for name in getattr(pkg, "__all__", []):
            graced.add((package_root, name))
    return graced


# ID: 55aa9c3f-11b5-4b8e-b3fb-636e71da866e
class DeadShimSensor(ScheduledWorker):
    """Graph-backed sensor for the ADR-151 dead-shim conjunction."""

    declaration_name = "dead_shim_sensor"

    def __init__(self, core_context: Any = None) -> None:
        super().__init__()
        self._core_context = core_context

    # ID: b3780791-0a68-4ba7-9893-b2085483ac08
    async def run(self) -> None:
        """
        One sensing cycle:
        1. Post heartbeat.
        2. Fetch D1-conjunction candidates (SymbolService, Body layer).
        3. Apply the D2 __all__ grace.
        4. Post findings for new candidates; skip already-open ones.
        5. Self-resolve open findings whose condition has cleared.
        6. Post completion report.
        """
        from body.services.service_registry import service_registry

        await self.post_heartbeat()

        symbol_svc = await service_registry.get_symbol_service()
        blackboard_svc = await service_registry.get_blackboard_service()

        candidates = await symbol_svc.fetch_dead_shim_candidates(limit=_CANDIDATE_LIMIT)

        graced_names = _published_contract_names()
        live: list[dict[str, Any]] = []
        graced_count = 0
        graced_dispatch = 0
        for row in candidates:
            if str(row["symbol_path"]).startswith(_DISPATCH_PATH_PREFIXES):
                graced_dispatch += 1
                continue
            package_root = str(row["module"]).split(".", 1)[0]
            top_name = str(row["qualname"]).split(".", 1)[0]
            if (package_root, top_name) in graced_names:
                graced_count += 1
                continue
            live.append(row)

        existing = {
            r["subject"]: r["id"]
            for r in await blackboard_svc.fetch_open_findings(
                prefix=f"{_SUBJECT_PREFIX}::%",
                limit=_CANDIDATE_LIMIT,
            )
        }

        flagged_subjects: set[str] = set()
        posted = 0
        for row in live:
            subject = f"{_SUBJECT_PREFIX}::{row['symbol_path']}"
            flagged_subjects.add(subject)
            if subject in existing:
                continue
            await self.post_finding(
                subject=subject,
                payload={
                    "symbol_path": row["symbol_path"],
                    "module": row["module"],
                    "qualname": row["qualname"],
                    "kind": row["kind"],
                    "rule": "modernization.dead_shim",
                    "remediation_contract": (
                        "ADR-151 D4 verify-then-delete: confirm no dynamic/"
                        "string-keyed dispatch or config reference before "
                        "governed deletion; remove orphaned imports/warnings "
                        "in the same change."
                    ),
                },
                resolution_mechanism="self_resolve",
            )
            posted += 1

        resolved = 0
        for subject, entry_id in existing.items():
            if subject not in flagged_subjects:
                await blackboard_svc.resolve_entries([entry_id])
                resolved += 1
                logger.info(
                    "DeadShimSensor: %s cleared — resolving open finding", subject
                )

        await self.post_report(
            subject="dead_shim_sensor.run.complete",
            payload={
                "candidates": len(candidates),
                "graced_published_contract": graced_count,
                "graced_dispatch_surface": graced_dispatch,
                "flagged": len(flagged_subjects),
                "posted": posted,
                "resolved": resolved,
            },
        )
        if flagged_subjects:
            logger.warning(
                "DeadShimSensor: %d dead-shim finding(s) open (%d new this cycle)",
                len(flagged_subjects),
                posted,
            )
