# Plan: Autonomous PromptModel Compliance

**Goal:** Reduce `ai.prompt.model_required` blocking violations from 36 to 0
through a constitutional worker pipeline — without manual file editing.

**Constitutional principle:** Each worker does one thing. No conjunctions in mandate.

---

## The Pipeline

```
Audit findings (database)
        │
        ▼
[AuditIngestWorker]          — sensing — reads audit results, posts raw violations
        │
        ▼ blackboard: violation findings
        │
[PromptExtractorWorker]      — sensing — reads source, extracts inline prompt text
        │
        ▼ blackboard: extracted prompt proposals
        │
[PromptArtifactWriter]       — acting  — writes var/prompts/<name>/ artifact files
        │
        ▼ blackboard: artifact written confirmations
        │
[CallSiteRewriter]           — acting  — rewrites make_request_async() → PromptModel.invoke()
        │
        ▼
Audit re-run → violation count drops
```

---

## Workers

### 1. AuditIngestWorker
**Layer:** `will/workers/`
**Class:** sensing
**Phase:** audit
**Approval:** not required

**Mandate:** Read the most recent audit run findings for rule `ai.prompt.model_required`
and post each violation as a blackboard finding.

**Does:**
- Queries `core.audit_runs` / `core.action_results` for latest findings
- Deduplicates against already-posted blackboard entries (idempotent)
- Posts one `finding` per violation: `{file, line, rule}`
- Posts a `report` when done: total violations found

**Does NOT:**
- Read source files
- Interpret what the violation means
- Suggest fixes

---

### 2. PromptExtractorWorker
**Layer:** `will/workers/`
**Class:** sensing
**Phase:** runtime
**Approval:** not required

**Mandate:** For each unprocessed `ai.prompt.model_required` violation on the
blackboard, read the violating source file and extract the inline prompt string
passed to `make_request_async()`.

**Does:**
- Claims open findings from blackboard (subject: `ai.prompt.model_required`)
- Reads the violating file at the reported line
- Uses AST to locate the call and extract the prompt argument
- Infers a PromptModel name from file path + function context
- Posts extraction result to blackboard: `{file, line, prompt_text, suggested_name, input_vars}`
- If extraction fails (complex f-string, dynamic prompt): posts `needs_human` status

**Does NOT:**
- Write any files
- Generate artifact content
- Rewrite call sites

**Uses:** `PromptModel` artifact — `var/prompts/prompt_extractor/`

---

### 3. PromptArtifactWriter
**Layer:** `body/workers/`
**Class:** acting
**Phase:** execution
**Approval:** required (human reviews generated artifacts before write)

**Mandate:** For each approved prompt extraction on the blackboard, generate
and write the three PromptModel artifact files to `var/prompts/<name>/`.

**Does:**
- Claims approved extraction findings from blackboard
- Generates `model.yaml`, `system.txt`, `user.txt` content via LLM
- Writes three files via FileHandler to `var/prompts/<name>/`
- Posts confirmation to blackboard: `{artifact_path, files_written}`

**Does NOT:**
- Touch source Python files
- Rewrite call sites
- Determine what the prompt name should be (already decided by PromptExtractorWorker)

**Uses:** `PromptModel` artifact — `var/prompts/prompt_artifact_generator/`

---

### 4. CallSiteRewriter
**Layer:** `body/workers/`
**Class:** acting
**Phase:** execution
**Approval:** required (human reviews rewrite before it lands)

**Mandate:** For each confirmed artifact write on the blackboard, rewrite the
corresponding `make_request_async()` call site to use `PromptModel.invoke()`.

**Does:**
- Claims confirmed artifact findings from blackboard
- Reads the source file
- Uses AST to locate the exact call site (file + line from finding)
- Rewrites: `client.make_request_async(prompt, ...)` → `PromptModel.load("<name>").invoke({...}, client, user_id="...")`
- Adds `from shared.ai.prompt_model import PromptModel` import if missing
- Writes via FileHandler
- Posts completion to blackboard

**Does NOT:**
- Generate artifact content
- Make judgment calls about what the rewrite should look like
- Modify anything outside the single call site it was given

---

## Prompt Artifacts Needed

Two new artifacts to build before the workers can run:

### `var/prompts/prompt_extractor/`
Used by: PromptExtractorWorker
Purpose: Given a code snippet containing a `make_request_async()` call,
identify the prompt string and classify its input variables.
Output format: JSON `{prompt_text, input_vars, suggested_name}`

### `var/prompts/prompt_artifact_generator/`
Used by: PromptArtifactWriter
Purpose: Given an extracted prompt and context, generate the three
PromptModel artifact files.
Output format: JSON `{model_yaml, system_txt, user_txt}`

---

## Build Order

```
Step 1 — Declarations (.intent/workers/)
         Four YAML files. No Python. Establish constitutional standing first.

Step 2 — Prompt artifacts (var/prompts/)
         prompt_extractor/ and prompt_artifact_generator/
         Workers cannot call LLMs without these.

Step 3 — AuditIngestWorker
         Simplest worker. No LLM calls. Pure DB read + blackboard write.
         End-to-end test: run it, verify blackboard entries appear.

Step 4 — PromptExtractorWorker
         AST work is the hard part. Handle failures gracefully.
         Test on 2-3 simple violations first.

Step 5 — PromptArtifactWriter
         Test with human approval loop active.
         Verify generated artifacts pass ai.prompt.model_artifact_required audit rule.

Step 6 — CallSiteRewriter
         Most dangerous worker — touches production Python.
         Test on deleted/branch files first.
         Verify audit rule clears after rewrite.

Step 7 — End-to-end run on all 36 violations
         Run pipeline, approve proposals batch by batch.
         Audit should reach 0 blocking violations.
```

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Inline prompt is a complex f-string or variable | PromptExtractorWorker posts `needs_human` — human writes artifact manually |
| Generated artifact is semantically wrong | Approval gate before PromptArtifactWriter writes — human reviews content |
| CallSiteRewriter breaks import structure | AST-based rewrite only, plus audit re-run as verification gate |
| Some violations are legitimately exempt | Check against `ai.prompt.model_required` excludes list before posting finding |
| Worker posts duplicate findings | AuditIngestWorker deduplicates by file+line+rule before posting |

---

## Definition of Done

```
core-admin code audit --rule ai.prompt.model_required
→ 0 blocking violations
→ PASSED
```

Every fix is traceable: blackboard entry → approved proposal → FileHandler write → audit confirmation.
No violation was fixed by hand. CORE fixed itself.
