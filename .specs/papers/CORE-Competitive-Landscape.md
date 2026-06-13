---
kind: paper
id: CORE-Competitive-Landscape
title: 'CORE: Competitive Landscape and Feature Comparison'
status: canonical
doctrine_tier: informational
---

# CORE: Competitive Landscape and Feature Comparison

**Document type:** Strategic paper
**Location:** `.specs/papers/CORE-Competitive-Landscape.md`
**Status:** Authoritative
**Author:** Dariusz Newecki
**Audience:** Internal — commercial representation, investor conversation

---

## 1. How to Use This Document

CORE has no direct competitor. This is not a marketing claim — it is a structural fact that this document proves. The correct question is not "which product does the same thing?" but "which adjacent products cover which parts of what CORE covers, and what is left uncovered?"

A commercial representative should use this document to:

- Answer the question "how is this different from X?" for any named tool
- Explain why integrating existing tools does not close the gap
- Demonstrate that CORE's position is falsifiable, not defensive

The claims in this document are stated so they can be disproved. If a prospect names a product that falsifies one, that is important information. Record it.

---

## 2. The Six Capabilities Required for Governed AI Code Production

Any system that lets AI generate production code under regulatory-grade discipline needs six distinct capabilities. These are the rows of every comparison table in this document.

| # | Capability | What it means |
|---|---|---|
| 1 | **Policy declaration** | Rules authored by humans, versioned, machine-readable, with an authority hierarchy. The engine evaluates; it does not author. |
| 2 | **Context construction** | Deterministic assembly of exactly what the AI generator sees before producing code. The context is governed, not tuned. |
| 3 | **AI code generation** | Non-deterministic output, explicitly untrusted, whose results are verified rather than accepted. |
| 4 | **Independent audit** | Detection that runs against the generated artefact and is structurally independent of the component that produced it. |
| 5 | **Autonomous remediation** | A closed loop where detected violations trigger deterministic repair, with human review on policy change rather than on every fix. |
| 6 | **Consequence logging** | Full causal record: Finding → Proposal → Approval → Execution → File change → New finding. Sufficient for an auditor to reconstruct why any committed line of code exists. |

Capabilities 1–3 are widely understood and well served by existing tools.
Capabilities 4–6 are what separate a governed system from an assisted one.

---

## 3. The Six Adjacent Categories

CORE does not replace any of these categories. It occupies the space none of them, alone or combined, currently covers.

---

### Category 1 — Policy-as-Code

**Representative products:** Open Policy Agent (OPA), Kyverno, Cedar

**What they do:** Evaluate declarative policy against structured input at runtime. Mature category with strong production deployments in cloud-native and IAM domains.

**What they cover:** Policy declaration (1) — this is their defining capability.

**What they do not cover:** These engines govern runtime decisions in deployed systems. They do not govern the code-generation process at source-file level, pre-commit. There is no standard OPA deployment that decides whether a proposed source-file change is constitutional before it is written to disk and certainly not one that triggers autonomous repair when the gate fails.

**How to answer when a prospect says "we already use OPA":**
OPA governs what your deployed services are allowed to do at runtime. CORE governs what your AI-generated code is allowed to look like before it is committed. These are different control points on different artefacts. OPA does not see your source files; CORE does not govern your service mesh. They are not substitutes.

---

### Category 2 — Closed-Loop Refactoring

**Representative products:** Moderne, OpenRewrite

**What they do:** Apply deterministic, recipe-based transformations across large codebases. Recipes are authored, tested, composable, and run without AI in the critical path.

**What they cover:** Autonomous remediation (5), provided the remediation is expressible as a refactor recipe.

**What they do not cover:** The remediation space is bounded by what recipes can express. There is no declared policy layer with authority hierarchy. There is no integrated AI generator. The system is not designed to govern AI output — it is designed to rewrite human-written code at scale. It has no consequence log with causal traceability.

