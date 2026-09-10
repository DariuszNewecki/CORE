---
kind: planning
title: CORE ADR-159 D9 Seal Custody and Trial 0 Apparatus Design
status: draft
---

# CORE ADR-159 D9 Seal Custody and Trial 0 Apparatus Design

**Status:** Draft — for Governor review. **Correction notice (2026-09-10, second pass):** the
prior version of this document contained a contradiction — its introduction and §7 (then-numbered
§6) claimed no sealed content was accessed while writing it, while the incident disclosure further
down the same document correctly said otherwise. That contradiction is corrected throughout this
version. The facts, restated once, precisely:

- No D9 mechanism has been implemented and no trial has been run.
- While distinguishing `seal_manifest.py`'s sealing *tooling* from the sealed *data* it turned out
  to also contain, this session accidentally accessed approximately two of the benchmark's eight
  rows during planning.
- No row content is reproduced anywhere in this document. The incident is described in full in
  §17, not hidden or softened.
- Because of this, and because CORE's project-memory store was separately found to already carry
  pre-existing Phase 1 content (§9 finding 6), **this session — and every session that loads CORE's
  current project memory — is excluded from serving as blind procedure author or trial runner.**
  §12's runner boundary and the companion blind-author brief
  (`.specs/planning/CORE-Autonomy-Trials-Blind-Author-Brief.md`) are written around that exclusion,
  not in spite of it.

**Scope:** design only, per ADR-159's own framing — "the run design for Trials 0 and 1 —
harness, isolation mechanics, output layout, procedure — is revisable mechanics and belongs in
`.specs/planning/`, not [the ADR]." This document does not alter ADR-159 D1–D9, does not redefine
T-A/T-B/T-C, and does not commit either trial's semantic procedure to text. It does not implement
D9, publish or hash the seal, author either trial procedure, invoke a fresh session, provision the
coldroom substrate, or run anything.

---

## 1. ADR-159 threshold and claim boundaries (restated, not redefined)

Restated here only to ground the design that follows; ADR-159 remains canonical on divergence.

| Threshold | State of | Criteria (abridged — see ADR-159 D2) |
|---|---|---|
| **T-A** | the runner | #855 reconciled; CI green; G8 attested; commit frozen and tagged. **Reached** (2026-09-04). |
| **T-B** | the claim | Trial 1 (D6) succeeds against its six declared criteria, with honest, reconstructable evidence. **Not reached.** |
| **T-C** | sustained operation | controlled write experiment succeeds; recovery/rollback proven; then a sustained soak with no unauthorized writes, no lost proposals, no ambiguous lifecycle states. **Not reached.** |

**D3 containment rule:** a finding beyond a threshold's declared criteria is backlog unless it
invalidates the trial in progress, argued explicitly in writing. §2's post-publication discipline
below applies this specifically to post-publication apparatus changes.

**D4 adaptation line:** acceptable adaptation (target `.intent/`, GRC catalogs, domain profiles,
configuration/resource bindings) versus thesis-negative adaptation (new `src/` modules, new
check/rule classes, target-specific runtime branches, schema changes). Both trials' reports must
quantify which category their own work fell into.

**Units D and E** (2026-09-06 – 2026-09-10) are preliminary engineering evidence for the mechanics
a controlled write and its rollback require. They occurred before D9 and T-B and receive no T-C or
other threshold credit (2026-09-10 Note).

---

## 2. Ordering (Governor ruling, 2026-09-10)

The required order, fixed now so it cannot be argued after the fact:

1. **Correct the planning record and record the ruling** — this document, this pass.
2. **Produce a frozen blind-author input brief** — `CORE-Autonomy-Trials-Blind-Author-Brief.md`,
   this unit, not invoked.
3. **In a separate future action**, use a fresh stateless author (no project memory, no
   conversation history, no connectors, no repository/web access — see the brief) to write both
   Trial 0 and Trial 1 semantic procedures.
4. **Review and freeze both procedures** without adding target-specific investigative guidance.
5. **Implement D9 custody and publish the seal plus manifest** (§7–§8) — only after step 4.
6. **Review D9 evidence.**
7. **Run Trial 0 exactly once.**
8. **Run Trial 1** only after Trial 0 is closed and ADR-159 permits proceeding.

**D9 must exist before Trial 0 runs (step 7); it does not need to precede blind procedure
authorship (steps 2–4).** Steps 2–4 can and should happen first — writing the procedures does not
require the seal to be published, and delaying them behind D9 custody work would only extend the
window during which an un-frozen procedure could still be shaped by hindsight.

