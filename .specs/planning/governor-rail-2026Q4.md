# Governor operating rail — 2026 Q4

**Status:** committed 2026-09-21 on the governor's Path A instruction; signature is the governor's, below. Draft history: Written 2026-09-20 after a seven-hour session that closed
two loops, opened five findings, and left T0 unset. Amended the same night by core-9d
(review pass; amendments marked `◆`).

## The problem, stated honestly

Not focus. Not discipline. The instrument outruns one governor's decision capacity.

CORE's sensors, audits and reports surface findings faster than one person can
adjudicate them, and every finding is *real* — that is the whole point of the system.
Trying harder does not scale against an instrument that gets better every month. The
only thing that scales is deciding **in advance what will be ignored**.

Every rail below is one CORE already runs, pointed at the governor instead of the daemon.

◆ **One constraint on the whole document, learned tonight.** A rail nobody reads is a
declaration, not a rail — `permitted_tools` was read by zero lines of source for four
months and hid 99 % of the LLM bill behind an accurate-looking `[]`. So every rail below
names **its instrument and its reader**: where the fact is written, and which recurring
moment reads it. A rail without both is struck at the review date, not kept as intent.

---

## D1 — One bar per quarter, pre-declared

One falsifiable condition, written and dated before the quarter starts, with a fixed
review date. Not a goal list. Not a roadmap. One sentence that a bad quarter cannot be
talked into passing.

Same instrument as the G4 soak pre-declaration: the bar is fixed while clear-headed,
so it cannot be redefined at 1am into whatever happened to occur.

> **This quarter's bar** (governor, 2026-09-21): By 2026-12-18, in every calendar month from
> October, CORE lands at least 30 tested symbols, and more than were added untested by hand
> that month, through autonomous proposals with no per-test governor approval, each landed
> test carrying a recorded perturbation verdict.
>
> **Preconditions — due before 2026-10-01** (the bar's instruments; without them it reads
> zero or cannot be read; each is an `act` under D2 by construction):
> 1. **The envelope ADR** — `flow.build_test_for_symbol` becomes auto-approvable under
>    stated conditions (today no flow is: #853 ruling 6, `eb853e36` 2026-09-15; last
>    self-approved test-gen proposal 2026-08-26). Draft: `var/tmp/ADR-163-…md`.
> 2. **The monthly census counter** — per calendar month: symbols landed with a test through
>    autonomous proposals (real commit, `approved_by = autonomous_self_promote`) vs public
>    symbols added in governor-authored commits with no test referencing them. No instrument
>    exists today; per-symbol linkage does (`symbol_name` on every test-gen proposal).
> 3. **The perturbation verdict** — a fixed set of breaks applied to the tested symbol in
>    the sandbox after acceptance: return-value replacement and comparison/boolean
>    inversion; per test `killed` / `survived` / `not applicable`; recorded on the consequence
>    record; not blocking. Definition in the envelope ADR; no instrument exists today
>    (`perturbation` appears nowhere in src/, .intent/ or the ADRs as of 2026-09-21).
>> 4. **Scope** — widen `include_files` in `.intent/enforcement/config/test_coverage.yaml`
>    (42 files today; 135 symbols in scope, 112 uncovered per the 2026-09-20 census). At the
>    08-26 success rate with no retry on failure the current scope yields ~94 landable
>    symbols *ever* — below the 90 the bar needs by December, with October and November
>    consuming it. A few hundred visible uncovered symbols is the margin. Direction: packages
>    that are mostly pure logic — the five 08-26 failures were all route handlers and
>    renderers with DB or Rich dependencies. **Decided 2026-09-21 (governor): all 64
>    `src/mind/logic/**/*.py` files — including the 8 that shell out, so their failures stay
>    visible in the census as symbols CORE could not test.** `.intent/` edit, after T1.
>
> **Instrument for the bar:** the census counter (2), read monthly from the consequence log.
> **Reader:** the first session of each month writes the previous month's numbers into its
> D5 line; 2026-12-18 reads three of them.
> **Review date:** 2026-12-18 (Friday) — set 2026-09-20, hour eight, the one thing decided tonight

