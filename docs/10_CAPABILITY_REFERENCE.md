# 10. Capability Reference

This document is the canonical, auto-generated reference for all capabilities recognized by the CORE constitution.
It is generated from the `core.knowledge_graph` database view and should not be edited manually.

## Domain: `action.handler`

- **`action.handler.execute`**
  - **Description:** No description provided.
  - **Source:** [body.actions.base](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.base#L1)
- **`action.handler.registry`**
  - **Description:** No description provided.
  - **Source:** [body.actions.registry](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.registry#L1)

## Domain: `agent.application`

- **`agent.application.scaffold`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.agent](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.agent#L1)

## Domain: `agent.roles`

- **`agent.roles.validate`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.capability_discovery_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.capability_discovery_service#L1)

## Domain: `ai.ollama`

- **`ai.ollama.generate`**
  - **Description:** No description provided.
  - **Source:** [services.llm.providers.ollama](https://github.com/DariuszNewecki/CORE/blob/main/services.llm.providers.ollama#L1)

## Domain: `ai.provider`

- **`ai.provider.generate`**
  - **Description:** No description provided.
  - **Source:** [services.llm.providers.base](https://github.com/DariuszNewecki/CORE/blob/main/services.llm.providers.base#L1)

## Domain: `ai.provider.openai`

- **`ai.provider.openai.invoke`**
  - **Description:** No description provided.
  - **Source:** [services.llm.providers.openai](https://github.com/DariuszNewecki/CORE/blob/main/services.llm.providers.openai#L1)

## Domain: `analysis.reuse`

- **`analysis.reuse.serialize`**
  - **Description:** No description provided.
  - **Source:** [services.context.reuse](https://github.com/DariuszNewecki/CORE/blob/main/services.context.reuse#L1)

## Domain: `app.exception`

- **`app.exception.register_handlers`**
  - **Description:** No description provided.
  - **Source:** [shared.errors](https://github.com/DariuszNewecki/CORE/blob/main/shared.errors#L1)

## Domain: `app.fastapi`

- **`app.fastapi.create`**
  - **Description:** No description provided.
  - **Source:** [api.main](https://github.com/DariuszNewecki/CORE/blob/main/api.main#L1)

## Domain: `application.scaffold`

- **`application.scaffold.create`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.agent](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.agent#L1)

## Domain: `ast.analysis`

- **`ast.analysis.find_parent_scope`**
  - **Description:** No description provided.
  - **Source:** [services.context.providers.ast](https://github.com/DariuszNewecki/CORE/blob/main/services.context.providers.ast#L1)
- **`ast.analysis.provide`**
  - **Description:** No description provided.
  - **Source:** [services.context.providers.ast](https://github.com/DariuszNewecki/CORE/blob/main/services.context.providers.ast#L1)

## Domain: `ast.docstring`

- **`ast.docstring.extract`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)

## Domain: `ast.metadata`

- **`ast.metadata.parse`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)

## Domain: `ast.normalize`

- **`ast.normalize.structure`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)

## Domain: `ast.structure`

- **`ast.structure.hash`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)

## Domain: `audit.capability`

- **`audit.capability.coverage_verify`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.capability_coverage](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.capability_coverage#L1)
- **`audit.capability.validate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.update_caps_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.update_caps_check#L1)
- **`audit.capability.verify_owner`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.capability_owner_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.capability_owner_check#L1)

## Domain: `audit.check`

- **`audit.check.base`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.base_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.base_check#L1)
- **`audit.check.private_id`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.private_id_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.private_id_check#L1)

## Domain: `audit.cli`

- **`audit.cli.registry_validate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.respect_cli_registry_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.respect_cli_registry_check#L1)

## Domain: `audit.code`

- **`audit.code.scan_duplicate_ids`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.id_uniqueness_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.id_uniqueness_check#L1)

## Domain: `audit.context`

- **`audit.context.initialize`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.audit_context](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.audit_context#L1)

## Domain: `audit.domain`

- **`audit.domain.validate_registration`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.domains_in_db_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.domains_in_db_check#L1)

## Domain: `audit.files`

- **`audit.files.structural_validate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.file_checks](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.file_checks#L1)

## Domain: `audit.finding`

- **`audit.finding.serialize`**
  - **Description:** No description provided.
  - **Source:** [shared.models.audit_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.models.audit_models#L1)

## Domain: `audit.findings`

- **`audit.findings.postprocess`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.audit_postprocessor](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.audit_postprocessor#L1)

## Domain: `audit.id_coverage`

- **`audit.id_coverage.check`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.id_coverage_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.id_coverage_check#L1)

## Domain: `audit.legacy_access`

- **`audit.legacy_access.detect`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.limited_legacy_access_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.limited_legacy_access_check#L1)

## Domain: `audit.legacy_tags`

- **`audit.legacy_tags.scan`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.legacy_tag_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.legacy_tag_check#L1)

## Domain: `audit.reasoning`

- **`audit.reasoning.trace_validate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.trace_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.trace_check#L1)

## Domain: `audit.report`

- **`audit.report.check_violations`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.constitutional_monitor](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.constitutional_monitor#L1)
- **`audit.report.summary`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.report](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.report#L1)

## Domain: `audit.run`

- **`audit.run.log`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.log_audit](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.log_audit#L1)

## Domain: `audit.runs`

- **`audit.runs.list`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.list_audits](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.list_audits#L1)

## Domain: `audit.severity`

- **`audit.severity.evaluate`**
  - **Description:** No description provided.
  - **Source:** [shared.models.audit_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.models.audit_models#L1)

## Domain: `autonomy.micro_proposal`

- **`autonomy.micro_proposal.execute`**
  - **Description:** No description provided.
  - **Source:** [features.autonomy.micro_proposal_executor](https://github.com/DariuszNewecki/CORE/blob/main/features.autonomy.micro_proposal_executor#L1)

## Domain: `autonomy.self_healing`

- **`autonomy.self_healing.fix_docstrings`**
  - **Description:** No description provided.
  - **Source:** [body.actions.healing_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.healing_actions#L1)

## Domain: `cache.context`

- **`cache.context.manage`**
  - **Description:** No description provided.
  - **Source:** [services.context.cache](https://github.com/DariuszNewecki/CORE/blob/main/services.context.cache#L1)

## Domain: `capability.alias`

- **`capability.alias.resolve`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.alias_resolver](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.alias_resolver#L1)

## Domain: `capability.audit`

- **`capability.audit.domains`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.audit_capability_domains](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.audit_capability_domains#L1)

## Domain: `capability.deprecate`

- **`capability.deprecate.legacy`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.capability](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.capability#L1)

## Domain: `capability.domain`

- **`capability.domain.cluster`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.semantic_clusterer](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.semantic_clusterer#L1)

## Domain: `capability.drift`

- **`capability.drift.detect`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.drift_detector](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.drift_detector#L1)

## Domain: `capability.list`

- **`capability.list.all`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.snapshot](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.snapshot#L1)

## Domain: `capability.manage`

- **`capability.manage.model`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `capability.management`

- **`capability.management.suggest`**
  - **Description:** No description provided.
  - **Source:** [will.agents.tagger_agent](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.tagger_agent#L1)

## Domain: `capability.migration`

- **`capability.migration.rename`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.utils_migration](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.utils_migration#L1)

## Domain: `capability.prune`

- **`capability.prune.private_symbols`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.prune_private_capabilities](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.prune_private_capabilities#L1)

## Domain: `capability.registry`

- **`capability.registry.load`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.capability_discovery_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.capability_discovery_service#L1)
- **`capability.registry.resolve`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.capability_discovery_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.capability_discovery_service#L1)

## Domain: `capability.tag`

- **`capability.tag.all`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.capability_tagging_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.capability_tagging_service#L1)
- **`capability.tag.sync`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.capability_tagging_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.capability_tagging_service#L1)

## Domain: `capability.tags`

- **`capability.tags.fix`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.metadata](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.metadata#L1)

## Domain: `capability.vectorize`

- **`capability.vectorize.all`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.run](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.run#L1)

## Domain: `cli.async`

- **`cli.async.execute`**
  - **Description:** No description provided.
  - **Source:** [shared.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.cli_utils#L1)

## Domain: `cli.command`

- **`cli.command.define`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)
- **`cli.command.import`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.mind](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.mind#L1)
- **`cli.command.locate`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.hub](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.hub#L1)
- **`cli.command.search`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.hub](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.hub#L1)

## Domain: `cli.commands`

- **`cli.commands.register_all`**
  - **Description:** No description provided.
  - **Source:** [body.cli.admin_cli](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.admin_cli#L1)
- **`cli.commands.sync`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.db_tools](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.db_tools#L1)

## Domain: `cli.commands.list`

- **`cli.commands.list.all`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.list_commands](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.list_commands#L1)

## Domain: `cli.diff`

- **`cli.diff.execute`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.mind](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.mind#L1)

## Domain: `cli.display`

- **`cli.display.error`**
  - **Description:** No description provided.
  - **Source:** [shared.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.cli_utils#L1)
- **`cli.display.info`**
  - **Description:** No description provided.
  - **Source:** [shared.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.cli_utils#L1)
- **`cli.display.success`**
  - **Description:** No description provided.
  - **Source:** [shared.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.cli_utils#L1)
- **`cli.display.warning`**
  - **Description:** No description provided.
  - **Source:** [shared.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.cli_utils#L1)

## Domain: `cli.drift`

- **`cli.drift.evaluate_failure`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.cli_utils#L1)

## Domain: `cli.error`

- **`cli.error.handle`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.__init__](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.__init__#L1)

## Domain: `cli.intent`

- **`cli.intent.translate`**
  - **Description:** No description provided.
  - **Source:** [will.cli_logic.chat](https://github.com/DariuszNewecki/CORE/blob/main/will.cli_logic.chat#L1)

## Domain: `cli.reconcile`

- **`cli.reconcile.execute`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.reconcile](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.reconcile#L1)

## Domain: `cli.registry`

- **`cli.registry.define`**
  - **Description:** No description provided.
  - **Source:** [shared.legacy_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.legacy_models#L1)
- **`cli.registry.list`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.hub](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.hub#L1)
- **`cli.registry.validate`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.diagnostics](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.diagnostics#L1)

## Domain: `cli.tree`

- **`cli.tree.display`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.diagnostics](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.diagnostics#L1)

## Domain: `cli.verify`

- **`cli.verify.run`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.mind](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.mind#L1)

## Domain: `client.orchestration`

- **`client.orchestration.provision`**
  - **Description:** No description provided.
  - **Source:** [services.llm.client_orchestrator](https://github.com/DariuszNewecki/CORE/blob/main/services.llm.client_orchestrator#L1)

## Domain: `clustering.find`

- **`clustering.find.clusters`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.diagnostics](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.diagnostics#L1)

## Domain: `code.analysis`

- **`code.analysis.check_syntax`**
  - **Description:** No description provided.
  - **Source:** [services.validation.syntax_checker](https://github.com/DariuszNewecki/CORE/blob/main/services.validation.syntax_checker#L1)
- **`code.analysis.collect_function_calls`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)
- **`code.analysis.find_duplicate_functions`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.knowledge_consolidation_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.knowledge_consolidation_service#L1)
- **`code.analysis.find_duplicates`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge#L1)
- **`code.analysis.scan_imports`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.import_scanner](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.import_scanner#L1)

## Domain: `code.ast`

- **`code.ast.extract_base_classes`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)
- **`code.ast.extract_parameters`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)
- **`code.ast.find_definition_line`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)

## Domain: `code.audit`

- **`code.audit.duplication_check`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.duplication_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.duplication_check#L1)

## Domain: `code.correction`

- **`code.correction.attempt`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.llm_correction](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.llm_correction#L1)

## Domain: `code.docstring`

- **`code.docstring.fix`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.docstring_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.docstring_service#L1)

## Domain: `code.docstrings`

- **`code.docstrings.fix`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.docstrings](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.docstrings#L1)

## Domain: `code.extract`

- **`code.extract.python`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.parsing](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.parsing#L1)

## Domain: `code.extraction`

- **`code.extraction.normalize`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.code_extractor](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.code_extractor#L1)

## Domain: `code.format`

- **`code.format.execute`**
  - **Description:** No description provided.
  - **Source:** [body.actions.healing_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.healing_actions#L1)
- **`code.format.files`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.code_style_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.code_style_service#L1)
- **`code.format.imports`**
  - **Description:** No description provided.
  - **Source:** [body.actions.healing_actions_extended](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.healing_actions_extended#L1)
- **`code.format.line_length`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.linelength_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.linelength_service#L1)
- **`code.format.python`**
  - **Description:** No description provided.
  - **Source:** [services.validation.black_formatter](https://github.com/DariuszNewecki/CORE/blob/main/services.validation.black_formatter#L1)
- **`code.format.style`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.code_style](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.code_style#L1)

## Domain: `code.format.line_length`

- **`code.format.line_length.fix`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.__init__](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.__init__#L1)

## Domain: `code.formatting`

- **`code.formatting.enforce_line_length`**
  - **Description:** No description provided.
  - **Source:** [body.actions.healing_actions_extended](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.healing_actions_extended#L1)

## Domain: `code.function`

- **`code.function.edit`**
  - **Description:** No description provided.
  - **Source:** [body.actions.code_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.code_actions#L1)

## Domain: `code.generation`

- **`code.generation.validate_and_correct`**
  - **Description:** No description provided.
  - **Source:** [will.agents.coder_agent](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.coder_agent#L1)

## Domain: `code.id`

- **`code.id.assign_missing`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.id_tagging_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.id_tagging_service#L1)

## Domain: `code.imports`

- **`code.imports.fix_unused`**
  - **Description:** No description provided.
  - **Source:** [body.actions.healing_actions_extended](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.healing_actions_extended#L1)
- **`code.imports.validate_grouping`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.import_group_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.import_group_check#L1)

## Domain: `code.integration`

- **`code.integration.execute`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.system](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.system#L1)

## Domain: `code.quality`

- **`code.quality.fix_and_lint`**
  - **Description:** No description provided.
  - **Source:** [services.validation.ruff_linter](https://github.com/DariuszNewecki/CORE/blob/main/services.validation.ruff_linter#L1)
- **`code.quality.fix_headers`**
  - **Description:** No description provided.
  - **Source:** [body.actions.healing_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.healing_actions#L1)
- **`code.quality.lint`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.audit](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.audit#L1)
- **`code.quality.remove_dead_code`**
  - **Description:** No description provided.
  - **Source:** [body.actions.healing_actions_extended](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.healing_actions_extended#L1)

## Domain: `code.quality.validate`

- **`code.quality.validate.todo_comments`**
  - **Description:** No description provided.
  - **Source:** [services.validation.quality](https://github.com/DariuszNewecki/CORE/blob/main/services.validation.quality#L1)

## Domain: `code.refactor`

- **`code.refactor.clarity`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.clarity](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.clarity#L1)
- **`code.refactor.complexity`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.clarity](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.clarity#L1)
- **`code.refactor.complexity_outliers`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.complexity_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.complexity_service#L1)
- **`code.refactor.execute`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.develop](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.develop#L1)

## Domain: `code.reuse`

- **`code.reuse.analyze`**
  - **Description:** No description provided.
  - **Source:** [services.context.reuse](https://github.com/DariuszNewecki/CORE/blob/main/services.context.reuse#L1)

## Domain: `code.review`

- **`code.review.submit`**
  - **Description:** No description provided.
  - **Source:** [will.cli_logic.reviewer](https://github.com/DariuszNewecki/CORE/blob/main/will.cli_logic.reviewer#L1)

## Domain: `code.security`

- **`code.security.validate_runtime`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.runtime_validation_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.runtime_validation_check#L1)

## Domain: `code.security.audit`

- **`code.security.audit.unverified_execution`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.no_unverified_code_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.no_unverified_code_check#L1)

## Domain: `code.semantics`

- **`code.semantics.cluster`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.graph_analysis_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.graph_analysis_service#L1)

## Domain: `code.style`

- **`code.style.enforce`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.style_checks](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.style_checks#L1)

## Domain: `code.validation`

- **`code.validation.correct`**
  - **Description:** No description provided.
  - **Source:** [will.orchestration.self_correction_engine](https://github.com/DariuszNewecki/CORE/blob/main/will.orchestration.self_correction_engine#L1)
- **`code.validation.execute`**
  - **Description:** No description provided.
  - **Source:** [will.orchestration.validation_pipeline](https://github.com/DariuszNewecki/CORE/blob/main/will.orchestration.validation_pipeline#L1)
- **`code.validation.python`**
  - **Description:** No description provided.
  - **Source:** [services.validation.python_validator](https://github.com/DariuszNewecki/CORE/blob/main/services.validation.python_validator#L1)

## Domain: `code_analysis.audit`

- **`code_analysis.audit.orphaned_logic`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.orphaned_logic](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.orphaned_logic#L1)

## Domain: `code_quality.health`

- **`code_quality.health.analyze`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.health_checks](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.health_checks#L1)

## Domain: `codebase.symbol`

- **`codebase.symbol.scan`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.sync_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.sync_service#L1)

## Domain: `cognitive.client`

- **`cognitive.client.provide`**
  - **Description:** No description provided.
  - **Source:** [will.orchestration.cognitive_service](https://github.com/DariuszNewecki/CORE/blob/main/will.orchestration.cognitive_service#L1)

## Domain: `cognitive.orchestration`

- **`cognitive.orchestration.initialize`**
  - **Description:** No description provided.
  - **Source:** [will.agents.cognitive_orchestrator](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.cognitive_orchestrator#L1)

## Domain: `compliance.audit`

- **`compliance.audit.no_write_intent`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.no_write_intent_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.no_write_intent_check#L1)

## Domain: `config.bootstrap`

- **`config.bootstrap.env`**
  - **Description:** No description provided.
  - **Source:** [services.config_service](https://github.com/DariuszNewecki/CORE/blob/main/services.config_service#L1)
- **`config.bootstrap.load`**
  - **Description:** No description provided.
  - **Source:** [shared.config](https://github.com/DariuszNewecki/CORE/blob/main/shared.config#L1)

## Domain: `config.file`

- **`config.file.load`**
  - **Description:** No description provided.
  - **Source:** [shared.config_loader](https://github.com/DariuszNewecki/CORE/blob/main/shared.config_loader#L1)

## Domain: `config.manage`

- **`config.manage.all`**
  - **Description:** No description provided.
  - **Source:** [services.config_service](https://github.com/DariuszNewecki/CORE/blob/main/services.config_service#L1)

## Domain: `config.path`

- **`config.path.resolve`**
  - **Description:** No description provided.
  - **Source:** [shared.config](https://github.com/DariuszNewecki/CORE/blob/main/shared.config#L1)

## Domain: `config.service`

- **`config.service.create`**
  - **Description:** No description provided.
  - **Source:** [services.config_service](https://github.com/DariuszNewecki/CORE/blob/main/services.config_service#L1)

## Domain: `constitution.audit`

- **`constitution.audit.run`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.audit](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.audit#L1)

## Domain: `constitution.monitor`

- **`constitution.monitor.headers`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.constitutional_monitor](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.constitutional_monitor#L1)

## Domain: `constitution.review`

- **`constitution.review.peer`**
  - **Description:** No description provided.
  - **Source:** [will.cli_logic.reviewer](https://github.com/DariuszNewecki/CORE/blob/main/will.cli_logic.reviewer#L1)

## Domain: `content.id`

- **`content.id.resolve_duplicates`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.metadata](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.metadata#L1)

## Domain: `context.module`

- **`context.module.build`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.context_builder](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.context_builder#L1)

## Domain: `context.package`

- **`context.package.build`**
  - **Description:** No description provided.
  - **Source:** [services.context.service](https://github.com/DariuszNewecki/CORE/blob/main/services.context.service#L1)

## Domain: `context.packet`

- **`context.packet.build`**
  - **Description:** No description provided.
  - **Source:** [services.context.cli](https://github.com/DariuszNewecki/CORE/blob/main/services.context.cli#L1)
- **`context.packet.manage`**
  - **Description:** No description provided.
  - **Source:** [services.context.database](https://github.com/DariuszNewecki/CORE/blob/main/services.context.database#L1)
- **`context.packet.show`**
  - **Description:** No description provided.
  - **Source:** [services.context.cli](https://github.com/DariuszNewecki/CORE/blob/main/services.context.cli#L1)
- **`context.packet.validate`**
  - **Description:** No description provided.
  - **Source:** [services.context.cli](https://github.com/DariuszNewecki/CORE/blob/main/services.context.cli#L1)

## Domain: `context.plan_executor`

- **`context.plan_executor.create`**
  - **Description:** No description provided.
  - **Source:** [body.actions.context](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.context#L1)

## Domain: `context.redaction.event`

- **`context.redaction.event.create`**
  - **Description:** No description provided.
  - **Source:** [services.context.redactor](https://github.com/DariuszNewecki/CORE/blob/main/services.context.redactor#L1)

## Domain: `context.reuse`

- **`context.reuse.summarize`**
  - **Description:** No description provided.
  - **Source:** [services.context.reuse](https://github.com/DariuszNewecki/CORE/blob/main/services.context.reuse#L1)

## Domain: `context.serialization`

- **`context.serialization.manage`**
  - **Description:** No description provided.
  - **Source:** [services.context.serializers](https://github.com/DariuszNewecki/CORE/blob/main/services.context.serializers#L1)

## Domain: `context.service`

- **`context.service.initialize`**
  - **Description:** No description provided.
  - **Source:** [shared.context](https://github.com/DariuszNewecki/CORE/blob/main/shared.context#L1)

## Domain: `context.task`

- **`context.task.build`**
  - **Description:** No description provided.
  - **Source:** [services.context.builder](https://github.com/DariuszNewecki/CORE/blob/main/services.context.builder#L1)

## Domain: `context.validation`

- **`context.validation.execute`**
  - **Description:** No description provided.
  - **Source:** [services.context.validator](https://github.com/DariuszNewecki/CORE/blob/main/services.context.validator#L1)

## Domain: `core.action`

- **`core.action.create`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `core.context`

- **`core.context.set`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.inspect](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.inspect#L1)

## Domain: `core.exception`

- **`core.exception.raise`**
  - **Description:** No description provided.
  - **Source:** [shared.exceptions](https://github.com/DariuszNewecki/CORE/blob/main/shared.exceptions#L1)

## Domain: `core.validation`

- **`core.validation.validate_code`**
  - **Description:** No description provided.
  - **Source:** [body.actions.validation_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.validation_actions#L1)

## Domain: `coverage.accumulate`

- **`coverage.accumulate.batch`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.coverage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.coverage#L1)

## Domain: `coverage.analyze`

- **`coverage.analyze.codebase`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.coverage_analyzer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.coverage_analyzer#L1)

## Domain: `coverage.auto_remediation`

- **`coverage.auto_remediation.execute`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.auto_remediation_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.auto_remediation_check#L1)

## Domain: `coverage.governance`

- **`coverage.governance.check`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.coverage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.coverage#L1)

## Domain: `coverage.history`

- **`coverage.history.display`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.coverage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.coverage#L1)

## Domain: `coverage.remediate`

- **`coverage.remediate.enhanced`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.coverage_remediation_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.coverage_remediation_service#L1)
- **`coverage.remediate.tests`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.coverage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.coverage#L1)

## Domain: `coverage.report`

- **`coverage.report.generate`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.coverage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.coverage#L1)

## Domain: `coverage.targets`

- **`coverage.targets.display`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.coverage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.coverage#L1)

## Domain: `coverage.violation`

- **`coverage.violation.detect`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.coverage_watcher](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.coverage_watcher#L1)

## Domain: `coverage.watch`

- **`coverage.watch.remediate`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.coverage_watcher](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.coverage_watcher#L1)

## Domain: `crate.create`

- **`crate.create.from_generation`**
  - **Description:** No description provided.
  - **Source:** [body.services.crate_creation_service](https://github.com/DariuszNewecki/CORE/blob/main/body.services.crate_creation_service#L1)

## Domain: `crate.intent`

- **`crate.intent.create`**
  - **Description:** No description provided.
  - **Source:** [body.services.crate_creation_service](https://github.com/DariuszNewecki/CORE/blob/main/body.services.crate_creation_service#L1)

## Domain: `crate.model`

- **`crate.model.define`**
  - **Description:** No description provided.
  - **Source:** [body.services.crate_processing_service](https://github.com/DariuszNewecki/CORE/blob/main/body.services.crate_processing_service#L1)

## Domain: `crate.processing`

- **`crate.processing.execute`**
  - **Description:** No description provided.
  - **Source:** [body.services.crate_processing_service](https://github.com/DariuszNewecki/CORE/blob/main/body.services.crate_processing_service#L1)
- **`crate.processing.orchestrate`**
  - **Description:** No description provided.
  - **Source:** [body.services.crate_processing_service](https://github.com/DariuszNewecki/CORE/blob/main/body.services.crate_processing_service#L1)

## Domain: `crate.proposal`

- **`crate.proposal.process`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.system](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.system#L1)

## Domain: `crypto.hash`

- **`crypto.hash.sha256`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.embedding_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.embedding_utils#L1)

## Domain: `crypto.key`

- **`crypto.key.load_private`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.cli_utils#L1)

## Domain: `cryptography.keypair`

- **`cryptography.keypair.generate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.key_management_service](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.key_management_service#L1)

## Domain: `data.comparison`

- **`data.comparison.diff`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.diff](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.diff#L1)

## Domain: `data.digest`

- **`data.digest.compute`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.utils](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.utils#L1)

## Domain: `data.redact`

- **`data.redact.packet`**
  - **Description:** No description provided.
  - **Source:** [services.context.redactor](https://github.com/DariuszNewecki/CORE/blob/main/services.context.redactor#L1)

## Domain: `data.structure`

- **`data.structure.canonicalize`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.utils](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.utils#L1)

## Domain: `database.cognitive_role`

- **`database.cognitive_role.define`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `database.connection`

- **`database.connection.test`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.engine](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.engine#L1)

## Domain: `database.export`

- **`database.export.yaml`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.db](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.db#L1)

## Domain: `database.import`

- **`database.import.yaml`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.import_](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.import_#L1)

## Domain: `database.links`

- **`database.links.fetch_all`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.snapshot](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.snapshot#L1)

## Domain: `database.manage`

- **`database.manage.symbol_capability_links`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `database.migration`

- **`database.migration.apply`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.migration_service](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.migration_service#L1)
- **`database.migration.ensure_ledger`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.common](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.common#L1)
- **`database.migration.run`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.manage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.manage#L1)
- **`database.migration.track`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `database.model`

- **`database.model.define`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `database.northstar`

- **`database.northstar.manage`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `database.schema`

- **`database.schema.modify`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `database.session`

- **`database.session.manage`**
  - **Description:** No description provided.
  - **Source:** [services.database.session_manager](https://github.com/DariuszNewecki/CORE/blob/main/services.database.session_manager#L1)
- **`database.session.provide`**
  - **Description:** No description provided.
  - **Source:** [services.database.session_manager](https://github.com/DariuszNewecki/CORE/blob/main/services.database.session_manager#L1)

## Domain: `database.snapshot`

- **`database.snapshot.create`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.snapshot](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.snapshot#L1)

## Domain: `database.sql`

- **`database.sql.apply_file`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.common](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.common#L1)

## Domain: `database.status`

- **`database.status.check`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.status_service](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.status_service#L1)
- **`database.status.display`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.inspect](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.inspect#L1)
- **`database.status.report`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.status_service](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.status_service#L1)

## Domain: `database.vector_index`

- **`database.vector_index.validate_registration`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.vector_index_in_db_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.vector_index_in_db_check#L1)

## Domain: `database.write`

- **`database.write.detect`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.governed_db_write_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.governed_db_write_check#L1)

## Domain: `demo.greeting`

- **`demo.greeting.print`**
  - **Description:** No description provided.
  - **Source:** [features.demo.hello_world](https://github.com/DariuszNewecki/CORE/blob/main/features.demo.hello_world#L1)

## Domain: `development.bug`

- **`development.bug.fix`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.develop](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.develop#L1)

## Domain: `development.cycle`

- **`development.cycle.execute`**
  - **Description:** No description provided.
  - **Source:** [features.autonomy.autonomous_developer](https://github.com/DariuszNewecki/CORE/blob/main/features.autonomy.autonomous_developer#L1)
- **`development.cycle.start`**
  - **Description:** No description provided.
  - **Source:** [api.v1.development_routes](https://github.com/DariuszNewecki/CORE/blob/main/api.v1.development_routes#L1)

## Domain: `development.goal`

- **`development.goal.define`**
  - **Description:** No description provided.
  - **Source:** [api.v1.development_routes](https://github.com/DariuszNewecki/CORE/blob/main/api.v1.development_routes#L1)

## Domain: `development.orchestrate`

- **`development.orchestrate.autonomous`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.run](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.run#L1)

## Domain: `diagnostics.check`

- **`diagnostics.check.legacy_tags`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.diagnostics](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.diagnostics#L1)

## Domain: `diagnostics.meta_paths`

- **`diagnostics.meta_paths.debug`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.diagnostics](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.diagnostics#L1)

## Domain: `diagnostics.report`

- **`diagnostics.report.unassigned_symbols`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.diagnostics](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.diagnostics#L1)

## Domain: `docs.capability`

- **`docs.capability.generate`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.project_docs](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.project_docs#L1)

## Domain: `documentation.audit`

- **`documentation.audit.clarity`**
  - **Description:** No description provided.
  - **Source:** [will.cli_logic.reviewer](https://github.com/DariuszNewecki/CORE/blob/main/will.cli_logic.reviewer#L1)

## Domain: `documentation.capability`

- **`documentation.capability.generate`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.generate_capability_docs](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.generate_capability_docs#L1)

## Domain: `domain.aliases`

- **`domain.aliases.generate`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.generate_correction_map](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.generate_correction_map#L1)

## Domain: `domain.persistence`

- **`domain.persistence.create`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `domain.sync`

- **`domain.sync.canonical`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.sync_domains](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.sync_domains#L1)

## Domain: `dotenv.sync`

- **`dotenv.sync.apply`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.manage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.manage#L1)

## Domain: `drift.analysis`

- **`drift.analysis.run`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.drift_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.drift_service#L1)

## Domain: `drift.report`

- **`drift.report.serialize`**
  - **Description:** No description provided.
  - **Source:** [shared.models.drift_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.models.drift_models#L1)

## Domain: `embedding.factory`

- **`embedding.factory.build`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.embedding_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.embedding_utils#L1)

## Domain: `embedding.generate`

- **`embedding.generate.single`**
  - **Description:** No description provided.
  - **Source:** [services.adapters.embedding_provider](https://github.com/DariuszNewecki/CORE/blob/main/services.adapters.embedding_provider#L1)

## Domain: `embedding.payload`

- **`embedding.payload.define`**
  - **Description:** No description provided.
  - **Source:** [shared.models.embedding_payload](https://github.com/DariuszNewecki/CORE/blob/main/shared.models.embedding_payload#L1)

## Domain: `embedding.text`

- **`embedding.text.generate`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.embedding_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.embedding_utils#L1)
- **`embedding.text.process`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.embedding_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.embedding_utils#L1)

## Domain: `embedding.vector`

- **`embedding.vector.generate`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.embedding_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.embedding_utils#L1)

## Domain: `environment.variables`

- **`environment.variables.validate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.environment_checks](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.environment_checks#L1)

## Domain: `ervice.snapshot`

- **`ervice.snapshot.create`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.mind](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.mind#L1)

## Domain: `execution.parallel`

- **`execution.parallel.process`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.parallel_processor](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.parallel_processor#L1)

## Domain: `execution.task`

- **`execution.task.validate`**
  - **Description:** No description provided.
  - **Source:** [shared.models.execution_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.models.execution_models#L1)

## Domain: `execution.task.params`

- **`execution.task.params.define`**
  - **Description:** No description provided.
  - **Source:** [shared.models.execution_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.models.execution_models#L1)

## Domain: `export.verify`

- **`export.verify.integrity`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.verify](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.verify#L1)

## Domain: `feature.develop`

- **`feature.develop.autonomous`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.develop](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.develop#L1)

## Domain: `file.classify`

- **`file.classify.by_extension`**
  - **Description:** No description provided.
  - **Source:** [services.storage.file_classifier](https://github.com/DariuszNewecki/CORE/blob/main/services.storage.file_classifier#L1)

## Domain: `file.content`

- **`file.content.parse_write_blocks`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.parsing](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.parsing#L1)
- **`file.content.read`**
  - **Description:** No description provided.
  - **Source:** [body.actions.file_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.file_actions#L1)

## Domain: `file.create`

- **`file.create.code`**
  - **Description:** No description provided.
  - **Source:** [body.actions.code_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.code_actions#L1)

## Domain: `file.edit`

- **`file.edit.content`**
  - **Description:** No description provided.
  - **Source:** [body.actions.code_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.code_actions#L1)

## Domain: `file.header`

- **`file.header.fix`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.header_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.header_service#L1)
- **`file.header.parse`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.header_tools](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.header_tools#L1)

## Domain: `file.management`

- **`file.management.delete`**
  - **Description:** No description provided.
  - **Source:** [body.actions.file_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.file_actions#L1)

## Domain: `file.operations`

- **`file.operations.copy`**
  - **Description:** No description provided.
  - **Source:** [shared.path_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.path_utils#L1)
- **`file.operations.stage`**
  - **Description:** No description provided.
  - **Source:** [services.storage.file_handler](https://github.com/DariuszNewecki/CORE/blob/main/services.storage.file_handler#L1)

## Domain: `file.yaml`

- **`file.yaml.save`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.cli_utils#L1)
- **`file.yaml.write`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.utils](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.utils#L1)

## Domain: `filesystem.directory`

- **`filesystem.directory.copy_tree`**
  - **Description:** No description provided.
  - **Source:** [shared.path_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.path_utils#L1)
- **`filesystem.directory.list`**
  - **Description:** No description provided.
  - **Source:** [body.actions.file_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.file_actions#L1)

## Domain: `findings.entry_point`

- **`findings.entry_point.downgrade`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.audit_postprocessor](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.audit_postprocessor#L1)

## Domain: `fix.run`

- **`fix.run.all`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.all_commands](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.all_commands#L1)

## Domain: `git.commit`

- **`git.commit.get_sha`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.common](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.common#L1)

## Domain: `git.repository`

- **`git.repository.manage`**
  - **Description:** No description provided.
  - **Source:** [services.git_service](https://github.com/DariuszNewecki/CORE/blob/main/services.git_service#L1)

## Domain: `github.issues`

- **`github.issues.bootstrap`**
  - **Description:** No description provided.
  - **Source:** [features.project_lifecycle.bootstrap_service](https://github.com/DariuszNewecki/CORE/blob/main/features.project_lifecycle.bootstrap_service#L1)

## Domain: `goal.alignment`

- **`goal.alignment.check`**
  - **Description:** No description provided.
  - **Source:** [will.orchestration.intent_alignment](https://github.com/DariuszNewecki/CORE/blob/main/will.orchestration.intent_alignment#L1)

## Domain: `governance.audit`

- **`governance.audit.dependency_injection`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.dependency_injection_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.dependency_injection_check#L1)
- **`governance.audit.file_header`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.file_header_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.file_header_check#L1)
- **`governance.audit.run`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.auditor](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.auditor#L1)

## Domain: `governance.duplicate_ids`

- **`governance.duplicate_ids.resolve`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.duplicate_id_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.duplicate_id_service#L1)

## Domain: `governance.entry_point`

- **`governance.entry_point.allow`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.audit_postprocessor](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.audit_postprocessor#L1)

## Domain: `governance.menu`

- **`governance.menu.show`**
  - **Description:** No description provided.
  - **Source:** [body.cli.interactive](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.interactive#L1)

## Domain: `governance.proposal`

- **`governance.proposal.create`**
  - **Description:** No description provided.
  - **Source:** [body.actions.governance_actions](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.governance_actions#L1)

## Domain: `governance.violation`

- **`governance.violation.record`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.constitutional_monitor](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.constitutional_monitor#L1)
- **`governance.violation.report`**
  - **Description:** No description provided.
  - **Source:** [will.orchestration.intent_guard](https://github.com/DariuszNewecki/CORE/blob/main/will.orchestration.intent_guard#L1)

## Domain: `guard.drift`

- **`guard.drift.analyze`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.guard_cli](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.guard_cli#L1)

## Domain: `handler.metadata`

- **`handler.metadata.extract`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.handler_discovery](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.handler_discovery#L1)

## Domain: `handlers.capability`

- **`handlers.capability.register`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.handler_discovery](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.handler_discovery#L1)

## Domain: `handlers.discover`

- **`handlers.discover.all`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.handler_discovery](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.handler_discovery#L1)

## Domain: `handlers.discovery`

- **`handlers.discovery.scan`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.handler_discovery](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.handler_discovery#L1)

## Domain: `handlers.validation`

- **`handlers.validation.run`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.handler_discovery](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.handler_discovery#L1)

## Domain: `headers.constitutional`

- **`headers.constitutional.fix`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.code_style](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.code_style#L1)

## Domain: `health.check`

- **`health.check.hub`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.hub](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.hub#L1)

## Domain: `imports.rewire`

- **`imports.rewire.all`**
  - **Description:** No description provided.
  - **Source:** [features.maintenance.maintenance_service](https://github.com/DariuszNewecki/CORE/blob/main/features.maintenance.maintenance_service#L1)
- **`imports.rewire.cli`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.tools](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.tools#L1)

## Domain: `incident.log`

- **`incident.log.bootstrap`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.fix_ir](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.fix_ir#L1)

## Domain: `incident_response.audit`

- **`incident_response.audit.log`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.ir_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.ir_check#L1)

## Domain: `inspect.duplicates`

- **`inspect.duplicates.semantic`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.duplicates](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.duplicates#L1)

## Domain: `inspection.duplicates`

- **`inspection.duplicates.analyze`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.inspect](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.inspect#L1)

## Domain: `integration.orchestrate`

- **`integration.orchestrate.autonomous`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.submit](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.submit#L1)

## Domain: `integration.workflow`

- **`integration.workflow.execute`**
  - **Description:** No description provided.
  - **Source:** [features.project_lifecycle.integration_service](https://github.com/DariuszNewecki/CORE/blob/main/features.project_lifecycle.integration_service#L1)

## Domain: `intent.constitution`

- **`intent.constitution.discover_paths`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.constitutional_parser](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.constitutional_parser#L1)

## Domain: `intent.schema`

- **`intent.schema.validate`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.validate](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.validate#L1)

## Domain: `introspection.capability`

- **`introspection.capability.collect`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.capability_discovery_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.capability_discovery_service#L1)
- **`introspection.capability.metadata`**
  - **Description:** No description provided.
  - **Source:** [shared.models.capability_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.models.capability_models#L1)
- **`introspection.capability.scan`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.discovery.from_source_scan](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.discovery.from_source_scan#L1)

## Domain: `introspection.drift`

- **`introspection.drift.analyze`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.symbol_drift](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.symbol_drift#L1)

## Domain: `introspection.symbol_index`

- **`introspection.symbol_index.build`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.symbol_index_builder](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.symbol_index_builder#L1)

## Domain: `ir.triage`

- **`ir.triage.bootstrap`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.fix_ir](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.fix_ir#L1)

## Domain: `knowledge.capabilities`

- **`knowledge.capabilities.search`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.search](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.search#L1)

## Domain: `knowledge.capability`

- **`knowledge.capability.list`**
  - **Description:** No description provided.
  - **Source:** [api.v1.knowledge_routes](https://github.com/DariuszNewecki/CORE/blob/main/api.v1.knowledge_routes#L1)

## Domain: `knowledge.diff`

- **`knowledge.diff.compare`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.knowledge_differ](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.knowledge_differ#L1)

## Domain: `knowledge.graph`

- **`knowledge.graph.build`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.knowledge_graph_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.knowledge_graph_service#L1)
- **`knowledge.graph.read`**
  - **Description:** No description provided.
  - **Source:** [services.knowledge.knowledge_service](https://github.com/DariuszNewecki/CORE/blob/main/services.knowledge.knowledge_service#L1)

## Domain: `knowledge.reconnaissance`

- **`knowledge.reconnaissance.generate_report`**
  - **Description:** No description provided.
  - **Source:** [will.agents.reconnaissance_agent](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.reconnaissance_agent#L1)

## Domain: `knowledge.search`

- **`knowledge.search.capabilities`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.search](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.search#L1)

## Domain: `knowledge.ssot`

- **`knowledge.ssot.verify`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.knowledge_source_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.knowledge_source_check#L1)

## Domain: `knowledge.symbols`

- **`knowledge.symbols.list_unassigned`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.audit_unassigned_capabilities](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.audit_unassigned_capabilities#L1)

## Domain: `knowledge.vector`

- **`knowledge.vector.sync_existing`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.knowledge_vectorizer](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.knowledge_vectorizer#L1)

## Domain: `knowledge.vectorize`

- **`knowledge.vectorize.capabilities`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.embeddings_cli](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.embeddings_cli#L1)
- **`knowledge.vectorize.capability`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.knowledge_vectorizer](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.knowledge_vectorizer#L1)

## Domain: `knowledge_base.sync`

- **`knowledge_base.sync.all`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.sync](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.sync#L1)

## Domain: `knowledge_graph`

- **`knowledge_graph.build_and_sync`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.constitutional_monitor](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.constitutional_monitor#L1)

## Domain: `legacy.cli.command`

- **`legacy.cli.command.define`**
  - **Description:** No description provided.
  - **Source:** [shared.legacy_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.legacy_models#L1)

## Domain: `legacy.manifest`

- **`legacy.manifest.define`**
  - **Description:** No description provided.
  - **Source:** [shared.legacy_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.legacy_models#L1)

## Domain: `legacy.model`

- **`legacy.model.cognitive_roles`**
  - **Description:** No description provided.
  - **Source:** [shared.legacy_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.legacy_models#L1)
- **`legacy.model.define`**
  - **Description:** No description provided.
  - **Source:** [shared.legacy_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.legacy_models#L1)

## Domain: `legacy.tags`

- **`legacy.tags.purge`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.purge_legacy_tags_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.purge_legacy_tags_service#L1)

## Domain: `llm.client`

- **`llm.client.create_for_role`**
  - **Description:** No description provided.
  - **Source:** [services.llm.client](https://github.com/DariuszNewecki/CORE/blob/main/services.llm.client#L1)
- **`llm.client.execute`**
  - **Description:** No description provided.
  - **Source:** [services.llm.client](https://github.com/DariuszNewecki/CORE/blob/main/services.llm.client#L1)
- **`llm.client.make_request`**
  - **Description:** No description provided.
  - **Source:** [body.services.llm_client](https://github.com/DariuszNewecki/CORE/blob/main/body.services.llm_client#L1)
- **`llm.client.manage`**
  - **Description:** No description provided.
  - **Source:** [services.llm.client_registry](https://github.com/DariuszNewecki/CORE/blob/main/services.llm.client_registry#L1)
- **`llm.client.request`**
  - **Description:** No description provided.
  - **Source:** [services.clients.llm_api_client](https://github.com/DariuszNewecki/CORE/blob/main/services.clients.llm_api_client#L1)

## Domain: `llm.resource`

- **`llm.resource.manage`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)
- **`llm.resource.select`**
  - **Description:** No description provided.
  - **Source:** [will.agents.deduction_agent](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.deduction_agent#L1)

## Domain: `llm.resource.config`

- **`llm.resource.config.get`**
  - **Description:** No description provided.
  - **Source:** [services.config_service](https://github.com/DariuszNewecki/CORE/blob/main/services.config_service#L1)

## Domain: `logging.action`

- **`logging.action.write`**
  - **Description:** No description provided.
  - **Source:** [shared.action_logger](https://github.com/DariuszNewecki/CORE/blob/main/shared.action_logger#L1)

## Domain: `logging.configure`

- **`logging.configure.root`**
  - **Description:** No description provided.
  - **Source:** [shared.logger](https://github.com/DariuszNewecki/CORE/blob/main/shared.logger#L1)

## Domain: `logging.failure`

- **`logging.failure.append`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.knowledge_helpers](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.knowledge_helpers#L1)

## Domain: `logging.level`

- **`logging.level.reconfigure`**
  - **Description:** No description provided.
  - **Source:** [shared.logger](https://github.com/DariuszNewecki/CORE/blob/main/shared.logger#L1)

## Domain: `logging.logger`

- **`logging.logger.get`**
  - **Description:** No description provided.
  - **Source:** [shared.logger](https://github.com/DariuszNewecki/CORE/blob/main/shared.logger#L1)

## Domain: `manifest.aggregate`

- **`manifest.aggregate.all`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.manifest_aggregator](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.manifest_aggregator#L1)

## Domain: `manifest.capabilities`

- **`manifest.capabilities.load`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.discovery.from_manifest](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.discovery.from_manifest#L1)

## Domain: `manifest.entry`

- **`manifest.entry.validate`**
  - **Description:** No description provided.
  - **Source:** [shared.schemas.manifest_validator](https://github.com/DariuszNewecki/CORE/blob/main/shared.schemas.manifest_validator#L1)

## Domain: `manifest.hygiene`

- **`manifest.hygiene.check`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.diagnostics](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.diagnostics#L1)
- **`manifest.hygiene.fix`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.fix_manifest_hygiene](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.fix_manifest_hygiene#L1)

## Domain: `manifest.lint`

- **`manifest.lint.check_placeholders`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.manifest_lint](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.manifest_lint#L1)

## Domain: `manifest.sync`

- **`manifest.sync.public`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.sync_manifest](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.sync_manifest#L1)

## Domain: `manifest.validation`

- **`manifest.validation.check_domain_placement`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.domain_placement](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.domain_placement#L1)

## Domain: `metadata.ids`

- **`metadata.ids.assign`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.metadata](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.metadata#L1)

## Domain: `migration.plan`

- **`migration.plan.parse`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.utils_migration](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.utils_migration#L1)

## Domain: `migration.record`

- **`migration.record.applied`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.common](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.common#L1)

## Domain: `migration.status`

- **`migration.status.get_applied`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.common](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.common#L1)

## Domain: `mind.governance.micro_proposal`

- **`mind.governance.micro_proposal.create`**
  - **Description:** No description provided.
  - **Source:** [features.autonomy.micro_proposal_executor](https://github.com/DariuszNewecki/CORE/blob/main/features.autonomy.micro_proposal_executor#L1)

## Domain: `mind.intent`

- **`mind.intent.translate`**
  - **Description:** No description provided.
  - **Source:** [will.agents.intent_translator](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.intent_translator#L1)

## Domain: `mind.ir.triage`

- **`mind.ir.triage.verify`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.ir_triage_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.ir_triage_check#L1)

## Domain: `mind.policy`

- **`mind.policy.resolve`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.policy_resolver](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.policy_resolver#L1)

## Domain: `mind.service`

- **`mind.service.get`**
  - **Description:** No description provided.
  - **Source:** [services.mind_service](https://github.com/DariuszNewecki/CORE/blob/main/services.mind_service#L1)

## Domain: `models.legacy`

- **`models.legacy.define`**
  - **Description:** No description provided.
  - **Source:** [shared.legacy_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.legacy_models#L1)

## Domain: `northstar.mission`

- **`northstar.mission.read`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.snapshot](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.snapshot#L1)

## Domain: `packet.redact`

- **`packet.redact.apply`**
  - **Description:** No description provided.
  - **Source:** [services.context.redactor](https://github.com/DariuszNewecki/CORE/blob/main/services.context.redactor#L1)

## Domain: `pattern.definition`

- **`pattern.definition.create`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.symbol_index_builder](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.symbol_index_builder#L1)

## Domain: `plan.execution`

- **`plan.execution.error`**
  - **Description:** No description provided.
  - **Source:** [shared.models.execution_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.models.execution_models#L1)
- **`plan.execution.orchestrate`**
  - **Description:** No description provided.
  - **Source:** [will.agents.plan_executor](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.plan_executor#L1)
- **`plan.execution.validate_and_parse`**
  - **Description:** No description provided.
  - **Source:** [will.agents.base_planner](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.base_planner#L1)

## Domain: `planner.config`

- **`planner.config.define`**
  - **Description:** No description provided.
  - **Source:** [shared.models.execution_models](https://github.com/DariuszNewecki/CORE/blob/main/shared.models.execution_models#L1)

## Domain: `planning.autonomous`

- **`planning.autonomous.execute`**
  - **Description:** No description provided.
  - **Source:** [will.cli_logic.proposals_micro](https://github.com/DariuszNewecki/CORE/blob/main/will.cli_logic.proposals_micro#L1)

## Domain: `planning.execution`

- **`planning.execution.create`**
  - **Description:** No description provided.
  - **Source:** [will.agents.planner_agent](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.planner_agent#L1)

## Domain: `planning.micro`

- **`planning.micro.create`**
  - **Description:** No description provided.
  - **Source:** [will.agents.micro_planner](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.micro_planner#L1)

## Domain: `poetry.command`

- **`poetry.command.run`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.subprocess_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.subprocess_utils#L1)

## Domain: `policy.action_step`

- **`policy.action_step.define`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.policy_gate](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.policy_gate#L1)

## Domain: `policy.actions`

- **`policy.actions.load`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.policy_loader](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.policy_loader#L1)

## Domain: `policy.coverage`

- **`policy.coverage.analyze`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.policy_coverage_service](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.policy_coverage_service#L1)
- **`policy.coverage.audit`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.diagnostics](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.diagnostics#L1)
- **`policy.coverage.generate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.policy_coverage_service](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.policy_coverage_service#L1)

## Domain: `policy.data_governance`

- **`policy.data_governance.load`**
  - **Description:** No description provided.
  - **Source:** [services.repositories.db.common](https://github.com/DariuszNewecki/CORE/blob/main/services.repositories.db.common#L1)

## Domain: `policy.enforcement`

- **`policy.enforcement.check`**
  - **Description:** No description provided.
  - **Source:** [will.orchestration.intent_guard](https://github.com/DariuszNewecki/CORE/blob/main/will.orchestration.intent_guard#L1)
- **`policy.enforcement.enforce`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.policy_gate](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.policy_gate#L1)

## Domain: `policy.ids`

- **`policy.ids.fix`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.metadata](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.metadata#L1)

## Domain: `policy.imports`

- **`policy.imports.validate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.import_rules](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.import_rules#L1)

## Domain: `policy.load`

- **`policy.load.file`**
  - **Description:** No description provided.
  - **Source:** [services.mind_service](https://github.com/DariuszNewecki/CORE/blob/main/services.mind_service#L1)

## Domain: `policy.management`

- **`policy.management.add_ids`**
  - **Description:** No description provided.
  - **Source:** [body.actions.healing_actions_extended](https://github.com/DariuszNewecki/CORE/blob/main/body.actions.healing_actions_extended#L1)
- **`policy.management.sync_ids`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.policy_id_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.policy_id_service#L1)

## Domain: `policy.micro_proposal`

- **`policy.micro_proposal.load`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.policy_loader](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.policy_loader#L1)

## Domain: `policy.microproposal`

- **`policy.microproposal.create`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.policy_gate](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.policy_gate#L1)

## Domain: `policy.naming`

- **`policy.naming.validate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.naming_conventions](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.naming_conventions#L1)

## Domain: `policy.rule`

- **`policy.rule.create`**
  - **Description:** No description provided.
  - **Source:** [will.orchestration.intent_guard](https://github.com/DariuszNewecki/CORE/blob/main/will.orchestration.intent_guard#L1)

## Domain: `policy.validation`

- **`policy.validation.execute`**
  - **Description:** No description provided.
  - **Source:** [body.services.validation_policies](https://github.com/DariuszNewecki/CORE/blob/main/body.services.validation_policies#L1)

## Domain: `policy.violation`

- **`policy.violation.raise`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.policy_gate](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.policy_gate#L1)

## Domain: `project.lifecycle`

- **`project.lifecycle.show_menu`**
  - **Description:** No description provided.
  - **Source:** [body.cli.interactive](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.interactive#L1)

## Domain: `project.scaffold`

- **`project.scaffold.create`**
  - **Description:** No description provided.
  - **Source:** [features.project_lifecycle.scaffolding_service](https://github.com/DariuszNewecki/CORE/blob/main/features.project_lifecycle.scaffolding_service#L1)

## Domain: `prompt.planning`

- **`prompt.planning.build`**
  - **Description:** No description provided.
  - **Source:** [will.agents.base_planner](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.base_planner#L1)

## Domain: `prompt.process`

- **`prompt.process.enrich`**
  - **Description:** No description provided.
  - **Source:** [will.orchestration.prompt_pipeline](https://github.com/DariuszNewecki/CORE/blob/main/will.orchestration.prompt_pipeline#L1)

## Domain: `proposal.approve`

- **`proposal.approve.execute`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.manage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.manage#L1)

## Domain: `proposal.create`

- **`proposal.create.micro`**
  - **Description:** No description provided.
  - **Source:** [will.cli_logic.proposals_micro](https://github.com/DariuszNewecki/CORE/blob/main/will.cli_logic.proposals_micro#L1)

## Domain: `proposal.info`

- **`proposal.info.read`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.proposal_service](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.proposal_service#L1)

## Domain: `proposal.list`

- **`proposal.list.pending`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.proposal_service](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.proposal_service#L1)

## Domain: `proposal.manage`

- **`proposal.manage.create`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `proposal.micro`

- **`proposal.micro.validate`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.micro_proposal_validator](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.micro_proposal_validator#L1)

## Domain: `proposal.rollback`

- **`proposal.rollback.archive`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.cli_utils#L1)

## Domain: `proposal.sign`

- **`proposal.sign.create`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.proposal_service](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.proposal_service#L1)

## Domain: `proposal.signature`

- **`proposal.signature.verify`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `proposal.token`

- **`proposal.token.generate`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.crypto](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.crypto#L1)

## Domain: `proposal.workflow`

- **`proposal.workflow.manage`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.proposal_service](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.proposal_service#L1)

## Domain: `quality.coverage`

- **`quality.coverage.monitor_and_remediate`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.coverage_watcher](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.coverage_watcher#L1)

## Domain: `quality_assurance.coverage`

- **`quality_assurance.coverage.enforce`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.coverage_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.coverage_check#L1)

## Domain: `redaction.report`

- **`redaction.report.manage`**
  - **Description:** No description provided.
  - **Source:** [services.context.redactor](https://github.com/DariuszNewecki/CORE/blob/main/services.context.redactor#L1)

## Domain: `refactor.audit`

- **`refactor.audit.detect`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.refactor_audit_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.refactor_audit_check#L1)

## Domain: `remediation.batch`

- **`remediation.batch.process`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.batch_remediation_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.batch_remediation_service#L1)

## Domain: `remediation.complexity`

- **`remediation.complexity.filter`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.complexity_filter](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.complexity_filter#L1)

## Domain: `remediation.result`

- **`remediation.result.track`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.constitutional_monitor](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.constitutional_monitor#L1)

## Domain: `report.drift`

- **`report.drift.write`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.drift_detector](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.drift_detector#L1)

## Domain: `repository.constitution`

- **`repository.constitution.scaffold`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.byor](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.byor#L1)

## Domain: `repository.root`

- **`repository.root.find`**
  - **Description:** No description provided.
  - **Source:** [shared.path_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.path_utils#L1)

## Domain: `resource.selection`

- **`resource.selection.optimize`**
  - **Description:** No description provided.
  - **Source:** [will.agents.resource_selector](https://github.com/DariuszNewecki/CORE/blob/main/will.agents.resource_selector#L1)

## Domain: `review.context`

- **`review.context.define`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.validate](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.validate#L1)

## Domain: `risk.gate`

- **`risk.gate.validate`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.validate](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.validate#L1)

## Domain: `runtime.service`

- **`runtime.service.manage`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `runtime.setting`

- **`runtime.setting.manage`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `schema.load`

- **`schema.load.file`**
  - **Description:** No description provided.
  - **Source:** [shared.schemas.manifest_validator](https://github.com/DariuszNewecki/CORE/blob/main/shared.schemas.manifest_validator#L1)

## Domain: `secrets`

- **`secrets.delete`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.secrets](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.secrets#L1)

## Domain: `secrets.access`

- **`secrets.access.not_found`**
  - **Description:** No description provided.
  - **Source:** [shared.exceptions](https://github.com/DariuszNewecki/CORE/blob/main/shared.exceptions#L1)

## Domain: `secrets.list`

- **`secrets.list.keys`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.secrets](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.secrets#L1)

## Domain: `secrets.manage`

- **`secrets.manage.all`**
  - **Description:** No description provided.
  - **Source:** [services.secrets_service](https://github.com/DariuszNewecki/CORE/blob/main/services.secrets_service#L1)

## Domain: `secrets.management`

- **`secrets.management.error`**
  - **Description:** No description provided.
  - **Source:** [shared.exceptions](https://github.com/DariuszNewecki/CORE/blob/main/shared.exceptions#L1)
- **`secrets.management.set`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.secrets](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.secrets#L1)

## Domain: `secrets.retrieve`

- **`secrets.retrieve.value`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.secrets](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.secrets#L1)

## Domain: `secrets.service`

- **`secrets.service.create`**
  - **Description:** No description provided.
  - **Source:** [services.secrets_service](https://github.com/DariuszNewecki/CORE/blob/main/services.secrets_service#L1)

## Domain: `security.policy`

- **`security.policy.enforce`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.security_checks](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.security_checks#L1)

## Domain: `self_healing.repair`

- **`self_healing.repair.automatic_repair_service`**
  - **Description:** Micro-fixer for automatic code repair
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.e_o_f_syntax_fixer`**
  - **Description:** Apply specific fix strategy
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.e_o_f_syntax_fixer`**
  - **Description:** Micro-fixer for automatic code repair
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.empty_function_fixer`**
  - **Description:** Micro-fixer for automatic code repair
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.empty_function_fixer`**
  - **Description:** Apply specific fix strategy
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.mixed_quote_fixer`**
  - **Description:** Micro-fixer for automatic code repair
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.mixed_quote_fixer`**
  - **Description:** Apply specific fix strategy
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.quote_fixer`**
  - **Description:** Micro-fixer for automatic code repair
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.quote_fixer`**
  - **Description:** Apply specific fix strategy
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.trailing_whitespace_fixer`**
  - **Description:** Apply specific fix strategy
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.trailing_whitespace_fixer`**
  - **Description:** Micro-fixer for automatic code repair
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.truncated_docstring_fixer`**
  - **Description:** Apply specific fix strategy
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.truncated_docstring_fixer`**
  - **Description:** Micro-fixer for automatic code repair
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.unterminated_string_fixer`**
  - **Description:** Apply specific fix strategy
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)
- **`self_healing.repair.unterminated_string_fixer`**
  - **Description:** Micro-fixer for automatic code repair
  - **Source:** [features.self_healing.test_generation.automatic_repair](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.automatic_repair#L1)

## Domain: `self_healing.test_gen`

- **`self_healing.test_gen.execute`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.executor](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.executor#L1)
- **`self_healing.test_gen.extract_code`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.code_extractor](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.code_extractor#L1)
- **`self_healing.test_gen.fix_single`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.single_test_fixer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.single_test_fixer#L1)
- **`self_healing.test_gen.replace_fn`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.single_test_fixer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.single_test_fixer#L1)

## Domain: `service.registry`

- **`service.registry.get`**
  - **Description:** No description provided.
  - **Source:** [body.services.service_registry](https://github.com/DariuszNewecki/CORE/blob/main/body.services.service_registry#L1)

## Domain: `settings.dotenv`

- **`settings.dotenv.sync`**
  - **Description:** No description provided.
  - **Source:** [features.maintenance.dotenv_sync_service](https://github.com/DariuszNewecki/CORE/blob/main/features.maintenance.dotenv_sync_service#L1)

## Domain: `shared.universal`

- **`shared.universal.normalize_whitespace`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.common_knowledge](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.common_knowledge#L1)

## Domain: `source.code`

- **`source.code.extract`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.knowledge_helpers](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.knowledge_helpers#L1)

## Domain: `ssot.migration`

- **`ssot.migration.run`**
  - **Description:** No description provided.
  - **Source:** [features.maintenance.migration_service](https://github.com/DariuszNewecki/CORE/blob/main/features.maintenance.migration_service#L1)

## Domain: `symbol.ast`

- **`symbol.ast.discover`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.sync_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.sync_service#L1)

## Domain: `symbol.database`

- **`symbol.database.fetch_all`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.snapshot](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.snapshot#L1)

## Domain: `symbol.definition`

- **`symbol.definition.create`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.manage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.manage#L1)
- **`symbol.definition.fetch_undefined`**
  - **Description:** No description provided.
  - **Source:** [features.project_lifecycle.definition_service](https://github.com/DariuszNewecki/CORE/blob/main/features.project_lifecycle.definition_service#L1)
- **`symbol.definition.generate`**
  - **Description:** No description provided.
  - **Source:** [features.project_lifecycle.definition_service](https://github.com/DariuszNewecki/CORE/blob/main/features.project_lifecycle.definition_service#L1)

## Domain: `symbol.enrich`

- **`symbol.enrich.autonomous`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.enrichment_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.enrichment_service#L1)
- **`symbol.enrich.descriptions`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.enrich](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.enrich#L1)

## Domain: `symbol.graph`

- **`symbol.graph.traverse`**
  - **Description:** No description provided.
  - **Source:** [services.context.providers.db](https://github.com/DariuszNewecki/CORE/blob/main/services.context.providers.db#L1)

## Domain: `symbol.id`

- **`symbol.id.extract`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)
- **`symbol.id.result`**
  - **Description:** No description provided.
  - **Source:** [shared.ast_utility](https://github.com/DariuszNewecki/CORE/blob/main/shared.ast_utility#L1)

## Domain: `symbol.index`

- **`symbol.index.build`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.symbol_index_builder](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.symbol_index_builder#L1)

## Domain: `symbol.meta`

- **`symbol.meta.define`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.symbol_index_builder](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.symbol_index_builder#L1)

## Domain: `symbols.sync`

- **`symbols.sync.database`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.sync_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.sync_service#L1)

## Domain: `symbols.update`

- **`symbols.update.key`**
  - **Description:** No description provided.
  - **Source:** [features.project_lifecycle.definition_service](https://github.com/DariuszNewecki/CORE/blob/main/features.project_lifecycle.definition_service#L1)

## Domain: `system.health`

- **`system.health.check`**
  - **Description:** No description provided.
  - **Source:** [main](https://github.com/DariuszNewecki/CORE/blob/main/main#L1)
- **`system.health.show_menu`**
  - **Description:** No description provided.
  - **Source:** [body.cli.interactive](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.interactive#L1)

## Domain: `system.info`

- **`system.info.display`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.develop](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.develop#L1)

## Domain: `system.introspection`

- **`system.introspection.run`**
  - **Description:** No description provided.
  - **Source:** [body.services.capabilities](https://github.com/DariuszNewecki/CORE/blob/main/body.services.capabilities#L1)

## Domain: `system.lifespan`

- **`system.lifespan.manage`**
  - **Description:** No description provided.
  - **Source:** [api.main](https://github.com/DariuszNewecki/CORE/blob/main/api.main#L1)

## Domain: `system.state`

- **`system.state.diff`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.knowledge_sync.diff](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.knowledge_sync.diff#L1)

## Domain: `tags.purge`

- **`tags.purge.legacy`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.metadata](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.metadata#L1)

## Domain: `task.management`

- **`task.management.create`**
  - **Description:** No description provided.
  - **Source:** [services.database.models](https://github.com/DariuszNewecki/CORE/blob/main/services.database.models#L1)

## Domain: `test.analysis`

- **`test.analysis.classify`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_target_analyzer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_target_analyzer#L1)
- **`test.analysis.inspect_targets`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.inspect](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.inspect#L1)

## Domain: `test.code`

- **`test.code.extract_and_replace`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.single_test_fixer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.single_test_fixer#L1)

## Domain: `test.context`

- **`test.context.analyze`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_context_analyzer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_context_analyzer#L1)
- **`test.context.format`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_context_analyzer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_context_analyzer#L1)

## Domain: `test.coverage`

- **`test.coverage.accumulate`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.coverage](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.coverage#L1)
- **`test.coverage.validate_refactor`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.checks.refactor_test_check](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.checks.refactor_test_check#L1)

## Domain: `test.execution`

- **`test.execution.run`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.executor](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.executor#L1)

## Domain: `test.failure`

- **`test.failure.format_context`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_failure_analyzer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_failure_analyzer#L1)

## Domain: `test.file.find`

- **`test.file.find.for_capability`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.cli_utils#L1)

## Domain: `test.fix`

- **`test.fix.single`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.single_test_fixer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.single_test_fixer#L1)

## Domain: `test.generation`

- **`test.generation.context_aware`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.context_aware_test_generator](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.context_aware_test_generator#L1)
- **`test.generation.generate`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.develop](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.develop#L1)
- **`test.generation.orchestrate`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.generator](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.generator#L1)
- **`test.generation.single_file`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.single_file_remediation](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.single_file_remediation#L1)

## Domain: `test.generation.prompt`

- **`test.generation.prompt.build`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.prompt_builder](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.prompt_builder#L1)

## Domain: `test.goal`

- **`test.goal.create`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.full_project_remediation](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.full_project_remediation#L1)

## Domain: `test.parser`

- **`test.parser.failures`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_generation.single_test_fixer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_generation.single_test_fixer#L1)

## Domain: `test.results`

- **`test.results.calculate_success_rate`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_failure_analyzer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_failure_analyzer#L1)

## Domain: `test.system`

- **`test.system.run`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.audit](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.audit#L1)

## Domain: `testing.accumulate`

- **`testing.accumulate.file`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.accumulative_test_service](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.accumulative_test_service#L1)

## Domain: `testing.analysis`

- **`testing.analysis.parse_failures`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_failure_analyzer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_failure_analyzer#L1)

## Domain: `testing.canary`

- **`testing.canary.run`**
  - **Description:** No description provided.
  - **Source:** [mind.governance.runtime_validator](https://github.com/DariuszNewecki/CORE/blob/main/mind.governance.runtime_validator#L1)

## Domain: `testing.coverage`

- **`testing.coverage.remediate`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.full_project_remediation](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.full_project_remediation#L1)

## Domain: `testing.generation`

- **`testing.generation.fix_iterative`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.iterative_test_fixer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.iterative_test_fixer#L1)
- **`testing.generation.single`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.simple_test_generator](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.simple_test_generator#L1)

## Domain: `testing.run`

- **`testing.run.pytest`**
  - **Description:** No description provided.
  - **Source:** [services.validation.test_runner](https://github.com/DariuszNewecki/CORE/blob/main/services.validation.test_runner#L1)

## Domain: `testing.target`

- **`testing.target.identify`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.test_target_analyzer](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.test_target_analyzer#L1)

## Domain: `text.extract`

- **`text.extract.json`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.parsing](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.parsing#L1)

## Domain: `text.format`

- **`text.format.collapse_blank_lines`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.common_knowledge](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.common_knowledge#L1)
- **`text.format.ensure_trailing_newline`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.common_knowledge](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.common_knowledge#L1)
- **`text.format.truncate`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.common_knowledge](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.common_knowledge#L1)

## Domain: `text.normalize`

- **`text.normalize.whitespace`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.common_knowledge](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.common_knowledge#L1)

## Domain: `time.utc`

- **`time.utc.now_iso`**
  - **Description:** No description provided.
  - **Source:** [shared.time](https://github.com/DariuszNewecki/CORE/blob/main/shared.time#L1)

## Domain: `tool.self_healing`

- **`tool.self_healing.fix`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.__init__](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.__init__#L1)

## Domain: `ui.confirmation`

- **`ui.confirmation.prompt`**
  - **Description:** No description provided.
  - **Source:** [shared.cli_utils](https://github.com/DariuszNewecki/CORE/blob/main/shared.cli_utils#L1)

## Domain: `ui.interactive`

- **`ui.interactive.launch`**
  - **Description:** No description provided.
  - **Source:** [body.cli.admin_cli](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.admin_cli#L1)

## Domain: `ui.menu`

- **`ui.menu.launch`**
  - **Description:** No description provided.
  - **Source:** [body.cli.interactive](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.interactive#L1)

## Domain: `ui.menu.show`

- **`ui.menu.show.development`**
  - **Description:** No description provided.
  - **Source:** [body.cli.interactive](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.interactive#L1)

## Domain: `validation.payload.embedding`

- **`validation.payload.embedding.fail`**
  - **Description:** No description provided.
  - **Source:** [services.clients.qdrant_client](https://github.com/DariuszNewecki/CORE/blob/main/services.clients.qdrant_client#L1)

## Domain: `validation.yaml`

- **`validation.yaml.validate`**
  - **Description:** No description provided.
  - **Source:** [services.validation.yaml_validator](https://github.com/DariuszNewecki/CORE/blob/main/services.validation.yaml_validator#L1)

## Domain: `vector.database`

- **`vector.database.sync`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.sync_vectors](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.sync_vectors#L1)

## Domain: `vector.embedding`

- **`vector.embedding.manage`**
  - **Description:** No description provided.
  - **Source:** [services.clients.qdrant_client](https://github.com/DariuszNewecki/CORE/blob/main/services.clients.qdrant_client#L1)

## Domain: `vector.export`

- **`vector.export.all`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.export_vectors](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.export_vectors#L1)

## Domain: `vector.retrieve`

- **`vector.retrieve.error`**
  - **Description:** No description provided.
  - **Source:** [services.clients.qdrant_client](https://github.com/DariuszNewecki/CORE/blob/main/services.clients.qdrant_client#L1)

## Domain: `vector.search`

- **`vector.search.similar`**
  - **Description:** No description provided.
  - **Source:** [services.context.providers.vectors](https://github.com/DariuszNewecki/CORE/blob/main/services.context.providers.vectors#L1)

## Domain: `vector.sync`

- **`vector.sync.bidirectional`**
  - **Description:** No description provided.
  - **Source:** [body.cli.commands.fix.db_tools](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.commands.fix.db_tools#L1)
- **`vector.sync.orphans`**
  - **Description:** No description provided.
  - **Source:** [features.self_healing.sync_vectors](https://github.com/DariuszNewecki/CORE/blob/main/features.self_healing.sync_vectors#L1)

## Domain: `vector_store.verify`

- **`vector_store.verify.synchronization`**
  - **Description:** No description provided.
  - **Source:** [body.cli.logic.vector_drift](https://github.com/DariuszNewecki/CORE/blob/main/body.cli.logic.vector_drift#L1)

## Domain: `vectorization.payload`

- **`vectorization.payload.serialize`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.knowledge_vectorizer](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.knowledge_vectorizer#L1)

## Domain: `vectorization.sync`

- **`vectorization.sync.all`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.vectorization_service](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.vectorization_service#L1)

## Domain: `vectorstore.chunks`

- **`vectorstore.chunks.retrieve`**
  - **Description:** No description provided.
  - **Source:** [features.introspection.knowledge_vectorizer](https://github.com/DariuszNewecki/CORE/blob/main/features.introspection.knowledge_vectorizer#L1)

## Domain: `yaml.constitutional`

- **`yaml.constitutional.process`**
  - **Description:** No description provided.
  - **Source:** [shared.utils.yaml_processor](https://github.com/DariuszNewecki/CORE/blob/main/shared.utils.yaml_processor#L1)
