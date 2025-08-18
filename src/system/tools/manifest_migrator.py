# src/system/tools/manifest_migrator.py
"""
Manifest Migrator / Validator

What it does (safe, self-contained):
1) Reads .intent/meta.yaml to discover constitutional paths.
2) Loads .intent/knowledge/source_structure.yaml to list domains.
3) Validates every manifest in .intent/manifests/ against .intent/schemas/manifest.schema.json.
4) Scaffolds any missing manifests with safe placeholders (capabilities: ["unassigned"]).
5) Detects duplicate capabilities across domains (and can fail on conflicts).
6) Optionally writes a drift report JSON (as defined in meta.yaml if present).

Run examples:
  python src/system/tools/manifest_migrator.py validate
  python src/system/tools/manifest_migrator.py scaffold
  python src/system/tools/manifest_migrator.py check-duplicates --fail-on-conflicts
  python src/system/tools/manifest_migrator.py all --fail-on-conflicts
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml  # PyYAML

try:
    from jsonschema import Draft7Validator
except Exception:  # pragma: no cover
    print(
        "ERROR: jsonschema is required. Please add `jsonschema` to your dependencies.",
        file=sys.stderr,
    )
    raise

# Optional niceties; if unavailable, we degrade gracefully.
try:
    from rich import box
    from rich.console import Console
    from rich.table import Table

    console = Console()
except Exception:  # pragma: no cover
    console = None
    Table = None
    box = None


# ---------- Utility: repo + constitution paths ----------


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Walk upward until a folder containing .intent/ is found."""
    here = (start or Path(__file__).resolve()).parent
    for p in [here] + list(here.parents):
        if (p / ".intent").exists():
            return p
    # Fallback: current working dir
    return Path.cwd()


REPO_ROOT = find_repo_root()
INTENT_DIR = REPO_ROOT / ".intent"
META_PATH = INTENT_DIR / "meta.yaml"

DEFAULT_SOURCE_STRUCTURE = "knowledge/source_structure.yaml"
DEFAULT_MANIFEST_SCHEMA = "schemas/manifest.schema.json"
DEFAULT_MANIFESTS_DIR = "manifests"
DEFAULT_DRIFT_REPORT = "reports/drift_report.json"


@dataclass
class Paths:
    source_structure: Path
    manifest_schema: Path
    manifests_dir: Path
    drift_report: Optional[Path]


def load_meta() -> Dict:
    if not META_PATH.exists():
        fail(f"Missing constitution index: {rel(META_PATH)}")
    meta = yaml.safe_load(META_PATH.read_text()) or {}

    # Knowledge
    knowledge = meta.get("knowledge", {})
    source_structure_rel = knowledge.get("source_structure", DEFAULT_SOURCE_STRUCTURE)

    # Schemas
    schemas = meta.get("schemas", {})
    manifest_schema_rel = schemas.get("manifest", DEFAULT_MANIFEST_SCHEMA)

    # Manifests dir
    manifests = meta.get("manifests", {})
    manifests_dir_rel = manifests.get("dir", DEFAULT_MANIFESTS_DIR)

    # Reports
    reports = meta.get("reports", {})
    drift_rel = reports.get("drift", DEFAULT_DRIFT_REPORT) if reports else None

    return {
        "source_structure": INTENT_DIR / source_structure_rel,
        "manifest_schema": INTENT_DIR / manifest_schema_rel,
        "manifests_dir": INTENT_DIR / manifests_dir_rel,
        "drift_report": (REPO_ROOT / drift_rel) if drift_rel else None,
    }


def load_paths() -> Paths:
    meta = load_meta()
    paths = Paths(
        source_structure=Path(meta["source_structure"]),
        manifest_schema=Path(meta["manifest_schema"]),
        manifests_dir=Path(meta["manifests_dir"]),
        drift_report=Path(meta["drift_report"]) if meta.get("drift_report") else None,
    )
    # Basic existence checks (manifests_dir may not exist yet)
    if not paths.source_structure.exists():
        fail(f"Missing knowledge map: {rel(paths.source_structure)}")
    if not paths.manifest_schema.exists():
        fail(f"Missing manifest schema: {rel(paths.manifest_schema)}")
    paths.manifests_dir.mkdir(parents=True, exist_ok=True)
    return paths


