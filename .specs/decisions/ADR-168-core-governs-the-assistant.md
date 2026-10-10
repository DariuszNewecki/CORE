---
kind: adr
id: ADR-168
title: 'ADR-168 — CORE governs the assistant: law, facts and verdict for every AI producer'
status: accepted
---

<!-- path: .specs/decisions/ADR-168-core-governs-the-assistant.md -->

# ADR-168 — CORE governs the assistant

**Date:** 2026-10-04 (revision 3, after two external reviews); accepted 2026-10-06
**Status:** Accepted 2026-10-06 by the governor, with the third review's D5 scope correction
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-10-04)

**Grounds:**
- Northstar "CORE — What It Does": the problem statement; "CORE governs the AI"; "never produce work it cannot defend".
- Charter §6: law precedes machinery.
- ADR-159: CORE as polyvalent governance machinery.
- ADR-084 D6/D7: interface symmetry and open-core completeness.
- ADR-110: exposure is a trust tier on the complete API.
- ADR-087: the OEM API contract.
- ADR-146: the consumer/operator split.

**Relates:** #942 (governor stamp identity), #944; ADR-169 (CORE knows its own state).

**Amends (on governor decision, see D6):** Northstar "CORE — What It Does".

## Governor decision required

**Does governing external AI assistants become the immediate proving priority, ahead of further investment on the autonomy axis?**

D1–D5 are architecture and follow from existing principles. D6 is the strategy amendment, and only the governor can make it. If the answer is no, D1–D4 can still stand, and D5 and D6 are withdrawn.

## Context

The founding problem, in the governor's words: *coding with AI without the misery of drift and hallucination.*

The Northstar names that problem. It answers it by placing the AI inside CORE: an untrusted worker on CORE's own production line, climbing an autonomy ladder (A1–A5) toward an unattended loop. CORE has built much of that.

The Northstar's deeper invariant does not depend on where the AI runs: *CORE governs AI output and does not trust the producer.* Its location assumption ("the AI is a component inside CORE") leaves out the AI most people code with: an assistant **outside** CORE (Claude Code, Cursor, Copilot), in conversation with a human. That is also the AI that does most of the work on CORE itself, and today it is governed by `CLAUDE.md` prose, not by CORE.

Evidence from this repository:

- Session memory is a list of corrections to that assistant: "grep the CLI before describing a capability", "never stamp governor authority", "verify docstrings", "count from source".
- On 2026-10-04 the assistant deleted a module without checking `.intent/`. CORE's phantom-capability gate caught it, but only in CI, after the push. CORE had the law and the check; the producer was not required to consult them first.
- The open-product persona (core-platform, "Indie SaaS Developer") already uses an AI assistant. The product scope guard reads: *"Not a code generator. It governs one; the generator is swappable."*

What is missing is a bridge: one that makes the producer take in CORE's facts *before* acting and CORE's verdict *before* the change stands.

## Decisions

### D1 — External assistants are governed producers

Any AI that produces changes to a governed repository is a producer under CORE's law, whether it is CORE's internal worker or an external assistant. **CORE provides the governance boundary every producer must satisfy. It is not the producer.** A producer may write bytes directly; what must pass through CORE is the boundary of facts, verdict and proposal.

This makes the Northstar's invariant explicit regardless of where the AI runs: the AI is never trusted. The thesis of ADR-159 (CORE governs an unfamiliar target without redesigning itself) applies unchanged. An external assistant is one more producer.

### D2 — The first assistant surface: three capabilities

The first assistant-facing surface consists of three capabilities:

| Capability | What it gives the assistant | What it reduces |
|---|---|---|
| **Law & facts** | Grounded answers with provenance, from three classes: **law** (authoritative `.intent/` content); **repository facts** (code, config, symbols, API routes and commands, observed deterministically); **decision history** (accepted ADRs and `.specs/` evidence) | Unsupported factual claims |
| **Verdict** | A deterministic audit of a proposed change (diff or working tree) before commit: blocking findings, each with the rule that fired | Governed rule violations and artifact drift |
| **Proposal** | The assistant may submit a change as a proposal. It may never approve one | Authority leakage |

**Epistemic contract for law & facts:**
- Every answer names its class and its source.
- The service never turns uncertainty into a fact. Unknown is returned as unknown.
- Inference about intent is out of scope. "Probably intended by the governor" is never an answer.
- The service returns facts with provenance, not "context".

No further assistant-facing capability is introduced until evidence from the first adopter (D4) shows a need for it.

