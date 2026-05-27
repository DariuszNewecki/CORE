<!-- path: .specs/papers/CORE-Governance-Topology.md -->

# CORE-Governance-Topology

**Status:** Accepted
**Date drafted:** 2026-05-26
**Date accepted:** 2026-05-26
**Drafter:** Claude (CCC backlog review session 2026-05-26)
**Author:** Darek (Dariusz Newecki)
**Operationalizes:** UR-07 (Defensibility is Non-Negotiable) — primary; UR-06 (Continuous Constitutional Governance) — secondary
**Revision history:** r1 initial draft 2026-05-26; r2 same day, incorporates five-issue review (row 2 direction fix, escape-hatch removal, §2.5 normative definition, §2.4 enforcement-surfaces restructure, §6.3 aspirational scoping, §11.3 row 2 migration, §7.2 sharpened addendum rule, §10.3 R1 distinction); accepted 2026-05-26
**Closes definition gap surfaced by:** 2026-05-26 CCC sweep of run `db48491b` (133 candidates, ~98% dismissal rate)

---

## §1 — Purpose

CORE's governance content lives across four surfaces — Northstar, Papers, ADRs, and Enforcement surfaces (`.intent/`) — but the directional relations between them are undeclared. ADR-049 D2 established the Paper→Rule direction; every other edge of the governance graph operates by convention or ambient understanding.

This gap is not academic. It produced 133 CCC candidates in a single audit cycle that asked structural questions the constitution had no answer for. The triage burden was real (~3 hours human + AI time) and the actionable yield was small (3 fixes from 133 candidates). The scanner is enforcing doctrine that hasn't been authored.

This paper closes the gap by declaring:

- What each governance surface is (§2), including the normative-vs-descriptive distinction (§2.5)
- The directional relation graph between them (§3)
- What ADRs are constitutionally (§4)
- The lifecycle that moves content between surfaces (§5)
- What coherence invariants the system actually requires (§6)
- How in-flight states (Open Debts, addenda, closure markers) are first-class (§7)
- How this topology relates to the framework/project namespace split (§8)

