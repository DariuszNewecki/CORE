# CORE

> **Executable constitutional governance for AI-assisted software development.**

AI can write code. It cannot be trusted to build complete, correct software autonomously.

CORE surrounds AI with a deterministic governance system. It does not make AI perfect — it makes AI mistakes detectable, traceable, and fixable in a controlled loop.

**LLMs operate inside CORE. Never above it.**

---

## What CORE Does

CORE is a governance runtime. When an AI agent proposes a change, CORE:

1. Validates it against constitutional rules before execution
2. Blocks what a *blocking* rule forbids — the change halts before it is applied; reporting and advisory rules surface findings and let it continue
3. Records decisions and the finding → proposal → approval → execution chain (recording is best-effort: a database failure does not stop execution — see the [Proof Index](proof-index.md))
4. Remediates automatically where rules permit; anything outside the narrow safe-auto-approval envelope waits for a human

The aim: AI-assisted development that is auditable and governed. It is **not yet proven safe to leave unattended** — CORE's own [production-readiness verdict](https://github.com/DariuszNewecki/CORE/blob/main/.specs/attestations/production-readiness.yaml) is NOT ATTESTED, and unattended reliability (gate G4) is not demonstrated.

The goal at A3 (Governed Autonomy) is that the governor's job shrinks to two things: check the dashboard, and write constitutional intent. That is the design target, not today's measured state — see the [Autonomy Ladder](autonomy-ladder.md).

---

## What CORE Is Not

- ❌ Not a generic LLM wrapper
- ❌ Not an autonomous coding agent you deploy and forget
- ❌ Not a CI system
- ❌ Not a replacement for human judgment

CORE is a **controlled production pipeline** whose purpose is to converge toward working, constitutionally compliant software.

---

## Where to Start

New to CORE? Start with the functional description before reading the architecture:

- [**What It Does**](https://github.com/DariuszNewecki/CORE/blob/main/.specs/northstar/CORE%20-%20What%20It%20Does.md) — what CORE is for, in plain language

Then:

- [How It Works](how-it-works.md) — the constitutional model and enforcement loop
- [Vocabulary](vocabulary.md) — every term CORE uses, defined precisely
- [Autonomy Ladder](autonomy-ladder.md) — current capability level (A3, unproven unattended) and roadmap
- [Getting Started](getting-started.md) — install and run your first audit
- [Audit in CI (no install)](cold-reviewer.md) — the GitHub Action
- [BYOR Quickstart](byor-quickstart.md) — govern your own repo from a naked machine, step by step
- [CLI Reference](cli-reference.md) — commands and workflows
- [Proof Index](proof-index.md) — each claim CORE makes, with its evidence and limits
- [Contributing](contributing.md) — how to engage with the project
