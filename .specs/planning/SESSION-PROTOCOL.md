<!-- path: .specs/planning/SESSION-PROTOCOL.md -->

# CORE — Session Protocol

**Status:** Active
**Authority:** Policy
**Scope:** Opening, running, and closing a CORE working session
**Last revised:** 2026-07-27

---

## 1. Purpose

This document defines how a CORE working session establishes state, selects work, maintains scope, records evidence, and closes.

It applies regardless of whether the session uses:

* A connected GitHub repository.
* A local development clone.
* An isolated clone.
* Claude Code.
* Codex.
* Another executor.
* A human-operated shell.

Durable architectural reasoning remains under `.specs/`. Runtime governance remains under `.intent/`. Operational work tracking remains in GitHub Issues, pull requests, actions, releases, and commit history.

Long narrative session handoffs are not maintained. A session must be reconstructible from authoritative artifacts and repository history.

---

## 2. Where things live

| Location                   | Role                                                                          | Cadence                                                        |
| -------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `.specs/decisions/`        | ADRs: durable architectural decisions and rationale                           | Append-oriented; revised only when the decision itself changes |
| `.specs/papers/`           | Constitutional and architectural papers                                       | Durable; revised when the model changes                        |
| `.specs/northstar/`        | Strategic direction                                                           | Rarely changed                                                 |
| `.specs/requirements/`     | Requirements and acceptance contracts                                         | Updated with governed feature arcs                             |
| `.specs/concepts/`         | Pre-decision concepts and proposals                                           | Updated until accepted, rejected, or superseded                |
| `.specs/attestations/`     | Evidence syntheses and acceptance records                                     | Created for bounded acceptance events                          |
| `.specs/state/`            | Dated investigations and historical state snapshots                           | Append-oriented                                                |
| `.specs/planning/`         | Active planning and operating protocols                                       | Updated when operating state changes                           |
| `.specs/planning/archive/` | Frozen historical plans                                                       | No operational authority                                       |
| `.specs/META/`             | Schemas and conventions governing specification documents                     | Updated when conventions change                                |
| `.intent/`                 | Runtime governance law: constitution, rules, mappings, declarations, taxonomy | Updated through governed change                                |
| `.intent/CHANGELOG.md`     | Constitutional change history                                                 | Updated when constitutional changes land                       |
| `CLAUDE.md`                | Claude Code executor contract                                                 | Updated when executor discipline changes                       |
| GitHub Issues              | Open work, hazards, defects, questions, governance debt, verification gaps    | Updated during the session                                     |
| GitHub Pull Requests       | Review and hosted-CI evidence surface                                         | Used when the workstream requires it                           |
| GitHub Actions             | Hosted verification evidence                                                  | Run when applicable                                            |
| GitHub Releases            | Published capability milestones                                               | Governor-authorized                                            |
| Git commit history         | Authoritative record of repository changes                                    | Produced as work lands                                         |
| Local working tree         | Current uncommitted or unpushed implementation state                          | Ephemeral but authoritative for that clone                     |
| Isolated clone             | Bounded implementation, acceptance, or cold-room state                        | Explicitly identified by path, branch, and SHA                 |

Gitignored or external commercial material may exist outside the published repository. It must not be assumed visible to an architect or external operator.

No new `handoff-*.md` session narratives are produced.

---

## 3. State authority

Different questions require different authorities.

| Question                                  | Primary authority                                       |
| ----------------------------------------- | ------------------------------------------------------- |
| What is published on `main`?              | Remote GitHub repository                                |
| Does a remote branch or SHA exist?        | Remote Git refs or GitHub API                           |
| What is in an unpushed branch?            | The local clone containing it                           |
| Is the working tree dirty?                | Local Git state                                         |
| What issues and PRs are open?             | GitHub                                                  |
| What does the runtime currently report?   | Live CLI, database, API, and services                   |
| What decision governs this work?          | Accepted ADR, constitution, rule, paper, or requirement |
| What did a frozen acceptance run prove?   | SHA-bound test output, report, and attestation          |
| What did an older context packet contain? | That packet only, as of its generation time             |

