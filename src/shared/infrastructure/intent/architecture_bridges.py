# src/shared/infrastructure/intent/architecture_bridges.py
"""
Architecture bridge declarations loader.

Provides queryable access to `.intent/architecture/bridges/` declarations
— constitutional records of data-flow bridge points where information
crosses CORE layer boundaries (issue #617).

Each bridge declares: bridge class, source layer/context, sink target,
attribution mechanism, and governing ADRs. This makes inter-layer data
flow queryable without grepping the source tree.

Authority: policy. Bridge declarations live under .intent/architecture/bridges/
and are accessed exclusively through this helper.

LAYER: shared/infrastructure/intent — pure helper. No imports from
will/, body/, or cli/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.infrastructure.intent.errors import GovernanceError
from shared.logger import getLogger


logger = getLogger(__name__)

_KIND = "architecture_bridge"


@dataclass(frozen=True)
# ID: 3a7f91d2-c841-4b6e-8de1-02e5a3f7bc49
class BridgeDeclaration:
    """Parsed representation of a single `.intent/architecture/bridges/*.yaml`."""

    id: str
    title: str
    description: str
    bridge_class: str
    bridge_layer: str
    source_layer: str
    source_context: str
    consuming_types: list[str]
    sink_target: str
    sink_layer: str
    sink_via: str
    attribution_mechanism: str
    attribution_field: str
    attribution_note: str
    authority_adrs: list[str]

    @classmethod
    # ID: 2f8b04c3-d951-4e7a-9af2-13d6c4e8a1b0
    def from_dict(cls, raw: dict[str, Any]) -> BridgeDeclaration:
        source = raw.get("source", {})
        sink = raw.get("sink", {})
        attribution = raw.get("attribution", {})
        return cls(
            id=raw.get("id", ""),
            title=raw.get("title", ""),
            description=(raw.get("description") or "").strip(),
            bridge_class=raw.get("bridge_class", ""),
            bridge_layer=raw.get("bridge_layer", ""),
            source_layer=source.get("layer", ""),
            source_context=(source.get("context") or "").strip(),
            consuming_types=list(source.get("consuming_types") or []),
            sink_target=sink.get("target", ""),
            sink_layer=sink.get("layer", ""),
            sink_via=sink.get("via", ""),
            attribution_mechanism=attribution.get("mechanism", ""),
            attribution_field=attribution.get("field", ""),
            attribution_note=(attribution.get("note") or "").strip(),
            authority_adrs=list(raw.get("authority_adrs") or []),
        )


# ID: 9e2a15b7-f463-4c8d-b3d0-7a1c5e9f0d82
def load_bridges() -> list[BridgeDeclaration]:
    """Return all declared architecture bridges from .intent/architecture/bridges/.

    Reads via IntentRepository.iter_documents() filtered to kind=architecture_bridge.
    Returns an empty list if the loader is unavailable (bootstrap / test context).
    """
    try:
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        repo = get_intent_repository()
        bridges: list[BridgeDeclaration] = []
        for _path, doc in repo.iter_documents(skip_components={"META"}):
            if not isinstance(doc, dict):
                continue
            if doc.get("kind") != _KIND:
                continue
            try:
                bridges.append(BridgeDeclaration.from_dict(doc))
            except Exception as exc:
                logger.warning(
                    "architecture_bridges: skipping malformed bridge: %s", exc
                )
        return bridges
    except GovernanceError:
        raise
    except Exception as exc:
        logger.warning("architecture_bridges: could not load bridges (%s).", exc)
        return []


# ID: 7c3d28e6-a17b-4f59-a9e0-6b4d2c8e5f1a
def bridges_consuming(type_name: str) -> list[BridgeDeclaration]:
    """Return bridges whose source.consuming_types includes the given type name."""
    return [b for b in load_bridges() if type_name in b.consuming_types]
