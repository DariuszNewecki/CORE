# ADR-002: Shared Layer Boundary Enforcement

**Status:** Accepted
**Date:** 2026-04-18
**Deciders:** Darek Newecki (Principal Architect)
**Context:** Shared/ boundary audit revealed constitutional violations requiring architectural resolution

## Context

The shared/ layer grew to 166 files (larger than mind/ at 71 files), with several boundary violations against the three-criterion admission test:
1. **Layer-independent** (no knowledge of specific layer logic)
2. **Serves multiple layers** (imported by ≥2 of mind/body/will)
3. **No governance logic** (no governance decisions in code)

Observation 8.1 hypothesized that shared/infrastructure/intent/intent_repository.py was "arguably closer to Body than layer-neutral utility." Empirical analysis of import topology disproved this (mind=2, body=6, will=5, cli=4 importers — genuinely multi-layer).

However, audit identified genuine boundary violations requiring constitutional resolution.

## Decisions

### 1. Constitutional Governance Extraction

**Problem:** `shared/ai/constitutional_envelope.py` contained hardcoded governance constants (`_LAYER_MAP`, `_ALWAYS_INCLUDE_CATEGORIES`, `_INCLUDE_ENFORCEMENT`) violating the principle "Governance mappings live in `.intent/`, never hardcoded in `src/`."

**Decision:** Extract governance constants to `.intent/enforcement/constitutional_envelope.yaml` and modify the code to read them dynamically via `IntentRepository.load_document()`.

**Rationale:** Constitutional violations must be resolved, not accommodated. Policy decisions belong in `.intent/`, mechanisms belong in `src/`. The extraction maintains fail-open robustness with fallback constants.

### 2. CLI Utilities Layer Alignment

**Problem:** `shared/cli_utils/` served 113 CLI files vs 1 Will file (99% single-layer usage), violating criterion 2.

**Decision:** Move `shared/cli_utils/` → `src/cli/utils/` with full import updates across 114 files and 4 `.intent/` governance mappings.

**Rationale:** CLI utilities belong in the CLI layer. The 1 Will importer (`daemon.py`) was resolved by moving the daemon itself to CLI (see decision 3).

### 3. CLI Entry Point Classification

**Problem:** `will/commands/daemon.py` exposed CLI entry points (`typer.Typer()`, `@daemon_app.command()`) but lived in Will layer. After cli_utils move, this would create Will→CLI import violation.

**Decision:** Move `will/commands/daemon.py` → `src/cli/commands/daemon.py` to align layer with function.

**Rationale:** CLI entry points belong in CLI layer regardless of implementation concerns. The daemon exposes CLI commands; its orchestration logic can live in CLI without architectural violation.

### 4. Remediation Planning Layer Assignment

**Problem:** `shared/self_healing/remediation_interpretation/` had single consumer (`body/workers/violation_remediator/worker.py`) and embedded governance logic (`_MIN_RECOMMENDED_SCORE = 15` threshold), violating criteria 2 & 3.

**Decision:** Move `shared/self_healing/remediation_interpretation/` → `src/will/self_healing/remediation_interpretation/`.

**Rationale:** Remediation planning (finding normalization, file role detection, strategy selection) is cognitive work belonging to Will layer. The move forced obs-8.6 resolution (see decision 5).

### 5. Obs-8.6 Resolution: Two-Worker Separation

**Problem:** Moving remediation_interpretation to Will exposed Body→Will import violation in `body/workers/violation_remediator/worker.py`. Investigation revealed two distinct workers with similar names:
- `will/workers/violation_remediator.py` (active daemon Blackboard consumer)
- `body/workers/violation_remediator/` (paused CLI LLM fixer package)

**Decision:** Move `body/workers/violation_remediator/` → `src/will/workers/violation_remediator_body/` to resolve import violation without name collision.

**Rationale:** The Body package contained cognitive planning logic (Will concerns), not execution logic (Body concerns). Renaming prevented collision with active worker while resolving constitutional violation. Both workers serve different purposes and can coexist in Will.

### 6. Subprocess Governance Enforcement

**Problem:** Moving `violation_remediator_body` to Will exposed `subprocess.run` usage violating `governance.dangerous_execution_primitives` (Will layer prohibits raw subprocess calls).

**Decision:** Replace raw `subprocess.run` with constitutional `subprocess_utils.run_command_async()` pattern.

**Rationale:** Dangerous primitives must route through constitutional infrastructure, not receive rule exceptions. The subprocess sanctuary (`shared/utils/subprocess_utils.py`) provides the proper interface.

### 7. Workers Base Class Layer Assignment

**Problem:** `shared/workers/base.py` self-declared `# ID: will.workers.base` and served predominantly Will (17 importers) vs Body (4 importers). The Worker concept is fundamentally Will-layer (autonomous officer with declared mandate).

**Decision:** Implicitly resolved via obs-8.6 (decision 5) — the 4 Body importers moved to Will, eliminating the cross-layer dependency.

**Rationale:** Worker is a Will concept. Placing the base class in shared/ was historically convenient but constitutionally incorrect.

## Consequences

### Positive
- **Constitutional compliance:** Zero shared/ boundary violations remaining
- **Layer clarity:** Each component lives in its proper constitutional layer
- **Governance separation:** Policy decisions in `.intent/`, mechanisms in `src/`
- **Audit health:** Findings reduced from 6 → 3 (all INFO, no warnings)
- **Forcing functions:** Moves exposed and resolved hidden constitutional debt

### Negative
- **File churn:** 115+ files touched across multiple commits
- **Import updates:** Widespread path changes requiring careful verification
- **Complexity:** Multiple interdependent moves requiring specific sequencing

### Neutral
- **obs-8.6 clarification:** Two-worker pattern now explicit rather than hidden
- **Intent validation:** Observation 8.1 hypothesis disproven by empirical analysis

## Compliance

All decisions comply with:
- **Mind-Body-Will separation:** Components in correct layers
- **Constitutional access patterns:** `.intent/` via `IntentRepository` only
- **Governance discipline:** Policy in `.intent/`, mechanism in `src/`
- **Dangerous primitive routing:** Infrastructure through constitutional interfaces

## Follow-up Actions

- [ ] Monitor audit health after moves settle
- [ ] Consider consolidating violation_remediator workers if functional overlap emerges
- [ ] Review other subprocess.run usage for similar constitutional violations

---

**Result:** Shared/ boundary audit complete with clean constitutional boundaries throughout the system.