A context packet is a convenience snapshot, not an authority over newer state.

Remote state, local state, runtime state, and evidence state must not be collapsed into one generic concept of “the repo.”

---

## 4. Session opening

Seven steps. Read and establish state before authorizing implementation.

### Step 1 — Load the interaction contract

The architect loads:

`.specs/planning/INTERACTION-CONTRACT.md`

before substantive analysis.

A fresh architect instance that has not loaded it is not operational.

### Step 2 — Establish the target state surface

Before discussing implementation, establish which state is in scope:

* Repository.
* Clone or execution environment.
* Branch.
* HEAD SHA.
* Base branch or base SHA.
* Dirty or clean working-tree status.
* Remote configuration.
* Whether the relevant branch and commits are pushed.
* Whether a candidate is frozen.

For a remote-only planning task, the connected GitHub repository may answer this directly.

For local or isolated work, the executor reports the state.

Canonical local identity prompt:

```text
Before doing any implementation, report the repository identity:

1. pwd
2. git status --short --branch
3. git branch --show-current
4. git rev-parse HEAD
5. git log -1 --oneline
6. git remote -v
7. git merge-base HEAD main
8. whether HEAD and the current branch are reachable from origin

Do not edit, stage, commit, push, merge, or clean anything.
```

A SHA that exists only locally must be labelled **local-only**.

### Step 3 — Read the governing context

Read the authorities relevant to the proposed work:

* Current file or subsystem.
* Referenced ADRs.
* Relevant papers or requirements.
* Applicable `.intent/` rules and enforcement mappings.
* Open issue or PR.
* Existing tests and prior evidence.

Use the connected repository for remote state and the executor for local-only or runtime state.

Generated context packets may be used for broad navigation, but their source ref and freshness must be established before relying on them.

The absence of a context packet does not block a session when the authoritative repository is directly accessible.

### Step 4 — Run the live state scan when relevant

Not every documentation or analysis session requires a running CORE deployment.

When the work depends on repository health, runtime behavior, daemon state, or current findings, run the applicable scan.

Canonical repository and runtime scan:

```text
Run the applicable current-state checks and report the unedited results.

Repository:
1. git status --short --branch
2. git rev-parse HEAD
3. poetry run core-admin code audit

Runtime, when this session depends on the live deployment:
4. systemctl --user status core-daemon
5. systemctl --user status core-api
6. poetry run core-admin runtime health
7. poetry run core-admin runtime dashboard --plain

Report:
- repository path, branch, and HEAD SHA
- dirty or clean state
- audit verdict and finding count
- failed or crashed rules
- daemon and API status
- governor-inbox count
- convergence, pipeline, and autonomous-reach signals
- any command that failed or returned incomplete output

Do not fix anything during this scan.
```

A failed scan is evidence, not permission to improvise a fix.

### Step 5 — Scan GitHub work state

Use the connected GitHub tools directly when available. Otherwise use the executor and `gh` with explicit JSON fields.

The scan covers:

* Open issues relevant to the active governed workstream.
* Recently updated high-priority or blocking issues.
* Verification-pending items.
* Open pull requests.
* Hosted CI state when relevant.
* Resolved issues that should be closed.
* Work with no valid issue, ADR, or planning anchor.

The scan must not hard-code a historical band or milestone as permanently current.

Canonical fallback prompt:

```text
Retrieve the current GitHub work state using gh with explicit JSON output.

1. Open issues:
   gh issue list --state open \
     --json number,title,labels,milestone,updatedAt,assignees \
     --limit 100

2. Open pull requests:
   gh pr list --state open \
     --json number,title,headRefName,baseRefName,isDraft,statusCheckRollup,updatedAt \
     --limit 50

3. Verification-pending issues:
   gh issue list --state open \
     --label "status:verification-pending" \
     --json number,title,labels,updatedAt \
     --limit 50

4. Blocked issues:
   gh issue list --state open \
     --label "status:blocked" \
     --json number,title,labels,updatedAt \
     --limit 50

Report the results without choosing or editing anything.
```

