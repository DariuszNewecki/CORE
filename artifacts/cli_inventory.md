# CLI Inventory

## Summary

| Metric | Count |
|---|---:|
| Total commands | 86 |
| Native (resource) | 38 |
| Shim | 9 |
| Needs conversion | 39 |
| Resources total | 9 |

## Discovery Coverage

| Stat | Count |
|---|---:|
| Apps found | 41 |
| Edges found | 18 |
| Commands found | 86 |
| Unresolved edges | 0 |
| Unresolved handler refs | 0 |

## Counts By Resource

| Resource | Actions |
|---|---:|
| code | 6 |
| dev | 3 |
| constitution | 4 |
| context | 3 |
| proposals | 6 |
| vectors | 5 |
| project | 3 |
| symbols | 3 |
| database | 5 |

## Resource: code

| Command | Handler | Classification | Evidence |
|---|---|---|---|
| `core-admin code lint` | `body.cli.resources.code.lint:lint_command` | native | /mnt/dev/CORE/src/body/cli/resources/code/lint.py:17 async def lint_command(ctx: typer.Context) -> None: |
| `core-admin code logging` | `body.cli.resources.code.logging:fix_logging_command` | native | /mnt/dev/CORE/src/body/cli/resources/code/logging.py:19 async def fix_logging_command( |
| `core-admin code docstrings` | `body.cli.resources.code.docstrings:fix_docstrings_command` | native | /mnt/dev/CORE/src/body/cli/resources/code/docstrings.py:19 async def fix_docstrings_command( |
| `core-admin code format` | `body.cli.resources.code.format:format_command` | native | /mnt/dev/CORE/src/body/cli/resources/code/format.py:17 async def format_command( |
| `core-admin code audit` | `body.cli.resources.code.audit:audit_command` | native | /mnt/dev/CORE/src/body/cli/resources/code/audit.py:19 async def audit_command( |
| `core-admin code test` | `body.cli.resources.code.test:test_command` | native | /mnt/dev/CORE/src/body/cli/resources/code/test.py:17 async def test_command(ctx: typer.Context) -> None: |

## Resource: dev

| Command | Handler | Classification | Evidence |
|---|---|---|---|
| `core-admin dev chat` | `body.cli.resources.dev.chat:chat_command` | native | /mnt/dev/CORE/src/body/cli/resources/dev/chat.py:60 async def chat_command( |
| `core-admin dev sync` | `body.cli.resources.dev.sync:sync_workflow` | native | /mnt/dev/CORE/src/body/cli/resources/dev/sync.py:17 async def sync_workflow( |
| `core-admin dev test` | `body.cli.resources.dev.test:test_interactive` | native | /mnt/dev/CORE/src/body/cli/resources/dev/test.py:17 async def test_interactive( |

## Resource: constitution

| Command | Handler | Classification | Evidence |
|---|---|---|---|
| `core-admin constitution validate` | `body.cli.resources.constitution.validate:validate_constitution` | native | /mnt/dev/CORE/src/body/cli/resources/constitution/validate.py:17 def validate_constitution(ctx: typer.Context) -> None: |
| `core-admin constitution query` | `body.cli.resources.constitution.query:query_constitution` | native | /mnt/dev/CORE/src/body/cli/resources/constitution/query.py:17 async def query_constitution( |
| `core-admin constitution status` | `body.cli.resources.constitution.status:status_coverage` | native | /mnt/dev/CORE/src/body/cli/resources/constitution/status.py:17 def status_coverage(ctx: typer.Context) -> None: |
| `core-admin constitution audit` | `body.cli.resources.constitution.audit:audit_policies` | native | /mnt/dev/CORE/src/body/cli/resources/constitution/audit.py:17 async def audit_policies( |

## Resource: context

| Command | Handler | Classification | Evidence |
|---|---|---|---|
| `core-admin context build` | `body.cli.resources.context.build:build` | native | /mnt/dev/CORE/src/body/cli/resources/context/__init__.py:26 app.command()(build); /mnt/dev/CORE/src/body/cli/resources/context/__init__.py:26 app.command()(build) |
| `core-admin context search` | `body.cli.resources.context.search:search` | native | /mnt/dev/CORE/src/body/cli/resources/context/__init__.py:27 app.command()(search); /mnt/dev/CORE/src/body/cli/resources/context/__init__.py:27 app.command()(search) |
| `core-admin context cache` | `body.cli.resources.context.cache:cache` | native | /mnt/dev/CORE/src/body/cli/resources/context/__init__.py:28 app.command()(cache); /mnt/dev/CORE/src/body/cli/resources/context/__init__.py:28 app.command()(cache) |

## Resource: proposals

| Command | Handler | Classification | Evidence |
|---|---|---|---|
| `core-admin proposals list` | `body.cli.resources.proposals:list_proposals` | native | /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:21 app.command("list")(list_mod.list_proposals); /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:21 app.command("list")(list_mod.list_proposals) |
| `core-admin proposals create` | `body.cli.resources.proposals:create_proposal` | native | /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:22 app.command("create")(create.create_proposal); /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:22 app.command("create")(create.create_proposal) |
| `core-admin proposals show` | `body.cli.resources.proposals:show_proposal` | native | /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:23 app.command("show")(manage.show_proposal); /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:23 app.command("show")(manage.show_proposal) |
| `core-admin proposals approve` | `body.cli.resources.proposals:approve_proposal` | native | /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:24 app.command("approve")(manage.approve_proposal); /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:24 app.command("approve")(manage.approve_proposal) |
| `core-admin proposals reject` | `body.cli.resources.proposals:reject_proposal` | native | /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:25 app.command("reject")(manage.reject_proposal); /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:25 app.command("reject")(manage.reject_proposal) |
| `core-admin proposals execute` | `body.cli.resources.proposals:execute_proposal` | native | /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:26 app.command("execute")(manage.execute_proposal); /mnt/dev/CORE/src/body/cli/resources/proposals/__init__.py:26 app.command("execute")(manage.execute_proposal) |

## Resource: vectors

| Command | Handler | Classification | Evidence |
|---|---|---|---|
| `core-admin vectors query` | `body.cli.resources.vectors.query:query_vectors` | native | /mnt/dev/CORE/src/body/cli/resources/vectors/query.py:31 async def query_vectors( |
| `core-admin vectors sync` | `body.cli.resources.vectors.sync:sync_vectors` | native | /mnt/dev/CORE/src/body/cli/resources/vectors/sync.py:17 async def sync_vectors( |
| `core-admin vectors status` | `body.cli.resources.vectors.status:status_vectors` | native | /mnt/dev/CORE/src/body/cli/resources/vectors/status.py:17 async def status_vectors(ctx: typer.Context) -> None: |
| `core-admin vectors cleanup` | `body.cli.resources.vectors.cleanup:cleanup_vectors` | native | /mnt/dev/CORE/src/body/cli/resources/vectors/cleanup.py:28 async def cleanup_vectors( |
| `core-admin vectors rebuild` | `body.cli.resources.vectors.rebuild:rebuild_vectors` | native | /mnt/dev/CORE/src/body/cli/resources/vectors/rebuild.py:28 async def rebuild_vectors( |

## Resource: project

| Command | Handler | Classification | Evidence |
|---|---|---|---|
| `core-admin project new` | `body.cli.resources.project.new:new_project_command` | native | /mnt/dev/CORE/src/body/cli/resources/project/new.py:18 async def new_project_command( |
| `core-admin project docs` | `body.cli.resources.project.docs:generate_project_docs` | native | /mnt/dev/CORE/src/body/cli/resources/project/docs.py:17 def generate_project_docs( |
| `core-admin project onboard` | `body.cli.resources.project.onboard:onboard_project` | native | /mnt/dev/CORE/src/body/cli/resources/project/onboard.py:19 def onboard_project( |

## Resource: symbols

| Command | Handler | Classification | Evidence |
|---|---|---|---|
| `core-admin symbols fix-ids` | `body.cli.resources.symbols.fix_ids:fix_ids_command` | native | /mnt/dev/CORE/src/body/cli/resources/symbols/fix_ids.py:17 async def fix_ids_command( |
| `core-admin symbols sync` | `body.cli.resources.symbols.sync:sync_symbols` | native | /mnt/dev/CORE/src/body/cli/resources/symbols/sync.py:17 async def sync_symbols( |
| `core-admin symbols audit` | `body.cli.resources.symbols.audit:audit_symbols` | native | /mnt/dev/CORE/src/body/cli/resources/symbols/audit.py:18 async def audit_symbols(ctx: typer.Context) -> None: |

## Resource: database

| Command | Handler | Classification | Evidence |
|---|---|---|---|
| `core-admin database export` | `body.cli.resources.database.export:export_database` | native | /mnt/dev/CORE/src/body/cli/resources/database/export.py:27 async def export_database( |
| `core-admin database sync` | `body.cli.resources.database.sync:sync_database` | native | /mnt/dev/CORE/src/body/cli/resources/database/sync.py:28 async def sync_database( |
| `core-admin database status` | `body.cli.resources.database.status:database_status` | native | /mnt/dev/CORE/src/body/cli/resources/database/status.py:28 async def database_status( |
| `core-admin database cleanup` | `body.cli.resources.database.cleanup:cleanup_database` | native | /mnt/dev/CORE/src/body/cli/resources/database/cleanup.py:28 async def cleanup_database( |
| `core-admin database migrate` | `body.cli.resources.database.migrate:migrate_database` | native | /mnt/dev/CORE/src/body/cli/resources/database/migrate.py:27 async def migrate_database( |

## Non-Resource Commands

| Command | Module | Handler | Classification | Evidence |
|---|---|---|---|---|
| `core-admin submit changes` | `/mnt/dev/CORE/src/body/cli/commands/submit.py` | `body.cli.commands.submit:integrate_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/submit.py:31 async def integrate_command( |
| `core-admin legacy-status drift` | `/mnt/dev/CORE/src/body/cli/commands/status.py` | `body.cli.commands.status:drift_cmd` | shim | /mnt/dev/CORE/src/body/cli/commands/status.py:47 async def drift_cmd( |
| `core-admin fix discover-actions` | `/mnt/dev/CORE/src/body/cli/commands/fix/handler_discovery.py` | `body.cli.commands.fix.handler_discovery:discover_actions_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/handler_discovery.py:24 def discover_actions_command(ctx: typer.Context) -> None: |
| `core-admin fix clarity` | `/mnt/dev/CORE/src/body/cli/commands/fix/clarity.py` | `body.cli.commands.fix.clarity:fix_clarity_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/clarity.py:32 async def fix_clarity_command( |
| `core-admin fix complexity` | `/mnt/dev/CORE/src/body/cli/commands/fix/clarity.py` | `body.cli.commands.fix.clarity:complexity_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/clarity.py:73 async def complexity_command( |
| `core-admin fix settings-di` | `/mnt/dev/CORE/src/body/cli/commands/fix/settings_access.py` | `body.cli.commands.fix.settings_access:fix_settings_di_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/settings_access.py:23 async def fix_settings_di_cmd( |
| `core-admin fix imports` | `/mnt/dev/CORE/src/body/cli/commands/fix/imports.py` | `body.cli.commands.fix.imports:fix_imports_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/imports.py:36 async def fix_imports_command( |
| `core-admin fix all` | `/mnt/dev/CORE/src/body/cli/commands/fix/all_commands.py` | `body.cli.commands.fix.all_commands:run_all_fixes` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/all_commands.py:46 async def run_all_fixes( |
| `core-admin fix db-registry` | `/mnt/dev/CORE/src/body/cli/commands/fix/db_tools.py` | `body.cli.commands.fix.db_tools:sync_db_registry_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/db_tools.py:32 async def sync_db_registry_command(ctx: typer.Context) -> None: |
| `core-admin fix vector-sync` | `/mnt/dev/CORE/src/body/cli/commands/fix/db_tools.py` | `body.cli.commands.fix.db_tools:fix_vector_sync_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/db_tools.py:50 async def fix_vector_sync_command( |
| `core-admin fix list` | `/mnt/dev/CORE/src/body/cli/commands/fix/list_commands.py` | `body.cli.commands.fix.list_commands:list_commands` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/list_commands.py:18 def list_commands() -> None: |
| `core-admin fix headers` | `/mnt/dev/CORE/src/body/cli/commands/fix/code_style.py` | `body.cli.commands.fix.code_style:fix_headers_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/code_style.py:95 async def fix_headers_cmd( |
| `core-admin fix modularity` | `/mnt/dev/CORE/src/body/cli/commands/fix/modularity.py` | `body.cli.commands.fix.modularity:fix_modularity_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/modularity.py:27 async def fix_modularity_cmd( |
| `core-admin fix atomic-actions` | `/mnt/dev/CORE/src/body/cli/commands/fix/atomic_actions.py` | `body.cli.commands.fix.atomic_actions:fix_atomic_actions_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/atomic_actions.py:37 async def fix_atomic_actions_cmd( |
| `core-admin fix audit` | `/mnt/dev/CORE/src/body/cli/commands/fix/audit.py` | `body.cli.commands.fix.audit:fix_audit_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/audit.py:38 async def fix_audit_command( |
| `core-admin fix ir-triage` | `/mnt/dev/CORE/src/body/cli/commands/fix/fix_ir.py` | `body.cli.commands.fix.fix_ir:fix_ir_triage` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/fix_ir.py:77 def fix_ir_triage( |
| `core-admin fix ir-log` | `/mnt/dev/CORE/src/body/cli/commands/fix/fix_ir.py` | `body.cli.commands.fix.fix_ir:fix_ir_log` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/fix_ir.py:95 def fix_ir_log( |
| `core-admin fix purge-legacy-tags` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:purge_legacy_tags_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/metadata.py:139 async def purge_legacy_tags_command( |
| `core-admin fix policy-ids` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_policy_ids_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/metadata.py:158 async def fix_policy_ids_command( |
| `core-admin fix tags` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_tags_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/metadata.py:183 async def fix_tags_command( |
| `core-admin fix duplicate-ids` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_duplicate_ids_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/metadata.py:214 async def fix_duplicate_ids_command( |
| `core-admin fix placeholders` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_placeholders_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/metadata.py:239 async def fix_placeholders_command( |
| `core-admin fix dead-code` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_dead_code_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/metadata.py:259 async def fix_dead_code_cmd( |
| `core-admin fix body-ui` | `/mnt/dev/CORE/src/body/cli/commands/fix/body_ui.py` | `body.cli.commands.fix.body_ui:fix_body_ui_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/fix/body_ui.py:35 async def fix_body_ui_command( |
| `core-admin legacy-check rule` | `/mnt/dev/CORE/src/body/cli/commands/check/__init__.py` | `body.cli.commands.check:attr` | shim | /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:28 check_app.command("rule")(attr); /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:28 check_app.command("rule")(attr) |
| `core-admin legacy-check audit` | `/mnt/dev/CORE/src/body/cli/commands/check/__init__.py` | `body.cli.commands.check:attr` | shim | /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:45 check_app.command("audit")(attr); /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:45 check_app.command("audit")(attr) |
| `core-admin legacy-check lint` | `/mnt/dev/CORE/src/body/cli/commands/check/__init__.py` | `body.cli.commands.check:attr` | shim | /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:57 check_app.command("lint")(attr); /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:57 check_app.command("lint")(attr) |
| `core-admin legacy-check tests` | `/mnt/dev/CORE/src/body/cli/commands/check/__init__.py` | `body.cli.commands.check:attr` | shim | /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:59 check_app.command("tests")(attr); /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:59 check_app.command("tests")(attr) |
| `core-admin legacy-check system` | `/mnt/dev/CORE/src/body/cli/commands/check/__init__.py` | `body.cli.commands.check:attr` | shim | /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:61 check_app.command("system")(attr); /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:61 check_app.command("system")(attr) |
| `core-admin legacy-check diagnostics` | `/mnt/dev/CORE/src/body/cli/commands/check/__init__.py` | `body.cli.commands.check:attr` | shim | /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:72 check_app.command("diagnostics")(attr); /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:72 check_app.command("diagnostics")(attr) |
| `core-admin legacy-check body-ui` | `/mnt/dev/CORE/src/body/cli/commands/check/__init__.py` | `body.cli.commands.check:attr` | shim | /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:74 check_app.command("body-ui")(attr); /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:74 check_app.command("body-ui")(attr) |
| `core-admin legacy-check quality-gates` | `/mnt/dev/CORE/src/body/cli/commands/check/__init__.py` | `body.cli.commands.check:attr` | shim | /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:88 check_app.command("quality-gates")(attr); /mnt/dev/CORE/src/body/cli/commands/check/__init__.py:88 check_app.command("quality-gates")(attr) |
| `core-admin inspect repo-census` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect.repo_census:repo_census_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py:76 inspect_app.command("repo-census")(repo_census_cmd); /mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py:76 inspect_app.command("repo-census")(repo_census_cmd) |
| `core-admin inspect clusters` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:clusters_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/analysis.py:142 {"name": "clusters", "func": clusters_cmd}, |
| `core-admin inspect find-clusters` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:find_clusters_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/analysis.py:143 {"name": "find-clusters", "func": find_clusters_cmd}, |
| `core-admin inspect duplicates` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:duplicates_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/analysis.py:144 {"name": "duplicates", "func": duplicates_command}, |
| `core-admin inspect common-knowledge` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:common_knowledge_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/analysis.py:145 {"name": "common-knowledge", "func": common_knowledge_cmd}, |
| `core-admin inspect decisions` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:decisions_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/decisions.py:87 {"name": "decisions", "func": decisions_cmd}, |
| `core-admin inspect command-tree` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:command_tree_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/diagnostics.py:135 {"name": "command-tree", "func": command_tree_cmd}, |
| `core-admin inspect test-targets` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:inspect_test_targets` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/diagnostics.py:136 {"name": "test-targets", "func": inspect_test_targets}, |
| `core-admin inspect symbol-drift` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:symbol_drift_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/drift.py:102 {"name": "symbol-drift", "func": symbol_drift_cmd}, |
| `core-admin inspect vector-drift` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:vector_drift_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/drift.py:103 {"name": "vector-drift", "func": vector_drift_command}, |
| `core-admin inspect patterns` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:patterns_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/patterns.py:185 {"name": "patterns", "func": patterns_cmd}, |
| `core-admin inspect refusals` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:refusals_list_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/refusals.py:147 {"name": "refusals", "func": refusals_list_cmd}, |
| `core-admin inspect refusal-stats` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:refusals_stats_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/refusals.py:148 {"name": "refusal-stats", "func": refusals_stats_cmd}, |
| `core-admin inspect refusals-by-type` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:refusals_by_type_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/refusals.py:149 {"name": "refusals-by-type", "func": refusals_by_type_cmd}, |
| `core-admin inspect refusals-by-session` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:refusals_by_session_cmd` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/refusals.py:150 {"name": "refusals-by-session", "func": refusals_by_session_cmd}, |
| `core-admin inspect status` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:status_command` | needs_conversion | /mnt/dev/CORE/src/body/cli/commands/inspect/status.py:54 {"name": "status", "func": status_command}, |

## Top 10 Conversion Candidates

| Command | Current Location | Target Resource | Action | Notes |
|---|---|---|---|---|
| `core-admin submit changes` | `/mnt/dev/CORE/src/body/cli/commands/submit.py` | proposals | changes | Non-resource CLI group; consider migrating under resource module |
| `core-admin fix discover-actions` | `/mnt/dev/CORE/src/body/cli/commands/fix/handler_discovery.py` | code | discover-actions | Non-resource CLI group; consider migrating under resource module |
| `core-admin fix clarity` | `/mnt/dev/CORE/src/body/cli/commands/fix/clarity.py` | code | clarity | Non-resource CLI group; consider migrating under resource module |
| `core-admin fix complexity` | `/mnt/dev/CORE/src/body/cli/commands/fix/clarity.py` | code | complexity | Non-resource CLI group; consider migrating under resource module |
| `core-admin fix settings-di` | `/mnt/dev/CORE/src/body/cli/commands/fix/settings_access.py` | code | settings-di | Non-resource CLI group; consider migrating under resource module |
| `core-admin fix imports` | `/mnt/dev/CORE/src/body/cli/commands/fix/imports.py` | code | imports | Non-resource CLI group; consider migrating under resource module |
| `core-admin fix all` | `/mnt/dev/CORE/src/body/cli/commands/fix/all_commands.py` | code | all | Non-resource CLI group; consider migrating under resource module |
| `core-admin fix db-registry` | `/mnt/dev/CORE/src/body/cli/commands/fix/db_tools.py` | code | db-registry | Non-resource CLI group; consider migrating under resource module |
| `core-admin fix vector-sync` | `/mnt/dev/CORE/src/body/cli/commands/fix/db_tools.py` | code | vector-sync | Non-resource CLI group; consider migrating under resource module |
| `core-admin fix list` | `/mnt/dev/CORE/src/body/cli/commands/fix/list_commands.py` | code | list | Non-resource CLI group; consider migrating under resource module |
