# src/body/self_healing/docstring_service.py

"""
AI-powered docstring healing — ADR-048 implementation.

Discovers public symbols missing docstrings via AST walk over the target
file (matches the ADR-047 ast_gate predicate). Generates docstrings via
PromptModel('docstring_writer'). Inserts via AST-position-based rewrite
through FileHandler.write_runtime_text — the governed mutation surface
used by every other fix.* action.

Constitutional alignment:
- AI invocation routes through PromptModel.invoke() — never direct
  make_request_async() (.intent/rules/ai/prompt_governance.json).
- File writes route through context.file_handler.write_runtime_text —
  the governed mutation surface.
- Symbol discovery predicate mirrors
  mind.logic.engines.ast_gate.checks.purity_checks.check_docstrings_present
  so detection and remediation converge on the same definition of
  "public symbol needing a docstring."
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# Audit rule scope (mirrors
# .intent/enforcement/mappings/code/purity.yaml#purity.docstrings.required).
# Sweep mode walks these directories; targeted mode uses an explicit
# file_path and ignores this list.
_SCOPE_DIRS: tuple[str, ...] = (
    "src/api",
    "src/cli/commands",
    "src/will/workers",
    "src/body/atomic",
)

# Placeholder-content rejection pattern. var/prompts/docstring_writer/system.txt
# rule #7 forbids FUTURE/PENDING/placeholder text; this is the post-generation
# enforcement that catches the case where the LLM disregards the rule. If the
# pattern matches we skip the symbol — inserting placeholder content would land
# a fresh `purity.no_todo_placeholders` violation and bounce the autonomous
# loop between gates.
_PLACEHOLDER_PATTERN = re.compile(r"\bTODO\b|\bFIXME\b|placeholder")


def _find_undocumented_public_symbols(
    tree: ast.AST,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
    """Walk a parsed module and return public symbols lacking a docstring.

    Public = name not starting with underscore. Symbol kinds covered:
    FunctionDef, AsyncFunctionDef, ClassDef — including methods and class
    declarations. Nested functions (functions whose immediate parent is
    itself a function) are excluded, mirroring the ADR-047 amendment to
    PurityChecks.check_docstrings_present (commit 6c1c7270). Nested
    classes are NOT excluded — only nested functions, matching the
    source-of-truth predicate exactly.
    """
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._parent = node  # type: ignore[attr-defined]

    candidates: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.name.startswith("_"):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = getattr(node, "_parent", None)
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
        if ast.get_docstring(node) is not None:
            continue
        candidates.append(node)
    return candidates


def _insert_docstrings(
    source: str,
    insertions: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, str]],
) -> str:
    """Insert generated docstrings at AST-determined positions.

    Logic ported from body/workers/doc_writer.py:_insert_docstring (retired
    under ADR-048 D3). Each insertion is (node, docstring); the docstring
    is placed at the position of body[0] with indentation
    `" " * (node.col_offset + 4)`. Insertions are processed bottom-to-top
    so earlier line numbers stay valid.
    """
    if not insertions:
        return source

    lines = source.splitlines(keepends=True)
    targets: list[tuple[int, str, str]] = []

    for node, docstring in insertions:
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        # Defensive: skip if a docstring snuck in between detection and write.
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            continue
        insert_line = first.lineno - 1  # 1-indexed AST → 0-indexed line list
        indent = " " * (node.col_offset + 4)
        targets.append((insert_line, indent, docstring))

    for insert_line, indent, docstring in sorted(
        targets, key=lambda t: t[0], reverse=True
    ):
        # The docstring_writer PromptModel contract requires the model to
        # include the surrounding triple-quote delimiters in its output
        # (model.yaml: output.must_contain: ['"""']; user.txt: "Start your
        # response directly with triple double-quotes"). Wrapping again here
        # would produce """"""...""""""  — invalid Python. See issue #334.
        doc_line = f"{indent}{docstring}\n"
        lines.insert(insert_line, doc_line)

    return "".join(lines)


