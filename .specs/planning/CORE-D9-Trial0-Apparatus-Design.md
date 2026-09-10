---
kind: planning
title: CORE ADR-159 D9 Seal Custody and Trial 0 Apparatus Design
status: draft
---

# CORE ADR-159 D9 Seal Custody and Trial 0 Apparatus Design

**Status:** Draft — for Governor review. Nothing in this document has been implemented. No D9
mechanism, no Trial 0 run, no external-target execution, and no access to the sealed answer
material's content occurred while writing it.

**Scope:** design only, per ADR-159's own framing — "the run design for Trials 0 and 1 —
harness, isolation mechanics, output layout, procedure — is revisable mechanics and belongs in
`.specs/planning/`, not [the ADR]." This document does not alter ADR-159 D1–D9, does not
redefine T-A/T-B/T-C, and does not commit to an implementation. The next unit implements D9 only
after this document is reviewed.

---

## 1. ADR-159 threshold and claim boundaries (restated, not redefined)

Restated here only to ground the design that follows; ADR-159 remains canonical on divergence.

| Threshold | State of | Criteria (abridged — see ADR-159 D2) |
|---|---|---|
| **T-A** | the runner | #855 reconciled; CI green; G8 attested; commit frozen and tagged. **Reached** (2026-09-04). |
| **T-B** | the claim | Trial 1 (D6) succeeds against its six declared criteria, with honest, reconstructable evidence. **Not reached.** |
| **T-C** | sustained operation | controlled write experiment succeeds; recovery/rollback proven; then a sustained soak with no unauthorized writes, no lost proposals, no ambiguous lifecycle states. **Not reached.** |

**D3 containment rule:** a finding beyond a threshold's declared criteria is backlog unless it
invalidates the trial in progress, argued explicitly in writing. This document's own Trial 0
design inherits that rule directly (§12).

**D4 adaptation line:** acceptable adaptation (target `.intent/`, GRC catalogs, domain
profiles, configuration/resource bindings) versus thesis-negative adaptation (new `src/`
modules, new check/rule classes, target-specific runtime branches, schema changes). Both trials'
reports must quantify which category their own work fell into. Nothing in this apparatus design
proposes any thesis-negative adaptation.

**Units D and E** (2026-09-06 – 2026-09-10) are preliminary engineering evidence for the
mechanics a controlled write and its rollback require. They occurred before D9 and T-B and
receive no T-C or other threshold credit (2026-09-10 Note).

---

## 2. Exact pins

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

The Trial 1 runner is the last baseline containing the Governor-authorized external-target
safety package — including physical symlink-containment enforcement (`b57423dc` itself) — while
excluding the later Unit D/E execution scaffolding and write-path corrections. First excluded
commit: `c0694953`. See the commit ledger below for the full accounting.

---

## 3. Commit ledger: T-A → Trial 1 runner (`27160a0a` → `b57423dc`, inclusive)

Five commits, all included in the Trial 1 runner pin.

| Commit | Subject | Classification |
|---|---|---|
| `660834c6` | feat(external): fail closed on target binding | **Production** — new module `src/shared/infrastructure/external_target_binding.py`. **Test** — `tests/shared/infrastructure/test_external_target_binding.py`. **Documentation** — ADR-159 Notes (2026-09-05 ruling). |
| `cb47438a` | feat(cli): pre-bootstrap external-verify launcher | **Production** — `src/cli/admin_cli.py`, `src/cli/runtime_external_verify.py`. **Test** — `tests/cli/test_runtime_external_verify.py`. |
| `fce5c064` | fix(coldroom): install and enable qemu-guest-agent in template prep | **Infrastructure/ops**, unrelated to the external-target safety package — `scripts/coldroom-prep.sh` only. Interleaved chronologically; no fixture/policy/test impact. Relevant to §9's substrate choice (the coldroom VM template script). |
| `c7de61e5` | feat(external): Unit C neutral target fixture proves authority boundary | **Fixture/policy** — `tests/fixtures/external_target/{materialize.py, intent_overlay/*, template/*}` (the neutral target template, the ratified `safe_auto_approval_envelope`). **Test** — `test_authority.py`, `test_materialization.py`. **Documentation** — ADR-159 Notes (2026-09-06 ruling). |
| `b57423dc` | fix(actions): deny symlink target escapes **(runner pin)** | **Production** — `src/body/atomic/executor.py` (`_check_physical_containment`, a real security fix, not fixture-scoped). **Test** — `tests/body/atomic/test_executor_physical_containment.py` (new), plus fixture-adjacent updates to `_probe.py`/`test_authority.py`. |

