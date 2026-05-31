# Nested-Scope Audit — 2026-04-19

> ### ⚠️ SUPERSEDED — 2026-04-20
>
> **The engine asymmetry this document analyses has been compensated. Original body preserved below as historical record.**
>
> **Engine fix:** `AuditorContext.get_files` now contains an `_include_matches` helper that collapses `**/` and `/**` to handle the zero-intermediate-directory case. Commit `8e9325fb` (2026-04-18). Live verification 2026-04-20: `_include_matches('src/will/agents/self_healing_agent.py', 'src/will/agents/**/*.py') = True`; `_include_matches('src/api/main.py', 'src/api/**/*.py') = True`.
>
> **Module path correction:** `AuditorContext` lives at `src/mind/governance/audit_context.py`, not `src/mind/logic/engines/ast_gate/base.py`. The body below's "line 48748 in the export" and "`ast_gate.base`" citations are stale.
>
> **Impact on the classification below:**
>
> - **HIDDEN DEBT (4 rules)** — this section is obsolete. The files listed as "blind-spot files" are now in scope. Three of the four were tactically patched with dual-pattern scopes in the 2026-04-19 session; those dual patterns are now redundant (harmless but removable). The fourth (`logic.di.no_global_session`) should have had its hidden findings surface once the fix landed; the 2026-04-20 audit shows no such findings, which means either (a) the hidden debt was resolved between document authoring and audit, (b) the dual-pattern patches are still doing the work, or (c) the signal classification in this audit was optimistic. Worth a spot-check when time permits.
>
> - **REVIEW (25 rules)** — still applies. These rules use opaque check types (`generic_primitive`, `required_calls`, `component_responsibility`, `path_restriction`, etc.) that cannot be evaluated statically. The engine fix does not change this bucket's status — they still need per-rule live verification if trusted coverage matters.
>
> - **OK (13 rules)** — still applies. No top-level files existed under these bases, or files existed but showed no violation signals.
>
> **Why preserved:** the document's methodology (static classification of scope-pattern blind spots) remains a valid pattern for future scope-pattern investigations. The HIDDEN DEBT inventory is a historical artifact of a condition that no longer applies.
>
> See:
> - `state/tracing_mandatory_diagnostic_2026-04-20.md` (falsifies `autonomy.tracing.mandatory` silent non-firing — row in the REVIEW table below)
> - `state/reconnaissance_2026-04-20.md` (ground-truth sweep, Section 7 verifies the fnmatch fix live)
> - `planning/CORE-A3-plan.md` — Resolved Blockers section (updated 2026-04-20)

---

**Purpose:** For every enforcement rule whose `applies_to` uses a `src/X/**/*.py` pattern, identify which top-level files under `src/X/` are silently skipped by Python's `fnmatch.fnmatch` semantics (include path in `AuditorContext.get_files`, line 48748).

**Background:** `fnmatch.fnmatch('src/api/main.py', 'src/api/**/*.py')` → `False`. The `**` in fnmatch does not match zero intermediate directories — it requires at least one. So any rule scoped `src/X/**/*.py` cannot see files at `src/X/*.py`. The exclude path in `get_files` hand-rolls `**` logic correctly; only the include path has the asymmetry.

**Snapshot caveat:** Analysis is against `context_core.txt` exported 2026-04-18. Three rules listed as HIDDEN DEBT below were already fixed in today's 2026-04-19 session and will not appear as issues after a fresh export:
- `architecture.api.no_body_bypass` — dual-pattern scope applied
- `architecture.api.no_direct_database_access` — dual-pattern scope applied
- `data.ssot.database_primacy` — scope widened to `src/**/*.py`

The one remaining live HIDDEN DEBT rule is `logic.di.no_global_session`.

**Classification scheme:**
- **HIDDEN DEBT** — top-level files exist, not in excludes, and show signals the rule is looking for. Would fire once the engine is fixed.
- **REVIEW** — top-level files exist but the check type can't be statically analyzed without running the engine (selector-based, LLM-based, or passive engines). Human inspection needed.
- **OK** — no top-level files under the base, or all signals are clean. Fixing the fnmatch asymmetry surfaces nothing here.

**Stats:** 42 rules use nested scope patterns, out of 123 total rules.
- HIDDEN DEBT: **4** rules
- REVIEW: **25** rules
- OK: **13** rules

## Hidden Debt — rules that will surface findings after the engine fix

| Rule | Mapping | check_type | # Debt files | Example |
|---|---|---|---|---|
| `logic.di.no_global_session` | `async_logic.yaml` | `import_boundary` | 14 | `src/body/services/artifact_service.py` (contains layer imports) |
| `data.ssot.database_primacy` | `governance.yaml` | `forbidden_assignments` | 8 | `src/body/services/artifact_service.py` (contains module-level uppercase assignment) |
| `architecture.api.no_direct_database_access` | `layer_separation.yaml` | `import_boundary` | 2 | `src/api/dependencies.py` (contains database session import) |
| `architecture.api.no_body_bypass` | `layer_separation.yaml` | `import_boundary` | 2 | `src/api/dependencies.py` (contains database session import) |

