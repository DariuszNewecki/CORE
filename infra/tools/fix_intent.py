#!/usr/bin/env python3
"""
fix_intent.py — Autonomous Docstring Writer for CORE

Standalone tool. Zero CORE dependencies. Uses local Qwen2.5-coder via Ollama
to generate missing method/class docstrings.

Usage:
    python infra/tools/fix_intent.py src/will/self_healing/alignment_orchestrator.py
    python infra/tools/fix_intent.py src/will/                 # directory
    python infra/tools/fix_intent.py src/                      # full repo
    python infra/tools/fix_intent.py src/ --write              # actually write
    python infra/tools/fix_intent.py src/ --stale              # also fix stale docs
    python infra/tools/fix_intent.py src/ --write --stale      # write + stale

Dry-run by default. Use --write to apply changes.

Integration note:
    Core logic lives in pure functions (find_missing_docstrings, generate_docstring,
    insert_docstring) — extractable as body/atomic/actions/fix_intent.py later.
    CLI wrapper is ~40 lines at the bottom.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://192.168.20.100:11434/api/generate"
MODEL = "qwen2.5-coder:3b-instruct-q4_k_m"
TIMEOUT = 120


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class MissingDoc:
    """A symbol that needs a docstring written."""

    name: str
    kind: str  # class / function / method
    line: int  # 1-based line of def/class statement
    body_line: int  # 1-based line where body starts (after colon)
    indent: str  # indentation of the def/class line
    snippet: str  # code snippet for context
    existing_doc: str  # non-empty if stale (to be replaced)


@dataclass
class FixResult:
    """Result of processing one file."""

    path: str
    fixed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    written: bool = False


# ---------------------------------------------------------------------------
# AST analysis — find symbols missing docstrings
# ---------------------------------------------------------------------------


def find_missing_docstrings(
    source: str,
    include_stale: bool = False,
) -> list[MissingDoc]:
    """
    Find all public symbols (class/function/method) that lack docstrings.

    If include_stale=True, also returns symbols whose existing docstring
    is very short (<20 chars) — likely placeholder text.

    Pure function — no I/O.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    lines = source.splitlines()
    missing: list[MissingDoc] = []

    def _indent(line_no: int) -> str:
        """Extract leading whitespace from a 1-based line number."""
        raw = lines[line_no - 1] if line_no <= len(lines) else ""
        return raw[: len(raw) - len(raw.lstrip())]

    def _snippet(node: ast.AST, max_lines: int = 20) -> str:
        start = node.lineno - 1
        end = min(start + max_lines, len(lines))
        return "\n".join(lines[start:end])

    def _body_start_line(node: ast.AST) -> int:
        """Line where we insert the docstring (first line of body)."""
        if node.body:
            first = node.body[0]
            # If first statement is already a docstring, use its line
            return first.lineno
        return node.lineno + 1

    def _visit(node: ast.AST, parent: str = "") -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_") and not node.name.startswith("__"):
                return  # skip private, keep dunders

            full_name = f"{parent}.{node.name}" if parent else node.name
            existing = ast.get_docstring(node) or ""

            needs_fix = False
            if not existing:
                needs_fix = True
            elif include_stale and len(existing.strip()) < 20:
                needs_fix = True

            if needs_fix:
                missing.append(
                    MissingDoc(
                        name=full_name,
                        kind="method" if parent else "function",
                        line=node.lineno,
                        body_line=_body_start_line(node),
                        indent=_indent(node.lineno),
                        snippet=_snippet(node),
                        existing_doc=existing,
                    )
                )

            # Visit methods inside functions (rare but valid)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _visit(child, parent=full_name)

        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                return

            existing = ast.get_docstring(node) or ""
            needs_fix = False
            if not existing:
                needs_fix = True
            elif include_stale and len(existing.strip()) < 20:
                needs_fix = True

            if needs_fix:
                missing.append(
                    MissingDoc(
                        name=node.name,
                        kind="class",
                        line=node.lineno,
                        body_line=_body_start_line(node),
                        indent=_indent(node.lineno),
                        snippet=_snippet(node, 15),
                        existing_doc=existing,
                    )
                )

            # Visit class body
            for child in node.body:
                _visit(child, parent=node.name)

    for node in ast.iter_child_nodes(tree):
        _visit(node)

    return missing


