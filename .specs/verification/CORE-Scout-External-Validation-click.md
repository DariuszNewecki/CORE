# CORE Scout External Validation — pallets/click

**Date:** 2026-06-23
**Branch:** main (dd0cba24 — clean)
**Target:** https://github.com/pallets/click (SHA 8a1b1a33d739be05b7e91251e3c0dde77c5e152f)
**Verdict:** PARTIAL

---

## 1. Executive Verdict

**PARTIAL.** The Scout workflow completes end-to-end — Phase A installs a machinery floor, Phase B invokes an LLM, produces evidence-grounded candidates, and writes syntactically valid output. Three of six inducted rules actually fire against click's source files via the offline audit (with a prerequisite workaround documented below). However:

- The 3 enforceable rules are generic (docstrings, bare-except, module-header) — the same rules Scout would propose for any medium-sized Python library.
- The `module_header` engine fires with CORE-internal logic ("Expected `# src/<path>`") that is meaningless to an external adopter.
- The audit path requires `cd` into the target repo and a manual fix to the machinery floor (`action_risk.yaml` drift), confirming there is no supported external-repo audit path today.
- Scout cannot propose rules for click-specific patterns (decorator conventions, type alias enforcement, ParamType subclassing) because its enforcement catalog lacks the vocabulary and its detect phase samples only 12 files with coarse signal extraction.
- LLM outputs are non-deterministic: two independent runs produced different candidate sets with different rule IDs for the same pattern (`scout.typing_import_convention` vs. `scout.type_checking_imports`).

Scout proves the _concept_ but not enough of the _value_ to recommend external adoption without Phase-B enhancements.

---

## 2. Commands Executed

```
# Baseline
git status && git log --oneline -3

# Phase A — dry-run
core-admin project onboard work/external-validation/click

# Phase A — stage + promote
core-admin project onboard work/external-validation/click --write --stage
core-admin project promote work/external-validation/click

# Phase B — dry-run Scout (piped accept-all)
printf 'a\na\na\na\na\na\n' | core-admin project scout work/external-validation/click

# Phase B — write Scout rules (piped accept-all)
printf 'a\na\na\na\na\na\n' | core-admin project scout work/external-validation/click --write

# Audit — from click directory (workaround required; see §4 and §7)
cd /opt/dev/CORE/work/external-validation/click
core-admin code audit --offline --files src/click/core.py --files src/click/types.py
core-admin code audit --offline --format json --files src/click/core.py --files src/click/types.py
core-admin code audit --offline --format json --files src/click/_compat.py
```

**Ratification strategy:** All candidates were accepted by piping `a\n` for each prompt. This is documented as a validation choice — not selective ratification. ADR-119 D5 prohibits `--accept-all`; piped stdin is the only non-interactive path and is functionally equivalent to batch-accept.

---

## 3. Target Repo Profile

| Property | Value |
|---|---|
| Repository | pallets/click |
| Commit SHA | 8a1b1a33d739be05b7e91251e3c0dde77c5e152f |
| Python files | 63 (17 in src/click/, 31 in tests/, 15 in examples/) |
| pyproject.toml | Present (flit build backend, PEP 621) |
| Test directory | `tests/` (pytest, 31 files) |
| Source layout | `src/click/` (src-layout) |
| Lint tool | Ruff (B, E, F, I, UP, W, ICN) |
| Type checking | mypy strict + pyright basic |
| Requires-python | >=3.10 |

**Notable click-specific patterns:**
- All files use `import typing as t` and `import collections.abc as cabc` — strict import aliasing convention enforced across 100% of source files.
- `if t.TYPE_CHECKING:` guard used uniformly for annotation-only imports.
- `from __future__ import annotations` in 100% of source files.
- Zero `print()` calls — exclusively uses `click.echo()`.
- Decorator-based CLI definition (`@click.command`, `@click.option`, etc.) — click's own public API.
- `ParamType` subclass hierarchy with mandatory `convert()` methods.
- `CliRunner` testing pattern used in 31 test files.

---