**Net production surface in the Trial 1 runner, beyond T-A:** the external-target binding guard
(`external_target_binding.py`), the pre-bootstrap CLI launcher (`admin_cli.py` route,
`runtime_external_verify.py`), and the physical symlink-containment check in
`body/atomic/executor.py`. All three are the Governor-authorized external-target safety package
(Units A/B/C/C.1); none are target-specific adaptation under ADR-159 D4 — they are general
hardening of the sandbox/authority boundary, applicable regardless of which external target is
ever evaluated.

## 4. Commit ledger: excluded from the Trial 1 runner (`c0694953` → `f2c50dc6`, inclusive)

Eight commits, all excluded. First excluded commit: `c0694953`.

| Commit | Subject | Classification |
|---|---|---|
| `c0694953` | test(external): prove governed format mutation | **Fixture/test** — Unit D scaffold (`db_provisioning.py`, `unit_d_orchestrator.py`, `unit_d_child.py`, `test_unit_d_orchestrator.py`). No production changes. |
| `8569f02f` | feat(external): authorize fixture-local proposal_consumer_worker declaration | **Fixture/policy** — new fixture-owned worker declaration, fixture-local UUID, scoped to `package/example.py`. **Test** — `test_materialization.py` update. Verified accurate in ADR-159 Notes (2026-09-10, §5 below). |
| `d12254e5` | fix(external): Unit D scaffold calls Worker.start(), not run() | **Fixture/test** only — `unit_d_child.py` fix, `test_unit_d_child.py` new. |
| `bd2b336f` | feat(external): authorize claim.proposal's policy dependency in fixture overlay | **Fixture/policy** — byte-identical copy of CORE's own `rules/will/proposal_lifecycle` into the fixture overlay. **Test** — `test_materialization.py` update. Verified accurate in ADR-159 Notes (2026-09-10, §5 below). |
| `b4acb30d` | fix(body): Unit D formatter-runtime correction — resolve and run Ruff directly | **Production** — `src/body/self_healing/code_style_service.py`, `src/shared/utils/subprocess_utils.py` (new `run_direct_command` sanctuary helper; the Poetry-wrapped-false-success fix). **Test** — `test_format_sandbox_correction.py`, `test_subprocess_utils__run_direct_command.py`, `test_unit_d_orchestrator.py` update. |
| `4ddcaa32` | fix(body): Unit D final Ruff-runtime correction — check/fix phase too | **Production** — `src/body/self_healing/code_style_service.py` (second phase of the same fix). **Test** — `test_code_style_service__format_code.py`, `test_format_sandbox_correction.py` update. |
| `cca802ee` | test(external): Unit E scaffold — live post-propagation rollback qualification | **Fixture/test** only — `unit_e_orchestrator.py`, `unit_e_child.py`, both test files; `unit_d_child.py` gained an optional `goal` parameter (default-preserving). |
| `f2c50dc6` | fix(external): route Unit D/E disposable workdirs through var/tmp, not /tmp | **Fixture/test** only — `unit_d_orchestrator.py`, `unit_e_orchestrator.py`. |

**Material consequence for anyone reasoning about the Trial 1 runner's behavior:** the Trial 1
runner (`b57423dc`) does **not** include the `b4acb30d`/`4ddcaa32` fix — `fix.format`'s Ruff
invocation at that pin still goes through `run_poetry_command`, which silently reports success
against a target with no `pyproject.toml` (the defect Unit D diagnosed and fixed later, excluded
here). This is not expected to matter for Trial 1 itself (the ITAM Governance Library is a
governed-document corpus, not software `fix.format` would run against), but is recorded here so
the runner's own known characteristics are not rediscovered as a surprise mid-trial.

---

## 5. Verification of ADR-159 Notes entries 1 and 2 (worker authority, policy dependency)

Performed before those Notes were appended (2026-09-10), against the repository at the cited
commits:

