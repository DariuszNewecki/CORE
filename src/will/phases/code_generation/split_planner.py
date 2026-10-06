# src/will/phases/code_generation/split_planner.py

"""
Deterministic split planning for ``refactor_modularity`` workflows.

The LLM no longer writes split code. It produces a ``SplitPlan`` (boundary
decisions only) and ``ModularitySplitter`` performs all file work
deterministically. Extracted from ``CodeGenerationPhase`` (ADR-095) so the
phase keeps only the Intelligent Reflex Loop; behavior is unchanged.
"""

from __future__ import annotations

import ast
import json
import time
from typing import TYPE_CHECKING, Any

from body.atomic.modularity_splitter import ModularitySplitter, SplitResult
from body.atomic.split_plan import SplitPlan, SplitPlanError
from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 6a55d689-dcef-4cdc-89b4-7914aa758f61
class DeterministicSplitPlanner:
    """LLM decides module boundaries only; AST machinery does all file work."""

    def __init__(self, core_context: CoreContext) -> None:
        self.context = core_context

    _SPLIT_PLAN_SYSTEM_PROMPT = (
        "You are a modularization planner.  You receive a Python source file "
        "and its already-identified responsibility clusters.  Your ONLY job is "
        "to produce a SplitPlan as JSON.  Do not write any code.  Do not "
        "explain anything outside the JSON."
    )

    _SPLIT_PLAN_USER_TEMPLATE = """\
Responsibility clusters already identified:
{clusters}

File: {source_file}

Actual symbols in this file (use ONLY these exact names):
{actual_symbols}

Source (for reference — do NOT rewrite it):
```python
{source_code}
```

Produce JSON matching exactly this schema:
{{
  "source_file": "...",
  "new_package_name": "...",
  "modules": [
    {{
      "module_name": "snake_case_name",
      "symbols": ["SymbolName", "function_name"],
      "rationale": "one sentence"
    }}
  ]
}}

Rules:
- Every top-level class and function must appear in exactly one module
- module_name must be a valid Python identifier
- At least 2 modules required
- new_package_name should match the original filename without .py

CRITICAL: Your response must be ONLY the JSON object.
No explanation. No markdown. No text before or after.
No ```json fences. Start your response with {{ and end with }}.
"""

    # ID: a0ad46a9-af80-40d5-8098-5e11ed14ce2d
    async def execute(self, context: WorkflowContext, start_time: float) -> PhaseResult:
        """LLM decides boundaries only; AST machinery does all file work."""
        plan = context.results.get("planning", {}).get("execution_plan", [])
        repo_root = self.context.git_service.repo_path

        logger.info(
            "Deterministic split path: %d plan step(s) for refactor_modularity",
            len(plan),
        )

        split_results: list[dict[str, Any]] = []

        for task in plan:
            file_path_str = getattr(getattr(task, "params", None), "file_path", None)
            if not file_path_str:
                continue

            source_path = repo_root / file_path_str
            if not source_path.exists():
                logger.warning("Source file not found: %s", source_path)
                continue

            source_code = source_path.read_text(encoding="utf-8")

            # --- Extract actual symbol names from AST --------------------
            tree = ast.parse(source_code, filename=file_path_str)
            actual_symbols = [
                node.name
                for node in ast.iter_child_nodes(tree)
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                )
            ]

            # --- Gather responsibility clusters from earlier phases -------
            clusters_raw = context.results.get("planning", {}).get("clusters", [])
            clusters_text = (
                json.dumps(clusters_raw, indent=2)
                if clusters_raw
                else "No pre-identified clusters available.  Infer from the source."
            )

            # --- Ask the LLM for boundary decisions only ------------------
            split_plan_result = await self._request_split_plan(
                source_file=file_path_str,
                source_code=source_code,
                clusters_text=clusters_text,
                actual_symbols=actual_symbols,
            )

            if split_plan_result is None:
                split_results.append(
                    {
                        "file": file_path_str,
                        "ok": False,
                        "error": "LLM failed to produce a valid SplitPlan",
                    }
                )
                continue

            # --- Deterministic split via AST ------------------------------
            splitter = ModularitySplitter()
            try:
                result: SplitResult = splitter.split(source_path, split_plan_result)
            except SplitPlanError as exc:
                logger.error("Split failed for %s: %s", file_path_str, exc)
                split_results.append(
                    {
                        "file": file_path_str,
                        "ok": False,
                        "error": str(exc),
                    }
                )
                continue

            split_results.append(
                {
                    "file": file_path_str,
                    "ok": True,
                    "split_result": result,
                    "plan": split_plan_result,
                }
            )

        ok = any(r.get("ok") for r in split_results)

        return PhaseResult(
            name="code_generation",
            ok=ok,
            data={
                "deterministic_split": True,
                "split_results": split_results,
            },
            duration_sec=time.perf_counter() - start_time,
        )

    # ID: c2ee2e4c-8779-463f-91a6-48c568710645
    async def _request_split_plan(
        self,
        source_file: str,
        source_code: str,
        clusters_text: str,
        actual_symbols: list[str],
    ) -> SplitPlan | None:
        """Ask the LLM for a SplitPlan JSON; parse and validate it.

        Returns None if the LLM response is unparseable or invalid.
        """
        user_prompt = self._SPLIT_PLAN_USER_TEMPLATE.format(
            clusters=clusters_text,
            source_file=source_file,
            source_code=source_code,
            actual_symbols=", ".join(actual_symbols),
        )

        try:
            if self.context.cognitive_service is None:
                return None
            model = PromptModel.load("code_generation_task_step_prompt")
            client = await self.context.cognitive_service.aget_client_for_role(
                model._artifact.manifest.role
            )
            raw_response = await model.invoke(
                context={
                    "task_step": (self._SPLIT_PLAN_SYSTEM_PROMPT + "\n\n" + user_prompt)
                },
                client=client,
                user_id="deterministic_split_planner",
            )

            # Extract JSON from response (may be wrapped in ```json fences)
            json_str = self._extract_json(raw_response)
            plan = SplitPlan.from_llm_json(json_str)
            logger.info(
                "SplitPlan validated: %d modules for %s",
                len(plan.modules),
                source_file,
            )
            return plan

        except SplitPlanError as exc:
            logger.error("SplitPlan validation failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("SplitPlan request failed: %s", exc)
            return None

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown code fences to expose raw JSON."""
        stripped = text.strip()
        if stripped.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = stripped.index("\n")
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        return stripped.strip()
