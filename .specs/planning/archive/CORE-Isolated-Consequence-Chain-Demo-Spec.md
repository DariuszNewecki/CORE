---
kind: planning
title: CORE — Isolated Consequence-Chain Demo
status: draft
---

<!-- Proposed repository path: .specs/planning/CORE-Isolated-Consequence-Chain-Demo.md -->

# CORE — Isolated Consequence-Chain Demo

**Status:** Draft implementation specification
**Assessment baseline:** `f7430b25cfcddd4178befcc0ff9b65d7d6730f31`
**Prepared:** 2026-07-23
**Scope:** Replace `scripts/demo.sh` without changing the running assessment system
**Implementation timing:** After the production-readiness assessment closes

## 1. Outcome

CORE will provide one explicit command:

```text
core-admin demo consequence-chain
```

The command demonstrates a genuine, deterministic governance chain:

```text
violation
  → persisted finding
  → governed proposal
  → recorded approval authority
  → sandboxed execution
  → committed source change
  → durable consequence
  → re-audit
  → resolved finding
```

The scenario operates only on a disposable clone and disposable infrastructure. It must not modify the invoking checkout, its Git index, its untracked files, its `.intent/`, or any existing CORE database, Qdrant instance, API, or daemon.

The demo is an on-ramp and evidence viewer. It is not an alternative execution lane and does not prove production readiness by itself.

## 2. Why the current implementation must be replaced

At the assessed baseline, `scripts/demo.sh` has five independent defects:

1. It creates commits in the invoking checkout and later calls `git reset --hard`.
2. It can absorb pre-existing staged changes into its seed commit and erase staged or unstaged work during cleanup.
3. `install-core.sh` runs it automatically instead of offering it as an explicit opt-in.
4. It calls `core-admin proposals ...`, but `core-admin` no longer registers the `proposals` namespace after consumer-command extraction.
5. Its final query selects the most recent consequence row and labels `autonomous_proposals.goal` as `FINDING`. It does not prove that the displayed proposal is linked to the seeded finding.

Several expected checks also use `|| true` or print a warning and continue. The script can therefore finish with a success-shaped message after a failed audit, failed execution, failed verification, or failed evidence query.

The narrative remains valuable. The implementation and its claims do not.

## 3. Governing decisions

### D1 — The demo is explicit and opt-in

Installation must not execute the demo.

`install-core.sh` will finish by offering:

```text
Run the isolated consequence-chain demo:
  poetry run core-admin demo consequence-chain
```

`scripts/demo.sh` becomes a compatibility wrapper that delegates to the new command and contains no scenario logic.

### D2 — The invoking checkout is read-only

The demo reads the invoking repository only to identify and copy its committed `HEAD`.

It must not:

- stage, commit, reset, restore, clean, checkout, or write files in the invoking repository;
- create a Git worktree registered against the invoking repository;
- use hardlinks to the invoking repository's Git objects;
- read uncommitted files into the demo clone;
- write to the invoking repository's `.intent/`, `var/`, database, or runtime.

The disposable repository is created by a local clone of committed `HEAD` using copied objects, with its remote removed before scenario execution.

### D3 — Every run has a unique, validated identity

Each run receives an opaque UUID `run_id`.

All disposable filesystem resources are rooted beneath the configured local-state directory:

```text
<CORE_DEMO_STATE_DIR>/runs/<run_id>/
```

`CORE_DEMO_STATE_DIR` is resolved by `shared.config.Settings`; its default is the platform's per-user local-state location, outside the invoking repository. It is never assembled by shell expansion.

Every directory and container resource created by the demo carries the same `run_id`. Cleanup may act only when:

- the target is a direct child of `<CORE_DEMO_STATE_DIR>/runs`;
- the basename exactly equals `run_id`;
- a marker file inside the directory contains the same `run_id`;
- the resolved target is not the invoking repository, its parent, the demo-runs root, the filesystem root, or a symlink escape.

No wildcard, unresolved environment variable, or broad recursive target may be used for cleanup.

### D4 — Infrastructure is disposable and collision-free