Apply any workstream-specific label, milestone, ADR, or planning filter only after reading the current governing surface.

Close already-resolved items before selecting new work.

### Step 6 — Select the lead

The architect identifies the strongest lead candidates based on:

1. An explicit governor direction.
2. A blocker in the current workstream.
3. Work required by an accepted ADR or requirement.
4. A current verification or acceptance gap.
5. A high-priority issue with clear closure conditions.
6. Governor-adjudication work that is blocking autonomous progress.

The architect may recommend one candidate and explain the reason.

The governor selects, redirects, or vetoes.

The lead is named with its issue, ADR, requirement, candidate SHA, or other authoritative anchor.

### Step 7 — Commit to the lead

State the expected session outcome in one sentence.

After selection:

* Stop comparing unrelated candidates.
* Do not absorb adjacent work silently.
* Record newly discovered work as issues.
* Change the lead only through explicit governor direction or a demonstrated blocker.

---

## 5. Session running

### 5.1 Interaction contract governs

`INTERACTION-CONTRACT.md` governs active turns, deliverable shapes, authority, verification, and drift handling.

### 5.2 Reconnaissance precedes editing

For implementation work, the executor reads:

* The target files.
* Every affected call site.
* Corresponding tests.
* Applicable ADRs and rules.
* Existing implementation that may already satisfy the request.

For non-trivial changes, the executor reports reconnaissance before editing when required by its executor contract.

### 5.3 New work is recorded immediately

A newly discovered:

* Defect.
* Hazard.
* Governance mismatch.
* False positive.
* Evidence gap.
* Tooling limitation.
* Open architectural question.

is opened as a GitHub issue during the session unless it is resolved within the bounded lead and does not warrant an independent record.

Deferred work is never parked only in conversation.

### 5.4 Evidence is claim-specific

For each acceptance claim, record:

* Exact candidate SHA.
* Exact command or test.
* Whether it was freshly run.
* Whether it directly tested the named behavior.
* Pass, fail, partial, or proxy status.
* Environment.
* Operator or agent identity where independence matters.
* Known limitations.

Partial or proxy evidence is not silently summarized as direct pass.

### 5.5 Candidate changes invalidate affected evidence

When a candidate changes:

* Assign the new SHA explicitly.
* State whether the change is production, test-only, documentation-only, or metadata-only.
* Re-run affected checks.
* Do not reuse an earlier top-line verdict without explaining why the evidence remains valid.

A frozen candidate is not mutated casually. A new commit creates a new candidate.

### 5.6 External-access gate

Before instructing a cold-room operator, external reviewer, hosted runner, or fresh developer to use a candidate, verify:

* The repository is accessible.
* The branch exists remotely.
* The SHA is reachable remotely.
* Required documentation exists at that SHA.
* Required artifacts are published or reproducible.
* The checkout command is valid from a clean clone.

A local-only commit cannot be an external acceptance candidate.

Making it remotely accessible is a governor-authorized publication action, not an implicit verification step.

### 5.7 Implementation does not imply publication

An executor may author and commit work where its contract permits.

The following remain separately controlled:

* Push.
* Pull-request creation when it exposes unpublished work.
* Merge.
* Release.
* Deployment.
* Branch deletion.
* Acceptance signature.

A request to verify does not authorize merge. A request to merge does not authorize release or deployment.

---

## 6. Session closing

Seven steps.

### Step 1 — Establish final state

Report:

* Repository or clone.
* Branch.
* Final HEAD SHA.
* Base SHA.
* Dirty or clean state.
* Commits created during the session.
* Whether the branch and commits exist on origin.
* Whether a candidate is frozen.

Do not describe a local-only commit as available to other operators.

### Step 2 — Report verification

Report every relevant check honestly:

* Scoped tests.
* Ruff or other lint checks.
* Type checks.
* Constitutional audit.
* Full suite or hosted CI, when run.
* Runtime or cold-room checks, when run.
* Failures, skips, incomplete runs, and inherited evidence.