# ---------------------------------------------------------------------------
# Ollama — generate docstring
# ---------------------------------------------------------------------------


def ask_ollama(prompt: str) -> str:
    """Send prompt to Ollama, return raw text response."""
    payload = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 200,
            },
        }
    ).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data.get("response", "").strip()
    except Exception as e:
        return f"ERROR: {e}"


def generate_docstring(symbol: MissingDoc) -> str | None:
    """
    Ask Qwen to write a docstring for the given symbol.

    Returns the docstring text (without triple-quotes) or None on failure.
    Pure function except for the Ollama HTTP call.
    """
    replace_hint = (
        f'\n\nExisting (too vague, replace): "{symbol.existing_doc}"'
        if symbol.existing_doc
        else ""
    )

    short_name = symbol.name.split(".")[-1]
    prompt = f"""Write a docstring for the Python {symbol.kind} `{short_name}`.

```python
{symbol.snippet}
```

Output ONLY plain English text. Hard rules:
- First line: one sentence saying what this {symbol.kind} does
- Add Args/Returns sections only if non-obvious
- Maximum 5 lines total
- Do NOT include the function/class name, signature, or any Python code
- Do NOT include def, class, self, async, or any keywords
- Do NOT include triple quotes or backticks
- Plain English only, nothing else"""

    response = ask_ollama(prompt)

    if response.startswith("ERROR:"):
        return None

    # Strip any accidental triple quotes or markdown fences
    cleaned = response.strip()
    # Remove all triple-quote variants
    cleaned = cleaned.replace('"""', "").replace("'''", "")
    # Remove markdown fences
    cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"```", "", cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return None

    return cleaned


# ---------------------------------------------------------------------------
# File modification — insert docstring
# ---------------------------------------------------------------------------


def insert_docstring(
    source: str,
    symbol: MissingDoc,
    docstring_text: str,
) -> str:
    """
    Insert (or replace) a docstring in source code.

    Uses line-based insertion: finds the def/class line, locates
    the first line of the body, inserts triple-quoted docstring there.

    Pure function — takes source string, returns modified source string.
    """
    lines = source.splitlines(keepends=True)
    method_indent = symbol.indent
    doc_indent = method_indent + "    "

    # Format the docstring
    text_lines = docstring_text.strip().splitlines()
    if len(text_lines) == 1:
        # Single line: """Summary."""
        doc_block = f'{doc_indent}"""{text_lines[0].strip()}"""\n'
    else:
        # Multi-line
        doc_parts = [f'{doc_indent}"""{text_lines[0].strip()}\n']
        for tl in text_lines[1:]:
            doc_parts.append(f"{doc_indent}{tl.strip()}\n")
        doc_parts.append(f'{doc_indent}"""\n')
        doc_block = "".join(doc_parts)

    # Find insertion point
    insert_at = symbol.body_line - 1  # 0-based index

    if symbol.existing_doc:
        # Replace existing docstring: find and remove the old one
        # Look for the triple-quote block starting at body_line
        i = insert_at
        if i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                quote = '"""' if stripped.startswith('"""') else "'''"
                # Single-line docstring
                if stripped.endswith(quote) and len(stripped) > 6:
                    lines[i] = doc_block
                    return "".join(lines)
                # Multi-line: find closing
                j = i + 1
                while j < len(lines) and quote not in lines[j]:
                    j += 1
                # Remove lines[i..j] inclusive, insert new
                lines[i : j + 1] = [doc_block]
                return "".join(lines)

    # Insert before body_line
    lines.insert(insert_at, doc_block)
    return "".join(lines)


# ---------------------------------------------------------------------------
# File processor
# ---------------------------------------------------------------------------