The demo starts fresh PostgreSQL and Qdrant instances through a dedicated Compose file:

```text
infra/demo/compose.yaml
```

The Compose project name is derived from `run_id`. The file must:

- declare no fixed `container_name`;
- bind only to loopback;
- use dynamically assigned host ports;
- use no pre-existing named volumes;
- use temporary storage for PostgreSQL and Qdrant;
- initialize PostgreSQL from the canonical fresh-install schema;
- define health checks;
- use `restart: "no"`;
- carry `core.demo.run_id=<run_id>` labels.

The running production Compose project, database, Qdrant instance, API, and daemon are never inspected, stopped, reconfigured, or reused.

### D5 — The isolated process loads isolated configuration

The disposable clone receives its own `.env`, pointing only to the run-specific PostgreSQL and Qdrant ports. LLM use is disabled.

The scenario runs in a child Python process with:

- working directory set to the disposable clone;
- the clone's `src/` first on `PYTHONPATH`;
- the current Python interpreter;
- inherited terminal input/output;
- no shell interpolation.

This is required because `shared.config.settings` is initialized at import time. Changing the parent process working directory after `core-admin` has started would not safely re-root an existing `CoreContext`.

Process execution must delegate to the existing subprocess sanctuary in `shared.utils.subprocess_utils`. Git operations and clone cleanup must delegate to `GitService`. Repository writes inside the clone must use `FileHandler` or an existing governed write surface.

No new direct `subprocess`, `os.system`, `Path.write_*`, `shutil.rmtree`, or shell-execution site is permitted outside an already governed infrastructure sanctuary.

### D6 — The demo uses the real production chain

The demo may orchestrate existing components, but it may not introduce a demo-only audit, proposal, approval, execution, or evidence path.

The scenario uses:

- `AuditViolationSensor`, executed for one cycle against `linkage.assign_ids`;
- `ViolationRemediatorWorker`, executed for one cycle to map the finding to `fix.ids`;
- the normal risk computation and proposal state manager;
- `POST /v1/proposals/{proposal_id}/execute` through the FastAPI application;
- the normal `ProposalExecutor`, `SandboxLifecycle`, action registry, `fix.ids`, finalization barrier, and consequence service;
- `GET /v1/proposals/{proposal_id}/chain` for evidence;
- a second sensor/audit cycle for closure verification.

The API may be exercised in-process through an ASGI client. This preserves the real routes and dependencies without exposing another host port or starting a long-running API process.

Direct SQL is prohibited in the scenario. Selecting the "latest" finding, proposal, or consequence is prohibited.

### D7 — The seed is committed only in the disposable clone

The scenario creates one file:

```text
src/body/analyzers/demo_onramp_<run-id-short>.py
```

The file contains one public function without its required stable ID anchor. The seed is committed in the disposable clone because production execution creates its sandbox from `HEAD`.

Before continuing, the demo proves:

- the seed path did not exist at the cloned baseline;
- only the seed file changed in the seed commit;
- `.intent/` is byte-identical to the cloned baseline;
- the seed commit is not reachable from the invoking repository;
- the disposable clone has no Git remote.

### D8 — Finding and proposal identity are exact

After the sensor cycle, the demo must resolve exactly one active finding whose:

- rule is `linkage.assign_ids`;
- file path is the run-specific seed path;
- creation time is within this run;
- subject matches the governed audit-finding identity.

After the remediation cycle, the demo reads the proposal ID from that finding's recorded linkage. It must not infer it from ordering, timestamps alone, textual goal matching, or "latest proposal".

The proposal must:

- contain the exact finding ID in `constitutional_constraints.finding_ids`;
- contain one `fix.ids` action scoped to the seed file;
- carry the computed risk and approval requirement;
- be in the state expected from the governed risk classification.

Zero matches, multiple matches, missing linkage, or mismatched scope fails the demo.

### D9 — Approval is represented truthfully

`fix.ids` is currently governed as a safe action. The real deterministic remediation path therefore auto-approves its proposal under:

```text
risk_classification.safe_auto_approval
```

The demo must display that authority exactly. It must not claim that the human operator approved the proposal.

