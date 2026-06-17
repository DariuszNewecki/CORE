# CORE — BYOR / GRC Program — Open Threads

**Status:** Working backlog (derived, non-authoritative)
**Location:** `.specs/planning/CORE-BYOR-Program-Backlog.md`
**Audience:** Internal — engineering sequencing for the BYOR adoption surface + the GRC commercial wedge
**Created:** 2026-06-17

---

## 0. How to read this

Derived backlog for the BYOR/GRC program. The *shape* is set by `CORE-BYOR.md`
(paper); decisions land as ADRs grounded in it; ship-state is the issues/ADRs
themselves. This doc only sequences what is open after the 2026-06-17 session
that parametrized the obligation layer and ratified + implemented ADR-111.

---

## 1. Done 2026-06-17 (context)

- **Obligation layer parametrized** (`57379c9d`) — code is artifact type #1, not
  CORE's scope; Final Invariant generalized ("never produce *work* it cannot defend").
- **`CORE-BYOR.md`** (paper, draft) — domain-general adoption surface; "Repository"
  is the single parametrization seam; two maturity axes (Autonomy × Reach); GRC
  gap-analysis as the first paid wedge under an honesty guardrail.
- **ADR-111** (accepted) + implemented (`d0418920`) — `project onboard` *delivers*
  the authored starter (machinery floor + 4-rule constitution) into `<target>/.intent/`;
  generator path removed. **#640 step 1 closed**, verified end-to-end.

---

## 2. Open threads

### T1 — Verify consumer-mode enforcement  **[GATE]**
Does the delivered starter actually *enforce* in a consumer repo? `code audit
--offline` from inside an onboarded repo *loaded* the four starter rules but logged
them as "no enforcement mappings." Confirm enforcement (or fix the starter /
F-10 consumer-audit path) **before** any doc promises self-serve. Domain: F-10 /
ADR-108. **Gates T2.**

### T2 — #640 step 2: newcomer docs  **[blocked on T1]**
Point `docs/cold-reviewer.md`'s "no `.intent/`" dead-end at `project onboard`; add a
"govern your own repo" step to README / getting-started. Per ADR-111 D6, MUST NOT
promise the self-serve path until T1 is confirmed (and #674 for `pip install` users).

### T3 — #674: ADR-108 D3 machinery-in-wheel
Bundle the machinery floor in the `core-runtime` wheel + loader fallback so
`pip install` adopters can onboard, not only source-tree runs. Unblocks wheel-user
BYOR. Tracked: issue #674.

### T4 — `work/`-staging airlock for onboard  **[design, deferred by governor]**
Decision deferred: keep "write into the named repo" (dry-run + refuse-if-exists as
the rails) vs. add a `work/<name>/` staging airlock the operator promotes. If
adopted → amend ADR-111 D3 + the implementation. Most relevant to the GRC/regulated path.

### T5 — Remaining BYOR-grounded ADRs (`CORE-BYOR.md` §9)
- **T5a** — Repository adapter interface (the concrete F-41/F-42/F-43 binding).
- **T5b** — GRC document/records Repository type + regulation→checkable-Intent
  representation. The commercial centerpiece; also the hardest part (RegTech).
- **T5c** — Per-finding attestation (proven / judged / attested) — the honesty
  guardrail made mechanical.

---

## 3. Sequencing

T1 first — cheap, and it gates the on-ramp's honesty. Then T2 (docs) and T3 (#674)
complete code-BYOR end-to-end for all users. T5b is the commercial payoff (GRC) and
the largest effort — where the real RegTech value and the hard intent-representation
problem live; T5a is its prerequisite. T4 is a parallel design call. The commercial
center of gravity is GRC (governor decision 2026-06-17); code self-development runs
on a maintenance track meanwhile.

---

## 4. References

- `CORE-BYOR.md` — the program's shape (grounds the ADRs below)
- ADR-111 — `project onboard` delivers the authored starter (#640 step 1)
- ADR-108 (D3 → #674), ADR-075 (namespace), ADR-090 (multi-domain)
- #640 (BYOR), #674 (wheel packaging)