Do not report “all passed” when named acceptance items remain partial, indirect, or unexecuted.

### Step 3 — Commits and publication status

An executor may commit its own authored work in accordance with its executor contract.

State explicitly:

* Commit SHA and message.
* Files changed.
* Whether the commit is pushed.
* Whether a pull request exists.
* Whether hosted CI ran against the exact candidate or against a synthetic merge ref.
* Any remaining governor action needed to make the work accessible.

Push remains governor-authorized.

### Step 4 — Update issues

* Close issues whose closure conditions were met.
* Add evidence to issues that remain open.
* Correct labels and milestones where needed.
* Create issues for surfaced but unresolved work.
* Record blockers precisely.

Issue history is the operational session record.

### Step 5 — Maintain governance artifacts only when triggered

Update a governance or planning artifact only when the session changed what that artifact governs.

Examples:

* New or amended architectural decision → ADR.
* Constitutional change → `.intent/CHANGELOG.md`.
* Formal acceptance event → attestation.
* Tracked operational criterion changed → relevant tracker.
* Protocol itself changed → this document or `INTERACTION-CONTRACT.md`.

Routine commits and issue closures do not require synthetic planning-log entries.

### Step 6 — Merge, release, or deploy only when separately authorized

A green candidate does not merge itself.

An acceptance recommendation does not constitute governor acceptance.

A merge authorization does not automatically authorize:

* Release.
* Deployment.
* Branch deletion.
* Publication of an unqualified attestation.
* Relaxation of a constitutional constraint.

Each externally consequential act is explicit.

### Step 7 — Close concisely

The closing statement contains:

* Lead outcome.
* Final candidate or commit SHA.
* Verification verdict.
* Remote publication status.
* Remaining blocker or limitation.
* Immediate governor action, when one exists.

No narrative handoff document is produced.

---

## 7. Issue writing template

Use the following minimal issue structure:

```markdown
## What it is

<One paragraph describing the defect, hazard, gap, or decision required.>

## How it surfaced

<The workstream, command, test, candidate, or investigation that exposed it.>

## Authority or expected contract

<ADR, rule, requirement, public API contract, documentation, or other source that defines the expected behavior.>

## Verified current state

<What was directly checked. Include paths, SHAs, commands, or concrete output where relevant.>

## What would close it

- <Concrete closure condition>
- <Required verification>
- <Required governance act, if any>

## References

- Commits: <sha>
- Related issues: #N
- Related ADRs: ADR-NNN
- Candidate or branch: <ref>
```

Labels and milestones follow the current governed catalog. They are not inferred from historical planning documents.

---

## 8. Changing this protocol

This document is governance text.

A durable revision requires governor authorization and lands at:

`.specs/planning/SESSION-PROTOCOL.md`

The change may be applied by the governor, an executor, or a connector-backed action under the confirmation rules in `INTERACTION-CONTRACT.md`.

A major change in session authority or decision rights may warrant an ADR. Updating obsolete tools, commands, paths, or work-selection mechanics normally does not.

---

## 9. Non-goals

This protocol does not specify:

* The active-turn interaction contract — see `INTERACTION-CONTRACT.md`.
* Source implementation rules — see the applicable executor contract.
* Runtime governance law — see `.intent/`.
* Architectural content of a lead.
* Issue-label definitions.
* A permanent strategic band, milestone, or product priority.
* A mandatory context-packet delivery mechanism.
* A requirement that every session operate a live CORE runtime.

---

*Established 2026-04-26.*

*Revised 2026-07-27: replaced the May 2026 Project Files and hard-coded Band E workflow with a platform-neutral authority model; added mandatory repository, branch, SHA, dirty-state, and remote-reachability identification; made context packets optional snapshots rather than prerequisites; updated the live scan to include current audit, runtime-health, and governor-dashboard surfaces; introduced SHA-bound evidence, candidate invalidation, external-access, and operator-independence controls; aligned commit and push boundaries with the current executor contract; and incorporated the operating lessons from isolated-clone and cold-room acceptance work.*
