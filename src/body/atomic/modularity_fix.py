# src/body/atomic/modularity_fix.py
# src/body/atomic/fix_actions.py

"""
Atomic Fix Actions - Code Remediation

Each action does ONE thing and returns ActionResult.
Actions are composable, auditable, and constitutionally governed.

Constitutional Alignment:
- Boundary: Uses CoreContext for repo_path (no direct settings access)
- Circularity Fix: Feature-level imports are performed inside functions.
- Remediation: Each action declares which audit check_ids it fixes via remediates=[].
  ViolationRemediatorWorker uses this to close the autonomous audit loop.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


_CFG_AZ = load_operational_config().analyzers


if TYPE_CHECKING:
    from pathlib import Path

    from body.atomic.split_plan import SplitPlan
    from body.infrastructure.storage.file_handler import FileHandler
    from shared.context import CoreContext

logger = getLogger(__name__)


_FALLBACK_SPLIT_CONFIDENCE_THRESHOLD: float = 0.70


def _load_split_confidence_threshold(repo_root) -> float:
    """Load split confidence threshold from governance_paths.yaml via PathResolver.

    Falls back to _FALLBACK_SPLIT_CONFIDENCE_THRESHOLD if the file is missing
    or the key is absent — never raises.
    """
    try:
        import yaml

        from shared.path_resolver import PathResolver

        path_resolver = PathResolver(repo_root)
        config_path = path_resolver.governance_config_path
        if not config_path.exists():
            return _FALLBACK_SPLIT_CONFIDENCE_THRESHOLD
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return _FALLBACK_SPLIT_CONFIDENCE_THRESHOLD
        return float(
            raw.get("modularity", {}).get(
                "split_confidence_threshold", _FALLBACK_SPLIT_CONFIDENCE_THRESHOLD
            )
        )
    except Exception:
        return _FALLBACK_SPLIT_CONFIDENCE_THRESHOLD


def _find_worst_modularity_violator(repo_root):
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


def _detect_layer_from_path(path, repo_root) -> str:
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


def _find_callers(target_path, repo_root) -> list[str]:
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


_DECORATORS_TO_PRESERVE: frozenset[str] = frozenset(
    {"register_action", "atomic_action"}
)


def _decorator_simple_name(deco) -> str | None:
    """Return the trailing identifier of a decorator expression, or None.

    Handles ``@name``, ``@name(...)``, ``@mod.name``, ``@mod.name(...)``.
    """
    import ast as _ast

    if isinstance(deco, _ast.Name):
        return deco.id
    if isinstance(deco, _ast.Attribute):
        return deco.attr
    if isinstance(deco, _ast.Call):
        return _decorator_simple_name(deco.func)
    return None


def _collect_preserved_decorators(source: str) -> dict[str, set[str]]:
    """Map each decorated symbol → set of preserve-target decorator names.

    Walks the full AST so methods inside classes are covered alongside
    top-level functions and classes.
    """
    import ast as _ast

    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return {}
    out: dict[str, set[str]] = {}
    for node in _ast.walk(tree):
        if not isinstance(
            node, _ast.FunctionDef | _ast.AsyncFunctionDef | _ast.ClassDef
        ):
            continue
        names = {
            n
            for d in node.decorator_list
            if (n := _decorator_simple_name(d)) is not None
        }
        targets = names & _DECORATORS_TO_PRESERVE
        if targets:
            out.setdefault(node.name, set()).update(targets)
    return out


def _invalidate_split_pycache(
    target: Path, file_handler: FileHandler, repo_root: Path
) -> list[Path]:
    """Remove stale .pyc artefacts left behind by a fix.modularity split.

    After step 7 writes the new package files and unlinks the original
    monolith, two regions can carry a .pyc that the daemon would otherwise
    serve on restart:

      - ``target.parent/__pycache__/<target.stem>.cpython-*.pyc`` —
        cached bytecode of the deleted monolith.
      - ``target.parent/<target.stem>`` (the new package directory) —
        nested ``__pycache__`` directories that may exist from a
        previous failed run.

    Mutations route through ``FileHandler.remove_file`` /
    ``FileHandler.remove_tree`` so the deletion is governed
    (architecture.governance_basics.logic_mutation_governed) and
    boundary-checked. Returns the absolute paths actually removed, for
    caller logging.

    See issue #212 / Failure 2 in CORE-ModularityLessons.md.
    """
    removed: list[Path] = []

    old_pycache = target.parent / "__pycache__"
    if old_pycache.is_dir():
        for stale in old_pycache.glob(f"{target.stem}.cpython-*.pyc"):
            try:
                rel = stale.relative_to(repo_root)
            except ValueError:
                continue
            file_handler.remove_file(str(rel))
            removed.append(stale)

    new_package_dir = target.parent / target.stem
    if new_package_dir.is_dir():
        for pycache_dir in new_package_dir.rglob("__pycache__"):
            if not pycache_dir.is_dir():
                continue
            try:
                rel = pycache_dir.relative_to(repo_root)
            except ValueError:
                continue
            file_handler.remove_tree(str(rel))
            removed.append(pycache_dir)

    return removed


def _check_decorator_conservation(
    original_source: str, produced_files: list[dict]
) -> list[str]:
    """Detect registration decorators present in *original_source* but missing
    from *produced_files*. Returns sorted ``"@deco on symbol"`` strings; empty
    list means conservation holds. ``__init__.py`` is skipped — re-exports
    don't carry definitions.
    """
    expected = _collect_preserved_decorators(original_source)
    if not expected:
        return []
    found: dict[str, set[str]] = {}
    for f in produced_files:
        path = f.get("path", "")
        if path.endswith("__init__.py"):
            continue
        for name, decos in _collect_preserved_decorators(f.get("content", "")).items():
            found.setdefault(name, set()).update(decos)
    missing: list[str] = []
    for sym, decos in expected.items():
        for d in decos:
            if d not in found.get(sym, set()):
                missing.append(f"@{d} on {sym}")
    return sorted(missing)


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

    # ID: 1c64dbd5-326a-45a1-adad-598b5d79f4ef
    def defined_top_level_names(self) -> set[str]:
        """Returns a set of all top-level names defined in the current scope.

        This includes class, function, and constant definitions at the top level,
        excluding any nested or local definitions within functions or classes.

        Returns:
            A set of strings representing the names of defined entities.
        """
        return set(self.classes) | set(self.functions) | set(self.constants)

    # ID: b5ab6c31-5f6e-4294-b735-4232e4f6ffac
    def defined_class_member_names(self) -> set[str]:
        """Returns a set of names for all defined class members.

        Aggregates method and variable names that are considered dominant within the class,
        indicating their significance or frequency of use in the class's implementation.

        Args:
            None

        Returns:
            A set containing names of all significant class member definitions.

        Raises:
            None"""
        return set(self.dominant_methods) | set(self.dominant_class_assigns)

    # ID: 2407928f-b671-43f8-b991-e31f9b9f1892
    def imported_lookup(self) -> dict[str, str]:
        """Fetches a mapping of imported symbols to their sources.

        Returns:
            A dictionary where keys are names of imported symbols and values
            are the corresponding source locations or module paths.
        """
        return {name: source for name, source in self.imported}

    # ID: be209121-da7a-4a19-9eff-3df1c907d6ec
    def render_for_prompt(self) -> str:
        """
        Generates a human-readable summary of symbol definitions and imports.

        Provides a detailed overview of what symbols are defined in this file, including
        classes, functions, constants, and dominant class methods, aiding developers in
        understanding the file's content and structure. Also lists imported symbols that
        are not considered valid split candidates.

        Returns:
            A multi-line string summarizing the file's symbol definitions and imports.
        """
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

    Walks the AST once and returns a structured inventory. Used twice by
    fix.modularity: once to constrain the LLM prompt to locally-defined
    candidates, and once after the LLM returns to reject any plan symbol
    that resolves to an import or to nothing at all. The dominant-class
    heuristic (≥3 methods on the largest top-level ClassDef) mirrors the
    one in ModularitySplitter so prompt and splitter agree on what counts
    as a class split.

    An empty inventory is returned on SyntaxError; downstream gates will
    catch the resulting validation failure.
    """
    import ast as _ast

    inv = _SymbolInventory()
    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return inv

    class_defs: list[_ast.ClassDef] = []
    for node in _ast.iter_child_nodes(tree):
        if isinstance(node, _ast.ClassDef):
            class_defs.append(node)
            inv.classes.append(node.name)
        elif isinstance(node, _ast.FunctionDef | _ast.AsyncFunctionDef):
            inv.functions.append(node.name)
        elif isinstance(node, _ast.AnnAssign) and isinstance(node.target, _ast.Name):
            inv.constants.append(node.target.id)
        elif isinstance(node, _ast.Assign):
            for target in node.targets:
                if isinstance(target, _ast.Name):
                    inv.constants.append(target.id)
        elif isinstance(node, _ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                inv.imported.append((bound, alias.name))
        elif isinstance(node, _ast.ImportFrom):
            source_mod = ("." * (node.level or 0)) + (node.module or "")
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                inv.imported.append((bound, source_mod))

    if class_defs:
        best: _ast.ClassDef | None = None
        best_count = 0
        for cls in class_defs:
            methods = [
                m
                for m in cls.body
                if isinstance(m, _ast.FunctionDef | _ast.AsyncFunctionDef)
            ]
            if len(methods) > best_count:
                best_count = len(methods)
                best = cls

        if best is not None and best_count >= 3:
            inv.dominant_class = best.name
            for member in best.body:
                if isinstance(member, _ast.FunctionDef | _ast.AsyncFunctionDef):
                    inv.dominant_methods.append(member.name)
                elif isinstance(member, _ast.AnnAssign) and isinstance(
                    member.target, _ast.Name
                ):
                    inv.dominant_class_assigns.append(member.target.id)
                elif isinstance(member, _ast.Assign):
                    for target in member.targets:
                        if isinstance(target, _ast.Name):
                            inv.dominant_class_assigns.append(target.id)

    return inv


def _validate_plan_against_inventory(
    plan: SplitPlan, inv: _SymbolInventory
) -> tuple[list[str], list[str]]:
    """Check every plan symbol resolves to a locally-defined name.

    Returns ``(imported_offenders, unknown_offenders)``. The first list
    holds symbols the LLM proposed that are actually imported (rendered as
    ``"name (from source_module)"``); the second holds names that exist
    nowhere in the file. Empty pair means the plan is internally
    consistent with the inventory.
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


@register_action(
    action_id="fix.modularity",
    description="Split a file that violates modularity rules using two-phase LLM analysis",
    category=ActionCategory.FIX,
    policies=["rules/architecture/modularity"],
    remediates=[],  # ADR-095 D5: governor-invoked CLI tool only; no autonomous rule binding.
)
@atomic_action(
    action_id="fix.modularity",
    intent="Two-phase split: Architect finds the seam, then Architect executes the plan. Logic Conservation Gate guards.",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 2e4e8a14-6495-4869-a047-43bb508d0d4a
async def action_fix_modularity(
    core_context: CoreContext,
    write: bool = False,
    file_path: str | None = None,
    **kwargs,
) -> ActionResult:
    """
    Split a modularity-violating file using two-phase LLM analysis.

    Phase 1 (modularity_analyze): Architect finds the natural seam and
    assigns confidence. Low/medium confidence defers to human session.

    Phase 2 (modularity_split): Architect executes the approved plan
    mechanically. Logic Conservation Gate validates before any write.
    """
    from body.atomic.modularity_splitter import ModularitySplitter
    from body.atomic.split_plan import SplitPlan, SplitPlanError
    from body.validators.logic_conservation_validator import LogicConservationValidator
    from shared.models.prompt_model import PromptModel

    start = time.time()
    repo_root = core_context.git_service.repo_path

    # 1. Find target file
    if file_path:
        target = repo_root / file_path
        if not target.exists():
            return ActionResult(
                action_id="fix.modularity",
                ok=False,
                data={"error": f"File not found: {file_path}"},
                duration_sec=time.time() - start,
            )
    else:
        target = _find_worst_modularity_violator(repo_root)
        if target is None:
            return ActionResult(
                action_id="fix.modularity",
                ok=True,
                data={"message": "No modularity violations found"},
                duration_sec=time.time() - start,
            )

    rel_path = str(target.relative_to(repo_root))
    original_content = target.read_text(encoding="utf-8")
    line_count = len(original_content.splitlines())
    layer = _detect_layer_from_path(target, repo_root)
    callers = _find_callers(target, repo_root)

    logger.info(
        "fix.modularity: analyzing %s (%d lines, layer=%s, callers=%d)",
        rel_path,
        line_count,
        layer,
        len(callers),
    )

    # 2. Classify every symbol in the file by origin (defined here vs
    # imported) from the AST. The rendered form goes into the LLM prompt
    # so the model only chooses split candidates from locally-defined
    # names; the structured form is re-checked after the LLM returns.
    # Issue #296: prior to this, the LLM saw raw file content and routinely
    # placed imported or invented symbols in plans.
    symbol_inventory = _extract_symbol_inventory(original_content)

    # 3. Phase 1 — find the seam via LLM
    if core_context.cognitive_service is None:
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": "cognitive_service not initialized"},
            impact=ActionImpact.WRITE_CODE,
            duration_sec=time.time() - start,
        )
    try:
        analyze_model = PromptModel.load("modularity_analyze")
        analyze_client = await core_context.cognitive_service.aget_client_for_role(
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
    except Exception as e:
        logger.error("fix.modularity: analyze phase failed: %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"analyze phase failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    # 4. Parse LLM response into a validated SplitPlan
    try:
        split_plan = SplitPlan.from_llm_json(plan_raw)
    except SplitPlanError as e:
        logger.error(
            "fix.modularity: could not parse analyze response: %s\nRaw: %s",
            e,
            plan_raw[:500] if plan_raw else "(empty)",
        )
        err_str = str(e)
        if err_str.startswith("llm_declined:"):
            reason = err_str[len("llm_declined:") :].strip()
            return ActionResult(
                action_id="fix.modularity",
                ok=False,
                data={"error": "llm_declined", "reason": reason, "file": rel_path},
                duration_sec=time.time() - start,
            )
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"plan validation failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    # Override structural fields — the action owns these, not the LLM.
    # LLM output routinely omits source_file and new_package_name;
    # trusting the LLM here causes ModularitySplitter to write to the
    # wrong location. target.stem is the authoritative package name
    # (enforced by validate() stem check).
    split_plan.source_file = rel_path
    split_plan.new_package_name = target.stem
    try:
        split_plan.validate()
    except SplitPlanError as e:
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"plan re-validation failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    logger.info(
        "fix.modularity: %s — split plan validated (%d modules), proceeding",
        rel_path,
        len(split_plan.modules),
    )

    # 4a. Inventory gate (issue #296) — every plan symbol must be locally
    # defined in the source file. Imported names (re-exports) and invented
    # names would otherwise reach the splitter as a generic "Symbols not
    # found in source AST" error after the LLM call has already been paid
    # for; catch them here with a precise message so retries don't keep
    # burning cycles on the same misclassification.
    imported_offenders, unknown_offenders = _validate_plan_against_inventory(
        split_plan, symbol_inventory
    )
    if imported_offenders or unknown_offenders:
        logger.error(
            "fix.modularity: plan references non-local symbols in %s "
            "(imported=%s, unknown=%s)",
            rel_path,
            imported_offenders,
            unknown_offenders,
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={
                "error": "plan references non-local symbols",
                "imported_in_plan": imported_offenders,
                "unknown_in_plan": unknown_offenders,
                "file": rel_path,
            },
            duration_sec=time.time() - start,
        )

    # 4b. Confidence gate — halt if LLM was insufficiently certain about the seam.
    confidence_threshold = _load_split_confidence_threshold(repo_root)
    if split_plan.confidence < confidence_threshold:
        logger.warning(
            "fix.modularity: low confidence split plan for %s "
            "(confidence=%.2f < threshold=%.2f) — aborting",
            rel_path,
            split_plan.confidence,
            confidence_threshold,
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={
                "error": "low_confidence",
                "confidence": split_plan.confidence,
                "threshold": confidence_threshold,
                "file": rel_path,
            },
            duration_sec=time.time() - start,
        )

    # 5. Phase 2 — deterministic split via ModularitySplitter
    logger.info(
        "fix.modularity: executing mechanical split of %s into %d modules",
        rel_path,
        len(split_plan.modules),
    )

    try:
        splitter = ModularitySplitter()
        split_result = splitter.split(source_path=target, plan=split_plan)
        files = [
            {"path": str(p.relative_to(repo_root)), "content": content}
            for p, content in split_result.files
        ]
    except SplitPlanError as e:
        logger.error("fix.modularity: split failed — %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"split failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    if not files:
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": "split produced no files", "file": rel_path},
            duration_sec=time.time() - start,
        )

    # 5a. Decorator Conservation Gate — fail fast before the LLM-backed
    # Logic Conservation Gate. Function bodies can be conserved while a
    # @register_action / @atomic_action decorator is silently dropped,
    # producing operationally broken output. See issue #211 / Failure 1
    # in CORE-ModularizationLessons.md.
    missing_decorators = _check_decorator_conservation(original_content, files)
    if missing_decorators:
        logger.error(
            "fix.modularity: decorator loss detected in %s: %s",
            rel_path,
            missing_decorators,
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={
                "error": "decorator_loss_detected",
                "missing_decorators": missing_decorators,
                "file": rel_path,
            },
            duration_sec=time.time() - start,
        )

    # 6. Logic Conservation Gate
    proposed_map = {f["path"]: f["content"] for f in files}
    try:
        conservation_validator = LogicConservationValidator()  # type: ignore[abstract]
        verdict = await conservation_validator.evaluate(
            original_code=original_content,
            proposed_map=proposed_map,
            deletions_authorized=False,
        )
    except Exception as e:
        logger.error("fix.modularity: Logic Conservation Gate failed: %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"conservation gate error: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    if not verdict.ok:
        ratio = verdict.data.get("ratio", 0.0)
        logger.error(
            "fix.modularity: logic evaporation in %s (ratio=%.2f) — aborting",
            rel_path,
            ratio,
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={
                "error": "logic_evaporation",
                "ratio": ratio,
                "file": rel_path,
            },
            duration_sec=time.time() - start,
        )

    # 7. Write files and delete original monolith
    if write:
        for file_info in files:
            core_context.file_handler.write_runtime_text(
                file_info["path"], file_info["content"]
            )
        logger.info(
            "fix.modularity: split complete — %d files written",
            len(files),
        )
        # Delete original monolith — the package __init__.py re-exports
        # all symbols so callers resolve without import-path changes.
        # Mirrors _execute_deterministic_split in the workflow path.
        if target.exists():
            core_context.file_handler.remove_file(rel_path)
            logger.info("fix.modularity: deleted original monolith %s", rel_path)

        # Issue #212 / Failure 2: invalidate stale .pyc so the daemon does
        # not serve the old monolith's bytecode (or stale bytecode under
        # the new package dir from previous failed runs) after restart.
        for invalidated in _invalidate_split_pycache(
            target, core_context.file_handler, repo_root
        ):
            try:
                logger.info(
                    "fix.modularity: invalidated stale bytecode %s",
                    invalidated.relative_to(repo_root),
                )
            except ValueError:
                logger.info(
                    "fix.modularity: invalidated stale bytecode %s", invalidated
                )
    else:
        logger.info(
            "fix.modularity: dry-run — would write %d files, delete %s",
            len(files),
            rel_path,
        )

    result_data = {
        "action": "split",
        "file": rel_path,
        "modules": len(split_plan.modules),
        "files_produced": [f["path"] for f in files],
        "files_count": len(files),
        "write": write,
    }
    if write:
        result_data["deleted_original"] = rel_path
    else:
        result_data["would_delete"] = rel_path

    return ActionResult(
        action_id="fix.modularity",
        ok=True,
        data=result_data,
        duration_sec=time.time() - start,
    )