**How to answer when a prospect says "we use OpenRewrite for this":**
OpenRewrite rewrites code according to deterministic recipes you author. CORE detects constitutional violations in AI-generated code and executes governed repair actions with a full audit trail. The remediation primitive is similar. Everything surrounding it — the policy layer, the AI generator, the consequence chain, the convergence metric — does not exist in OpenRewrite.

---

### Category 3 — Agentic Coders

**Representative products:** Devin, Aider, Cursor Agent, SWE-agent, Claude Code, GitHub Copilot (agent mode)

**What they do:** Generate code iteratively with tests as oracle. Write, run, observe, iterate until tests pass or the task is abandoned.

**What they cover:** AI code generation (3) as their defining capability. Weak partial coverage of context construction (2).

**What they do not cover:** Tests-as-oracle is not a policy layer. The audit system is the same system that produced the code — there is no structural independence. Remediation is driven by failing tests, not by detected policy violations. There is no consequence log with traceable causality.

**The critical distinction:** CORE uses agentic coders as a component — as the code-producing worker inside a governed pipeline. It does not compete with them. The question is not "CORE or Cursor Agent?" The question is "Cursor Agent ungoverned, or Cursor Agent inside a governed pipeline?" CORE is the governance layer that makes agentic coders safe to deploy in regulated or high-accountability contexts.

**How to answer when a prospect says "we already use Claude Code / Cursor / Copilot":**
Good. CORE is not a replacement. CORE is the governance wrapper. Your agentic coder produces code; CORE audits it against your constitutional rules, detects violations, proposes corrections, logs the full consequence chain, and closes the loop. What you have today is a code-producing tool with no governance. What CORE adds is law.

---

### Category 4 — Detect + AI Fix

**Representative products:** SonarQube + AI CodeFix, Amazon Q Developer, GitHub Copilot Autofix, Snyk + AI suggestions

**What they do:** Static analysis surfaces findings; an AI proposes a fix; a human accepts or rejects.

**What they cover:** Independent audit (4) as their defining capability.

**What they do not cover:** The fix is a one-shot suggestion, not an element of a convergence loop. There is no metric for whether findings are being closed faster than they are created. There is no constitutional authority hierarchy separating what policy declares from how enforcement runs. Human-in-the-loop is the default for every single fix — there is no autonomous acceptance path. There is no consequence log linking a committed change back to the finding that caused it.

**How to answer when a prospect says "SonarQube already does this":**
SonarQube finds violations and proposes fixes one at a time. CORE measures whether your codebase is converging toward compliance over time, operates autonomously within constitutional limits, and produces a signed causal record linking every file change to the finding, proposal, and approval that produced it. For a regulatory audit, SonarQube produces a list of issues. CORE produces an evidence package.

---

### Category 5 — Supply Chain Provenance

**Representative products:** SLSA (Supply-chain Levels for Software Artefacts), Sigstore, SBOM tools (Syft, CycloneDX)

**What they do:** Record what was built, from what sources, by what process. Establish the provenance of build artefacts.

**What they cover:** Consequence logging (6), for build provenance — what artefact was produced and how.

**What they do not cover:** SLSA records that a binary was built from a specific commit using a specific pipeline. It does not record *why* that commit contains the code it contains — which violation was detected, which proposal was approved, which human governor authorised the change. CORE's consequence chain captures decision causality, not build provenance. These are complementary, not substitutes.

**How to answer when a prospect asks about SBOM / SLSA:**
SLSA tells you that your binary came from this commit, built by this pipeline, at this time. CORE tells you that line 47 of that commit exists because sensor X detected a violation in the AI-generated draft, proposal P-0123 was generated and approved by the governor, and re-audit confirmed resolution. The audit trail is causal, not just provenance. For regulated industries, both are needed.

---

### Category 6 — Regulatory Frameworks

**Representative standards:** GAMP 5, ALCOA+, IEC 62304, EU AI Act Articles 9 and 17, FDA 21 CFR Part 11

**What they are:** These are not products. They are regulatory requirements describing what compliant systems must do. They require traceability, validation, change control, and risk management documentation.

