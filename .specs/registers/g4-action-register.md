# G4 action register (Soak NG, hand-kept)

**What this is.** A dated record of what happened while CORE was being developed: fixes, catches, health
problems, events, and the assistant's own misses — each with **who** did it and the **CORE record** that
proves it.

**What this is not.** G4 evidence. URS G4 (proposal 0008) requires the record to be *produced by CORE from
its own records, never assembled by hand*. This register is (1) the interim record until that daily report
exists, and (2) its **specification**: the "CORE record" column says where the generator must read each fact.
A fact whose column says `none` is a gap CORE cannot see yet — an instrumentation item.

**Kept by:** the assistant drafts; the governor approves with the session's law batch (ADR-170).
Times are UTC unless marked. Lessons drawn from these rows: `lessons-register.md`.

---

## 2026-10-10

### Fixes (all by the assistant as producer; none by CORE's autonomous loop)

| ID | Commit | What | Found by | CORE record |
|---|---|---|---|---|
| A-01 | 0f319c48 | Stuck-finalizing reaper keeps `addressed_finding_ids` in the rebuilt consequence | assistant (C-06) | git; commit-gate verdict |
| A-02 | 10828ca0 | Malformed proposals refused at submission; unknown action never "safe"; POST /proposals → 422 | assistant recon (C-07) | git; verdict |
| A-03 | b509e5c0 | `assisted.validate_diff` sees files a patch creates | external reviewer (C-05) | git; verdict |
| A-04 | e6aa7ad0 | CCC `check`/`report` name skipped/failed check classes; PARTIAL | assistant (C-08) | git; verdict |
| A-05 | e0c2312d | Batch embedding calls the batch method (broken by 409f9d4e, 2026-07-03) | assistant (C-09) | git; verdict |
| A-06 | faa0fd90 | Fallback client passes batch embedding through (missing since 2026-05-27) | assistant, from live seed log (C-09) | git; verdict |
| A-07 | a554c726 | Unjudged CCC pairs = PARTIAL, not "no contradiction"; embed failure = error | assistant (C-10) | git; verdict |
| A-08 | 1cd0d822 | Regenerated `docs/reference/openapi.json` | CORE CI (C-11) | git; CI run |

### Catches — who objected, and what changed

| ID | Caught by | What | Outcome | CORE record |
|---|---|---|---|---|
| C-01 | governor | "CORE cannot write code — the assistant's route and CORE's are one flow; only problem ownership differs" | ADR-168 amendment, proposal 0009 | law ledger (0009); chat: **none** |
| C-02 | governor | "Does it already exist?" is asked nowhere in the pipeline | Plan step 0; lesson L5 | **none** |
| C-03 | governor | "Why run CCC if we don't evaluate its findings?" — after the assistant proposed setting 24 candidates aside | 24 investigated | **none** |
| C-04 | governor | "Read it carefully" — "0 real conflicts" was AI grading AI, dismissals unchecked, code silently ruled the winner | Re-verification of the 15 dismissals; 7 stale texts to be decided, not tidied | **none** |
| C-05 | external reviewer | New files invisible to validation; validation finding-scoped; submit vs execute checks; R4; law path | A-03; ADR-168 A3–A6 | **none** |
| C-06 | assistant | Reaper dropped evidence-only finding links | A-01 | git |
| C-07 | assistant (recon agent, verified) | POST /proposals skipped validation; unknown actions scored "safe" | A-02 | git |
| C-08 | assistant | CCC contradiction checks skipped: `governance_claims` collection absent; summary said "0 skipped" | A-04; collection re-seeded (E-04) | CCC run dfa4950d (DB) |
| C-09 | assistant | Every batch embedding failed (two layers) | A-05, A-06 | seed log (var/, not DB) |
| C-10 | assistant | 930/930 LLM-judge failures reported as "0 contradictions" | A-07 | CCC run ce1a1190 (DB) |
| C-11 | **CORE** — CI hermetic tests | OpenAPI copy stale after A-02 | A-08 | CI run 38032487803 (a test, not a CORE rule) |
| C-12 | **CORE** — CCC, once repaired | 24 contradiction candidates → 7 conflicts between law text and reality, 1 open question of law (ADR-138), 2 missing cross-refs, 15 *proposed* dismissals — **unverified** (AI grading AI, C-04), being re-checked; side findings H-05, H-06 | Re-verified (C-14); triage recorded 9 confirmed / 15 dismissed; law 0011 (`var/reports/ccc-triage-20261010.md`) | CCC run 6558a043 (DB) |
| C-13 | **CORE** — pre-commit gate | 10 commits checked, 10 allowed, 0 blocked | — | `var/experiments/adr168/verdicts.jsonl` (var/, not DB) |

### Health — CORE problems found

