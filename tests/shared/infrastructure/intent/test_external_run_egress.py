# tests/shared/infrastructure/intent/test_external_run_egress.py

"""Egress preflight primitives (#895 U3, ADR-159 §C): host/port views of the
configured destinations, never credentials; allowed-host matching."""

from __future__ import annotations

from shared.infrastructure.intent.external_run_egress import (
    Endpoint,
    configured_endpoints,
    endpoint_from_url,
    is_allowed,
    rejected_endpoints,
)


def test_endpoint_from_url_drops_credentials_path_and_query() -> None:
    ep = endpoint_from_url(
        "database",
        "DATABASE_URL",
        "postgresql+asyncpg://user:s3cret@db.local:5433/core?x=1",
        source="env",
    )
    assert (ep.host, ep.port, ep.scheme) == ("db.local", 5433, "postgresql+asyncpg")
    payload = ep.to_payload()
    assert "s3cret" not in str(payload) and "user" not in str(payload)
    assert payload["status"] == "configured"


def test_empty_url_is_unbound() -> None:
    ep = endpoint_from_url("vector_store", "QDRANT_URL", "", source="env")
    assert ep.unbound and ep.to_payload()["status"] == "unbound"
    assert is_allowed(ep, ())  # reaches nothing, always allowed


def test_configured_endpoints_covers_every_input() -> None:
    eps = configured_endpoints(
        [
            {"name": "b", "api_url": "http://10.0.0.2:11434"},
            {"name": "a", "api_url": "http://10.0.0.1:11434"},
        ],
        database_url="postgresql://u:p@10.0.0.9:5432/db",
        qdrant_url="",
    )
    assert [(e.role, e.name, e.host, e.port) for e in eps] == [
        ("llm_resource", "a", "10.0.0.1", 11434),
        ("llm_resource", "b", "10.0.0.2", 11434),
        ("database", "DATABASE_URL", "10.0.0.9", 5432),
        ("vector_store", "QDRANT_URL", None, None),
    ]


def test_allowed_matching_host_and_host_port() -> None:
    ep = Endpoint("llm_resource", "a", "http", "10.0.0.1", 11434, "seed")
    assert is_allowed(ep, ("10.0.0.1",))
    assert is_allowed(ep, ("10.0.0.1:11434",))
    assert not is_allowed(ep, ("10.0.0.1:11435",))
    assert not is_allowed(ep, ("10.0.0.2",))
    assert not is_allowed(ep, ())  # enforced with an empty set rejects everything bound


def test_rejected_endpoints_lists_only_outsiders() -> None:
    eps = configured_endpoints(
        [{"name": "a", "api_url": "http://10.0.0.1:11434"}],
        database_url="postgresql://u:p@10.0.0.9:5432/db",
        qdrant_url="",
    )
    assert [e.name for e in rejected_endpoints(eps, ("10.0.0.1",))] == ["DATABASE_URL"]
    assert rejected_endpoints(eps, ("10.0.0.1", "10.0.0.9:5432")) == []
