---
kind: adr
id: ADR-031
title: ADR-031 — No Hardcoded Runtime Directory Paths
status: proposed
---

<!-- path: .specs/decisions/ADR-031-no-hardcoded-runtime-dir-paths.md -->

# ADR-031 — No Hardcoded Runtime Directory Paths

**Date:** 2026-05-09
**Status:** Proposed
**Author:** Darek (Dariusz Newecki)

---

## Context

CORE has a canonical path abstraction: `PathResolver` in
`src/shared/path_resolver.py`. Its declared defaults are:

```python
_DEFAULT_LOGS_SUBDIR    = ("var", "logs")
_DEFAULT_REPORTS_SUBDIR = ("var", "reports")
```

These defaults are correct. The problem is that ~30 call sites in `src/`
bypass PathResolver entirely and construct runtime directory paths as string
literals:

```python
# Examples found across src/
self.reports_dir = repo_path / "reports"           # FileService root
CORE_ACTION_LOG_PATH = REPO_ROOT / "logs" / "..."  # config.py
repo_root / "reports" / "audit" / "latest_audit.json"
Path("reports") / "decisions"
file_service.ensure_dir("reports/audit")
```

CORE governs *how* you write (FileHandler, governed mutation surface) but not
*where* you resolve runtime output directories to. The path naming layer is
constitutionally ungoverned.

The closest existing rule is `governance.artifact_mutation.traceable`, which
correctly names the intent but is `engine: advisory` — deliberately, because
the original authors judged general write-path detection too noisy. That
judgment was correct for write-path detection. It does not apply to the more
targeted problem of runtime directory name literals in path construction.

A planned structural change — consolidating top-level `logs/` and `reports/`
into `var/logs/` and `var/reports/` — makes this defect load-bearing: without
a rule, the audit cannot detect bypass sites, and the migration cannot be
governed or remediated autonomously.

The direct analog in existing constitutional law is
`architecture.intent.non_gateway_no_direct_resolution`, which forbids direct
`.intent/` path construction outside the canonical gateway. No equivalent rule
exists for runtime output directories.

---

## Decision

### D1 — New rule: `architecture.path_access.no_hardcoded_runtime_dirs`

**Statement:** Runtime output directory names (`logs`, `reports`) MUST NOT
appear as string literals in path construction expressions in `src/`. All
runtime path resolution MUST route through PathResolver or FileHandler.

**Enforcement:** blocking
**Authority:** constitution
**Phase:** audit

### D2 — Engine: `regex_gate`

`regex_gate` is the correct engine for the initial deployment. It catches the
dominant violation pattern — string literals containing `"reports/"` or
`"logs/"` in path construction — without requiring a new ast_gate check type.

The `ast_gate` path division form (`repo_root / "reports"`) is not fully
caught by regex and is a known gap. A future `check_type:
hardcoded_runtime_paths` in `ast_gate` closes that gap. Filing as Band D
follow-up; not blocking this ADR.

### D3 — Canonical exclusions

The rule MUST NOT flag the infrastructure that defines the canonical surface:

- `src/shared/path_resolver.py` — IS the canonical resolver
- `src/shared/infrastructure/storage/file_handler.py` — IS the governed write surface
- `src/shared/infrastructure/storage/file_provider.py` — uses `"logs"` and
  `"reports"` as logical scope keys, not path strings
- `tests/**` — test fixtures construct paths directly against tmp_path
- `infra/**` — dev scripts outside constitutional audit scope

### D4 — Migration sequencing

This rule immediately produces ~30 findings. These are not suppressed. They
enter the autonomous proposal/remediation loop as
`architecture.path_access.no_hardcoded_runtime_dirs` violations.

The two leverage roots are highest priority:

1. `src/shared/config.py:66` — `CORE_ACTION_LOG_PATH` — fix this and the
   action log path moves globally.
2. `src/body/services/file_service.py:48` — `self.reports_dir = repo_path /
   "reports"` — fix this root and every call site routing through FileService
   resolves automatically.

Fix these two first (canary), verify no regressions, then let the remediation
loop close the remaining ~28 sites.

### D5 — `governance.artifact_mutation.traceable` retained as advisory

The existing advisory rule covers write-path traceability broadly. It is not
elevated to blocking — the original false-positive risk judgment still applies
for that wider scope. D1's rule is the structural complement, not a
replacement.

---

## Consequences

**Immediate:** ~30 new `architecture.path_access.no_hardcoded_runtime_dirs`
findings appear on next audit cycle. These are governance debt that already
existed; the rule makes it visible.

**Forward:** The `var/` directory consolidation (`logs/` → `var/logs/`,
`reports/` → `var/reports/`) becomes governable. Once call sites are remediated
to route through PathResolver, moving the physical directories is a one-line
change to PathResolver's defaults with no downstream code impact.

**ast_gate follow-up:** `check_type: hardcoded_runtime_paths` — catches the
`/ "reports"` path division form that regex_gate misses. Band D backlog item.

**`.intent/` worker globs:** `repo_crawler.yaml` and `repo_embedder.yaml`
reference `"reports/**"` as scope patterns. These are declarative governance
scope declarations, not path construction — exempt from the rule. They DO need
updating when the physical directory moves. Governor action at migration time.

**`pyproject.toml` coverage paths:** Four coverage output lines reference
`reports/htmlcov`, `reports/coverage.xml`, `reports/coverage.json`. These are
tool configuration, not `src/` code — exempt from the rule, updated manually
at migration time.

---

## References

- Migration scan: Claude Code session 2026-05-09
- Related rule: `governance.artifact_mutation.traceable` (advisory, retained)
- Structural analog: `architecture.intent.non_gateway_no_direct_resolution`
- PathResolver canonical defaults: `src/shared/path_resolver.py:56-57`
- Band D follow-up: `ast_gate` `check_type: hardcoded_runtime_paths`
- GitHub issue: to be opened under Band D (Engine Integrity / G4)
