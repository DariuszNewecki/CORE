# Nested-Scope Audit — 2026-04-19

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

## Full Detail — every blind-spot pair

_Grouped by rule. Rows with **YES** in "In excludes?" will not surface when the engine is fixed._

### `logic.di.no_global_session`
_.intent/enforcement/mappings/architecture/async_logic.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/services/**/*.py` | `src/body/services/__init__.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/artifact_service.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/audit_findings_service.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/blackboard_service.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/capabilities.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/consequence_log_service.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/constitutional_validator.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/crate_creation_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/crate_processing_service.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/database_service.py` | no | contains database session import |
| `src/body/services/**/*.py` | `src/body/services/doc_service.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/file_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/governance_init.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/health_log_service.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/intent_schema_validator.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/llm_client.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/mind_state_service.py` | no | contains database session import |
| `src/body/services/**/*.py` | `src/body/services/policy_expression_evaluator.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/service_registry.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/symbol_query_service.py` | no | contains database session import |
| `src/body/services/**/*.py` | `src/body/services/symbol_service.py` | no | contains layer imports |
| `src/body/services/**/*.py` | `src/body/services/worker_registry_service.py` | no | contains layer imports |

### `atomic_actions.fix_action_scope`
_.intent/enforcement/mappings/architecture/atomic_actions.yaml_  — engine=`advisory` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/atomic/**/*.py` | `src/body/atomic/__init__.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/build_tests_action.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/check_actions.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/crate_ops.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/executor.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/file_ops.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/fix_actions.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/import_resolver.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/metadata_ops.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_fix.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_splitter.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/registry.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/remediate_cognitive_role.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/split_plan.py` | no | check_type='?' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/sync_actions.py` | no | check_type='?' not analyzed |

### `atomic_actions.must_have_decorator`
_.intent/enforcement/mappings/architecture/atomic_actions.yaml_  — engine=`python_runtime` / check_type=`registration_time_validation`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/atomic/**/*.py` | `src/body/atomic/__init__.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/build_tests_action.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/check_actions.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/crate_ops.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/executor.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/file_ops.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/fix_actions.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/import_resolver.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/metadata_ops.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_fix.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_splitter.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/registry.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/remediate_cognitive_role.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/split_plan.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/sync_actions.py` | no | check_type='registration_time_validation' not analyzed |

### `atomic_actions.must_return_action_result`
_.intent/enforcement/mappings/architecture/atomic_actions.yaml_  — engine=`python_runtime` / check_type=`registration_time_validation`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/atomic/**/*.py` | `src/body/atomic/__init__.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/build_tests_action.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/check_actions.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/crate_ops.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/executor.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/file_ops.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/fix_actions.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/import_resolver.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/metadata_ops.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_fix.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_splitter.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/registry.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/remediate_cognitive_role.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/split_plan.py` | no | check_type='registration_time_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/sync_actions.py` | no | check_type='registration_time_validation' not analyzed |

### `atomic_actions.no_governance_bypass`
_.intent/enforcement/mappings/architecture/atomic_actions.yaml_  — engine=`python_runtime` / check_type=`comprehensive_validation`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/atomic/**/*.py` | `src/body/atomic/__init__.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/build_tests_action.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/check_actions.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/crate_ops.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/executor.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/file_ops.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/fix_actions.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/import_resolver.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/metadata_ops.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_fix.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_splitter.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/registry.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/remediate_cognitive_role.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/split_plan.py` | no | check_type='comprehensive_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/sync_actions.py` | no | check_type='comprehensive_validation' not analyzed |

### `atomic_actions.result_must_be_structured`
_.intent/enforcement/mappings/architecture/atomic_actions.yaml_  — engine=`python_runtime` / check_type=`runtime_validation`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/atomic/**/*.py` | `src/body/atomic/__init__.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/build_tests_action.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/check_actions.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/crate_ops.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/executor.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/file_ops.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/fix_actions.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/import_resolver.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/metadata_ops.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_fix.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_splitter.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/registry.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/remediate_cognitive_role.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/split_plan.py` | no | check_type='runtime_validation' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/sync_actions.py` | no | check_type='runtime_validation' not analyzed |

