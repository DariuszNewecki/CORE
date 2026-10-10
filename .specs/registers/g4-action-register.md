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
| C-12 | **CORE** — CCC, once repaired | 24 contradiction candidates → 7 conflicts between law text and reality, 1 open question of law (ADR-138), 2 missing cross-refs, 15 *proposed* dismissals — **unverified** (AI grading AI, C-04), being re-checked; side findings H-05, H-06 | Triage held until the dismissals are verified (`var/reports/ccc-triage-20261010.md`) | CCC run 6558a043 (DB) |
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