## 4. Phase A Onboarding Result

**Result: Success (29 files delivered)**

The dry-run previewed 29 files. Stage+promote succeeded. The promoted `.intent/` tree contains:

```
.intent/
  META/               — 15 schema files (GLOBAL-DOCUMENT-META-SCHEMA.json, rule_document.schema.json, etc.)
  constitution/       — CONSTITUTION.md (starter stub)
  enforcement/config/ — 10 config files (action_risk.yaml, audit_verdict.yaml, etc.)
  taxonomies/         — 3 files (cognitive_roles.yaml, filesystem_operations.yaml, operational_capabilities.yaml)
```

**No rules directory was created.** Phase A delivers machinery floor only. This is correct per ADR-119.

**Machinery floor content assessment:**
- The delivered `action_risk.yaml` is a snapshot that is out of date with CORE's registered action set. The `document.run.gap_analysis` action was registered after the machinery floor was last updated. Running `core-admin` from within the click directory fails at bootstrap with:
  ```
  ConstitutionalError: action_risk policy is missing impact_level for registered actions: ['document.run.gap_analysis']
  ```
- **Workaround applied for validation:** The missing entry was added manually to `work/external-validation/click/.intent/enforcement/config/action_risk.yaml`. This is a validation artifact, not a CORE source modification.
- **ADR-119 D3 check:** Phase A installs machinery floor only, no rule layer — consistent with ADR-119. The CONSTITUTION.md stub does not impose rule content.
- **CORE-internal concept leakage in CONSTITUTION.md:** The stub references "CORE runtime" by name and includes instructions specific to CORE's setup model. This is acceptable for a branded starter document but would need rebranding for white-label use.

---

## 5. Phase B Scout Result

### LLM induction used: YES
LLM provider: `anthropic_claude_sonnet` (claude-sonnet-4-6, ConstitutionalCoherenceAnalyst role).

### Detect phase
Scout sampled 12 files (the maximum), prioritizing by file size since click has no entry-point files matching the detect-phase name list (`__main__.py`, `main.py`, `app.py`, `cli.py`, etc.). Files sampled in order: largest first (core.py, types.py, _termui_impl.py, termui.py, testing.py, shell_completion.py, utils.py, _compat.py, parser.py, decorators.py, _winconsole.py, formatting.py), then test files.

**Structural signals extracted:**
- Python files total: 63
- Has src/ layout: yes
- Public symbols (sample estimate): 434
- Docstrings present: ~46%
- print() calls: 0
- Bare except occurrences: 2
- Type annotations (→): present
- from __future__ import annotations: 11 of 12 sampled files
- Decorator usage: yes

### Candidates proposed (Run 1, dry-run — not written)
| Rule ID | Enforcement | Rationale quality | Catalog match |
|---|---|---|---|
| scout.future_annotations | advisory | Good — specific to 11/12 observation | No match |
| scout.type_annotations | advisory | Good — specific to API surface | No match |
| scout.bare_except | reporting | Good — 2 occurrences detected | Yes (no_bare_except) |
| scout.docstrings | reporting | Good — 46% coverage, specific evidence | Yes |
| scout.no_print | advisory | Good — 0 print calls observed | Yes |
| scout.typing_import_convention | reporting | Excellent — click-specific import aliasing | No match |

### Candidates proposed (Run 2, written)
| Rule ID | Enforcement | Rationale quality | Catalog match |
|---|---|---|---|
| scout.future_annotations | advisory | Good | No match |
| scout.type_annotations | advisory | Good | No match |
| scout.no_bare_except | reporting | Good | Yes |
| scout.docstrings | reporting | Good | Yes |
| scout.type_checking_imports | advisory | Excellent — observes click's TYPE_CHECKING pattern | No match |
| scout.module_header | reporting | Acceptable — observes 2/12 sampled files have headers | Yes |

**Non-determinism observed:** The two LLM runs produced different candidate sets. `scout.no_print` appeared in Run 1 but not Run 2; `scout.module_header` appeared in Run 2 but not Run 1. Rule IDs for the same observed pattern differ (`scout.typing_import_convention` vs. `scout.type_checking_imports`). This non-determinism means repeated Scout runs produce different governance outputs.

