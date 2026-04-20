# Diagnostic — autonomy.tracing.mandatory

Date: 2026-04-20
Target: `autonomy.tracing.mandatory` applied to `src/will/agents/self_healing_agent.py`
Claim under test: *rule produces zero findings despite the file containing no
`self.tracer.record` calls.*

---

## Headline

**The premise is false.** The rule is firing and IS producing a finding against
`src/will/agents/self_healing_agent.py`. No stage fails; the signal is reaching
the final report.

Evidence: [reports/audit_findings.json](../../reports/audit_findings.json) contains

```json
{
  "check_id": "autonomy.tracing.mandatory",
  "severity": "warning",
  "message": "Line 51: missing mandatory call(s): ['self.tracer.record']",
  "file_path": "src/will/agents/self_healing_agent.py"
}
```

Line 51 of [src/will/agents/self_healing_agent.py:51](../../src/will/agents/self_healing_agent.py#L51)
is `class SelfHealingAgent(Worker):`. A repo-wide `grep -n 'tracer\|Tracer'` on that
file returns nothing — the class contains zero tracer references — and the audit
correctly reports that.

The pipeline also produces a second finding for
[src/will/agents/tagger_agent.py:27](../../src/will/agents/tagger_agent.py#L27).

---

## Stage-by-stage results

### 1. Rule loading — PASS

`poetry run core-admin check rule --rule autonomy.tracing.mandatory --verbose`
does not exist (`No such command 'check'`). The command in the brief is wrong.

However the same invocation's startup log proves the rule was loaded:

```
IntentRepository indexed 132 policies and 120 rules.
Loaded 121 enforcement mappings from 33 files
Extracted 119 executable rules from 132 policies
Found 1 declared-only rules (no enforcement mappings):
  governance.artifact_mutation.traceable
```

`autonomy.tracing.mandatory` is NOT the declared-only rule, so it has an
enforcement mapping and was extracted as executable. The mapping lives at
[.intent/enforcement/mappings/will/autonomy.yaml:18](../../.intent/enforcement/mappings/will/autonomy.yaml#L18)
and binds it to `engine: ast_gate` with
`check_type: generic_primitive`,
`selector.name_regex: "Agent$"`,
`requirement: {check_type: required_calls, calls: ["self.tracer.record"]}`.

### 2. Scope resolution — PASS (with corrected import path)

The brief's import `from mind.logic.engines.ast_gate.base import AuditorContext`
raises `ImportError`. `AuditorContext` does not live in `ast_gate.base`; it lives
at [src/mind/governance/audit_context.py:70](../../src/mind/governance/audit_context.py#L70).
The brief's path is stale documentation.

Re-running with the correct import:

```python
from mind.governance.audit_context import AuditorContext
ctx = AuditorContext(Path('.').resolve())
files = ctx.get_files(['src/will/agents/**/*.py'],
                      ['src/will/agents/**/__init__.py',
                       'src/will/agents/**/factory.py'])
```

yields:

```
self_healing_agent in list: True
24 files matched
MATCH: /opt/dev/CORE/src/will/agents/self_healing_agent.py
```

Scope includes the target file.

### 3. Full audit run — rule fires, finding emitted

`poetry run core-admin code audit` summary table:

```
autonomy.tracing.mandat…   Line 51: missing   2 occurrences
                            mandatory call(s): ['self.tracer.record']
Rules declared: 120  Rules executed: 119  Coverage: 100.0%  Crashed: 0
Total findings: 39   Verdict: PASS
```

The `grep -i 'tracing.mandatory\|self_healing_agent' /tmp/audit_run.log` in the
brief yields no matches only because Rich wraps the words (`tracing.mandat…`,
`self_healing_a…`) across visual columns — a display artefact, not a signal of
absence. The raw findings JSON shows both occurrences cleanly.

### 4. Auto-ignore — empty

[reports/audit_auto_ignored.json](../../reports/audit_auto_ignored.json)
contains `{"generated_at": "...", "items": []}` (note: the top-level key is
`items`, not `entries` — the brief's filter would have returned empty even if
items existed). [reports/audit_auto_ignored.md](../../reports/audit_auto_ignored.md)
confirms `Total auto-ignored: 0`. Nothing is being silently dropped.

### 5. Stub-skip logic — does not apply

[src/mind/governance/constitutional_auditor_dynamic.py:66](../../src/mind/governance/constitutional_auditor_dynamic.py#L66):

```python
if rule.engine == "llm_gate" and "stub" in engine_type_name.lower():
    ...
    skipped_stub_count += 1
```

The guard is narrowly gated to `engine == "llm_gate"`. `autonomy.tracing.mandatory`
has `engine: ast_gate`, so it never enters this branch.

### 6. Direct engine invocation — reproduces the finding

```python
import ast
from mind.logic.engines.ast_gate.checks.generic_checks import GenericASTChecks
src = open('src/will/agents/self_healing_agent.py').read()
tree = ast.parse(src)
selector = {'name_regex': 'Agent$'}
requirement = {'check_type': 'required_calls', 'calls': ['self.tracer.record']}
for node in ast.walk(tree):
    if GenericASTChecks.is_selected(node, selector):
        err = GenericASTChecks.validate_requirement(node, requirement)
        print(type(node).__name__, getattr(node, 'name', '?'), '->', err)
```

Output:

```
ClassDef SelfHealingAgent -> missing mandatory call(s): ['self.tracer.record']
```

Same verdict as the orchestrated run.

---

## Failure-stage conclusion

| Stage              | Status                                                     |
|--------------------|------------------------------------------------------------|
| scope              | PASS — file included                                       |
| orchestrator load  | PASS — rule extracted and mapped to `ast_gate`             |
| dispatch           | PASS — engine runs against the file                        |
| auto-ignore        | PASS — zero suppressions, `items` list empty               |
| display            | PASS — present in JSON *and* in Rich summary table         |

**No stage fails.** The investigation's starting observation ("zero findings")
does not match the observed state of the system. Two hypotheses for where that
impression came from:

1. A `grep` over the Rich-wrapped stdout log (where `tracing.mandatory` is
   rendered as `tracing.mandat…`) was used as the oracle — that grep silently
   misses the real hit.
2. An older audit artefact pre-dating the current rule extraction was consulted.
   Current [reports/audit_findings.json](../../reports/audit_findings.json) is
   stamped with the 2026-04-20 run and contains the finding.

The brief also contains two stale references that should not be treated as
ground truth in future diagnostics:
- `core-admin check rule` subcommand does not exist.
- `AuditorContext` is not in `mind.logic.engines.ast_gate.base`; the real module
  is `mind.governance.audit_context`.

Per the brief, no fix is proposed.