## Review Needed — rules with opaque check types

Check types like `generic_primitive`, `required_calls`, `registration_time_validation`, `component_responsibility`, or passive engines cannot be evaluated statically. These rules may have hidden debt but need engine-assisted or human inspection.

| Rule | Mapping | check_type | # Top-level files |
|---|---|---|---|
| `atomic_actions.must_return_action_result` | `atomic_actions.yaml` | `registration_time_validation` | 15 |
| `atomic_actions.must_have_decorator` | `atomic_actions.yaml` | `registration_time_validation` | 15 |
| `atomic_actions.result_must_be_structured` | `atomic_actions.yaml` | `runtime_validation` | 15 |
| `atomic_actions.no_governance_bypass` | `atomic_actions.yaml` | `comprehensive_validation` | 15 |
| `atomic_actions.fix_action_scope` | `atomic_actions.yaml` | `?` | 15 |
| `architecture.channels.api_structured_output_only` | `channels.yaml` | `forbidden_imports_and_calls` | 4 |
| `architecture.channels.cli_rendering_allowed` | `channels.yaml` | `?` | 4 |
| `architecture.will.must_delegate_to_body` | `layer_separation.yaml` | `component_responsibility` | 26 |
| `architecture.layers.no_mind_execution` | `layer_separation.yaml` | `component_responsibility` | 1 |
| `architecture.shared.no_strategic_decisions` | `layer_separation.yaml` | `component_responsibility` | 18 |
| `architecture.mind.no_execution_semantics` | `mind_execution_semantics.yaml` | `?` | 1 |
| `architecture.patterns.action_pattern` | `patterns.yaml` | `action_pattern` | 35 |
| `cli.resource_first` | `interface_design.yaml` | `?` | 1 |
| `cli.no_layer_exposure` | `interface_design.yaml` | `?` | 1 |
| `cli.standard_verbs` | `interface_design.yaml` | `?` | 1 |
| `cli.dangerous_explicit` | `interface_design.yaml` | `?` | 1 |
| `cli.async_execution` | `interface_design.yaml` | `?` | 1 |
| `cli.discovery_strict` | `interface_design.yaml` | `?` | 1 |
| `cli.help_required` | `interface_design.yaml` | `?` | 1 |
| `purity.docstrings.required` | `purity.yaml` | `?` | 2 |
| `infrastructure.no_strategic_decisions` | `authority_boundaries.yaml` | `component_responsibility` | 8 |
| `infrastructure.no_business_logic` | `authority_boundaries.yaml` | `component_responsibility` | 8 |
| `infrastructure.no_bare_except` | `authority_boundaries.yaml` | `?` | 8 |
| `autonomy.lanes.boundary_enforcement` | `autonomy.yaml` | `path_restriction` | 14 |
| `autonomy.tracing.mandatory` | `autonomy.yaml` | `generic_primitive` | 14 |

## OK — rules whose blind spot is harmless

These rules use nested scope but either have no top-level files to miss, or the top-level files show no violation signals.

| Rule | Mapping | # Top-level files examined |
|---|---|---|
| `architecture.mind.no_database_access` | `layer_separation.yaml` | 1 |
| `architecture.mind.no_filesystem_writes` | `layer_separation.yaml` | 1 |
| `architecture.mind.no_body_invocation` | `layer_separation.yaml` | 1 |
| `architecture.mind.no_will_invocation` | `layer_separation.yaml` | 1 |
| `architecture.body.no_rule_evaluation` | `layer_separation.yaml` | 1 |
| `architecture.will.no_direct_database_access` | `layer_separation.yaml` | 1 |
| `architecture.will.no_filesystem_operations` | `layer_separation.yaml` | 1 |
| `architecture.layers.no_body_to_will` | `layer_separation.yaml` | 1 |
| `architecture.shared.no_layer_imports` | `layer_separation.yaml` | 18 |
| `architecture.boundary.database_session_access` | `privileged_boundaries.yaml` | 2 |
| `architecture.boundary.settings_access` | `privileged_boundaries.yaml` | 3 |
| `architecture.boundary.file_handler_access` | `privileged_boundaries.yaml` | 2 |
| `architecture.boundary.llm_client_access` | `privileged_boundaries.yaml` | 2 |

*The full per-rule detail table from the original document is preserved in git history at this path prior to the 2026-04-20 supersession. It has been truncated here for brevity; the full inventory can be recovered with `git log -p -- .specs/state/nested_scope_audit_2026-04-19.md`.*
