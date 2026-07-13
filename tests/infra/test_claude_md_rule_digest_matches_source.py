"""Guard against CLAUDE.md rule-digest drift (#775).

CLAUDE.md's "Constitutional rules" section is a hand-maintained derived
summary of .intent/rules/architecture/*.json, and documents its own
integrity check inline: "the digest's rule-id set must equal
`jq -r '.rules[].id' .intent/rules/architecture/*.json | sort -u`." That
check was an honor-system NOTE only — nothing enforced it, so it silently
drifted (header said 71, source said 73) until reconciled by hand on
2026-07-12 (T3.1 in the external-review planning doc). This test is that
enforcement: it fails at CI/audit time instead of drifting silently again.

Deliberately hard-fails rather than skips if CLAUDE.md is missing or the
digest line's shape changes — a skip-on-missing guard is exactly the
failure mode that let a sibling guard (tests/infra/
test_repo_artifacts_type_check_matches_registry.py, #647/#776) go dark
for a week after an unrelated file rename.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_RULES_DIR = _REPO_ROOT / ".intent" / "rules" / "architecture"

_DIGEST_LINE_PATTERN = re.compile(
    r"At digest time:\s*(\d+)\s*blocking\s*\+\s*(\d+)\s*reporting\s*\+\s*"
    r"(\d+)\s*advisory\s*=\s*(\d+)\."
)


def _digest_counts_from_claude_md() -> tuple[int, int, int, int]:
    """Extract (blocking, reporting, advisory, total) from CLAUDE.md's
    digest line."""
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    match = _DIGEST_LINE_PATTERN.search(text)
    assert match, (
        "CLAUDE.md's 'At digest time: N blocking + N reporting + N advisory "
        "= N.' line not found — if the digest's wording changed, update "
        "_DIGEST_LINE_PATTERN above rather than letting this guard go dark "
        "(#775)."
    )
    blocking, reporting, advisory, total = (int(g) for g in match.groups())
    return blocking, reporting, advisory, total


def _source_counts_from_rules() -> tuple[int, int, int, int]:
    """Compute (blocking, reporting, advisory, total) from
    .intent/rules/architecture/*.json — the digest's own declared scope."""
    counts = {"blocking": 0, "reporting": 0, "advisory": 0}
    total = 0
    for rule_file in sorted(_RULES_DIR.glob("*.json")):
        data = json.loads(rule_file.read_text(encoding="utf-8"))
        for rule in data.get("rules", []):
            enforcement = rule.get("enforcement")
            assert enforcement in counts, (
                f"{rule_file.name}: rule {rule.get('id')!r} has enforcement="
                f"{enforcement!r}, not one of {sorted(counts)} — CLAUDE.md's "
                "digest only accounts for these three severities."
            )
            counts[enforcement] += 1
            total += 1
    return counts["blocking"], counts["reporting"], counts["advisory"], total


def test_claude_md_digest_matches_architecture_rules_source() -> None:
    """CLAUDE.md's rule-count digest must equal the live severity counts
    from .intent/rules/architecture/*.json."""
    assert _CLAUDE_MD.exists(), (
        f"CLAUDE.md not found at {_CLAUDE_MD} — if it moved, update "
        "_CLAUDE_MD above rather than letting this guard go dark (#775)."
    )
    digest = _digest_counts_from_claude_md()
    source = _source_counts_from_rules()

    assert digest == source, (
        "CLAUDE.md rule-digest drift (#775) — the digest says "
        f"{digest[0]} blocking + {digest[1]} reporting + {digest[2]} "
        f"advisory = {digest[3]}, but .intent/rules/architecture/*.json "
        f"currently has {source[0]} blocking + {source[1]} reporting + "
        f"{source[2]} advisory = {source[3]}. Update CLAUDE.md's digest "
        "line to match."
    )


def test_claude_md_digest_internally_consistent() -> None:
    """The digest's own stated total must equal the sum of its three
    severity counts (catches a typo'd total even if the parts drifted
    together with source by coincidence)."""
    blocking, reporting, advisory, total = _digest_counts_from_claude_md()
    assert blocking + reporting + advisory == total, (
        f"CLAUDE.md digest line is internally inconsistent: "
        f"{blocking} + {reporting} + {advisory} != {total}"
    )
