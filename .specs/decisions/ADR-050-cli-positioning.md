# ADR-050 — CLI is outside CORE: operator client, not entry-point boundary

**Status:** Accepted
**Date:** 2026-05-15
**Authors:** Darek (Dariusz Newecki)
**Closes:** CLI governance gap surfaced by 2026-05-15 full architecture audit
**Relates to:** ADR-049 (doctrine-rule parity), CORE-Mind-Body-Will-Separation
paper §2 / §6, 2026-05-15 static architecture review

---

## Context

CORE's three-layer model (Mind / Body / Will) is a closed system. The
architecture paper (§2) states: "implementation is divided into exactly
three architectural layers. No component may exist outside these layers."
§6 adds a fourth structural element — API — explicitly positioned as an
entrypoint boundary, not a layer.

`src/cli/` exists and is admitted by `architecture.layer_exclusivity`, but
the paper says nothing about it. The 2026-05-15 full architecture audit
found:

- ~80 cross-layer imports in `src/cli/` targeting `will.*`, `body.*`, and
  `mind.*` directly.
- 5 reverse imports: `src/will/` reaching back into `src/cli/` (layer
  inversion).
- Zero `ast_gate import_boundary` rules governing `src/cli/` at all.
- No paper section defining CLI's role, permitted dependencies, or
  governance model.

CLI has been operating as an informal parallel entry point into CORE,
bypassing the only governed boundary (API) and accumulating ungoverned
imports as each new command was added.

### The question this ADR answers

Two topologies were considered:

- **A** — `User → API → CORE`: API is the sole entry point; CLI either
  does not exist or is a thin HTTP client entirely outside the system.
- **B** — `User → CLI → API → CORE`: CLI is an operator-facing client
  that routes all work through API; API remains the sole governed entry
  point into CORE.

A third option — CLI as a second parallel entry-point boundary alongside
API — was rejected because it requires governing two entry boundaries
independently, keeping them in sync, and produces exactly the ungoverned
state the audit found.

---

## Decision

### D1 — CORE is Mind / Body / Will. CLI is outside CORE.

The closed system boundary is: `src/mind/`, `src/body/`, `src/will/`.
`src/api/` is the sole governed entry point into that system, as defined
by the paper's §6. `src/cli/` is outside the system boundary entirely.
It is an operator-facing client application, not a layer, not an
entry-point boundary, not part of CORE's architectural model.

The interaction topology is:

```
User → CLI → API → Will → Body / Mind
```

CLI translates operator intent into API calls. API governs what CORE
exposes. CORE executes under its constitutional model.

### D2 — CLI's only permitted import target inside the repository is `api.*`

As a client of API, CLI has one and only one sanctioned dependency on
CORE's internals: the `api.*` package. This covers route definitions,
request/response models, and any API-level client façade that may be
introduced. All other cross-repository imports from `src/cli/` — whether
targeting `will.*`, `body.*`, `mind.*`, or `shared.*` directly — are
violations.

Standard library and third-party packages (e.g. `typer`, `rich`) are
unrestricted.

### D3 — Will may not import from CLI

The 5 currently identified reverse imports (`src/will/workflows/phases/`
importing `cli.commands.*` and `cli.logic.*`) are architectural inversions.
A client dependency may not flow backward into the system the client
calls. These imports are violations under this ADR and must be
resolved before any tightening rule lands.

### D4 — A blocking `ast_gate import_boundary` rule enforces D2

A new rule `architecture.cli.api_only` is added to
`.intent/enforcement/mappings/architecture/layer_separation.yaml`:

```yaml
architecture.cli.api_only:
  engine: ast_gate
  check: import_boundary
  applies_to: src/cli/**/*.py
  forbidden:
    - src.will
    - will
    - src.body
    - body
    - src.mind
    - mind
    - src.shared
    - shared
  excludes: []
  severity: blocking
  rationale: >
    CLI is a client application outside CORE's closed system. Its only
    sanctioned CORE dependency is api.*. Direct imports from will, body,
    mind, or shared bypass the governed API boundary and are
    constitutionally prohibited. See ADR-050.
```

No `excludes:` entries are permitted at rule creation. Every current
violation must be resolved by either (a) adding an API endpoint that
covers the use case, or (b) removing the CLI command if no API
equivalent is warranted.

### D5 — The architecture paper is amended

§2 of `CORE-Mind-Body-Will-Separation.md` is updated to acknowledge
CLI's existence and position explicitly:

> *`src/cli/` is an operator-facing client application. It sits outside
> CORE's three-layer model. It calls CORE exclusively through the API
> entry-point boundary defined in §6. It is governed by
> `architecture.cli.api_only` (ADR-050).*