# ---------- Source structure parsing ----------


@dataclass
class DomainDef:
    name: str
    path: str
    enabled: bool
    description: str


def load_domains(source_structure_path: Path) -> List[DomainDef]:
    data = yaml.safe_load(source_structure_path.read_text()) or {}
    doms = []
    for entry in data.get("domains", []):
        name = entry.get("domain")
        if not name:
            # skip malformed
            continue
        doms.append(
            DomainDef(
                name=name,
                path=str(entry.get("path", "")),
                enabled=bool(entry.get("enabled", True)),
                description=str(entry.get("description", "")) or f"Domain {name}",
            )
        )
    return doms


# ---------- Manifest IO + validation ----------


def schema_validator(schema_path: Path) -> Draft7Validator:
    raw = json.loads(schema_path.read_text())
    return Draft7Validator(raw)


def manifest_path_for(domain: str, manifests_dir: Path) -> Path:
    return manifests_dir / f"{domain}.manifest.json"


def read_manifest(path: Path) -> Dict:
    try:
        return json.loads(path.read_text())
    except Exception as e:
        fail(f"Invalid JSON in {rel(path)}: {e}")


def write_manifest(path: Path, manifest: Dict) -> None:
    txt = json.dumps(manifest, indent=2, ensure_ascii=False)
    path.write_text(txt + "\n")


# ---------- Reporting helpers ----------


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except Exception:
        return str(p)


def info(msg: str) -> None:
    if console:
        console.print(f"[bold cyan]INFO[/] {msg}")
    else:
        print(f"INFO {msg}")


def warn(msg: str) -> None:
    if console:
        console.print(f"[bold yellow]WARN[/] {msg}")
    else:
        print(f"WARN {msg}")


def fail(msg: str, code: int = 1) -> None:
    if console:
        console.print(f"[bold red]ERROR[/] {msg}")
    else:
        print(f"ERROR {msg}", file=sys.stderr)
    sys.exit(code)


# ---------- Core actions ----------


def validate_manifests(
    paths: Paths, fail_on_error: bool = True
) -> Tuple[int, List[str]]:
    """Validate all manifests against the schema. Returns (#errors, error_messages)."""
    validator = schema_validator(paths.manifest_schema)
    errors = 0
    messages: List[str] = []

    domains = load_domains(paths.source_structure)
    for d in domains:
        mpath = manifest_path_for(d.name, paths.manifests_dir)
        if not mpath.exists():
            warn(f"Missing manifest for domain '{d.name}': {rel(mpath)}")
            errors += 1
            messages.append(f"missing: {d.name}")
            continue
        data = read_manifest(mpath)
        problems = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if problems:
            errors += len(problems)
            warn(f"Schema violations in {rel(mpath)}")
            for e in problems:
                loc = "/".join([str(x) for x in e.path]) or "(root)"
                msg = f"  - {loc}: {e.message}"
                messages.append(f"{d.name}: {msg}")
                if console:
                    console.print(f"[dim]{msg}[/]")
                else:
                    print(msg)
        else:
            info(f"OK: {rel(mpath)}")

    if errors and fail_on_error:
        fail(f"Validation failed with {errors} error(s).")
    return errors, messages


def scaffold_missing(paths: Paths) -> List[Path]:
    """Create minimal manifests for domains that don't have one yet."""
    created: List[Path] = []
    domains = load_domains(paths.source_structure)
    for d in domains:
        mpath = manifest_path_for(d.name, paths.manifests_dir)
        if mpath.exists():
            continue
        manifest = {
            "domain": d.name,
            "description": d.description or f"Domain {d.name}",
            "capabilities": [
                "unassigned"
            ],  # placeholder to satisfy schema (minItems: 1)
            "imports": [],  # optional; can be filled later
            "notes": "Scaffolded by manifest_migrator. Replace 'unassigned' with real capabilities.",
            "version": "0.1.0",
            "owners": [],
        }
        write_manifest(mpath, manifest)
        created.append(mpath)
        info(f"Scaffolded: {rel(mpath)}")
    if not created:
        info("No scaffolding needed. All manifests exist.")
    return created