**Post-publication discipline:** after the seal is published (step 5), only a mechanical apparatus
correction justified through a written D3 invalidation argument may be considered — and even then,
it must not silently alter a frozen investigation prompt, scoring rule, target decomposition, or
pass criterion. A defect discovered in the *apparatus* (isolation, evidence capture, harness
plumbing) is fixable under that argument. A defect discovered in the *procedure itself* is not
silently patchable — see §14's D3 discussion, unchanged in substance from the prior pass.

**2026-09-10 update — steps 2–3 advanced; step 7 now has a disclosed blocker.** The blind-author
brief was delivered to a fresh, stateless session (Claude Opus 5, Playground; no project
attachment, memory, connectors, or repository/web access per its own "Author's note on
environment"). Both Trial 0 and Trial 1 procedures were produced in that single generation attempt.
The raw output is filed, with full provenance disclosure, at
`.specs/attestations/adr-159-blind-author-raw-claude-opus-5-20260910.md` — custody, not authorship;
see that file's own §1 for why a session with loaded project memory may file it without violating
the exclusion above.

Independently, `.specs/planning/CORE-Autonomy-Trial-Runner-Interface-Appendix.md` (read-only
object-level inspection of both frozen runner pins, no checkout or execution) found that **neither
pin exposes an interface matching what both procedures assume** — a component that accepts a
free-text task statement and autonomously plans and executes a multi-step investigation, recording
its own findings to the blackboard. The closest real primitives at both pins are a non-executing
constitutional-validation demo, a read-only/non-execution conversational Q&A path, and a
goal-blind named-worker launcher. Full evidence: the Appendix's headline finding and its
item-by-item detail (items 1–14).

**This is a blocker on step 7 (Trial 0 execution), not resolved by this document.** Realizing
either procedure as written against `27160a0a` would require new production code that does not
exist at that pin — which step 2's own ordering constraint (blind authorship before D9, D9 before
execution) does not license this document, or any session, to design, build, or route around.
Whether to adapt the runner, adapt the procedure, or treat this as a Trial 0 finding in its own
right is **the Governor's decision, to be made separately** — not resolved here and not implied by
anything above.

---

## 3. Exact pins

### Trial 0 — apparatus rehearsal (ADR-159 D5)

| | Value |
|---|---|
| Runner | T-A certified baseline: tag `autonomy-experiment-ready-2026-09-04`, commit `27160a0a8768cf72bbe2a8fecc3d9169db758efc` |
| Subject | frozen CORE at `c4d9fdf9dc52c7d71981e367b64d00b0c994910b` (the Phase 1 `core_baseline_pin`), read-only, no later issues/commits/ADRs/benchmark answers visible |
| Outputs | stored separately from the subject and from the runner's own repository (D5) |

Not rebaselined by this unit. If the frozen runner cannot execute the preregistered trial, that
is an honest Trial 0 result, not permission to patch it (Governor ruling, 2026-09-10).

### Trial 1 — the proof (ADR-159 D6)

| | Value |
|---|---|
| Runner | `b57423dc85c11c6650a9515c136bab49b02107ec` (Unit C.1) — separately frozen, disclosed by exact SHA only; no tag or release created for it |
| Subject | `DariuszNewecki/ITAM-Governance-Library @ a2fe0a62d96423d8bc7296e3976e642a2cb120a3` |
| Subject verification | **Verified** via GitHub's commit API (`GET /repos/DariuszNewecki/ITAM-Governance-Library/commits/a2fe0a62d96423d8bc7296e3976e642a2cb120a3`, 2026-09-10) — resolves to a real commit, author `Dariusz Newecki`, dated 2026-08-23. Not cloned for this verification. |

The Trial 1 runner is the last baseline containing the Governor-authorized external-target safety
package — including physical symlink-containment enforcement (`b57423dc` itself) — while excluding
the later Unit D/E execution scaffolding and write-path corrections. First excluded commit:
`c0694953`. See §5 for the full commit ledger.

### Blind-authored procedure pin cross-verification (2026-09-10)