§6 is updated to name both API and CLI in the entry-boundary topology
diagram, with CLI shown as a caller of API, not a parallel entry point.

---

## Migration

The ~80 current violations cannot be resolved before this ADR lands;
they are the reason it exists. The resolution sequence is:

1. **Resolve Will → CLI inversions first (D3).** Five files; these
   are the most structurally damaging because they mean CORE already
   depends on its own client. These must be fixed before the rule lands.
2. **Add the blocking rule (D4) with a temporary global suppress.**
   The rule is authored, accepted, and visible in audit output as
   `SUPPRESSED — migration in progress`. This makes the violation
   count visible without blocking the daemon.
3. **Migrate CLI commands to API calls, command by command.** Each
   migrated command removes imports from the suppress list. The
   suppress list is the migration backlog — it shrinks to zero at
   migration completion.
4. **Remove the suppress and promote the rule to fully blocking.**
   At that point the audit verdict changes from `SUPPRESSED` to active
   enforcement. No new CLI → CORE direct import can land without an
   immediate audit failure.

Each batch of migrated commands that requires a new API endpoint
warrants a single focused PR. The migration is sequenced to prioritise
commands that already have a clear Will-workflow equivalent (sync,
proposals, audit) over commands that reach Body or Mind for
administrative diagnostics.

---

## Consequences

### Positive

- **CLI governance is fully closed by one rule.** No per-command
  exceptions, no per-import judgements. The rule is binary: CLI calls
  API or it fails audit.
- **API becomes the complete public contract of CORE.** If something
  is not in API, CLI cannot reach it. This forces API completeness
  rather than allowing CLI to silently bypass it.
- **The paper's "exactly three layers" claim becomes true.** CLI is
  formally outside the system; the §2 claim is no longer contradicted
  by the perimeter rule.
- **Will → CLI inversions are eliminated.** CORE stops depending on
  its own operator client.
- **Future commands cannot accumulate ungoverned imports.** The rule
  fails audit at PR time, not at the next architecture review.

### Negative

- **Migration surface is large.** ~80 import sites across ~50 CLI
  files. Several will require new API endpoints before the CLI command
  can be migrated cleanly.
- **API must grow to cover operator use cases.** Some current CLI →
  Body/Mind imports reach administrative and diagnostic functionality
  that has no API equivalent today. Those endpoints must be designed
  and added before the corresponding CLI commands can be cleaned up.
- **Migration is not atomic.** The suppress-then-drain approach means
  there is a window where violations are visible but not blocking. That
  window should be treated as a tracked debt, not a normal state.

### Neutral

- The CLI user experience does not change. Commands continue to work
  during migration; the change is internal to how they are implemented.
- `src/cli/` is not deleted or restructured. It remains the operator
  interface; only its import dependencies change.

---

## Verification

This ADR is verified when:

1. **Rule `architecture.cli.api_only` exists and is active** in
   `layer_separation.yaml` as `ast_gate import_boundary`, applies to
   `src/cli/**/*.py`, forbids `will`, `body`, `mind`, `shared` (and
   `src.` variants), and has an empty `excludes:` list.

2. **Zero Will → CLI imports exist** in `src/will/**/*.py`. A grep
   for `from cli.` and `import cli.` in `src/will/` returns no results.

3. **A full audit run reports zero findings under
   `architecture.cli.api_only`.** All CLI commands exercise their
   functionality through `api.*` imports only.

4. **The architecture paper §2 and §6 are updated** per D5, with CLI
   named explicitly as an operator client outside the three-layer model.

5. **No `excludes:` entries exist in the rule at verification time.**
   The migration is complete, not suppressed.

---

## References

- `.specs/papers/CORE-Mind-Body-Will-Separation.md:§2` — "exactly three
  layers" claim (contradicted by CLI's current existence outside the
  model).
- `.specs/papers/CORE-Mind-Body-Will-Separation.md:§6` — API as
  entrypoint boundary (the model this ADR extends to CLI).
- ADR-049 — doctrine-rule parity; establishes the pattern this ADR
  follows for closing rule gaps.
- 2026-05-15 full architecture audit — source of all CLI finding counts
  and the Will → CLI inversion list.
- `src/will/workflows/phases/code_fixers_phase.py:13-15` — Will → CLI
  inversions (fix_headers_internal, fix_ids_internal, LoggingFixer).
- `src/will/workflows/phases/quality_checks_phase.py:9` — Will → CLI
  inversion (check_body_contracts).
- `src/will/workflows/phases/code_analysis_phase.py:9` — Will → CLI
  inversion (inspect_duplicates_async).
- `.intent/enforcement/mappings/architecture/layer_separation.yaml` —
  target file for the new rule (D4).