- **Worker authority (`8569f02f`):** confirmed — `tests/fixtures/external_target/intent_overlay/workers/proposal_consumer_worker.yaml` scopes `mandate.scope.paths` to exactly `["package/example.py"]`; `permitted_tools` is exactly `crate.create`, `canary.validate`, `crate.apply`, `git.commit` — byte-identical to production's own `.intent/workers/proposal_consumer_worker.yaml` list; `identity.uuid` (`b7e25f7a-91f3-4f77-ba34-d29a871c3e0c`) is confirmed distinct from the production worker's UUID (`c1d2e3f4-a5b6-7890-cdef-123456789abc`); the diff touches only `tests/fixtures/external_target/` — no root `.intent/` change; `safe_auto_approval_envelope.yaml` is untouched by the commit.
- **Proposal-lifecycle policy dependency (`bd2b336f`):** confirmed — the fixture's `intent_overlay/rules/will/proposal_lifecycle.json` added by this commit is byte-identical to CORE's own `.intent/rules/will/proposal_lifecycle.json` (both then and now); `body/atomic/proposal_lifecycle_actions.py`'s `claim.proposal` registration declares `policies=["rules/will/proposal_lifecycle"]`, confirming the stated dependency is real and pre-existing, not invented for the fixture.

Both entries were appended to ADR-159's Notes as retrospective summaries, explicitly dated and
marked as such — see the ADR itself, not reproduced here.

---

## 6. D9 — seal threat model

**Asset:** the Phase 1 sealed benchmark, `work/external-validation/phase1-benchmark-SEALED.json`
(governor-signed, sealed 2026-08-27; run closed 2026-08-29) — eight rows scoring Trial-0/Trial-1
correctness against a pre-registered answer key. Its path is confirmed to exist; **its content
was not read, and is not reproduced, in this document** except by structural reference (pin
values, row count, field-shape) already stated in ADR-159 D5/D9 or independently confirmed as
schema-only, never data, in §9 below.

**What the threat model protects against:**

1. **Runner self-answering.** If the Trial 0 runner process (or Trial 1's, symmetrically) can
   read the seal's rows, its "recall" figure is definitionally worthless — it would be reading
   the answer key, not deriving findings. This is D9's core concern, stated directly in ADR-159:
   "a runner that can read its own answer key produces a recall figure of no evidential value."
2. **Single-point-of-failure custody.** The seal currently exists only on the operator's local
   disk, under a `.gitignore`d path (`work/*`, line 88). A disk failure, an accidental `rm`, or
   simply nobody else being able to check the seal's own claims makes the sealed artifact "a
   claim about evidence," not evidence (D9's own framing) — indistinguishable from an unrecorded
   result.
3. **Retroactive tampering.** If the seal can be edited after Trial 0/1 run, a disappointing
   recall figure could be quietly revised. `seal_manifest.py`'s own sha256-over-canonical-bytes
   pattern (confirmed to exist by structural reference — see §9) is the existing mitigation; D9
   requires that mitigation be independently checkable, not merely asserted.
4. **Operator-as-single-witness.** The Governor is both the seal's author and (in a solo-dev
   project) the only available evaluator. D9's "retrievable... by someone other than its author"
   property cannot, in this project's actual staffing, mean a literal second human. §11 states
   the practical substitute this design relies on and flags it as a real, disclosed limitation
   rather than pretending it away.
5. **Incidental leakage via tooling.** This unit's own session accidentally read part of the
   seal's content while inspecting what it believed was pure sealing *tooling* (`seal_manifest.py`
   embeds both the sealing logic and the row data in one file — see §14's incident note). This is
   itself a threat-model finding: any future design that treats "the sealing script" and "the
   sealed data" as one artifact invites exactly this mistake. §9's design separates them.