| ID | Problem | Since | Status |
|---|---|---|---|
| H-01 | `governance_claims` collection absent → CCC contradiction checks blind | unknown | re-seeded (2,956 points) |
| H-02 | Batch embedding broken | 2026-05-27 (wrapper) / 2026-07-03 (409f9d4e) | fixed A-05, A-06 |
| H-03 | CCC reported partial runs as complete | #624 recorded it; never displayed | fixed A-04, A-07 |
| H-04 | CCC run from the CLI cannot reach the LLM judge (credentials readable by `core` only) | 2026-10-08 | open — real runs need `sudo -u core` |
| H-05 | CCC claim harvester judges retired/withdrawn ADRs as live | unknown | open |
| H-06 | 7 blocking Class-B rules enforced only at CORE's own generation boundary — not on other producers | ADR-142 | open — producer-proposal build (A3) |

### Events

| ID | Time | Event | By |
|---|---|---|---|
| E-01 | 03:45 | `main` promoted e84c7327 → f3b48054 | assistant, governor-approved |
| E-02 | 05:00:09 | Law 0009 approved (ADR-168 Proposal capability) → ac97c7ba | governor |
| E-03 | 05:41–06:02 | Seed bootstrap (×2; first stopped on unfixed code) | assistant, governor-approved |
| E-04 | 05:39 / 06:06 / 06:24 | CCC runs dfa4950d (partial), ce1a1190 (false clean), 6558a043 (real, as `core`) | assistant / assistant / governor |
| E-05 | several | Services restarted on new code (17 units) | assistant |
| E-06 | ~07:12 | `.venv` editable reinstall (metadata 2.12.1 → 2.13.0) | assistant, governor-approved |
| E-07 | 06:53 / 07:14 | develop pushed → a554c726 (CI red, C-11) → 1cd0d822 | assistant |

### Assistant's own misses

| ID | Miss | Caught by | Consequence |
|---|---|---|---|
| M-01 | Ran a test that uses the shared `core_test` database without asking | assistant | none (own cleanup); reported |
| M-02 | Typed a symbol UUID by hand | assistant | replaced before commit |
| M-03 | A-05's test mocked the layer below; fix was incomplete | live seed log | A-06 |
| M-04 | Process watcher used `kill -0` on a `core` process; permission error read as "finished" | governor ("still running?") | false "incomplete run" report, corrected |
| M-05 | "I checked the key claims myself" — no dismissal had been checked | governor (C-04) | re-verification |
| M-06 | Changed a route description without regenerating the OpenAPI copy | CORE CI (C-11) | CI red once |
| M-07 | Proposed setting aside 24 findings without reading them | governor (C-03) | investigation |

### Day summary (by hand — the daily report must compute this)

