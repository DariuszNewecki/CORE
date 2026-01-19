# src/features/self_healing/test_context/examples.py

"""Refactored logic for src/features/self_healing/test_context/examples.py."""

from __future__ import annotations

from pathlib import Path


# ID: 930e05fb-c828-4995-9bfe-729fde9ff573
def find_similar_tests(
    repo_root: Path, module_name: str, classes: list, functions: list
) -> list:
    examples = []
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return []
    for test_file in tests_dir.rglob("test_*.py"):
        try:
            content = test_file.read_text(encoding="utf-8")
            score = sum(
                2 for c in classes if c["name"].lower() in content.lower()
            ) + sum(1 for f in functions if f["name"] in content)
            if score > 0:
                examples.append(
                    {
                        "file": str(test_file.relative_to(repo_root)),
                        "similarity": score,
                        "snippet": extract_snippet(content),
                    }
                )
        except Exception:
            continue
    return sorted(examples, key=lambda x: x["similarity"], reverse=True)[:3]


# ID: 0f835005-0080-4f59-a4db-4b4e2da92c17
def extract_snippet(content: str, max_lines: int = 20) -> str:
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("def test_"):
            snippet = []
            for j in range(i, min(i + max_lines, len(lines))):
                if j > i and lines[j].strip().startswith("def "):
                    break
                snippet.append(lines[j])
            return "\n".join(snippet)
    return "\n".join(lines[:max_lines])