6. **Memory-substrate leakage (discovered while writing this document, unresolved by any control
   below).** This project's Claude Code auto-memory system persists project memory in files
   outside the repository, auto-loaded into every session's context by the harness itself,
   independent of the CORE checkout's own filesystem/network/credential isolation. Several memory
   files predating D9 (written before the sealing regime existed) already contain Phase 1
   benchmark content. §9's filesystem/network isolation of the CORE checkout — cloning fresh from
   GitHub, denying paths to `work/`/`ITAM` — does **nothing** to prevent a Claude-Code-driven
   runner from separately auto-loading this pre-existing memory store, because the memory
   substrate is a property of the harness/session, not of the repository checkout the other
   controls govern. **This is a real, currently unmitigated gap, not a hypothetical one** —
   confirmed content, not merely a theoretical risk. If any future Trial 0/Trial 1 runner is
   itself a Claude Code session (as this design otherwise assumes it may be, per §9.4's
   application-layer controls), its memory directory must be fresh/scoped/absent, exactly as
   rigorously as its filesystem and network access are — this document does not yet specify how,
   and no control elsewhere in this document addresses it. Flagged as an open item in §12's
   acceptance criteria and §14's non-claims, not resolved here.

---

## 7. Where the seal may be retained

D9 states three satisfying options without preferring one: commit the sealed JSON, publish a
hash of it, or hold it in a governed store. Evaluated here, not decided:

