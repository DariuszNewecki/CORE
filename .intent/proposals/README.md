# Proposals

Create proposals here with filename pattern `cr-*.yaml`.

## Format
- `target_path`: repo-relative path (e.g., `.intent/policies/safety_policies.yaml`)
- `action`: currently only `replace_file`
- `justification`: why this is needed
- `content`: full new file contents (string)
- `rollback_plan` (optional): notes to revert
- `signatures`: added by `core-admin proposals-sign`

See `cr-example.yaml` for a starter.
