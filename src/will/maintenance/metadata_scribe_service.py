# src/will/maintenance/metadata_scribe_service.py
# ID: 15a2b3c4-d5e6-7890-abcd-ef1234567815

"""
Metascribe Service - Will Layer.
Reasons about CLI command implementation to generate @command_meta decorators.
"""

from __future__ import annotations

import textwrap
from typing import Any

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

    # ID: 3ceb44a4-b67a-47b8-9c6c-4f4058ea2103
    async def draft_metadata(
        self, function_name: str, docstring: str, file_path: str, source_code: str
    ) -> dict[str, Any] | None:
        """
        Asks the AI Architect to classify a command based on its implementation.
        """
        prompt = textwrap.dedent(
            f"""
            Analyze the following CLI command function and determine its CORE constitutional metadata.

            FUNCTION NAME: {function_name}
            FILE PATH: {file_path}
            DOCSTRING: {docstring}

            CONTEXT:
            - CommandBehavior:
                'read' (Pure inspection/list/show, no state changes)
                'validate' (Audits/tests/checks that can fail, no state changes)
                'mutate' (Changes code, database, or vectors)
                'transform' (Data migrations, imports/exports)

            - CommandLayer:
                'mind' (Governance, law, .intent handling)
                'body' (Execution, infrastructure, mechanical tools)
                'will' (Agents, cognitive reasoning, autonomous loops)

            RULES:
            1. canonical_name must be 'resource.action' (e.g., 'symbols.sync').
            2. For hyphenated commands (fix-ids), the canonical name should be 'resource.action' (symbols.fix-ids).
            3. 'dangerous' must be true if behavior is 'mutate' or 'transform'.

            RESPONSE FORMAT (Strict JSON):
            {{
                "canonical_name": "string",
                "behavior": "read|validate|mutate|transform",
                "layer": "mind|body|will",
                "summary": "one sentence description starting with a capital letter",
                "dangerous": boolean
            }}

            CODE IMPLEMENTATION:
            ---
            {source_code[:3000]}
            ---
        """
        )

        try:
            # Use the Architect role for better structural reasoning
            agent = await self.cognitive.aget_client_for_role("RefactoringArchitect")
            response = await agent.make_request_async(
                prompt, user_id="metascribe_draft"
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