| Option | Retrievability | Runner-inaccessibility | Cost/risk |
|---|---|---|---|
| **Commit the sealed JSON to a repository the runner cannot reach** (e.g. a private tracking repo distinct from `DariuszNewecki/CORE`, or a new orphan branch/`refs/` namespace never checked out by the runner's clone) | High — anyone with repo access can fetch and verify the committed bytes against the recorded hash. | High, **if** the runner's own checkout is a fresh clone of `DariuszNewecki/CORE`'s `main` history only (never fetches the separate repo/ref) — see §9. | Low engineering cost. Requires a second repo or an unusual ref the runner's clone step must be documented to never touch — a discipline requirement, not a technical guarantee, unless enforced by network policy too (§10). |
| **Publish only a hash** of the existing sealed JSON (e.g. in this ADR's Notes, or a `.specs/attestations/` record), leaving the JSON itself wherever it currently lives or moving it to a governed store outside the repo entirely | Retrievability is then a property of the *hash*, not the file — anyone can confirm a *later-produced* copy matches what was sealed, but cannot *retrieve the content* from the hash alone. Satisfies "integrity-checkable"; only partially satisfies "retrievable" (D9 requires the artifact retrievable, not merely verifiable once already possessed). | Trivially high — nothing about the runner's environment changes; the seal's actual bytes never enter any repo. | Cheapest option, but weakest on retrievability alone — needs pairing with an actual custody location (this row is not self-sufficient; it composes with one of the other two). |
| **Hold it in a governed store** (e.g. `.specs/attestations/` if it is judged appropriate to publish the artifact itself there, given `.specs/attestations/` already holds prior sealed reports such as `e15-coldroom-3cbe0be0-20260726.md`) | High — same tree everyone already reads for other attestations. | Same conditional as row 1 — depends entirely on what the runner's checkout includes. | If placed inside `CORE`'s own tree, the runner's frozen clone of `main` **would** include it unless the seal is added only to a ref/tag the runner's clone step is documented to exclude, or added to `main` only *after* the runner tag is already cut (order-dependent — D9 already requires the seal exist "before Trial 0 runs," which this option can still satisfy if sealed after `27160a0a` was tagged but the runner's clone step pins to the tag, not `main`'s tip). |

None of these is selected here. §12 states the smallest remaining Governor decision.

---

## 8. Retrievability and integrity-check mechanism (mechanism-agnostic)

Whichever custody option is chosen, the mechanism must provide, independent of this design:

1. A **content hash** (sha256, matching `seal_manifest.py`'s existing pattern by structural
   reference) computed over the sealed artifact's canonical bytes, recorded somewhere durable and
   reachable by someone other than the operator's live working tree alone — e.g. in this ADR's
   Notes, or a `.specs/attestations/` record, once a location is chosen (§12).
2. A **retrieval path** — a location from which the artifact's bytes can actually be fetched,
   not merely a hash compared against a copy someone already has.
3. A **re-verification step** anyone (not just the operator) can run: fetch the artifact from the
   retrieval path, hash it, compare to the recorded hash. This is the same class of check
   `git worktree`/`git fsck` integrity relies on — no new subsystem, per D9's own instruction
   that the mechanism is "a planning decision, not a constitutional one."

---

## 9. Runner-inaccessibility mechanism

**Hard isolation constraint (restated from the brief):** the sealed material resides in a
gitignored path inside the operator's live CORE working tree (`/opt/dev/CORE/work/`, plus the
`ITAM` symlink at `/opt/dev/CORE/ITAM` → `/mnt/vector_db/YPTO/ITAM`). No Trial 0 runner process
may access the operator's live checkout, or any other filesystem location containing the seal.
The runner's own frozen CORE checkout is separate and does not contain the seal.

**Design — two independent layers, mirroring the existing VM-302 blind-author isolation spec's
own two-layer pattern (OS/network layer as load-bearing, application layer as defense in depth;
`work/external-validation/DRAFT-vm302-isolation-specification.md`, confirmed to exist, read in
full for this design — it concerns the *blind catalog-author* role, not Trial 0, but its
mechanics transfer directly):**

1. **Filesystem layer (load-bearing).** The runner's frozen CORE checkout is a **fresh `git
   clone`** of `https://github.com/DariuszNewecki/CORE.git` at the tag
   `autonomy-experiment-ready-2026-09-04`/commit `27160a0a...` — never a copy, bind-mount, or
   worktree of the operator's local `/opt/dev/CORE`. The frozen Phase 1 **subject** checkout
   (`c4d9fdf9...`) is, symmetrically, a fresh clone from GitHub at that SHA — never the operator's
   pre-existing local worktree at `work/external-validation/core-phase1-frozen` (confirmed to
   exist on this machine; it is operator-side reference material only and must not be exposed to
   the runner substrate). A process with no bind-mount, no shared filesystem namespace, and no
   path string pointing at `/opt/dev/CORE/work` or `/opt/dev/CORE/ITAM` structurally cannot read
   what was never mounted into its namespace — the same guarantee §2 of the VM-302 spec states for
   the blind author ("No sibling copy... anywhere on this box... enforced by mount topology
   instead of instruction").
2. **Network layer (load-bearing).** Default-deny egress (the VM-302 spec's `nftables`
   single-`inet`-table pattern, IPv4+IPv6, confirmed workable there), permitting only what the
   runner genuinely needs: DNS to the substrate's own trusted resolver, and whatever LLM/API
   endpoints CORE's own cognitive components require to run (mirroring the VM-302 spec's four-host
   Anthropic allowlist, §4 of that document) — explicitly **denying** any path back to
   `github.com`/`api.github.com` beyond the one clone-time fetch of the pinned tag (or performing
   that single clone from outside the sealed network boundary, before isolation is sealed, so the
   running trial has no live GitHub egress at all — the stronger of the two options and the one
   this design prefers). No route to the operator's own LAN/host at all — the substrate should not
   be able to reach `/opt/dev/CORE` even over network file-sharing, not just lack a local mount.
3. **Credential layer (defense in depth).** No credentials granting access to the operator's
   account, disk, or any store holding the seal are provisioned into the runner's environment. If
   the chosen custody mechanism (§7) is a governed store requiring authentication, the runner is
   never given that credential — only the operator's own post-run evaluation step (§10) is.
4. **Application layer (defense in depth, not load-bearing alone).** If the runner is itself
   Claude-Code-driven (CORE operating autonomously under a Claude Code session, as this session
   does), the same settings class the VM-302 spec uses — `sandbox.filesystem.denyRead` /
   `sandbox.credentials.files` for any path that could resolve to the seal, `permissions.deny` for
   `WebFetch`/`WebSearch` if network egress is not otherwise required, `disableClaudeAiConnectors:
   true` — should be layered on top of §1/§2, exactly as the VM-302 spec argues for its own role:
   "Claude Code's own docs are explicit that denying WebFetch 'doesn't prevent network access... '
   That's why [the OS/network layer] remain[s] the load-bearing boundary and this section is
   defense in depth."

**Candidate substrate — the existing coldroom VM.** `scripts/coldroom-prep.sh` (last touched
`fce5c064`, within the Trial 1 runner's own included range — see §3) already provisions a fresh
Ubuntu 24.04 host/container with Docker, Postgres 16, Poetry, and `qemu-guest-agent` for Proxmox
lifecycle management; `.specs/planning/CORE-Cleanroom-Rebuild-Runbook.md` (accepted, existing
planning document, read in full for this design) documents a working, previously-exercised
procedure (2026-07-12 execution log entry) for standing up exactly this kind of host from a fresh
clone and verifying it end-to-end. This substrate **simultaneously satisfies both D9 properties**
as follows:

- **Runner-inaccessibility:** a fresh Proxmox VM/LXC container, created per the Cleanroom Runbook,
  has its own disk and its own network namespace — no filesystem path to `/opt/dev/CORE` exists on
  it at all, satisfying §1/§2 above structurally, not by discipline alone (the operator's tree
  simply is not reachable from a different machine on the network unless explicitly bridged, which
  this design does not do).
- **Seal retrievability:** entirely independent of the runner substrate — retrievability is a
  property of where the SEALED ARTIFACT lives (§7/§8), which is never the coldroom VM. The
  coldroom VM's isolation is what makes it *safe* to finalize a retrievability mechanism (commit,
  publish-hash, or governed-store) without that mechanism ever risking runner exposure, since the
  runner has no route to it regardless of which option §12 eventually selects.

The two properties are therefore not in tension on this substrate: inaccessibility is enforced by
the coldroom VM's isolation (independent of where the seal lives), and retrievability is enforced
by the seal's custody mechanism (independent of the runner's isolation) — each is satisfied by a
different, non-overlapping control, which is the affirmative answer D9 requires rather than an
assertion that one property happens to imply the other.

