# src/body/cli/logic/diagnostics.py
"""
Logic layer for CLI diagnostics commands.

Rules:
- No Rich / Typer UI rendering here (command layer owns presentation).
- Pure, testable functions where possible.
- Defensive behavior: never crash CLI because of unexpected Typer internals.
"""

from __future__ import annotations

from typing import Any, Protocol

from shared.context import CoreContext
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger


logger = getLogger(__name__)


# --- Typer Introspection Protocols (minimal surface; avoids import cycles) ---


# ID: 2c0a9d7b-6f2c-4c2b-a4d0-8d0d53c3b2a1
class TyperCommandLike(Protocol):
    name: str | None
    help: str | None


# ID: 9bd4d6a1-4f2d-4f5f-9f4b-7c0a6e3b1b90
class TyperGroupLike(Protocol):
    name: str | None
    typer_instance: Any


# ID: 5b0f1a6e-2c18-4b87-9f5f-0b1e6c3e7a12
class TyperAppLike(Protocol):
    registered_commands: list[TyperCommandLike]
    registered_groups: list[TyperGroupLike]


# ID: 3c7a1c34-8b36-4d2e-9b2b-3c94b7a8bb12
def build_cli_tree_data(app: TyperAppLike) -> list[dict[str, Any]]:
    """
    Build a hierarchical representation of a Typer CLI app.
    """

    def _summary(help_text: str | None) -> str:
        if not help_text:
            return ""
        return help_text.splitlines()[0].strip()

    def _walk(node_app: TyperAppLike) -> list[dict[str, Any]]:
        children: list[dict[str, Any]] = []

        try:
            groups = list(getattr(node_app, "registered_groups", []) or [])
        except Exception:
            groups = []

        for grp in groups:
            name = getattr(grp, "name", None)
            sub_app = getattr(grp, "typer_instance", None)
            if not name or sub_app is None:
                continue

            group_node: dict[str, Any] = {"name": str(name)}
            grp_help = getattr(grp, "help", None)
            if grp_help:
                group_node["help"] = _summary(str(grp_help))

            sub_children = _walk(sub_app)
            if sub_children:
                group_node["children"] = sub_children

            children.append(group_node)

        try:
            commands = list(getattr(node_app, "registered_commands", []) or [])
        except Exception:
            commands = []

        for cmd in commands:
            name = getattr(cmd, "name", None)
            if not name:
                continue
            cmd_node: dict[str, Any] = {"name": str(name)}
            cmd_help = getattr(cmd, "help", None)
            if cmd_help:
                cmd_node["help"] = _summary(str(cmd_help))
            children.append(cmd_node)

        def _sort_key(n: dict[str, Any]) -> tuple[int, str]:
            is_leaf = 0 if "children" in n else 1
            return (is_leaf, n.get("name", ""))

        return sorted(children, key=_sort_key)

    return _walk(app)


# ID: e9d2a1f3-5c4b-8a7e-9f1d-2b3c4d5e6f7a
async def get_unassigned_symbols_logic(
    core_context: CoreContext,
) -> list[dict[str, Any]]:
    """
    Get symbols that have not been assigned a capability ID.
    """
    try:
        knowledge_service = KnowledgeService(core_context.git_service.repo_path)
        graph = await knowledge_service.get_graph()
        symbols = graph.get("symbols", {})

        unassigned = []
        for key, symbol_data in symbols.items():
            name = symbol_data.get("name")
            if name is None:
                continue

            if name.startswith("_"):
                continue

            file_path = symbol_data.get("file_path", "")
            if "tests/" in file_path or "/test" in file_path:
                continue

            if symbol_data.get("capability") == "unassigned":
                symbol_data["key"] = key
                unassigned.append(symbol_data)

        return unassigned
    except Exception as e:
        logger.error("Error processing knowledge graph: %s", e)
        return []


# ID: 5086836c-c833-4099-a6da-2522eda85ec3
def list_constitutional_files_logic() -> list[str]:
    """
    Returns the list of constitutional files discovered by the IntentRepository.
    """
    logger.info("Retrieving indexed constitutional files from IntentRepository...")

    repo = get_intent_repository()
    repo.initialize()  # Ensure current state is indexed

    # 1. Collect all indexed policy and standard files
    paths = [str(ref.path) for ref in repo.list_policies()]

    # 2. Add structural META files (The "Contract" files)
    # Using repo.root instead of settings.MIND to stay repo-local
    core_structure = [
        repo.root / "META" / "intent_tree.schema.json",
        repo.root / "META" / "rule_document.schema.json",
        repo.root / "META" / "enums.json",
        repo.root / "constitution" / "precedence_rules.yaml",
    ]

    for cf in core_structure:
        if cf.exists():
            paths.append(str(cf))

    return sorted(list(set(paths)))