Before execution, the command asks:

```text
The isolated proposal is policy-approved as safe.
Continue with execution in the disposable repository? [y/N]
```

This prompt is consent to continue the demonstration, not a proposal approval event.

An unattended test mode may use `--simulate-confirmation`, but the final report must label the operator confirmation as simulated. This flag is for CI and cold-room verification; it must not change the proposal's recorded approval identity or authority.

A future human-approval scenario must use a genuinely human-gated action. It must not force `fix.ids` into a false risk class merely to stage a dramatic approval step.

### D10 — Every claim fails closed

The demo exits non-zero unless all of the following hold:

1. Disposable infrastructure is healthy.
2. The seed commit contains only the seed file.
3. The first sensor cycle produces exactly the expected finding.
4. The remediator produces exactly one correctly linked proposal.
5. The proposal's risk and approval authority match governed state.
6. Execution reaches `completed`.
7. `completed` has a durable consequence record.
8. The consequence belongs to the exact proposal ID.
9. The consequence includes non-null pre- and post-execution SHAs.
10. The post SHA differs from the pre SHA.
11. `files_changed` includes the seed file and no unexpected source file.
12. The original finding is resolved and remains linked to the proposal.
13. Re-audit no longer reports `linkage.assign_ids` for the seed file.
14. The clone's `.intent/` hash is unchanged.
15. The invoking repository's HEAD, index, tracked bytes, and pre-existing untracked bytes are unchanged.

Warnings cannot substitute for any of these assertions.

### D11 — Cleanup is scoped and observable

On success, the demo:

1. stops and removes only the Compose project carrying its `run_id`;
2. removes its temporary containers, network, and storage;
3. removes the disposable clone through the validated cleanup surface;
4. verifies that no resource carrying its `run_id` remains.

On failure or interruption:

- infrastructure cleanup still runs;
- the invoking repository still remains untouched;
- the workspace may be retained for diagnosis, but the command must print its exact path and mark it as retained;
- `core-admin demo cleanup <run_id>` may remove a retained workspace only after the D3 validations pass.

Cleanup failure changes the final verdict to failure. It is never swallowed.

### D12 — Evidence is rendered from the exact chain response

The terminal summary shows:

- run ID and assessed commit;
- finding ID, rule, path, and original status;
- proposal ID, action, risk, approval authority, and approver identity;
- execution claimer and terminal status;
- pre/post SHA and changed files;
- resolved finding ID;
- re-audit result;
- cleanup result;
- whether operator confirmation was human or simulated.

The command supports:

```text
--output <path>
```

When supplied, it writes a Markdown report and JSON companion to the explicitly chosen destination. Without `--output`, it writes no report into the invoking checkout.

The report must state:

> This demonstration proves one isolated consequence chain. It is not a production-readiness attestation.

## 4. Proposed component map

| Surface | Responsibility |
|---|---|
| `src/cli/resources/demo/__init__.py` | Register the `demo` resource namespace. |
| `src/cli/resources/demo/consequence_chain.py` | Parse options, obtain operator confirmation, render outcome, and map failures to CLI exit codes. |
| `src/cli/logic/demo/consequence_chain.py` | Compose the parent/child scenario without implementing domain substitutes. |
| `src/cli/logic/demo/models.py` | Typed run, phase, assertion, and evidence records. |
| `src/shared/config.py` | Declare and resolve `CORE_DEMO_STATE_DIR` outside the invoking repository. |
| `src/shared/utils/subprocess_utils.py` | Add the narrow inherited-stdio/explicit-env process primitive required for the isolated child and fixed Docker Compose commands. |
| `src/shared/infrastructure/git_service.py` | Add validated local-clone creation, remote removal, and marker-checked clone cleanup. |
| `infra/demo/compose.yaml` | Ephemeral PostgreSQL and Qdrant only. |
| `src/api/cli/proposals_client.py` | Add a typed `get_proposal_chain(proposal_id)` method for the existing exact-ID route. |
| `scripts/demo.sh` | Compatibility wrapper only. |
| `install-core.sh` | Stop auto-running the demo; print the opt-in command. |
| `README.md`, `docs/getting-started.md`, `docs/cli-reference.md` | Document prerequisites, expected output, failure semantics, and cleanup. |

