# src/shared/infrastructure/intent/external_run_seed.py
"""
External-run seed document: what the operator supplies so an isolated
external run can plan (#894 seeding unit; Governor rulings 2026-09-15 A/D/E).

One Mind stays intact: the execution copy's own machinery-floor taxonomy
defines ROLES (projected by ``project.cognitive_roles``); the runner
supplies its own planner PROMPT (a materialization layer); the OPERATOR
supplies runtime resources through this document. Nothing here reads
CORE's live database, CORE's ``.intent/`` or Qdrant.

Seed directory layout (all YAML)::

    <seed>/llm_resources/<name>.yaml   -- one llm_resources definition each,
                                          the shape ``author.llm_resource``
                                          validates; may carry ``model_digest``
    <seed>/assignments.yaml            -- {assignments: [{role, resource,
                                          priority, is_active}]}
    <seed>/system_config.yaml          -- {operating_mode, llm_enabled}

This module is pure: it parses, validates the CLOSED field sets, computes
the deterministic manifest and ``seed_hash``, and states refusals. Writing
is the ``seed.external_run_resources`` atomic action's job; the network
digest probe is a small explicit function the action calls.

Refusals (fail closed, every one a distinct reason):
- unreadable/missing document or unknown top-level key (closed fields);
- an assignment naming a resource the document does not define;
- ``system_config.llm_enabled`` false, or ``operating_mode`` outside the
  closed vocabulary;
- a resource whose ``locality`` the seeded ``operating_mode`` excludes;
- zero resources providing a required capability, or MORE THAN ONE
  qualified resource with no explicit assignment (ambiguous -- the
  capability-score fallback is not deterministic across seeds);
- a ``locality: remote`` resource (needs a secret this document never
  carries) unless an explicit ``secret_present`` acknowledgement is given
  by the caller; and, at probe time, a pinned ``model_digest`` the endpoint
  does not report for ``model_name``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.exceptions import CoreError


_DISPOSABLE_DB_NAME_RE = re.compile(r"^core_unitd_[0-9a-f]{16}$")
_PRODUCTION_DB_NAMES = frozenset(
    {"core", "core_test", "postgres", "template0", "template1"}
)

_OPERATING_MODES = frozenset({"local_only", "hybrid", "remote_only"})
_LOCALITY_BY_MODE: dict[str, frozenset[str]] = {
    "local_only": frozenset({"local"}),
    "remote_only": frozenset({"remote"}),
    "hybrid": frozenset({"local", "remote"}),
}
_ASSIGNMENT_FIELDS = frozenset({"role", "resource", "priority", "is_active"})
_SYSTEM_CONFIG_FIELDS = frozenset({"operating_mode", "llm_enabled"})


# ID: efb38102-c9fe-4f87-85dd-6d88ca63cc13
class SeedError(CoreError):
    """The seed document cannot be applied; the message names the refusal."""


# ID: 12d8c84d-4384-44f9-880a-a11bf96c8483
def validate_isolated_database_name(name: str) -> None:
    """Defence in depth for the isolation proof: refuse any production or
    non-disposable-shaped name. The PRIMARY proof is that the connected
    database's ``current_database()`` equals the run-specific name the
    apparatus supplied -- checked by the writer action on its own
    connection; this function only rules out the names that must never be
    seeded regardless."""
    if name in _PRODUCTION_DB_NAMES:
        raise SeedError(f"refusing to seed a production database: {name!r}")
    if not _DISPOSABLE_DB_NAME_RE.fullmatch(name):
        raise SeedError(
            f"refusing to seed a non-disposable-shaped database name: {name!r} "
            "(expected core_unitd_<16 hex>)"
        )


@dataclass(frozen=True)
# ID: 18c242bd-2ddb-467b-9c63-e2054dbc2cc2
class SeedDocument:
    """Parsed, closed-field seed content (validated against the taxonomy by the
    writer; this dataclass only guarantees shape and internal consistency)."""

    resources: tuple[dict[str, Any], ...]
    assignments: tuple[dict[str, Any], ...]
    system_config: dict[str, Any]
    source_dir: Path
    file_hashes: dict[str, str] = field(default_factory=dict)

    # ID: 74a66669-b6c4-4b05-83f2-8e9319d5a997
    def resource(self, name: str) -> dict[str, Any] | None:
        return next((r for r in self.resources if r.get("name") == name), None)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_yaml(path: Path) -> Any:
    import yaml

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SeedError(f"seed document missing: {path}")
    except Exception as exc:  # yaml errors are many; the reason is what matters
        raise SeedError(
            f"seed document unreadable: {path} ({type(exc).__name__}: {exc})"
        )


# ID: fbca3776-255e-476e-a844-354910513820
def load_seed_document(seed_dir: Path) -> SeedDocument:
    """Parse and shape-check a seed directory. Raises :class:`SeedError`."""
    seed_dir = Path(seed_dir)
    if not seed_dir.is_dir():
        raise SeedError(f"seed directory not found: {seed_dir}")
    hashes: dict[str, str] = {}

    res_dir = seed_dir / "llm_resources"
    res_files = sorted(res_dir.glob("*.yaml")) if res_dir.is_dir() else []
    if not res_files:
        raise SeedError(
            f"seed defines no llm_resources (expected {res_dir}/<name>.yaml)"
        )
    resources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for f in res_files:
        doc = _load_yaml(f)
        if not isinstance(doc, dict) or not isinstance(doc.get("name"), str):
            raise SeedError(
                f"llm_resources definition must be a mapping with a name: {f}"
            )
        if doc["name"] in seen:
            raise SeedError(f"duplicate llm_resources definition for {doc['name']!r}")
        seen.add(doc["name"])
        resources.append(doc)
        hashes[f"llm_resources/{f.name}"] = _sha256_bytes(f.read_bytes())

    a_path = seed_dir / "assignments.yaml"
    a_doc = _load_yaml(a_path)
    if not isinstance(a_doc, dict) or set(a_doc) != {"assignments"}:
        raise SeedError("assignments.yaml must contain exactly one key: assignments")
    assignments: list[dict[str, Any]] = []
    for i, a in enumerate(a_doc["assignments"] or []):
        if not isinstance(a, dict) or set(a) != _ASSIGNMENT_FIELDS:
            raise SeedError(
                f"assignments[{i}] must have exactly the fields "
                f"{sorted(_ASSIGNMENT_FIELDS)} (closed set)"
            )
        if a["resource"] not in seen:
            raise SeedError(
                f"assignments[{i}] names resource {a['resource']!r} the seed does not define"
            )
        if not isinstance(a["priority"], int) or a["priority"] < 1:
            raise SeedError(f"assignments[{i}].priority must be a positive integer")
        if not isinstance(a["is_active"], bool):
            raise SeedError(f"assignments[{i}].is_active must be a boolean")
        assignments.append(dict(a))
    hashes["assignments.yaml"] = _sha256_bytes(a_path.read_bytes())

    s_path = seed_dir / "system_config.yaml"
    s_doc = _load_yaml(s_path)
    if not isinstance(s_doc, dict) or set(s_doc) != _SYSTEM_CONFIG_FIELDS:
        raise SeedError(
            f"system_config.yaml must have exactly the fields "
            f"{sorted(_SYSTEM_CONFIG_FIELDS)} (closed set)"
        )
    if s_doc["operating_mode"] not in _OPERATING_MODES:
        raise SeedError(
            f"system_config.operating_mode {s_doc['operating_mode']!r} not in "
            f"{sorted(_OPERATING_MODES)}"
        )
    if s_doc["llm_enabled"] is not True:
        raise SeedError("system_config.llm_enabled must be true for an external run")
    hashes["system_config.yaml"] = _sha256_bytes(s_path.read_bytes())

    return SeedDocument(
        resources=tuple(resources),
        assignments=tuple(assignments),
        system_config=dict(s_doc),
        source_dir=seed_dir,
        file_hashes=hashes,
    )


# ID: d6ffe0e1-e96c-4c82-82d9-d6c5bb4c9aaa
def check_seed_serves_roles(
    seed: SeedDocument,
    required_capabilities_by_role: dict[str, frozenset[str]],
    *,
    secret_present: frozenset[str] = frozenset(),
) -> None:
    """Refuse a seed that cannot deterministically serve every required role.

    *required_capabilities_by_role* is what the execution copy's taxonomy
    declares for the roles the run needs (``{"Planner": {"planning"}}``).
    *secret_present* names resources whose remote secret the caller has
    verified exists in the isolated secret store; any other remote resource
    is refused here because this document never carries secrets.
    """
    mode = seed.system_config["operating_mode"]
    allowed_localities = _LOCALITY_BY_MODE[mode]
    for r in seed.resources:
        locality = r.get("locality", "local")
        if locality not in allowed_localities:
            raise SeedError(
                f"resource {r['name']!r} has locality {locality!r}, excluded by "
                f"operating_mode {mode!r}"
            )
        if locality == "remote" and r["name"] not in secret_present:
            raise SeedError(
                f"remote resource {r['name']!r} needs an api key the seed document "
                "never carries; none is present in the isolated secret store"
            )
        if r.get("is_available", True) is not True:
            raise SeedError(f"resource {r['name']!r} is not is_available: true")
    for role, caps in sorted(required_capabilities_by_role.items()):
        explicit = [a for a in seed.assignments if a["role"] == role and a["is_active"]]
        if explicit:
            top = min(a["priority"] for a in explicit)
            if sum(1 for a in explicit if a["priority"] == top) > 1:
                raise SeedError(
                    f"role {role!r} has more than one active priority-{top} assignment"
                )
            continue
        qualified = [
            r["name"]
            for r in seed.resources
            if caps <= frozenset(r.get("provided_capabilities") or [])
        ]
        if not qualified:
            raise SeedError(
                f"no seeded resource provides {sorted(caps)} for role {role!r} and no "
                "assignment names one"
            )
        if len(qualified) > 1:
            raise SeedError(
                f"ambiguous: {len(qualified)} seeded resources qualify for role {role!r} "
                f"({', '.join(sorted(qualified))}) and no assignment picks one"
            )


# ID: 8687d69c-63db-4287-a6a7-a6af70253c70
def seed_manifest(
    seed: SeedDocument,
    *,
    verified_digests: dict[str, str],
    prompts: list[dict[str, Any]],
    roles: list[dict[str, Any]],
) -> dict[str, Any]:
    """The deterministic record of everything seeded (sorted keys, JSON-able)."""
    return {
        "resources": [
            {
                "name": r["name"],
                "model_name": r.get("model_name"),
                "locality": r.get("locality", "local"),
                "api_url_host": _host_of(r.get("api_url")),
                "pinned_digest": r.get("model_digest"),
                "verified_digest": verified_digests.get(r["name"]),
                "definition_sha256": seed.file_hashes.get(
                    f"llm_resources/{r['name']}.yaml"
                ),
            }
            for r in sorted(seed.resources, key=lambda r: r["name"])
        ],
        "assignments": sorted(
            (dict(a) for a in seed.assignments),
            key=lambda a: (a["role"], a["priority"], a["resource"]),
        ),
        "system_config": dict(sorted(seed.system_config.items())),
        "prompts": sorted(prompts, key=lambda p: p["id"]),
        "roles": sorted(roles, key=lambda r: r["role"]),
        "seed_files": dict(sorted(seed.file_hashes.items())),
    }


# ID: 64b3f5a4-06c7-424d-8843-396987a311b6
def seed_hash(manifest: dict[str, Any]) -> str:
    """Canonical SHA-256 of a manifest (sorted keys, compact separators)."""
    text = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return _sha256_bytes(text.encode("utf-8"))


def _host_of(url: Any) -> str | None:
    if not isinstance(url, str) or not url:
        return None
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    return parts.hostname


# ID: 49f73174-e05c-40fa-87bb-ffef3f649fe5
def probe_ollama_digest(
    api_url: str, model_name: str, *, timeout_sec: float = 10.0
) -> str | None:
    """Return the digest the Ollama endpoint reports for *model_name*, or None
    when the model is absent. Raises :class:`SeedError` when the endpoint is
    unreachable. The only network call in the seeding path, and it goes to
    the pinned endpoint the seed itself names."""
    import httpx

    base = api_url.rstrip("/")
    try:
        response = httpx.get(f"{base}/api/tags", timeout=timeout_sec)
        response.raise_for_status()
    except Exception as exc:
        raise SeedError(
            f"pinned endpoint {base} unreachable for digest verification: {exc}"
        )
    for model in response.json().get("models", []):
        if model.get("name") == model_name or model.get("model") == model_name:
            return str(model.get("digest") or "") or None
    return None