Without this declaration, downstream work — CCC scanner redesign, governance application data model, framework/project split (#457) — has no doctrine to compare against. With it, each becomes a scoped engineering problem.

### §1.1 — Grounding in northstar

This paper operationalizes **UR-07 (Defensibility is Non-Negotiable)** as
primary grounding. UR-07 requires that every output be traceable to a stated
requirement. Traceability requires a *shape* — a declared topology — otherwise
the chain has no inspectable form and the constitutional record cannot be
defended. This paper declares that shape.

Secondary grounding is **UR-06 (Continuous Constitutional Governance)**:
governance is uninterrupted and applies to every artifact, including the
governance graph itself. The directional grid in §3 is the structural
expression of UR-06 reaching the meta-governance layer.

Row 1 of §3 itself ("Northstar → Paper: constitutional, Paper § cites UR-NN")
is satisfied for this paper by the citation above. Migration of pre-existing
papers to row 1 compliance follows the §11 backfill-on-touch posture; the
governor may extend §11 to explicitly enumerate row 1 in a future revision.

---

## §2 — The four governance surfaces

CORE governance lives across four declared surfaces. Each carries a distinct kind of content, authority class, audience, and mutability posture.

### §2.1 — Northstar (`.specs/northstar/`)

User requirements (UR-01..UR-08), foundational invariants, the *why* of CORE. Authored before any code, amendable only by governor declaration. The audience is the governor and any future GxP-class regulated customer reading the system's evidence trail.

Northstar content is the **rate-limiting layer**: nothing else in the governance graph may make claims that contradict a northstar invariant.

### §2.2 — Constitutional papers (`.specs/papers/`)

Architectural reasoning, timeless declarations, the *what* of CORE's design. Papers operationalize northstar invariants into structural claims: how Mind/Body/Will separate, how `.intent/` is accessed, how vocabulary is governed.

Papers contain both **normative** and **descriptive** content (see §2.5). Per ADR-049 D2, every *normative* paper claim must cite an enforcing rule or explicitly mark itself aspirational. Descriptive sections explain reasoning without constraining behavior and are exempt from the citation requirement.

### §2.3 — ADRs (`.specs/decisions/`)

Dated decisions, the *when-and-how-we-changed-our-mind* record. Append-only history: ADRs are not amended in place; later ADRs supersede earlier ADRs via explicit `Supersedes:` frontmatter declarations.

ADRs are decisions, not principles. An ADR records that a choice was made, by whom, when, against what alternatives, with what consequences. Constitutional principles live in papers; ADRs change them.

### §2.4 — Enforcement surfaces (`.intent/`)

Machine-readable governance: rule statements, enforcement mechanics, operational law, and meta-governance. What the audit pipeline actually checks. Authority class is `constitution` for blocking rules and `policy` for reporting rules; the distinction is operational, not structural.

The `.intent/` tree contains seven distinct artifact families:

**Rules** (`.intent/rules/`) — rule documents declaring constraints with enforcement levels. The primary normative content of the enforcement surface.

**Enforcement mechanics:**

- `.intent/enforcement/mappings/` — engine bindings declaring which engine enforces which rule and with what parameters
- `.intent/enforcement/contracts/` — JSON schemas constraining data structure shape (`data.contracts.*_conforms` rules reference these)
- `.intent/enforcement/config/` — operational config (`action_risk.yaml`, etc.) governing runtime behavior parameters
- `.intent/enforcement/remediation/` — mapping rules to fix actions (`auto_remediation.yaml`)

**Operational law:**

- `.intent/workers/` — worker declarations (identity, schedule, capabilities)
- `.intent/workflows/` — workflow definitions
- `.intent/policies/` — policy YAML declarations
- `.intent/taxonomies/` — vocabulary registers (capability taxonomy, principal roles)
- `.intent/governance/` — meta-governance (projections inventory, drainer registry)
- `.intent/constitution/` — constitutional fragments

**Meta:**

- `.intent/META/` — schemas, enums, vocabulary projection (the projection of `CORE-Vocabulary.md`'s canonical section per ADR-023)

Rules are the **primary enforcement surface**; the other six families operationalize, parameterize, or contextualize the rules. For §3's directional grid, **"Rule" in rows 4, 7, 8, 9, 10 is shorthand for any artifact in `.intent/`** — all enforcement surfaces are subject to the same governance posture. A change to a mapping, contract, config file, worker declaration, or taxonomy carries the same row 4 requirement as a change to a rule statement: the governing ADR's D-text must name the affected artifact.

An artifact that doesn't exist is not enforced; a paper claim without a citing artifact is aspirational; an ADR decision without a shipped artifact in `.intent/` is in-flight (per §7).

### §2.5 — Normative vs descriptive claims

The §3 grid and §6 invariants depend on distinguishing two kinds of content within governance artifacts:

A **normative** claim contains MUST, MUST NOT, SHALL, MAY NOT, is constitutionally prohibited, or makes a categorical statement about what the system does or does not do. Normative claims constrain behavior.

A **descriptive** claim explains structure, history, or reasoning without constraining behavior. Descriptive claims contextualize, motivate, or document but do not themselves create enforcement obligations.

**Constitutional consequences:**

- Only normative claims trigger row 3's citation requirement (Paper → Rule). Descriptive paper sections are exempt; they may exist without a corresponding enforcement artifact.
- The §6.1 contradiction invariant operates only on normative claims. Two descriptive sections cannot contradict each other in the governance sense — they explain different things, or the same thing differently, but neither constrains behavior.
- §6.2 (vocabulary invariant) applies to both normative and descriptive content. Term usage must be consistent everywhere; reasoning matters less.

Authors are responsible for marking ambiguous claims as one or the other when intent is not obvious from phrasing.

---

## §3 — The directional relation graph

The core of this paper. The grid below declares which directional links between surfaces are constitutional (required), editorial (permitted but not required), and forbidden.

| # | From → To | Verdict | Mechanism |
|---|---|---|---|
| 1 | Northstar → Paper | **constitutional** | Paper § cites `UR-NN` it operationalizes |
| 2 | ADR → Paper | **constitutional (upward exception)** | ADR References block cites grounding paper(s). ADRs without grounding paper are in-flight migration debt per §11.3; no escape hatch is provided |
| 3 | Paper → Rule | **constitutional** (extends ADR-049 D2) | Normative paper § cites `<rule_id>` (`<rule_path>`) OR marks itself aspirational. Descriptive sections are exempt per §2.5 |
| 4 | ADR → Rule | **constitutional (strict)** | Every ADR that affects rule interpretation (statement, mapping, contract, OR scope/interpretation via clarification) MUST name the affected `.intent/` artifact in its D-text at the time of acceptance |
| 5 | ADR → ADR (supersedes) | **constitutional** (existing precedent) | Frontmatter `Supersedes:` field with scope ("partially", "fully") |
| 6 | ADR → ADR (related) | **editorial** | References block; explicit `Relates:` frontmatter for tighter coupling |
| 7 | Rule → ADR | **editorial** | Rule rationale cites ADR. Rules implementing a specific decision SHOULD cite the governing ADR; foundational hygiene rules (style, layout, purity) need not |
| 8 | Rule → Paper | **editorial** | Rule rationale cites paper § |
| 9 | Rule → Northstar | **forbidden (strict)** | Rules cite paper/ADR that operationalizes UR; direct `UR-NN` citation in rule rationale or metadata is governance-skip. No exceptions |
| 10 | Rule → Rule (cross-reference) | **editorial** | Rule rationale cites adjacent rule |

### §3.1 — The two governing principles plus one exception

**Downward links are constitutional** (Northstar → Paper → Rule): required to be linked because higher tiers are normative and must be operationalized to carry weight. Higher-tier without lower-tier link is aspirational governance.

**Upward links are editorial** (Rule → Paper, Rule → ADR, etc.): lower tiers can stand alone as foundational discipline; upward citations are documentation hygiene, not constitutional requirement.

**One upward exception is constitutional:** ADR → Paper (row 2). ADRs amend constitutional content and therefore require architectural grounding. An ADR without grounding paper is operating in a vacuum — the decision has no constitutional context to compare against. This exception applies only to ADRs because they are the one surface whose entire purpose is to amend the constitution; rules (lower tier) carry no such obligation.

**One direction is forbidden:** Rule → Northstar direct citation. The chain must always go through Paper/ADR. This prevents the architectural-reasoning layer from being skipped.

### §3.2 — Why row 4 is strict

The strict reading on row 4 — every ADR that affects rule interpretation must name the artifact in its D-text, even when the change ships later via addendum — is load-bearing. It prevents the failure mode the 2026-05-26 session surfaced repeatedly: ADR D-text saying one thing, governor clarification widening scope, implementation addendum recording the clarification, rule statement implementing the widened scope — and a reader of D-text alone being misled.

The cost of strict row 4 is editorial discipline at ADR acceptance time. The benefit is that the D-text remains the canonical reference; readers do not need to scan addenda to discover that scope was clarified.

### §3.3 — Why row 9 is strict

The strict reading on row 9 — rules may not directly cite URs, ever — prevents the architectural-reasoning layer from being bypassed. A rule that claims "Authority: UR-07" without an intermediate paper claims that the rule IS the operationalization of UR-07. If no paper exists to make that claim auditable, the rule is unfalsifiable: there is no architectural artifact to compare against.

The cost of strict row 9 is that any UR-load-bearing rule requires an operationalizing paper. The benefit is that the constitutional chain (UR → Paper → Rule) is always intact and inspectable.

---

## §4 — What ADRs are, and what they are not

ADRs are **dated decisions**. They record what changed, when, by whom, against what alternatives, with what consequences. They are not Constitutional papers; they amend the Constitution but are not themselves the Constitution.

The relationship: **papers state what is; ADRs record decisions about what to change.** A paper says "Mind/Body/Will are separated, and Body never imports Will." An ADR says "On 2026-05-19, we decided to extract `fix_actions.py:666` Body→Will import into a Body-layer facade by 2026-09-16, with closure path Option A." The paper is timeless; the ADR is timestamped.

### §4.1 — Append-only history

ADRs are append-only. Original D-text is preserved; amendments come as later addenda within the same ADR or via successor ADRs that explicitly supersede via frontmatter `Supersedes:` declaration.

This is not stylistic preference. It is the constitutional record's defensibility: a reader inspecting an ADR sees the moment-of-acceptance reasoning. Rewriting D-text would falsify the historical record and break commit-message references that point at specific decisions.

### §4.2 — Graduation: do ADRs become papers?

**This paper takes the "never" posture.** ADRs stay as the dated history. Papers are independently authored and maintained. When an ADR's content is constitutionally important enough to belong in a paper, the paper is authored or amended to incorporate the principle — but the ADR remains as the historical record of the decision that produced the paper change.

The alternative — "at stability, an ADR graduates into a paper section" — was considered and rejected because it conflates two different artifact types. Decisions and principles are not the same shape: decisions have alternatives, dates, and consequences; principles do not.

---

## §5 — Lifecycle: how an idea becomes enforced

The canonical lifecycle from concern to enforcement:

1. **Concern surfaces** — via incident, audit finding, architecture review, CCC candidate, or governor reconnaissance
2. **Discussion** — chat, draft, exploration; no formal artifact yet
3. **Paper authored or amended** (if no grounding paper exists, one must be authored or identified before ADR acceptance) — establishes the constitutional context the ADR will operate within
4. **ADR drafted** — governor authors `.specs/decisions/ADR-NNN-<slug>.md` with Context, Decision, Alternatives Considered, Consequences, Verification; per row 2, the ADR cites the grounding paper(s)
5. **ADR accepted** — governor sets `Status: Accepted`; per row 4 strict, every D-section that affects rule interpretation names the `.intent/` artifact
6. **Implementation** — rule authored or amended, mapping wired, contract authored, code shipped per ADR D-text
7. **Verification** — audit passes; ADR Verification section criteria satisfied
8. **Closure** — ADR status remains `Accepted` (ADRs are not closed; their implementation is closed); the `.intent/` artifact is active and enforcing

Steps 1–5 are governor-authored. Step 6 may be Claude-executed under the standard reconnaissance-before-editing posture. Step 7 is governor-verified. Step 8 is implicit when verification passes.

Not every concern produces an ADR. Foundational engineering hygiene (code/style, code/layout) ships as rules without an ADR moment, because there is no "decision" to record — the discipline was always there. Per row 7 editorial, this is permitted.

---

## §6 — Coherence requirements (what the CCC should actually check)

The governor's session-end framing of CCC's purpose: "no contradictions, same vocabulary, same logic." This translates into three invariants the scanner should check directly, rather than via formal-traceability heuristics:

### §6.1 — Contradiction invariant

No two governance artifacts may make conflicting **normative** claims about the same concern (descriptive content is exempt per §2.5). If paper §A says "X is constitutionally prohibited" and rule R says "X is permitted under condition Y," that is drift regardless of formal mapping.

### §6.2 — Vocabulary invariant

The same concept must use the same term across all surfaces (applies to both normative and descriptive content). Vocabulary projections (per ADR-023) are the enforcement mechanism: a term defined in `CORE-Vocabulary.md` is the canonical name; uses elsewhere must conform.

### §6.3 — Logic invariant (aspirational, pending pattern register)

Similar problems must be solved with the same shape. Inconsistent solutions to similar problems are drift even when no contradiction or vocabulary issue is present.

**Aspirational status:** scanner enforcement of this invariant is deferred pending authoring of a canonical pattern register (`.intent/governance/patterns.yaml` or equivalent). Without a register, "similarity" is an LLM judgment call susceptible to the same hallucination failure modes that motivated this paper. The seed set of established patterns includes:

- **Closure ADR pattern** — Body-layer facade with injected callable for cross-layer dependency closures (ADR-051 precedent; ADR-063 and ADR-064 instances)
- **Vocabulary retirement pattern** — `enums.json` amendment + DB CHECK constraint update + Python class migration + ALCOA-aware backfill (ADR-068 D5 precedent; ADR-059 D2 instance)
- **Append-only closure marker pattern** — preserve original text + add dated/attributed marker pointing at the authoritative artifact (used 3× in 2026-05-26 R3b sweep: ADR-042 rationale, ADR-023 D5.3 footnote, ADR-011 Open Debts closure)
- **Sandbox-execution pattern** — write-bearing atomic actions execute in `/tmp/core-action-sandbox-<uuid>/` worktree (ADR-071 D2.2 precedent)

Authoring the pattern register is a follow-up artifact after this paper's acceptance. Until it exists, §6.3 is declared as governance posture but not scanner-enforced.

---

## §7 — Open Debt, addenda, and other in-flight states

Governance content is not always finished at acceptance. Four in-flight states are first-class, not drift:

### §7.1 — Open Debts

ADRs may declare known governance debt in an Open Debts section. The 2026-05-26 ADR-011 case is canonical: at acceptance, the ADR declared "A governance rule encoding this principle is not yet authored" as Open Debt. The rule was subsequently authored. The closure pattern (§7.4) brings the Open Debt's status current.

### §7.2 — Implementation addenda

ADRs may carry implementation addenda recording details that emerged during implementation but do not change the original D-text. **Implementation addenda may not contain governor clarifications that change the enforcement scope, the set of artifacts affected, or the implementation shape that was declared in the original D-text. Any such change must appear in the D-text as a dated amendment, not in an addendum.**

The boundary: addenda are for *implementation context* (which engine was chosen, which test fixtures were needed, what minor structural choices the implementer made within the declared scope). They are not for *scope expansion* or *interpretation widening* — those modify governance semantics and must appear as D-text amendments per row 4 strict.

The ADR-023 D5.3 case from the 2026-05-26 session illustrates the failure mode this rule prevents: the original D5.3 restricted `authoritative_paper` paths to `.specs/papers/`, but a governor clarification widened the scope to `.specs/` and `.intent/` and recorded the clarification in the Implementation addendum (Part 3/4). A reader of D5.3 alone was misled. Under this paper's row 4 strict + §7.2 sharpened rule, the clarification would have been recorded as a D5.3 amendment at the time of clarification.

### §7.3 — Deferred implementation

ADRs may declare that implementation is deferred (e.g., ADR-068 D5: "Implementation is deferred; no `src/` changes are made at ADR acceptance"). The ADR is accepted; the rule/code change ships later. Per row 4 strict, the ADR's D-text still names the artifacts that will be changed.

### §7.4 — Closure markers (append-only ADR convention)

When an Open Debt is closed or deferred implementation ships, the ADR is updated with a dated closure marker inline, preserving original text. The 2026-05-26 ADR-011 case used:

```markdown
**Closed (Open Debt status as of YYYY-MM-DD):** Rule `<id>` was subsequently
authored at `<path>` (enforcement: <level>, authority: <class>). [...]
```

The closure marker is the canonical mechanism. It preserves the historical record while making current state discoverable for a reader of the ADR alone.

---

## §8 — Framework / project namespace split (forward reference to #457)

Every governance artifact belongs to a namespace — `framework` (ships with CORE, applies to any governed project) or `project::<name>` (specific to a named repo, with CORE itself being `project::core`). The CORE deployment is the framework + `project::core`. A BYOR deployment is the framework + `project::<external>`.

This paper declares the **constitutional principle** that the namespace split exists. The operational mechanics — tagging convention, classification mapping, manifest format — are governed by the ADR filed under issue #457.

§8 is intentionally brief here. The substance is the existence of the principle, not its mechanics.

---

## §9 — What this paper is NOT

This paper does not govern:

- **The content of any specific rule, ADR, or paper.** This paper is about structure, not content. Specific governance decisions belong in ADRs and papers; this paper governs how those artifacts relate.
- **The CCC scanner implementation.** This paper provides what the scanner should compare against; scanner-prompt work is a separate engineering exercise.
- **The governance application data model.** This paper is the prerequisite, not the design. Once accepted, the data model becomes a scoped engineering problem.
- **Source code under `src/`.** Source is governed by the enforcement surface; the enforcement surface is governed by this topology. Source itself is not in scope here.
- **The pattern register (§6.3).** §6.3 declares the logic invariant as aspirational and names the seed pattern set; authoring the register is a follow-up artifact.

---

## §10 — Implementation consequences

### §10.1 — Immediate

Once accepted, this paper:

- Provides the comparison surface for CCC checks. R3a (rule→ADR) and R2 (rule→northstar) become structurally invalid per rows 7 and 9; either suppress them or rewrite them against the coherence invariants from §6.
- Unblocks #457 (framework/project split). The split's ADR can reference §8 of this paper.
- Establishes the data-model surface for the future governance application.
- Closes the "ambient understanding" gap that R3a and R2 candidates kept exposing.

### §10.2 — New CCC check classes enabled

- **Row 2 verification:** every ADR cites at least one grounding paper in its References block. Grep-checkable.
- **Row 4 verification:** for every governance change in `.intent/` (rule statement, mapping, contract, config, worker, taxonomy), there must be an ADR whose D-text names the affected artifact. Grep-checkable, not LLM-judged.
- **Row 3 verification:** every normative paper § cites an enforcing rule or marks itself aspirational. Extends ADR-049 D2 (originally scoped to imports/layer-boundaries/component-responsibilities) to all normative claims. Scanner-checked via ROW3_CITATION (ADR-073 D6) using §2.5's normative-marker register at `.intent/enforcement/config/normative_markers.yaml`.
- **§6.1 contradiction invariant:** pairwise scan of normative claims across governance artifacts for conflicts on the same concern.
- **§6.2 vocabulary invariant:** scan for term usage that diverges from canonical vocabulary projections.
- **§6.3 logic invariant (deferred):** scan for problem-pattern instances that diverge from registered precedent shapes. Requires the pattern register from §6.3; not enforceable today.

### §10.3 — CCC check classes to suppress or reshape

- **R3a (rule→ADR coverage):** per row 7 editorial. Suppress.
- **R2 (rule→northstar coverage):** per row 9 forbidden. Suppress.
- **R1 — proximity-based (adjacent-ADR cross-reference):** the structural premise — that adjacent ADR numbers are topically adjacent — is wrong; sequencing is by authoring order. Suppress.
- **R1 — relationship-based (scoped):** ADR pairs with explicit `Relates:` frontmatter declarations are a defensible check target. Retain a scoped R1 check that operates only against explicitly-related ADR pairs, looking for contradiction per §6.1 rather than absence of cross-reference.

---

## §11 — Migration handling

Three rows in §3 (rows 2, 4, and 9) impose constitutional requirements that pre-existing artifacts may not satisfy. Migration handling for each:

### §11.1 — Row 4 migration: backfill on touch (recommended)

Strict row 4 applies to ADRs accepted from this paper's acceptance date forward. Pre-existing ADRs are honored as-written but become candidates for backfill whenever they are amended for any other reason. This matches CORE's existing posture (incremental compliance, no big-bang migrations) and bounds the editorial cost.

Alternative postures considered:

- **Grandfather (cheapest):** strict applies only to ADRs accepted from acceptance date forward; pre-existing ADRs are never required to comply. Cost: zero. Risk: pre-existing ADR drift remains untracked.
- **Audit + backfill (most expensive):** one-shot governor pass to amend every existing ADR out of compliance. Cost: substantial editorial work across ~70 ADRs. Benefit: clean state from day one.

The middle path (backfill on touch) is recommended because it captures most of the benefit at proportional cost.

### §11.2 — Row 9 migration: audit + backfill (recommended)

Row 9 strict (forbidden Rule→Northstar direct citation) likely has fewer retroactive cases. Any existing rule with `Authority: UR-NN` metadata or direct UR citation in rationale is in violation. Recommend: one-shot governor audit + backfill, because the population is likely small and the violations are mechanical to detect (`grep -rn "UR-\d+" .intent/rules/` gives the candidate list).

### §11.3 — Row 2 migration: backfill on touch (recommended)

Row 2 strict (ADR must cite grounding paper) has retroactive consequences similar to row 4. Most existing ADRs cite related ADRs in References blocks; not all cite grounding papers explicitly. Apply the same backfill-on-touch posture from §11.1: pre-existing ADRs are honored as-written; when amended for any other reason, ADRs are brought into row 2 compliance by ensuring the References block names at least one grounding paper.

For ADRs that genuinely have no grounding paper (some early-phase decisions predate the relevant papers), backfill may require authoring the missing paper first. In that case the migration is staged: paper authored → ADR amended to cite it → compliance achieved.

---

## §12 — References

- ADR-049 — Doctrine-rule parity; D2 establishes the existing Paper→Rule constitutional direction (row 3)
- ADR-066 — Unmapped-rules invariant; precedent for "silence is not a valid signal" framing applicable to §6
- ADR-023 — Vocabulary canonical store; the projection compilation pattern grounding §6.2 and the §7.2 cautionary example
- ADR-068 — Principal role taxonomy; the cognate namespace-declaration pattern grounding §4 and §7; the precedent for §6.3's vocabulary-retirement pattern
- ADR-070 — Source-projection coherence; the projection inventory pattern this paper extends
- ADR-051 — File-handler shared-excludes closure; the precedent for §6.3's closure-ADR pattern
- ADR-071 D2.2 — Worktree sandbox; the precedent for §6.3's sandbox-execution pattern
- Issue #457 — Framework/project namespace split (orthogonal axis; §8 references this)
- `.specs/papers/CORE-Mind-Body-Will-Separation.md` — precedent for paper §s with normative claims
- `.specs/papers/CORE-Constitutional-Foundations.md` — establishes the constitution-tier authority that §2.2 derives from
- 2026-05-26 CCC backlog review session — empirical surfacing of the definition gap; closed run `db48491b` (133 candidates triaged, ~98% dismissal rate, 3 ADR fixes shipped)
- 2026-05-26 r1 review (5 issues raised) — input to r2 revision: row 2 direction fix, escape-hatch removal, §2.5 normative definition, §2.4 enforcement-surfaces restructure, §6.3 aspirational scoping, §11.3 row 2 migration, §7.2 sharpened addendum rule, §10.3 R1 distinction
