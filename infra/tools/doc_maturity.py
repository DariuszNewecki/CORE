#!/usr/bin/env python3
"""
doc_maturity.py — Documentation Maturity Analyzer for CORE

Standalone tool. Zero CORE dependencies. Uses local Qwen2.5-coder via Ollama
to assess documentation quality beyond simple presence checks.

Usage:
    python infra/tools/doc_maturity.py src/cli/admin_cli.py     # single file
    python infra/tools/doc_maturity.py src/cli                  # directory
    python infra/tools/doc_maturity.py src/                     # full repo

Output:
    - Console: summary table with tiers per file
    - reports/doc_maturity/report.json
    - reports/doc_maturity/report.html

Tiers:
    MATURE  (>80)  — docstring accurate and complete
    PARTIAL (50-80) — docstring exists but incomplete
    STALE   (<50)  — docstring exists but misleading/outdated
    MISSING        — no docstring at all
"""

from __future__ import annotations

import ast
import json
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://192.168.20.100:11434/api/generate"
MODEL = "qwen2.5-coder:3b-instruct-q4_k_m"
REPORTS_DIR = Path("reports/doc_maturity")

TIER_MATURE = "MATURE"
TIER_PARTIAL = "PARTIAL"
TIER_STALE = "STALE"
TIER_MISSING = "MISSING"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SymbolResult:
    name: str
    kind: str  # function / class / method
    line: int
    has_docstring: bool
    score: int  # 0-100, 0 if missing
    tier: str
    issues: list[str] = field(default_factory=list)
    suggestion: str = ""


@dataclass
class FileResult:
    path: str
    symbols: list[SymbolResult] = field(default_factory=list)
    file_score: int = 0
    tier: str = TIER_MISSING
    error: str = ""

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)

    @property
    def missing_count(self) -> int:
        return sum(1 for s in self.symbols if s.tier == TIER_MISSING)

    @property
    def stale_count(self) -> int:
        return sum(1 for s in self.symbols if s.tier == TIER_STALE)

    @property
    def mature_count(self) -> int:
        return sum(1 for s in self.symbols if s.tier == TIER_MATURE)


# ---------------------------------------------------------------------------
# AST extraction
# ---------------------------------------------------------------------------


def extract_symbols(source: str) -> list[dict]:
    """Extract public functions, classes, methods with their docstrings."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    symbols = []
    lines = source.splitlines()

    def _get_source_snippet(node: ast.AST, max_lines: int = 30) -> str:
        start = node.lineno - 1
        end = min(start + max_lines, len(lines))
        return "\n".join(lines[start:end])

    def _visit(node: ast.AST, parent: str = "") -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_") and not node.name.startswith("__"):
                return  # skip private, keep dunder
            docstring = ast.get_docstring(node) or ""
            kind = "method" if parent else "function"
            symbols.append(
                {
                    "name": f"{parent}.{node.name}" if parent else node.name,
                    "kind": kind,
                    "line": node.lineno,
                    "docstring": docstring,
                    "snippet": _get_source_snippet(node),
                }
            )
            for child in ast.walk(node):
                if child is not node and isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    pass  # don't recurse into nested functions

        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                return
            docstring = ast.get_docstring(node) or ""
            symbols.append(
                {
                    "name": node.name,
                    "kind": "class",
                    "line": node.lineno,
                    "docstring": docstring,
                    "snippet": _get_source_snippet(node, 15),
                }
            )
            for child in node.body:
                _visit(child, parent=node.name)

    for node in ast.iter_child_nodes(tree):
        _visit(node)

    return symbols


# ---------------------------------------------------------------------------
# Ollama LLM call
# ---------------------------------------------------------------------------


def ask_ollama(prompt: str, timeout: int = 30) -> str:
    """Send prompt to local Ollama and return the response text."""
    payload = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 256,
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("response", "").strip()
    except Exception as e:
        return f"ERROR: {e}"


def assess_symbol(symbol: dict, debug: bool = False) -> SymbolResult:
    """Ask LLM to rate documentation maturity of a single symbol."""
    docstring = symbol["docstring"]
    snippet = symbol["snippet"]
    name = symbol["name"]
    kind = symbol["kind"]

    if not docstring:
        return SymbolResult(
            name=name,
            kind=kind,
            line=symbol["line"],
            has_docstring=False,
            score=0,
            tier=TIER_MISSING,
            issues=["No docstring present"],
        )

    prompt = f"""You are a code documentation reviewer. Assess this Python {kind}'s documentation.

