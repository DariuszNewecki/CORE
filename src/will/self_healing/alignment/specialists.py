# src/features/self_healing/alignment/specialists.py

"""Refactored logic for src/features/self_healing/alignment/specialists.py."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response, parse_write_blocks


if TYPE_CHECKING:
    from shared.infrastructure.config_service import ConfigService

logger = getLogger(__name__)


# ID: db02b8db-97e9-4b1a-9f08-d49da0271b6d
class SpecialistDispatcher:
    def __init__(self, cognitive_service, symbol_finder, config_service: ConfigService):
        self.cognitive = cognitive_service
        self.symbol_finder = symbol_finder
        self.config_service = config_service

    async def _repo_root(self) -> Path:
        return Path(await self.config_service.get("REPO_PATH", required=True))

    async def _prompt_path(self, prompt_name: str) -> Path:
        repo_root = await self._repo_root()
        safe = prompt_name.strip().replace("\\", "/").split("/")[-1]
        return repo_root / "var" / "prompts" / f"{safe}.prompt"

    # ID: 3415c10d-1be1-4113-88db-9c3c57443219
    async def trigger_modularizer(self, file_path: str, write: bool) -> bool:
        """Agentic healing for God Objects."""
        logger.info("📐 God Object detected. Triggering Modularizer Specialist...")
        repo_root = await self._repo_root()
        prompt_path = await self._prompt_path("modularizer")
        template = await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")
        source_code = await asyncio.to_thread(
            (repo_root / file_path).read_text, encoding="utf-8"
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
                    (repo_root / path).write_text, content, encoding="utf-8"
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
        repo_root = await self._repo_root()
        hints = await self.symbol_finder.get_context_for_import_error(error_msg)
        prompt_path = await self._prompt_path("logic_alignment")
        template = await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")
        source_code = await asyncio.to_thread(
            (repo_root / file_path).read_text, encoding="utf-8"
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
                (repo_root / file_path).write_text,
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
        repo_root = await self._repo_root()
        source_code = await asyncio.to_thread(
            (repo_root / file_path).read_text, encoding="utf-8"
        )
        prompt_path = await self._prompt_path("logic_alignment")
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
                (repo_root / file_path).write_text,
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
        repo_root = await self._repo_root()
        if not write:
            return False
        if task == "header":
            from body.self_healing.header_service import HeaderService

            await asyncio.to_thread(
                HeaderService(repo_root=repo_root)._fix,
                [str(repo_root / file_path)],
            )
            return True
        if task == "ids":
            from body.self_healing.id_tagging_service import assign_missing_ids

            await assign_missing_ids(
                context=None, write=False
            )  # Context handled by Registry
            return True
        return False
