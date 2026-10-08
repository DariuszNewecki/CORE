---
kind: adr
id: ADR-170
title: 'ADR-170 — The law has a custodian: proposed by anyone, checked by CORE, approved by the governor, written by core-law'
status: accepted
---

<!-- path: .specs/decisions/ADR-170-law-custodian.md -->

# ADR-170 — The law has a custodian

**Date:** 2026-10-08 (draft 2); accepted 2026-10-08
**Status:** Accepted 2026-10-08 by the governor (option A: accept, and start the D0 rehearsal now)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-10-08)

**Grounds:**
- Charter §6: law precedes machinery.
- ADR-168 D1–D3: every AI is a producer; an assistant may propose but never approve; no conversational authority. D4: CORE's own development adopts it first.
- ADR-132 D10.1: a local caller's identity comes from the kernel, never from a claim. D10.8 and its parking addendum: bytes the assistant writes must not run with authority. The equivalent-routes argument (R1–R4) sets the honesty bar for every claim made here.
- ADR-101 D1: a commit contains only bytes its author produced.
- The ADR-168 experiment (2026-10-04 to 06): a decision can be rehearsed before it is built, and evaluated from its own log.

**Closes (when Stages 1 and 2 are live):** #945.
**Relates:** #942 (governor stamp identity, parked under ADR-132); ADR-168 D2 "Proposal".

## Governor decision required

1. **Adopt the separation (D1).** Anyone may propose a change to the governed text. CORE checks it. Only the governor approves. Only `core-law` writes, and that includes the governor's own changes.
2. **Rehearse it from acceptance (D0).** Everyone acts as if Stage 1 were live, with nothing built yet. The rehearsal log decides what Stage 1 builds.

## Acceptance (2026-10-08)

The governor accepted both decisions in session: the separation (D1) and the rehearsal from acceptance (D0). This ADR is itself the first proposal under D0 (`0001-adr-170`). The approval was given in chat, as D0's stand-in for the sudo password.

## Context

`.intent/` is the law the runtime and the gates read. `.specs/` is the reasoning and decision history behind it. `CLAUDE.md` and `.claude/` are the contract and the hook that bind the coding assistant. All of them are meant to be human-authored. Today:

| Path | Owner, mode | Who can change it |
|---|---|---|
| repository root | `core:core-dev 2775` | every `core-dev` member can rename or replace any entry, including the whole `.intent/` directory |
| `.intent/`, `.specs/` | `core:core-dev 2775` | the governor, the services, the assistant |
| `CLAUDE.md` | `core-claude:core-dev 664` | **owned by the assistant it governs** |
| `.claude/settings.json`, `.claude/hooks/` | `core:core-dev`, group-writable | the assistant can switch off its own pre-commit verdict (ADR-168 D4.1) |

The only thing between the assistant and these files is prose in the file the assistant owns. CORE detects uncommitted law changes (law drift, DEGRADED). After a commit, a change is simply the new law.

The realistic risk is not an assistant attacking CORE. It is **drift**: an assistant "fixing" a rule so that a check goes green, softening its own contract, or tidying the law without asking. A gate the producer can edit is not a gate.

**Rate of change** (counted from git on 2026-10-08):
- **Rules:** 96 (2026-03-01) → 255 (2026-08-01), then flat: 257, 260, 265 today. The rulebook has stabilised at about +5 a month.
- **Lines changed in `.intent/` per month:** May 15,500; Jun 4,300; Jul 9,000; Aug 2,500; Sep 1,000. October's 866 lines in 8 days come from the exception clean-up.
- **Commits touching `.intent/` or `.specs/`:** still about 27 a week on average, mostly small edits (config, worker declarations, exception removal, headers) and ADR text.

So changes worth the governor's attention are rare, and housekeeping is frequent. The procedure has to make the rare ones stand out, not bury them.

## Decisions

### D1 — Three roles, never merged

| Role | Who | Can |
|---|---|---|
| Proposer | anyone: the assistant, another AI, the governor | write a proposal; never governed text |
| Approver | the governor only | approve or refuse; never write |
| Writer | `core-law` only | write exactly the approved bytes; never decide |

