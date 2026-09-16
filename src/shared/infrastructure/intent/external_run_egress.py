# src/shared/infrastructure/intent/external_run_egress.py

"""Egress preflight for an externally bound run (#895 U3, ADR-159 §C).

The runner records which network destinations CORE is *configured* to reach
and refuses to start when any of them is outside the operator's
``--allowed-hosts``. It never claims to observe sockets: the coldroom's own
logs are the enforcement evidence. What it does guarantee is ordering --
the check runs BEFORE the seeding step, which is the first egress
(``probe_ollama_digest`` contacts the pinned model endpoint and the seed
actions write the isolated database), and again AFTER seeding against what
was actually registered (governor correction 1, 2026-09-16).

Every configured endpoint CORE knows about is covered:

- each seeded LLM resource's ``api_url`` (``llm_resources/*.yaml``), and
  after seeding the ``api_url`` of every row in ``core.llm_resources``;
- the isolated database (``DATABASE_URL`` -- host and port only, the URL
  carries a password and is never recorded);
- the policy-vector store (``QDRANT_URL``; bound empty for an external run
  per ruling C, recorded as ``unbound``).

Allowed-host entries are ``host`` or ``host:port``. A bare host allows any
port on that host; ``host:port`` allows exactly that port. Hostnames compare
case-insensitively.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit


ENDPOINT_UNBOUND = "unbound"


@dataclass(frozen=True)
# ID: a39e8e5b-6552-44e6-b2fe-721f138e2f35
class Endpoint:
    """A network destination CORE is configured to reach. Host and port only."""

    role: str  # llm_resource | database | vector_store
    name: str  # resource name, "DATABASE_URL", "QDRANT_URL"
    scheme: str | None
    host: str | None
    port: int | None
    source: str  # where the configuration was read from

    @property
    # ID: 0ec6266f-6c89-4d4e-bb70-2dcd4713969c
    def unbound(self) -> bool:
        return self.host is None

    # ID: 1281a6de-0649-4afc-b85e-800061f855cc
    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = ENDPOINT_UNBOUND if self.unbound else "configured"
        return payload


# ID: b3eb403c-e051-4c80-9136-2b603d5ac59d
def parse_allowed_hosts(values: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Normalize repeatable / comma-separated ``--allowed-hosts`` values.

    Entries are lower-cased, stripped, de-duplicated, order preserved.
    """
    seen: list[str] = []
    for value in values or ():
        for raw in str(value).split(","):
            entry = raw.strip().lower()
            if entry and entry not in seen:
                seen.append(entry)
    return tuple(seen)


def _split_entry(entry: str) -> tuple[str, int | None]:
    host, sep, port = entry.rpartition(":")
    if sep and port.isdigit() and host:
        return host.strip("[]"), int(port)
    return entry.strip("[]"), None


# ID: 1d073eb7-f2cf-4cdb-a5b0-27474021bc77
def endpoint_from_url(role: str, name: str, url: Any, *, source: str) -> Endpoint:
    """Host/port view of *url*; credentials, path and query are dropped."""
    if not isinstance(url, str) or not url.strip():
        return Endpoint(role, name, None, None, None, source)
    parts = urlsplit(url.strip())
    try:
        port = parts.port
    except ValueError:
        port = None
    return Endpoint(
        role,
        name,
        parts.scheme or None,
        parts.hostname.lower() if parts.hostname else None,
        port,
        source,
    )


# ID: 7ac7a355-b09c-4b82-8a2b-2bdcfc6f3244
def configured_endpoints(
    seed_resources: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    database_url: str | None,
    qdrant_url: str | None,
) -> list[Endpoint]:
    """Every destination the run is configured to reach, from its inputs."""
    endpoints = [
        endpoint_from_url(
            "llm_resource",
            str(resource.get("name")),
            resource.get("api_url"),
            source=f"seed:llm_resources/{resource.get('name')}.yaml::api_url",
        )
        for resource in sorted(seed_resources, key=lambda r: str(r.get("name")))
    ]
    endpoints.append(
        endpoint_from_url("database", "DATABASE_URL", database_url, source="env")
    )
    endpoints.append(
        endpoint_from_url("vector_store", "QDRANT_URL", qdrant_url, source="env")
    )
    return endpoints


# ID: 9edf5f38-000c-4380-bc27-1bdd8a2f6e22
def is_allowed(endpoint: Endpoint, allowed_hosts: tuple[str, ...]) -> bool:
    """An unbound endpoint reaches nothing and is always allowed."""
    if endpoint.unbound:
        return True
    for entry in allowed_hosts:
        host, port = _split_entry(entry)
        if host == endpoint.host and (port is None or port == endpoint.port):
            return True
    return False


# ID: 54534fdd-0fbb-4298-996c-7e8370c5b25c
def rejected_endpoints(
    endpoints: list[Endpoint], allowed_hosts: tuple[str, ...]
) -> list[Endpoint]:
    """Endpoints outside the allowed set. Empty allowed set rejects every bound one."""
    return [e for e in endpoints if not is_allowed(e, allowed_hosts)]