**What they cover:** They describe the requirements for consequence logging (6) and independent audit (4) in the strongest possible terms.

**What they do not cover:** Frameworks describe obligations; they do not implement them. A regulated organisation that must comply with GAMP 5 for computer system validation of AI-generated artefacts has no off-the-shelf tool today that provides this end-to-end. CORE is the instrument. The framework is the law CORE produces evidence for.

**How to answer when a prospect says "we handle compliance separately":**
CORE does not replace your compliance process. CORE is the instrument that produces the evidence your compliance process requires — specifically for AI-generated code, which your existing CSV and change control procedures were not designed to handle. Every time an AI agent modifies a file in a system under GxP, someone needs to document: what changed, why, who authorised it, and what verification followed. CORE makes that documentation automatic, queryable, and signed.

---

## 4. The Coverage Matrix

The claim: no single product in any adjacent category covers all six required capabilities. CORE is the only runtime that covers all six.

|                           | OPA / Kyverno | Moderne | Devin / Cursor | SonarQube + AI | SLSA | GAMP 5 | **CORE** |
|---------------------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1. Policy declaration     | ◆   |     |     |     |     | ○   | ●   |
| 2. Context construction   |     | ○   | ○   |     |     |     | ●   |
| 3. AI code generation     |     |     | ◆   | ○   |     |     | ●   |
| 4. Independent audit      |     | ○   |     | ◆   | ○   | ●   | ●   |
| 5. Autonomous remediation |     | ●   |     |     |     |     | ●   |
| 6. Consequence logging    |     |     |     |     | ●   | ●   | ●   |

◆ = category-defining capability  ● = fully covered  ○ = partial or weak  blank = not addressed

**How to read this:** No column other than CORE contains a mark in every row. This is the claim the matrix makes and the claim it stands or falls on.

**How to falsify this:** Name a product from one of the six categories that covers all six rows. Or name a seventh category with a product that does. If a prospect does this, that is important competitive intelligence. Record the product name and bring it back.

---

## 5. The Integration Cost Argument

A prospect may say: "We can integrate these tools ourselves."

The honest answer: yes, they can. The question is whether the integration actually closes the gap, and at what cost.

A regulated organisation that assembles the full stack from parts needs to:

- Select and deploy a policy-as-code engine and author policy in its DSL
- Select an agentic coder and constrain its output to the policy surface — building the context-construction layer themselves
- Deploy a static-analysis stack and configure rules to mirror the policy layer — accepting that rules and policies will drift against each other over time
- Build the closed loop: detection → proposal → approval → execution → re-detection, with convergence metrics
- Build consequence logging that links every file edit to the finding, proposal, and approval that produced it
- Author the GAMP 5 / CSV documentation that qualifies each tool above as an instrument of record, and update it whenever any tool changes

This is twelve to eighteen months of engineering for a team that knows what it is building. The failure mode is not that any single piece is hard. The failure mode is that the pieces drift against each other — the static analyser and the policy engine disagree; the consequence log becomes incomplete because no one owns the cross-cutting concern; the qualification documentation is always six months behind the toolchain.

CORE is the cross-cutting concern, built as a runtime rather than as a procedure.

---

## 6. What CORE Explicitly Does Not Claim

CORE does not claim to be the best static analyser — SonarQube has more rules.
CORE does not claim to be the best agentic coder — Devin has more agent polish.
CORE does not claim to be the best policy engine — OPA has better tooling ecosystem.
CORE does not claim to replace GAMP 5, ALCOA+, or any regulatory framework.

**CORE claims one thing: it is the only runtime that connects all six capabilities in a single governed pipeline with a constitutional authority hierarchy and a full consequence chain. No adjacent product or combination of adjacent products does this today.**

---

*This document is derived from the architectural landscape analysis in the CORE project knowledge base. Named products represent their categories as of mid-2026; the category analysis is stable even as individual products evolve. Update product names as needed; the structural gap arguments do not depend on any specific product remaining unchanged.*
