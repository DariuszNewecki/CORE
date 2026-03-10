# src/will/maintenance/metadata_scribe_service.py

"""
Metascribe Service - Will Layer.
Reasons about CLI command implementation to generate @command_meta decorators.
"""

from __future__ import annotations

from typing import Any

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response


logger = getLogger(__name__)


# ID: 52a1c0d3-fb4a-463d-8896-138a623a8304
class MetadataScribeService:
    """
    AI specialist that drafts constitutional metadata for CLI commands.
    """

    def __init__(self, cognitive_service: Any):
        self.cognitive = cognitive_service
        self.draft_metadata_model = PromptModel.load(
            "src_maintenance_metadata_scribe_service_draft_metadata"
        )

    # ID: 3ceb44a4-b67a-47b8-9c6c-4f4058ea2103
    async def draft_metadata(
        self, function_name: str, docstring: str, file_path: str, source_code: str
    ) -> dict[str, Any] | None:
        """
        Asks the AI Architect to classify a command based on its implementation.
        """
        try:
            # Use the Architect role for better structural reasoning
            agent = await self.cognitive.aget_client_for_role("RefactoringArchitect")

            context = {
                "function_name": function_name,
                "file_path": file_path,
                "docstring": docstring,
                "source_code": source_code[:3000],
            }

            response = await self.draft_metadata_model.invoke(
                context=context, client=agent, user_id="metascribe_draft"
            )

            meta = extract_json_from_response(response)
            if isinstance(meta, dict) and "canonical_name" in meta:
                return meta
            return None
        except Exception as e:
            logger.error(
                "Metascribe failed to draft metadata for %s: %s", function_name, e
            )
            return None