◆ **Instrument:** this file, committed at `.specs/planning/governor-rail-<quarter>.md`
(a planning artifact, not law — it governs the governor, not CORE; nothing in `.intent/`
reads it). **Reader:** D5's session-start line quotes the bar verbatim, so it is re-read
every session by construction.

◆ **Note on the empty slot.** D2 cannot run until this line is filled: "act only if it
blocks the bar" has no truth value against a blank. Tonight's table below was scored
against an *implied* bar (push + T0); if the real bar is something else, re-score it.

## D2 — Every discovery gets a disposition at the moment of discovery

Three outcomes, chosen immediately, never deferred:

- **act** — only if it blocks this quarter's bar ◆ *— and the blocking argument is
  written in one line at the moment of choosing, ADR-159 D3's own standard: "must be
  argued explicitly in writing … the finding must show that the trial's evidence is
  wrong, not merely that CORE could be better"*
- **file** — the default; an issue, then back to what was being done
- **drop** — explicitly, in one line, with the reason

The default is *file*, not *act*. A finding that is real, urgent-feeling, and unrelated
to the bar is still *file*. The cost of filing is a minute; the cost of acting is an
evening.

◆ **Instrument:** the issue itself. `file` = an issue with label `disposition:filed`;
`drop` = one line in the session's D5 record (no issue — an issue for a drop is a file
by another name); `act` = the one-line argument in the D5 record. **Reader:** D6's
weekly count, which only counts what carries the label.

## D3 — A cap on open governor decisions

At most **N** decisions may be open at once (ADRs owed, rulings pending, issues assigned
to the governor and blocking others).

At the cap, nothing new opens. New findings go to a backlog that is **not read** until
the review date. This is ADR-104's abandon-at-cap rail: a queue nobody can drain is not a
queue, it is a loop.

> **N =** _(to be set — pick a number that hurts slightly)_

◆ **A ratchet, not a cliff.** Measured 2026-09-20 22:40Z (`gh issue list --assignee
DariuszNewecki --state open`): 42 open assigned issues, of which decisions the governor
alone can make: #920, #917, #900, #897, #887, #816, #801, #891 (ADR, `status:blocked`),
and #808, which is *one* issue carrying **39 indeterminate findings needing triage**.
Off-GitHub, also open tonight: the G4 pre-declaration signature and T0; the envelope
ADR; ADR-161 acceptance; three drafts in `var/tmp/ingest-fix-drafts/`; 20 `pending`
test-gen proposals; #891's one ping. That is **≈ 16 decisions open**, one of which hides 39.

A cap set below that number starts tripped: at N = 5 the rail's first act would be
eleven sessions of pure closure before the quarter's bar may even be opened — it would
forbid the work it exists to protect, be broken in week one, and be dead for the quarter.
So N is not a cliff. **N starts at the measured count (16) and is non-increasing**: a
decision may be opened only by closing one first. It bites tonight (five findings would
have cost five closures), never forbids the bar, and converges without a moment where the
rule is absurd. This is also the faithful borrowing: ADR-104's cap bounds a *loop*, not a
backlog, and the Convergence Principle is a rate equation — a ratchet is a rate
constraint, a cliff is not.

> **N₀ =** 9 — measured 2026-09-21 by the D3 query after the `governor-decision` label was created, #808 split, and D7 written (#921–#925 + #917 #920 #900 #801; #897 #891 #887 moved to D7 under `disposition:ignored-2026Q4`; #918 closed on its commits; #919/#816 classified execution). The hand count of 16 on 2026-09-20 and the interim 12 are superseded. · **N is non-increasing** · **review-day target:** 8

#808 is counted as **one** until it is split. One issue holding 39 findings is a
cap-evasion device; the ratchet's pressure is what should force the split, not a
counting rule that absorbs it. ◆ **This makes N₀ = 16 wrong by construction**, and the
rail's first honest act is finding out by how much: splitting #808 into its real
decisions is the **precondition for D3 meaning anything**, not an item to schedule into
the quarter — it comes **before the signature**. Signing with #808 unsplit is signing a
cap whose starting number is known to be false. The split needs no bar: thirty-nine
findings triaged into clusters is adjudication, not strategy. Order for the next session:
split #808 and re-measure N₀ → fill D1 and D7 and sign → set T0.

