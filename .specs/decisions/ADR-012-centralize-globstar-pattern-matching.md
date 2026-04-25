# ADR-012: Centralize globstar pattern matching via pathspec

**Status:** Accepted
**Date:** 2026-04-25
**Authors:** Darek (Dariusz Newecki)
**Related:** Issue #121 (silent under-enforcement), Issue #117 (same engine class, AuditorContext surface; retargets to migration)
**Reconnaissance:** Session 2026-04-25 — empirical 14-case behavior matrix, 8-call-site inventory, `.intent/` pattern audit

## Context

`pathlib.Path.match` is used at eight sites across `src/` to evaluate whether a file path matches a glob pattern. On Python 3.12.3 (the runtime CORE targets), `Path.match` has two semantics that callers do not appear to expect:

1. **`**` is treated as a single segment**, equivalent to `*`. The pattern `src/**/*.py` matches `src/api/main.py` (3 segments matching 3 segments) but does **not** match `src/main.py` (too few segments) or `src/api/sub/main.py` (too many).
2. **Matching is suffix-only.** A pattern is checked against the trailing N segments of the path, where N is the pattern's segment count. `Path("var/secrets/k.txt").match("secrets/*")` returns `True` because the last two segments of the path match the two-segment pattern — even though the caller may have intended `secrets/*` to mean "anchored at root."

A 14-case empirical run (this session) found four behavior mismatches between `Path.match` and `fnmatch.fnmatch` at realistic inputs. Three of the four are silent under-enforcement at security-sensitive sites:

| Path | Pattern | Path.match | fnmatch | Site |
|---|---|---|---|---|
| `var/app/secrets/sub/k.txt` | `**/secrets/**` | False | True | redactor |
| `.intent/keys/sub/k.txt` | `.intent/keys/*` | False | True | FileNavigator |
| `src/api/sub/main.py` | `src/**/*.py` | False | True | (no live consumer) |
| `var/secrets/k.txt` | `secrets/*` | True | False | FileNavigator (over-fires; right answer wrong reason) |

The eight call sites are:

- `src/body/governance/intent_guard.py:305` — IntentGuard rule scope check
- `src/body/governance/path_validator.py:186` — `_matches_pattern` static helper
- `src/body/services/validation/validation_policies.py:55` — exclude-pattern check in safety scanner
- `src/body/autonomy/micro_proposal_executor.py:170` — allowed/forbidden path check
- `src/shared/infrastructure/context/redactor.py:53` — redaction forbid-glob check (security)
- `src/shared/infrastructure/context/limb_workspace.py:108` — crate file enumeration
- `src/will/tools/file_navigator.py:90-91` — agent file-access forbid-glob check (security)
- `src/shared/utils/path_utils.py:146` — `matches_glob_pattern` central helper, **never called**, contains the same broken body

The central helper `matches_glob_pattern` was authored as the canonical entry point but never adopted. Its docstring asserts `matches_glob_pattern('src/main.py', 'src/**/*.py') # True` — empirically false on Python 3.12.

A correct implementation already exists at `src/mind/governance/audit_context.py:193` (`_include_matches`) and `:168` (`_is_excluded`). It uses `fnmatch.fnmatch` plus a `**/`-collapse / `/**`-collapse fallback to handle the zero-directory case. Real landing SHA: `f634e521`. (The A3 plan attributes this to commit `8e9325fb`, which does not exist in the repository — corrected in the same commit set as this ADR.)

`pathspec` is already present in `poetry.lock` as a transitive dependency at version 0.12.1.