---

## 10. Scoring outside the runner

After the Trial 0 run completes inside the coldroom VM:

1. The runner's blackboard database (the isolated, disposable Postgres instance created for this
   run — same disposable-database pattern already proven in Unit D/E's `db_provisioning.py`,
   never the operator's `core`/`core_test`) is exported to a flat evidence file (JSON/SQL dump) —
   the same "capture, don't reopen" discipline the VM-302 spec uses for its own run evidence (§6
   of that document: "authoring → session ends → operator captures raw artifacts → hash/seal → no
   reopening").
2. The exported evidence is copied **out** of the coldroom VM to the operator's evidence store —
   at this point the runner's own further participation ends; the VM is torn down or at minimum
   the evidence copy inside it is not treated as authoritative once external copies exist.
3. **Scoring — comparing the runner's recovered findings against the sealed eight rows — happens
   in a separate process, outside the runner substrate**, on the operator's machine or a fresh
   evaluation session, using the retrieval path chosen in §12. The runner process itself never
   receives the seal, never receives a "you got N/8" signal, and never re-runs conditioned on the
   score.
4. The recall figure (D5: "of the eight sealed Phase 1 benchmark rows, how many the runner
   independently recovers, stated as a number before any interpretation is offered") is computed
   and reported at this stage, not inside the trial.

---

## 11. Trust boundaries

| Role | Trusted for | Not trusted for / structurally denied |
|---|---|---|
| **Operator** (Dariusz) | Controlling the physical/VM infrastructure; starting/stopping the runner; holding custody of the seal; declaring the run closed. | Being the *only* witness to the seal (D9's actual concern) — mitigated by making the artifact retrievable (§7/§8) so its claims are independently re-checkable by hash, even though, in this solo-developer project, no literal second human is currently available to act as evaluator. **This is a disclosed, real limitation of a one-operator project, not a solved property** — see §14. |
| **Runner** (frozen CORE at `27160a0a`, executing inside the isolated substrate) | Executing deterministically; honestly reporting its own findings and refusals (the same constitutional honesty properties CORE already enforces on itself); producing a blackboard-reconstructable trail. | Reading the seal, the subject's later state, or anything else that would let it "recognize" rather than "recover" the answer key (D9's core concern) — denied structurally, not by instruction (§9). |
| **Evaluator** (whoever performs §10's scoring step) | Comparing exported evidence against the retrieved seal; computing the recall figure; reporting it as a number before interpretation. | Having participated in configuring or running the trial in a way that could bias scoring — in practice, in this project, the evaluator role is a distinct *process/session*, run after the trial closes and using only the exported evidence plus the independently-retrieved seal, not the same continuous session that ran the trial. This is the practical substitute for "someone other than its author" available to a solo-developer project, stated explicitly rather than left implicit. |
| **Governor** | Final sign-off; the only party who can sign a threshold claim (ADR-159 D2: "Claude never signs a threshold"); deciding D3 invalidation arguments; choosing among §7's custody options. | Nothing here removes any existing Governor authority; this table exists to make explicit what each *other* role is and is not trusted for. |

---

## 12. Trial 0 isolated checkout/process design

Consolidating §9–§10 into one procedure:

1. **Provision** a fresh coldroom VM/LXC per `CORE-Cleanroom-Rebuild-Runbook.md` Phase 1 steps 1–3
   (`coldroom-prep.sh`, then a **fresh clone** — not a copy — of `DariuszNewecki/CORE` at the
   `autonomy-experiment-ready-2026-09-04` tag).
2. **Apply network policy** (§9.2) before any trial code runs: default-deny egress, DNS to the
   substrate's own resolver only, the minimum LLM/API allowlist CORE's own cognitive components
   require, no route to the operator's LAN/host.
3. **Provision the subject** as a second fresh clone (`c4d9fdf9...`), read-only-mounted into the
   runner's evaluation path — no later commits, issues, ADRs, or benchmark answers reachable from
   inside this checkout (this is naturally true of a clone pinned to one SHA with no `fetch`
   permitted post-isolation).
4. **Provision a disposable database**, same pattern as Unit D/E's `db_provisioning.py` — unique
   name, ephemeral container, never the shared `core`/`core_test` instance.
5. **Pre-run hash.** Compute and record sha256 (or `git rev-parse`/`git write-tree` where
   applicable) over: the runner checkout's tree, the subject checkout's tree, and the disposable
   database's freshly-loaded-schema state. This is the "nothing was altered before the trial
   started" baseline, mirroring Unit D/E's own `git_snapshot`/`hash_tree` pattern.
6. **Run** the preregistered Trial 0 procedure (itself out of scope for this document — the
   procedure's content is a separate design step; this document specifies only the isolation
   apparatus around it) with the network/filesystem/credential controls from §9 already active.
7. **Post-run hash.** Recompute the same three hashes. Any drift outside what the trial itself was
   expected to produce (a) is evidence, not noise — record it; (b) does not, by itself, invalidate
   the apparatus's own integrity claims unless it shows the isolation controls were bypassed
   (D3's "invalidates" bar — see below).
8. **Sanitized evidence capture.** Export the blackboard contents and any captured process
   stdout/stderr through the same `redact_secrets`/`scan_for_secrets` discipline Unit D/E already
   established (DSN-shaped credential redaction, applied here to anything the isolated network
   layer's own config might otherwise leak — proxy addresses, resolver IPs, any LLM API identifiers
   present in logs).
9. **Deterministic failure behavior.** Every failure mode — provisioning failure, network-policy
   application failure, subject-checkout mismatch, runner crash, timeout — produces a structured,
   labeled result (the same `_fail(stage, error)` shape Unit D/E's child scripts already use), not
   a silent hang or an ambiguous partial state. No automatic retry inside a single trial invocation
   (mirrors Unit D/E's "invoke the scenario exactly once" discipline).
10. **The frozen runner is never patched during a trial.** If step 6 exposes a defect in the
    `27160a0a` runner itself, the trial stops, is reported as a Trial 0 result exactly as it
    occurred (D5's own instruction: "that is an honest Trial 0 result — not permission to patch
    it"), and any correction happens afterward, on `main`, as ordinary corrective work — never by
    editing the tagged commit, and never by silently re-running the same trial claim against a
    patched runner without a fresh T-A-equivalent re-certification.
11. **Teardown.** Remove exactly the disposable VM/container and disposable database created for
    this run; the subject and runner checkouts inside it are removed with the VM (they were never
    the operator's canonical copies — those remain the GitHub-hosted tag/SHA, always re-fetchable).

**D3 invalidation process, applied to Trial 0's own apparatus:** a finding about this apparatus
(the isolation held, but recall was low; the isolation held, but a dependency was unexpectedly
missing) is backlog, per D3, unless it is argued in writing to show the *apparatus itself*
produced wrong evidence — e.g., proof that network isolation was NOT actually enforced (an egress
succeeded that should have been blocked), or that the runner in fact had a readable path to the
seal. Only that class of finding blocks or invalidates a Trial 0 (or later Trial 1) result;
everything else — including "the recall figure was lower than hoped," which is explicitly not a
threshold per D5 — is recorded and carried forward, not treated as a blocker.

---

## 13. Acceptance criteria

**D9 acceptance (before Trial 0 may run):**

- [ ] A custody mechanism for the sealed artifact is chosen from (or equivalent to) §7's options,
  by explicit Governor decision (§14).
- [ ] The chosen mechanism provides a recorded content hash, reachable independent of the
  operator's live working tree alone.
- [ ] The chosen mechanism provides an actual retrieval path (not hash-only, per §8).
- [ ] A re-verification step (fetch, hash, compare) is documented and has been exercised at least
  once by re-computing the hash against the retrieved copy.
- [ ] The runner-inaccessibility mechanism (§9) is implemented and independently demonstrated —
  e.g., an attempted read of the seal's known path from inside the isolated substrate fails
  (filesystem layer), and an attempted egress to a disallowed host from inside the substrate is
  blocked (network layer) — both demonstrated without ever exposing the seal's content during the
  demonstration.
- [ ] **§6 finding 6 (memory-substrate leakage) is resolved, not merely acknowledged** — if the
  runner is Claude-Code-driven, it is confirmed to start with no project memory directory, or a
  freshly scoped one verified free of Phase 1 content, before it ever touches the subject or the
  network-isolated substrate. Unresolved as of this document's writing (2026-09-10) — pre-existing
  memory content confirmed present, no control yet specified.

**Trial 0 start acceptance:**

- [ ] D9 acceptance (above) is fully satisfied.
- [ ] The coldroom VM (or equivalent substrate) is freshly provisioned per §12 steps 1–4, with
  fresh clones (not copies) of both runner and subject pins.
- [ ] Pre-run hashes are recorded (§12 step 5).
- [ ] The preregistered Trial 0 procedure itself (its content, separate from this apparatus) is
  written and reviewed.
- [ ] Network/filesystem/credential controls are verified active before the procedure begins.

---

## 14. Explicit non-claims

- This document does not implement D9. No custody mechanism has been created; no VM has been
  provisioned; no isolation control has been applied.
- This document does not run Trial 0 or Trial 1, and does not execute another external-target
  scenario.
- This document does not change any production behavior, `.intent/` semantics (beyond the single
  authorized namespace-manifest registration for this file itself), schema, or configuration.
- This document does not resolve which of §7's custody options the Governor will choose — that
  decision is the smallest explicit Governor decision still required, stated plainly:

  > **Open decision:** which of §7's three custody options (commit the sealed JSON to a
  > runner-unreachable location; publish a hash and relocate the artifact to a governed store;
  > or hold it in `.specs/attestations/`-equivalent governed storage with clone-order discipline)
  > should hold the Phase 1 seal going forward? No credential, external storage account, or new
  > infrastructure is assumed or invented by this document; the decision is which of the
  > already-available mechanisms to use, not building a new one.

  > **Second open decision, more urgent than the first:** §6 finding 6 — this project's Claude
  > Code auto-memory store already contains pre-existing Phase 1 benchmark content, predating D9,
  > in files this document does not name or further inspect. §9's checkout-level isolation does
  > not touch this channel at all. Before any Claude-Code-driven Trial 0/Trial 1 runner is used,
  > the Governor must decide how that runner's memory is scoped — a fresh/empty memory directory,
  > a filtered one, or a non-Claude-Code runner implementation entirely. This document proposes no
  > default; it states only that §13's D9 acceptance criteria cannot be met without an explicit
  > answer to this question.

- **Incident disclosure, not a non-claim:** while writing this document, this session accidentally
  read approximately the first two rows' worth of content (claim text and evidence paths) from
  `work/external-validation/seal_manifest.py`, believing it to be pure sealing tooling based on the
  VM-302 spec's description of it. It is not pure tooling — the sealing logic and the sealed row
  data live in the same file. No content from those rows is reproduced anywhere in this document,
  in ADR-159's Notes, in project memory, or in this unit's final report. This is disclosed here,
  and prominently in the final report, rather than omitted. It bears on whether this session (or
  its transcript) should be treated as still "blind" with respect to the Phase 1 benchmark for any
  future role — that determination is the Governor's, not this session's own, and is not resolved
  by this document. One structural lesson this incident already justifies, independent of that
  determination: §7/§9's design deliberately treats "the sealing script" and "the sealed data" as
  two artifacts requiring separate custody, specifically because this project's own existing
  `seal_manifest.py` conflates them and that conflation is what caused the accidental read.
