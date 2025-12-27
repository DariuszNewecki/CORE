# src/features/self_healing/test_generation/context_builder.py
"""
ContextPackageBuilder

Responsible for building ContextPackage and converting it into ModuleContext.
"""

from __future__ import annotations

import ast
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from features.self_healing.test_context_analyzer import ModuleContext
from shared.config import settings
from shared.infrastructure.context import ContextBuilder
from shared.infrastructure.context.providers import (
    ASTProvider,
    DBProvider,
    VectorProvider,
)
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 230dbdcb-b444-4078-8241-094f785b6e85
class ContextPackageBuilder:
    """Builds ContextPackage → ModuleContext."""

    # ID: d047b64c-e60b-4ed2-9a88-231107db4046
    async def build(self, session: AsyncSession, module_path: str) -> ModuleContext:
        """
        Build Packet → Convert to ModuleContext

        Args:
            session: Database session (injected dependency)
            module_path: Path to module to analyze
        """
        full_path = settings.REPO_PATH / module_path
        source = full_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # determine target functions
        target_funcs = [
            n.name
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")
        ]

        # Build task spec
        module_name = (
            module_path.replace("src/", "").replace(".py", "").replace("/", ".")
        )
        task_id = f"test_gen_{module_path.replace('/', '_')}"

        task_spec = {
            "task_id": task_id,
            "task_type": "test.generate",
            "target_file": module_path,
            "target_symbol": target_funcs[0] if target_funcs else None,
            "summary": f"Generate tests for {module_path}",
            "scope": {
                "include": [module_name],
                "exclude": ["tests/*", "*.pyc"],
                "roots": [module_name.split(".")[0]],
            },
            "constraints": {"max_tokens": 50000, "max_items": 30},
        }

        # Build packet with injected session
        dbp = DBProvider(db_service=session)
        astp = ASTProvider(project_root=str(settings.REPO_PATH))
        vecp = VectorProvider()
        builder = ContextBuilder(
            db_provider=dbp,
            vector_provider=vecp,
            ast_provider=astp,
            config={"max_tokens": 50000, "max_context_items": 30},
        )
        packet = await builder.build_for_task(task_spec)

        return self._packet_to_context(packet, module_path, source, tree)

    def _packet_to_context(
        self,
        packet: dict,
        module_path: str,
        source_code: str,
        tree: ast.AST,
    ) -> ModuleContext:
        """
        Convert ContextPackage to ModuleContext
        """
        items = packet.get("context", [])
        functions = []

        for item in items:
            if item.get("item_type") in ("code", "symbol"):
                content = item.get("content", "")
                name = item.get("name", "")
                functions.append(
                    {
                        "name": name,
                        "docstring": item.get("summary", ""),
                        "is_private": name.startswith("_"),
                        "is_async": "async def" in content,
                        "args": [],
                        "code": content,
                    }
                )

        return ModuleContext(
            module_path=module_path,
            module_name=Path(module_path).stem,
            import_path=module_path.replace("src/", "")
            .replace(".py", "")
            .replace("/", "."),
            source_code=source_code,
            module_docstring=ast.get_docstring(tree),
            classes=[],
            functions=functions,
            imports=[],
            dependencies=[],
            current_coverage=0.0,
            uncovered_lines=[],
            uncovered_functions=[f["name"] for f in functions],
            similar_test_files=[],
            external_deps=[],
            filesystem_usage=False,
            database_usage=False,
            network_usage=False,
        )
