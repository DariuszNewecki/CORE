<!-- path: .specs/papers/CORE-ConservationGate.md -->

# CORE — The ConservationGate

**Status:** Canonical
**Authority:** Constitution
**Scope:** All LLM-produced code changes

---

## 1. Purpose

This paper defines the ConservationGate — the runtime Gate that ensures
LLM-produced code preserves the logic of what it replaces.

---

## 2. The Problem

An LLM can produce code that is:
- syntactically valid
- stylistically correct
- constitutionally compliant

And still silently delete behavior. This is logic evaporation.

Logic evaporation is undetectable by syntax checks, linting, or
constitutional rule evaluation. It requires measuring the ratio of
preserved logic to original logic.

---

## 3. Definition

The ConservationGate measures the ratio of original code that is
preserved in the proposed replacement. If the ratio falls below the
declared threshold, the proposed code is rejected.

---

## 4. Measurement

The ConservationGate uses `LogicConservationValidator.evaluate()`:

**Inputs:**
- `original_code` — the source code before the LLM processed it
- `proposed_map` — a dict of `{file_path: proposed_content}`
- `deletions_authorized` — boolean. If True, the threshold is waived.

**Measurement:**
The validator extracts logical tokens from both original and proposed
code and computes the preservation ratio:

```
ratio = preserved_tokens / original_tokens
```

Logical tokens are function definitions, class definitions, and
meaningful statement bodies — not comments, whitespace, or formatting.

**Output:**
- `ok: True` if ratio >= threshold or deletions_authorized is True
- `ok: False` if ratio < threshold
- `data.ratio` — the measured ratio
- `data.blockers` — reasons for rejection if ok is False

---

## 5. Threshold

The minimum preservation ratio is **0.50**. This is a constitutional
Rule declared in `.intent/rules/will/autonomy.json` under rule ID
`autonomy.conservation.min_preservation_ratio`. It is blocking at
runtime. Changing the threshold requires a rule amendment — it is not
an operational configuration value.

A ratio below 0.50 means the proposed code has deleted more than half
of the original logical tokens. The proposal is rejected and the
original code is restored.

---

## 6. Invocation Point

The ConservationGate is evaluated in `ModularityRemediationService`
after the workflow reports success and before the result is accepted:

```
LLM produces code → workflow reports success → ConservationGate evaluates
→ passes: accept result
→ fails: revert to original, mark failed
```

It is also available for use by any Worker that invokes an LLM to
produce a replacement for existing code.

---

## 7. Authorized Deletions

When a Proposal explicitly authorizes deletions (`deletions_authorized=True`),
the ConservationGate threshold is waived. This is for cases where the
intent is to remove code — such as splitting a file, where the original
file's content moves to new files rather than being preserved in place.

Authorized deletions must be declared explicitly in the Proposal.
The default is False.

---

## 8. Non-Goals

This paper does not define:
- the token extraction algorithm in detail
- integration with the Canary
