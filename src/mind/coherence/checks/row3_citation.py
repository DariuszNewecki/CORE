# src/mind/coherence/checks/row3_citation.py
"""ROW3_CITATION — every normative paper § cites an enforcing rule or marks
itself aspirational.

Per ADR-073 D6 / topology §10.2 row 3. Operationalizes ADR-049 D2's existing
constitutional obligation that has been declared-but-unenforced.

Mechanism: split each paper into top-level §s, classify each via the §2.5
marker register from D10, emit when a normative section has no rule citation
and no aspirational/pending/deferred marker.
"""

from __future__ import annotations

import re
from pathlib import Path

from body.governance.coherence_harvester import NormativeMarkerRegister

from .base import CoherenceCandidate


_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
_RULE_CITE = re.compile(r"\.intent/[\w\-.]+/[\w\-./*{}]+\.[a-z]+", re.IGNORECASE)
_LEADING_NUMBERING = re.compile(r"^[\d.]+\s*")

# Headings that legitimately use normative vocabulary about the paper's own
# process (amendment mechanism, status lifecycle) rather than about runtime
# behavior. ADR-049 D2's citation obligation does not apply — there is no
# operational rule to cite. Definition sections are deliberately NOT in this
# set; they carry rule-enforceable claims about the paper's subject.
_BOILERPLATE_HEADINGS = frozenset(
    {
        "purpose",
        "abstract",
        "motivation",
        "problem statement",
        "the problem",
        "alignment statement",
        "conclusion",
        "closing statement",
        "summary",
        "non-goals",
        "relationship to other papers",
        "amendment discipline",
        "status: superseded",
        "why it was superseded",
        "constitutional identity",
        "constitutional identity (historical)",
    }
)


# ID: b70fb5d2-9de3-4575-b1b2-58f4c88cc147
class Row3CitationCheck:
    """Emit ROW3_CITATION for normative paper §s missing rule citation or aspirational marker."""

    relation = "ROW3_CITATION"

    # ID: 2cf281c7-a32b-4b91-ab6e-abe4ad406427
    def __init__(self, repo_root: Path, register: NormativeMarkerRegister) -> None:
        self._repo_root = Path(repo_root)
        self._register = register
        self._aspirational = re.compile(
            "|".join(re.escape(m) for m in register.aspirational_markers),
            re.IGNORECASE,
        )

    # ID: 8cbccb3a-6a50-4d88-82d6-e6b231434064
    async def run(self) -> list[CoherenceCandidate]:
        papers = self._repo_root / ".specs" / "papers"
        if not papers.is_dir():
            return []
        candidates: list[CoherenceCandidate] = []
        for path in sorted(papers.glob("*.md")):
            content = path.read_text(encoding="utf-8", errors="replace")
            rel = str(path.relative_to(self._repo_root))
            for heading, section_text in _iter_sections(content):
                normalized = _LEADING_NUMBERING.sub("", heading).strip().lower()
                if normalized in _BOILERPLATE_HEADINGS:
                    continue
                if not self._register.marker_pattern.search(section_text):
                    continue
                if _RULE_CITE.search(section_text):
                    continue
                if self._register.aspirational_markers and self._aspirational.search(
                    section_text
                ):
                    continue
                candidates.append(
                    CoherenceCandidate(
                        relation=self.relation,
                        documents=[rel],
                        claim=(
                            f"Paper § '{heading}' contains normative markers but "
                            "cites no enforcing rule and carries no aspirational/pending marker."
                        ),
                        rationale=(
                            "ADR-049 D2 (operationalized by topology row 3) requires "
                            "every normative paper § to either name a `.intent/rules/...` "
                            "artifact that enforces the claim, or explicitly mark "
                            "itself aspirational/pending/deferred. Neither was detected in "
                            "this section. Either backfill the rule citation or add "
                            "an aspirational marker so the claim's status is honest."
                        ),
                    )
                )
        return candidates


def _iter_sections(content: str):
    """Yield (heading_text, section_body) for each top-level heading."""
    matches = list(_HEADING.finditer(content))
    if not matches:
        return
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        yield m.group(2).strip(), content[start:end]
