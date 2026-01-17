# src/body/atomic/executor.py

"""
Universal action executor for CORE's atomic actions.

ActionExecutor is the governed gateway for executing registered atomic actions.
It enforces logic conservation on file mutations and applies a deterministic
finalizer pipeline to code artifacts.
"""

from __future__ import annotations

import ast
import inspect
import time
from typing import TYPE_CHECKING, Any

from body.atomic.registry import ActionDefinition, action_registry
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: executor_main
# ID: e1b46328-53d2-4abe-93e4-3b875d50300f
class ActionExecutor:
    """Universal execution gateway with a deterministic finalizer for code mutations."""

    def __init__(self, core_context: CoreContext):
        self.core_context = core_context
        self.registry = action_registry
        logger.debug("ActionExecutor initialized")

    # ID: executor_execute
    @atomic_action(
        action_id="action.execute",
        intent="Governed execution with automatic constitutional finalization",
        impact=ActionImpact.WRITE_CODE,
        policies=["atomic_actions"],
    )
    # ID: 0724a464-ca71-4c53-878c-2c2d75dabcde
    async def execute(
        self,
        action_id: str,
        write: bool = False,
        **params: Any,
    ) -> ActionResult:
        """Execute a registered action with authorization, finalization, and auditing."""
        start_time = time.perf_counter()
        definition = self.registry.get(action_id)
        if not definition:
            result = ActionResult(
                action_id=action_id,
                ok=False,
                data={"error": f"Action not found: {action_id}"},
            )
            duration_sec = time.perf_counter() - start_time
            if hasattr(result, "duration_sec"):
                result.duration_sec = duration_sec
            else:
                result.data["duration_sec"] = duration_sec
            logger.warning(
                "AUDIT: action=%s category=missing write=%s ok=%s duration=%.2fs",
                action_id,
                write,
                result.ok,
                duration_sec,
            )
            return result

        auth_check = self._check_authorization(definition, write)
        if not auth_check["authorized"]:
            result = ActionResult(
                action_id=action_id,
                ok=False,
                data={"error": auth_check["reason"] or "Unauthorized"},
            )
            duration_sec = time.perf_counter() - start_time
            if hasattr(result, "duration_sec"):
                result.duration_sec = duration_sec
            else:
                result.data["duration_sec"] = duration_sec
            try:
                await self._audit_log(definition, result, write, duration_sec)
            except Exception:
                logger.exception("Audit log failed for action %s", action_id)
            return result

        if (
            write
            and action_id in ("file.create", "file.edit")
            and isinstance(params.get("code"), str)
        ):
            await self._guard_logic_conservation(
                params.get("file_path"),
                params.get("code", ""),
            )
            file_path = params.get("file_path") or "unknown.py"
            logger.info("Finalizing code artifact for %s", file_path)
            params["code"] = await self._finalize_code_artifact(
                file_path,
                params.get("code", ""),
            )

        try:
            exec_params = self._prepare_params(definition, write, params)
            result = await definition.executor(**exec_params)
        except Exception as exc:
            logger.error("Action %s failed: %s", action_id, exc, exc_info=True)
            result = ActionResult(
                action_id=action_id, ok=False, data={"error": str(exc)}
            )

        duration_sec = time.perf_counter() - start_time
        if hasattr(result, "duration_sec"):
            try:
                result.duration_sec = duration_sec
            except Exception:
                if isinstance(result.data, dict):
                    result.data["duration_sec"] = duration_sec
        elif isinstance(result.data, dict):
            result.data["duration_sec"] = duration_sec

        try:
            await self._audit_log(definition, result, write, duration_sec)
        except Exception:
            logger.exception("Audit log failed for action %s", action_id)

        return result

    # ID: logic_conservation_gate
    async def _guard_logic_conservation(
        self, file_path: str | None, new_code: str
    ) -> None:
        """Block suspiciously large deletions during write mutations."""
        if not file_path or not new_code:
            return

        abs_path = self.core_context.git_service.repo_path / file_path
        if not abs_path.exists():
            return

        try:
            old_code = abs_path.read_text(encoding="utf-8")
        except Exception:
            return

        # ID: 7f002b46-17c9-44e6-bef3-c064a6eb864f
        def normalized_size(text: str) -> int:
            return len("\n".join(line.rstrip() for line in text.splitlines()))

        old_size = normalized_size(old_code)
        new_size = normalized_size(new_code)

        if old_size > 500 and new_size < (old_size * 0.5):
            logger.error(
                "Logic conservation violation: %s shrank from %s to %s characters",
                file_path,
                old_size,
                new_size,
            )
            raise ValueError(
                "Logic Conservation Violation: "
                f"Code shrank from {old_size} to {new_size} characters."
            )

    # ID: atomic_finalizer_pipeline
    async def _finalize_code_artifact(self, file_path: str, code: str) -> str:
        """Apply header normalization, ID injection, and formatting to code."""
        from shared.utils.header_tools import HeaderComponents, HeaderTools

        header = HeaderTools.parse(code)
        original_body = header.body[:]
        header.location = f"# {file_path}"
        if not header.module_description:
            header.module_description = f'"""Refactored logic for {file_path}."""'
        header.has_future_import = True

        reconstructed = HeaderTools.reconstruct(header)
        if original_body:
            expected_body = "\n".join(original_body).strip()
            if expected_body and not reconstructed.strip().endswith(expected_body):
                header_only = HeaderComponents(
                    location=header.location,
                    module_description=header.module_description,
                    has_future_import=header.has_future_import,
                    other_imports=header.other_imports,
                    body=[],
                )
                header_text = HeaderTools.reconstruct(header_only).rstrip()
                body_text = "\n".join(original_body).rstrip()
                reconstructed = f"{header_text}\n\n{body_text}\n"
        code = reconstructed

        import uuid

        from shared.ast_utility import find_symbol_id_and_def_line

        try:
            tree = ast.parse(code)
            lines = code.splitlines()

            # ID: 8b3b7d42-e66f-422a-ad3f-b1bb00bcb587
            def has_id_tag(def_line: int) -> bool:
                tag_index = def_line - 2
                if 0 <= tag_index < len(lines):
                    return lines[tag_index].lstrip().startswith("# ID:")
                return False

            targets: list[tuple[int, int]] = []
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if node.name.startswith("_"):
                        continue
                    result = find_symbol_id_and_def_line(node, lines)
                    if has_id_tag(result.definition_line_num):
                        continue
                    col_offset = getattr(node, "col_offset", 0) or 0
                    targets.append((result.definition_line_num, col_offset))

            for def_line, col_offset in sorted(
                targets, key=lambda item: item[0], reverse=True
            ):
                indent = " " * col_offset
                lines.insert(def_line - 1, f"{indent}# ID: {uuid.uuid4()}")

            code = "\n".join(lines).rstrip() + "\n"
        except Exception as exc:
            logger.warning("Finalizer: ID injection failed: %s", exc)

        from shared.infrastructure.validation.black_formatter import (
            format_code_with_black,
        )

        try:
            code = format_code_with_black(code)
        except Exception:
            pass

        if not code.endswith("\n"):
            code += "\n"

        return code

    # ID: executor_check_authorization
    def _check_authorization(
        self, definition: ActionDefinition, write: bool
    ) -> dict[str, Any]:
        """Authorize actions based on impact level with a permissive default."""
        impact = definition.impact_level.lower()
        if impact in {"safe", "moderate"}:
            return {"authorized": True, "reason": None}
        return {"authorized": True, "reason": None}

    # ID: executor_prepare_params
    def _prepare_params(
        self, definition: ActionDefinition, write: bool, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Prepare executor parameters using signature inspection."""
        sig = inspect.signature(definition.executor)
        accepts_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )

        exec_params: dict[str, Any] = {}
        if "write" in sig.parameters:
            exec_params["write"] = write
        if "core_context" in sig.parameters:
            exec_params["core_context"] = self.core_context

        if accepts_kwargs:
            exec_params.update(params)
        else:
            for key, value in params.items():
                if key in sig.parameters and key not in exec_params:
                    exec_params[key] = value

        return exec_params

    # ID: executor_audit_log
    async def _audit_log(
        self,
        definition: ActionDefinition,
        result: ActionResult,
        write: bool,
        duration_sec: float,
    ) -> None:
        """Log a structured audit record for an action execution."""
        logger.info(
            "AUDIT: action=%s category=%s write=%s ok=%s duration=%.2fs",
            definition.action_id,
            definition.category.value,
            write,
            result.ok,
            duration_sec,
        )
