# Constitutional Peer Review

## 1. Principle: Proactive Self‑Improvement

One of CORE’s foundational ideas is that a governed system should not merely **maintain** its constitution — it should actively **improve** it.

Constitutional Peer Review is the mechanism that allows CORE to periodically ask:

> **“Is our constitution the best it can be?”**

This feature enables CORE to use Large Language Models (LLMs) as **external expert reviewers**. These AI systems can:

* identify gaps,
* highlight ambiguities,
* suggest clarifications,
* propose structural improvements.

But critically:

> **LLMs may *recommend* changes — they can never *apply* them.**

Human operators remain fully in control at every step.

---

## 2. The Workflow: Safe, Human‑in‑the‑Loop

Peer review is a **governed**, **non-destructive**, and **human-led** process.

It consists of three stages:

1. *(Optional)* Export the constitutional bundle
2. Request the AI peer review
3. Translate feedback into actionable governance steps

---

## 3. Step 1 — Export the Constitutional Bundle (Optional)

This step packages the entire Mind (`.intent/`) into a single file that can be:

* inspected manually,
* shared across models,
* analyzed offline.

Run:

```bash
poetry run core-admin review export
```

This command:

* reads `meta.yaml` to find all constitutional files,
* packages them into:
  **`reports/constitutional_bundle.txt`**.

This bundle is what external reviewers will analyze.

---

## 4. Step 2 — Requesting the AI Peer Review

This is the main workflow. It automates everything:

```bash
poetry run core-admin review constitution
```

What happens internally:

1. CORE re‑exports the constitutional bundle.
2. Loads specialized instructions from:

   * `.intent/prompts/constitutional_review.prompt`
3. Sends the bundled constitution + instructions to the LLM assigned to the **SecurityAnalyst** role.
4. Writes the results to:

   * **`reports/constitutional_review.md`**

The output is a structured Markdown report containing:

* strengths,
* weaknesses,
* unclear sections,
* missing principles,
* inconsistencies,
* actionable suggestions.

This is a **second opinion** from an intelligent external reviewer.

---

## 5. Step 3 — Taking Action on the Feedback

The peer‑review output is advisory.
Nothing changes automatically.

Human operators are responsible for reading the report and deciding what actions to take.
Common follow‑ups include:

### **A. Add to the Project Roadmap**

If the feedback identifies a gap (e.g., *“Secrets management policy lacks rotation rules”*), it should be added to:

* the roadmap,
* or the technical debt log.

### **B. File a Constitutional Proposal**

Strong suggestions should be translated into a formal amendment:

```
.intent/proposals/cr-new-rule.yaml
```

Then proceed with:

* `proposals sign`
* `proposals approve`
* automatic canary audit

### **C. Update Governance Artifacts**

Some feedback may concern:

* unclear roles,
* inconsistent naming,
* stale schemas,
* missing principles.

These changes also require the normal proposal workflow.

---

## 6. Why Peer Review Matters

Constitutional Peer Review gives CORE:

* **an external viewpoint**,
* **a source of expert critique**,
* **a mechanism for evolving governance**,
* **a way to detect blind spots**,
* **a structured, safe feedback loop**.

It is one of the key systems enabling CORE to become **self‑reflective** while remaining **human‑controlled**.

This closes the loop in CORE’s governance philosophy:

> **The Mind defines the rules.
> The Auditor enforces the rules.
> Peer Review improves the rules.**
