<!-- path: .intent/papers/CORE-Workers-and-Governance-Model.md -->

# CORE — Workers, Supervision, and the Blackboard

**Status:** Constitutional Paper
**Location:** `.intent/papers/CORE-Workers-and-Governance-Model.md`
**Scope:** Autonomous entity model, supervision, coordination

---

## 1. Purpose

This paper defines the constitutional model for autonomous entities operating within CORE.

It establishes what a Worker is, what a ShopManager is, how they coordinate, and what obligations govern their behavior. It does not define implementation. It defines standing.

For technical implementation details of each Worker see the dedicated papers:
`CORE-ViolationSensor.md`, `CORE-RemediatorWorker.md`, `CORE-ViolationExecutor.md`,
`CORE-ConsumerWorker.md`, `CORE-ShopManager.md`.

---

## 2. The Problem This Solves

CORE's enforcement infrastructure is mature. Its constitutional law is declared. Its atomic actions are available. What has been missing is a model for *who* acts autonomously, *under what authority*, and *how* that activity is governed.

Without this model, autonomous processes are just scripts. They may be useful, but they are not constitutional entities. They have no declared mandate, no traceable identity, and no supervision. They cannot be held to law they have never sworn to uphold.

This paper closes that gap.

---

## 3. Two Classes of Autonomous Entity

CORE recognizes exactly two classes of autonomous entity:

### 3.1 Worker

A Worker is a constitutional officer with a single declared responsibility.

A Worker:
- Holds a mandate declared in `.intent/workers/`
- Is responsible for exactly one domain of concern
- Calls Agents or LLMs as labor tools — they have no constitutional standing of their own
- Produces Proposals; it does not execute actions directly — with one constitutional exception: ConsumerWorker's sole mandate is executing approved Proposals via ActionExecutor.
- Registers its identity on startup against its `.intent/` declaration
- Writes a constitutional record of every decision it makes

A Worker does not improvise. It does not exceed its mandate. Its intelligence is irrelevant to its authority. Its authority comes from its constitutional declaration — not from its capability.

The LLM inside a Worker is labor. The Worker's constitution is the law.

### 3.2 ShopManager

A ShopManager is a supervisory officer. It does not perform domain work.

A ShopManager:
- Monitors Worker liveness and constitutional compliance
- Reads Worker history from the Blackboard — it does not ping Workers directly
- Has no Proposal authority — it cannot act on the system
- Its only constitutional power is to escalate
- Operates as a team — ShopManagers monitor each other
- Escalates to the Human only when the supervisory team itself cannot resolve a condition

A ShopManager that attempts domain work is in constitutional violation.

---

## 4. The Blackboard

Workers and ShopManagers do not communicate with each other directly. They coordinate through a shared ledger: the Blackboard.

The Blackboard is not a constitutional entity. It is infrastructure. The constitution governs *behavior around* the Blackboard, not the Blackboard itself.

For the technical definition of the Blackboard see `CORE-Blackboard.md`.

**What the Blackboard contains:**
- Findings posted by sensing Workers
- Claims made by acting Workers
- Proposals created and their outcomes
- History written by all entities

**How coordination works:**
- A Worker posts a finding — it does not notify anyone
- Another Worker reads the Blackboard, claims the finding atomically, and acts
- A ShopManager reads Worker history — silence is a signal
- No Worker knows what other Workers exist; they only know the Blackboard schema

This decoupling is intentional. Workers are replaceable. The Blackboard is permanent.

---

## 5. Worker Types

Workers fall into three natural categories based on their relationship to the Blackboard:

**Sensing Workers** — observe the system and post findings. They do not act.

**Acting Workers** — claim findings, create Proposals, and drive execution. They do not observe.

**Governance Workers** — monitor constitutional health of the system itself. They post governance findings.

No Worker operates across categories. Sensing and acting are separate mandates.

---

## 6. Constitutional Obligations

The following obligations apply to all autonomous entities without exception:

**Identity:** Every entity must have a UUID declared in its `.intent/` file. Every Proposal and every Blackboard entry it creates must carry that UUID. Proposals without a valid registered identity are rejected before reaching any enforcement gate.

**History:** Every decision, every claim, every Proposal created must be written to the Blackboard as a constitutional record. Acting without writing history is a constitutional violation. Silence is not neutral — it is a violation.

**Scope:** No entity may act outside its declared mandate. An entity that exceeds its scope is in violation regardless of the quality of its reasoning.

