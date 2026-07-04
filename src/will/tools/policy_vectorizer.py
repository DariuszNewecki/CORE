# src/will/tools/policy_vectorizer.py
"""Policy vectorizer — PolicyVectorizer re-exported from shared.tools per ADR-063.

CLI functions (vectorize_policies_command, run_as_script) remain here because they
directly instantiate CognitiveService, which is a will-layer service.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.tools.policy_vectorizer import PolicyVectorizer
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)

# RUF006: persistent task registry prevents GC of running tasks
_RUNNING_TASKS: set[asyncio.Task] = set()

__all__ = ["PolicyVectorizer", "run_as_script", "vectorize_policies_command"]


# ID: 64c63d13-45c0-4ef5-9001-42703a6158a6
async def vectorize_policies_command(repo_root: Path) -> dict[str, Any]:
    """CLI command wrapper for policy vectorization."""
    qdrant_service = QdrantService()
    cognitive_service = CognitiveService(
        repo_path=repo_root, qdrant_service=qdrant_service
    )
    await cognitive_service.initialize()  # type: ignore[call-arg]

    vectorizer = PolicyVectorizer(repo_root, cognitive_service, qdrant_service)
    return await vectorizer.vectorize_all_policies()


# ID: 5ccf49ce-779c-443a-b03b-188d77602a90
def run_as_script():
    """Constitutional entry point for standalone execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Vectorize constitutional policies into Qdrant."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Path to the CORE repository root.",
    )

    args = parser.parse_args()

    async def _main() -> None:
        try:
            result = await vectorize_policies_command(args.repo_root)
            logger.info(
                "Success! Vectorized %s policies.", result.get("policies_vectorized", 0)
            )
        except Exception as e:
            logger.error("Vectorization failed: %s", e)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        task = asyncio.create_task(_main())
        _RUNNING_TASKS.add(task)
        task.add_done_callback(_RUNNING_TASKS.discard)
    else:
        asyncio.run(_main())


if __name__ == "__main__":
    run_as_script()