**Transport and exposure:**
- The surface is delivered as an MCP server over the OEM API (ADR-087).
- It may expose only operations in the API's `user-facing` exposure tier (ADR-110, enforced through `ROUTER_EXPOSURE`), or operations separately promoted into that tier.
- It MUST NOT tunnel `governor-only` routes, or in-process `core-admin` operator capabilities (ADR-146 D3), to an assistant.
- Every assistant gets the same tools through the same public contract. There is no first-party-only path (ADR-084 D6).

### D3 — No conversational authority

- No utterance in a conversation is a governance act. A chat "yes" is not an approval, a waiver or a ruling.
- Approvals, waivers and rulings remain structured governor acts.
- The assistant may draft them, explain them and give the governor the exact command.
- Submitting a proposal is a producer act, and it is allowed.

**Until #942 is resolved, the assistant surface MUST expose no operation whose result is represented as authenticated governor authority.** This is fail-closed and testable. No MCP tool may write `principal.governor`, or anything recorded as a governor approval, waiver or ruling.

### D4 — CORE's own development adopts it first

The first adopter of D2 is this repository, worked on by Claude Code. In order:

1. **First-adopter integration: a pre-commit verdict.** A Claude Code hook in this repo runs the blocking offline audit (`core-admin code audit --offline --severity=block`) before any commit the assistant makes. This proves the following and nothing more: *the normal Claude Code commit path is governed pre-commit and refuses a planted blocking violation.* The hook is producer-side configuration, so it is ergonomics and evidence, not an enforcement boundary.
2. **Bypass-resistant enforcement.** A repository-controlled gate, outside the producer's authority, prevents a change carrying a blocking violation from landing on the protected branch. Only this step supports the claim that *a producer cannot land a change around CORE*. For CORE's current GitHub repository the expected implementation is the existing offline audit as a required CI status, plus branch protection on `main`.
3. **The MCP server**, starting with law & facts and verdict.
4. **Classify `CLAUDE.md` deliberately.** When an instruction's violation would be governed architectural, authority or integrity drift, and deterministic enforcement is practical, the instruction does not stay prose-only. Each instruction is classified as:
   - **constitutional** → an `.intent/` rule;
   - **ordinary engineering quality** → tests, linter or tool config;
   - **human collaboration** → stays in `CLAUDE.md`.

   `.intent/` does not become "everything we can test".

### D5 — Priority follows the surface (conditional on D6)

**For discretionary capability development, priority goes to work that strengthens law & facts, verdict or proposal for external producers. Foundational correctness, security, constitutional integrity and operational reliability remain prerequisite work.**

(Wording adopted at acceptance from the third review. The earlier "ranked by one question" was too absolute: foundational work should not have to be argued into one of the three surfaces to qualify.)

Within discretionary work:

- **First:**
  - D4;
  - cross-artifact consistency checks (the class that caught the phantom capability);
  - self-model accuracy;
  - verdict determinism.
- **Continues, not first:** the autonomy ladder (ADR-159, A1–A5). This ADR retires nothing.
- **Maintenance only until D4 step 3 lands:** in-house AI code generation (the test-generation loop and LLM-written remediations).
- **Product direction retired:** CORE will not build a first-party conversational agent. The conversation belongs to whichever assistant the user already has. Whether `src/will/agents/conversational/` is deleted is **not** decided here. Deletion follows only from a separate mechanical dead-code proof: no registration, no callers, no declared capability or prompt artifact, and no test or runtime dependency.

### D6 — Northstar amendment (proposed text; the governor authors on acceptance)

Insert in "CORE — What It Does", after "What CORE Is Not":

> ## The Assistant Outside
>
> Most AI that produces work does not run inside CORE. It runs beside the
> human, as a coding assistant in conversation. CORE governs that AI the same
> way it governs its own workers: it is never trusted.
>
> CORE gives every assistant grounded facts with their provenance (so it need
> not guess), a verdict on its change before the change stands (so governed
> violations do not land), and a way to propose (so it never decides). The
> conversation belongs to the assistant. Authority never does.
>
> CORE's own development is the first place this holds.

In "Where CORE Is Going", add: *the assistant surface is proven on CORE itself first; the autonomy axis is climbed after that, not instead of it.*

## Consequences

- CORE becomes more useful for the persona it already targets, with less infrastructure. The verdict runs offline today.
- If D6 is accepted, the daemon's generation loop loses priority, and planned work there waits.
- `CLAUDE.md` is classified over time. Instructions that matter constitutionally become law, and prose drift becomes rule drift that CORE can sense.
- New machinery (the MCP server) is introduced after this law, per Charter §6.

## Explicitly not decided here

