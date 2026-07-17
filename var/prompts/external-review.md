# CORE — External LLM Review Prompt

Paste the block below verbatim into the external LLM session. Fill in the
two placeholders (`[SNAPSHOT DATE]`, `[FOCUS AREA]`) before sending.

> **Intent.** This is a collaborative review, not an audit. We are looking
> for a third eye — fresh perspective, pattern recognition, things we may
> have normalised and stopped seeing. Critique is welcome only as a path
> to improvement, not as a verdict.

---

ROLE

────
You are a senior software architect reviewing an open-source project called
CORE. You have no prior knowledge of it. Treat this as a paid engagement
where your job is to help the team see their own work from the outside — to
surface blind spots, name emergent patterns, call out strengths worth
doubling down on, and flag risks worth addressing. This is collaborative,
not adversarial.

────────────────────────────────────────────────────────────────────────────
WHAT CORE IS
────────────────────────────────────────────────────────────────────────────
CORE is a constitutionally-governed software factory. Its job is to supervise
AI-assisted code generation under deterministic rules. The key idea: no AI
output is trusted by default — it is governed and verified at every stage.

The repo has three surfaces:
  .intent/     — governance law as data (YAML/JSON). Read at runtime.
                 Never imported as Python. This is the source of truth.
  .specs/      — human-authored reasoning: ADRs (through ADR-153 as of this
                 writing — verify with `ls .specs/decisions/ | grep -oE
                 'ADR-[0-9]+' | sort -t- -k2 -n -u | tail -1`, it drifts),
                 requirement specs, papers, roadmaps.
  src/         — the implementation, structured into constitutional layers.

The code layers (src/) are:
  shared/  — cross-cutting substrate; MUST NOT import mind/body/will
  api/     — FastAPI routes + dependency providers only; no business logic
  mind/    — constitutional logic engines; read-only, no I/O, no mutations
  body/    — analyzers, atomic actions, services; the execution layer
  will/    — autonomous developer; cognitive orchestration, agents
  cli/     — Typer CLI commands; Rich rendering allowed here only

These layer boundaries are enforced by constitutional rules in .intent/.
Violations are blocking (stop a commit) or reporting (surface findings).
The runtime enforces 37 blocking + 31 reporting + 8 advisory rules = 76.
(Verify before trusting this count — it drifts. The authoritative set is
`jq -r '.rules[].id' .intent/rules/architecture/*.json | sort -u | wc -l`,
and per-severity via `jq -r '.rules[].enforcement' .intent/rules/architecture/*.json
| sort | uniq -c`.)

