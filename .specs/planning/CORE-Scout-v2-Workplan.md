# CORE Scout v2 — Workplan

**Source:** CORE Scout External Validation — pallets/click (2026-06-23)
**Validation report:** `.specs/planning/CORE-Scout-External-Validation-click.md`
**Verdict that triggered this plan:** PARTIAL

---

## How this document is organised

Each gap from the validation is assigned to exactly one tracking form:

| Form | When used |
|---|---|
| **GH issue** | Broken behaviour — crash, wrong output, false positive, missing first-class capability |
| **ADR** | Architectural decision with meaningful design space; changing it alters a contract or a previously-decided constraint |
| **BAU task** | Enhancement or expansion that has no design ambiguity and doesn't alter a prior decision |

---

## GH Issues (bugs and missing-capability gaps)

### #685 — Machinery floor `action_risk.yaml` missing `document.run.gap_analysis` `priority:high`

Bootstrap crash (`ConstitutionalError`) when any `core-admin` command runs from inside an onboarded external repo directory. Blocks every BYOR adopter from audit on day one.

**Fix scope:** one-line addition to `src/shared/_machinery_floor/enforcement/config/action_risk.yaml` + a CI gate that catches floor/registry drift going forward.

---

### #686 — `module_header` engine fires CORE-style path comments on external repos `priority:high`

`ast_gate check_type: module_header` expects `# src/<path>` headers (a CORE-internal symbol-ID convention). Against external repos it produces the finding `"Expected '# src/<path>', got: 'from __future__ import annotations'"` — meaningless to any external adopter. Rule statement ("modules MUST include a module-level docstring") and engine behaviour are misaligned.

**Fix scope:** remove `module_header` from the Scout enforcement catalog, or introduce a `check_type: module_docstring` engine that tests for an actual module-level docstring string.

---

### #687 — `no_bare_except` catalog regex fires on typed `except Exception: pass`, not bare excepts `priority:medium`

Pattern `"except Exception:\\s*pass"` captures a typed-and-silenced exception — distinct from a true bare except (`except:`) and often legitimate in `__del__` methods and cleanup paths. Fired 3 times in `pallets/click` on intentional silences.

**Fix scope:** split into `no_bare_except` (pattern: `^\\s*except:\\s*$`) and optionally a separate advisory `no_except_pass` with `__del__` scope exclusions.

---

### #688 — `code audit` has no `--target <path>` flag; external repo audit requires undocumented `cd` workaround `priority:medium`

`resolve_default_repo_path()` walks up from `cwd` to find `.intent/`. There is no supported way to point `core-admin code audit` at an external repo from the CORE working directory. Not surfaced in help, not mentioned in onboarding output, blocks CI integration.

**Fix scope:** add `--target` option to `code audit`; update onboarding completion message to show the correct invocation.

---

### #689 — Scout LLM induction non-deterministic — same repo, different rule IDs across runs `priority:medium`

Two independent runs on `pallets/click` at the same commit produced different candidate sets and different rule IDs for the same observed patterns (`scout.typing_import_convention` vs `scout.type_checking_imports`). Makes Scout governance output non-idempotent and blocks automated Scout regression testing.

**Fix scope:** set `temperature=0` in `var/prompts/scout_rule_inducer/model.yaml`; optionally cache detect+suggest output keyed by target commit SHA.

---

## ADR candidates

### ADR-TBD-A — Scout session artifact: design, location, and governance

**Why an ADR:** The validation has no persistent record of what Scout observed, proposed, or ratified. Adding a session artifact requires deciding: what is recorded, where it lives (`<target>/scout-session.yaml`? `work/external-validation/<name>/`?), who owns it (Phase B output vs. operator-generated report), and whether it is governed (written via `FileHandler`, subject to `file.create` atomic action, or exempt as a diagnostic).

This is a new governed artifact type — not a trivial file addition.

**Suggested scope:** ADR covering session artifact schema, write path (atomic action or diagnostic-exempt), location convention, and whether it becomes a prerequisite for a `--reset` re-induction path.

**Pre-work:** resolve #689 (determinism) first; the session artifact design partly depends on whether SHA-keyed caching is adopted.

---

### ADR-TBD-B — CI-compatible Scout mode: amend ADR-119 D5

**Why an ADR:** ADR-119 D5 explicitly mandates per-rule human ratification and prohibits `--accept-all`. The validation exposed that this constraint also prevents:
- automated regression testing of Scout itself,
- CI-pipeline Scout runs in BYOR adopter workflows,
- re-induction without an operator present.

Allowing any non-interactive path requires amending D5 — the constraint was deliberate (prevent auto-acceptance of LLM-generated governance). The design question is whether a `--ci` mode or a `--accept-all` flag with audit-log is acceptable, and under what conditions.

**Suggested scope:** ADR amendment to D5 defining a sanctioned non-interactive path (e.g., `--accept-all` writes a ratification log artifact that is subject to governor review), and the conditions under which it may be used.

---

## BAU tasks