CODE:
```python
{snippet}
```

DOCSTRING:
"{docstring}"

Rate the documentation maturity from 0-100 based on:
- Does the docstring accurately describe what the code ACTUALLY does? (most important)
- Is it complete (params, return, exceptions where relevant)?
- Is it specific or vague/generic?
- Would a new developer understand the code from this alone?

Respond ONLY with valid JSON, no other text:
{{"score": <0-100>, "issues": ["issue1", "issue2"], "suggestion": "one sentence improvement"}}

If score >= 80: documentation is accurate and complete.
If score 50-79: exists but incomplete or slightly inaccurate.
If score < 50: exists but stale, misleading, or too vague to be useful."""

    response = ask_ollama(prompt)

    if debug:
        print(f"\n[DEBUG] Raw response for {name}:\n{response}\n")

    # Parse JSON response
    try:
        # Strip markdown fences if present
        raw = response.strip()
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break
        # Find first JSON object if there's extra text
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]
        data = json.loads(raw)
        score = max(0, min(100, int(data.get("score", 0))))
        issues = data.get("issues", [])
        suggestion = data.get("suggestion", "")
    except Exception as e:
        if debug:
            print(f"[DEBUG] Parse error: {e}")
        score = 0
        issues = [f"LLM parse error: {response[:120]}"]
        suggestion = ""

    if score >= 80:
        tier = TIER_MATURE
    elif score >= 50:
        tier = TIER_PARTIAL
    else:
        tier = TIER_STALE

    return SymbolResult(
        name=name,
        kind=kind,
        line=symbol["line"],
        has_docstring=True,
        score=score,
        tier=tier,
        issues=issues,
        suggestion=suggestion,
    )


# ---------------------------------------------------------------------------
# File analysis
# ---------------------------------------------------------------------------


def analyse_file(path: Path, debug: bool = False) -> FileResult:
    """Analyse a single Python file."""
    result = FileResult(path=str(path))

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        result.error = str(e)
        return result

    symbols = extract_symbols(source)

    if not symbols:
        result.tier = TIER_MATURE  # no public symbols = nothing to document
        result.file_score = 100
        return result

    for sym in symbols:
        sym_result = assess_symbol(sym, debug=debug)
        result.symbols.append(sym_result)

    scored = [s for s in result.symbols if s.has_docstring]
    missing = [s for s in result.symbols if not s.has_docstring]

    if scored:
        avg_score = sum(s.score for s in scored) / len(scored)
        # Missing docstrings pull the file score down
        penalty = len(missing) / len(result.symbols)
        result.file_score = int(avg_score * (1 - penalty))
    else:
        result.file_score = 0

    if result.file_score >= 80:
        result.tier = TIER_MATURE
    elif result.file_score >= 50:
        result.tier = TIER_PARTIAL
    elif result.missing_count == len(result.symbols):
        result.tier = TIER_MISSING
    else:
        result.tier = TIER_STALE

    return result


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def collect_files(target: Path) -> list[Path]:
    """Collect all Python files from target (file, directory, or src/)."""
    if target.is_file():
        return [target] if target.suffix == ".py" else []

    files = [
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
    return sorted(files)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

TIER_COLORS = {
    TIER_MATURE: "#22c55e",
    TIER_PARTIAL: "#f59e0b",
    TIER_STALE: "#ef4444",
    TIER_MISSING: "#6b7280",
}

TIER_BG = {
    TIER_MATURE: "#052e16",
    TIER_PARTIAL: "#451a03",
    TIER_STALE: "#450a0a",
    TIER_MISSING: "#111827",
}


def print_console_report(results: list[FileResult]) -> None:
    """Print a readable summary to stdout."""
    total = len(results)
    if total == 0:
        print("No Python files found.")
        return

    counts = {TIER_MATURE: 0, TIER_PARTIAL: 0, TIER_STALE: 0, TIER_MISSING: 0}
    for r in results:
        counts[r.tier] += 1

    print()
    print("━" * 80)
    print("  DOCUMENTATION MATURITY REPORT")
    print("━" * 80)
    print(f"  Files analysed : {total}")
    print(
        f"  ✅ MATURE       : {counts[TIER_MATURE]} ({counts[TIER_MATURE]*100//total}%)"
    )
    print(
        f"  🟡 PARTIAL      : {counts[TIER_PARTIAL]} ({counts[TIER_PARTIAL]*100//total}%)"
    )
    print(
        f"  🔴 STALE        : {counts[TIER_STALE]} ({counts[TIER_STALE]*100//total}%)"
    )
    print(
        f"  ⬜ MISSING      : {counts[TIER_MISSING]} ({counts[TIER_MISSING]*100//total}%)"
    )
    print("━" * 80)
    print()

    # Sort by score ascending (worst first)
    sorted_results = sorted(results, key=lambda r: r.file_score)

    tier_icon = {
        TIER_MATURE: "✅",
        TIER_PARTIAL: "🟡",
        TIER_STALE: "🔴",
        TIER_MISSING: "⬜",
    }

    for r in sorted_results:
        icon = tier_icon[r.tier]
        score_str = f"{r.file_score:3d}%" if r.file_score else "  0%"
        symbols_str = f"{r.symbol_count} symbols"
        print(f"  {icon} {score_str}  {r.path:<60} {symbols_str}")
        if r.error:
            print(f"       ERROR: {r.error}")

    print()
    print("  Full report: reports/doc_maturity/report.html")
    print("━" * 80)
    print()


def generate_html_report(results: list[FileResult], target: str) -> str:
    """Generate a dark, terminal-aesthetic HTML report."""
    total = len(results)
    counts = {TIER_MATURE: 0, TIER_PARTIAL: 0, TIER_STALE: 0, TIER_MISSING: 0}
    for r in results:
        counts[r.tier] += 1

    overall_score = int(sum(r.file_score for r in results) / total) if total else 0

    sorted_results = sorted(results, key=lambda r: r.file_score)

    def file_row(r: FileResult) -> str:
        color = TIER_COLORS[r.tier]
        symbols_html = ""
        for s in sorted(r.symbols, key=lambda x: x.score):
            s_color = TIER_COLORS[s.tier]
            issues_html = "".join(f"<li>{i}</li>" for i in s.issues) if s.issues else ""
            symbols_html += f"""
            <div class="symbol" style="border-left: 3px solid {s_color}">
                <div class="symbol-header">
                    <span class="symbol-name">{s.name}</span>
                    <span class="symbol-kind">{s.kind}</span>
                    <span class="symbol-score" style="color:{s_color}">
                        {"MISSING" if not s.has_docstring else f"{s.score}%"}
                    </span>
                </div>
                {f'<ul class="issues">{issues_html}</ul>' if issues_html else ""}
                {f'<div class="suggestion">💡 {s.suggestion}</div>' if s.suggestion else ""}
            </div>"""

        return f"""
        <div class="file-card" onclick="this.classList.toggle('open')">
            <div class="file-header">
                <div class="file-path">
                    <span class="tier-badge" style="background:{color}20;color:{color};border:1px solid {color}40">
                        {r.tier}
                    </span>
                    <span class="path">{r.path}</span>
                </div>
                <div class="file-meta">
                    <span class="score" style="color:{color}">{r.file_score}%</span>
                    <span class="sym-count">{r.symbol_count} symbols</span>
                    <span class="chevron">▶</span>
                </div>
            </div>
            <div class="file-body">
                {symbols_html if symbols_html else '<p class="no-symbols">No public symbols found</p>'}
            </div>
        </div>"""

    files_html = "\n".join(file_row(r) for r in sorted_results)

    bar_mature = counts[TIER_MATURE] * 100 // total if total else 0
    bar_partial = counts[TIER_PARTIAL] * 100 // total if total else 0
    bar_stale = counts[TIER_STALE] * 100 // total if total else 0
    bar_missing = counts[TIER_MISSING] * 100 // total if total else 0

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CORE — Documentation Maturity</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600&family=Syne:wght@400;700;800&display=swap');

  :root {{
    --bg: #080b0f;
    --surface: #0d1117;
    --border: #1e2a3a;
    --text: #c9d1d9;
    --dim: #4a5568;
    --mature: #22c55e;
    --partial: #f59e0b;
    --stale: #ef4444;
    --missing: #4a5568;
    --accent: #38bdf8;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'JetBrains Mono', monospace;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 2rem;
  }}

  header {{
    border-bottom: 1px solid var(--border);
    padding-bottom: 2rem;
    margin-bottom: 2rem;
  }}

  .title {{
    font-family: 'Syne', sans-serif;
    font-size: 2.5rem;
    font-weight: 800;
    color: #fff;
    letter-spacing: -0.02em;
  }}

  .subtitle {{
    color: var(--dim);
    font-size: 0.85rem;
    margin-top: 0.5rem;
  }}

  .meta {{
    color: var(--accent);
    font-size: 0.8rem;
    margin-top: 0.25rem;
  }}

  .overview {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
    gap: 1rem;
    margin-bottom: 2rem;
  }}

  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem;
  }}

  .stat-label {{
    font-size: 0.7rem;
    color: var(--dim);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
  }}

  .stat-value {{
    font-size: 2rem;
    font-weight: 600;
    font-family: 'Syne', sans-serif;
  }}

  .stat-sub {{
    font-size: 0.75rem;
    color: var(--dim);
    margin-top: 0.25rem;
  }}

  .progress-bar {{
    display: flex;
    height: 8px;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 2rem;
    gap: 2px;
  }}

  .progress-segment {{
    height: 100%;
    transition: width 0.5s ease;
  }}

  .legend {{
    display: flex;
    gap: 2rem;
    margin-bottom: 2rem;
    font-size: 0.8rem;
  }}

  .legend-item {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--dim);
  }}

  .legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }}

  .files-list {{
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }}

  .file-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.2s;
  }}

  .file-card:hover {{
    border-color: var(--accent);
  }}

  .file-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    gap: 1rem;
  }}

  .file-path {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 0;
  }}

  .tier-badge {{
    font-size: 0.65rem;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    white-space: nowrap;
    font-weight: 600;
    letter-spacing: 0.05em;
  }}

  .path {{
    font-size: 0.8rem;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}

  .file-meta {{
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-shrink: 0;
    font-size: 0.8rem;
  }}

  .score {{
    font-weight: 600;
    font-size: 1rem;
    min-width: 3rem;
    text-align: right;
  }}

  .sym-count {{
    color: var(--dim);
    white-space: nowrap;
  }}

  .chevron {{
    color: var(--dim);
    transition: transform 0.2s;
    font-size: 0.7rem;
  }}

  .file-card.open .chevron {{
    transform: rotate(90deg);
  }}

  .file-body {{
    display: none;
    padding: 0 1rem 1rem;
    border-top: 1px solid var(--border);
  }}

  .file-card.open .file-body {{
    display: block;
  }}

  .symbol {{
    padding: 0.75rem;
    margin-top: 0.75rem;
    background: var(--bg);
    border-radius: 4px;
    padding-left: 1rem;
  }}

  .symbol-header {{
    display: flex;
    align-items: center;
    gap: 1rem;
  }}

  .symbol-name {{
    font-weight: 600;
    color: #fff;
    font-size: 0.85rem;
  }}

  .symbol-kind {{
    font-size: 0.7rem;
    color: var(--dim);
    background: #1e2a3a;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
  }}

  .symbol-score {{
    font-size: 0.85rem;
    font-weight: 600;
    margin-left: auto;
  }}

  .issues {{
    margin-top: 0.5rem;
    padding-left: 1rem;
    font-size: 0.75rem;
    color: var(--dim);
    list-style: disc;
  }}

  .issues li {{
    margin-top: 0.2rem;
  }}

  .suggestion {{
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: var(--accent);
    opacity: 0.8;
  }}

  .no-symbols {{
    color: var(--dim);
    font-size: 0.8rem;
    padding-top: 0.75rem;
    font-style: italic;
  }}

  footer {{
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--dim);
    font-size: 0.75rem;
    text-align: center;
  }}
</style>
</head>
<body>

<header>
  <div class="title">Documentation Maturity</div>
  <div class="subtitle">Target: <code>{target}</code></div>
  <div class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} · Model: {MODEL}</div>
</header>

<div class="overview">
  <div class="stat-card">
    <div class="stat-label">Overall Score</div>
    <div class="stat-value" style="color:{'#22c55e' if overall_score>=80 else '#f59e0b' if overall_score>=50 else '#ef4444'}">{overall_score}%</div>
    <div class="stat-sub">across {total} files</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Mature</div>
    <div class="stat-value" style="color:#22c55e">{counts[TIER_MATURE]}</div>
    <div class="stat-sub">{bar_mature}% of files</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Partial</div>
    <div class="stat-value" style="color:#f59e0b">{counts[TIER_PARTIAL]}</div>
    <div class="stat-sub">{bar_partial}% of files</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Stale</div>
    <div class="stat-value" style="color:#ef4444">{counts[TIER_STALE]}</div>
    <div class="stat-sub">{bar_stale}% of files</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Missing</div>
    <div class="stat-value" style="color:#4a5568">{counts[TIER_MISSING]}</div>
    <div class="stat-sub">{bar_missing}% of files</div>
  </div>
</div>

<div class="progress-bar">
  <div class="progress-segment" style="width:{bar_mature}%;background:#22c55e"></div>
  <div class="progress-segment" style="width:{bar_partial}%;background:#f59e0b"></div>
  <div class="progress-segment" style="width:{bar_stale}%;background:#ef4444"></div>
  <div class="progress-segment" style="width:{bar_missing}%;background:#1e2a3a"></div>
</div>

<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#22c55e"></div>MATURE (>80%)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div>PARTIAL (50-80%)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div>STALE (&lt;50%)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#1e2a3a;border:1px solid #4a5568"></div>MISSING</div>
</div>

<div class="files-list">
{files_html}
</div>

<footer>
  CORE Documentation Maturity Analyzer · infra/tools/doc_maturity.py
</footer>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def check_ollama() -> bool:
    """Verify Ollama is reachable and the model responds."""
    print(f"🔌 Checking Ollama ({MODEL})...")
    response = ask_ollama('Reply with {"ok": true} and nothing else.', timeout=10)
    if response.startswith("ERROR:"):
        print(f"   ❌ Ollama unreachable: {response}")
        print("   Is Ollama running?  ollama serve")
        print(f"   Is model pulled?    ollama pull {MODEL}")
        return False
    print("   ✅ Ollama reachable\n")
    return True


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python doc_maturity.py <file|directory> [--debug]")
        sys.exit(1)

    target = Path(sys.argv[1])
    debug = "--debug" in sys.argv

    if not target.exists():
        print(f"Error: {target} does not exist")
        sys.exit(1)

    if not check_ollama():
        sys.exit(1)

    files = collect_files(target)
    if not files:
        print("No Python files found.")
        sys.exit(0)

    print(f"\n🔍 Analysing {len(files)} file(s) with {MODEL}...")
    print("   This may take a few minutes for large directories.\n")

    results: list[FileResult] = []
    start = time.time()

    for i, f in enumerate(files, 1):
        rel = f.relative_to(Path.cwd()) if f.is_absolute() else f
        print(f"   [{i:3d}/{len(files)}] {rel}", end="", flush=True)
        result = analyse_file(f, debug=debug)
        result.path = str(rel)
        results.append(result)
        tier_icon = {"MATURE": "✅", "PARTIAL": "🟡", "STALE": "🔴", "MISSING": "⬜"}
        print(f" → {tier_icon[result.tier]} {result.file_score}%")

    elapsed = time.time() - start

    # Write reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORTS_DIR / "report.json"
    html_path = REPORTS_DIR / "report.html"

    json_data = {
        "target": str(target),
        "generated_at": datetime.now().isoformat(),
        "model": MODEL,
        "elapsed_seconds": round(elapsed, 1),
        "files": [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(json_data, indent=2))

    html_path.write_text(generate_html_report(results, str(target)))

    print(f"\n   Completed in {elapsed:.1f}s")
    print_console_report(results)


if __name__ == "__main__":
    main()
