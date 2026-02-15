# CLI Conversion Clusters

Source: `/opt/dev/CORE/artifacts/cli_inventory.json`

## Summary

- Needs conversion: **39**
- Clusters: **3**

### Clusters by size (descending)

| Cluster (legacy root) | Commands |
|---|---:|
| `fix` | 22 |
| `inspect` | 16 |
| `submit` | 1 |

### Proposed target resources (from recommender)

| Target resource | Commands |
|---|---:|
| `code` | 38 |
| `proposals` | 1 |

## Clusters

### `fix` (22 commands)

| Command | Current module | Handler | Target resource | Action |
|---|---|---|---|---|
| `core-admin fix all` | `/mnt/dev/CORE/src/body/cli/commands/fix/all_commands.py` | `body.cli.commands.fix.all_commands:run_all_fixes` | `code` | `all` |
| `core-admin fix atomic-actions` | `/mnt/dev/CORE/src/body/cli/commands/fix/atomic_actions.py` | `body.cli.commands.fix.atomic_actions:fix_atomic_actions_cmd` | `code` | `atomic-actions` |
| `core-admin fix audit` | `/mnt/dev/CORE/src/body/cli/commands/fix/audit.py` | `body.cli.commands.fix.audit:fix_audit_command` | `code` | `audit` |
| `core-admin fix body-ui` | `/mnt/dev/CORE/src/body/cli/commands/fix/body_ui.py` | `body.cli.commands.fix.body_ui:fix_body_ui_command` | `code` | `body-ui` |
| `core-admin fix clarity` | `/mnt/dev/CORE/src/body/cli/commands/fix/clarity.py` | `body.cli.commands.fix.clarity:fix_clarity_command` | `code` | `clarity` |
| `core-admin fix complexity` | `/mnt/dev/CORE/src/body/cli/commands/fix/clarity.py` | `body.cli.commands.fix.clarity:complexity_command` | `code` | `complexity` |
| `core-admin fix db-registry` | `/mnt/dev/CORE/src/body/cli/commands/fix/db_tools.py` | `body.cli.commands.fix.db_tools:sync_db_registry_command` | `code` | `db-registry` |
| `core-admin fix dead-code` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_dead_code_cmd` | `code` | `dead-code` |
| `core-admin fix discover-actions` | `/mnt/dev/CORE/src/body/cli/commands/fix/handler_discovery.py` | `body.cli.commands.fix.handler_discovery:discover_actions_command` | `code` | `discover-actions` |
| `core-admin fix duplicate-ids` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_duplicate_ids_command` | `code` | `duplicate-ids` |
| `core-admin fix headers` | `/mnt/dev/CORE/src/body/cli/commands/fix/code_style.py` | `body.cli.commands.fix.code_style:fix_headers_cmd` | `code` | `headers` |
| `core-admin fix imports` | `/mnt/dev/CORE/src/body/cli/commands/fix/imports.py` | `body.cli.commands.fix.imports:fix_imports_command` | `code` | `imports` |
| `core-admin fix ir-log` | `/mnt/dev/CORE/src/body/cli/commands/fix/fix_ir.py` | `body.cli.commands.fix.fix_ir:fix_ir_log` | `code` | `ir-log` |
| `core-admin fix ir-triage` | `/mnt/dev/CORE/src/body/cli/commands/fix/fix_ir.py` | `body.cli.commands.fix.fix_ir:fix_ir_triage` | `code` | `ir-triage` |
| `core-admin fix list` | `/mnt/dev/CORE/src/body/cli/commands/fix/list_commands.py` | `body.cli.commands.fix.list_commands:list_commands` | `code` | `list` |
| `core-admin fix modularity` | `/mnt/dev/CORE/src/body/cli/commands/fix/modularity.py` | `body.cli.commands.fix.modularity:fix_modularity_cmd` | `code` | `modularity` |
| `core-admin fix placeholders` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_placeholders_command` | `code` | `placeholders` |
| `core-admin fix policy-ids` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_policy_ids_command` | `code` | `policy-ids` |
| `core-admin fix purge-legacy-tags` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:purge_legacy_tags_command` | `code` | `purge-legacy-tags` |
| `core-admin fix settings-di` | `/mnt/dev/CORE/src/body/cli/commands/fix/settings_access.py` | `body.cli.commands.fix.settings_access:fix_settings_di_cmd` | `code` | `settings-di` |
| `core-admin fix tags` | `/mnt/dev/CORE/src/body/cli/commands/fix/metadata.py` | `body.cli.commands.fix.metadata:fix_tags_command` | `code` | `tags` |
| `core-admin fix vector-sync` | `/mnt/dev/CORE/src/body/cli/commands/fix/db_tools.py` | `body.cli.commands.fix.db_tools:fix_vector_sync_command` | `code` | `vector-sync` |

### `inspect` (16 commands)

| Command | Current module | Handler | Target resource | Action |
|---|---|---|---|---|
| `core-admin inspect clusters` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:clusters_cmd` | `code` | `clusters` |
| `core-admin inspect command-tree` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:command_tree_cmd` | `code` | `command-tree` |
| `core-admin inspect common-knowledge` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:common_knowledge_cmd` | `code` | `common-knowledge` |
| `core-admin inspect decisions` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:decisions_cmd` | `code` | `decisions` |
| `core-admin inspect duplicates` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:duplicates_command` | `code` | `duplicates` |
| `core-admin inspect find-clusters` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:find_clusters_cmd` | `code` | `find-clusters` |
| `core-admin inspect patterns` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:patterns_cmd` | `code` | `patterns` |
| `core-admin inspect refusal-stats` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:refusals_stats_cmd` | `code` | `refusal-stats` |
| `core-admin inspect refusals` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:refusals_list_cmd` | `code` | `refusals` |
| `core-admin inspect refusals-by-session` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:refusals_by_session_cmd` | `code` | `refusals-by-session` |
| `core-admin inspect refusals-by-type` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:refusals_by_type_cmd` | `code` | `refusals-by-type` |
| `core-admin inspect repo-census` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect.repo_census:repo_census_cmd` | `code` | `repo-census` |
| `core-admin inspect status` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:status_command` | `code` | `status` |
| `core-admin inspect symbol-drift` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:symbol_drift_cmd` | `code` | `symbol-drift` |
| `core-admin inspect test-targets` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:inspect_test_targets` | `code` | `test-targets` |
| `core-admin inspect vector-drift` | `/mnt/dev/CORE/src/body/cli/commands/inspect/__init__.py` | `body.cli.commands.inspect:vector_drift_command` | `code` | `vector-drift` |

### `submit` (1 commands)

| Command | Current module | Handler | Target resource | Action |
|---|---|---|---|---|
| `core-admin submit changes` | `/mnt/dev/CORE/src/body/cli/commands/submit.py` | `body.cli.commands.submit:integrate_command` | `proposals` | `changes` |
