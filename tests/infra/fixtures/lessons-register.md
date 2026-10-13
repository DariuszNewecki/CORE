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
| L18 | 2026-10-10 | **Before saying a capability does not exist, search every surface that could hold it** — both CLIs, the API, other repositories. | "No approve command" — it was in core-cli (M-14) | open |
| L19 | 2026-10-10 | **A change to a governed shape carries its contract in the same batch.** The audit sees the gap only as `info`. | U1 provenance fields (C-22, M-15) | applied in law 0014; **open** as habit |
| L20 | 2026-10-10 | **A rule enforced only at one producer's boundary hides debt everywhere else.** | 41 test files break Class B rules unseen (C-26) | open |
| L21 | 2026-10-10 | **What CORE documents and tests against is the released version of a sibling package, not the local build.** | core-cli installed unreleased (C-24, M-17) | applied: release before declare (ADR-167 D2) |
| L22 | 2026-10-10 | **A docstring that says "cached" is a claim; measure it.** Performance defects hide behind it. | PatternValidators (C-25) | applied (A-19) |
| L23 | 2026-10-10 | **One real end-to-end run finds what unit tests cannot.** U8 found two defects that every test had passed. | C-31, C-32 | applied: acceptance is a real run |
| L24 | 2026-10-10 | **"Orphan" needs an owner check.** A cleanup that removes everything matching a name removes live work too. | H-17 | applied (A-26) |
| L25 | 2026-10-10 | **"Done" is proven by the effect, not by an exit code.** `git apply` exited 0 and changed nothing. | H-18 | applied (A-26) |
| L26 | 2026-10-10 | **Step 0 applies to my own plans.** Read the decisions on a subject before designing it. | C-35, M-25 | open — habit |
| L27 | 2026-10-10 | **Restart after every commit while the services run the dev tree** — until D2, when deployment becomes the governor's act. | C-33, M-23 | open → superseded by D2 |
| L28 | 2026-10-11 | **A "deviation" written in build notes is still a shipped gap.** Writing it down is not closing it; close it, or file it with an owner. | C3's boot-recovery window (C-46, M-27) | applied (A-40); **open** as habit |
| L29 | 2026-10-11 | **When the layout changes, law terms defined against the old layout must be re-defined in law, and the code re-checked against the new definition.** "Code on disk = `src/`" silently became "never stale". | C4 vs ADR-030 (C-47, M-29) | applied: ADR-030/169 amendments (0018), A-42 |
| L30 | 2026-10-11 | **Prove a relocation by running the real thing in the new layout and diffing.** The probe found the one cwd dependency that recon missed. | D2 audit probe (C-45) | applied (A-39); **open** for the daemon path, proven at go-live |
| L31 | 2026-10-11 | **A route that writes where law forbids writing is dead code with a URL.** Grepping runtime writes into law found a broken endpoint. | `/fix/ir` (C-48, H-21) | applied (A-40) |
| L32 | 2026-10-11 | **Text-matching hooks fire on text, not intent.** A command that only writes the words `git commit` triggers the commit gate. | verdicts.jsonl 10:12:33 | open — harmless today (an extra audit); matters if a hook ever acts |
| L33 | 2026-10-11 | **"Explicitly set" is not a fact a model keeps for you.** A validator that fills a field marks it set; decide by value, not by provenance flags. And "inert" is a claim to test in every place the code runs, worktrees included. | `law_roots` vs C1 (C-50, M-31) | applied (A-43, regression test) |
| L34 | 2026-10-11 | **A procedure run by hand decays within days; what must be recorded must be recorded by the tool.** | Rehearsal ledger: ask times stopped at 0006, line counts at 0004, 0012's line lost (C-53, M-33, M-34) | applied: ADR-170 amendment (0019) — `law apply` writes every field |
| L35 | 2026-10-11 | **A claim in a commit message is not evidence.** "Ledger appended" and "no change while unset" were both false; only the artifact or a run proves it. | M-32, M-33 | open — habit; Stage 2's custody rule for the ledger |
| L36 | 2026-10-11 | **Check an amendment against the decision it amends.** A new item that strengthens one property can break the property the decision exists for. | 0019 item 3 vs ADR-170 D2 (C-54, M-35) | open — habit: re-read the amended ADR's D-sections before asking |
| L37 | 2026-10-11 | **Prove a tool in the shape it will run, not in a richer one.** `check-tree` passed in a full worktree; `law apply` gives it a smaller tree. The installed-wheel test found it. | C-57, M-38 | applied: `test_law_apply_installed_wheel.py`; **open** as habit (cf. L30) |
| L38 | 2026-10-11 | **An audit that imports code audits the code it imports, not the code it was pointed at.** | C-58, M-37 | applied: 8e9b5408 (reports "not evaluated"; `PYTHONPATH=<tree>/src` evaluates the tree) |
| L39 | 2026-10-11 | **A security rule written in law must be tested against the mechanism's defaults.** "sudo asks for a password" was true and still let a cached login approve. | C-60, M-41 | applied: `timestamp_timeout=0`, acceptance check 3b (0022) |
| L40 | 2026-10-11 | **Protection by ownership must cover every parent, and every account that can bypass ownership.** | C-61, M-42 | applied: setup step 5a/5b, rename probe |
| L41 | 2026-10-11 | **A root script must never inherit a terminal.** Any command can stop to ask. | M-44 | applied (A-54) |
| L42 | 2026-10-11 | **A failed write that leaves the new bytes in place makes the retry look like no change.** The 0025 ledger line says 0 lines changed and no computed warning. Compare against the last committed law, not the destination. | C-66, E-38 | open — #966 |
| L43 | 2026-10-11 | **"The latest file" by name sort is whatever sorts last.** The wheel test installed 2.11.0 once `dist/` was cleared. Name the version under test. | A-58 | applied |
| L44 | 2026-10-11 | **A filter that drops what it cannot attribute turns "nothing checked" into "clean".** | A-60 | applied (8e9b5408) |
| L45 | 2026-10-11 | **An account the law says must never approve can approve while it holds sudo.** 0025's first write ran as `core-darek` (E-38). The must-never in ADR-068 A4 is a live gap, not a future one. | E-38 | open — governor decision on `core-darek`'s sudo/docker; approver binding (ADR-132 D10.11 step 4) |
| L46 | 2026-10-11 | **A rule repeated as text for months is a wish; enforce it.** The governor's "≤5 lines, no narration" rule failed in session after session as memory notes. | governor | applied: Stop hook `core-chat-length.sh` (0026); memory hot index cut to 8 rules |