- MCP tool names, schemas or packaging. That is a follow-up implementation decision.
- Commercial surfaces. Everything in D2 is open (ADR-084 D7).
- Changes to ADR-159 trial design or schedule. If D5 affects them, that is a separate ruling.
- Deletion of any specific module (see D5).

## Acceptance checks

1. **D4.1:** with Claude Code in this repo, the hook refuses a commit carrying a planted blocking violation and allows the clean one.
2. **D4.2:** a direct push of a change carrying a planted blocking violation cannot land on `main`, whatever producer or shell makes it.
3. **D3:** no MCP operation can create or change any record whose authority semantics represent an authenticated governor act. `principal.governor` is the current concrete case. A test checks every current representation of governor authority over the tool registry.

## Review record

One external review (2026-10-04). Revision 2 adopts its findings:
- the "closed set" is removed (D2);
- exposure is grounded in ADR-110 tiers rather than a superseded "API ⊂ CLI" shorthand;
- the #942 condition is fail-closed (D3);
- the hook's proof is narrowed and the repository gate is added (D4.1/D4.2);
- the `CLAUDE.md` classification rule is narrowed (D4.4);
- deletion is decoupled from this ADR (D5);
- the epistemic contract and provenance are added (D2);
- the outcome labels are made precise;
- the governor decision is surfaced explicitly.

Second review (2026-10-04) judged revision 2 sound and governor-ready, and voted yes on the decision. Revision 3 adopts its three corrections:
- D1 now reads "the governance boundary every producer must satisfy";
- D4.2 now states the property, with branch protection named as the current implementation;
- the D3 acceptance check now tests authority semantics, not one field name.

## Experiment evidence (2026-10-06, appended; not a revision)

The governor chose on 2026-10-04 to run D4.1 and D4.2 as an experiment before deciding D5/D6.
Data from `var/experiments/adr168/verdicts.jsonl`, 2026-10-04 11:40Z to 2026-10-06 15:04Z:

- **73 assistant commit attempts. 69 allowed, 4 refused.**
  - 2 refusals were deliberate acceptance plants: the pipe test, and the planted `asyncio.run`
    (`async.no_manual_loop_run`).
  - **2 were real catches** that would otherwise have been committed:
    - 2026-10-04 16:47Z: 8 blocking findings on a `src/api/serve.py` change
      (`governance.logic_mutation.governed`, `governance.mutation_surface.filehandler_required`,
      `linkage.assign_ids`, `linkage.no_orphan_ids`);
    - 2026-10-04 19:00Z: a `.intent/` change that left a rule unmapped
      (`governance.remediation.all_rules_mapped`).
- **Cost:** median 109 s per commit (p90 117 s, max 120 s), about 133 minutes over 73 commits.
  This is the full offline audit on every commit. A verdict an assistant consults before
  acting (D2) has to be much faster to be used willingly. That is an input to D4.3, not a reason
  against D4.1.
- **Acceptance check 1 (D4.1): met.** The plant was refused and the clean commit allowed
  (2026-10-04).
- **Acceptance check 2 (D4.2): met.** `main` is protected, with 8 required checks enforced for
  admins too. A direct push is refused (GH006, 2026-10-04), and every change since has landed by
  develop, green CI, then fast-forward.
