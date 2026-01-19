# src/features/self_healing/alignment/specialists.py

"""Refactored logic for src/features/self_healing/alignment/specialists.py."""

from __future__ import annotations

import asyncio

from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response, parse_write_blocks


logger = getLogger(__name__)


# ID: db02b8db-97e9-4b1a-9f08-d49da0271b6d
class SpecialistDispatcher:
    def __init__(self, cognitive_service, symbol_finder):
        self.cognitive = cognitive_service
        self.symbol_finder = symbol_finder

    # ID: 3415c10d-1be1-4113-88db-9c3c57443219
    async def trigger_modularizer(self, file_path: str, write: bool) -> bool:
        """Agentic healing for God Objects."""
        logger.info("📐 God Object detected. Triggering Modularizer Specialist...")
        prompt_path = settings.paths.prompt("modularizer")
        template = await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")
        source_code = await asyncio.to_thread(
            (settings.REPO_PATH / file_path).read_text, encoding="utf-8"
        )

        final_prompt = template.format(
            file_path=file_path,
            current_lines=len(source_code.splitlines()),
            max_lines=400,
            source_code=source_code,
        )

        agent = await self.cognitive.aget_client_for_role("RefactoringArchitect")
        response = await agent.make_request_async(
            final_prompt, user_id="police_agent_modularizer"
        )

        blocks = parse_write_blocks(response)
        if not blocks:
            return False
        if write:
            for path, content in blocks.items():
                await asyncio.to_thread(
                    (settings.REPO_PATH / path).write_text, content, encoding="utf-8"
                )
                logger.info("📦 Modularizer: Created/Updated %s", path)
            return True
        return False

    # ID: 46794206-c8f9-4c68-b52b-f3bdb74620d7
    async def trigger_logic_repair(
        self, file_path: str, error_msg: str, write: bool
    ) -> bool:
        """Agentic healing for broken imports/drift."""
        logger.info("🧠 Logic drift detected. Triggering Logic Specialist...")
        hints = await self.symbol_finder.get_context_for_import_error(error_msg)
        prompt_path = settings.paths.prompt("logic_alignment")
        template = await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")
        source_code = await asyncio.to_thread(
            (settings.REPO_PATH / file_path).read_text, encoding="utf-8"
        )

        final_prompt = template.format(
            file_path=file_path,
            error_message=error_msg,
            symbol_hints=hints or "Use architectural standards.",
            source_code=source_code,
        )

        agent = await self.cognitive.aget_client_for_role("Coder")
        response = await agent.make_request_async(
            final_prompt, user_id="police_agent_logic"
        )
        fixed_code = extract_python_code_from_response(response)

        if fixed_code and write:
            await asyncio.to_thread(
                (settings.REPO_PATH / file_path).write_text,
                fixed_code,
                encoding="utf-8",
            )
            logger.info("🔧 Logic Specialist: Repaired imports in %s", file_path)
            return True
        return False

    # ID: b898a0d4-600e-437f-8a91-a787872b82e9
    async def trigger_generic_repair(
        self, file_path: str, violation: dict, write: bool
    ) -> bool:
        """Generic healing for violations not covered by specific handlers."""
        source_code = await asyncio.to_thread(
            (settings.REPO_PATH / file_path).read_text, encoding="utf-8"
        )
        prompt_path = settings.paths.prompt("logic_alignment")
        template = await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")

        violation_details = f"Rule: {violation.get('check_id')}\nSeverity: {violation.get('severity')}\nMessage: {violation.get('message')}\nLine: {violation.get('line_number', 'none')}"
        final_prompt = template.format(
            file_path=file_path,
            error_message=violation_details,
            symbol_hints="Search codebase for similar implementations.",
            source_code=source_code,
        )

        agent = await self.cognitive.aget_client_for_role("Coder")
        response = await agent.make_request_async(
            final_prompt, user_id="police_agent_generic"
        )
        fixed_code = extract_python_code_from_response(response)

        if fixed_code and write:
            await asyncio.to_thread(
                (settings.REPO_PATH / file_path).write_text,
                fixed_code,
                encoding="utf-8",
            )
            return True
        return False

    # ID: d199fc8c-45b6-445b-b879-7af3c38138cc
    async def heal_structural_clerk(
        self, file_path: str, task: str, write: bool
    ) -> bool:
        """Deterministic healing for metadata."""
        if not write:
            return False
        if task == "header":
            from features.self_healing.header_service import HeaderService

            await asyncio.to_thread(
                HeaderService()._fix, [str(settings.REPO_PATH / file_path)]
            )
            return True
        if task == "ids":
            from features.self_healing.id_tagging_service import assign_missing_ids

            await assign_missing_ids(
                context=None, write=False
            )  # Context handled by Registry
            return True
        return False