**Proposal authority:** Workers propose; they do not execute directly. All proposals pass through constitutional enforcement gates before any action runs. The single exception is ConsumerWorker, whose declared mandate is execution of approved Proposals — it does not propose, it only executes what has already been authorized.

**Thoroughness over throughput:** A Worker must not prioritize speed over accuracy. Autonomous operation is only valuable if its output is trustworthy. A Worker that produces fast but unreliable results is in violation of its mandate — confident wrong output is constitutionally worse than no output. Duration of execution is not a metric of failure. A Worker that takes two days to do its job correctly has succeeded. A Worker that takes two minutes and produces degraded output has failed.

---

## 7. Lifecycle

Workers are started by the system and declare themselves to the Blackboard on startup. The ShopManager team validates each registration against `.intent/`.

Workers are stopped constitutionally — not killed arbitrarily. In-flight Proposals at the time of termination are resolved before shutdown or explicitly marked as abandoned in the Blackboard record.

A Worker whose declaration has been updated in `.intent/` operates under its new mandate for all future Proposals. Proposals created under a prior mandate are resolved under the law that was in force at the time of creation.

---

## 7a. Technical Run Cycle

Every Worker executes the same technical cycle when started:

start() → _register() → run() → [post report] → end

**Step 1 — `_register()`**
The Worker declares its identity in `core.worker_registry`. This is not
optional. A Worker that cannot register has no constitutional standing
and must not proceed.

Registration records: `worker_uuid`, `worker_name`, `worker_class`,
`phase`, `status=active`, `last_heartbeat=now()`.

If the Worker UUID already exists in the registry (daemon restart),
registration updates `status=active` and `last_heartbeat`.

**Step 2 — `run()`**
The Worker's single unit of constitutional work. Subclasses implement
this method. It must:

1. Post a heartbeat immediately on entry.
2. Query the Blackboard for open findings matching its mandate.
3. If no findings: post a report and return.
4. Claim findings atomically (FOR UPDATE SKIP LOCKED).
5. Process each claimed finding.
6. Mark each finding resolved, abandoned, or deferred.
7. Post a completion report.

**Step 3 — Heartbeat**
The heartbeat is a Blackboard entry of type `heartbeat` posted at the
start of every `run()`. It proves the Worker is alive and constitutionally
compliant. A Worker that does not post a heartbeat within its SLA is
considered silent. Silence triggers ShopManager escalation.

**Step 4 — Failure handling**
If `run()` raises an unhandled exception, the Worker posts a
`worker.error` report with `status=abandoned` and re-raises.
In-flight claimed findings are left in `claimed` status — the
ShopManager detects them as stale and escalates.

**Step 5 — Termination**
Workers are stopped by the daemon. In-flight findings at termination
time must be resolved or explicitly marked `abandoned` before the
Worker stops. A Worker that terminates with claimed findings it has
not resolved is in violation.

---

## 8. Supervision Model

ShopManagers operate as a team. Each holds a different watch responsibility:

- Worker health and liveness
- Blackboard integrity and ledger health
- Proposal pipeline health and constitutional compliance

The team monitors itself. A ShopManager that goes silent triggers escalation from its peers. If the supervisory team cannot resolve a condition — the Human is notified.

The Human is not in the loop for normal operations. HQ is called only when the managers cannot handle it.

---

## 9. Phased Coordination

Workers are phase-aware. Phase separation provides implicit orchestration without a central coordinator:

- **Audit phase** — Sensing Workers run, post findings to the Blackboard
- **Plan phase** — Acting Workers claim findings, create Proposals
- **Execute phase** — Approved Proposals run through ActionExecutor
- **Report phase** — Governance Workers verify outcomes, post results

Phase gates enforce sequence. No Worker acts outside its phase.

---

## 10. What This Paper Does Not Define

This paper does not define:

- Worker schemas or YAML structure — that is META
- Blackboard table structure — that is `CORE-Blackboard.md`
- Specific Worker implementations — that is their dedicated papers
- Trigger mechanisms — that is operational configuration

Law precedes machinery. This paper is law. Machinery follows.

---

## 11. Closing Statement

A Worker is not an agent in the popular sense. It is a constitutional officer.

Its authority comes from its declaration, not its intelligence. Its intelligence is a tool it picks up and puts down. The constitution remains in force regardless of what the tool produces.

This is the inversion that governs CORE's autonomous entity model: the system does not trust its workers' reasoning. It trusts its law.