- Fixes: 8 code commits + 1 law change, **all by the assistant**; 0 by CORE's autonomous loop.
- Catches: 13 — governor 4, external reviewer 1, assistant 5, **CORE 3** (one only after the assistant repaired it).
- Health problems found: 6 (4 fixed, 2 open).
- CORE-recordable today: git, CI, CCC runs (DB). **Not recordable:** chat catches, reviewer catches, commit-gate
  verdicts (file in `var/`, not in CORE's records), seed logs.

### 2026-10-10, afternoon

**Fixes and law (assistant as producer; none by CORE's loop)**

| ID | Commit | What | Found by | CORE record |
|---|---|---|---|---|
| A-09 | 751f2a64 | Law 0010: these registers | governor (idea) | git; law ledger |
| A-10 | c3621395 | Law 0011: 12 files — stale law text corrected; ADR-138 narrowed to ADR-142 classes; ADR-120/158 accepted | CCC + C-14 | git; law ledger |
| A-11 | 17d0d688 | CCC harvester skips superseded/retired documents | CCC triage (H-05) | git; verdict |
| A-12 | bd4a684b | Onboard docstrings + OpenAPI: floor from `shared._machinery_floor` | CCC triage | git; verdict; CI green |
| A-13 | 7013daed | Law 0012: topology rows 2/4 relaxed; triage carry-forward; 8 floor configs → framework; 20 references; ADR-094 not built; ADR-117 accepted | CCC structural triage | git; law ledger |
| A-14 | 376f9580 | CCC checks: PATH_REF parser, ROW3 drafts, ROW2/ROW4 amended rules, git `--follow`, triage carry-forward | CCC structural triage | git; verdict; CI **red** (C-19) |
| A-15 | 8d2af032 | ROW3 draft check as a status set (guard test) | CORE CI (C-19) | git; CI green |

**Catches**

| ID | Caught by | What | Outcome | CORE record |
|---|---|---|---|---|
| C-14 | assistant (after C-04) | Re-reading all 17 proposed dismissals: 15 hold, 2 are real text gaps (ADR-076, ADR-059) | Decided by governor; law 0011 | **none** (report in `var/`) |
| C-15 | assistant | CCC forgets triage between runs — every run re-raises everything | Carry-forward (A-13, A-14) | **none** |
| C-16 | assistant (CCC PATH_REF) | ADR-094 accepted but never built; ADR-117/120/158 "Proposed" yet applied | Governor decisions; laws 0011/0012 | CCC run 6558a043 (indirect) |
| C-17 | assistant (CCC ROW4) | 4 law files with no recorded decision; 17 introduced under an issue only | Deferred — to trace | CCC run 6558a043 |
| C-18 | **CORE** — pre-commit gate | Refused law 0012's commit: my code had orphaned a symbol ID (`linkage.no_orphan_ids`) | Fixed, recommitted | `var/experiments/adr168/verdicts.jsonl` (var/, not DB) |
| C-19 | **CORE** — CI guard test | `'draft'` literal in production code (retired Proposal status) — CI 38038361862 | A-15 | CI run |
| C-20 | governor | Row 4 rule as I first worded it ("folder") — approved, then shown too narrow by my own dry run | Folder condition dropped before law | **none** |

**Health**

| ID | Problem | Since | Status |
|---|---|---|---|
| H-07 | CCC triage not carried across runs | CCC birth | fixed (A-13, A-14) |
| H-08 | Six CCC check defects (PATH_REF parser, ROW4 rename date, ROW3 drafts, ROW2 name-match, manifest misclassification, retired docs) | various | fixed (A-11, A-13, A-14) |
| H-09 | Three ADRs applied as law while still "Proposed" (117, 120, 158) | 2026-06/08 | accepted by governor |
| H-10 | An accepted ADR never built (ADR-094, URS sensor); SPECGAP cannot see ADR deliverables | 2026-06-06 | recorded; open |

**Events**

| ID | Time | Event | By |
|---|---|---|---|
| E-08 | 07:20 / 07:35 / 08:25 | Laws 0010, 0011, 0012 approved | governor |
| E-09 | ~07:45 | CCC contradiction triage recorded (9 confirmed / 15 dismissed) | governor |
| E-10 | 07:47 / 08:31 / 08:44 / 08:56 | Pushes; CI green, green, **red**, green | assistant |
| E-11 | 09:2x–10:16 | CCC structural triage recorded; run 6558a043 **closed**: 469 candidates — 49 confirmed / 280 dismissed / 140 deferred / 0 unreviewed (verified from the run) | governor |

**Assistant's misses**

| ID | Miss | Caught by | Consequence |
|---|---|---|---|
| M-08 | A `-k` sweep pulled 5 `core_test` integration tests into a scoped run (second time, after M-01) | assistant | none; scoped runs now use `-m "not trio and not integration"` |
| M-09 | Inserted a function between another function and its symbol ID | CORE gate (C-18) | commit refused once |
| M-10 | Compared a paper status with the literal `"draft"` | CORE CI (C-19) | CI red once |
| M-11 | First structural triage script over-confirmed 3 items (matched documents, not document + path) | assistant | fixed before handover |
| M-12 | Predicted ROW4 at ~23; the rule as worded left 41 | assistant (dry run) | C-20 |
| M-13 | Two counting errors in the structural report (130 ≠ 134; 17 vs 14) | assistant (re-adding) | fixed before handover |

**Day total (by hand)** — fixes and law: 15 entries, all by the assistant; catches: 20 — governor 5, reviewer 1, assistant 9,
**CORE 5** (C-11, C-12 once repaired, C-13, C-18, C-19); assistant misses: 13.


### 2026-10-10, session 2 (producer build)

**Fixes and law (assistant as producer; none by CORE's loop)**

| ID | Commit | What | Found by | CORE record |
|---|---|---|---|---|
| A-16 | af77b677 | Every proposal carries provenance (anchor, owner, producer, retires); submission refuses without it | plan U1 | git; verdict |
| A-17 | ef9e88f7 | Law 0014: ADR-168 R1–R5; governed text as data; proposal contracts caught up | governor rulings; C-22 | law ledger; git |
| A-18 | c117711c | General validation: governed-text refusal, full blocking audit over the patched tree, tests (shared-state markers excluded) | plan U2 | git; verdict |
| A-19 | 78db86df | Class B test rules bind every producer; PatternValidators statement cache fixed (~4 s → ms per file) | plan U2b; C-25 | git; verdict |
| A-20 | ecfb9694 / fedca645 | Step 0: patch facts, retirement verified, ADR mentions + history, look-alikes ("unavailable" ≠ "none") | plan U3; C-27 | git; verdict |
| A-21 | 17bf4007 | An approved patch's declared deletions reach the main tree and the commit | plan U4; H-15 | git; verdict |
| A-22 | 89685c53 | Producer is the git author, CORE the committer | plan U5 | git (`%an`/`%cn`) |
| A-23 | ea6eefb6 / 3d4c0fef | POST /v1/proposals/submit; MCP `validate_change` / `submit_change`; D3 authority test | plan U7 | git; verdict |
| A-24 | core-cli 04ac037, 6035ed6; tag v2.1.0; CORE 028c9960 | `core proposals approve` needs a person at a terminal typing the short id; `show` explains who, why, checks (operator role, governor grant) | plan U6; C-28 | core-cli git + PyPI 2.1.0; **none** in CORE's records |

**Catches**

| ID | Caught by | What | Outcome | CORE record |
|---|---|---|---|---|
| C-21 | governor | "It will not be me but my Claude session as core-darek" — approval by a model under the governor's account | R2: approval typed by the human at a terminal | law 0014 |
| C-22 | **CORE** — audit in the law-batch check | U1 added proposal fields without their data contracts (`data.contracts.*_conforms`, info) | Law 0014 | law-check run (var/, not DB) |
| C-23 | **CORE** — pre-commit gate | Public-named nested helper without an ID (`linkage.assign_ids`) | Renamed private; recommitted | `var/experiments/adr168/verdicts.jsonl` |
| C-24 | **CORE** — pre-commit gate | `docs/reference/core.md` out of date after installing unreleased core-cli (`cli.reference_current`) | ADR-167 D2 path: released core-cli 2.1.0 | `verdicts.jsonl` |
| C-25 | assistant | PatternValidators re-scanned all `.intent/` rules 5× per validated file | A-19 | git |
| C-26 | assistant | 41 of 1044 existing test files break the Class B rules (3 are CORE-generated) — never seen, the rules bind only at write time | Whole-file judgement for any producer touching them | **none** |
| C-27 | assistant | Vector search helpers return `[]` on error — a failed search would read "nothing similar" | Step 0 uses the raising search | **none** |
| C-28 | assistant | `core proposals approve` had no confirmation and was not marked dangerous | A-24 | **none** |
| C-29 | **CORE** — pre-commit gate | 14 commits checked, 12 allowed, 2 refused (C-23, C-24) | — | `verdicts.jsonl` |
| C-30 | **CORE** — audit in the law-batch check | This batch's two new contracts were not classified in the namespace manifest (`governance.namespace.classification_complete`, blocking) | Manifest entries added to the batch before asking | law-check run (var/, not DB) |

**Health**

| ID | Problem | Since | Status |
|---|---|---|---|
| H-11 | Class B statement loader re-scanned the law on every check | #589 | fixed (A-19) |
| H-12 | 41 test files violate Class B rules; no audit sees committed tests | ADR-142 | open |
| H-13 | `QdrantService.search_similar` / `VectorProvider` return `[]` on failure | unknown | open (step 0 avoids it) |
| H-14 | A model on the governor's account can approve via the API | — | open: #942; R2 is a speed bump |
| H-15 | Sandbox copy-back dropped every deletion | ADR-071 D2.2 | fixed (A-21) |
| H-16 | CORE's LLM lanes do not report which model wrote the bytes; commits name the role | — | open |

**Events**

| ID | Time | Event | By |
|---|---|---|---|
| E-12 | ~10:35 | `main` promoted f3b48054..18a364bf (17 commits, CI green) | assistant, governor yes |
| E-13 | 11:13:13 | Law 0014 approved | governor |
| E-14 | ~13:04 | core-cli `v2.1.0` tagged and pushed (published to PyPI by its CI); the assistant's tag push was refused by the permission system | governor |
| E-15 | ~13:00 | core-platform read-only study (`var/reports/core-platform-study-20261010.md`) | assistant, at governor request |

**Assistant's misses**

| ID | Miss | Caught by | Consequence |
|---|---|---|---|
| M-14 | Told the governor there was no approve command — searched `core-admin` only; it was in `core` (core-cli) | assistant (U6 recon) | corrected in chat |
| M-15 | Added fields to a governed class without its data contract | CORE (C-22) | law 0014 |
| M-16 | Nested public-named helper without an ID | CORE (C-23) | commit refused once |
| M-17 | Installed an unreleased core-cli into CORE's environment without checking ADR-167 D2 | CORE (C-24) | commit refused once; release done |
| M-18 | First D3 test matched `session.execute` as "execution" — too broad | assistant (own run) | narrowed; mutation-checked |
| M-19 | Test helper used a plain mock for an awaited state manager | assistant (own run) | fixed before commit |
| M-20 | New contract files without namespace-manifest entries — the known "registrations" lesson, missed again | CORE (C-30) | caught before approval |

**Session total (by hand)** — fixes and law: 9 entries, all by the assistant; catches: 10 — governor 1, assistant 4,
**CORE 5** (C-22, C-23, C-24, C-29, C-30); assistant misses: 7 (4 caught by CORE).

### 2026-10-10, session 2 — acceptance and close

**Fixes and law (assistant as producer, unless noted)**

| ID | Commit | What | Found by | CORE record |
|---|---|---|---|---|
| A-25 | 6c422e40 | MCP submit tools pass the patch byte for byte (stripping dropped its final newline) | U8 run 06bb1632 (C-31) | git; verdict |
| A-26 | ad337e5d | A live sandbox is never swept; a vanished one never falls through to the main repo; apply proves its effect | U8 attempt 1, da93593b (C-32) | git; verdict |
| A-27 | 32b98a3d | **U8: the first change through the one flow** — submitted via MCP, validated (169 s), approved by the governor at a terminal, committed with the producer as author and CORE as committer, consequence recorded | plan U8 | proposal 40264fc6; consequence ad337e5d → 32b98a3d |
| A-28 | 72dcd4a9 | Assisted-lane factory test passes a producer | CORE CI (C-34) | git; CI 38061834699 green |
| A-29 | 3a6b1b53 | Law 0016: ADR-132 D10 unparked (human-only governor account; sandbox runner service; order) | governor rulings | law ledger; git |
| A-30 | ac489af3 + root act | D1: CORE's git never runs repo hooks or fsmonitor; `.git/config`, `hooks/`, `info/` owned by `core` | plan D1 | git; verdict; root act **none** |
| A-31 | 79b9cbb2 … 8b40d525 (6) | **CORE's own loop**: tests generated for `sandbox_lifecycle.py` after U8 touched it — author `core:flow.build_test_for_symbol`, committer CORE daemon (U5 shown for CORE's own producer) | CORE (test coverage sensor) | git; proposals |

**Catches**

| ID | Caught by | What | Outcome | CORE record |
|---|---|---|---|---|
| C-31 | **CORE** — validation run | "corrupt patch at line 17": the submit tool stripped the patch | A-25 | fix run 06bb1632 (DB) |
| C-32 | assistant | Approved proposal da93593b marked **completed** with an empty production set — nothing applied | Root cause via the governor's journal read; A-26 | proposal da93593b + consequence (0 files) (DB) |
| C-33 | **CORE** — ADR-030 stale-code guard | The consumer suspended itself rather than run code older than HEAD after 6c422e40 | Restart; then executed | blackboard `suspended.stale_code` (DB) |
| C-34 | **CORE** — CI hermetic tests | 1 of 6067 failed: a unit test I had not run (missing producer) | A-28 | CI 38060894074 |
| C-35 | assistant (step 0 on my own plan) | Platform plan P1 designed a password before reading ADR-132 D10, which had already decided identity (kernel peer uid; parked) | P1 dropped; D10 unparked (A-29) | **none** |
| C-36 | governor | "B seems cleanest … enrich it with a dedicated user" — the sandbox runner gets its own account | D10.10 | law 0016 |
| C-37 | assistant | After D1, `.git/` stays group-writable: `.git/config` can still be replaced wholesale | Full R3 moved to D2 (services' own git) | **none** |
| C-38 | **CORE** — pre-commit gate | 6 commits checked since law 0015, 6 allowed | — | `verdicts.jsonl` |

**Health**

| ID | Problem | Since | Status |
|---|---|---|---|
| H-17 | Worker boot sweeps removed live action sandboxes | ADR-071 D2.2 | fixed (A-26) |
| H-18 | `git apply` in a vanished sandbox reported success; proposals completed with nothing applied | same | fixed (A-26) |
| H-19 | R3: `.git/` group-writable → config replaceable | — | open → D2 |
| H-20 | Production DB credential (`.env` `DATABASE_URL`) readable by the assistant | — | open → D6 |

**Events**

| ID | Time | Event | By |
|---|---|---|---|
| E-16 | 14:00 | Proposal da93593b approved (typed); false-completed at 14:13 | governor; CORE |
| E-17 | 14:39 | **U8 passed**: 40264fc6 → 32b98a3d | governor + CORE |
| E-18 | 14:4x / 15:0x | develop pushed (15 commits); CI red (C-34), fix pushed, CI green | assistant |
| E-19 | 15:15:36 | Law 0016 approved | governor |
| E-20 | ~15:3x | D1 root act (git custody) | governor |
| E-21 | ~15:45 | core-platform: invitation accepted (write access); governor's 2 docs commits pushed; Node.js 22 installed | governor; assistant (operator) |

**Assistant's misses**

| ID | Miss | Caught by | Consequence |
|---|---|---|---|
| M-21 | Read the patch through a stripping helper | CORE (C-31) | one failed validation |
| M-22 | Excluded a whole test file instead of relying on the marker filter | CORE CI (C-34) | CI red once |
| M-23 | Did not restart services after 6c422e40 | CORE (C-33) | ~12 min delay |
| M-24 | Told the governor to run a sudo command with `!` (no terminal in my shell) | governor (failed) | one wasted step |
| M-25 | Designed P1 before checking ADR-132 | assistant (C-35) | plan corrected before any build |

**Session-2 total (by hand)** — fixes and law: 16 entries (15 by the assistant, 1 by CORE's own loop);
catches: 18 — governor 2, assistant 8, **CORE 8**; assistant misses: 12 (7 caught by CORE).

---

## 2026-10-11

ADR-132 D10 · D2 (release runtime, CORE's own git) built and left inert. Two sessions: the morning (design, three
review rounds, C1–C5 and the law routing) and the afternoon (governor's answers, closing the gaps, C6, this batch).

### Fixes and builds (all by the assistant as producer; none by CORE's autonomous loop)

| ID | Commit | What | Found by | CORE record |
|---|---|---|---|---|
| A-32 | d6644393 | Copy-back refuses when the main tree's HEAD moved under a target file (a live bug) | external reviewer (C-39) | git; commit-gate verdict |
| A-33 | 17d8abf0 | Roots follow an explicit `REPO_PATH`; services refuse a missing/empty/floor law root (exit 78) | design | git; verdict |
| A-34 | 070e72ba | An installed release is its own code identity (C4) | design (C-39) | git; verdict |
| A-35 | 1d3ee22d | RepoSync: fast-forward only, journalled, recoverable; repo lock (C2) | design (C-40) | git; verdict |
| A-36 | d6274aac | Proposals run under the repo lock; a busy lock leaves the proposal approved, not failed (also the ADR-023 D4 refusal); consumer syncs first (C3) | design | git; verdict |
| A-37 | 4d5e6617, 8459f839 | About 60 service-path law reads routed through `law_roots` (law beside the clone) | assistant recon | git; verdict |
| A-38 | 76964b52 | Test remediator's fallback root is the configured one | assistant recon | git; verdict |
| A-39 | c22d24c5 | Import-resolution tools run in the analysed repository, not the working directory | assistant's D2 audit probe (C-45) | git; verdict |
| A-40 | 6bd70010 | Every service process recovers an interrupted sync before reading; last law-path leftovers; `/fix/ir` writes `var/mind/ir` | governor (C-46); assistant (C-48) | git; verdict |
| A-41 | 6a64a5c3, 151d100d | D2 units and `core-deploy`, prepared not installed, with 29 tests (operator role: infra/, governor grant) | design (C6) | git; verdict |
| A-42 | 528526b8 | A release process goes stale when `current` is switched without a restart (ADR-030) | assistant (C-47) | git; verdict |
| A-43 | 099d8f37 | Law beside the clone decided by value: dev worktrees (sandboxes, the law scratch worktree) keep their own law | CORE (C-50) | git; verdict |

### Catches — who objected, and what changed

| ID | Caught by | What | Outcome | CORE record |
|---|---|---|---|---|
| C-39 | external reviewer | D2 rev 1, six points: a push runs the receiver's hooks; `code_identity` fingerprints the clone's `src/`; copy-back had no base check; MIND/SPECS ignore `REPO_PATH`; `EnvironmentFile` would undo #962; `core-law` does not exist yet | rev 2; transport B; A-32 | **none** |
| C-40 | external reviewer | rev 2: a fast-forward deletes law kept in a sparse checkout (reproduced); `.git` 700 contradicts the fetch; migrations before readiness; build accounts; checkout not atomic | rev 3: law out of the clone; journal + recovery | **none** |
| C-41 | external reviewer | rev 3: committed law is not approved law while `develop` is unprotected | ruling B withdrawn; A stands | **none** |
| C-42 | governor | "Stop the ping-pong": three review rounds were enough | build, then one bundled ask | **none** |
| C-43 | CORE (fast verdict) | `# ID` above the decorator on `repo_lock` | fixed before commit | **none** (fast verdicts are not logged) |
| C-44 | mypy (run by the assistant) | A `Literal` type miss in C3; the fast verdict does not evaluate `quality.type_safety` | fixed before commit | **none** |
| C-45 | assistant (D2 audit probe) | The only difference between the normal and the D2-layout audit: `mypy src` ran from the working directory | A-39; then identical, 243 rules / 31 findings | probe output in `var/tmp/d2probe` (not durable) |
| C-46 | governor | "Before declaring D2 ready, close the startup recovery window and the remaining law paths" | A-40 | **none** |
| C-47 | assistant (re-reading ADR-030 for this batch, as the design required) | C4's "release never goes stale" silently retired ADR-030 for releases | A-42; ADR-030/169 amendments | **none** |
| C-48 | assistant recon | `POST /fix/ir` wrote into `.intent/`, which IntentGuard refuses: the endpoint could never have worked | A-40 | **none** |
| C-49 | assistant (writing tests) | `core-deploy` left a refused release installed, so a corrected re-run would refuse "exists" | fixed before commit | **none** |
| C-50 | **CORE** (offline audit, in this batch's D0 check) | A rule failed on a contract path outside the scratch worktree: since C1, an explicit `REPO_PATH` marks MIND "set", so `law_roots` sent every dev worktree to the main tree's law. D2 was not inert in dev, and D0 checks would have validated the current law, not the batch | A-43; D0 checks now pass `REPO_PATH=<worktree>` | audit JSON of the check (`var/tmp/law0018-audit.json`, not durable) |

**Health**

| ID | Problem | Since | Status |
|---|---|---|---|
| H-21 | `POST /fix/ir` always failed (target inside `.intent/`) | unknown | fixed (A-40) |
| H-22 | Copy-back could overwrite a newer committed change to the same file | ADR-071 | fixed (A-32) |
| H-19 | R3: `.git/` group-writable → config replaceable | — | built for the services (D10.12), **not live** |

**Events**

| ID | Time | Event | By |
|---|---|---|---|
| E-22 | ~06:3x | main promoted 18a364bf..c0675bbb (25 commits, CI green) | governor yes; assistant |
| E-23 | morning | Rulings: transport B; law A; fix copy-back now | governor |
| E-24 | ~08:2x | Pause; 9 commits local; questions left | governor |
| E-25 | afternoon | Answers: infra/ operator grant (local preparation only), law batch now, push at session end | governor |

**Assistant's misses**

| ID | Miss | Caught by | Consequence |
|---|---|---|---|
| M-26 | D2 rev 1/2 made claims the reviewer disproved (push hooks, law in a sparse checkout) | external reviewer (C-39, C-40) | two revisions |
| M-27 | Shipped C3 with a known recovery window, written down as a "deviation" | governor (C-46) | closed in A-40 before go-live |
| M-28 | Law routing batches 1–2 missed the daemon's worker discovery and five more reads | assistant (final sweep) | closed in A-40 |
| M-29 | C4 declared releases never stale, against ADR-030 | assistant (C-47) | closed in A-42 |
| M-30 | First `core-deploy` draft left refused releases behind | assistant (C-49) | never committed |
| M-31 | Claimed D2 code "inert today" without testing a worktree inside the dev checkout; `law_roots` trusted `model_fields_set`, which C1's own derivation fills | CORE (C-50) | dev sandboxes read the main tree's law from the 08:01 routing commit (once the services restarted) until the fix; the law was identical in practice; fixed A-43 |

**2026-10-11 total (by hand)** — fixes and builds: 12 entries, all by the assistant; catches: 12 — governor 2,
external reviewer 3, assistant 4, **CORE 2**, mypy (a tool) 1; assistant misses: 6, one caught by CORE. The
commit gate ran 12 times for 13 commits and allowed every run, plus one false trigger on a command that only
wrote a file containing the words `git commit` (`var/experiments/adr168/verdicts.jsonl`, 10:12:33).

## 2026-10-11 (after law 0018) and 2026-10-11 session 3

After the 0018 push: CI red, two fixes, CI green, main promoted. Session 3: the ADR-170 rehearsal evaluation.

### Fixes and builds (all by the assistant as producer)

| ID | Commit | What | Found by | CORE record |
|---|---|---|---|---|
| A-44 | ffa1cf81 | Law loaders discover the law from the working directory first; an explicit `REPO_PATH` decides only where no law is found (undoes the external-target regression of 8459f839) | **CORE CI** (C-51) | git; verdict; CI run 38133587504 |
| A-45 | 34a314ee | Test only: a killed worker that is still a zombie counts as dead | CORE CI (C-52) | git; CI |

### Catches — who objected, and what changed

| ID | Caught by | What | Outcome | CORE record |
|---|---|---|---|---|
| C-51 | **CORE** (CI, hermetic suite, run 38132196522) | 8459f839 made law loaders prefer an explicit `REPO_PATH`; external-target runs set it to the target, so `fix.format` read the target's minimal law and failed | A-44; regression test fails on the old code | CI run |
| C-52 | CORE CI (same run) | A process test read a zombie as alive (flaky, test defect) | A-45 | CI run |
| C-53 | assistant (writing the rehearsal evaluation) | Proposal 0012 (7013daed, 20 files) has no rehearsal-ledger line, although its commit says "ledger appended"; bytes match `hashes.txt` | reconstructed line appended with 0019; Stage 2's custody rule is the standing check | ledger; git |

**Events**

| ID | Time | Event | By |
|---|---|---|---|
| E-26 | ~10:3x | develop pushed c0675bbb..50cbc9e6; CI red (C-51, C-52); fixes pushed; CI 38133587504 green | governor yes; assistant |
| E-27 | ~11:0x | main promoted c0675bbb..34a314ee (fast-forward, CI green) | governor yes; assistant |
| E-28 | session 3 | ADR-170 rehearsal evaluation written (`var/reports/adr170-rehearsal-evaluation-20261011.md`) | assistant |

**Assistant's misses**

| ID | Miss | Caught by | Consequence |
|---|---|---|---|
| M-32 | 8459f839's message claimed "no change while `REPO_PATH` is unset"; external-target runs set it | CORE CI (C-51) | develop red for one push; fixed A-44 |
| M-33 | Did not append 0012's ledger line, and wrote in the commit that it had | assistant, a day later (C-53) | acceptance check 1 failed for one commit; the custody was intact, the record was not |
| M-34 | Stopped recording `asked_utc` after 0006 and `lines_changed` after 0004 | assistant (evaluation) | approval latency unmeasured for 12 of 18 batches |

**2026-10-11 after 0018 (by hand)** — fixes: 2, by the assistant; catches: 3 — **CORE 2** (CI), assistant 1;
assistant misses: 3, one caught by CORE.

### Session 3, continued — `law apply` built

| ID | Commit | What | Found by | CORE record |
|---|---|---|---|---|
| A-46 | (this batch's code commit) | `law apply` / `law check-tree`: proposal read once into memory, data checks in a child on the proposal's tree, computed + declared warnings, custodian-only writer, signed ledger line, two destinations; 26 tests (3 mutation-checked) | design (ADR-170 Stage 1) | git; verdict |

| ID | Caught by | What | Outcome | CORE record |
|---|---|---|---|---|
| C-54 | assistant (recon for `law apply`) | Law 0019 item 3 had `law apply` run the full audit, which executes repository code — against D2 | governor ruled "data checks only"; corrected in ADR-170 (0020) | **none** |
| C-55 | **CORE** (fast verdict) | `# ID` above `@dataclass` on 6 classes; a `print()` in the CLI | fixed before commit | **none** (fast verdicts are not logged) |

| ID | Miss | Caught by | Consequence |
|---|---|---|---|
| M-35 | Wrote and got approved a law item (0019 item 3) that contradicts the same ADR's D2 | assistant, 10 minutes later (C-54) | one corrective batch; nothing was built on it |
| M-36 | Put `# ID` above `@dataclass` again (same trap as C-43) | CORE (C-55) | none |

### Session 3, continued — Stage 1 prepared

| ID | Commit | What | Found by | CORE record |
|---|---|---|---|---|
| A-47 | c82da3ea | `law apply`'s scratch tree links the whole repository: the law references files outside the copied entries, so every real proposal was refused | assistant's installed-wheel test, asked for by the governor (C-57) | git; verdict |
| A-48 | c82da3ea | `tests/infra/test_law_apply_installed_wheel.py`: `law apply` from the built wheel — account refusal, report-only default, `--write` + typed id, signature, no git, no dev-tree import | governor (asked before tagging) | git; CI |
| A-49 | e9d240ae | `infra/core-law-setup` (operator role, governor grant): account, root-owned released venv, key kept on re-run, ownership, sticky root, `/opt/core/law`, sudoers, probes; 15 tests | design (Stage 1) | git |

| ID | Caught by | What | Outcome | CORE record |
|---|---|---|---|---|
| C-56 | **CORE** (commit gate, `cli.dangerous_explicit`) | `law apply` had no `--write`; a typed id is not a substitute (#824) | `--write` added before the first commit | verdicts.jsonl |
| C-57 | governor (asked for the wheel test) → assistant's test | Scratch tree too small: `references_resolve` refused every real proposal | A-47 | test run |
| C-58 | assistant (probe after C-56) | A worktree audit judges CLI rules against the installed code | issue #965 | GitHub #965 |

**Events**

| ID | Time | Event | By |
|---|---|---|---|
| E-29 | ~12:0x | develop pushed 34a314ee..1d19a454; CI 38138492511 green | governor yes; assistant |
| E-30 | ~12:0x | Operator grant: prepare and test the Stage 1 setup script; wheel test before tagging; one law batch | governor |

**Assistant's misses**

| ID | Miss | Caught by | Consequence |
|---|---|---|---|
| M-37 | Trusted the worktree audit for a CLI change | CORE commit gate (C-56) | none; gap filed (#965) |
| M-38 | Called `check-tree` "proven live" from a full worktree; `law apply` builds a smaller tree | the wheel test (C-57) | would have refused every real proposal; never released |
| M-39 | Typed symbol UUIDs by hand twice, against my own rule | assistant, before commit | none |

**Session 3 total (by hand)** — fixes and builds: 6 (A-44–A-49); catches: 8 — **CORE 3**, governor 1 (via the
test they asked for), assistant 4; assistant misses: 8 (M-32–M-39), 2 caught by CORE.

### Session 3, continued — release candidate review

| ID | Commit | What | Found by | CORE record |
|---|---|---|---|---|
| A-50 | 2c2d19c6 | core-law-setup: owner/mode table now → after; the repository's parent taken from `core` (`/opt/dev` root:root 755); root-equivalent accounts named; repository-rename probe | governor (asked to confirm no bypass) | git |
| A-51 | 910b55f8 | core-law-setup: venv installed at its final path, previous one restored on failure; `timestamp_timeout=0`; real-venv tests and visudo | governor (C-59, C-60) | git |

| ID | Caught by | What | Outcome | CORE record |
|---|---|---|---|---|
| C-59 | **governor** (release review) | The venv built at `venv.new` and renamed: its entry points point at the old path | A-51; tests fail on the old code | **none** |
| C-60 | **governor** (release review) | sudo's credential cache let `law apply` run without a fresh password | A-51; ADR-170 amendment 0022 | **none** |
| C-61 | assistant (bypass check the governor asked for) | `/opt/dev` owned by `core`: the parent's owner can rename the repository; `core-darek` in `docker` | A-50; docker membership left to the governor | **none** |

**Events**

| ID | Time | Event | By |
|---|---|---|---|
| E-31 | ~12:3x | develop pushed 1d19a454..b1e740ba; CI 38140632656 green | governor yes; assistant |
| E-32 | ~13:0x | 2.14.0 release candidate fc37cfad pushed; CI 38141384814 green; tag held after review | governor |
| E-33 | ~13:2x | `.venv` editable reinstall, `--no-deps`: reports 2.14.0, dependency pins unchanged | governor yes; assistant |

**Assistant's misses**

| ID | Miss | Caught by | Consequence |
|---|---|---|---|
| M-40 | Built the venv elsewhere and renamed it; tested with a fake host whose `core-admin` was an empty file | governor (C-59) | Stage 1 setup would have left core-law without a working command; never run |
| M-41 | Wrote a sudo rule that asks for a password but honours sudo's cache, against D6's intent | governor (C-60) | never installed |
| M-42 | Left `/opt/dev` owned by `core` out of the name-protection design | assistant, when asked (C-61) | never installed |