The final repository paths may change during implementation if existing module conventions demand it. The separation of responsibilities and safety boundaries may not.

## 5. CLI contract

```text
core-admin demo consequence-chain
    [--output PATH]
    [--keep-workspace]
    [--simulate-confirmation]
    [--timeout-seconds INTEGER]
```

Defaults:

- interactive confirmation required;
- no output file;
- workspace removed on success;
- infrastructure always removed;
- overall timeout bounded;
- no LLM;
- no production connection reuse.

Exit codes reuse CORE's established CLI semantics:

| Exit | Meaning |
|---|---|
| `0` | Every scenario assertion and cleanup assertion passed. |
| `2` | Pre-flight/configuration failure; the scenario did not start. |
| `64` | Scenario, evidence, isolation, or cleanup failure. |
| `130` | Operator interruption; infrastructure cleanup attempted and result reported. |

## 6. Acceptance-test contract

### 6.1 Unit and contract tests

| ID | Test | Required result |
|---|---|---|
| U01 | CLI registration | `core-admin demo consequence-chain --help` resolves without loading production data. |
| U02 | Installer behavior | `install-core.sh` contains no executable demo invocation. |
| U03 | Wrapper behavior | `scripts/demo.sh` delegates only; it contains no Git mutation, DB query, or swallowed failure. |
| U04 | No destructive Git | Demo code contains no `git reset --hard`, `git clean`, or checkout of the invoking repository. |
| U05 | Clone isolation | Clone uses copied objects, has no remote, and is pinned to the captured source `HEAD`. |
| U06 | Cleanup guard | Wrong parent, missing marker, marker mismatch, symlink escape, root target, and source-repo target are all refused. |
| U07 | Resource identity | Compose project, labels, paths, and evidence all carry the same `run_id`. |
| U08 | Exact finding selection | Zero, duplicate, stale, or path-mismatched findings fail. |
| U09 | Exact proposal linkage | Proposal is obtained from the finding linkage; ordering-based lookup is impossible. |
| U10 | Exact consequence linkage | Chain lookup uses the proposal ID; "latest consequence" lookup is impossible. |
| U11 | Approval honesty | Safe auto-approval is rendered as policy authority; operator confirmation is not rendered as approval. |
| U12 | Fail-closed assertions | Removing any required chain field changes the result to failure. |
| U13 | `.intent/` immutability | Hash drift in either source or cloned `.intent/` fails the run. |
| U14 | Output discipline | No report is written without `--output`; explicit output contains matching Markdown and JSON identities. |
| U15 | Timeout | Every wait has a deadline and reports the phase that exceeded it. |

### 6.2 Integration and end-to-end tests

| ID | Test | Required result |
|---|---|---|
| E01 | Full chain | Seed → finding → proposal → execution → consequence → resolved finding → clean re-audit passes against fresh infrastructure. |
| E02 | Dirty source repository | Pre-existing staged, unstaged, and untracked files remain byte-identical; index tree and `HEAD` remain identical. |
| E03 | Production collision defense | Existing database/Qdrant/API environment variables are deliberately populated with sentinel endpoints; the demo still uses only generated endpoints. |
| E04 | Parallel runs | Two runs execute concurrently without sharing ports, paths, containers, findings, proposals, or consequences. |
| E05 | Repeatability | Three consecutive runs produce independent IDs and all pass cleanup. |
| E06 | Failure after clone | Injected failure cleans infrastructure state and leaves source unchanged. |
| E07 | Failure after infrastructure start | Injected failure removes only the run-specific Compose resources. |
| E08 | Failure after seed commit | Source remains unchanged; retained/removed workspace behavior matches the option. |
| E09 | Failure after proposal creation | No production data is touched; failure evidence identifies the exact proposal. |
| E10 | Execution failure | The demo reports the proposal terminal state and reason; it never prints the success thesis. |
| E11 | Missing consequence | A `completed` proposal without consequence evidence fails the demo. |
| E12 | Interrupt | SIGINT during sensing, execution, and verification produces exit `130` and bounded cleanup. |
| E13 | No `.intent/` mutation | Source and clone `.intent/` trees are byte-identical before and after the scenario. |
| E14 | No LLM dependency | The full scenario passes with no LLM URL, key, or model service. |
| E15 | Cold-room run | A non-author follows public documentation on a clean supported host and completes the demo without source inspection. |