The hazard direction the originating issue body anticipated (#121) — "rules will start firing, audit count will jump" — is incorrect. The audit pipeline already uses the working `_include_matches`/`_is_excluded` helpers via `AuditorContext`. The actual hazard is **inverted**: tightening write/read enforcement that has been silently loose. Operations the daemon and Claude Code currently execute may begin to be blocked by IntentGuard or `FileNavigator` after migration.

## Decision

Adopt `pathspec`'s `GitWildMatchPattern` (gitignore semantics) as the standard glob-matching primitive across `src/`. Centralize all path-pattern evaluation through a single helper module. Migrate the seven raw `Path.match` call sites and the broken central helper. Audit and rewrite hardcoded pattern strings whose intent does not survive the semantic shift.

`AuditorContext` (`audit_context.py`) is **not** in scope for this ADR. Its hand-rolled `_include_matches`/`_is_excluded` helpers compensate correctly today and have been validated against the live audit baseline. Migrating them is structural consolidation, not bug fix; it is tracked separately as Issue #117 (retargeted from its original "fix the asymmetry" framing to "migrate to the central helper").

### 1. Promote `pathspec` from transitive to direct dependency

Add to `pyproject.toml` `[tool.poetry.dependencies]`: `pathspec = "^0.12"`. The library is already installed; this declares the dependency explicitly so dependency hygiene rules can govern it.

### 2. New helper module — `src/shared/utils/glob_match.py`

Single entry point for glob matching across `src/`. Two public functions:

- `matches_glob(path: str | Path, pattern: str) -> bool` — gitignore-semantic single-pattern match.
- `matches_any_glob(path: str | Path, patterns: Iterable[str]) -> bool` — any-of convenience.

Both convert path to POSIX form, then evaluate via `pathspec.patterns.GitWildMatchPattern`. No fallback to `Path.match` or raw `fnmatch`.

The existing `path_utils.matches_glob_pattern` and `matches_any_pattern` are deprecated (with `DeprecationWarning`) and delegate to the new helper for one release cycle, then are removed.

### 3. Migrate seven call sites

Each site replaces `Path(x).match(pat)` with `matches_glob(x, pat)`. Each site's hardcoded pattern strings are audited for gitignore-semantic correctness in the same commit. Per-site pattern changes are listed in §5. The eighth site (`audit_context.py`) is excluded per the scope statement above.

### 4. Test coverage

New file `tests/shared/utils/test_glob_match.py` covering at minimum the four empirical mismatches identified above, plus the gitignore semantic boundary cases (anchored vs unanchored, `**` zero-dir, `**` recursive, trailing `/`).

### 5. Pattern rewrites required

Adopting gitignore semantics changes how some existing patterns evaluate. Rewrites required in the same commit as adoption:

**`src/will/tools/file_navigator.py` `FORBIDDEN_PATTERNS`:**

```python
# Before                  →  After (gitignore-semantic intent preserved)
".env"                    →  "**/.env"          # forbid at any depth, not just root
"*.key"                   →  "**/*.key"         # explicit; current is unanchored already
".git/*"                  →  "**/.git/**"       # forbid traversal at any depth
"__pycache__"             →  "**/__pycache__/**"
".intent/keys/*"          →  ".intent/keys/**"  # close current under-enforcement
"secrets/*"               →  "**/secrets/**"    # close current under-enforcement
```

**`src/shared/infrastructure/context/redactor.py` `DEFAULT_FORBIDDEN_PATHS`:** patterns are already gitignore-shaped; no rewrites required. The redactor was over-relying on Path.match's suffix-matching by coincidence; migration is behaviorally tightening at deep nesting.

Other call sites consume patterns from `.intent/enforcement/mappings/*.yaml` (for IntentGuard rule.pattern, validation_policies excludes) or from runtime arguments (limb_workspace, path_validator). The `.intent/` patterns under `applies_to`/`excludes` are evaluated by `AuditorContext` and remain on the existing helpers (out of scope).

## Alternatives Considered

**Keep `Path.match` and document the quirks.** Rejected. Documentation does not fix silent under-enforcement at security-sensitive sites. The behavior contradicts the docstring of the central helper that claims to wrap it.

**Hand-rolled fnmatch + `**/`-collapse logic, extracted from `audit_context._include_matches`.** Considered seriously. Same correctness on the four mismatches; no new direct dependency; preserves the exact semantic CORE already uses in audit. Rejected on three grounds: (a) hand-rolled glob semantics are a known foot-gun across decades of tooling; (b) `pathspec` is industry-standard, well-tested, and gitignore semantics are what most callers intuitively expect; (c) `pathspec` is already present transitively — promotion is a one-line change.

**Wait for Python 3.13's `PurePath.full_match`.** Rejected. CORE cannot upgrade to 3.13 for this issue alone, and `full_match` would still leave the existing `Path.match` calls broken (they are explicitly different methods).

**Use `glob.translate` (Python 3.13+) to compile patterns to regex.** Rejected for the same reason as above.

**Roll a custom globstar parser.** Rejected. Reinventing pathspec.

**Migrate `audit_context.py` in this ADR.** Considered. Rejected to keep change classes separate: the seven raw `Path.match` sites carry empirical correctness fixes (security-relevant) and require pattern-string rewrites; AuditorContext is structurally identical work but has no live bug — it is consolidation, not repair. Bundling them risks an audit-baseline drift in the same commit as the security tightening, with no way to attribute a regression to one or the other. Tracked as Issue #117.

**Phased migration of the seven sites (helper now, sites later).** Rejected. The originating issue (#121) explicitly framed this as "own session with own ADR required — not end-of-session cleanup." A complete migration of the in-scope sites in one motion is what the issue prescribes. Per-site adoption commits remain granular within the session.

## Consequences

### Positive

- Single source of truth for glob matching across the in-scope `src/` sites. The seven raw `Path.match` sites and the broken central helper collapse to one primitive.
- Three security-relevant under-enforcements close: redactor at deep nesting, FileNavigator at deep `.intent/keys/` and `secrets/` paths.
- Tests cover the actual failure modes for the first time.
- Issue #117 retargets to a migration task that finishes the engine-class consolidation when AuditorContext lands on the same primitive. Closing it becomes definite (move-to-helper) rather than ambiguous (was-the-original-bug-fixed-by-the-compensation).

### Negative

- **Tightening hazard.** Several patterns previously under-enforced will begin to fire correctly. The daemon and Claude Code may hit `IntentGuard` blocks on writes that previously slipped through, and `FileNavigator` may begin denying agent reads of paths it previously permitted. The blast radius is bounded — the rewrite list in §5 is exhaustive — but operationally the first audit and first daemon cycle after merge must be observed carefully.
- **Pattern semantics shift.** Anchored-by-default-with-separator (`secrets/*` matches root only) differs from `Path.match`'s suffix matching. The §5 rewrites encode the intended semantic explicitly; any pattern not on that list keeps the old phrasing and may behave differently. This is acceptable because the patterns CORE actually uses are enumerated and audited.
- **Direct dependency on `pathspec`.** Already installed transitively; promotion makes the surface explicit. Acceptable.
- **Two glob primitives in `src/` until #117 lands.** AuditorContext keeps `_include_matches`/`_is_excluded`; everything else uses the new helper. Documented exception, not silent inconsistency.

### Neutral

- IntentGuard's `rule.pattern` consumer is currently unused for `**` patterns (no rule's `scope[0]` value contains `**`). The IntentGuard migration is structural cleanup, not a behavioral fix.
- `path_utils.matches_glob_pattern` deprecation period: one release cycle. CORE has no external API consumers, so the cycle is bookkeeping; deletion in the same session is also acceptable.
- Audit count is not expected to change. The hazard direction is at the write/read enforcement layer, not at the audit layer.

## References

- Issue #121 — originating bug report; framing requires correction (audit-jump anticipation was wrong direction)
- Issue #117 — same engine class, AuditorContext include-pattern asymmetry; retargets to migration task; closes when AuditorContext lands on the central helper
- Issue #142 — CLI-depth misfire; **not** a #121 symptom (CLI rules use `runtime_check`/`python_runtime` engines, not `Path.match` scope evaluation); independent
- A3 plan claim of #117 closed by commit `8e9325fb`: incorrect; real SHA is `f634e521` (`Draw down 11 audit findings (18 -> 6); verdict FAILED -> PASSED`). Corrected in the same commit set as this ADR.
- `src/mind/governance/audit_context.py:168-218` — `_include_matches` / `_is_excluded` (working solution preserved out of scope; migrates per #117)
- `src/shared/utils/path_utils.py:125-167` — broken central helper being replaced
- 14-case empirical behavior matrix — produced this session, recorded in commit referencing this ADR
- `pathspec` documentation — `GitWildMatchPattern` semantics (gitignore.5)
