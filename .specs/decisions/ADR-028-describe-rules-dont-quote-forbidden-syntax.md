<!-- path: .specs/decisions/ADR-028-describe-rules-dont-quote-forbidden-syntax.md -->
# ADR-028: Describe rules; don't quote forbidden syntax

**Status:** Accepted
**Date:** 2026-05-08
**Authors:** Darek (Dariusz Newecki)

## Context

CORE rules use deterministic string-matching engines (`regex_gate`, AST
checks with `required_calls`, `forbidden_calls`, `forbidden_imports`, and
similar). These engines scan all files within their declared scope — including
docstrings, comments, ADRs, and rationale prose.

On 2026-04-24, `architecture.blackboard.worker_only_inserts` fired on
`src/body/atomic/remediate_cognitive_role.py` line 58. The violation was not
a forbidden INSERT in production code — it was a docstring explaining ADR-011
that contained the phrase "every INSERT into core.blackboard_entries" verbatim.
The rule caught its own documentation. Fixed in commit `10bf08de`; the
underlying convention was not codified.

The root cause is structural: any rule whose engine matches a literal string
will catch that string wherever it appears in scope — including in the prose
written to explain why the rule exists.

## Decision

**Rule documentation MUST describe what is forbidden by paraphrase, not by
reproduction of the forbidden pattern.**

This applies to:
- Rule `statement` fields in `.intent/` rule documents
- Rationale prose in `.intent/` mapping files
- Docstrings in `src/` files governed by string-matching rules
- ADRs and papers in `.specs/` when they fall within a rule's scope
- Comments in any in-scope file

The obligation is: convey the meaning without triggering the detector.

**Examples:**

| Context | Violating form | Compliant form |
|---------|----------------|----------------|
| Docstring explaining `worker_only_inserts` | "Workers may not execute `INSERT INTO core.blackboard_entries` directly" | "Only Workers may write new entries to the blackboard attribution table" |
| Rationale for an import-ban rule | "This bans `from rich import print`" | "This bans direct use of the presentation library's print primitive" |
| ADR explaining a forbidden call | "`session.execute(text(...))` is forbidden outside Body" | "Raw SQL execution is forbidden outside the Body layer" |

The rule is not that literal strings may never appear in documentation — it
is that documentation in scope of a string-matching rule MUST NOT reproduce
the exact pattern the rule detects.

## Alternatives Considered

**Add scope excludes for documentation paths.** Rejected: `.specs/` and
docstrings are legitimate governance targets. Excluding them would leave
real violations in those locations undetected.

**Use negative lookahead in rule patterns to skip comments/strings.** Rejected:
AST-level string matching does not support lookahead in the CORE engine
architecture, and adding it would complicate the engine for a problem that
is better resolved at authoring time.

**Suppress per-violation with inline annotations.** Rejected: inline suppression
is a symptom of miscommunication between the rule and its documentation.
The correct fix is documentation that communicates accurately without
reproducing the forbidden form.

## Consequences

**Positive:**
- Rules no longer false-positive on their own documentation.
- Documentation authors are pushed toward precise paraphrase, which
  often produces clearer explanations than literal reproduction.
- The convention is checkable: any in-scope file containing the exact
  forbidden pattern is a real violation, not a documentation artifact.

**Negative:**
- Documentation authors must be aware of which rules govern their file's scope.
  This is an authoring burden with no automated assist at present.

**Neutral:**
- Existing documentation that violates the convention is technical debt,
  not an immediately breaking issue. Violations are corrected as they surface
  via the audit.

## References

- Commit `10bf08de` — first instance fixed: docstring in `remediate_cognitive_role.py`
- Commit `4ce1de85` — related attribution rule hardening
- ADR-011 — `architecture.blackboard.worker_only_inserts` rule context
- `CORE-Rule-Authoring-Discipline.md` — Documentation Hygiene section (added per this ADR)