async def _heal_file(
    context: CoreContext,
    file_path: str,
    dry_run: bool,
    prompt_model: PromptModel,
    writer_client: Any,
) -> int:
    """Heal a single file. Returns the count of docstrings inserted."""
    repo_path = Path(context.git_service.repo_path)
    full_path = repo_path / file_path
    if not full_path.exists():
        logger.warning("fix.docstrings: file not found: %s", file_path)
        return 0

    source = full_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        logger.warning("fix.docstrings: cannot parse %s: %s", file_path, e)
        return 0

    candidates = _find_undocumented_public_symbols(tree)
    if not candidates:
        logger.info(
            "fix.docstrings: %s — all public symbols have docstrings.",
            file_path,
        )
        return 0

    logger.info(
        "fix.docstrings: %s — found %d symbol(s) requiring docstrings.",
        file_path,
        len(candidates),
    )

    insertions: list[
        tuple[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, str]
    ] = []
    for node in candidates:
        node_source = ast.get_source_segment(source, node)
        if not node_source:
            continue
        try:
            new_doc = await prompt_model.invoke(
                context={"source_code": node_source},
                client=writer_client,
                user_id="docstring_healing_service",
            )
        except ValueError as e:
            logger.warning(
                "fix.docstrings: PromptModel output validation failed for "
                "'%s' at %s:%d: %s",
                node.name,
                file_path,
                node.lineno,
                e,
            )
            continue
        except Exception as e:
            logger.error(
                "fix.docstrings: error generating docstring for '%s' at %s:%d: %s",
                node.name,
                file_path,
                node.lineno,
                e,
            )
            continue

        if not new_doc:
            continue
        # Reject placeholder content (system.txt rule #7). Inserting would
        # produce a fresh purity.no_todo_placeholders violation and bounce
        # the autonomous loop between gates.
        if _PLACEHOLDER_PATTERN.search(new_doc):
            logger.warning(
                "fix.docstrings: rejecting placeholder content for '%s' at "
                "%s:%d (matched FUTURE/PENDING/placeholder).",
                node.name,
                file_path,
                node.lineno,
            )
            continue
        insertions.append((node, new_doc.strip()))

    if not insertions:
        logger.info("fix.docstrings: %s — no docstrings generated.", file_path)
        return 0

    updated = _insert_docstrings(source, insertions)

    # Validate the would-be source before any write. Catches malformed
    # docstring generation (the failure mode in #334) before commit. In
    # dry-run mode this is the only verification path; in write mode it
    # is a belt-and-braces check before FileHandler hands off to the
    # post-write validator.
    try:
        ast.parse(updated)
    except SyntaxError as e:
        logger.error(
            "fix.docstrings: %s — generated source fails ast.parse: %s",
            file_path,
            e,
        )
        return 0

    if dry_run:
        logger.info(
            "[DRY RUN] %s — would write %d docstring(s) (ast.parse: OK).",
            file_path,
            len(insertions),
        )
        return 0

    context.file_handler.write_runtime_text(file_path, updated)
    logger.info(
        "fix.docstrings: %s — wrote %d docstring(s).",
        file_path,
        len(insertions),
    )
    return len(insertions)


def _iter_scope_files(repo_path: Path) -> list[str]:
    """Yield repo-relative .py files in the audit rule's scope.

    Mirrors purity.docstrings.required.scope from the enforcement mapping:
    applies_to = _SCOPE_DIRS; excludes = __init__.py.
    """
    paths: list[str] = []
    for scope_dir in _SCOPE_DIRS:
        base = repo_path / scope_dir
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if p.name == "__init__.py":
                continue
            paths.append(str(p.relative_to(repo_path)))
    return paths


async def _async_fix_docstrings(
    context: CoreContext,
    dry_run: bool,
    limit: int = 0,
    file_path: str | None = None,
) -> None:
    """Heal missing docstrings via AST walk and PromptModel generation.

    Two invocation modes:

    1. Targeted (autonomous loop): caller supplies ``file_path``. Heal
       that one file. ProposalExecutor expands
       ``actions[i].parameters.file_path`` into this argument.
    2. Sweep (legacy CLI): ``file_path`` is None. Walk every .py file
       under _SCOPE_DIRS, healing each one.

    The knowledge graph is no longer consulted (ADR-048). The audit-gate
    predicate (ast.get_docstring on public defs/classes) is the single
    source of truth for "needs a docstring."
    """
    prompt_model = PromptModel.load("docstring_writer")
    writer_client = await context.cognitive_service.aget_client_for_role(
        prompt_model.manifest.role
    )
    repo_path = Path(context.git_service.repo_path)

    if file_path:
        normalized = file_path.lstrip("./").replace("\\", "/")
        await _heal_file(context, normalized, dry_run, prompt_model, writer_client)
        return

    files = _iter_scope_files(repo_path)
    if limit > 0:
        files = files[:limit]

    total_inserted = 0
    files_touched = 0
    for fp in files:
        inserted = await _heal_file(context, fp, dry_run, prompt_model, writer_client)
        if inserted > 0:
            files_touched += 1
            total_inserted += inserted

    logger.info(
        "fix.docstrings: sweep complete — inserted %d docstring(s) across "
        "%d file(s) out of %d scanned.",
        total_inserted,
        files_touched,
        len(files),
    )


# ID: f74db998-8680-40b8-bd62-e6495b5d6df3
async def fix_docstrings(
    context: CoreContext,
    write: bool = False,
    limit: int = 0,
    file_path: str | None = None,
) -> None:
    """Public entry point for the docstring healing self-healing command.

    Args:
        context: CoreContext with file_handler, cognitive_service, git_service.
        write: When True, persists changes. When False, dry-run only.
        limit: Max files to process in sweep mode. 0 means no limit.
            Ignored when ``file_path`` is set.
        file_path: When supplied, heal only that repo-relative file.
            None preserves the legacy whole-tree sweep over _SCOPE_DIRS.
    """
    await _async_fix_docstrings(
        context=context, dry_run=not write, limit=limit, file_path=file_path
    )
