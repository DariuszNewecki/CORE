# src/shared/infrastructure/repositories/db/manifest.py
"""
Typed view of ``infra/migrations/manifest.yaml`` (ADR-162 D6, D7, D12 §2-3).

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination) — parses and validates
the manifest; decides nothing about which migration to run.

Manifest shape::

    migrations:
      directory: infra/scripts/migrations
      order:                      # append-only, chronological filenames
        - 20260426_....sql
      probes:                     # optional, keyed by an ``order`` entry
        20260722_active_finding_dedup.sql:
          verify: "select exists (...)"   # boolean SQL — the postcondition
          reconcilable: true              # D12 §2: record-without-execute
                                          # permitted iff verify passes
          transactional: true             # reserved; false is refused (D7)
      baselines:                  # optional, D3/D4 — declared upgrade origins
        v2.9.1:
          through: 20260628_....sql       # last entry included in the baseline
          probes:                         # every one must be true to adopt
            - "select exists (...)"
            - "select not exists (...)"   # discriminates from later baselines

Every ``probes`` / ``baselines`` query is a read-only SQL statement returning
exactly one boolean. Structural violations raise :class:`ManifestError`
(fail closed, ``governance.no_governance_bypass``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .common import REPO_ROOT, load_policy


_ENTRY_KEYS = {"verify", "reconcilable", "transactional"}
_BASELINE_KEYS = {"through", "probes"}
_MIGRATIONS_KEYS = {"directory", "order", "probes", "baselines"}


# ID: 6859f5b8-bdb8-4c1a-9dea-ff7bfa7e634a
class ManifestError(ValueError):
    """The migration manifest is structurally invalid."""


@dataclass(frozen=True)
# ID: 0cf4e9af-fe41-450a-ab19-70c668b07ddb
class MigrationEntry:
    """One ledgered migration: its file and its verification contract."""

    id: str
    verify: str | None = None
    reconcilable: bool = False
    transactional: bool = True


@dataclass(frozen=True)
# ID: 8d457a01-7a01-4844-baa7-9c81db4ed9c9
class Baseline:
    """A declared upgrade origin: the manifest prefix a release shipped with."""

    tag: str
    through: str
    probes: tuple[str, ...]


@dataclass(frozen=True)
# ID: fecf824f-967f-4418-8f02-8715ad64d908
class Manifest:
    """The validated manifest."""

    directory: Path
    entries: tuple[MigrationEntry, ...]
    baselines: tuple[Baseline, ...] = field(default_factory=tuple)

    @property
    # ID: b4df6566-6764-4492-992b-585312bc3c22
    def order(self) -> tuple[str, ...]:
        return tuple(e.id for e in self.entries)

    # ID: 5e0b237d-80f2-4617-bbd5-84e9771ccf3f
    def entry(self, mig_id: str) -> MigrationEntry:
        for e in self.entries:
            if e.id == mig_id:
                return e
        raise KeyError(mig_id)

    # ID: bcd9922c-64c4-4ec7-a0a3-96e37f7c3be5
    def baseline(self, tag: str) -> Baseline:
        for b in self.baselines:
            if b.tag == tag:
                return b
        raise KeyError(tag)

    # ID: e4794203-2e89-4b66-9531-104702ee039c
    def entries_through(self, mig_id: str) -> tuple[MigrationEntry, ...]:
        """Entries up to and including ``mig_id`` in manifest order."""
        idx = self.order.index(mig_id)
        return self.entries[: idx + 1]

    # ID: 33168a0d-0c19-4aa7-97be-11410dd56662
    def sql_path(self, mig_id: str, repo_root: Path) -> Path:
        return repo_root / self.directory / mig_id


def _require_bool(value: Any, *, where: str) -> bool:
    if not isinstance(value, bool):
        raise ManifestError(f"{where} must be a boolean, got {value!r}")
    return value


def _require_probe(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{where} must be a non-empty SQL string")
    return value.strip()


# ID: 5ff67c6f-1d5f-41f6-b820-c3bbfe926ff8
def parse_manifest(policy: dict[str, Any]) -> Manifest:
    """Build a :class:`Manifest` from the raw YAML mapping, validating structure."""
    if not isinstance(policy, dict) or not isinstance(policy.get("migrations"), dict):
        raise ManifestError("manifest must contain a 'migrations' mapping")
    cfg: dict[str, Any] = policy["migrations"]
    unknown = set(cfg) - _MIGRATIONS_KEYS
    if unknown:
        raise ManifestError(f"unknown keys under migrations: {sorted(unknown)}")

    directory = cfg.get("directory")
    if not isinstance(directory, str) or not directory:
        raise ManifestError("migrations.directory must be a non-empty string")

    order = cfg.get("order")
    if not isinstance(order, list) or not order:
        raise ManifestError("migrations.order must be a non-empty list")
    if any(not isinstance(m, str) or not m.endswith(".sql") for m in order):
        raise ManifestError("every migrations.order entry must be a .sql filename")
    if len(set(order)) != len(order):
        dupes = sorted({m for m in order if order.count(m) > 1})
        raise ManifestError(f"migrations.order lists entries more than once: {dupes}")

    raw_probes = cfg.get("probes") or {}
    if not isinstance(raw_probes, dict):
        raise ManifestError("migrations.probes must be a mapping keyed by filename")
    orphan = sorted(set(raw_probes) - set(order))
    if orphan:
        raise ManifestError(f"migrations.probes keys not in order: {orphan}")

    entries: list[MigrationEntry] = []
    for mig_id in order:
        spec = raw_probes.get(mig_id)
        if spec is None:
            entries.append(MigrationEntry(id=mig_id))
            continue
        if not isinstance(spec, dict):
            raise ManifestError(f"migrations.probes[{mig_id}] must be a mapping")
        extra = set(spec) - _ENTRY_KEYS
        if extra:
            raise ManifestError(
                f"migrations.probes[{mig_id}] has unknown keys: {sorted(extra)}"
            )
        verify = (
            _require_probe(spec["verify"], where=f"probes[{mig_id}].verify")
            if "verify" in spec
            else None
        )
        reconcilable = _require_bool(
            spec.get("reconcilable", False), where=f"probes[{mig_id}].reconcilable"
        )
        transactional = _require_bool(
            spec.get("transactional", True), where=f"probes[{mig_id}].transactional"
        )
        if reconcilable and verify is None:
            raise ManifestError(
                f"probes[{mig_id}] is reconcilable but declares no verify probe "
                "(ADR-162 D12 §2: reconciliation requires a proving probe)"
            )
        entries.append(
            MigrationEntry(
                id=mig_id,
                verify=verify,
                reconcilable=reconcilable,
                transactional=transactional,
            )
        )

    raw_baselines = cfg.get("baselines") or {}
    if not isinstance(raw_baselines, dict):
        raise ManifestError("migrations.baselines must be a mapping keyed by tag")
    baselines: list[Baseline] = []
    for tag, spec in raw_baselines.items():
        if not isinstance(tag, str) or not tag:
            raise ManifestError("baseline tags must be non-empty strings")
        if not isinstance(spec, dict):
            raise ManifestError(f"baselines[{tag}] must be a mapping")
        extra = set(spec) - _BASELINE_KEYS
        if extra:
            raise ManifestError(f"baselines[{tag}] has unknown keys: {sorted(extra)}")
        through = spec.get("through")
        if not isinstance(through, str) or through not in order:
            raise ManifestError(
                f"baselines[{tag}].through must name an order entry, got {through!r}"
            )
        probes = spec.get("probes")
        if not isinstance(probes, list) or not probes:
            raise ManifestError(
                f"baselines[{tag}].probes must be a non-empty list (ADR-162 D3)"
            )
        baselines.append(
            Baseline(
                tag=tag,
                through=through,
                probes=tuple(
                    _require_probe(p, where=f"baselines[{tag}].probes[{i}]")
                    for i, p in enumerate(probes)
                ),
            )
        )
    # Baselines are an ordered chain (D4): later tags include earlier prefixes.
    positions = [order.index(b.through) for b in baselines]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise ManifestError(
            "baselines must be declared in chronological order with distinct "
            "'through' entries (ADR-162 D4)"
        )

    return Manifest(
        directory=Path(directory),
        entries=tuple(entries),
        baselines=tuple(baselines),
    )


# ID: e48cf184-967d-4a53-aa06-12a8db8e15d3
def verify_manifest_matches_disk(manifest: Manifest, repo_root: Path) -> None:
    """Every entry has a file and every ``.sql`` file is an entry (ADR-162 D6, D12 §3).

    Raises :class:`ManifestError` naming the offenders. There is no unmanaged
    list: a ``.sql`` file in the migrations directory that the manifest does
    not ledger is an unledgered schema change, and the engine refuses to run
    with one present rather than pretend the ledger is complete.
    """
    directory = repo_root / manifest.directory
    if not directory.is_dir():
        raise ManifestError(f"migrations directory not found: {directory}")
    on_disk = {p.name for p in directory.glob("*.sql")}
    listed = set(manifest.order)
    missing = sorted(listed - on_disk)
    unledgered = sorted(on_disk - listed)
    if missing or unledgered:
        raise ManifestError(
            "manifest and migrations directory disagree: "
            f"listed but missing on disk={missing}; on disk but not ledgered={unledgered}"
        )


# ID: df841458-9938-46ac-9e2d-4c537b12a369
def load_manifest(*, verify_disk: bool = True) -> Manifest:
    """Load and validate the repository manifest via :func:`load_policy`.

    With ``verify_disk`` (the default) the manifest is also checked against
    the migrations directory in both directions.
    """
    manifest = parse_manifest(load_policy())
    if verify_disk:
        if REPO_ROOT is None:
            raise ManifestError(
                "cannot verify the manifest against disk without a source tree"
            )
        verify_manifest_matches_disk(manifest, REPO_ROOT)
    return manifest
