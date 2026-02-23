# src/body/cli/logic/body_contracts_fixer.py
# ID: bea4d40b-5ab4-4925-ad4d-bc3cb448bd95

"""Headless fixer for Body-layer contract violations."""

from __future__ import annotations

import textwrap
import time
from pathlib import Path

# CONSTITUTIONAL FIX: Import TYPE_CHECKING and Any
from typing import TYPE_CHECKING, Any

from cli.logic.body_contracts_checker import check_body_contracts
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor


if TYPE_CHECKING:
    from shared.context import CoreContext
    from shared.infrastructure.storage.file_handler import FileHandler

logger = getLogger(__name__)

_BODY_UI_FIX_PROMPT = textwrap.dedent(
    "\n    You are refactoring Python code for a constitutional system called CORE.\n\n    GOAL\n    ----\n    - Remove ALL terminal UI from the given module:\n      - No Rich imports or usage\n      - No console.print() or input()\n      - No direct os.environ / os.environ[...] access\n    - Preserve the module's behavior as a HEADLESS Body-layer service/logic.\n\n    CONTEXT\n    -------\n    CORE governance rules for Body code:\n    - Body modules MUST be headless:\n      - No Rich UI (Console, Progress, status, etc.)\n      - No console.print() / input() calls\n    - Configuration must come from shared.config.settings, not os.environ.\n    - Logging MUST use shared.logger.getLogger(__name__).\n\n    REQUIREMENTS\n    ------------\n    1. Remove or refactor any Rich / console imports and usage.\n       - If the module needs observability, use logger.debug/info/warning/error.\n    2. Remove or refactor console.print() / input() calls.\n       - Replace with logger.info/debug where appropriate, or return values.\n    3. Replace os.environ[...] or os.environ.get(...) with settings access\n       (e.g., shared.config.settings or an injected config object) when possible.\n       If you cannot infer an exact mapping, keep a FUTURE comment but do NOT\n       keep direct os.environ in the Body module.\n    4. DO NOT change public function signatures unless absolutely necessary.\n    5. DO NOT introduce any new UI dependencies.\n\n    OUTPUT FORMAT\n    -------------\n    Return ONLY the full corrected Python module.\n    DO NOT wrap it in backticks, comments, or explanation.\n    "
)


async def _process_single_file(
    item: tuple[Path, list[dict[str, Any]]],
    agent: Any,
    write: bool,
    file_handler: FileHandler,
) -> dict[str, Any]:
    """
    Worker function to process a single file.
    """
    path, vlist = item
    logger.info("Processing %s...", path.name)
    try:
        original_source = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Body UI fixer: cannot read %s: %s", path, e)
        return {
            "path": str(path),
            "had_violations": True,
            "modified": False,
            "error": f"read_error: {e}",
        }

    summary_lines = sorted(
        {f"- {v['rule_id']} @ line {v.get('line')}: {v['message']}" for v in vlist}
    )
    violation_summary = "\n".join(summary_lines)
    prompt = (
        _BODY_UI_FIX_PROMPT
        + "\n\nFILE PATH:\n"
        + str(path)
        + "\n\nVIOLATIONS DETECTED:\n"
        + violation_summary
        + "\n\nCURRENT FILE CONTENT:\n\n"
        + original_source
    )

    try:
        raw_response = await agent.make_request_async(prompt, user_id="fix_body_ui")
    except Exception as e:
        logger.warning("Body UI fixer: LLM request failed for %s: %s", path, e)
        return {
            "path": str(path),
            "had_violations": True,
            "modified": False,
            "error": f"llm_error: {e}",
        }

    new_source = raw_response.strip()
    if new_source.startswith("```"):
        lines = new_source.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        new_source = "\n".join(lines).strip()

    if new_source == original_source:
        return {
            "path": str(path),
            "had_violations": True,
            "modified": False,
            "info": "LLM returned identical content.",
        }

    if write:
        try:
            # CONSTITUTIONAL FIX: Use governed mutation surface
            rel_path = str(path.relative_to(file_handler.repo_path))
            file_handler.write_runtime_text(rel_path, new_source)
            logger.info("Body UI fixer: updated file %s", path)
        except Exception as e:
            logger.warning("Body UI fixer: failed to write %s: %s", path, e)
            return {
                "path": str(path),
                "had_violations": True,
                "modified": False,
                "error": f"write_error: {e}",
            }
    return {"path": str(path), "had_violations": True, "modified": write}


@atomic_action(
    action_id="fix.body-ui",
    intent="Autonomously fix Body UI violations using LLM",
    impact=ActionImpact.WRITE_CODE,
    policies=["body_contracts", "agent_governance"],
    category="fixers",
)
# ID: 2b467a78-e140-4431-9166-1f485a8fe619
async def fix_body_ui_violations(
    core_context: CoreContext,
    write: bool = False,
    repo_root: Path | None = None,
    limit: int | None = None,
) -> ActionResult:
    """
    Use an LLM (via CoreContext) to automatically fix Body UI/env violations.
    """
    start_time = time.time()
    if repo_root is None:
        repo_root = core_context.git_service.repo_path

    check_result = await check_body_contracts(repo_root=repo_root)
    violations_raw: list[dict[str, Any]] = check_result.data.get("violations", [])

    if not violations_raw:
        return ActionResult(
            action_id="fix.body-ui",
            ok=True,
            data={"files_processed": 0},
            duration_sec=time.time() - start_time,
        )

    by_file: dict[Path, list[dict[str, Any]]] = {}
    for v in violations_raw:
        path = Path(v["file"])
        by_file.setdefault(path, []).append(v)

    items = list(by_file.items())
    if limit:
        items = items[:limit]

    cognitive = core_context.cognitive_service
    agent = await cognitive.aget_client_for_role("CodeReviewer")
    processor = ThrottledParallelProcessor(description="Fixing Body UI violations...")

    # ID: dbf3bacb-1562-48e3-acfa-9127c985737b
    async def worker(item):
        # Pass the file_handler from context
        return await _process_single_file(item, agent, write, core_context.file_handler)

    per_file_results = await processor.run_async(items, worker)
    files_modified = sum(1 for res in per_file_results if res.get("modified"))

    return ActionResult(
        action_id="fix.body-ui",
        ok=True,
        data={
            "files_found": len(by_file),
            "files_processed": len(per_file_results),
            "files_modified": files_modified,
            "dry_run": not write,
            "per_file": per_file_results,
        },
        duration_sec=time.time() - start_time,
        impact=ActionImpact.WRITE_CODE if write else ActionImpact.READ_ONLY,
    )