**3 matched · 3 unmatched** in the written run (consistent with Run 1's matching count).

**Evidence samples:** Scout provided specific file:line evidence for each candidate, e.g.:
- `src/click/core.py, src/click/types.py` for type_annotations
- `src/click/_termui_impl.py and parser.py` for module_header pattern
- `examples/complex/complex/cli.py` for future_annotations exception

Evidence quality is good — grounded in observed signals, not generic best-practice assertions.

---

## 6. Generated Rules and Mappings

### scout_inducted.json — syntactically valid JSON

```json
{
  "rules": [
    {"id": "scout.future_annotations", "enforcement": "advisory"},
    {"id": "scout.type_annotations",   "enforcement": "advisory"},
    {"id": "scout.no_bare_except",     "enforcement": "reporting"},
    {"id": "scout.docstrings",         "enforcement": "reporting"},
    {"id": "scout.type_checking_imports", "enforcement": "advisory"},
    {"id": "scout.module_header",      "enforcement": "reporting"}
  ]
}
```

- All IDs are namespaced under `scout.*` — correct.
- No CORE-internal concepts (paths, ADR references, internal types) appear in the rule statements or rationale.
- `authority: "policy"`, `phase: "runtime"` — valid vocabulary.
- `$schema: "META/rule_document.schema.json"` — references local machinery floor schema.

### scout.yaml — syntactically valid YAML

Three mappings (no_bare_except → regex_gate, docstrings → ast_gate, module_header → ast_gate). Engines (`regex_gate`, `ast_gate`) are valid CORE engine identifiers. Scopes are `**/*.py` with appropriate excludes for venv/build dirs.

**Declared-only rules (3):** scout.future_annotations, scout.type_annotations, scout.type_checking_imports — no catalog entry, so governance intent is recorded but not enforced.

---

## 7. Offline Audit Result

### Problem: No first-class external repo audit path

`core-admin code audit` has no `--target` or `--path` parameter. The audit discovers its rule set via `resolve_default_repo_path()` which walks up from `cwd` looking for `.intent/`. To audit against click's rules, one must `cd` into the click directory before invoking `core-admin`.

Running `core-admin` from `/opt/dev/CORE` (the default) uses CORE's own 208-rule set — Scout-inducted rules are unknown to it and produce zero findings.

**Workaround used:** `cd work/external-validation/click && core-admin code audit --offline --files src/click/core.py`

### Additional blocker: action_risk drift

The machinery floor's `action_risk.yaml` is missing `document.run.gap_analysis`, which is registered in CORE's action registry. Bootstrap fails with `ConstitutionalError` when running from click's directory. **Fixed in click's `.intent/` for this validation; NOT fixed in CORE source.**

### Audit results after workaround

**Against src/click/core.py + src/click/types.py (2 files):**
- Rules executed: 3 (of 3 declared — 3 declared-only rules are skipped)
- Total findings: 94
  - `scout.docstrings`: 92 findings (missing docstrings on public methods in core.py and types.py)
  - `scout.module_header`: 2 findings (core.py and types.py have no module-level docstring)
- scout.no_bare_except: 0 findings (these files have no bare-except patterns)
- Verdict: PASS (all findings are INFO severity, not blocking)

**Against src/click/_compat.py:**
- Total findings: 22
  - `scout.no_bare_except`: 3 findings (lines 73, 166, 564 — `except Exception: pass` in `__del__` and error-handling paths)
  - `scout.docstrings`: 18 findings
  - `scout.module_header`: 1 finding

**Quality issue with module_header rule:** The `ast_gate check_type: module_header` engine expects `# src/<path>` style headers (CORE's own symbol-ID convention). Its findings message reads: `"Missing or incorrect module header. Expected '# src/<path>', got: 'from __future__ import annotations'"`. This is a CORE-internal convention leaking through the enforcement mapping — the rule text says "modules MUST include a module-level docstring" but the engine checks for CORE-style path comments. The rule statement and the engine behavior are misaligned.

**Quality issue with no_bare_except rule:** The regex pattern `"except Exception:\\s*pass"` fires on legitimate `except Exception: pass` in `__del__` methods and error-path cleanup code in click. These are intentional silences that click uses deliberately (and consistently). The rule's rationale claims "2 bare_except occurrences" but the actual patterns are typed (`except Exception:`) not bare (`except:`). The regex catalog entry conflates "bare except" with "typed-but-pass except" — a real distinction that the LLM observed correctly but the catalog encoded incorrectly.

---

## 8. Did Scout Add Real Value?

**Partially.** Evaluating against the stated criteria:

| Question | Assessment |
|---|---|
| Did Scout inspect enough of the repo to understand click? | Partially — 12 of 63 files, all from `src/click/` (tests excluded from sampling priority), no example files. Missed click's test conventions entirely. |
| Did Scout propose rules specific to click? | Two of six are click-specific: `scout.type_checking_imports` (click's TYPE_CHECKING guard pattern) and `scout.typing_import_convention` (Run 1). The other four are universal. |
| Did Scout merely reproduce generic starter rules? | Four of six match the fallback starter menu (future_annotations, docstrings, no_bare_except, no_print). The 12-signal detect phase is insufficient to distinguish click from any other Python library. |
| Were proposed rules defensible? | All six are defensible — each has genuine evidence from the code. None are fabricated. |
| Were enforcement levels reasonable? | Yes. `advisory` for near-universal patterns, `reporting` for partially-followed ones, no `blocking` proposed. Ramp awareness shown. |
| Did Scout identify missing governance opportunities from click's actual structure? | No. Scout missed: (1) the strict import aliasing convention (`import typing as t`, `import collections.abc as cabc`), which has 100% compliance and deserves a catalog entry; (2) click's decorator-based API surface; (3) ParamType.convert() mandatory override; (4) testing conventions (CliRunner pattern); (5) the `py.typed` marker presence signaling a typed library. |
| Could an external maintainer trust the result without reading CORE internals? | Mostly — but the `module_header` engine misfires (CORE-internal check leaks through), and the `no_bare_except` finding on `__del__` methods would surprise a click maintainer. Three of six rules have no enforcement (declared-only) with an opaque message about the catalog. |

---

## 9. Gaps Found

### Gaps that work

- Phase A installs a clean machinery floor (no rules, correct) via stage+promote.
- Phase B uses LLM with the correct separation: observations vs. enforcement mapping.
- Evidence samples are shown to the operator during ratification.
- JSON/YAML output is syntactically valid and correctly namespaced.
- 3 of 3 enforced rules actually fire against click's code.
- Enforcement levels were calibrated correctly (no inappropriate blocking proposals).
- The fallback menu (D7) is available and goes through catalog matching.
- The confirm loop (D5) works; per-rule ratification is enforced.

### Gaps — shallow induction

1. **12-file sample ceiling is too low for library understanding.** Click's src/ has 17 files; Scout samples 12. Zero test files are included in the primary sample (they appear last, after the 12 cap is hit). Scout cannot observe click's testing conventions, decorator patterns, or ParamType hierarchy.

2. **Detect phase signals are too coarse.** The 9 numeric signals (print count, bare-except count, decorator presence) cannot distinguish a CLI framework from a web server. Scout cannot observe: import aliasing conventions, decorator API surface, abstract method patterns, class hierarchy constraints, or CI-enforced type annotations.

3. **Enforcement catalog has 6 entries.** The catalog covers basic hygiene only. Click-relevant patterns (import aliasing, type alias enforcement, `if TYPE_CHECKING:` guards, `convert()` override requirements) have no catalog entries. All three click-specific observations fall into the declared-only bucket.

4. **LLM output is non-deterministic.** Two independent runs on the same repo produced different rule IDs for the same pattern. The rationale text also varied. This means repeated Scout runs are not idempotent: a second Scout run is blocked by the existing `scout_inducted.json`.

### Gaps — audit path

5. **No external-repo audit path.** `core-admin code audit` cannot be pointed at a target repo. The only path requires `cd`-ing into the target, which relies on `resolve_default_repo_path()`'s `.intent/` walk-up heuristic. This is fragile and undocumented for BYOR users.

6. **Machinery floor `action_risk.yaml` is stale.** `src/shared/_machinery_floor/enforcement/config/action_risk.yaml` is missing `document.run.gap_analysis` (and potentially other recently-added actions). Bootstrap fails when auditing from the external repo directory.

### Gaps — engine/catalog quality

7. **`module_header` engine behavior leaks CORE-internal convention.** The `ast_gate check_type: module_header` expects `# src/<path>` style headers — a CORE-internal symbol-ID convention. For external repos, this fires as a false positive with a confusing message. Scout should not map `scout.module_header` to this engine without scope adjustment or a different check_type.

8. **`no_bare_except` regex is over-broad.** The regex pattern `"except Exception:\\s*pass"` fires on legitimate `except Exception: pass` in `__del__` methods and cleanup code. The LLM correctly observed "2 bare except occurrences" but the catalog entry captures a superset.

9. **Declared-only rules lack an explanation for adopters.** The output "No catalog match — rule will be declared but not enforced" is shown at ratification time but not surfaced in the generated `scout_inducted.json`. A BYOR maintainer reading the output file has no path to add enforcement.

### Gaps — non-interactive support

10. **No non-interactive mode.** ADR-119 D5 mandates per-rule ratification with no `--accept-all`. This is correct for a human governance workflow but prevents CI-compatible Scout runs or automated regression testing of Scout itself. The piped `printf 'a\n...'` workaround used in this validation is fragile.

11. **No evidence artifact.** Scout produces no report artifact documenting what was observed, what was proposed, and what rationale was applied. The operator sees findings only once at ratification time; there is no persistent record of the Scout session for future audit.

---

## 10. Recommended Next Changes

Listed by impact, not effort:

### High impact / low effort

**A. Fix `module_header` engine mapping.** Remove `scout.module_header` from the enforcement catalog or replace its `check_type: module_header` with `check_type: top_level_docstring` if such a check exists. The current mapping produces CORE-internal findings against external code. This is a catalog fix, not a Scout logic change.

**B. Fix machinery floor `action_risk.yaml` drift.** Add `document.run.gap_analysis: {impact_level: safe, artifact_types: [document_corpus]}` to `src/shared/_machinery_floor/enforcement/config/action_risk.yaml`. This is a one-line addition that unblocks `cd`-into-target audit.

**C. Narrow `no_bare_except` regex.** The pattern `"except Exception:\\s*pass"` is over-broad. Change to only match true bare excepts: `"^\\s*except:\\s*(pass)?\\s*$"`. The `except Exception:` variant is typed exception handling; silence of that type should be a separate, more carefully scoped rule.

### High impact / moderate effort

**D. Add import-aliasing entry to enforcement catalog.** `import typing as t` enforcement is the most clearly click-specific pattern Scout observed. Add a catalog entry using a `regex_gate` or `ast_gate` check. This would have enabled `scout.typing_import_convention` (Run 1) and `scout.type_checking_imports` (Run 2) to be enforced.

**E. Add `code audit --target <path>` parameter.** A dedicated target flag would make the external repo audit path explicit and documented, without requiring `cd`. The `resolve_default_repo_path()` walk-up remains the fallback for `cd`-based usage.

**F. Increase sample ceiling and include test files.** Raise `_DETECT_MAX_FILES` from 12 to 30, or move to full-repo scan with size limits per file. Include at least 3 test files in the sample (not just as overflow). This doubles the signal available to the LLM at minimal cost.

### Medium impact / high effort

**G. Expand enforcement catalog with 10+ patterns.** Current 6-entry catalog produces declared-only rules for half of all LLM proposals. Additions needed: import aliasing, type alias, TYPE_CHECKING guard, abstract method enforcement, `convert()` override, class hierarchy contracts, pyright/mypy config markers.

**H. Add a Scout session artifact.** Write a `work/external-validation/<name>/scout-session.yaml` recording: target, commit SHA, files sampled, LLM model used, candidate proposals, ratification decisions, and written rule IDs. This enables repeatability auditing and is prerequisite to any CI-compatible Scout flow.

**I. Address non-determinism.** Use temperature=0 or seed the LLM call to improve reproducibility of rule proposals. Consider caching the detect+suggest output keyed by target commit SHA.

---

## 11. Acceptance Criteria for a Future "Scout v2"

A future Scout run against `pallets/click` at the same commit should satisfy ALL of the following to claim a PASS verdict:

**Workflow completeness**
- [ ] Phase A completes without workarounds (action_risk.yaml is current at time of delivery).
- [ ] Phase B completes without `cd`-into-target workaround — `core-admin project scout <path> --write` is sufficient.
- [ ] Offline audit is run as `core-admin code audit --offline --target <path>` without `cd`.

**Induction quality**
- [ ] At least one click-specific rule is proposed (import aliasing, decorator convention, TYPE_CHECKING guard, or ParamType.convert override).
- [ ] All test files are represented in the detect-phase sample (at least 3 test files).
- [ ] No proposed rule is identical to the fallback starter menu entry for the same pattern (the LLM must be observing click, not reciting defaults).
- [ ] Evidence samples point to actual lines in click's source (no generic descriptions).
- [ ] The rationale explicitly references click's own design decisions (e.g., "as stated in parser.py's module docstring").

**Enforcement quality**
- [ ] 5 or more of 6 proposed rules are matched to the enforcement catalog (not declared-only).
- [ ] `scout.module_header` (if proposed) maps to a check that fires correctly on Python module docstrings — not CORE-style path headers.
- [ ] `scout.no_bare_except` (if proposed) does not fire on `except Exception: pass` in `__del__` methods.
- [ ] All three of `scout.docstrings`, `scout.no_bare_except`, and `scout.module_header` produce zero false positives against code that legitimately satisfies the rule.

**Audit quality**
- [ ] The offline audit produces findings with rule IDs (`check_id`) populated (not `null`).
- [ ] Finding messages are interpretable without CORE knowledge.
- [ ] The audit PASS/FAIL verdict is correct (PASS if no blocking rules fire, FAIL if blocking rules with violations fire).
- [ ] A Scout session artifact exists at `<target>/scout-session.yaml` or equivalent.

**Repeatability**
- [ ] Two independent Scout runs on the same commit produce rule IDs that overlap >= 80%.
- [ ] Re-running Scout after rules exist produces a clear "already inducted, use --reset to reinduct" message.

---

## Appendix: Files Generated

All files below are in `work/external-validation/click/` (gitignored, ephemeral):

```
.intent/rules/scout_inducted.json          — 6 inducted rules
.intent/enforcement/mappings/scout.yaml    — 3 enforcement mappings
.intent/enforcement/config/action_risk.yaml — (manually patched: +1 entry)
```

## Appendix: Key Source Files Inspected

| File | Purpose |
|---|---|
| `src/cli/resources/project/scout.py` | CLI entry point (thin wrapper) |
| `src/cli/logic/scout.py` | Full workflow: detect → suggest → match → confirm → write |
| `src/mind/logic/scout_inducer.py` | LLM call (Mind layer; no I/O) |
| `var/prompts/scout_rule_inducer/model.yaml` | PromptModel descriptor |
| `var/prompts/scout_rule_inducer/system.txt` | LLM system prompt |
| `var/prompts/scout_rule_inducer/user.txt` | LLM user prompt template |
| `var/prompts/scout_rule_inducer/enforcement_catalog.yaml` | 6-entry obs→engine map |
| `src/shared/_machinery_floor/` | Phase A floor delivered to targets |
| `src/shared/config.py` | `resolve_default_repo_path()` — cwd-walk intent discovery |