◆ **Instrument:** the label `governor-decision` on exactly the issues that count, and
the query `gh issue list --assignee DariuszNewecki --state open --label governor-decision
--json number -q length`. Off-GitHub decisions get an issue or they are not open.
**Reader:** the same query, run at D5's session start; the number it returns is written
into the journal line, and it may not exceed the previous session's number. If it does,
the session's first objective is closing one.

## D4 — Containment: discovery expands only forward

A finding surfaced while working on something else never changes the current objective.
It is filed and left. The session ends on what it started on.

ADR-159 D3, applied to the governor. Tonight this rule was followed once (the
comment-matching false positive → cluster list) and broken four times.

◆ **Keep D3's exception, in D3's words.** ADR-159 D3 is not "never": *"Anything
discovered beyond a threshold's declared criteria is backlog, **unless it invalidates the
result of the trial in progress**."* Dropping the clause makes D4 stricter than the law it
cites, and it is exactly the clause under which hour 7 was legitimate: 2,160 unaccounted
paid calls inside a frozen 72 h window, from two workers declaring no LLM, would have
surfaced on day two as a recurring error signature and forced a C8 judgment mid-soak —
that *invalidates* the soak's evidence, not merely improves CORE. The rail should say
"unless it invalidates the bar's evidence, argued in one written line" — which is D2's
`act` clause. D4 without it will be broken again the first time it is right to break it.

◆ **Instrument / reader:** none of its own; D4 is D2 applied across a session boundary,
and D5's outcome line ("did the objective move") is what reads it.

## D5 — Every session declares its objective and its outcome

One line at the start naming what this session is for. One line at the end saying
whether it moved. Both recorded.

This is the cheapest instrument on the list and the one that would have caught tonight:
at hour four it would have read *"objective: push and set T0 — not moved."*

◆ **Instrument:** the memory journal already in use (`memory/journal.md`), one dated
entry per session: `objective:` / `bar:` (quoted from D1) / `open decisions:` (D3 query
result) / at close `outcome: moved | not moved` + the `drop` and `act` lines from D2.
**Reader:** the next session's start — it opens the journal before anything else (the
existing "session resume — internalize closures" norm, made mandatory rather than
habitual). A session whose start line names the same objective as the previous
"not moved" is the signal D6 counts.

◆ **Also the rail for the execution arm.** Claude Code's own memory already carries
"classify every task PRODUCT > EXPERIMENT > CEREMONY; stop after 2 non-product tasks".
D5 is that rule at the governor's altitude; the two should cite each other so a session
that drifts is caught from either side.

## D6 — Weekly convergence check on the governor's own queue

Decisions closed vs decisions opened, per week. The same law CORE is judged by.

Two consecutive diverging weeks means one of two things is wrong, and the review picks
which: the cap (N too high) or the bar (too broad for one person).

◆ **Citation:** ADR-014 — "The Convergence Principle is a rate equation: resolutions must
exceed creations." **Instrument:** two `gh` queries on the `governor-decision` label
(`--state closed --search "closed:>=<week-start>"` vs `--search "created:>=<week-start>"`),
run on a fixed weekday, numbers appended to the journal. **Reader:** the review date, and
the governor on the day it is run — two diverging weeks is a *finding about the rail*, and
by D2 it gets a disposition on the spot.

## D7 — The ignore list, written now

What is deferred by construction this quarter, named in advance so that picking it up
is a visible decision rather than a drift:

> **Decided 2026-09-21 (governor).** Deferred this quarter by construction:
> - **packaging and onboarding polish** — #892, #795, #796, #797, #888
> - **the external trial (bar candidate B)** — with #897 (Trial-0 evidence custody) and #891
>   (gate evidence observability); ADR-159 Trial 0-R1 authorisation stays where it is
> - **embedding consolidation** — #887 (full re-embed)
> - **the audit-engine false-positive cluster** — #858, #869, #870, #876, #902, #904, plus the
>   comment-matching `fix.path_resolver` false positive (unfiled); #876 is the one that could
>   fake a C8 signature — if it does, D2's `act` clause covers it
> - **core-platform**
> - **G11 residual** — #919 (paper drift; execution, not a decision)
> - **the `permitted_tools` enforcement rule** (`var/tmp/ingest-fix-drafts/rule-workers-no-full-audit.md`)
>   — safe to ignore *only because* soak condition **C9 was adopted** into the pre-declaration
>   2026-09-21 as the runtime verdict for the same property; the rule follows on a quiet week
>   once C9 has shown what normal looks like
>
> **Not on the list, deliberately:** #920 (reject without disposition) — a rejection that does
> not reject collides with the bar the first time a generated test is rejected; it stays a
> decision. #808's five clusters (#921–#925) are decisions, not ignores.

◆ **On the last candidate:** the `permitted_tools` rule is already drafted
(`var/tmp/ingest-fix-drafts/rule-workers-no-full-audit.md`) and applying it is a Path A
edit of minutes, so ignoring it is a real choice, not a saving. It is a *safe* ignore only
because soak condition C9 (`llm_exchange_log` per role per day vs a T0 baseline) is the
runtime verdict for the same property — if C9 is not adopted into the pre-declaration,
the rule should come off this list. Ignore one or the other, not both.

◆ **Instrument:** this section, plus label `disposition:ignored-<quarter>` on the issues
it names, so a session that touches one trips D2 visibly. **Reader:** the review date.

---

## What this would have done to tonight

| hour | what happened | under the rail |
|---|---|---|
| 1 | #901 closeout reviewed, D10 identified | act — blocks nothing, but it was the session's objective |
| 2 | reaper pass, delegate-to-human ruling | act — same thread |
| 3 | G4 pre-declaration hardened | act — same thread |
| 4 | strategy conversation, quarterly bar discussed | **new objective** — should have been a new session |
| 5 | coverage census, flow anatomy, cost trace | file — none of it blocked the push |
| 6 | precedent check, envelope ADR scoped | file |
| 7 | LocalCoder spend traced, two workers fixed | ◆ **act** — the fix invalidates the soak's evidence if left (2,160 undeclared paid calls in-window; a DeepSeek hiccup lands as a C8 signature in two "no-LLM" workers). The *trace* was a hour-5 by-product and belongs to "file"; the *fix*, once the trace existed, met D2's act clause. What the rail would have changed is the order: T0 signed at hour two, this fix as next session's first `act`. |

Outcome unchanged in quality. Outcome changed in sequence: the push and T0 happen at
hour two, and hours four through seven become next week's declared work instead of
tonight's undeclared work. ◆ *Hour 7 excepted: it would have been next week's declared
work and still an `act`, and the soak would have started with the old bursts inside its
window — which is the one thing the rail must be allowed to prevent.*

---

## Signature

> Signed: _(governor — name, date)_

## Amendment

This document is amended by the governor at a review date, not mid-session. A rail
changed while it is inconvenient is not a rail.

◆ **Direction of change, borrowed from ADR-160 D4:** tightening (a lower N, a narrower
bar, a longer ignore list) may happen at any time; loosening happens only at the review
date, with the D6 numbers in hand. Fail-closed for the governor as for CORE.

◆ **Who wrote it, and what the review must therefore ask.** This is a rail against the
governor's own drift, written by the governor and the two agents that participated in
that drift. Not disqualifying — but the 2026-12-18 review must answer **two** questions
separately, and record both: *was the rail followed* (the D5/D6 numbers say), and *did
it help* (did the bar move because of the rail, or despite it, or would it have moved
anyway). The second is the one nobody asks of their own system; a rail that was followed
and did not help is struck, not amended.

◆ **What this document is not:** law. It lives in `.specs/planning/`, is signed by the
governor, and binds the governor. CORE's daemon does not read it; Claude Code sessions
read it through D5. If any rail here later wants enforcement by CORE itself (D3's cap as
a blackboard SLA, for instance), that is an ADR, and it is on the D7 list until then.

---

