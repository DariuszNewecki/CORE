<!-- path: .intent/papers/CORE-IntentRepository.md -->

# CORE — The IntentRepository

**Status:** Canonical
**Authority:** Constitution
**Scope:** All runtime access to .intent/

---

## 1. Purpose

This paper defines the IntentRepository — the runtime index of all
constitutional documents, rules, and policies in `.intent/`.

---

## 2. Definition

The IntentRepository is the single source of truth for all `.intent/`
content at runtime. No component may read `.intent/` files directly.
All access goes through the IntentRepository.

It is a singleton. One instance per process. Thread-safe via lock.

---

## 3. What It Indexes

On first access, the IntentRepository scans `.intent/` and builds
two indexes:

**Policy index** — every `.yaml`, `.yml`, and `.json` file found in the
active directories declared in `META/intent_tree.yaml`. Each file is
indexed by its `policy_id` — the path relative to `.intent/` without
extension.

**Rule index** — every rule extracted from every indexed policy file.
Rules are found in sections named `rules`, `safety_rules`, `agent_rules`,
or `principles`. Each rule is indexed by its `id` field.

The active directories are: `META`, `constitution`, `rules`, plus any
optional directories declared in `intent_tree.yaml` that exist on disk.

---

## 4. Initialization

The index is built lazily on first access and cached for the process
lifetime. Building the index twice is prevented by a thread lock.

Initialization logs: `IntentRepository indexed N policies and M rules.`

If `META/intent_tree.yaml` does not exist, the repository falls back to
scanning only `META`, `constitution`, and `rules`.

---

## 5. Public API

| Method | Returns | Description |
|--------|---------|-------------|
| `get_rule(rule_id)` | `RuleRef` | Retrieve a single rule by ID. Raises `GovernanceError` if not found. |
| `list_policies()` | `list[PolicyRef]` | All indexed policies, sorted by policy_id. |
| `list_policy_rules()` | `list[dict]` | All rules from all policies, flattened. |
| `load_document(path)` | `dict` | Load and parse a single `.intent/` file. |
| `load_policy(policy_id)` | `dict` | Load a policy by its canonical ID. |
| `load_text(rel_path)` | `str` | Load a file as raw text by repo-relative path. |
| `filter_rules(...)` | `list[dict]` | Filter rules by phase, authority, policy_id, section. |

---

## 6. RuleRef

A `RuleRef` is the indexed form of a rule. It contains:

| Field | Description |
|-------|-------------|
| `rule_id` | The rule's unique ID. |
| `policy_id` | The policy that contains this rule. |
| `source_path` | The file path where this rule was found. |
| `content` | The full rule dict as declared in the policy file. |

---

## 7. PolicyRef

A `PolicyRef` is the indexed form of a policy. It contains:

| Field | Description |
|-------|-------------|
| `policy_id` | Path relative to `.intent/` without extension. |
| `path` | Absolute path to the policy file. |

---

## 8. Read-Only Contract

The IntentRepository is read-only. It loads documents. It indexes rules.
It never writes to `.intent/`.

`.intent/` is immutable to CORE at runtime. The IntentRepository
enforces this by having no write methods.

---

## 9. Non-Goals

This paper does not define:
- the format of policy or rule documents
- how rules are evaluated against code
- the enforcement engine
