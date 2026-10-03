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

## Choose your path

| You want to… | Start here | You need |
|---|---|---|
| Audit code against rules on your machine | [Start a governed project](start-a-project.md) | Python 3.12+ |
| Add ready-made rules to a governed repository | [Add a rule pack](adopt-a-pack.md) | Python 3.12+ |
| Block pull requests that break the rules | [Audit in CI](cold-reviewer.md) (GitHub) · [pre-commit or GitLab](other-ci.md) | A repository with a `.intent/` |
| Bring an existing repository under governance, with rules fitted to it | [Govern your own repository](byor-quickstart.md) | `core-cli` and a running CORE |
| Run the whole loop — audit, propose, approve, fix, verify — and see CORE govern itself | [Run the full runtime](getting-started.md) | Docker, Poetry; an LLM only for code generation |
| Check compliance documents against a regulation | [Run a GRC gap analysis](grc-gap-analysis.md) | The full runtime |
| Upgrade an existing installation | [Upgrade a CORE database](upgrading.md) | — |
| Build on CORE's API | [API contract](reference/api.md) | — |

CORE ships two command-line tools. `core-admin` (`pip install core-runtime`) runs CORE
on your machine and operates a CORE installation. `core` (`pip install core-cli`) is a
small client for a running CORE: proposals, the remediation lane, onboarding. See
[which one you need](cli-reference.md).

## Know this first

- **Not production-attested.** CORE's own
  [production-readiness verdict](https://github.com/DariuszNewecki/CORE/blob/main/.specs/attestations/production-readiness.yaml)
  is NOT ATTESTED. Do not leave it unattended on code that matters.
- **No API authentication.** The API binds to `127.0.0.1` and trusts every caller.
  Keep it there.
- **An LLM is optional.** Auditing, rule packs, CI gating and the deterministic fixes
  need none. Code generation, rule induction and judged GRC verdicts do; CORE names no
  vendor and works with a local model server or an external API.
- **Open and complete.** Everything on this site is in the open-source product (MIT),
  free indefinitely. Commercial offerings add usability and scale around it, never a
  missing capability (ADR-084).

## Understand it

- [**What It Does**](https://github.com/DariuszNewecki/CORE/blob/main/.specs/northstar/CORE%20-%20What%20It%20Does.md) — what CORE is for, in plain language
- [How It Works](how-it-works.md) — the constitutional model and enforcement loop
- [Autonomy Ladder](autonomy-ladder.md) — current capability level (A3, unproven unattended)
- [Proof Index](proof-index.md) — each claim CORE makes, with its evidence and limits
- [Vocabulary](vocabulary.md) — every term CORE uses, defined precisely