### `architecture.channels.api_structured_output_only`
_.intent/enforcement/mappings/architecture/channels.yaml_  — engine=`ast_gate` / check_type=`forbidden_imports_and_calls`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/api/**/*.py` | `src/api/__init__.py` | no | check_type='forbidden_imports_and_calls' not analyzed |
| `src/api/**/*.py` | `src/api/dependencies.py` | no | check_type='forbidden_imports_and_calls' not analyzed |
| `src/api/**/*.py` | `src/api/errors.py` | no | check_type='forbidden_imports_and_calls' not analyzed |
| `src/api/**/*.py` | `src/api/main.py` | no | check_type='forbidden_imports_and_calls' not analyzed |

### `architecture.channels.cli_rendering_allowed`
_.intent/enforcement/mappings/architecture/channels.yaml_  — engine=`advisory` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/cli/**/*.py` | `src/cli/__init__.py` | no | check_type='?' not analyzed |
| `src/cli/**/*.py` | `src/cli/admin_cli.py` | no | check_type='?' not analyzed |
| `src/cli/**/*.py` | `src/cli/cli_user.py` | no | check_type='?' not analyzed |
| `src/cli/**/*.py` | `src/cli/interactive.py` | no | check_type='?' not analyzed |

### `architecture.api.no_body_bypass`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/api/**/*.py` | `src/api/__init__.py` | no | none detected |
| `src/api/**/*.py` | `src/api/dependencies.py` | no | contains database session import |
| `src/api/**/*.py` | `src/api/errors.py` | no | none detected |
| `src/api/**/*.py` | `src/api/main.py` | no | contains layer imports |

### `architecture.api.no_direct_database_access`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/api/**/*.py` | `src/api/__init__.py` | no | none detected |
| `src/api/**/*.py` | `src/api/dependencies.py` | no | contains database session import |
| `src/api/**/*.py` | `src/api/errors.py` | no | none detected |
| `src/api/**/*.py` | `src/api/main.py` | no | contains layer imports |

### `architecture.body.no_rule_evaluation`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/**/*.py` | `src/body/__init__.py` | no | none detected |

### `architecture.layers.no_body_to_will`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/**/*.py` | `src/body/__init__.py` | no | none detected |

### `architecture.layers.no_mind_execution`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`knowledge_gate` / check_type=`component_responsibility`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | check_type='component_responsibility' not analyzed |

### `architecture.mind.no_body_invocation`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | none detected |

### `architecture.mind.no_database_access`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | none detected |

### `architecture.mind.no_filesystem_writes`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`no_direct_writes`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | none detected |

### `architecture.mind.no_will_invocation`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | none detected |

### `architecture.shared.no_layer_imports`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/shared/**/*.py` | `src/shared/__init__.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/action_logger.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/action_types.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/activity_logging.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/ast_utility.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/atomic_action.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/cli_types.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/component_primitive.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/config.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/config_loader.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/context.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/exceptions.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/governance_token.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/logger.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/path_resolver.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/path_utils.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/time.py` | no | none detected |
| `src/shared/**/*.py` | `src/shared/universal.py` | no | none detected |

### `architecture.shared.no_strategic_decisions`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`knowledge_gate` / check_type=`component_responsibility`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/shared/**/*.py` | `src/shared/__init__.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/action_logger.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/action_types.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/activity_logging.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/ast_utility.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/atomic_action.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/cli_types.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/component_primitive.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/config.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/config_loader.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/context.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/exceptions.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/governance_token.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/logger.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/path_resolver.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/path_utils.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/time.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/**/*.py` | `src/shared/universal.py` | no | check_type='component_responsibility' not analyzed |

### `architecture.will.must_delegate_to_body`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`knowledge_gate` / check_type=`component_responsibility`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/will/agents/**/*.py` | `src/will/agents/__init__.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/base_planner.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/coder_agent.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/coder_agent_refusal_handler.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/cognitive_orchestrator.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/execution_agent.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/governance_mixin.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/micro_planner.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/plan_executor.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/planner_agent.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/resource_selector.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/self_healing_agent.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/tagger_agent.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/traced_agent_mixin.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/__init__.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/cognitive_service.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/decision_tracer.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/intent_alignment.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/intent_guard.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/phase_registry.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/process_orchestrator.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/prompt_pipeline.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/remediation_orchestrator.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/self_correction_engine.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/validation_pipeline.py` | no | check_type='component_responsibility' not analyzed |
| `src/will/orchestration/**/*.py` | `src/will/orchestration/workflow_orchestrator.py` | no | check_type='component_responsibility' not analyzed |

### `architecture.will.no_direct_database_access`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/will/**/*.py` | `src/will/__init__.py` | no | none detected |