- **Acceptance check 3 (D3): not yet testable.** No MCP surface exists.
- **Work done since 2026-10-04 that already follows the D5 ranking:** verdict trustworthiness
  (#952 substrate-wide verdicts; ADR-169 law relation; #956 NOT EVALUATED rendering), and
  self-model accuracy (#957 floor taxonomy). Releases 2.12.0 and 2.12.1 were verified by
  cold-room installs on Ubuntu 26.04.

The decision the ADR asks for is unchanged: **does governing external AI assistants become the
immediate proving priority (D5, D6)?**

## Acceptance (2026-10-06)

The governor accepted this ADR on 2026-10-06, with D1–D4 and D6 as written and D5 in the scoped
wording above.

**Third external review (2026-10-06), after the experiment evidence above.** It judged the
direction evidence-backed, citing the two real catches and acceptance checks 1 and 2 as met. It
voted yes on D6 and recommended D1–D4 essentially as written. It made one substantive
correction, D5's scope, which was adopted at acceptance rather than through a further revision
(no review loop). It added one design input for D4.3, recorded here and not decided here: keep
**fast producer feedback** (seconds, for the assistant) distinct from **authoritative repository
enforcement** (the full audit, which may stay slower), and never weaken the latter to speed up
the former.

**Drafter's note on that input, for D4.3:** a fast verdict must never present itself as the
authoritative one. If it evaluates a subset of rules, it says so in the same honest terms the
audit uses (`NOT EVALUATED`, DEGRADED; #952, #956), so it cannot recreate the false certainty
those fixes removed.

**Next proof (D4.3):** Claude, working on CORE, asks CORE a question about this repository and
gets a provenance-backed answer; submits a proposed change and gets a deterministic verdict fast
enough to use interactively; and remains unable to exercise governor authority (acceptance
check 3).

## Amendment 2026-10-06: D2 transport (governor ruling, option B)

The assistant surface runs **local first**: an MCP server started by the assistant, calling the
same in-process functions as the offline audit, with no services required. CLI, MCP and later API
routes are thin faces over **one shared implementation**, and a parity test asserts that they give
identical answers. This replaces "delivered as an MCP server over the OEM API" as the *first*
delivery; API routes for the same operations follow when a server deployment needs them.

Unchanged: every assistant gets the same operations (ADR-084 D6); the surface exposes only an
explicit allowlist of read and verdict operations; nothing it exposes can write governor authority
(D3).

Grounds: the recon in `var/reports/adr168-d43-design-20261006.md` found that the API requires
PostgreSQL and Qdrant to start, while the newcomer path is `pip install` only.

## Amendment 2026-10-10: the Proposal capability — one way in for every producer (governor ruling)

**Why.** The governor, 2026-10-10: CORE never writes code; a model does — CORE's internal one or the
assistant beside the governor. The two routes differ only in **who owns the problem**. CORE's own
fixes enter as proposals and leave a full chain (problem → code → verdict → approval → consequence);
the assistant's commits leave only a commit. D2's third capability, **Proposal**, closes that gap and
was not built. This amendment rules how it is built. Evidence: `var/reports/producer-proposal-recon-20261010.md`
(recon, plus one external review verified against the code).

**A1 — The allowlist gains exactly one write.** The 2026-10-06 amendment's "explicit allowlist of read
and verdict operations" becomes: read and verdict operations, **plus submit-a-proposal**. Submit may
create a pending proposal. It never approves, rejects or executes one, and never sets an approval
authority or a status other than pending. D3 is unchanged.

**A2 — One way in.** A code change from any producer — CORE's internal worker or an external assistant —
enters as a proposal carrying: its **anchor** (a finding, or an issue or ADR reference), its **problem
owner** (the governor, or CORE for a finding CORE raised), its **producer** (which model or agent
wrote the bytes), the exact patch, CORE's verdict, the approval, and the consequence. The anchor is
context, never authority. Authority is the approval.

**A3 — CORE chooses the checks.** For a change not born from a finding, CORE does not check "the
finding cleared"; it runs the full blocking audit on the patched tree (as the commit gate does), ruff
and the tests for every touched and every new file. Every rule it could not evaluate is named. A
blocking finding refuses the submission. A patch's added, modified and deleted files are all part of
what is checked, applied and committed.

**A4 — Two checks, not one.** *Submission* checks the proposal is well-formed (at least one known
action, declared files within the blast bound, risk computed and failing closed). *Execution* checks it
is authorized. A proposal awaiting approval is a valid submission.

**A5 — Law keeps its own way in.** A patch touching governed text — `.intent/`, `.specs/`, `CLAUDE.md`,
`.claude/settings.json`, `.claude/hooks/` — is refused at submission. Governed text enters only under
ADR-170 (custody, ledger; the D0 chat stand-in belongs to that rehearsal alone).

**A6 — Attribution.** In the commit, the **producer is the git author** and the applying actor (CORE)
is the **committer**. The approval is recorded on the proposal and its consequence, not in git. This is
ADR-101 D1 applied: the bytes are the producer's.

**A7 — Approval is a governor act through CORE** (D3), not a chat answer. Low-risk changes may be
approved automatically only within the existing safe auto-approval envelope; this amendment widens
nothing there.

**Stated limits (not closed here):**
- Approval identity is unauthenticated in OSS mode until #942 / ADR-132 D10 closes.
- Validation runs the producer's code (tests, imports) before approval — ADR-132 R4, parked. A worktree
  separates files, not execution authority.
- A proposal applies only to the base it was validated on; an intervening commit requires
  revalidation and renewed approval (ADR-154 D2).
- Until the capability is built, the assistant keeps the present route: direct commits under the
  pre-commit verdict (D4.1) and protected `main` (D4.2).

**Acceptance check 4.** One real assistant change is submitted through the assistant surface,
checked by CORE, approved through the intended mechanism, committed with the producer as author,
and linked to its consequence record.