## ◆ Appendix — candidates for the two blanks (the governor's to choose, not the reviewer's)

### The bar — three falsifiable sentences, each already instrumented somewhere

| | candidate | evidence that decides it | what it depends on | what it forbids you from ignoring |
|---|---|---|---|---|
| A | "A 72-hour G4 soak on a frozen `main` passes every pre-declared condition C1–C9 with no disqualifier, signed in `.specs/attestations/`." | the pre-declaration's §5 queries (already written) | T0 being set; the ingest fix live (done 20:35Z) | nothing on the D7 candidate list |
| B | "ADR-159 T-B: Trial 1 on an external repository succeeds against its declared pass criteria with honest, reconstructable evidence." | ADR-159 D6/D9 evidence apparatus; runner c0ccd6ce certified (#895) | A first (the soak is Trial 1's precondition by ADR-159's own order) | #897 (evidence custody), #891 (evidence observability), the envelope ADR if Trial 1 needs test-gen to fire |
| C | "An adopter installs CORE from PyPI onto a fresh machine and reaches a green `core-admin code audit` without governor intervention." | a cold run from the real CLI (#892 says `project new` has never worked from a clean install) | packaging and onboarding polish (#892, #795, #796, #888) | exactly the "packaging and onboarding polish" line on the D7 list — so B and C cannot both be true of the same quarter's lists |

A is two weeks of work and is what tonight was for; it is too small to be a quarter's
bar and too near to be ignored — it is the first `act` under whatever bar is chosen. B is
the thesis and is what the whole apparatus since ADR-159 exists to test. C is the
product and is the one the D7 candidates would have to be rewritten for. **The record
argues for B**, with A as its stated precondition and C explicitly on the ignore list —
◆ *and that sentence is a reviewer choosing the governor's bar in everything but the
signing. B commits the quarter to proving the thesis rather than shipping the product;
that is the fork circled for two hours tonight without a decision. Sleep on B
specifically. If C is chosen instead, rewrite the D7 list before signing, not after.*

### The review date

Q4 2026 runs 10-01 → 12-31. A review date must be a day the governor will actually sit:
**2026-12-18 (Friday)** leaves the holidays outside the quarter's evidence and gives
D6 eleven full weekly readings. If the bar is A rather than B, the quarter is wrong-sized
and the review date should be T1 + 7 days instead.

### The ignore list — what the record says about each candidate

| candidate | issues | keep on the list? |
|---|---|---|
| G11 migration safety | ADR-162 complete (v2.10.2); residual in #919 (paper drift) | yes — closed by release; #919 is prose |
| audit-engine false-positive cluster | #858, #869, #870, #876, #902, #904 | yes — none blocks A or B; note #876 (timeout reported as BLOCK) is the one that could fake a C8 signature; if it does, D2's `act` clause covers it |
| core-platform | — | yes |
| packaging and onboarding polish | #892, #795, #796, #797, #888 | yes **if the bar is B**; impossible if the bar is C |
| reject-without-disposition | #920 | yes — but it is also the shape D2 needs for governor "no"s; if D2 is signed, #920 is half-answered by this document and should say so when closed |
| `permitted_tools` enforcement rule | drafted, `var/tmp/ingest-fix-drafts/` | yes **only if C9 is adopted** into the pre-declaration; otherwise apply the rule (minutes) and ignore C9 instead |
| not on the list but should be decided | #808 — 39 indeterminate findings under one issue | **not ignorable and not one decision**: split it into ≤ 5 clusters this quarter or the ratchet is fiction |
| not on the list, safe to add | #887 (embedding consolidation = full re-embed), #896 (blackboard index), #848 (CI perf), #774 (literal sweep), #819, #816 | yes — none touches A or B |

### Now, or sleep on it

D1's own sentence: "the bar is fixed while clear-headed, so it cannot be redefined at
1am." It is hour eight. **Set the review date tonight** — it is one date and binds
nothing else — and make "fill D1 and D7, sign the rail" the declared objective of the
next session's first D5 line. That gives the rail an honest first journal entry and
keeps its first decision from being made under the condition it was written to prevent.