### 6.3 Negative claim tests

The test suite must explicitly prove that the demo cannot pass when:

- the expected rule does not fire;
- the finding is not persisted;
- the finding and proposal are not linked in both directions;
- the proposal action or file scope differs;
- the approval authority is missing;
- execution returns success but proposal state is not `completed`;
- `completed` lacks its consequence timestamp or row;
- pre/post SHAs are missing or equal;
- an unexpected file changes;
- re-audit still finds the violation;
- `.intent/` changes;
- cleanup leaves a run-labeled container, network, storage object, or child process.

## 7. Implementation sequence

### Phase 0 — Entry conditions

Do not begin implementation until:

- the 72-hour production-readiness soak and final assessment are closed;
- the G6 risk-vocabulary defect has been remediated and regression-tested;
- the next available ADR number is known;
- the governor approves the isolation and orchestration decisions as an ADR.

The ADR must record at minimum D1–D11 from this specification. It must not authorize CORE to write to `.intent/`.

### Phase 1 — Isolation substrate

Implement and test:

- clone creation and cleanup;
- run identity and marker validation;
- disposable Compose project;
- child-process re-rooting;
- invoking-repository before/after fingerprint.

No audit or mutation scenario is added in this phase.

### Phase 2 — Genuine chain scenario

Wire the existing sensor, deterministic remediator, proposal route, executor, exact chain route, and re-audit. Add the fail-closed assertion model before rendering celebratory output.

### Phase 3 — Public surface

Add the CLI namespace, compatibility wrapper, installer change, documentation, and explicit evidence export.

### Phase 4 — Adversarial verification

Run:

- unit and integration suite;
- constitutional audit;
- dirty-repository test;
- parallel-run test;
- interruption/failure-injection matrix;
- non-author cold-room run.

The feature is not complete until the cold-room operator can explain what happened from the report without reading source code.

## 8. Definition of done

The replacement is complete only when:

- the old implementation logic is gone;
- installation never runs the demo automatically;
- the demo exercises a genuine finding-linked proposal;
- every displayed chain element belongs to the same exact proposal;
- approval authority is represented truthfully;
- a dirty invoking repository is unchanged byte-for-byte;
- no production service or data is reused;
- cleanup is bounded, scoped, verified, and failure-visible;
- documentation is sufficient for a non-author;
- the complete acceptance-test contract is green;
- the constitutional audit is green;
- the resulting evidence is independently reviewed.

## 9. Explicit non-goals

This work does not:

- fix G1, G5, G10, or G13 merely by existing;
- provide a web UI;
- demonstrate a human-approved dangerous action;
- validate production database migration or rollback;
- run against the live CORE deployment;
- modify `.intent/`;
- change the risk classification of `fix.ids`;
- conceal failures to improve the demonstration;
- replace the production-readiness assessment.

## 10. Reviewer checklist

Before implementation is accepted, the reviewer answers:

1. Can any code path write to the invoking checkout?
2. Can any code path resolve a finding, proposal, or consequence by "latest"?
3. Can the demo claim success after a missing link?
4. Can the operator confirmation be confused with recorded proposal approval?
5. Can a production endpoint leak into the child configuration?
6. Can cleanup escape the validated run directory?
7. Can an interruption leave a process or container running?
8. Does any demo-only function bypass the normal sensor, proposal, executor, or consequence services?
9. Is `.intent/` byte-identical in both the invoking repository and disposable clone?
10. Does the report plainly state the limits of what the demo proves?

Any "yes" to questions 1–7, any "no" to questions 8–10, or any unverifiable answer blocks acceptance.