### `architecture.will.no_filesystem_operations`
_.intent/enforcement/mappings/architecture/layer_separation.yaml_  — engine=`ast_gate` / check_type=`no_direct_writes`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/will/**/*.py` | `src/will/__init__.py` | no | none detected |

### `architecture.mind.no_execution_semantics`
_.intent/enforcement/mappings/architecture/mind_execution_semantics.yaml_  — engine=`llm_gate` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | check_type='?' not analyzed |

### `architecture.patterns.action_pattern`
_.intent/enforcement/mappings/architecture/patterns.yaml_  — engine=`ast_gate` / check_type=`action_pattern`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/atomic/**/*.py` | `src/body/atomic/__init__.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/build_tests_action.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/check_actions.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/crate_ops.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/executor.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/file_ops.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/fix_actions.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/import_resolver.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/metadata_ops.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_fix.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/modularity_splitter.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/registry.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/remediate_cognitive_role.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/split_plan.py` | no | check_type='action_pattern' not analyzed |
| `src/body/atomic/**/*.py` | `src/body/atomic/sync_actions.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/__init__.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/audit_reporter.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/check_atomic_actions.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/components.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/daemon.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/dev_sync.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/develop.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/diagnostics.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/fix_governed.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/fix_logging.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/governance.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/guard.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/interactive_test.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/mind.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/refactor.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/repo_census.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/run.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/search.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/status.py` | no | check_type='action_pattern' not analyzed |
| `src/cli/commands/**/*.py` | `src/cli/commands/submit.py` | no | check_type='action_pattern' not analyzed |

### `architecture.boundary.database_session_access`
_.intent/enforcement/mappings/architecture/privileged_boundaries.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | none detected |
| `src/will/**/*.py` | `src/will/__init__.py` | no | none detected |

### `architecture.boundary.file_handler_access`
_.intent/enforcement/mappings/architecture/privileged_boundaries.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | none detected |
| `src/will/**/*.py` | `src/will/__init__.py` | no | none detected |

### `architecture.boundary.llm_client_access`
_.intent/enforcement/mappings/architecture/privileged_boundaries.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/**/*.py` | `src/body/__init__.py` | no | none detected |
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | none detected |

### `architecture.boundary.settings_access`
_.intent/enforcement/mappings/architecture/privileged_boundaries.yaml_  — engine=`ast_gate` / check_type=`import_boundary`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/**/*.py` | `src/body/__init__.py` | no | none detected |
| `src/mind/**/*.py` | `src/mind/__init__.py` | no | none detected |
| `src/will/**/*.py` | `src/will/__init__.py` | no | none detected |

### `cli.async_execution`
_.intent/enforcement/mappings/cli/interface_design.yaml_  — engine=`python_runtime` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/cli/resources/**/*.py` | `src/cli/resources/__init__.py` | no | check_type='?' not analyzed |

### `cli.dangerous_explicit`
_.intent/enforcement/mappings/cli/interface_design.yaml_  — engine=`runtime_check` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/cli/resources/**/*.py` | `src/cli/resources/__init__.py` | no | check_type='?' not analyzed |

### `cli.discovery_strict`
_.intent/enforcement/mappings/cli/interface_design.yaml_  — engine=`python_runtime` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/cli/resources/**/*.py` | `src/cli/resources/__init__.py` | no | check_type='?' not analyzed |

### `cli.help_required`
_.intent/enforcement/mappings/cli/interface_design.yaml_  — engine=`runtime_check` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/cli/resources/**/*.py` | `src/cli/resources/__init__.py` | no | check_type='?' not analyzed |

### `cli.no_layer_exposure`
_.intent/enforcement/mappings/cli/interface_design.yaml_  — engine=`runtime_check` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/cli/resources/**/*.py` | `src/cli/resources/__init__.py` | no | check_type='?' not analyzed |

### `cli.resource_first`
_.intent/enforcement/mappings/cli/interface_design.yaml_  — engine=`runtime_check` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/cli/resources/**/*.py` | `src/cli/resources/__init__.py` | no | check_type='?' not analyzed |

### `cli.standard_verbs`
_.intent/enforcement/mappings/cli/interface_design.yaml_  — engine=`runtime_check` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/cli/resources/**/*.py` | `src/cli/resources/__init__.py` | no | check_type='?' not analyzed |

### `purity.docstrings.required`
_.intent/enforcement/mappings/code/purity.yaml_  — engine=`llm_gate` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/**/*.py` | `src/body/__init__.py` | no | check_type='?' not analyzed |
| `src/will/**/*.py` | `src/will/__init__.py` | no | check_type='?' not analyzed |

