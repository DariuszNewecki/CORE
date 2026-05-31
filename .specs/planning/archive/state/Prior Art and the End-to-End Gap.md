# Prior Art and the End-to-End Gap

**A prior-art review for CORE**
Draft v1 — 2026-04-19

---

## 1. The problem this document addresses

If you run an engineering organisation in a regulated environment — pharma, med-devices, finance, safety-critical — and you want to use AI to generate production code without surrendering traceability, you face a specific integration problem. You cannot buy it as a product. You can buy parts of it.

This document names the parts, maps them to the adjacent categories that implement each part today, and identifies the gap that remains when those categories are combined. It is written for a technical decision-maker evaluating whether to build the integration in-house, commission it from a vendor, or adopt CORE.

The document makes no novelty claim. The claim is integrative: **CORE is a single runtime that covers the six components required for end-to-end AI-drift control; no single product in the adjacent categories covers all six.** Every claim below is stated so that it can be falsified by naming a product that contradicts it.

---

## 2. What end-to-end AI-drift control actually requires

Any system that intends to let AI generate production code under regulatory-grade discipline needs six distinct capabilities. These are the rows of the coverage matrix in §4.

1. **Policy declaration.** Rules expressed as law — versioned, authored by humans, machine-readable, not hard-coded. The engine evaluates; it does not author.
2. **Context construction.** Deterministic assembly of the exact information the generator sees before producing code. The context is an input to be governed, not a prompt to be tuned.
3. **AI code generation.** Non-deterministic production, explicitly untrusted, whose outputs are verified rather than accepted.
4. **Independent audit.** A detection system that runs against the generated artefact and is not authored by the same component that produced it. Independence is structural, not rhetorical.
5. **Autonomous remediation.** A closed loop in which detected violations trigger deterministic repair actions, with human review on policy change rather than on every fix.
6. **Consequence logging.** A full causal record from finding → proposal → approval → execution → file change → new finding. Complete enough that an auditor can reconstruct why any line of committed code exists.

Components 1–3 are widely understood. Components 4–6 are what separate a governed system from an assisted one.

---

## 3. The six adjacent categories

Each of the six categories below is a legitimate, mature industry category. CORE does not replace any of them. It occupies the space where none of them, individually or combined, currently operates.

### 3.1 Policy-as-code (OPA, Kyverno, Cedar)

Evaluates declarative policy against structured input at runtime. This is a well-developed category with strong tooling, good community patterns, and production maturity across cloud-native and IAM domains.

**What it covers:** policy declaration (1) as a category-defining capability.

**What it does not cover:** policy-as-code engines govern runtime decisions in deployed systems. They do not govern the code-generation process itself. There is no standard OPA deployment that decides whether a proposed source-file change is constitutional before it is written to disk.

**Falsifiable claim:** no general-purpose policy-as-code engine today is integrated with an AI code-generation loop such that the engine gates what the generator produces at source-file level, pre-commit, with autonomous repair when the gate fails.

### 3.2 Closed-loop refactoring (Moderne / OpenRewrite)

Applies deterministic, recipe-based transformations across large codebases. Recipes are authored, tested, composable, and run without AI in the critical path.

**What it covers:** autonomous remediation (5), provided the remediation is expressible as a refactor recipe.

**What it does not cover:** the remediation space is bounded by what recipes can express. There is no declared policy layer with authority hierarchy. There is no integrated AI generator. The system is not designed to govern AI output; it is designed to rewrite human-written code at scale.

**Falsifiable claim:** no Moderne-class tool today declares a constitutional policy layer, or governs the output of an AI generator, or operates under an authority hierarchy that distinguishes constitution from policy.

### 3.3 Agentic coders (Devin, Aider, Cursor Agent, SWE-agent)

Generate code iteratively with tests as oracle. Agents write, run, observe, and iterate until tests pass or the task is abandoned.

**What it covers:** AI code generation (3) as a category-defining capability. Weak partial coverage of context construction (2).

**What it does not cover:** tests-as-oracle is not a policy layer. The audit system is the same system that produced the code — there is no structural independence. There is no autonomous remediation driven by detected policy violations; there is iteration driven by failing tests. There is no consequence log with traceable causality.

**Falsifiable claim:** no publicly available agentic coder today operates under a declared, human-authored policy layer evaluated by a component architecturally independent of the generator, with a consequence log sufficient to reconstruct why each committed change exists.

### 3.4 Detect + suggest fix (SonarQube + AI CodeFix, Amazon Q Developer, GitHub Copilot Autofix)

Static analysis surfaces findings; an AI proposes fixes; a human accepts or rejects.

**What it covers:** independent audit (4) as a category-defining capability.

**What it does not cover:** the fix is a one-shot suggestion, not an element of a convergence loop. There is no metric for whether findings are being closed faster than created. There is no constitutional authority separating what policy declares from how enforcement runs. There is no autonomous acceptance path; human-in-the-loop is the default for every fix.

**Falsifiable claim:** no detect-and-fix product today exposes a convergence metric (rate of issue resolution vs. rate of issue creation) as a first-class operational signal, nor operates without human-in-the-loop acceptance for mechanically safe repairs.

### 3.5 Supply-chain provenance (SLSA, in-toto, Sigstore)

Records the build chain with cryptographic provenance. Answers: *what produced this artefact, from what source, under what process?*

**What it covers:** consequence logging (6) from a build-provenance perspective. Partial coverage of independent audit (4).

**What it does not cover:** SLSA records the chain of custody of a built artefact. It does not record the chain of custody of a *decision* — the reasoning that led to this file containing this line. It is silent on policy declaration, code generation, and remediation.