def process_file(
    path: Path,
    write: bool = False,
    include_stale: bool = False,
    verbose: bool = False,
) -> FixResult:
    """
    Process a single Python file: find missing docstrings, generate, optionally write.

    This is the main integration point for CORE's atomic action wrapper.
    Returns a FixResult with details of what was done.
    """
    result = FixResult(path=str(path))

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        result.errors.append(f"Read error: {e}")
        return result

    missing = find_missing_docstrings(source, include_stale=include_stale)

    if not missing:
        return result

    # Process bottom-to-top so earlier line numbers stay valid
    missing.sort(key=lambda s: s.line, reverse=True)

    current_source = source

    for sym in missing:
        if verbose:
            print(
                f"     → generating docstring for {sym.kind} {sym.name}...", flush=True
            )

        docstring = generate_docstring(sym)

        if docstring is None:
            result.errors.append(f"{sym.name}: LLM failed")
            result.skipped.append(sym.name)
            continue

        try:
            new_source = insert_docstring(current_source, sym, docstring)
            ast.parse(new_source)  # Validate — reject if broken
            current_source = new_source
            result.fixed.append(sym.name)
        except SyntaxError as e:
            result.errors.append(f"{sym.name}: insertion broke syntax ({e})")
            result.skipped.append(sym.name)

    if result.fixed and write:
        try:
            path.write_text(current_source, encoding="utf-8")
            result.written = True
        except Exception as e:
            result.errors.append(f"Write error: {e}")

    return result


def collect_files(target: Path) -> list[Path]:
    """Collect Python files from target path."""
    if target.is_file():
        return [target] if target.suffix == ".py" else []

    return sorted(
        [
            p
            for p in target.rglob("*.py")
            if not any(
                part in p.parts
                for part in (
                    "__pycache__",
                    ".venv",
                    "venv",
                    ".git",
                    "var",
                    "work",
                )
            )
        ]
    )


# ---------------------------------------------------------------------------
# Connectivity check
# ---------------------------------------------------------------------------


def check_ollama() -> bool:
    """Verify Ollama is reachable."""
    print(f"🔌 Checking Ollama ({MODEL})...")
    response = ask_ollama('Say "ok" and nothing else.')
    if response.startswith("ERROR:"):
        print(f"   ❌ {response}")
        print(f"   ollama serve  |  ollama pull {MODEL}")
        return False
    print("   ✅ Ollama reachable\n")
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    target = Path(args[0])
    write = "--write" in args
    include_stale = "--stale" in args
    verbose = "--verbose" in args or "-v" in args

    if not target.exists():
        print(f"Error: {target} does not exist")
        sys.exit(1)

    if not check_ollama():
        sys.exit(1)

    files = collect_files(target)
    if not files:
        print("No Python files found.")
        sys.exit(0)

    mode = "WRITE" if write else "DRY-RUN"
    stale_note = " + stale" if include_stale else ""
    print(f"✏️  fix_intent [{mode}] — missing{stale_note} docstrings")
    print(f"   {len(files)} file(s) to process\n")

    start = time.time()
    total_fixed = 0
    total_skipped = 0
    total_errors = 0
    changed_files: list[FixResult] = []

    for i, f in enumerate(files, 1):
        rel = f if not f.is_absolute() else f.relative_to(Path.cwd())
        result = process_file(
            f, write=write, include_stale=include_stale, verbose=verbose
        )

        if result.fixed or result.errors:
            status = "✅" if not result.errors else "⚠️ "
            written_note = (
                " [written]" if result.written else " [dry-run]" if result.fixed else ""
            )
            print(
                f"   [{i:3d}/{len(files)}] {rel}"
                f" → {len(result.fixed)} fixed, {len(result.skipped)} skipped"
                f"{written_note}"
            )
            if result.errors and verbose:
                for err in result.errors:
                    print(f"              ⚠️  {err}")
            if result.fixed:
                changed_files.append(result)
        else:
            if verbose:
                print(f"   [{i:3d}/{len(files)}] {rel} → no missing docstrings")

        total_fixed += len(result.fixed)
        total_skipped += len(result.skipped)
        total_errors += len(result.errors)

    elapsed = time.time() - start

    print()
    print("━" * 70)
    print(f"  Completed in {elapsed:.1f}s")
    print(f"  Docstrings generated : {total_fixed}")
    print(f"  Skipped (LLM error)  : {total_skipped}")
    print(f"  Errors               : {total_errors}")
    if not write and total_fixed > 0:
        print(f"\n  Re-run with --write to apply {total_fixed} docstring(s)")
    print("━" * 70)

    # Integration hint: these results map directly to ActionResult in CORE
    # FixResult.fixed → action succeeded symbols
    # FixResult.errors → action failed symbols
    # FixResult.written → action had side effects


if __name__ == "__main__":
    main()