### `data.ssot.database_primacy`
_.intent/enforcement/mappings/data/governance.yaml_  — engine=`ast_gate` / check_type=`forbidden_assignments`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/body/services/**/*.py` | `src/body/services/__init__.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/artifact_service.py` | no | contains module-level uppercase assignment |
| `src/body/services/**/*.py` | `src/body/services/audit_findings_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/blackboard_service.py` | no | contains module-level uppercase assignment |
| `src/body/services/**/*.py` | `src/body/services/capabilities.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/consequence_log_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/constitutional_validator.py` | no | contains module-level uppercase assignment |
| `src/body/services/**/*.py` | `src/body/services/crate_creation_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/crate_processing_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/database_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/doc_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/file_service.py` | no | contains module-level uppercase assignment |
| `src/body/services/**/*.py` | `src/body/services/governance_init.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/health_log_service.py` | no | contains module-level uppercase assignment |
| `src/body/services/**/*.py` | `src/body/services/intent_schema_validator.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/llm_client.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/mind_state_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/policy_expression_evaluator.py` | no | contains module-level uppercase assignment |
| `src/body/services/**/*.py` | `src/body/services/service_registry.py` | no | contains module-level uppercase assignment |
| `src/body/services/**/*.py` | `src/body/services/symbol_query_service.py` | no | none detected |
| `src/body/services/**/*.py` | `src/body/services/symbol_service.py` | no | contains module-level uppercase assignment |
| `src/body/services/**/*.py` | `src/body/services/worker_registry_service.py` | no | none detected |

### `infrastructure.no_bare_except`
_.intent/enforcement/mappings/infrastructure/authority_boundaries.yaml_  — engine=`regex_gate` / check_type=`?`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/__init__.py` | no | check_type='?' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/bootstrap_registry.py` | no | check_type='?' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/config_service.py` | no | check_type='?' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/config_validator.py` | no | check_type='?' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/diagnostic_service.py` | no | check_type='?' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/git_service.py` | no | check_type='?' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/knowledge_graph_service.py` | no | check_type='?' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/secrets_service.py` | no | check_type='?' not analyzed |

### `infrastructure.no_business_logic`
_.intent/enforcement/mappings/infrastructure/authority_boundaries.yaml_  — engine=`knowledge_gate` / check_type=`component_responsibility`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/__init__.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/bootstrap_registry.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/config_service.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/config_validator.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/diagnostic_service.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/git_service.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/knowledge_graph_service.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/secrets_service.py` | no | check_type='component_responsibility' not analyzed |

### `infrastructure.no_strategic_decisions`
_.intent/enforcement/mappings/infrastructure/authority_boundaries.yaml_  — engine=`knowledge_gate` / check_type=`component_responsibility`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/__init__.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/bootstrap_registry.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/config_service.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/config_validator.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/diagnostic_service.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/git_service.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/knowledge_graph_service.py` | no | check_type='component_responsibility' not analyzed |
| `src/shared/infrastructure/**/*.py` | `src/shared/infrastructure/secrets_service.py` | no | check_type='component_responsibility' not analyzed |

### `autonomy.lanes.boundary_enforcement`
_.intent/enforcement/mappings/will/autonomy.yaml_  — engine=`glob_gate` / check_type=`path_restriction`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/will/agents/**/*.py` | `src/will/agents/__init__.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/base_planner.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/coder_agent.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/coder_agent_refusal_handler.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/cognitive_orchestrator.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/execution_agent.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/governance_mixin.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/micro_planner.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/plan_executor.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/planner_agent.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/resource_selector.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/self_healing_agent.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/tagger_agent.py` | no | check_type='path_restriction' not analyzed |
| `src/will/agents/**/*.py` | `src/will/agents/traced_agent_mixin.py` | no | check_type='path_restriction' not analyzed |

### `autonomy.tracing.mandatory`
_.intent/enforcement/mappings/will/autonomy.yaml_  — engine=`ast_gate` / check_type=`generic_primitive`

| Pattern | Blind-spot file | In excludes? | Violation signal |
|---|---|---|---|
| `src/will/agents/**/*.py` | `src/will/agents/__init__.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/base_planner.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/coder_agent.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/coder_agent_refusal_handler.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/cognitive_orchestrator.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/execution_agent.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/governance_mixin.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/micro_planner.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/plan_executor.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/planner_agent.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/resource_selector.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/self_healing_agent.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/tagger_agent.py` | no | check needs selector-based inspection |
| `src/will/agents/**/*.py` | `src/will/agents/traced_agent_mixin.py` | no | check needs selector-based inspection |