### B1 — Replace file-sampling detect phase with full-repo AST signal extraction

**The real problem is not the ceiling — it's the architecture.**

The current detect phase passes raw file content from up to 12 files to the LLM. ADR-119 D3 specifies something different: "Extract structural signals: naming patterns, import graph shape, decorator usage, comment density, exception-handling style, print/logging patterns, public-symbol coverage." Those are aggregate, repo-wide properties — not a file sample. Raising the ceiling to 30 or 50 doesn't fix the wrong model.

The correct detect phase:
1. Walks the entire repo with an AST pass (all `.py` files, no cap).
2. Produces an aggregate signal report — counts, ratios, patterns — not raw source.
3. Passes the signal report (not file content) to the LLM in the suggest phase.

Signals that must be derived from the full repo, not a sample:
- Import graph shape (which modules import which; aliasing conventions like `import typing as t`)
- Decorator inventory (all decorators used, their frequency and definition sites)
- Exception-handling style (bare except count vs. typed vs. silenced — across the whole repo)
- Public-symbol coverage (docstring ratio for all public classes/functions)
- `TYPE_CHECKING` guard usage frequency
- Abstract method / mandatory-override patterns
- Class hierarchy depth and composition patterns
- `py.typed` marker presence (project-level signal)
- Test framework signals (test file count, `CliRunner` usage, fixture patterns)
- CI configuration (mypy strict/basic, ruff rule sets, pyright settings from `pyproject.toml`)

The LLM receives a structured signal document, not file chunks. This is both more token-efficient and more informative.

**Effort:** medium-large. New AST extraction layer; scout workflow detect stage replaced, not patched. Scout prompt templates need updating to expect signal documents.

---

### B3 — Expand enforcement catalog from 6 to 15+ entries

Current catalog covers: `docstrings`, `no_bare_except`, `module_header`, `no_print`, `future_annotations`, `type_annotations`. Half of click-specific LLM proposals fell into declared-only because no catalog entry existed.

Entries to add (minimum):
- `import_aliasing` — `import typing as t`, `import collections.abc as cabc` pattern (regex_gate)
- `type_checking_guard` — `if t.TYPE_CHECKING:` guard for annotation-only imports (ast_gate)
- `no_raw_print` — same as `no_print` but as a separate reporting entry so it survives when `no_print` is renamed
- `mandatory_override` — base class declares abstract method, subclasses must implement (ast_gate)
- `no_except_pass` — typed exception silenced with `pass` (advisory; distinct from `no_bare_except`)
- `py_typed_marker` — `py.typed` present → library declares type completeness

**Effort:** medium. Catalog-only changes; each entry needs test coverage against a known-positive file.

---

### B4 — Surface declared-only rule explanation in generated `scout_inducted.json`

When Scout writes 3-of-6 rules as declared-only, the generated JSON contains no explanation. A BYOR maintainer reading `scout_inducted.json` sees rules with no enforcement and no path to add it. The ratification message ("No catalog match — rule will be declared but not enforced") is shown once at interaction time and then lost.

Add a `declared_only_reason` or `enforcement_note` field to declared-only rule entries in the generated JSON, explaining that no enforcement mapping exists yet and pointing to the enforcement catalog.

**Effort:** small. JSON writer change in `src/cli/logic/scout.py`; no schema break (additive field).

---

## Dependency order

```
#685 (floor crash)       ← fix first; unblocks all audit-path work
#686 (module_header)     ← fix before B3 catalog expansion (removes a bad entry)
#687 (no_bare_except)    ← fix before B3 (corrects an existing entry)
#689 (non-determinism)   ← fix before ADR-TBD-A (session artifact design depends on caching approach)
ADR-TBD-A (artifact)     ← after B1 (detect signals inform session artifact schema)
ADR-TBD-B (CI mode)      ← independent; unblocks automated Scout testing
B1 (full-repo AST detect) ← independent; unblocks B3 (richer signals → better catalog coverage)
B3 (catalog expansion)   ← after #686, #687; B1 informs which new entries matter most
B4 (declared-only UX)    ← independent; low-risk any time
#688 (--target flag)     ← independent; unblocks CI integration
```

---

## Acceptance gate for "Scout v2 PASS"

A future Scout run against `pallets/click` at commit `8a1b1a33` earns a PASS verdict when all criteria in `.specs/planning/CORE-Scout-External-Validation-click.md §11` are satisfied. The minimum bar:

1. Phase A completes without workarounds (fixes #685).
2. `core-admin project scout <path> --write` and `core-admin code audit --offline --target <path>` both work without `cd` (fixes #688, relates to ADR-TBD-B).
3. At least one click-specific rule is enforced (not declared-only), grounded in click's actual design (import aliasing, TYPE_CHECKING guard, or ParamType.convert override) (B3).
4. `scout.module_header` (if proposed) fires on missing module docstrings, not CORE path headers (fixes #686).
5. Two Scout runs on the same commit overlap >= 80% in rule IDs (fixes #689).