**Falsifiable claim:** no SLSA-level attestation today captures the reasoning chain from policy finding through proposal, approval, and execution, at the granularity needed to reconstruct why a specific source edit was made.

### 3.6 Regulated software frameworks (GAMP 5, ALCOA+, CSV)

Human-authored frameworks defining validation, data integrity, and qualification requirements for software in regulated environments. These are process frameworks, not tools.

**What it covers:** policy declaration (1) as specification language. Consequence logging (6) as a requirement.

**What it does not cover:** these frameworks describe what compliant systems must do; they do not implement it. They assume the team will compose tools and write SOPs to meet the requirements. Integration cost is borne entirely by the adopting organisation.

**Falsifiable claim:** no off-the-shelf tool today implements GAMP 5-aligned AI code governance end-to-end, such that adoption provides out-of-the-box coverage for computerised system validation against AI-generated artefacts.

---

## 4. Coverage matrix

|                           | Policy-as-code | Moderne-class | Agentic coders | Detect+AI-fix | SLSA class | GAMP 5 / ALCOA+ | **CORE** |
|---------------------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Policy declaration        | ◆   |     |     |     |     | ○   | ●   |
| Context construction      |     | ○   | ○   |     |     |     | ●   |
| AI code generation        |     |     | ◆   | ○   |     |     | ●   |
| Independent audit         |     | ○   |     | ◆   | ○   | ●   | ●   |
| Autonomous remediation    |     | ●   |     |     |     |     | ●   |
| Consequence logging       |     |     |     |     | ●   | ●   | ●   |

**Legend:**
◆ = category-defining capability
● = covered
○ = partial or weak
blank = not addressed

**How to read the matrix:** no column other than the CORE column contains a mark in every row. This is the claim the matrix makes and the claim it stands or falls on.

**How to falsify the matrix:** name a product that belongs to one of the six categories and that covers all six rows. Or: name a seventh category with a product that does.

---

## 5. Where CORE admits overlap

The document strengthens, rather than weakens, by acknowledging three places where CORE is not original:

1. **`.intent/` is a shim for a future policy engine of OPA's shape.** The current hand-authored YAML layer is a stand-in for a PolicyFactory/Manager that has not yet been built. Architecturally, `.intent/` is external to CORE at runtime — CORE accepts law as input. The long-term trajectory is to replace the shim with a real policy engine, at which point category 3.1 becomes a dependency rather than a gap.

2. **The audit engine borrows from static-analysis and compiler tradition.** Sensors, AST-based rules, and deterministic remediators are idioms inherited from category 3.2 and from classical static analysis. CORE's contribution is composition under a constitutional authority hierarchy, not the underlying detection technique.

3. **Consequence logging is conceptually adjacent to supply-chain provenance.** CORE's consequence log captures decision causality rather than build provenance, but the design idea — that an auditor must be able to reconstruct *why* an artefact exists — is continuous with SLSA's ambitions.

What CORE integrates is the *end-to-end*. What CORE claims to have invented is not any individual row.

---

## 6. The integration cost if you build it yourself

A regulated organisation that wants end-to-end AI-drift control and chooses to integrate from parts faces the following work:

- Select and deploy a policy-as-code engine (OPA, Kyverno, or Cedar) and author policy in its DSL. Integrate with developer tooling such that policy is evaluated against proposed source changes, not just runtime requests.
- Select an agentic coder or LLM integration and constrain its output to the policy surface. Build the context-construction layer that feeds it.
- Deploy a static-analysis stack (SonarQube or equivalent) and configure rules to mirror the policy layer. Accept that rules and policies will drift.
- Build the closed loop: detection → proposal → approval → execution → re-detection. Define convergence metrics. Wire autonomy thresholds.
- Build consequence logging, linking every edit to the finding, proposal, and approval that produced it. Validate sufficient for internal audit; extend for regulatory audit.
- Author the GAMP 5 / CSV documentation that qualifies each of the tools above as an instrument of record. Update documentation when any tool changes.

This is twelve to eighteen months of engineering for a team that knows what it is building. The failure mode is not that any one piece is hard. The failure mode is that the pieces drift against each other — the static analyser and the policy engine disagree; the context layer and the generator evolve independently; the consequence log becomes incomplete because no one owns the cross-cutting concern.

CORE is the cross-cutting concern, built as a runtime rather than as a procedure.

---

## 7. What this document does not claim

- It does not claim CORE is the only possible integration. Others can and may be built.
- It does not claim every CORE component is best-in-class against the category leader. It claims the integration is unique, not the parts.
- It does not claim completeness. Open items — full consequence logging, PolicyFactory, self-governance of `.intent/` — are documented and public.
- It does not claim CORE replaces GAMP 5, ALCOA+, or any regulatory framework. CORE is an instrument that, properly qualified, produces evidence that satisfies those frameworks.

---

## 8. For the reader who intends to falsify this

The testable claim is §4. The method is:

1. Pick a product from one of the six adjacent categories.
2. Identify a row in the coverage matrix where this document marks the category as blank, partial, or covered-but-not-defining.
3. Produce the evidence — documentation, source, or demonstration — that the product actually covers that row as a first-class capability.
4. Send it.

The document is intended to be honest enough that contradicting evidence would update it, not argue with it.

---

*Document status: draft v1. Intended audience: technical decision-makers in regulated environments evaluating AI-drift governance. Authors welcome falsifying evidence at the issue tracker of github.com/DariuszNewecki/CORE.*