CORE sits between proposer and approver as the **checker**. It advises; it does not decide (D5).

### D2 — Governed text and its custodian

**Governed text** is:
- `.intent/**` (the law);
- `.specs/**` (the reasoning and decisions);
- `CLAUDE.md` and `.claude/settings.json` and `.claude/hooks/**` (the assistant's contract and its enforcement hook).

`.claude/settings.local.json` and the assistant's private memory are not governed text.

**`core-law`** is a system account with no login shell and no password.
- It owns the governed text. Files are `0644` and directories `0755`, so everyone reads and only `core-law` writes. The setgid bit is removed in these trees.
- **The names are protected too, not only the contents.** No other account may rename, replace or delete `.intent`, `.specs`, `CLAUDE.md` or `.claude` in the repository root. The mechanism (the sticky bit on the root, or an equivalent) is chosen in Stage 1. It must be proven against `mv .intent x && mkdir .intent` as `core-claude`, and against git checkout of root-level files still working.
- **It runs only code the assistant cannot change.** `core-law` runs `core-admin` from its own venv, installed from a **released** `core-runtime` wheel (proposed: `/opt/core-law/venv`, owned by `core-law`). It never runs the development tree's code, so D10.8 routes R1 and R2 do not reach it.
- **It never runs git and never executes repository code.** It reads the law as data, writes files and writes the ledger (D4). Routes R3 (`.git/config`, hooks) and R4 (repository tests, `conftest.py`) do not reach it.
- The services (`core`) never write governed text. For `.intent/` that is IntentGuard's hard invariant. A recon on 2026-10-08 found no runtime writer of `.specs/` (`sync_vocabulary` stages to `var/drafts/`). Stage 1 re-proves this with a day of service journals.

### D3 — The amendment procedure

1. **Propose.** A proposal is normally **a working session's whole batch**. The proposer writes complete new files, not diffs, under `var/law-proposals/<id>/`, mirroring repository paths, plus `proposal.md`, which records:
   - what changes and why;
   - the files to remove, under "Remove";
   - the ADR or issue each change rests on.
2. **Check.** CORE builds the would-be tree in a scratch copy and runs D5. The report leads with refusals and warnings; housekeeping comes last.
3. **Approve and write.** The governor runs one line:
   ```
   sudo -u core-law /opt/core-law/venv/bin/core-admin law apply <id>
   ```
   `law apply`:
   1. reads the proposal **once, into memory**, and hashes it;
   2. runs D5 on exactly those bytes and shows the report;
   3. asks the governor to type the proposal id. Any other input aborts and writes nothing;
   4. writes the in-memory bytes;
   5. appends the ledger line (D4).
4. **Commit.** The assistant or the governor commits the changed files and the ledger line together, naming the proposal id. ADR-101 holds: the commit carries only `core-law`'s bytes.

An emergency (production down, and law the cause) follows the same procedure with a one-file batch. There is no fast lane except root (D6).

### D4 — The ledger

`.intent/custody/ledger.jsonl` is append-only and written only by `core-law`. One line per applied proposal records:
- the proposal id;
- the approver, taken from `SUDO_USER`, which sudo sets and the caller cannot supply;
- the UTC time;
- every path written or removed, with its new sha256;
- CORE's verdict and every warning the governor accepted;
- a signature over the line, made with `core-law`'s SSH signing key (`ssh-keygen -Y sign`). The private key is readable by `core-law` only.

The public key is in `.intent/custody/allowed_signers`. It is governed text, so changing it goes through D3.

### D5 — CORE checks; the governor decides

**Refuse: mechanical breakage.** Governed text that would break CORE is never written, whoever approves it:
- `.intent/` and `.specs/` schema validation (`MetaValidator` and `SpecsDocValidator`, as `core-admin constitution validate`);
- `architecture.intent.references_resolve`;
- the law loading at all (`IntentRepository` initialises on the scratch copy);
- `.claude/settings.json` parsing as JSON.

**Warn, at the top of the report.** The governor may approve over a warning, and an accepted warning is recorded in the ledger:
- a rule added or removed;
- an enforcement level changed, with lowering (blocking → reporting → advisory) marked as **weakening**;
- a `scope.excludes` entry added, or `applies_to` narrowed;
- `.intent/constitution/`, `.intent/META/`, `.intent/rules/governance/` or `.intent/custody/` touched. This is always flagged, as the constitutional core. Changes to the "law about law" are checked by its current version, like a constitution's amendment clause;
- `CLAUDE.md` or `.claude/` changed: the assistant's own contract or hook.

**Housekeeping, listed last:** everything else, grouped by directory with counts.

CORE has no veto beyond mechanical breakage. Otherwise CORE could lock out its own governor.

### D6 — The approval is the sudo password

The governor's sudo password is the approval. The kernel and sudo establish who approved, in the spirit of ADR-132 D10.1. No claim is taken from a file, a flag or a chat message, so this needs no API, no database and no #942 work.

- Sudo to `core-law` **must ask for a password**. A `NOPASSWD` rule for that target is forbidden.
- Root can override everything. That is the governor's break-glass, by design. A break-glass change is followed by a proposal that brings the ledger back in line (D7 flags it until then).

### D7 — The landing check

The lock stops direct writes. It does not stop a commit that changes governed text without touching the working tree (git plumbing). On this server such a commit does not change the law in force, because CORE reads the files on disk. It does change the law for every checkout of the pushed branch.

A new rule, `governance.law.custody_required`, says that every governed-text file changed in a commit must match a sha256 in a validly signed ledger line. CORE's audit evaluates it, and CI already runs that audit. It follows the usual ramp: reporting, then blocking once the history since activation is clean. Commits before activation are exempt.

### D8 — Stages

| Stage | Contents | When |
|---|---|---|
| **0, Rehearsal** | D0 | from acceptance |
| **1** | D2–D6: the account, the ownership and name protection, `law apply` (shipped in a release), the ledger, and CLAUDE.md's gate section rewritten as "propose" | after the rehearsal evaluation; needs a release and one root session |
| **2** | D7: `governance.law.custody_required`, reporting, then blocking | right after Stage 1 |
| **3** | CORE verifies the custody signature when it **loads** the law and refuses unsigned law: law as a signed bundle from a custodian, the OPA-style end state. The ADR-168 D2 "proposal" capability writes into `var/law-proposals/` | **only on a trigger:** a second human governor, law served to more than one CORE instance, or an adopter asking for it |

### D0 — The rehearsal

From acceptance until Stage 1 is live, everyone acts as if it were. Nothing is built.

**The assistant:**
1. Never writes governed text directly. Every change goes into a proposal under `var/law-proposals/<id>/`, following D3 step 1. A session's changes accumulate in one open proposal.
2. Before asking for approval, runs the D5 checks by hand: it applies the batch in a scratch worktree under `var/tmp/`, then runs `core-admin constitution validate` and the full offline audit (`core-admin code audit --offline`, as the pre-commit hook runs it) there. `code verify` alone is not enough: it skips whole-repository rules, which is how proposal 0001 missed its manifest entry. It lists the warnings by the D5 categories. The report states plainly that the checks were run by the assistant, not by `core-law`.
3. Asks for approval **once per batch**, normally at the end of a session, or earlier if the work cannot go on without it. The report leads with refusals and warnings.

**The governor** approves in chat. That chat answer **stands in** for the sudo password. It carries exactly the authority that a Path A confirmation carries today, no more. It is recorded as a stand-in, never as an authenticated approval.

**On approval, the assistant:**
1. copies exactly the proposal's bytes into place and checks their sha256 against the report;
2. appends a ledger line to `var/law-custody/rehearsal-ledger.jsonl`, outside `.intent/`, because the rehearsal ledger is not law. The line records the D4 fields plus `"rehearsal": true`, no signature, and the friction notes below;
3. commits the files and names the proposal id.

**Friction log.** Each line also records:
- the number of files and the lines changed;
- the warnings by category;
- the minutes from asking to approval;
- whether work stalled while waiting;
- anything the procedure got in the way of.

**What the rehearsal cannot prove.** It does not test the lock, the name protection, `law apply`, the signature or the landing check. It tests the **workflow**: batch sizes, warning rates, approval latency, and whether the report helps the governor decide. The lock is tested in Stage 1's acceptance checks.

**Evaluation.** After two weeks, or ten proposals, whichever comes later. The evaluation comes from the rehearsal ledger, like ADR-168's from `verdicts.jsonl`. It decides whether the batch granularity, the warning set and the report order stand, and then whether Stage 1 is built as written.

**Exception.** Only the governor may write governed text directly during the rehearsal. When they do, they say so, and the assistant records it as a rehearsal break-glass line.

## What this does and does not claim

- **Stops (Stage 1):** the assistant, the services or a slip of the governor's own hand writing governed text directly, or swapping it out by renaming. Every change becomes a deliberate, recorded governor act.
- **Detects (Stage 2):** governed text committed without a matching ledger line.
- **Does not stop, until ADR-132 D10.8:** a deliberately deceptive assistant changing the audit engine in `src/` so that `custody_required` stops firing. The equivalent-routes argument applies. Nothing may describe the law as tamper-proof against a deliberately deceptive assistant. The claim is: **drift and convenience edits are prevented; circumvention leaves evidence.**
- **During the rehearsal:** nothing is prevented. The discipline is the assistant's own, recorded in a ledger the governor can read. The rehearsal is an experiment, not a control, and is never described as one.

## Is this overengineering?

Stage 3 would be, today, so it waits for a trigger, as #962 (sandboxing) did. Stages 0–2 are not: they are one procedure, one account, one command, one append-only file and one rule. They close the place where CORE's central claim (AI output is not trusted by default) fails at its own root, for the threat that actually occurs: drift.

## Consequences

- **Cost to the governor:** about one approval per working session. In Stage 1, that is one pasted line, a password and a typed id.
- **Cost to the assistant:** it drafts every governed-text change as a proposal. CLAUDE.md Paths A, B and C are replaced by D3 (Stage 1), and suspended in favour of D0 during the rehearsal.
- **Code depending on new law** waits for its batch's approval. The friction log measures how often that happens.
- **`git pull` or checkout** that changes governed text fails for accounts other than `core-law` (Stage 1). On this server governed text originates here, so this is rare, and it is resolved by applying the same bytes as a proposal.
- **Releases:** `law apply` must ship in a release before Stage 1 can start, because `core-law` runs released code only.

## Explicitly not decided here

- **Adopters:** how much of this ships as a product feature. `law apply` and `custody_required` work in any repository; the OS account is a recommendation, not a requirement. This belongs in its own decision, after Stage 1 runs on CORE.
- Multi-governor approval (two signatures).

## Acceptance checks

**Rehearsal (Stage 0):**
1. From acceptance, `git log` shows no commit touching governed text without a matching rehearsal-ledger line, except recorded break-glass.
2. The evaluation is written from the ledger and handed to the governor.

**Stage 1:**
3. As `core-claude` and as `core`: writing, renaming or deleting any governed-text file or tree is denied (including `mv .intent x`).
4. As `core-darek` without sudo: the same.
5. A schema-invalid proposal: `law apply` refuses it; nothing is written and no ledger line is added.
6. A proposal lowering a blocking rule: the warning is shown first. On typing the id, the files are written, and the ledger records the accepted warning and `SUDO_USER=core-darek`.
7. Editing `var/law-proposals/<id>/` after `law apply` has read it does not change what gets written.
8. Git checkout and commit of non-governed root files still work for `core-claude`.
9. The services run for a day with no permission errors on governed text in the journal.

**Stage 2:**
10. A commit changing `.intent/` through git plumbing, with no matching ledger line, is flagged by `governance.law.custody_required` in CI.
