# 10. Capability Reference

This document is the canonical, auto-generated reference for all capabilities recognized by the CORE constitution.
It is generated from the `core.knowledge_graph` database view and should not be edited manually.

## Domain: `admin.byor`

- **`admin.byor.initialize`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/byor.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/byor.py#L1)

## Domain: `admin.key_management`

- **`admin.key_management.generate_keypair`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/key_management_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/key_management_service.py#L1)

## Domain: `alias.resolution`

- **`alias.resolution.resolve`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/alias_resolver.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/alias_resolver.py#L1)

## Domain: `ast.definition.line`

- **`ast.definition.line.find`**
  - **Description:** No description provided.
  - **Source:** [src/shared/ast_utility.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/ast_utility.py#L1)

## Domain: `ast.symbol`

- **`ast.symbol.resolve`**
  - **Description:** No description provided.
  - **Source:** [src/shared/ast_utility.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/ast_utility.py#L1)

## Domain: `ast.symbol.definition`

- **`ast.symbol.definition.resolve`**
  - **Description:** No description provided.
  - **Source:** [src/shared/ast_utility.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/ast_utility.py#L1)

## Domain: `async.processing`

- **`async.processing.execute`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/parallel_processor.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/parallel_processor.py#L1)

## Domain: `audit`

- **`audit.list`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/list_audits.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/list_audits.py#L1)

## Domain: `audit.finding`

- **`audit.finding.serialize`**
  - **Description:** No description provided.
  - **Source:** [src/shared/models/audit_models.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/models/audit_models.py#L1)

## Domain: `audit.run`

- **`audit.run.create`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/log_audit.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/log_audit.py#L1)

## Domain: `audit.severity`

- **`audit.severity.is_blocking`**
  - **Description:** No description provided.
  - **Source:** [src/shared/models/audit_models.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/models/audit_models.py#L1)

## Domain: `capability.maintenance`

- **`capability.maintenance.prune_private`**
  - **Description:** No description provided.
  - **Source:** [src/features/self_healing/prune_private_capabilities.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/self_healing/prune_private_capabilities.py#L1)

## Domain: `capability.meta`

- **`capability.meta.key`**
  - **Description:** No description provided.
  - **Source:** [src/shared/models/capability_models.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/models/capability_models.py#L1)

## Domain: `charter.policies`

- **`charter.policies.repair_ids`**
  - **Description:** No description provided.
  - **Source:** [src/features/self_healing/policy_id_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/self_healing/policy_id_service.py#L1)

## Domain: `cli.admin`

- **`cli.admin.tree`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/diagnostics.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/diagnostics.py#L1)

## Domain: `cli.code`

- **`cli.code.review`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/reviewer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/reviewer.py#L1)

## Domain: `cli.commands`

- **`cli.commands.register`**
  - **Description:** No description provided.
  - **Source:** [src/cli/commands/inspect.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/commands/inspect.py#L1)

## Domain: `cli.logic`

- **`cli.logic.reconcile`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/reconcile.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/reconcile.py#L1)

## Domain: `cli.logic.tools`

- **`cli.logic.tools.rewire_imports`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/tools.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/tools.py#L1)

## Domain: `cli.registry`

- **`cli.registry.validate`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/diagnostics.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/diagnostics.py#L1)

## Domain: `cli.search`

- **`cli.search.capabilities`**
  - **Description:** No description provided.
  - **Source:** [src/cli/commands/search.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/commands/search.py#L1)

## Domain: `cli.tools`

- **`cli.tools.register`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/tools.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/tools.py#L1)

## Domain: `code.function`

- **`code.function.edit`**
  - **Description:** No description provided.
  - **Source:** [src/core/actions/code_actions.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/actions/code_actions.py#L1)

## Domain: `code.python`

- **`code.python.validate`**
  - **Description:** No description provided.
  - **Source:** [src/core/python_validator.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/python_validator.py#L1)

## Domain: `code.validation`

- **`code.validation.execute`**
  - **Description:** No description provided.
  - **Source:** [src/core/validation_pipeline.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/validation_pipeline.py#L1)

## Domain: `constitution.audit`

- **`constitution.audit.review`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/reviewer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/reviewer.py#L1)

## Domain: `context.plan`

- **`context.plan.executor`**
  - **Description:** No description provided.
  - **Source:** [src/core/actions/context.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/actions/context.py#L1)

## Domain: `core.actions`

- **`core.actions.execute`**
  - **Description:** No description provided.
  - **Source:** [src/core/actions/base.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/actions/base.py#L1)

## Domain: `core.agents`

- **`core.agents.execution`**
  - **Description:** No description provided.
  - **Source:** [src/core/agents/execution_agent.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/agents/execution_agent.py#L1)
- **`core.agents.reconnaissance`**
  - **Description:** No description provided.
  - **Source:** [src/core/agents/reconnaissance_agent.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/agents/reconnaissance_agent.py#L1)

## Domain: `core.proposal`

- **`core.proposal.approve`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/crypto.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/crypto.py#L1)

## Domain: `core.self_correction`

- **`core.self_correction.attempt_correction`**
  - **Description:** No description provided.
  - **Source:** [src/core/self_correction_engine.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/self_correction_engine.py#L1)

## Domain: `core.system`

- **`core.system.greet`**
  - **Description:** No description provided.
  - **Source:** [src/features/demo/hello_world.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/demo/hello_world.py#L1)

## Domain: `crate.processing`

- **`crate.processing.execute`**
  - **Description:** No description provided.
  - **Source:** [src/core/crate_processing_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/crate_processing_service.py#L1)

## Domain: `data.export`

- **`data.export.execute`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/db.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/db.py#L1)

## Domain: `database.migration`

- **`database.migration.read`**
  - **Description:** No description provided.
  - **Source:** [src/services/repositories/db/common.py](https://github.com/DariuszNewecki/CORE/blob/main/src/services/repositories/db/common.py#L1)

## Domain: `db.sql`

- **`db.sql.apply`**
  - **Description:** No description provided.
  - **Source:** [src/services/repositories/db/common.py](https://github.com/DariuszNewecki/CORE/blob/main/src/services/repositories/db/common.py#L1)

## Domain: `diagnostics.clustering`

- **`diagnostics.clustering.find`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/diagnostics.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/diagnostics.py#L1)

## Domain: `diagnostics.debug`

- **`diagnostics.debug.meta_paths`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/diagnostics.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/diagnostics.py#L1)

## Domain: `docs.clarity`

- **`docs.clarity.audit`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/reviewer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/reviewer.py#L1)

## Domain: `drift.report`

- **`drift.report.serialize`**
  - **Description:** No description provided.
  - **Source:** [src/shared/models/drift_models.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/models/drift_models.py#L1)

## Domain: `embedding.chunk`

- **`embedding.chunk.average`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/embedding_utils.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/embedding_utils.py#L1)

## Domain: `embedding.factory`

- **`embedding.factory.create`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/embedding_utils.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/embedding_utils.py#L1)

## Domain: `execution.orchestrator`

- **`execution.orchestrator.execute`**
  - **Description:** No description provided.
  - **Source:** [src/core/agents/plan_executor.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/agents/plan_executor.py#L1)

## Domain: `execution.task`

- **`execution.task.create`**
  - **Description:** No description provided.
  - **Source:** [src/shared/models/execution_models.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/models/execution_models.py#L1)

## Domain: `file`

- **`file.create`**
  - **Description:** No description provided.
  - **Source:** [src/core/actions/code_actions.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/actions/code_actions.py#L1)
- **`file.delete`**
  - **Description:** No description provided.
  - **Source:** [src/core/actions/file_actions.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/actions/file_actions.py#L1)
- **`file.edit`**
  - **Description:** No description provided.
  - **Source:** [src/core/actions/code_actions.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/actions/code_actions.py#L1)

## Domain: `file.header`

- **`file.header.components`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/header_tools.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/header_tools.py#L1)
- **`file.header.parse_reconstruct`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/header_tools.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/header_tools.py#L1)

## Domain: `file.import`

- **`file.import.scan`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/import_scanner.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/import_scanner.py#L1)

## Domain: `file.list`

- **`file.list.read`**
  - **Description:** No description provided.
  - **Source:** [src/core/actions/file_actions.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/actions/file_actions.py#L1)

## Domain: `file.read`

- **`file.read.execute`**
  - **Description:** No description provided.
  - **Source:** [src/core/actions/file_actions.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/actions/file_actions.py#L1)

## Domain: `file.write`

- **`file.write.parse_blocks`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/parsing.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/parsing.py#L1)

## Domain: `git.repository.commit`

- **`git.repository.commit.get`**
  - **Description:** No description provided.
  - **Source:** [src/services/repositories/db/common.py](https://github.com/DariuszNewecki/CORE/blob/main/src/services/repositories/db/common.py#L1)

## Domain: `governance.audit`

- **`governance.audit.capability_coverage`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/capability_coverage.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/capability_coverage.py#L1)
- **`governance.audit.execute`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/base_check.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/base_check.py#L1)
- **`governance.audit.scope`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/constitutional_auditor.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/constitutional_auditor.py#L1)

## Domain: `governance.auditor`

- **`governance.auditor.context`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/audit_context.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/audit_context.py#L1)

## Domain: `governance.capability.assignment`

- **`governance.capability.assignment.orphaned_logic`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/orphaned_logic.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/orphaned_logic.py#L1)

## Domain: `governance.check`

- **`governance.check.result`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/knowledge_source_check.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/knowledge_source_check.py#L1)

## Domain: `governance.checks`

- **`governance.checks.domain_placement`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/domain_placement.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/domain_placement.py#L1)
- **`governance.checks.duplication`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/duplication_check.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/duplication_check.py#L1)
- **`governance.checks.legacy_tags`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/diagnostics.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/diagnostics.py#L1)
- **`governance.checks.manifest_lint`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/manifest_lint.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/manifest_lint.py#L1)
- **`governance.checks.orphaned_logic`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/diagnostics.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/diagnostics.py#L1)
- **`governance.checks.style`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/style_checks.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/style_checks.py#L1)

## Domain: `governance.diagnostics`

- **`governance.diagnostics.unassigned_symbols`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/audit_unassigned_capabilities.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/audit_unassigned_capabilities.py#L1)

## Domain: `governance.health`

- **`governance.health.analyze`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/health_checks.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/health_checks.py#L1)

## Domain: `governance.linkage.id`

- **`governance.linkage.id.coverage`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/id_coverage_check.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/id_coverage_check.py#L1)

## Domain: `governance.manifest`

- **`governance.manifest.domain_placement`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/diagnostics.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/diagnostics.py#L1)

## Domain: `governance.naming`

- **`governance.naming.validate`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/naming_conventions.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/naming_conventions.py#L1)

## Domain: `governance.policy`

- **`governance.policy.load_actions`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/policy_loader.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/policy_loader.py#L1)
- **`governance.policy.load_micro_proposal`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/policy_loader.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/policy_loader.py#L1)

## Domain: `governance.policy_coverage`

- **`governance.policy_coverage.generate`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/policy_coverage_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/policy_coverage_service.py#L1)

## Domain: `governance.proposal`

- **`governance.proposal.create`**
  - **Description:** No description provided.
  - **Source:** [src/core/actions/governance_actions.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/actions/governance_actions.py#L1)

## Domain: `governance.runtime.environment`

- **`governance.runtime.environment.verify`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/environment_checks.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/environment_checks.py#L1)

## Domain: `governance.security.secrets`

- **`governance.security.secrets.detect`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/security_checks.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/security_checks.py#L1)

## Domain: `governance.style`

- **`governance.style.no_legacy_capability_tags`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/checks/legacy_tag_check.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/checks/legacy_tag_check.py#L1)

## Domain: `introspection.alias_map`

- **`introspection.alias_map.generate`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/generate_correction_map.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/generate_correction_map.py#L1)

## Domain: `introspection.ast`

- **`introspection.ast.symbol_discovery`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/sync_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/sync_service.py#L1)

## Domain: `introspection.capability`

- **`introspection.capability.load`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/capability_discovery_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/capability_discovery_service.py#L1)

## Domain: `introspection.clustering`

- **`introspection.clustering.find_semantic_clusters`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/graph_analysis_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/graph_analysis_service.py#L1)
- **`introspection.clustering.run`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/semantic_clusterer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/semantic_clusterer.py#L1)

## Domain: `introspection.discovery`

- **`introspection.discovery.collect`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/capability_discovery_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/capability_discovery_service.py#L1)
- **`introspection.discovery.from_kgb`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/discovery/from_kgb.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/discovery/from_kgb.py#L1)
- **`introspection.discovery.from_source_scan`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/discovery/from_source_scan.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/discovery/from_source_scan.py#L1)

## Domain: `introspection.docs`

- **`introspection.docs.generate`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/project_docs.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/project_docs.py#L1)

## Domain: `introspection.documentation`

- **`introspection.documentation.generate`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/generate_capability_docs.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/generate_capability_docs.py#L1)

## Domain: `introspection.drift`

- **`introspection.drift.analyze`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/drift_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/drift_service.py#L1)
- **`introspection.drift.detect`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/drift_detector.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/drift_detector.py#L1)

## Domain: `introspection.knowledge`

- **`introspection.knowledge.build_sync`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/knowledge_graph_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/knowledge_graph_service.py#L1)

## Domain: `introspection.manifest`

- **`introspection.manifest.load`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/discovery/from_manifest.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/discovery/from_manifest.py#L1)

## Domain: `introspection.registry`

- **`introspection.registry.resolve`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/capability_discovery_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/capability_discovery_service.py#L1)

## Domain: `introspection.report`

- **`introspection.report.write`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/drift_detector.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/drift_detector.py#L1)

## Domain: `introspection.roles`

- **`introspection.roles.validate`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/capability_discovery_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/capability_discovery_service.py#L1)

## Domain: `introspection.source_code`

- **`introspection.source_code.extract`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/knowledge_helpers.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/knowledge_helpers.py#L1)

## Domain: `introspection.vectorization`

- **`introspection.vectorization.collect`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/knowledge_helpers.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/knowledge_helpers.py#L1)
- **`introspection.vectorization.retrieve_stored_chunks`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/knowledge_vectorizer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/knowledge_vectorizer.py#L1)
- **`introspection.vectorization.run`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/vectorization_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/vectorization_service.py#L1)
- **`introspection.vectorization.sync_existing_ids`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/knowledge_vectorizer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/knowledge_vectorizer.py#L1)

## Domain: `knowledge.vector`

- **`knowledge.vector.embedding`**
  - **Description:** No description provided.
  - **Source:** [src/shared/models/embedding_payload.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/models/embedding_payload.py#L1)

## Domain: `knowledge.vectorization`

- **`knowledge.vectorization.process`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/knowledge_vectorizer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/knowledge_vectorizer.py#L1)

## Domain: `knowledge_base.sync`

- **`knowledge_base.sync.execute`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/sync.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/sync.py#L1)

## Domain: `ledger.migrations`

- **`ledger.migrations.ensure`**
  - **Description:** No description provided.
  - **Source:** [src/services/repositories/db/common.py](https://github.com/DariuszNewecki/CORE/blob/main/src/services/repositories/db/common.py#L1)

## Domain: `llm.client.request`

- **`llm.client.request.async`**
  - **Description:** No description provided.
  - **Source:** [src/services/clients/llm_api_client.py](https://github.com/DariuszNewecki/CORE/blob/main/src/services/clients/llm_api_client.py#L1)

## Domain: `logging.provider`

- **`logging.provider.get_logger`**
  - **Description:** No description provided.
  - **Source:** [src/features/governance/policy_loader.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/governance/policy_loader.py#L1)

## Domain: `manifest.aggregation`

- **`manifest.aggregation.merge`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/manifest_aggregator.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/manifest_aggregator.py#L1)

## Domain: `manifest.hygiene`

- **`manifest.hygiene.fix`**
  - **Description:** No description provided.
  - **Source:** [src/features/self_healing/fix_manifest_hygiene.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/self_healing/fix_manifest_hygiene.py#L1)

## Domain: `manifest.validation`

- **`manifest.validation.entry`**
  - **Description:** No description provided.
  - **Source:** [src/shared/schemas/manifest_validator.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/schemas/manifest_validator.py#L1)

## Domain: `meta.path`

- **`meta.path.discovery`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/constitutional_parser.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/constitutional_parser.py#L1)

## Domain: `migration.ledger`

- **`migration.ledger.record`**
  - **Description:** No description provided.
  - **Source:** [src/services/repositories/db/common.py](https://github.com/DariuszNewecki/CORE/blob/main/src/services/repositories/db/common.py#L1)

## Domain: `migration.plan`

- **`migration.plan.parse`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/utils_migration.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/utils_migration.py#L1)
- **`migration.plan.update_capability_tag`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/utils_migration.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/utils_migration.py#L1)

## Domain: `parsing.json`

- **`parsing.json.extract`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/parsing.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/parsing.py#L1)

## Domain: `planner.configuration`

- **`planner.configuration.manage`**
  - **Description:** No description provided.
  - **Source:** [src/shared/models/execution_models.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/models/execution_models.py#L1)

## Domain: `planning.plan`

- **`planning.plan.create`**
  - **Description:** No description provided.
  - **Source:** [src/core/agents/planner_agent.py](https://github.com/DariuszNewecki/CORE/blob/main/src/core/agents/planner_agent.py#L1)

## Domain: `project.lifecycle`

- **`project.lifecycle.bootstrap_issues`**
  - **Description:** No description provided.
  - **Source:** [src/features/project_lifecycle/bootstrap_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/project_lifecycle/bootstrap_service.py#L1)

## Domain: `project_lifecycle.bootstrap`

- **`project_lifecycle.bootstrap.register`**
  - **Description:** No description provided.
  - **Source:** [src/features/project_lifecycle/bootstrap_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/project_lifecycle/bootstrap_service.py#L1)

## Domain: `project_lifecycle.scaffolding`

- **`project_lifecycle.scaffolding.new`**
  - **Description:** No description provided.
  - **Source:** [src/features/project_lifecycle/scaffolding_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/project_lifecycle/scaffolding_service.py#L1)
- **`project_lifecycle.scaffolding.write_file`**
  - **Description:** No description provided.
  - **Source:** [src/features/project_lifecycle/scaffolding_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/project_lifecycle/scaffolding_service.py#L1)

## Domain: `project_lifecycle.symbols`

- **`project_lifecycle.symbols.get_undefined`**
  - **Description:** No description provided.
  - **Source:** [src/features/project_lifecycle/definition_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/project_lifecycle/definition_service.py#L1)

## Domain: `proposals.micro`

- **`proposals.micro.set_context`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/proposals_micro.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/proposals_micro.py#L1)

## Domain: `refactoring.imports`

- **`refactoring.imports.rewire`**
  - **Description:** No description provided.
  - **Source:** [src/features/maintenance/maintenance_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/maintenance/maintenance_service.py#L1)

## Domain: `repository.analysis`

- **`repository.analysis.initialize`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/byor.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/byor.py#L1)

## Domain: `review.export`

- **`review.export.bundle`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/reviewer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/reviewer.py#L1)

## Domain: `schema.json`

- **`schema.json.load`**
  - **Description:** No description provided.
  - **Source:** [src/shared/schemas/manifest_validator.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/schemas/manifest_validator.py#L1)

## Domain: `self_healing.id_tagging`

- **`self_healing.id_tagging.assign_missing`**
  - **Description:** No description provided.
  - **Source:** [src/features/self_healing/id_tagging_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/self_healing/id_tagging_service.py#L1)

## Domain: `self_healing.tags`

- **`self_healing.tags.purge`**
  - **Description:** No description provided.
  - **Source:** [src/features/self_healing/purge_legacy_tags_service.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/self_healing/purge_legacy_tags_service.py#L1)

## Domain: `self_healing.vector_cleanup`

- **`self_healing.vector_cleanup.sync`**
  - **Description:** No description provided.
  - **Source:** [src/features/self_healing/prune_orphaned_vectors.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/self_healing/prune_orphaned_vectors.py#L1)

## Domain: `system.knowledge`

- **`system.knowledge.register`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/embeddings_cli.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/embeddings_cli.py#L1)

## Domain: `system.logging`

- **`system.logging.record_failure`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/knowledge_helpers.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/knowledge_helpers.py#L1)

## Domain: `text.normalization`

- **`text.normalization.process`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/embedding_utils.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/embedding_utils.py#L1)

## Domain: `utils.hashing`

- **`utils.hashing.sha256_hex`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/embedding_utils.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/embedding_utils.py#L1)

## Domain: `vector.storage`

- **`vector.storage.export`**
  - **Description:** No description provided.
  - **Source:** [src/features/introspection/export_vectors.py](https://github.com/DariuszNewecki/CORE/blob/main/src/features/introspection/export_vectors.py#L1)

## Domain: `vectorize.cli`

- **`vectorize.cli.run`**
  - **Description:** No description provided.
  - **Source:** [src/cli/logic/embeddings_cli.py](https://github.com/DariuszNewecki/CORE/blob/main/src/cli/logic/embeddings_cli.py#L1)

## Domain: `yaml.constitutional`

- **`yaml.constitutional.operations`**
  - **Description:** No description provided.
  - **Source:** [src/shared/utils/yaml_processor.py](https://github.com/DariuszNewecki/CORE/blob/main/src/shared/utils/yaml_processor.py#L1)