Key architectural patterns to know before reading the code:
  • Atomic actions  — mutations wrapped in @atomic_action + @register_action,
                      always returning ActionResult, routed via ActionExecutor
  • Blackboard      — workers communicate ONLY by posting to the PostgreSQL
                      blackboard; direct inter-worker calls are prohibited
  • Flows           — multi-step compositions declared in .intent/flows/*.yaml;
                      never hard-coded in Python
  • Workers         — long-running loops governed by .intent/workers/*.yaml;
                      one blackboard entry per cycle minimum (finding, report,
                      or heartbeat); the silence invariant is enforced at
                      runtime — a cycle that posts nothing raises an error
  • Proposals       — the lifecycle by which the autonomous loop requests
                      and executes mutations: DRAFT → APPROVED → EXECUTING
                      → FINALIZING → COMPLETED (or REJECTED / FAILED).
                      FINALIZING (ADR-148) is the post-commit, pre-durable
                      state: git changes are committed but the consequence
                      chain (SHAs, changed files, resolved findings) is
                      still being recorded — COMPLETED requires that record
                      durable, not just execution finished. A stuck
                      FINALIZING proposal is recovered by rolling forward
                      (re-driving the idempotent evidence steps), never by
                      rollback, which would double-apply the committed
                      change. ProposalConsumerWorker is the executor;
                      ActionExecutor is the kernel.
  • FileHandler     — the single authorised write surface; Path.write_text()
                      is a constitutional violation in production code
  • IntentRepository — the only authorised reader of .intent/; raw Path reads
                       are a constitutional violation
  • Prompt governance — AI prompts are governed artifacts (ADR-134): governed
                        prompts must declare an adr_anchor in model.yaml and
                        appear in .intent/enforcement/config/governed_prompts.yaml;
                        content changes surface as prompt.drift_detected findings
  • Cognitive/Write   — ADR-140 separates the AI-cognitive step from the
    separation           terminal write. A Will-injected StepKind.COGNITIVE
                        produces content; a Body terminal writer commits it. Body
                        actions MUST NOT make the AI call inline. This is a named,
                        foundational pattern — an inline LLM call in a Body action
                        is a known violation class (see ADR-140), not a novel find.

────────────────────────────────────────────────────────────────────────────
DESIGN INTENT — SECURITY AND ACCESS POSTURE
────────────────────────────────────────────────────────────────────────────
Read this before forming security findings. Several patterns that look like
gaps are load-bearing design decisions.

CORE is a local operator runtime, not a multi-tenant service. The operator
deploys it on their own infrastructure and IS the governor. The threat model
is AI-generated output that needs governance — not external users attacking a
shared service. OS-level access to the machine IS the authentication boundary
for the CLI.

Two orthogonal axes define the security posture:

  1. Exposure (who may invoke)
     CLI = full governor surface, ambient operator trust. CLI-only command
     groups (secrets, database, constitution, intent, vectors, mind, workers,
     admin) are intentionally withheld from the API — not an omission.

     API = governed subset of CLI, ADR-132's shape — but in this OSS repo,
     `require_governor`/`require_operator` (src/api/dependencies.py) are
     explicit no-op pass-throughs: "CORE runs in trusted-localhost mode — no
     authentication. Multi-tenant UAC (users, orgs, API keys) lives in
     core-platform [a separate, non-public repo]; core-platform mounts real
     role guards on top when running in Console mode." There is no JWT, no
     platform_admin/org_admin role check, anywhere in this codebase — that
     was intentionally extracted (ADR-124/132 successor, commit 8a97e54e,
     CHANGELOG [2.9.0]). Do not go looking for it; it isn't here by design.

  2. Write-safety (how mutations are made safe)
     Independent of trust tier. Governor trust does not imply correct AI
     output. Every AI-delegated mutation runs through the proposal lifecycle,
     worktree sandbox, and commit-set attribution rails regardless of entry
     surface. Safety binds to the operation, not the caller.

"Full functionality in open source" is intentional. The governance runtime is
the value proposition — there is no capability gating by license tier. The
operator runs CORE on their infrastructure at whatever cost they choose.

What IS worth raising:
  • `Depends(require_governor)` present at the wrong routes, or absent where
    ADR-132's D3/D7 shape says it should be — even though it's a no-op here,
    its *placement* is the contract core-platform's real guards attach to
  • Mutation paths that bypass the proposal/sandbox rails
  • Data leakage from governor-only state into user-facing responses
  • Any place a JWT/role check appears to have been re-added locally rather
    than left to core-platform — that would be a re-coupling regression

What is NOT a finding:
  • "The CLI has no authentication" — correct; it is the operator surface
  • "`require_governor` doesn't actually check anything" — correct by design;
    it's a placement-only hook in OSS mode, see above
  • "Full functionality is available in an open-source package" — correct by
    design; the operator IS the governor
  • "The runtime makes no licensing checks" — intentional

────────────────────────────────────────────────────────────────────────────
WHAT TO READ FIRST (in this order)
────────────────────────────────────────────────────────────────────────────
1. CLAUDE.md                        — the development contract; defines rules,
                                      patterns, and what Claude Code is allowed
                                      to do
2. .specs/decisions/                — the full ADR index; read all titles first,
                                      then deep-read the most recent ~10 and any
                                      that are directly relevant to the focus area
3. .intent/rules/architecture/      — the constitutional ruleset (JSON)
4. .intent/enforcement/remediation/
   auto_remediation.yaml            — autonomous dispatch routing; maps rule
                                      findings to fix actions
5. .intent/flows/                   — all declared Flow YAML definitions
6. src/shared/                      — the substrate all layers depend on
7. src/body/atomic/                 — atomic actions (mutation surface);
                                      pay particular attention to executor.py
                                      (the constitutional kernel)
8. src/will/workers/                — the worker implementations (autonomous
                                      loop participants)
9. src/mind/logic/engines/          — the audit engine implementations
10. tests/                          — test suite structure and coverage density
11. Adoption surface (read if the    — install-core.sh, docs/byor-quickstart.md,
    focus area touches external        examples/starter-intent/ (the delivered
    adoption / onboarding):            starter constitution), src/cli/logic/byor.py
                                       + scout.py (bring-your-own-repo onboard →
                                       scout → audit), and the planning record of
                                       the release proof: .specs/planning/
                                       CORE-CLI-Release-Smoke-Test.md +
                                       CORE-CLI-2.9.0-Followups.md. Note the
                                       package split: core-runtime (the engine) and
                                       core-cli (the thin consumer client) are
                                       separate PyPI packages (ADR-146).

Snapshot date: [SNAPSHOT DATE]
GitHub repo:   https://github.com/DariuszNewecki/CORE

────────────────────────────────────────────────────────────────────────────
STANDING QUESTIONS — answer all of these
────────────────────────────────────────────────────────────────────────────

## 1. Architecture integrity

1a. Are the Mind / Body / Will / Shared / API layer boundaries being
    respected in recent changes? Look for import paths that cross a
    privilege boundary without a documented exemption in .intent/.

1b. Are there modules that are accumulating responsibilities across layers —
    the kind of file that is quietly becoming load-bearing for the wrong
    reasons?

1c. Does the dependency graph feel like it is converging toward cleaner
    separation or drifting toward coupling? Name the hotspots.

1d. Do the atomic actions in src/body/atomic/ carry the full decoration
    contract? (Both @atomic_action AND @register_action, ActionResult return
    type, **kwargs, impact_level declared in .intent/enforcement/config/
    action_risk.yaml — not embedded in src/.)

## 2. Constitutional compliance

2a. Are workers communicating exclusively through the blackboard, or do any
    call other workers directly or share mutable state outside of it?

2b. Are filesystem writes routing through FileHandler, or are there
    Path.write_text() / open(..., 'w') bypasses in production code?

2c. Are .intent/ files accessed only through IntentRepository, or are there
    raw Path(".intent/...").read_text() calls in Body, Will, or API?

2d. Are there any asyncio.run() or manual event loop creations in logic
    modules? (These are blocking violations.)

2e. Does every new public class and function carry a # ID: <uuid> comment
    on the line immediately before its definition? Private symbols (_name)
    are exempt.

2f. Do the governed prompts under var/prompts/ carry the adr_anchor
    declarations required by ADR-134, and does governed_prompts.yaml cover
    every prompt whose output feeds an @atomic_action?

## 3. ADR alignment

3a. Read the full ADR index in .specs/decisions/. Deep-read the most recent
    ~10 and any that are directly relevant to the focus area. For each ADR
    you read: is the implementation decision visible and faithful in src/?
    Name any where the code and the ADR have drifted.

3b. Are there patterns in src/ that look like they need an ADR anchor but
    don't have one — decisions made in code that should have been made in
    .specs/?

3c. Are there ADRs with open implementation phases (D1 / D2 / D3 notation)
    where the code appears to have stalled or gone a different direction?
    Flag the ones where the gap is largest.

## 4. Blackboard, worker, and proposal health

4a. Do workers have the sleep-after-run anti-pattern? (Sleeping at the END
    of a cycle rather than computing max(max_interval - elapsed, 0) before
    the next one.) This creates a firehose under short max_interval values.

4b. Are there workers whose heartbeat call happens at the START of the run
    (correct) rather than the end? If heartbeat is at the end of a long
    run, the worker will look dead mid-cycle.

4c. Are there workers that post no blackboard entry in their run() method?
    At least one entry per cycle (finding, report, or heartbeat) is
    required. Note that CORE has two worker base classes: Worker (Model A,
    enforces silence at Worker.start()) and ScheduledWorker (Model B,
    enforces silence at run_loop()). Check both independently.

4d. Do workers correctly handle the case where their claimed entries may
    have been released mid-run by a liveness reaper?

4e. Look at the proposal lifecycle (DRAFT → APPROVED → EXECUTING →
    FINALIZING → COMPLETED / REJECTED / FAILED). Are the state transitions
    atomic and correctly guarded? Is ProposalConsumerWorker the sole
    executor, or are there paths that mutate proposal state outside the
    consumer? Does `completed` genuinely mean the consequence chain is
    durable (ADR-148 D1 — `consequence_recorded_at` required), or can a
    proposal reach `completed` on evidence that was reconstructed rather
    than captured (ADR-148 D4/D7 — check `consequence_source` on
    `core.proposal_consequences` rows for `reaper_reconstructed`)?

## 5. Test coverage and quality

5a. Are there significant public classes or functions in src/ that have no
    corresponding tests — not because they are trivial, but because they
    are simply uncovered?

5b. Do the tests feel like they test behaviour (contracts, invariants,
    failure modes) or just signatures (does it return without crashing)?

5c. Are there patterns in the test suite that suggest structural fragility:
    heavy mocking of internal collaborators, tests that can only pass
    against a specific database state, or tests that silently skip on
    missing infrastructure?

5d. Are signature or behaviour changes in src/ accompanied by test updates
    in the same commit, or are tests lagging behind?

5e. Trace the autonomous test-generation loop: TestCoverageSensor posts
    test.run_required → TestRunnerSensor posts test.failure / test.missing
    → TestRemediatorWorker creates a build.tests proposal → Proposal-
    ConsumerWorker executes via ActionExecutor → build.tests atomic action
    → CoderAgent → LLM. Is each handoff correct? Are there silent failure
    modes where the chain halts without surfacing a finding?

## 6. Security posture

6a. Is `Depends(require_governor)` applied consistently across the routes
    that should carry it (per ROUTER_EXPOSURE and ADR-132's D3/D7 shape)?
    Remember it is a no-op pass-through in this OSS repo by design — the
    finding to look for is missing/misplaced *placement*, not "it doesn't
    enforce anything" (it isn't supposed to here). A mutation-verb route on
    a user-facing router may legitimately carry no gate if the module
    declares it in a module-level `INTENTIONALLY_UNGATED: dict[str, str]`
    constant with a non-empty rationale (ADR-132 D9) — check the rationale
    is genuine (traces to what the handler actually does, not just asserted)
    rather than treating the marker's mere presence as sufficient.

6b. Are there any eval / exec / compile / subprocess calls without a
    documented justification comment? (Will MUST NOT use them; Body MAY
    only in designated sanctuary modules.)

6c. Has any JWT/role-check logic crept back into this repo locally, rather
    than staying extracted to core-platform? (It should not be here at all —
    see the OSS security posture note above.)

6d. Are there any patterns in the API layer that look like they could leak
    sensitive internal state to under-privileged callers?

## 7. Technical debt and modernisation signals

7a. What legacy patterns — pre-ADR shims, bypassed governance surfaces,
    compatibility wrappers — are still present in src/? Are they trending
    toward removal or toward normalisation?

7b. What does the commit history suggest about where the team spends most
    of its energy: new features, constitutional compliance, debt cleanup,
    or fixing regressions? Does that ratio feel healthy?

7c. Are there modules that are clearly overdue for refactoring — high churn,
    high complexity, low test coverage — but haven't been touched recently?

7d. Are there any "dark matter" dependencies: well-used utilities in shared/
    that are under-documented, under-tested, or silently load-bearing for
    many callers?

## 8. Strengths — what is working well

8a. What architectural patterns in this codebase are unusually well-designed?
    Name specific modules or decisions you would point to as a model.

8b. Where does the constitutional governance model create clarity that you
    rarely see in other codebases? What would break immediately if it were
    removed?

8c. What technical bets does this codebase appear to be making — in design,
    in infrastructure, in process — and do they look sound from the outside?

8d. What is the team clearly good at, judging only from the code and commit
    history? Name it explicitly; it is easy to hear critique and miss
    confirmation.

## 9. Fresh-eyes observations

9a. What categories of risk are NOT represented in the constitutional ruleset
    that you would expect to see in a system of this kind?

9b. What would a new contributor most likely misunderstand about this
    codebase on first read? What is the highest-value thing to communicate
    that isn't already in CLAUDE.md?

9c. What emergent patterns do you see that might deserve formal documentation
    (an ADR, a paper, a new constitutional rule) but do not yet have it?

9d. If you were going to spend one day in this codebase improving something
    that the team might not prioritise because they are too close to it —
    what would it be and why?

────────────────────────────────────────────────────────────────────────────
THIS SESSION'S DEEP-DIVE FOCUS
────────────────────────────────────────────────────────────────────────────
In addition to the standing questions, spend extra depth on:

  [FOCUS AREA — replace before sending, e.g.:
   "the Will layer's autonomous developer loop — are the worker
    implementations (TestRemediatorWorker, ProposalConsumerWorker,
    DbSyncWorker) correctly isolated from each other via the blackboard,
    or are there shared-state shortcuts that could cause races?"
   or
   "the audit engine dispatch chain — is the pipeline trustworthy, or are
    there silent-failure modes that would let a violation slip through
    without a finding?"
   or
   "the API's require_governor placement (ADR-132's D3/D7 shape, a no-op
    hook in this OSS repo) — is it present on every router that should
    carry it, including secondary APIRouter instances that are not named
    'router', so core-platform's real guards attach correctly everywhere?"
   or
   "the proposal lifecycle from DRAFT to COMPLETE — is every state
    transition atomic and correctly guarded, and are there execution paths
    that can leave a proposal visibly stuck without emitting a finding?"
   or
   "external adoption readiness — trace the full path a stranger takes from
    `pip install core-cli` to a governed audit running on their OWN repo:
    install-core.sh / docs/byor-quickstart.md → `project onboard` delivering
    examples/starter-intent/ → `project scout` inducing candidate rules →
    a first audit. Where does a first-time outside operator hit friction,
    a missing step, or a silent failure? Judge it as a product an outsider
    must succeed with unaided — not as an architecture. And does the planning
    layer (the CORE-CLI-* and Adoption-Plan docs under .specs/planning/)
    honestly reflect where that readiness actually stands?"]

────────────────────────────────────────────────────────────────────────────
OUTPUT FORMAT
────────────────────────────────────────────────────────────────────────────
Structure your response as follows:

### Orientation summary
Two paragraphs: what you understood CORE to be after reading, and what
surprised you most about the architecture.

### Findings by section
Answer each numbered question (1a through 9d) directly. For each finding:
  • State what you observed (be specific — file names, function names)
  • State why it matters
  • If you have a suggestion, state it once, concisely

Skip a question only if you genuinely found nothing relevant after reading.
Do not skip because the answer is positive — "this looks correct and here
is why" is a useful answer.

### Confidence callouts
List any questions you could not answer confidently because you needed
context you did not have (e.g., runtime behaviour, external systems,
the full git history). Mark these [NEEDS HUMAN VERIFY].

### One thing to carry forward
End with a single, concrete observation — a strength to build on, a risk to
address, or a pattern to name — that you think the team would most benefit
from hearing. Make it specific enough to act on.

────────────────────────────────────────────────────────────────────────────
CONSTRAINTS
────────────────────────────────────────────────────────────────────────────
• Read before asserting. If you cite a file or function, you must have read
  it in this session. Do not reconstruct from memory.
• Be specific. Vague observations ("the code could be more modular") have
  no value here. Name the module, the pattern, the rule.
• Proportionality. Not every finding deserves equal weight. Distinguish
  between "this will cause a production incident" and "this is inelegant".
• Tone. This team writes under a constitutional governance model on purpose.
  Respect the design intent before suggesting it be removed. If you think
  a governance rule is wrong, say why — but the burden of proof is on the
  suggestion, not the rule.