The four pins above were checked, verbatim, against the corresponding pins copied into the
blind-authored Document A §A3 and Document B §B3 (preserved at
`.specs/attestations/adr-159-blind-author-raw-claude-opus-5-20260910.md`). All four match exactly:
Trial 0 runner (`27160a0a...` / tag `autonomy-experiment-ready-2026-09-04`), Trial 0 subject
(`c4d9fdf9...`), Trial 1 runner (`b57423dc...`), Trial 1 subject (`a2fe0a62...`). The blind author's
own note discloses these were copied "verbatim and unverified" from its perspective (it had no
means to reach anything); this cross-check is the corresponding verification from this side —
confirming the brief delivered the correct pins, not confirming the pins themselves resolve at
execution time (that remains A5/B5's job, unperformed, at run time).

---

## 4. Verification of ADR-159 Notes entries 1 and 2 (worker authority, policy dependency)

Unchanged from the prior pass — performed before those Notes were appended (2026-09-10), against
the repository at the cited commits:

- **Worker authority (`8569f02f`):** confirmed — `tests/fixtures/external_target/intent_overlay/workers/proposal_consumer_worker.yaml` scopes `mandate.scope.paths` to exactly `["package/example.py"]`; `permitted_tools` is exactly `crate.create`, `canary.validate`, `crate.apply`, `git.commit` — byte-identical to production's own `.intent/workers/proposal_consumer_worker.yaml` list; `identity.uuid` (`b7e25f7a-91f3-4f77-ba34-d29a871c3e0c`) is confirmed distinct from the production worker's UUID (`c1d2e3f4-a5b6-7890-cdef-123456789abc`); the diff touches only `tests/fixtures/external_target/` — no root `.intent/` change; `safe_auto_approval_envelope.yaml` is untouched by the commit.
- **Proposal-lifecycle policy dependency (`bd2b336f`):** confirmed — the fixture's `intent_overlay/rules/will/proposal_lifecycle.json` added by this commit is byte-identical to CORE's own `.intent/rules/will/proposal_lifecycle.json` (both then and now); `body/atomic/proposal_lifecycle_actions.py`'s `claim.proposal` registration declares `policies=["rules/will/proposal_lifecycle"]`, confirming the stated dependency is real and pre-existing, not invented for the fixture.

---

## 5. Commit ledgers

### Included in the Trial 1 runner (`27160a0a` → `b57423dc`, inclusive) — five commits

| Commit | Subject | Classification |
|---|---|---|
| `660834c6` | feat(external): fail closed on target binding | **Production** — new module `src/shared/infrastructure/external_target_binding.py`. **Test** — `tests/shared/infrastructure/test_external_target_binding.py`. **Documentation** — ADR-159 Notes (2026-09-05 ruling). |
| `cb47438a` | feat(cli): pre-bootstrap external-verify launcher | **Production** — `src/cli/admin_cli.py`, `src/cli/runtime_external_verify.py`. **Test** — `tests/cli/test_runtime_external_verify.py`. |
| `fce5c064` | fix(coldroom): install and enable qemu-guest-agent in template prep | **Infrastructure/ops**, unrelated to the external-target safety package — `scripts/coldroom-prep.sh` only. Relevant to §11's substrate choice. |
| `c7de61e5` | feat(external): Unit C neutral target fixture proves authority boundary | **Fixture/policy** — `tests/fixtures/external_target/{materialize.py, intent_overlay/*, template/*}`. **Test** — `test_authority.py`, `test_materialization.py`. **Documentation** — ADR-159 Notes (2026-09-06 ruling). |
| `b57423dc` | fix(actions): deny symlink target escapes **(runner pin)** | **Production** — `src/body/atomic/executor.py` (`_check_physical_containment`, a real security fix). **Test** — `tests/body/atomic/test_executor_physical_containment.py` (new), plus fixture-adjacent updates. |

**Net production surface in the Trial 1 runner, beyond T-A:** the external-target binding guard,
the pre-bootstrap CLI launcher, and the physical symlink-containment check. All three are the
Governor-authorized external-target safety package (Units A/B/C/C.1); none are target-specific
adaptation under ADR-159 D4.

### Excluded from the Trial 1 runner (`c0694953` → `f2c50dc6`, inclusive) — eight commits

| Commit | Subject | Classification |
|---|---|---|
| `c0694953` | test(external): prove governed format mutation | **Fixture/test** — Unit D scaffold. No production changes. |
| `8569f02f` | feat(external): authorize fixture-local proposal_consumer_worker declaration | **Fixture/policy** — verified in §4. |
| `d12254e5` | fix(external): Unit D scaffold calls Worker.start(), not run() | **Fixture/test** only. |
| `bd2b336f` | feat(external): authorize claim.proposal's policy dependency in fixture overlay | **Fixture/policy** — verified in §4. |
| `b4acb30d` | fix(body): Unit D formatter-runtime correction — resolve and run Ruff directly | **Production** — `code_style_service.py`, `subprocess_utils.py` (new `run_direct_command`; the Poetry-wrapped-false-success fix). |
| `4ddcaa32` | fix(body): Unit D final Ruff-runtime correction — check/fix phase too | **Production** — `code_style_service.py`, second phase. |
| `cca802ee` | test(external): Unit E scaffold — live post-propagation rollback qualification | **Fixture/test** only. |
| `f2c50dc6` | fix(external): route Unit D/E disposable workdirs through var/tmp, not /tmp | **Fixture/test** only. |

**Material consequence:** the Trial 1 runner (`b57423dc`) does **not** include the
`b4acb30d`/`4ddcaa32` fix — `fix.format`'s Ruff invocation at that pin still goes through
`run_poetry_command`, which silently reports success against a target with no `pyproject.toml`.
Not expected to matter for Trial 1 (a governed-document corpus, not software `fix.format` would
run against), recorded so it isn't rediscovered mid-trial as a surprise.

---

## 6. D9 — seal threat model

**Asset:** the Phase 1 sealed benchmark, `work/external-validation/phase1-benchmark-SEALED.json`
(governor-signed, sealed 2026-08-27; run closed 2026-08-29) — eight rows scoring Trial-0/Trial-1
correctness against a pre-registered answer key. Its path is confirmed to exist. **Its content was
not deliberately read or reproduced in this document; §17 discloses one accidental partial
exception (~2 of 8 rows), during this pass's own predecessor, with no content repeated here.**

**What the threat model protects against:**

1. **Runner self-answering.** If the Trial 0 runner process (or Trial 1's, symmetrically) can read
   the seal's rows, its "recall" figure is definitionally worthless. D9's core concern, stated
   directly in ADR-159: "a runner that can read its own answer key produces a recall figure of no
   evidential value."
2. **Single-point-of-failure custody.** The seal currently exists only on the operator's local
   disk, under a `.gitignore`d path (`work/*`, line 88). §7 resolves this.
3. **Retroactive tampering.** If the seal can be edited after Trial 0/1 run, a disappointing recall
   figure could be quietly revised. `seal_manifest.py`'s own sha256-over-canonical-bytes pattern
   (confirmed to exist by structural reference, never read further than necessary to confirm its
   shape) is the existing mitigation; §7's published manifest makes it independently checkable.
4. **Operator-as-single-witness.** The Governor is both the seal's author and, in a solo-developer
   project, the only human available at all. §12 states precisely what this design can and cannot
   claim about that — see the retrieval-independence / scoring-separation split there; the prior
   pass's "a different session is a practical substitute" claim is withdrawn, not merely reworded.
5. **Incidental leakage via tooling.** The prior pass of this document (and its predecessor
   session) accidentally read part of the seal's content while inspecting what was believed to be
   pure sealing *tooling* — `seal_manifest.py` embeds both the sealing logic and the row data in
   one file. §17 discloses this fully. Structural lesson already applied: §7/§11 treat "the sealing
   script" and "the sealed data" as two artifacts requiring separate handling.
6. **Memory-substrate leakage — confirmed, not hypothetical, still unresolved by a control in this
   document.** CORE's Claude Code auto-memory system persists project memory in files outside the
   repository, auto-loaded into every session's context by the harness itself, independent of the
   CORE checkout's own filesystem/network/credential isolation. Several memory files predating D9
   already contain Phase 1 benchmark content. Checkout-level isolation (§11) does nothing to
   prevent a Claude-Code-driven process from separately auto-loading this store. **This is why §12
   requires the trial runner to be frozen CORE itself, launched by a deterministic operator
   harness — not Claude Code, and not any process that would auto-load this project's memory.**
   Blind procedure authorship carries the identical requirement (§2 step 3; the companion brief
   specifies a session with no project memory at all).
7. **Custody of the blind author's raw output is not the same exposure as authorship or running.**
   §6 point 6's exclusion is scoped to *producing* a procedure or *running* a trial with
   memory-loaded context, because contaminated memory could leak answer-key content into work that
   is later scored. Receiving already-finished text from a stateless author, checking its
   provenance, and filing it unmodified is a custodial act on text the custodian did not generate —
   there is no channel for this session's memory to alter content it never authored. (Governor
   ruling, 2026-09-10, recorded here because this is the section that states the exclusion this
   ruling narrows.) This does not reopen or soften points 1–6 above: a memory-loaded session remains
   excluded from writing either procedure and from being any trial's runner, scorer, or adjudicator.

---

## 7. Seal custody — decided, conditionally

**Decision (Governor ruling, 2026-09-10):** the sealed artifact's custody mechanism is a **tracked
public attestation** — not one of the three previously-undecided options, now resolved:

- the exact sealed artifact bytes, committed as-is;
- a SHA-256 manifest alongside it;
- tracked under `.specs/attestations/` (the same tree already holding prior sealed reports, e.g.
  `e15-coldroom-3cbe0be0-20260726.md`);
- retrievable through public Git history by anyone, indefinitely, independent of the operator's
  local disk, account session, or continued availability.

**Conditions that must both hold before publication (not yet satisfied; not performed in this
unit):**

1. **Both semantic procedures are frozen first** (§2 steps 1–4). Publishing the seal before the
   procedures exist would let their authorship be shaped, even inadvertently, by proximity to the
   answer key.
2. **A non-printing automated scan proves the artifact contains no credentials or sensitive
   material.** "Non-printing" — the scan's own output must not itself become a second disclosure
   channel (e.g., it reports pass/fail and, on failure, categories/locations, never matched
   secret values). If the scan fails, publication is refused and a new custody ruling is required;
   this document does not specify a fallback, because none is authorized to be invented here.

This document does not publish, copy, hash, or scan the artifact — that is step 5 of §2's ordering,
performed after both conditions are independently confirmed satisfied.

---

## 8. Retrievability and integrity-check mechanism

Once §7's conditions are met and the attestation is published:

1. The commit adding it to `.specs/attestations/` carries the SHA-256 manifest in the same commit
   as the artifact — no separate, later "here is the hash" step that could itself be tampered with
   independently.
2. **Retrieval path:** `git clone`/`git show` against the public `DariuszNewecki/CORE` history, by
   anyone, with no credential and no dependency on the operator's disk or account.
3. **Re-verification:** fetch the artifact from that path, compute its SHA-256, compare to the
   manifest recorded in the same commit. The same class of check `git fsck` already relies on — no
   new subsystem, per D9's own instruction that the mechanism is "a planning decision, not a
   constitutional one."

---

## 9. Runner boundary (Governor ruling, 2026-09-10)

**The trial runner is frozen CORE itself, launched directly by a deterministic operator harness
inside the coldroom VM. Claude Code is not the runtime wrapper for either trial.**

Claude Code (this session, or a general-purpose session like it) may help **build or review**
apparatus **before** a trial runs — writing the isolation scripts, reviewing the harness, checking
evidence-capture code, exactly the kind of work this document itself is. It must not, for either
trial:

- author either blind procedure (§2 step 3 is reserved for a fresh stateless session with no
  project memory — see the companion brief);
- wrap or direct the live trial (the operator harness invokes the frozen runner directly — a shell
  script or equivalent deterministic launcher, not an interactive or agentic Claude Code process
  standing between the operator and the runner);
- supply prompts during execution (the runner's prompts come from the frozen procedure, provisioned
  before isolation is sealed — nothing is typed or generated live);
- inspect the subject during the run (the operator does not read along; inspection during
  execution is exactly the self-answering risk §6 finding 1 describes, applied to a human observer
  instead of the runner itself, and is refused for the same reason);
- score the output before the runner terminates (§12 — scoring is strictly post-termination);
- initiate a retry (§14 step 9 — no automatic or operator-triggered retry inside one trial
  invocation).

**What CORE's own frozen runner may do:** make the LLM calls its frozen configuration defines.
Those calls must begin with fresh provider context each time — no inherited Claude Code memory,
no inherited conversation history, nothing carried over from any apparatus-building or
procedure-authoring session that preceded the trial. §10's exact-runner verification confirms the
frozen runner's own LLM-calling code has no structural path to acquire any of that even if it
wanted to (no `tools` parameter is ever passed to any provider's completion call).

---

## 10. Exact-runner verification (read-only object inspection, both pins)

Performed via `git grep`/`git show` against the two frozen commit objects directly — **neither
runner was executed.**

**Method and findings:**

1. Searched both `27160a0a8768cf72bbe2a8fecc3d9169db758efc` and
   `b57423dc85c11c6650a9515c136bab49b02107ec` for web-search/fetch/browser/connector-shaped
   identifiers across `src/`. Two hits in each, both confirmed false positives on inspection: the
   string "connector" appears in `src/mind/governance/executable_rule.py` (a code comment: "just
   the connector (pure data)") and as the class name `IntentConnector` in
   `src/shared/infrastructure/intent/intent_connector.py` — an internal `.intent/` data-loading
   abstraction, unrelated to any web/GitHub connector concept.
2. Searched both pins for GitHub API client usage (`api.github.com`, `PyGithub`, `octokit`) in
   `src/` — **zero matches** in either.
3. Read `src/shared/infrastructure/llm/providers/anthropic.py` in full at `b57423dc` — the only
   outbound network call is `httpx.AsyncClient.post()` to
   `{api_url}/v1/messages`, with a payload containing exactly `model`, `max_tokens`, `system`,
   `messages` — **no `tools` key, no tool-use of any kind.** `response_format` is explicitly
   documented as "currently ignored... falls back to standard text generation." Confirmed
   byte-identical between `27160a0a` and `b57423dc` (`diff` of the file at both SHAs: no
   difference) — neither Unit A/B/C/C.1 touched this file.
4. Checked the OpenAI and Ollama provider implementations (`providers/openai.py`,
   `providers/ollama.py`) and the shared `providers/base.py` for `tools=`/`tool_choice` — **zero
   matches** in any of the three.
5. Enumerated every `@atomic_action`-registered action at `b57423dc` (38 actions, full list
   retained in this pass's own working notes) — none are web/search/fetch/browse-shaped; the
   complete action surface is file/crate/proposal/sync/test/fix/build/refactor/document-scoped.

**Conclusion:** neither frozen runner exposes or requests web search, URL fetching, browser tools,
GitHub connectors, provider-hosted retrieval, or an arbitrary remote-content-capable tool
definition, as verified by direct object-level inspection rather than asserted from memory or
documentation. **No unresolved D9 blocker from this specific check.** (§6 finding 6, the
memory-substrate leakage, remains a separate, already-flagged, genuinely unresolved blocker — see
§15's acceptance criteria.)

---

## 11. Runner-inaccessibility mechanism

**Hard isolation constraint:** the sealed material resides in a gitignored path inside the
operator's live CORE working tree (`/opt/dev/CORE/work/`, plus the `ITAM` symlink at
`/opt/dev/CORE/ITAM` → `/mnt/vector_db/YPTO/ITAM`). No Trial 0/1 runner process may access the
operator's live checkout, or any other filesystem location containing the seal. The runner's own
frozen CORE checkout is separate and does not contain the seal.

**Filesystem layer (load-bearing).** The runner's frozen CORE checkout is a **fresh `git clone`**
of `https://github.com/DariuszNewecki/CORE.git` at the relevant pin — never a copy, bind-mount, or
worktree of the operator's local `/opt/dev/CORE`. The frozen Phase 1 **subject** checkout
(`c4d9fdf9...`) is, symmetrically, a fresh clone from GitHub — never the operator's pre-existing
local worktree at `work/external-validation/core-phase1-frozen` (confirmed to exist on this
machine; operator-side reference material only, never exposed to the runner substrate). A process
with no bind-mount, no shared filesystem namespace, and no path string pointing at
`/opt/dev/CORE/work` or `/opt/dev/CORE/ITAM` structurally cannot read what was never mounted into
its namespace.

**Network boundary — restricted, not absent (Governor ruling, 2026-09-10; replaces the prior
pass's "no live GitHub egress at all" framing with an explicit, checkable deny-list):**

- **Provisioning happens before isolation is sealed.** Both pinned checkouts (runner and subject)
  are fetched *before* the network policy below takes effect — not during the trial, under an
  assumed-safe exception.
- **No GitHub credentials are ever provisioned into the runner's environment.**
- Explicitly **denied**, by hostname, after isolation is sealed: `github.com`, `api.github.com`,
  `raw.githubusercontent.com`, `codeload.github.com`, `objects.githubusercontent.com`, and every
  other `*.githubusercontent.com` endpoint.
- **No general HTTP/HTTPS proxy** — the substrate does not run an open forward proxy the runner
  could route arbitrary traffic through.
- **Only the exact DNS and LLM API destinations the pinned runner's frozen configuration requires**
  are reachable — an explicit allowlist, not a broad "LLM traffic is fine" carve-out.
- **Destination enforcement does not rely solely on mutable/shared CDN IP assumptions** — hostname/
  SNI-based filtering (the VM-302 spec's own CONNECT/SNI pattern, §4 of that document, transfers
  directly) rather than a static IP allowlist that a CDN could silently reassign out from under the
  policy.
- **No model-provider server-side URL retrieval, browsing, search, connectors, or file-fetch tools**
  — confirmed structurally absent from the frozen runner's own code (§10), and additionally denied
  at the network layer as defense in depth, in case a future configuration change ever tried to
  request one.

**Credential layer (defense in depth).** No credentials granting access to the operator's account,
disk, or any store holding the seal are provisioned into the runner's environment.

**Candidate substrate — the existing coldroom VM.** `scripts/coldroom-prep.sh` (last touched
`fce5c064`, within the Trial 1 runner's own included range) already provisions a fresh Ubuntu 24.04
host/container with Docker, Postgres 16, Poetry, and `qemu-guest-agent`;
`.specs/planning/CORE-Cleanroom-Rebuild-Runbook.md` documents a working, previously-exercised
procedure (2026-07-12 execution log entry) for standing up exactly this kind of host from a fresh
clone and verifying it end-to-end. A fresh VM/LXC container has its own disk and its own network
namespace — no filesystem path to `/opt/dev/CORE` exists on it at all, satisfying
runner-inaccessibility structurally, not by discipline alone. Seal retrievability (§7/§8) is
entirely independent of this substrate — it is a property of where the published attestation
lives, never the coldroom VM — so the two D9 properties are satisfied by non-overlapping controls,
not by one implying the other.

---

## 12. Scoring separation and retrieval independence — two distinct properties

The prior pass of this document conflated these under one "trust boundaries" table, including a
now-withdrawn claim that a different Claude process/session was "the practical substitute" for
D9's "someone other than its author" requirement. That claim is removed, not reworded, because a
different session run by the same operator, on the same disk, under the same account, establishes
neither property on its own. The two properties, stated separately:

**Retrieval independence.** Another principal — not the seal's author, not dependent on the
author's local disk or account session — must be able to retrieve and independently verify the
sealed artifact. This is what §7's public tracked attestation is *for*: anyone with access to
public GitHub history can clone the repository, extract the artifact, recompute its SHA-256, and
compare it to the manifest, without asking the operator for anything and without trusting any
claim the operator makes about it. A same-operator, different-session evaluation step does **not**
establish this property — it still depends on the same one disk and the same one account
throughout. Retrieval independence is a property of *where the artifact lives and how it can be
fetched*, not of *which process later reads it*.

**Scoring separation.** Scoring occurs after the runner stops, outside the runner, using frozen
scoring rules and reproducible evidence:

1. The runner's blackboard database (isolated, disposable — same pattern as Unit D/E's
   `db_provisioning.py`, never the operator's `core`/`core_test`) is exported to a flat evidence
   file after the trial terminates.
2. The exported evidence is copied out of the coldroom VM; the runner's participation ends there.
3. Scoring — comparing the runner's recovered findings against the retrieved, independently-
   verified sealed artifact — happens in a separate process, using the frozen scoring rules from
   the frozen procedure (§2 step 4), never rules improvised at scoring time.
4. The runner never receives the seal, never receives a "you got N/8" signal, and never re-runs
   conditioned on the score (§9's no-retry rule).

**A separate process supports scoring separation. It does not, by itself, establish retrieval
independence.** Both properties are required; neither substitutes for the other. This document
satisfies retrieval independence through §7's custody decision and scoring separation through the
procedure above — deliberately two different mechanisms, not one mechanism asked to do both jobs.

---

## 13. Trust boundaries

| Role | Trusted for | Not trusted for / structurally denied |
|---|---|---|
| **Operator** (Dariusz) | Controlling the physical/VM infrastructure; starting/stopping the runner; declaring the run closed. | Being the sole custodian of the seal after publication — resolved by §7/§8's retrieval independence, not by operator discipline. |
| **Runner** (frozen CORE, launched by the deterministic operator harness inside the isolated substrate — never Claude Code, per §9) | Executing deterministically; honestly reporting its own findings and refusals; producing a blackboard-reconstructable trail. | Reading the seal, the subject's later state, or anything that would let it "recognize" rather than "recover" the answer key — denied structurally (§10, §11), not by instruction. |
| **Blind procedure author** (a fresh stateless session, per the companion brief — never this session or any session sharing CORE's project memory) | Writing both trial procedures from the brief's allowed sources only. | Any access to the seal, to project memory, to the repository beyond what the brief hands it, or to prior Unit D/E findings as investigative hints. |
| **Evaluator** (whoever performs §12's scoring step) | Comparing exported evidence against the independently-retrieved seal; computing the recall figure; reporting it as a number before interpretation. | Scoring before the runner terminates; using anything other than the frozen scoring rules; being treated as sufficient for retrieval independence on its own (§12). |
| **Governor** | Final sign-off; the only party who can sign a threshold claim (ADR-159 D2); deciding D3 invalidation arguments; the decisions already made in this ruling (custody mechanism, runner boundary, network policy). | Nothing here removes any existing Governor authority. |

---

## 14. Trial 0 isolated checkout/process design

Consolidating §9–§12 into one procedure:

1. **Provision** a fresh coldroom VM/LXC per `CORE-Cleanroom-Rebuild-Runbook.md` Phase 1 steps
   1–3, then a **fresh clone** — not a copy — of `DariuszNewecki/CORE` at the relevant pin.
2. **Provision the subject** as a second fresh clone, before isolation is sealed (§11).
3. **Seal the network boundary** (§11) — deny-list applied, allowlist restricted to the exact LLM
   endpoints the frozen configuration requires.
4. **Provision a disposable database** — unique name, ephemeral container, never the shared
   `core`/`core_test` instance.
5. **Pre-run hash.** Record sha256/`git write-tree` over the runner checkout's tree, the subject
   checkout's tree, and the disposable database's freshly-loaded-schema state.
6. **Run** the frozen procedure (§2 step 4's output — not authored by this document or this
   session) via the deterministic operator harness (§9) — no Claude Code wrapper.
7. **Post-run hash.** Recompute the same three hashes; unexpected drift is evidence, not noise.
8. **Sanitized evidence capture.** Export the blackboard contents and any captured process
   stdout/stderr through the same `redact_secrets`/`scan_for_secrets` discipline Unit D/E already
   established.
9. **Deterministic failure behavior; no automatic retry** inside a single trial invocation.
10. **The frozen runner is never patched during a trial** (D5's own instruction). Any correction
    happens afterward, on `main`, never by editing the tagged commit, never by silently re-running
    the same trial claim against a patched runner without fresh re-certification.
11. **Teardown.** Remove exactly the disposable VM/container and disposable database; the checkouts
    inside it were never the operator's canonical copies.

**D3 invalidation, applied to Trial 0's own apparatus:** a finding about the apparatus (isolation
held, but recall was low; isolation held, but a dependency was unexpectedly missing) is backlog per
D3 unless argued in writing to show the apparatus itself produced wrong evidence — proof that
network isolation was not actually enforced, or that the runner had a readable path to the seal.
Everything else, including "the recall figure was lower than hoped" (explicitly not a threshold per
D5), is recorded and carried forward, not treated as a blocker.

---

## 15. Acceptance criteria

**D9 acceptance (before Trial 0 may run — note the ordering from §2: this follows blind procedure
authorship, it does not precede it):**

- [ ] Both semantic procedures (Trial 0 and Trial 1) are frozen (§2 steps 2–4).
- [ ] The non-printing automated scan has run against the sealed artifact and passed.
- [ ] The tracked public attestation (artifact + SHA-256 manifest) is published under
  `.specs/attestations/`.
- [ ] The retrieval/re-verification step (§8) has been exercised at least once independent of the
  operator's own working copy.
- [ ] The runner-inaccessibility mechanism (§11) is implemented and independently demonstrated —
  an attempted read of the seal's known path from inside the isolated substrate fails, and an
  attempted egress to a denied host is blocked — without ever exposing the seal's content during
  the demonstration.
- [ ] **§6 finding 6 (memory-substrate leakage) is resolved, not merely acknowledged.** Confirmed
  present and confirmed unresolved as of this document. No Claude-Code-driven process with access
  to CORE's current project memory may be the runner (§9 already forecloses Claude Code as the
  runner entirely, which resolves this for the runner role specifically — but the same exclusion
  must hold for blind procedure authorship too; the companion brief's authoring-environment
  requirements enforce this).

**Trial 0 start acceptance:**

- [ ] D9 acceptance (above) is fully satisfied.
- [ ] The coldroom VM (or equivalent substrate) is freshly provisioned per §14 steps 1–4.
- [ ] Pre-run hashes are recorded (§14 step 5).
- [ ] The frozen Trial 0 procedure (§2 step 4's output) exists and has been reviewed.
- [ ] Network/filesystem/credential controls are verified active before the procedure begins.

---

## 16. Explicit non-claims

- This document does not implement D9. No custody mechanism has been created; no VM has been
  provisioned; no isolation control has been applied; the seal has not been published, copied,
  hashed, or scanned.
- This document does not run Trial 0 or Trial 1, author either trial's semantic procedure, invoke
  a fresh session, or execute another external-target scenario.
- This document does not change any production behavior, `.intent/` semantics (beyond the single
  authorized namespace-manifest registration for this file and the companion brief), schema, or
  configuration.
- The blind-author brief this unit produces (`CORE-Autonomy-Trials-Blind-Author-Brief.md`) is an
  input packet only — it is not invoked, and neither trial procedure is written, in this unit.

---

## 17. Incident disclosure

While preparing the *prior* pass of this document, this session accidentally read approximately
the first two rows' worth of content (claim text and evidence paths) from
`work/external-validation/seal_manifest.py`, believing it to be pure sealing tooling. It is not —
the sealing/hashing logic and the sealed row data live in the same file. **No content from those
rows is reproduced anywhere in this document, in ADR-159's Notes, in project memory, or in any
unit's final report.**

Separately, while writing the prior pass, this session found that several project-memory files
predating D9 (written 2026-08-27 through 2026-08-29, before the sealing regime existed) already
contain real Phase 1 benchmark content — row identifiers, claim summaries, and in at least one case
apparent directly-quoted document text. This is **confirmed content, not a hypothetical risk**, and
is materially larger than the single accidental read above: it means any Claude-Code-driven process
in this project directory, including a hypothetical future trial runner if one were ever
Claude-Code-driven, would auto-load this content regardless of any checkout-level isolation.

**Consequence, stated once and acted on throughout this document rather than merely noted:** this
session, and every session that loads CORE's current project memory, is excluded from serving as
blind procedure author or trial runner. §9 makes the runner frozen CORE itself under a
non-Claude-Code operator harness — which independently satisfies this exclusion for the runner
role, since a deterministic harness invoking a frozen binary/checkout does not load this project's
Claude Code memory at all. The companion blind-author brief's authoring-environment requirements
(fresh stateless session, no project memory, no connectors, no repository/web access) satisfy it
for the authorship role.

This determination — whether this session or its transcript should be treated as still eligible for
any other role touching Trial 0/Trial 1 — remains the Governor's, not this session's own to decide
beyond what is stated above.
