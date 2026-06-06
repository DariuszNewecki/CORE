<!-- path: .specs/papers/CORE-URS-Verifier.md -->

# CORE — URS Verifier (Requirement Fulfillment Verification)

**Status:** Draft (initial conceptualization 2026-06-06 — operationalizes `.specs/requirements/URS-requirement-fulfillment-verification.md` v0.1)
**Authority:** Paper (architectural operationalization of the URS)
**Scope:** The architectural design of the URSSatisfactionSensor — a sensor that reads URS documents under `.specs/requirements/` and emits findings when their declared acceptance criteria are not satisfied by CORE's current runtime state.
**Audience:** Future implementer of the sensor; downstream ADR author.
**Drafter:** Claude (session 2026-06-06 — drafted under "keep going" continuation authorization at the close of an exploratory thread that produced the CONCEPT freeze + URS v0.1 + ADR-093 + this paper as a single coherent artifact chain).
**Relates:** `.specs/requirements/URS-requirement-fulfillment-verification.md` (the URS this paper operationalizes — Appendix A's provisional criterion-manifest shape gets its final form in §4 below). `.specs/concepts/CORE-URS-Intake-Concept.md` (the frozen pre-URS thinking that named the gap). ADR-093 (Feature/Extension class split + URS-line discipline — establishes the discipline this Verifier enforces). `.specs/papers/CORE-ConstitutionalCoherenceChecker.md` (CCC paper — sibling instrument in the coherence family; §12 below amends its §8). `.specs/requirements/URS-mechanism-coherence.md` (sibling URS at the rule-mechanism layer — §12 below amends its §3). ADR-091 D6 (canonical subject format the Verifier follows). F-41 artifact_type registry (the Verifier registers itself against).

---

## 1. Purpose

This paper operationalizes the URS for Requirement Fulfillment Verification. It closes the provisional shapes the URS deliberately deferred to paper-scope and specifies the architectural design choices needed before an implementing ADR can codify storage schemas, CLI surfaces, and scheduling.

The paper does **not** specify implementation details that are ADR-scope (database tables, dashboard widgets, exact CLI flags). It specifies the architectural shape from which those details flow.

The eight responsibilities this paper inherits from URS §7:

1. Define the criterion manifest's exact storage format.
2. Define the verifier_hint vocabulary or document why it remains free-form.
3. Specify the trusted-kernel boundary in concrete terms (list of modules).
4. Specify the fixture file format and location under `.intent/` or `.specs/`.
5. Specify the finding payload structure.
6. Specify the misclassification structural form — Reviewer 3's Stage 2 double-duty resolution.
7. Specify the URS-shape validation as a precondition to verification (R-011 enforcement).
8. Amend CCC paper §8 and URS-mechanism-coherence §3 to register this sibling instrument.

Each is addressed in a dedicated section below.

## 2. Grounding

The URS this paper operationalizes is grounded in **UR-07 (Defensibility is Non-Negotiable)** at the intent-runtime layer, with secondary grounding in **UR-06 (Continuous Constitutional Governance)**. This paper inherits both anchors. Where the URS says "CORE shall verify rather than assume," this paper specifies *how* the verification mechanism is shaped.

The architectural posture this paper follows from URS R-004: **author authority over verification strategy is preserved.** The paper specifies mechanism — it does not allow the mechanism to override URS-author declarations. Where the mechanism's classification of a criterion differs from the author's declaration, the paper specifies the *protest path* (misclassification finding) and refuses the temptation of silent reclassification.

## 3. Architectural Scope

The Verifier is implemented as a single sensor-class worker. Single, because the URS R-002 demands sensor-shape integration with the existing daemon cycle and the simplest sensor is one worker. Multiple verifiers (per URS, per class, etc.) would multiply scheduling complexity without a corresponding architectural gain.

The sensor's responsibilities, in execution order:

1. **Discovery.** Walk `.specs/requirements/` for `URS-*.md` and `*-URS.md` files (the two filename shapes the existing 5 URSs use; future URSs adopt the `URS-*.md` shape per consistency with §4.7 below).
2. **URS-shape validation.** For each URS file, check that it carries a criterion manifest in the form specified in §4. URSs without a manifest, or with a malformed manifest, produce a single `malformed_no_manifest` or `malformed_manifest` finding (per §11) and are skipped for criterion-level verification.
3. **Criterion extraction.** For each well-formed URS, extract its criterion list with declared `verification_class`, `verifier_hint`, and supporting fields.
4. **Per-criterion verification.** For each criterion, dispatch to the verification strategy for its declared `verification_class` (per §5). Emit one finding per non-satisfied verdict (per §9).
5. **Coverage manifest emission.** After the full pass, emit a coverage-manifest finding (per §9.3) summarizing every URS and every criterion as `checked` or `skipped`-with-rationale.
6. **Heartbeat + cycle close.** Standard worker close pattern; no Verifier-specific lifecycle beyond what the daemon already provides.

The Verifier reads. It does not write. It does not mutate URSs, manifests, fixtures, or any other source artifact. Its sole side effect is finding emission to the blackboard.

## 4. The Criterion Manifest — Final Storage Form

### 4.1 Decision: embedded YAML block in the URS body

The criterion manifest lives in an Appendix at the end of each URS document, as a fenced YAML code block. The Appendix is mandatory for URSs authored or substantively amended after ADR-093's acceptance date (2026-06-06).

Reasons for the embedded-YAML form over alternatives:

- **Single source.** The URS and its manifest stay together — one file to read, one file to author, one file to commit. Decoupling the manifest into a separate `.urs.manifest.yaml` introduces a synchronization burden the URS author would have to track manually.
- **YAML over table.** A Markdown table with one row per criterion is human-readable but breaks for criteria with multi-line `claim` or structured `evidence_required` fields. YAML accommodates structured values natively.
- **Appendix over frontmatter.** Frontmatter would put the manifest above the URS body's prose. Authors read prose first, criteria second; the manifest follows the §5 Functional Requirements section that names the criteria.

The Appendix title is `Appendix A — Criterion Manifest`. URS-requirement-fulfillment-verification.md already adopted this convention in its retrofit per ADR-093 D8.

### 4.2 Required fields per criterion

Each criterion entry shall declare:

```yaml
- id: <stable identifier>            # required; pattern ^[A-Z]+-[0-9]+$
  claim: <natural-language>          # required; one or more sentences
  verification_class: <enum>         # required; mechanical | behavioral | judgmental
  verifier_hint: <natural-language>  # required; see §4.4
```

These four fields are the URS R-001 minimum. URS authors **shall** declare all four.

### 4.3 Optional fields per criterion

The following fields **may** be declared per criterion. The Verifier honors them when present; absence is not a defect.

```yaml
- ...
  fixture_ref: <path>                # for behavioral; relative to repo root, under .intent/ or .specs/
  evidence_required: [<list>]        # mechanical/behavioral; what the Verifier should observe
  proxy_class: <enum>                # see §6 (Stage 2 double-duty)
  related_adrs: [<id>]               # for traceability; not Verifier-consumed
```

URS authors are encouraged but not required to declare these. The Verifier treats their absence as "use the conservative default" — e.g., for a behavioral criterion without `fixture_ref`, the Verifier emits `unverifiable_no_evidence_path` rather than silently passing.

### 4.4 The `verifier_hint` vocabulary

The hint remains **free-form prose** in this paper's design. The URS §6 Non-Requirements list explicitly left `verifier_hint` vocabulary open; this paper sustains that openness rather than imposing a structure prematurely.

Three honest reasons for keeping `verifier_hint` free-form:

- The vocabulary of evidence (grep patterns, fixture references, fixture+predicate combinations, human-evidence pointers, etc.) varies per criterion class and per criterion. A premature DSL would over-constrain URS authors.
- The Verifier consumes `verifier_hint` as guidance, not as authoritative spec. The verification strategy in §5 is class-driven; `verifier_hint` informs strategy execution but does not directly drive it.
- The future URS author who articulates a stable `verifier_hint` shape will have evidence the current author lacks. Locking the shape now is premature.

A future paper amendment may codify a `verifier_hint` structure if patterns emerge. Until then, treat the field as documentation aimed at human readers + the implementer of the verification strategy.

### 4.5 The closed `verification_class` vocabulary

Per URS R-001, `verification_class` is one of:

- **`mechanical`** — verification by predicate over current state. Examples: existence check on a file, grep over a code symbol, count over a database column. Deterministic, fast, no fixtures.
- **`behavioral`** — verification by exercising a fixture and observing system behavior. Examples: feed a known-malformed URS to the Verifier and check it emits the expected finding; invoke a chokepoint and check it refuses the right input. Deterministic given fixtures.
- **`judgmental`** — verification requires human evidence. Examples: "an outside developer reproduces the install from public docs alone" (URS #561). The Verifier does not attempt judgment; it produces a `requires_human_evidence` verdict.

The vocabulary is closed at three values. Extending it is a governance amendment, not a paper amendment.

### 4.6 Misclassification handling — see §6

The Verifier never silently reclassifies. See §6 for the structural form.

### 4.7 Filename convention going forward

New URSs adopt the `URS-<short-name>.md` filename convention (e.g., `URS-requirement-fulfillment-verification.md`, `URS-mechanism-coherence.md`). The three older `CORE-*-URS.md` files are grandfathered per ADR-093 D7. The Verifier accepts both filename shapes during discovery.

## 5. Verification Strategy per Class

The Verifier dispatches per `verification_class`. The strategies are distinct.

### 5.1 Mechanical class

Execution: a Python predicate over current state, invoked by the Verifier's mechanical-strategy module. The predicate has read-only access to:

- The filesystem (`.specs/`, `.intent/`, `src/`, `tests/`).
- The PostgreSQL database (read-only connection to `core.*` tables).
- The `IntentRepository` for governance state.

Each mechanical criterion's `verifier_hint` describes the predicate's intent in prose. The verification module owns the actual predicate code, organized as a registry keyed by URS-id × criterion-id. The future ADR specifies whether predicates live in `src/` (under a sensor-strategies subtree) or in `.intent/` (as declared YAML pointing at named predicates).

Outcomes: `satisfied`, `unsatisfied`, `unverifiable_no_evidence_path` (predicate not implemented yet), `misclassified` (per §6).

### 5.2 Behavioral class

Execution: a fixture-driven exercise where the Verifier feeds a known input (the fixture, per §7) to a CORE component and observes the response. The fixture file at `fixture_ref` declares the input and the expected behavior shape.

Each behavioral criterion's `verifier_hint` describes the exercise in prose; the verification module owns the fixture-loading + invocation + observation code, organized symmetrically with the mechanical-strategy module.

Outcomes: same closed set as §5.1.

### 5.3 Judgmental class

Execution: none. The Verifier emits `requires_human_evidence` directly. The verdict is the deterministic verdict for this class — the Verifier does not attempt judgment.

The finding payload (per §9) carries the criterion's `claim` so the governor reading the dashboard sees what evidence is being requested without re-deriving from the URS.

### 5.4 No LLM in any strategy

URS R-003 forbids LLM judgment in the verdict path. This paper sustains that constraint across all three strategies. No strategy invokes `cognitive_service`. No strategy reads `prompt_artifacts`. The Verifier's worker declaration explicitly omits `cognitive_capabilities`.

This is a deliberate constraint, not an oversight. The Verifier's job is to report observed state, not to make judgments. Adding LLM-as-judge would dilute the determinism the URS-line discipline depends on.

## 6. The Misclassification Verdict — Structural Form

### 6.1 The default path

When a criterion declares `verification_class: X` and the strategy-X module finds no resolvable predicate or fixture, the Verifier emits a `misclassified` verdict with payload:

```json
{
  "declared_class": "<X>",
  "resolved_class": "<unknown | Y>",
  "rationale": "<why X did not resolve>"
}
```

The `resolved_class` is `unknown` when no other class resolves either, or `Y` when class Y resolves (and the criterion's declaration appears to be the wrong class). The Verifier does **not** proceed under class Y — that would be silent reclassification. It emits the finding and moves to the next criterion.

### 6.2 Reviewer 3's Stage 2 double-duty resolution

Reviewer 3 flagged that `verification_class` does double duty: verification *strategy* (how do we check?) and criterion *kind* (what kind of claim?). These can diverge.

The optional `proxy_class` field (per §4.3) admits the divergence explicitly:

```yaml
- id: AC-001
  claim: "..."
  verification_class: behavioral  # kind: this is a behavioral claim
  proxy_class: mechanical          # strategy: a mechanical proxy resolves it
  verifier_hint: "grep ..."
```

When `proxy_class` is declared, the Verifier dispatches to the `proxy_class` strategy and reports the verdict against the declared verification class. The URS author retains authority — the divergence is *declared*, not inferred.

When `proxy_class` is absent and the declared `verification_class` doesn't resolve, the Verifier emits `misclassified` per §6.1. It does not infer that a proxy might exist.

### 6.3 The misclassification feedback is non-blocking

Per URS R-012, a misclassified verdict on one criterion does not halt evaluation of other criteria. The Verifier completes the full pass and reports each criterion's verdict independently.

## 7. The Fixture File Format

### 7.1 Storage location

Fixtures referenced by behavioral criteria live under one of:

- `.intent/fixtures/urs/<urs-id>/<criterion-id>.<ext>` — for fixtures that exercise governance state (declarations, rules, policies).
- `.specs/fixtures/urs/<urs-id>/<criterion-id>.<ext>` — for fixtures that exercise document state (URSs, papers, ADRs).

Both locations are constitutional surface per URS R-005. Fixtures **shall not** live under `tests/` — that would conflate test-suite cruft with constitutional fixtures.

The `<ext>` is whatever the fixture's content shape requires (`.yaml`, `.md`, `.json`, `.py`, etc.). The Verifier loads the file by path; the strategy module interprets the content.

### 7.2 Required fields per fixture

Each fixture file's header (frontmatter for Markdown; comment block for code; YAML keys for YAML) shall declare:

```yaml
urs_id: <id>           # required; matches the URS the fixture belongs to
criterion_id: <id>     # required; matches the criterion within that URS
intent: <prose>        # required; what this fixture exercises
expected_outcome: <prose>  # required; the behavior the strategy module asserts
```

These four fields are the fixture-shape minimum. The strategy module may require additional fields per-class; those are documented in the strategy module's docstring.

### 7.3 Fixture lifecycle

Fixtures are versioned with their URSs. When a URS amendment changes a criterion's claim, the criterion's fixture must be reviewed in the same change-set. The future ADR specifies whether this discipline is enforced (e.g., by an audit rule) or relies on reviewer attention.

Fixtures that fail to load (file missing, parse error) produce an `unverifiable_no_evidence_path` verdict for the criterion, with the rationale pointing at the load failure.

## 8. The Trusted Kernel

### 8.1 What the kernel is

Per URS R-007, the Verifier declares its **trusted kernel** — the body of code whose correctness is established by inspection rather than by verification through itself.

The trusted kernel exists to prevent the Verifier from degenerating into unaccountable meta-recursion. A Verifier whose entire mechanism depends on itself for correctness has no terminal evidence. The kernel is the terminal evidence: a small, inspectable body of code whose correctness is asserted by human review.

### 8.2 The kernel's membership (provisional list for the implementing ADR to refine)

The implementing ADR shall declare the kernel as an explicit Python list, importable by tooling. The membership shall include at minimum:

- The Verifier's worker entry point (the function the daemon invokes per cycle).
- The discovery walker (locates `URS-*.md` and `*-URS.md` files under `.specs/requirements/`).
- The manifest parser (extracts the YAML block from the Appendix and validates §4 fields).
- The verdict-class dispatcher (routes by `verification_class` to the strategy module).
- The finding-emission helper (constructs the per-finding payload per §9).
- The coverage-manifest builder (assembles the per-run summary per §9.3).

The strategy modules themselves (mechanical / behavioral / judgmental) are **outside** the kernel — they are too large for one-sitting inspection and they are exercised by the kernel rather than trusted by it. A bug in a strategy module produces a wrong verdict; a bug in the kernel produces a wrong-shape verdict on every criterion, which is detectable as a class.

### 8.3 The kernel size bound

The kernel is sized for inspection in one sitting. Per URS R-006 echoed: an inspector with no prior context shall be able to read the entire kernel and assess its correctness in 30–60 minutes. This is a soft bound, not a line-count cap. If the kernel exceeds the bound, the ADR's first revision shall refactor it down.

## 9. The Finding Payload Structure

### 9.1 Subject format

Per URS R-005, finding subjects follow `urs::<urs_id>::<criterion_id>` (canonical format per ADR-091 D2). The `urs_id` is the URS filename without extension (e.g., `URS-mechanism-coherence`); the `criterion_id` is the criterion's declared `id` (e.g., `R-005`).

Coverage-manifest findings use the subject `urs.coverage::<run_id>` — a separate namespace so coverage entries don't collide with per-criterion findings.

### 9.2 Per-criterion finding payload

```json
{
  "urs_id": "<id>",
  "criterion_id": "<id>",
  "claim": "<from manifest>",
  "verdict": "<satisfied | unsatisfied | unverifiable_no_evidence_path | requires_human_evidence | misclassified>",
  "verification_class_declared": "<from manifest>",
  "verification_class_resolved": "<actual class used; matches declared unless proxy_class>",
  "verifier_hint": "<from manifest>",
  "evidence_path": "<what was checked; class-dependent>",
  "fixture_ref": "<from manifest if applicable>",
  "rationale": "<short prose; required for unsatisfied/unverifiable/misclassified>"
}
```

Satisfied criteria emit no per-criterion finding per URS R-005 (silence-as-success). The coverage manifest still reports them (per §9.3) for completeness.

### 9.3 Coverage manifest payload

```json
{
  "run_id": "<uuid>",
  "ran_at": "<iso-8601 timestamp>",
  "urs_count": <int>,
  "criterion_count": <int>,
  "verdicts": {
    "satisfied": <int>,
    "unsatisfied": <int>,
    "unverifiable_no_evidence_path": <int>,
    "requires_human_evidence": <int>,
    "misclassified": <int>,
    "malformed_no_manifest": <int>,
    "malformed_manifest": <int>,
    "skipped": <int>
  },
  "skipped_details": [
    {"urs_id": "<id>", "criterion_id": "<id>", "rationale": "<prose>"}
  ]
}
```

Skipped entries require non-empty rationale per URS R-008. Items skipped without rationale are themselves coverage findings, emitted as per-criterion findings with verdict `skipped_without_rationale` (extending the closed verdict set for the malformed case is permitted because it represents a defect in the manifest, not a verdict on the criterion itself).

## 10. Sensor Declaration Shape

The Verifier ships as `.intent/workers/urs_satisfaction_sensor.yaml` with this declaration shape:

```yaml
$schema: "META/worker.schema.json"
kind: worker

metadata:
  id: workers.urs_satisfaction_sensor
  title: URS Satisfaction Sensor
  version: "0.1.0"
  authority: policy
  status: active   # ADR-scope decision; may start at paused per the URS-line maturation cadence
  rationale: >
    Implements ADR-093 + URS-requirement-fulfillment-verification.md.
    The fourth coherence-family instrument: walks .specs/requirements/
    and emits findings when declared URS criteria are unsatisfied by
    current runtime state.

identity:
  uuid: "<fresh uuid4, ADR-scope>"
  class: sensing

mandate:
  responsibility: >
    Read URS manifests, dispatch per-criterion verification, emit
    findings. No mutations. No LLM. Deterministic verdicts only.
  phase: audit
  permitted_tools: []
  scope:
    paths: []
    artifact_type:
      - urs   # ADR-scope: register a new F-41 artifact_type for URSs
              # covering .specs/requirements/*.md; or reuse spec_markdown
              # with a discriminator. The ADR decides.

implementation:
  module: will.workers.urs_satisfaction_sensor
  class: URSSatisfactionSensor
  requires_core_context: true
```

The `artifact_type` decision is ADR-scope per the §13 deferral list. Two viable paths: register `urs` as a new F-41 artifact_type (cleaner separation; declares URS as a first-class governance artifact) or reuse `spec_markdown` with a path-prefix discriminator (lighter touch; doesn't add to F-41's registry).

## 11. URS-shape Validation as Precondition

Per URS R-011 (authoring obligation: no new URS without manifest), the Verifier enforces shape validation as the first check per URS.

The check sequence per URS:

1. **Discovery filter.** Is the file under `.specs/requirements/` matching the URS filename pattern? If no, skip.
2. **Header presence.** Does the file's Markdown body include an `## Appendix A — Criterion Manifest` section? If no, emit `malformed_no_manifest` finding for the URS and skip criterion-level verification.
3. **Block extraction.** Does the Appendix include a fenced YAML code block? If no, emit `malformed_manifest` with rationale "appendix present but no YAML block."
4. **Field validation.** Does each criterion entry carry the four required fields (`id`, `claim`, `verification_class`, `verifier_hint`)? If any is missing, emit `malformed_manifest` with per-criterion rationale.
5. **Enum validation.** Is each criterion's `verification_class` in the closed set `{mechanical, behavioral, judgmental}`? If no, emit `malformed_manifest`.

Only after all five checks pass does the Verifier proceed to per-criterion verification. The malformed findings are themselves findings on the URS as a whole, not on individual criteria.

The grandfathered pre-URS-line URSs (per ADR-093 D7) are skipped at step 2 with rationale `pre_urs_line_grandfathered`. The Verifier emits a coverage entry but no malformed finding. Optional retrofit per ADR-093 §D7 changes this — once a grandfathered URS is retrofitted, the next Verifier run treats it as URS-line-discipline-bound.

## 12. Amendments to Sibling Documents

### 12.1 CCC paper §8 amendment

Per URS §7 and the CCC paper's R3 relationship to mechanism coherence, the CCC paper's §8 "Sibling Instruments" section requires an additional entry registering the URS Verifier:

> **Requirement Fulfillment Verification (`.specs/papers/CORE-URS-Verifier.md`)** — the fourth coherence-family instrument, verifying whether CORE's runtime state honors the claims its URSs make. CCC and the URS Verifier are complementary: CCC asks "do documents agree with each other?"; the URS Verifier asks "do documents' acceptance claims hold?" Both are deterministic verdicts (CCC for documents, the URS Verifier for runtime). Neither is autonomous; both are surfaced to the governor for triage and resolution.

The amendment lands when the ADR codifies this paper's implementation. The CCC paper edit is governor-authored or governor-confirmed Path A write.

### 12.2 URS-mechanism-coherence §3 amendment

Per URS §7 and the URS-mechanism-coherence URS's §3 prior-work table, the table requires a fourth row:

> | **Requirement Fulfillment Verification (this paper's URS)** | **URS claim vs CORE runtime state** | **Deterministic; declared-classification; URS-author authority** |

Same authoring discipline as §12.1.

### 12.3 ADR-093 reference closure

ADR-093 D5 deferred the Extension Manifest paper to "when the first new E-NN entry needs to land." This paper is the URS-side analog (a paper that operationalizes a coherence-family URS). The Extension Manifest paper remains separate work — different artifact class (E-NN attaches to interfaces; URSs verify state) — and is not addressed here.

## 13. Open Decisions Deferred to ADR

The following decisions are left to the implementing ADR. Each affects implementation but not architectural shape, so they belong in the ADR rather than this paper.

1. **The `artifact_type` for URSs.** Register a new `urs` artifact_type in `.intent/artifact_types/`, or reuse `spec_markdown` with a discriminator. §10 sketches the choice; the ADR decides.
2. **Predicate/fixture storage location.** Strategy modules carry the predicates and fixture-load logic. Whether predicates live in `src/will/workers/urs_satisfaction_sensor/strategies/` or are declared by YAML in `.intent/` and resolved by name is an ADR call.
3. **Run cadence.** Per-cycle (every daemon tick) or scheduled (e.g., on URS file changes). Sensor-shape default is per-cycle; the ADR may refine.
4. **CLI surface.** `core-admin specs verify [urs_id]` or similar; flags for `--format`, `--severity`, etc. ADR-scope.
5. **Dashboard widget.** Whether the governor dashboard surfaces URS-coverage as its own panel or routes URS findings through the existing Convergence Direction panel. ADR-scope.
6. **Worker `status: active | paused` at first ship.** This paper specifies `active` in §10 as the architectural default; the ADR may ship `paused` if implementation maturity warrants.
7. **Fixture lifecycle enforcement.** §7.3 names the discipline (fixtures reviewed with their URSs); whether enforcement is by audit rule or by reviewer attention is ADR-scope.
8. **The pre-URS-line URS retrofit cadence.** Whether any of the four grandfathered URSs gets retrofitted as part of the implementing ADR's ship, or all are deferred indefinitely per ADR-093 D7.

## 14. Path Forward

```
URS v0.1                              (shipped 2026-06-06)
   ↓
ADR-093                               (shipped 2026-06-06; URS-line discipline)
   ↓
THIS PAPER                            (shipped 2026-06-06; architectural operationalization)
   ↓
ADR-094 (or next number)              (codifies implementation: storage, CLI, scheduling)
   ↓
URSSatisfactionSensor implementation  (sensor worker + strategies + tests + fixtures)
   ↓
Live discipline                       (every new URS post-URS-line carries a manifest;
                                      Verifier emits findings on the existing dashboard)
```

The ADR is the next step. The paper is complete as drafted — it answers the eight responsibilities URS §7 named and adds §13's deferred ADR-scope decisions for the implementing author.

## 15. Closing Note

This paper completes the artifact chain from the CONCEPT (the gap recognition) through the URS (the requirements) to the architectural design (this document). The implementing ADR and the sensor code that follows it are downstream work; the governance frame for them is now stable.

Three things this paper deliberately did not do:

- It did not specify the exact wire format of `evidence_path` in the per-criterion finding payload — that's strategy-module-internal and stabilizes during implementation.
- It did not specify the URL or CLI shape of the dashboard widget — that's UX-scope, not architecture-scope.
- It did not pre-commit which grandfathered URSs (if any) get retrofitted in the first sensor-ship. That decision belongs with the governor and the implementing ADR's author.

The paper exists so that the implementing ADR has a stable architectural target. The ADR exists so that the implementation has a stable governance frame. Both layers are now in place; what remains is engineering.
