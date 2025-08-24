# 0. What is CORE? (And Why Should I Care?)

## The Problem: Software Forgets Its Purpose

Traditional software development is a battle against complexity and entropy. Over time, even well-designed systems suffer from:
- **Drift:** The code no longer matches the original design documents.
- **Duplication:** The same logic is written in multiple places because no one knew it already existed.
- **Degradation:** Small fixes and new features slowly erode the architectural integrity.

The **intent**—the *why* behind the code—gets lost.

## The Solution: A System That Remembers

**CORE is a self-governing AI development framework that never forgets its purpose.**

It's not just another code generator. It is a system designed to build other systems, governed by a machine-readable "constitution" that lives alongside the code. Think of it as an AI-powered software architect, lead developer, and QA engineer, all working in perfect sync, guided by a set of explicit rules you define.

**In short: CORE transforms your high-level goals into running, governed software, and ensures it *stays* aligned with your intent as it evolves.**

---

## How It Works: The Mind, Body, and Will

CORE's architecture is a simple trinity:

*   🏛️ **The Mind (`.intent/`):** The Constitution. This is where you, the human, declare your intent. It contains the principles, architectural rules, and goals for your project. It is the timeless source of truth.

*   🦾 **The Body (`src/`):** The Machinery. A set of simple, reliable tools that can write files, run tests, and analyze code. Its job is to act, not to think.

*   🧠 **The Will (LLMs):** The Reasoning Layer. An orchestrated set of specialized AI agents that act as the system's "brain." The Will's sole purpose is to read the **Mind** and use the **Body's** tools to make the intent a reality.

This separation is not just a guideline; it's a law enforced by CORE's own "immune system" (`ConstitutionalAuditor`). The Will can *never* take an action that violates the rules laid down in the Mind.

---

## Who Is This For?

CORE is for developers and teams who believe that:
- **Clarity** is more important than cleverness.
- **Governance** isn't bureaucracy; it's a competitive advantage.
- **Traceability** and **safety** are non-negotiable, especially when working with AI.

If you want to build systems that are resilient, auditable, and continuously aligned with their purpose, CORE is for you.

## Next Steps

Now that you understand the *why*, you're ready for the *how*.

1.  **[The CORE Philosophy (`docs/01_PHILOSOPHY.md`)](docs/01_PHILOSOPHY.md)** — For a deeper dive into the principles.
2.  **[The README (`README.md`)](../README.md)** — For instructions on how to get started and run the code.