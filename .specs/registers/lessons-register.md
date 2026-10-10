# Lessons register

**Purpose.** What working on CORE taught us about *how* CORE should be built and governed — lessons that
are true beyond the incident that taught them. One row per lesson. A lesson is closed only when it is
**applied**: turned into a rule, a check, a test, a procedure step or a decision — and the row names where.

**Kept by:** the assistant drafts; the governor approves with the session's law batch (ADR-170).
**Not:** an incident log (that is `g4-action-register.md`), and not gate evidence.

Status: `open` (learned, not yet applied) · `applied` (names where) · `superseded`.

| # | Date | Lesson | Observed in | Status / where applied |
|---|---|---|---|---|
| L1 | 2026-10-10 | **A check must say "could not check" differently from "checked, nothing found".** Every silent failure today looked like a clean result. | CCC skipped classes reported "0 skipped"; batch-embed and judge failures read as "0 contradictions"; a process watcher read "permission denied" as "finished" (C-08, C-09, C-10, H-03, M-04) | applied in CCC (e6aa7ad0, a554c726); **open** as a general rule for every check and sensor |
| L2 | 2026-10-10 | **Running a check without evaluating its findings is ceremony.** Running CCC commits us to triaging what it says. | Proposal to "set aside" 24 unread candidates (C-03, M-07) | applied: all 469 triaged; triage carries forward (law 0012, 376f9580); **open** as plan step 0 |
| L3 | 2026-10-10 | **AI grading AI is not verification.** A dismissal hides a real problem if wrong; dismissals need independent checking, not only the confirmations. | "0 real conflicts" rested on agent dismissals I had not checked (C-04, M-05) | applied once (C-14: 2 of 17 dismissals were wrong); **open** as a rule |
| L4 | 2026-10-10 | **When law text and code disagree, "the code wins" is a governor decision, not a default.** | 7 stale-text verdicts quietly ruled for the code; ADR-138 vs 18 blocking rules (C-04) | open |
| L5 | 2026-10-10 | **"Does it already exist / was it already decided?" is asked first, before planning or code.** | Saved work twice (link recording, assisted lane); missing once produced a second proposal route that skipped validation (C-02, C-07) | open — plan step 0 |
| L6 | 2026-10-10 | **Code must keep a live link to its reason; the pipeline must be able to remove as well as add.** Dead code is code whose reason died unnoticed. | Recent dead-code deletions; CORE's apply path silently drops deletions (#451) | open — producer-proposal build (A2 anchor, deletions) |
| L7 | 2026-10-10 | **A fix to an integration is proven by a live run, not by a test that mocks the layer below.** | e0c2312d's test mocked the service and missed the wrapper; the live seed log exposed it (C-09, M-03) | applied in faa0fd90 (parity test); **open** as a habit |
| L8 | 2026-10-10 | **Silencing a type error by changing a call can change behaviour.** Type clean-ups that touch calls need a behavioural test. | 409f9d4e (2026-07-03) swapped the batch call; broken 3 months (H-02) | open |
| L9 | 2026-10-10 | **A change of permissions changes what our tools can see — and they fail silently.** | Since the 10-08 secrets move, CLI runs cannot reach the LLM judge (930/930 failed); `kill -0` on another user's process (H-04, M-04) | open |
| L10 | 2026-10-10 | **Generated artifacts move with the change that alters their source; environment metadata drifts.** | OpenAPI copy not regenerated → CI red; `.venv` metadata said 2.12.1 after the 2.13.0 release (C-11, M-06) | open |
| L11 | 2026-10-10 | **Law prose goes stale silently.** 7 of 24 CCC candidates were true statements turned false. Law needs a standing "is this still true?" loop. | CCC run 6558a043 triage (C-12) | open |
| L12 | 2026-10-10 | **Count who caught what.** On a busy day almost every catch came from the governor, a reviewer or the assistant — not from CORE. | This register, day 1 | open — G4 daily report must attribute catches |
| L13 | 2026-10-10 | **Scoped tests miss repo-wide guards.** A change to `src/` must also run the tests that scan all of `src/`. | `'draft'` literal caught only by CI (C-19, M-10) | open |
| L14 | 2026-10-10 | **Dry-run a rule against the real data before asking for its approval.** | The "folder" wording of row 4 was approved, then shown too narrow (C-20, M-12) | applied in law 0012 (dry run before the batch); **open** as procedure |
| L15 | 2026-10-10 | **Evaluation needs memory.** Findings that return every run unchanged turn review into ceremony. | CCC re-raised dismissed candidates every run (C-15) | applied (law 0012, 376f9580) |
| L16 | 2026-10-10 | **"Accepted" and "built" are different facts; so are "applied" and "accepted".** Check both directions. | ADR-094 accepted, never built; ADR-117/120/158 applied while "Proposed" (C-16) | open — a check for ADR deliverables (SPECGAP sees none) |
| L17 | 2026-10-10 | **A boundary held by attention fails; hold it by mechanism.** | `core_test` reached twice by scoped runs (M-01, M-08) | applied: `-m "not integration"` (memory) |