def collect_capabilities(paths: Paths) -> Dict[str, List[str]]:
    """Return {domain: [capabilities...]} for all existing manifests (missing ones count as [])."""
    domains = load_domains(paths.source_structure)
    result: Dict[str, List[str]] = {}
    for d in domains:
        mpath = manifest_path_for(d.name, paths.manifests_dir)
        if not mpath.exists():
            result[d.name] = []
            continue
        m = read_manifest(mpath)
        caps = m.get("capabilities") or []
        # normalize to strings
        result[d.name] = [str(c) for c in caps if isinstance(c, (str, int))]
    return result


def find_duplicate_capabilities(cap_map: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Return {capability: [domains...]} for capabilities present in >1 domain."""
    reverse: Dict[str, List[str]] = {}
    for domain, caps in cap_map.items():
        for c in caps:
            reverse.setdefault(c, []).append(domain)
    return {cap: doms for cap, doms in reverse.items() if len(doms) > 1}


def check_duplicates(
    paths: Paths, fail_on_conflicts: bool = False
) -> Dict[str, List[str]]:
    cap_map = collect_capabilities(paths)
    dups = find_duplicate_capabilities(cap_map)

    if console and Table:
        table = Table(
            title="Duplicate Capabilities", box=box.SIMPLE_HEAVY if box else None
        )
        table.add_column("Capability")
        table.add_column("Domains")
        if dups:
            for cap, doms in sorted(dups.items()):
                table.add_row(cap, ", ".join(sorted(doms)))
        else:
            table.add_row("—", "No duplicates")
        console.print(table)
    else:
        if dups:
            print("Duplicate capabilities detected:")
            for cap, doms in sorted(dups.items()):
                print(f"  - {cap}: {', '.join(sorted(doms))}")
        else:
            print("No duplicate capabilities.")

    if dups and fail_on_conflicts:
        fail("Conflicting capabilities found across domains.", code=2)

    return dups


def write_drift_report(
    paths: Paths, validation_errors: List[str], duplicates: Dict[str, List[str]]
) -> Optional[Path]:
    if not paths.drift_report:
        return None
    report_path = paths.drift_report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "validation_errors": validation_errors,
        "duplicates": duplicates,
    }
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    info(f"Wrote drift report: {rel(report_path)}")
    return report_path


# ---------- CLI ----------


def parse_args(argv: List[str]) -> Tuple[str, Dict[str, bool]]:
    """
    Minimal arg parser (keeps dependencies light).
    Commands: validate | scaffold | check-duplicates | all
    Flags: --fail-on-conflicts
    """
    if not argv:
        return "all", {}
    cmd = argv[0]
    flags = {"fail-on-conflicts": False}
    for a in argv[1:]:
        if a == "--fail-on-conflicts":
            flags["fail-on-conflicts"] = True
    if cmd not in {"validate", "scaffold", "check-duplicates", "all"}:
        fail(
            f"Unknown command '{cmd}'. Use: validate | scaffold | check-duplicates | all"
        )
    return cmd, flags


def main(argv: Optional[List[str]] = None) -> None:
    cmd, flags = parse_args(argv or sys.argv[1:])
    paths = load_paths()

    # 1) Ensure manifests exist
    if cmd in {"scaffold", "all"}:
        scaffold_missing(paths)

    # 2) Validate
    validation_errors: List[str] = []
    if cmd in {"validate", "all"}:
        errors, messages = validate_manifests(paths, fail_on_error=False)
        validation_errors = messages
        if errors:
            warn(f"Validation found {errors} error(s).")

    # 3) Duplicates
    duplicates: Dict[str, List[str]] = {}
    if cmd in {"check-duplicates", "all"}:
        duplicates = check_duplicates(
            paths, fail_on_conflicts=flags.get("fail-on-conflicts", False)
        )

    # 4) Drift report (optional, only if path configured)
    write_drift_report(paths, validation_errors, duplicates)

    # Exit codes
    if validation_errors or duplicates:
        # Non-zero exit only if asked to fail on conflicts, or if there were schema errors.
        if validation_errors or flags.get("fail-on-conflicts"):
            sys.exit(1)

    # All good
    sys.exit(0)


if __name__ == "__main__":
    main()
