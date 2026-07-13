# src/will/agents/modularity_cognitive_delegate.py
"""
ModularityCognitiveDelegate — Will-tier CognitiveFlowDelegate for flow.fix_modularity.

Implements shared.protocols.CognitiveFlowDelegate for the "modularity_analysis"
cognitive capability. Handles the "analyze.modularity_seam" cognitive step by:
  1. Resolving the target file (caller-supplied file_path, or the worst
     current modularity-score violator if omitted)
  2. Building prompt-grounding context (layer, callers, symbol inventory)
  3. Running the single-shot modularity_analyze prompt
  4. Parsing, structurally overriding, and validating the returned SplitPlan
     (inventory gate + confidence gate) — this IS the "cognitive" work:
     deciding whether the LLM's proposed seam is usable
  5. Returning {"resolved_file_path": ..., "plan_raw": ...} for FlowExecutor
     to thread downstream to the fix.modularity write action, which performs
     one further defensive parse+validate pass per ADR-140 D1

ADR-140 D1/D6 (#769). The AST-classification helpers below
(_find_worst_modularity_violator, _detect_layer_from_path, _find_callers,
_SymbolInventory, extract_symbol_inventory, validate_plan_against_inventory)
moved here from body/atomic/modularity_fix.py — pure prompt-grounding and
plan-acceptance logic, not a write concern, mirroring _extract_symbol_code's
move to TestGenCognitiveDelegate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.protocols.cognitive_flow_delegate import CognitiveStepError


if TYPE_CHECKING:
    from body.atomic.split_plan import SplitPlan
    from shared.context import CoreContext

logger = getLogger(__name__)

_CFG_AZ = load_operational_config().analyzers

_ANALYZE_PROMPT = "modularity_analyze"


# ---------------------------------------------------------------------------
# AST-classification helpers (moved from body/atomic/modularity_fix.py)
# ---------------------------------------------------------------------------


def _find_worst_modularity_violator(repo_root: Path) -> Path | None:
    """Find the src/ Python file with the most lines. Excludes __init__.py and tests."""
    skip_dirs = {"tests", "__pycache__", ".venv", "venv", ".git", "work", "var"}
    src_root = repo_root / "src"
    if not src_root.exists():
        return None

    worst: tuple[int, Path] | None = None
    for py_file in src_root.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        if any(part in py_file.parts for part in skip_dirs):
            continue
        try:
            line_count = len(py_file.read_text(encoding="utf-8").splitlines())
            if line_count >= _CFG_AZ.max_module_lines:
                if worst is None or line_count > worst[0]:
                    worst = (line_count, py_file)
        except Exception:
            continue
    return worst[1] if worst else None


def _detect_layer_from_path(path: Path, repo_root: Path) -> str:
    """Detect architectural layer from file path."""
    rel = str(path.relative_to(repo_root))
    if rel.startswith("src/mind"):
        return "mind"
    if rel.startswith("src/body"):
        return "body"
    if rel.startswith("src/will"):
        return "will"
    if rel.startswith("src/shared"):
        return "shared"
    return "unknown"


def _find_callers(target_path: Path, repo_root: Path) -> list[str]:
    """Find files in src/ that import from the target module."""
    import ast

    target_module = (
        str(target_path.relative_to(repo_root)).replace("/", ".").removesuffix(".py")
    )
    if target_module.startswith("src."):
        target_module = target_module[4:]

    callers = []
    src_root = repo_root / "src"
    for py_file in src_root.rglob("*.py"):
        if py_file == target_path:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import | ast.ImportFrom):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if node.module == target_module or node.module.startswith(
                            target_module + "."
                        ):
                            callers.append(str(py_file.relative_to(repo_root)))
                            break
        except Exception:
            continue
    return callers


@dataclass
class _SymbolInventory:
    """AST-extracted classification of a file's symbol surface.

    Locally-defined names are valid split candidates; imported names are
    re-exports and must never appear in a plan. Issue #296: prior to this
    classification the LLM was free-associating over the raw file text and
    routinely placed imported or invented symbols in plans, costing a full
    retry cycle each time.
    """

    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    constants: list[str] = field(default_factory=list)
    dominant_class: str | None = None
    dominant_methods: list[str] = field(default_factory=list)
    dominant_class_assigns: list[str] = field(default_factory=list)
    imported: list[tuple[str, str]] = field(default_factory=list)

    # ID: 4d3c2b1a-0e9f-4a8d-b7c6-5f4e3d2c1b0a
    def defined_top_level_names(self) -> set[str]:
        """All top-level names defined in the current scope."""
        return set(self.classes) | set(self.functions) | set(self.constants)

    # ID: 5e4d3c2b-1a0f-4b9e-c8d7-6a5b4c3d2e1f
    def defined_class_member_names(self) -> set[str]:
        """All defined class member names (dominant-class methods + assigns)."""
        return set(self.dominant_methods) | set(self.dominant_class_assigns)

    # ID: 6f5e4d3c-2b1a-4c0f-d9e8-7b6c5d4e3f2a
    def imported_lookup(self) -> dict[str, str]:
        """Mapping of imported symbols to their source module."""
        return {name: source for name, source in self.imported}

    # ID: 7a6b5c4d-3e2f-4d1a-e0f9-8c7d6e5f4a3b
    def render_for_prompt(self) -> str:
        """Human-readable summary of symbol definitions and imports for the prompt."""
        if not (
            self.classes or self.functions or self.constants or self.dominant_methods
        ):
            return "(file could not be parsed — no symbols available)"

        lines: list[str] = ["Defined here:"]
        if self.classes:
            lines.append(f"  Classes:    {self.classes}")
        if self.functions:
            lines.append(f"  Functions:  {self.functions}")
        if self.constants:
            lines.append(f"  Constants:  {self.constants}")
        if self.dominant_class and self.dominant_methods:
            lines.append(
                f"  Methods of dominant class '{self.dominant_class}' "
                f"({len(self.dominant_methods)}):"
            )
            for m in self.dominant_methods:
                lines.append(f"    - {m}")
            if self.dominant_class_assigns:
                lines.append("  Class-level assignments:")
                for a in self.dominant_class_assigns:
                    lines.append(f"    - {a}")

        if self.imported:
            lines.append("")
            lines.append(
                "Imported (NOT valid split candidates — these are "
                "re-exports, not definitions):"
            )
            for name, source in self.imported:
                lines.append(f"  - {name} (from {source})")

        return "\n".join(lines)


def _extract_symbol_inventory(source: str) -> _SymbolInventory:
    """Classify every top-level symbol in *source* by origin.

    Walks the AST once and returns a structured inventory: used to constrain
    the LLM prompt to locally-defined candidates, and to reject any plan
    symbol that resolves to an import or to nothing at all. The
    dominant-class heuristic (>=3 methods on the largest top-level ClassDef)
    mirrors the one in ModularitySplitter so prompt and splitter agree on
    what counts as a class split.

    An empty inventory is returned on SyntaxError; the confidence/validation
    gates downstream reject the resulting plan.
    """
    import ast

    inv = _SymbolInventory()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return inv

    class_defs: list[ast.ClassDef] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            class_defs.append(node)
            inv.classes.append(node.name)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            inv.functions.append(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            inv.constants.append(node.target.id)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    inv.constants.append(target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                inv.imported.append((bound, alias.name))
        elif isinstance(node, ast.ImportFrom):
            source_mod = ("." * (node.level or 0)) + (node.module or "")
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                inv.imported.append((bound, source_mod))

    if class_defs:
        best: ast.ClassDef | None = None
        best_count = 0
        for cls in class_defs:
            methods = [
                m
                for m in cls.body
                if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef)
            ]
            if len(methods) > best_count:
                best_count = len(methods)
                best = cls

        if best is not None and best_count >= 3:
            inv.dominant_class = best.name
            for member in best.body:
                if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
                    inv.dominant_methods.append(member.name)
                elif isinstance(member, ast.AnnAssign) and isinstance(
                    member.target, ast.Name
                ):
                    inv.dominant_class_assigns.append(member.target.id)
                elif isinstance(member, ast.Assign):
                    for target in member.targets:
                        if isinstance(target, ast.Name):
                            inv.dominant_class_assigns.append(target.id)

    return inv


def _validate_plan_against_inventory(
    plan: SplitPlan, inv: _SymbolInventory
) -> tuple[list[str], list[str]]:
    """Check every plan symbol resolves to a locally-defined name.

    Returns (imported_offenders, unknown_offenders). Empty pair means the
    plan is internally consistent with the inventory.
    """
    imported_map = inv.imported_lookup()
    top_level_set = inv.defined_top_level_names()
    class_member_set = inv.defined_class_member_names()

    imported_offenders: list[str] = []
    unknown_offenders: list[str] = []

    for mod in plan.modules:
        valid_set = class_member_set if mod.is_class_split else top_level_set
        for sym in mod.symbols:
            if sym in valid_set:
                continue
            if sym in imported_map:
                imported_offenders.append(f"{sym} (from {imported_map[sym]})")
            else:
                unknown_offenders.append(sym)

    return imported_offenders, unknown_offenders


# ---------------------------------------------------------------------------
# CognitiveFlowDelegate implementation
# ---------------------------------------------------------------------------


# ID: f87dadde-1ef3-426d-bfc3-359aa2abf8c1
class ModularityCognitiveDelegate:
    """
    CognitiveFlowDelegate implementation for the modularity_analysis
    cognitive capability.

    Handles the "analyze.modularity_seam" step declared in
    flow.fix_modularity.yaml. Injected by will.governance.fix_runner's
    flow dispatch when flow_def.cognitive_capability ==
    "modularity_analysis" (ADR-140 D9 pattern, applied to the governor-CLI
    dispatch path rather than ProposalExecutor since fix.modularity has no
    autonomous rule binding — ADR-095 D5).
    """

    def __init__(self, core_context: CoreContext) -> None:
        self._core_context = core_context

    # ID: 0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d
    async def execute_cognitive_step(
        self,
        step_ref: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a cognitive step for modularity analysis.

        Supported step_refs:
          "analyze.modularity_seam" — single-shot LLM seam analysis.

        Raises CognitiveStepError on unknown step_ref or analysis failure.
        """
        if step_ref == "analyze.modularity_seam":
            return await self._analyze_modularity_seam(params)

        raise CognitiveStepError(
            step_ref=step_ref,
            reason=f"ModularityCognitiveDelegate does not handle step_ref {step_ref!r}",
        )

    async def _analyze_modularity_seam(self, params: dict[str, Any]) -> dict[str, Any]:
        """Find the natural split seam for a modularity-violating file."""
        from shared.models.prompt_model import PromptModel

        repo_root: Path = self._core_context.git_service.repo_path
        file_path = params.get("file_path")

        if file_path:
            target = repo_root / file_path
            if not target.exists():
                raise CognitiveStepError(
                    step_ref="analyze.modularity_seam",
                    reason=f"File not found: {file_path}",
                )
        else:
            target = _find_worst_modularity_violator(repo_root)
            if target is None:
                raise CognitiveStepError(
                    step_ref="analyze.modularity_seam",
                    reason="no_violations_found",
                )

        rel_path = str(target.relative_to(repo_root))
        original_content = target.read_text(encoding="utf-8")
        line_count = len(original_content.splitlines())
        layer = _detect_layer_from_path(target, repo_root)
        callers = _find_callers(target, repo_root)
        symbol_inventory = _extract_symbol_inventory(original_content)

        logger.info(
            "ModularityCognitiveDelegate: analyzing %s (%d lines, layer=%s, callers=%d)",
            rel_path,
            line_count,
            layer,
            len(callers),
        )

        cognitive_service = self._core_context.cognitive_service
        if cognitive_service is None:
            try:
                cognitive_service = (
                    await self._core_context.registry.get_cognitive_service()
                )
            except Exception as exc:
                raise CognitiveStepError(
                    step_ref="analyze.modularity_seam",
                    reason=f"cognitive_service unavailable: {exc}",
                ) from exc

        try:
            analyze_model = PromptModel.load(_ANALYZE_PROMPT)
            analyze_client = await cognitive_service.aget_client_for_role(
                analyze_model.manifest.role
            )
            plan_raw = await analyze_model.invoke(
                analyze_client,
                {
                    "file_path": rel_path,
                    "layer": layer,
                    "violations": "architecture.max_file_size, modularity.refactor_score_threshold",
                    "line_count": str(line_count),
                    "content": original_content,
                    "callers": "\n".join(callers) if callers else "(none)",
                    "symbol_inventory": symbol_inventory.render_for_prompt(),
                },
            )
        except Exception as exc:
            raise CognitiveStepError(
                step_ref="analyze.modularity_seam",
                reason=f"analyze phase failed: {exc}",
            ) from exc

        self._validate_plan(plan_raw, rel_path, target, symbol_inventory)

        logger.info(
            "ModularityCognitiveDelegate: %s — split plan accepted",
            rel_path,
        )
        return {"resolved_file_path": rel_path, "plan_raw": plan_raw}

    def _validate_plan(
        self,
        plan_raw: str,
        rel_path: str,
        target: Path,
        symbol_inventory: _SymbolInventory,
    ) -> None:
        """Parse and gate the LLM's plan before accepting it (ADR-140: the
        cognitive step decides whether the generation is usable; the write
        action performs only one further defensive pass on the artifact).
        """
        from body.atomic.split_plan import SplitPlan, SplitPlanError

        try:
            split_plan = SplitPlan.from_llm_json(plan_raw)
        except SplitPlanError as exc:
            err_str = str(exc)
            if err_str.startswith("llm_declined:"):
                reason = "llm_declined: " + err_str[len("llm_declined:") :].strip()
            else:
                reason = f"plan validation failed: {exc}"
            raise CognitiveStepError(
                step_ref="analyze.modularity_seam", reason=reason
            ) from exc

        # Structural override — the caller owns these, not the LLM (mirrors
        # the write action's own override before ModularitySplitter.split).
        split_plan.source_file = rel_path
        split_plan.new_package_name = target.stem
        try:
            split_plan.validate()
        except SplitPlanError as exc:
            raise CognitiveStepError(
                step_ref="analyze.modularity_seam",
                reason=f"plan re-validation failed: {exc}",
            ) from exc

        imported_offenders, unknown_offenders = _validate_plan_against_inventory(
            split_plan, symbol_inventory
        )
        if imported_offenders or unknown_offenders:
            raise CognitiveStepError(
                step_ref="analyze.modularity_seam",
                reason=(
                    "plan references non-local symbols "
                    f"(imported={imported_offenders}, unknown={unknown_offenders})"
                ),
            )

        confidence_threshold = (
            load_operational_config().modularity.split_confidence_threshold
        )
        if split_plan.confidence < confidence_threshold:
            raise CognitiveStepError(
                step_ref="analyze.modularity_seam",
                reason=(
                    "low_confidence: "
                    f"{split_plan.confidence:.2f} < threshold={confidence_threshold:.2f}"
                ),
            )
