<!-- path: .specs/requirements/URS-requirement-fulfillment-verification.md -->

# URS — Requirement Fulfillment Verification

**Status:** Draft (initial conceptualization 2026-06-06 — awaiting governor review)
**Authority:** Requirements
**Scope:** A sensor that reads URS documents under `.specs/requirements/` and emits findings when their declared acceptance criteria are not satisfied by CORE's current runtime state. This URS does **not** govern decomposition, ADR drafting, work-item dispatch, conversation primitives, or any other intake-pipeline stage downstream of verification.
**Audience:** Governor (architect, intent author, non-programmer); future implementer of the URSSatisfactionSensor.
**Version:** 0.1
**Relates:** `.specs/concepts/CORE-URS-Intake-Concept.md` (the frozen pre-URS thinking that surfaced the intake gap); URS-mechanism-coherence (sibling instrument — the rule-vs-mechanism layer; this URS is the URS-vs-runtime layer); ADR-068 (Principal Role Taxonomy — the `resolution_authority` anchor); Issue #428 (in-flight resolution_authority taxonomy work on blackboard findings); ADR-091 D2 (canonical subject format `<artifact_type>::<sub_namespace>::<identity_key_value>`); CCC paper (the pattern this URS borrows for coverage manifest discipline).

---

## 1. Purpose

CORE audits `src/` against `.intent/` (standard audit). CORE audits the constitution against itself at the document layer (CCC). CORE audits the autonomous remediation loop for fix-effectiveness (Coherence Sensor). The mechanism layer between rule declaration and rule enforcement is in flight (URS-mechanism-coherence).

**Nothing yet asks whether CORE's runtime honors the claims its own URSs make.** A URS declares what CORE should do — and once a URS is accepted, the question of whether that claim is fulfilled by current implementation has historically been answered by the governor reading documents, reading code, and reasoning. The system itself has no surface that consumes URSs as input and reports satisfaction status as output.

This gap is the intake gap framed by `.specs/concepts/CORE-URS-Intake-Concept.md` and verified there by grep: zero workers, sensors, services, or APIs read `.specs/requirements/` to evaluate satisfaction. The CONCEPT named the full pipeline (URS → Verifier → Decomposer → ADR Proposer → Approval → Administrator → Execution); four external reviews converged on the same first move — **build only the Verifier**.

This URS scopes only the Verifier. The Verifier is a sensor. Decomposer, ADR Proposer, and downstream pipeline stages are deferred to subsequent URSs after the Verifier's evidence shape is stable.

## 2. Grounding

This URS operationalizes **UR-07 (Defensibility is Non-Negotiable)** at the intent-runtime layer, in the same way URS-mechanism-coherence operationalizes UR-07 at the rule-mechanism layer. Defensibility breaks just as completely when an accepted URS's claim is silently unfulfilled as when a declared rule's mechanism is silently inert. Both are failures of the constitution to actually constitute.

Secondary grounding is **UR-06 (Continuous Constitutional Governance)** — governance applies to the intent layer as completely as to the rule layer. There is no exempt class of URS where the relationship between claim and implementation may drift unverified.

## 3. Prior Work and Scope of the Gap

The coherence family currently has three layers (verified instrument or URS), with this URS opening the fourth:

| Instrument | Layer | Trust posture |
|---|---|---|
| Standard audit (`core-admin code audit`) | `src/` vs declared rules | Deterministic; fail-closed |
| Constitutional Coherence Checker (CCC, ADR-067) | document vs document (ADR/rule/northstar) | LLM as candidate-finder; governor triage |
| URS-mechanism-coherence (URS v0.1) | rule declaration vs rule mechanism | Deterministic; fail-closed (URS-only) |
| **Requirement Fulfillment Verification (this URS)** | **URS claim vs CORE runtime state** | **Deterministic; declared-classification; URS-author authority** |

The CONCEPT (§2) frames this as the fourth coherence layer. The reviewer who anchored the strongest correction (recorded in `.specs/concepts/CORE-URS-Intake-Concept.md` §11) identified that this layer's instrument is architecturally continuous with TestCoverageSensor and AuditViolationSensor — it walks a constitutional surface, derives expected state, compares against observed state, emits findings. The instrument is therefore a *sensor*, not a new pipeline class.

## 4. User Role

**Primary user:** the governor (architect, intent author, non-programmer). The governor authors URSs and accepts them as governance. The governor requires the system itself to report whether accepted URSs are fulfilled by current runtime state, with verdicts produced on the governor's behalf and surfaced on the existing dashboard alongside other audit findings.

**Secondary user:** the autonomous remediation loop. URS-satisfaction findings flow through the same blackboard surface as other findings, so existing pipelines (sensor → finding → remediator) can route them where remediation paths exist. Today no `fix.*` action exists for URS-class findings; the loop's role here is *surfacing*, not *fixing*, until decomposer + ADR proposer ship.

## 5. Functional Requirements

### R-001. URS authors declare acceptance criteria with classification

Every URS under `.specs/requirements/` shall present its acceptance criteria as a structured list. Each criterion shall declare at minimum:

- `id` — stable identifier (e.g., `AC-001`), unique within the URS
- `claim` — natural-language statement of what shall be true
- `verification_class` — one of `mechanical` | `behavioral` | `judgmental` (closed vocabulary)
- `verifier_hint` — best-effort guidance for the Verifier (grep predicate, fixture reference, "human evidence required")

The exact storage format (embedded YAML block, criterion table, separate manifest file) is paper-scope per §7. The requirement is that the metadata be declared by the author, not inferred by the Verifier.

### R-002. The Verifier is a sensor

The instrument shall be implemented as a worker of `class: sensing` declared under `.intent/workers/`, mirroring `audit_violation_sensor.yaml` and `test_coverage_sensor.yaml`. The sensor declaration carries `mandate.scope.artifact_type` referencing a registered artifact_type covering `.specs/requirements/` (F-41 registry). The sensor runs on the existing daemon cycle; no new schedule, no separate instrument lifecycle.

This requirement absorbs Reviewer 1's strongest correction recorded in the CONCEPT §11 Reception: Stages 1–2 of the CONCEPT pipeline collapse into the existing sensor/finding machinery.

### R-003. Verdicts are deterministic, per criterion, drawn from a closed vocabulary

For each acceptance criterion in a URS, the Verifier shall produce exactly one verdict from the closed set:

- `satisfied` — evidence path resolves and confirms the claim
- `unsatisfied` — evidence path resolves and falsifies the claim
- `unverifiable_no_evidence_path` — mechanical or behavioral criterion declared but no evidence path can be constructed (declared but unprovable)
- `requires_human_evidence` — judgmental criterion (the Verifier does not attempt LLM judgment)
- `misclassified` — criterion declared in one verification_class but evidence path only resolves in another (handled per R-004)

No LLM judgment enters the verdict path for mechanical or behavioral classes. The `requires_human_evidence` verdict is the deterministic verdict for judgmental criteria — the verdict is "human evidence required," not "satisfied / unsatisfied."

### R-004. Authority over verification strategy stays with the URS author

When a criterion declares `verification_class: mechanical` but no mechanical evidence path resolves, the Verifier shall emit a `misclassified` finding identifying the criterion and the apparent mismatch. The Verifier shall **not** silently reclassify and proceed under a different class. The URS author is the authority on what verification strategy applies; the Verifier reports when the declared strategy cannot be enacted.

This also resolves Reviewer 3's "Stage 2 double-duty" observation (recorded in the CONCEPT §11 Reception): a criterion's verification *strategy* and criterion *kind* can diverge. Whether that divergence is admitted as a separate axis or as misclassification is paper-scope; the URS requires only that the author retain authority.

### R-005. Findings follow the canonical subject format

Findings emitted by the Verifier shall use the subject namespace pattern `urs::<urs_id>::<criterion_id>` per ADR-091 D2's canonical `<artifact_type>::<sub_namespace>::<identity_key_value>` shape. The subject prefix `urs` is allocated to this instrument; the per-finding subject identifies the URS and the criterion uniquely.

Satisfied criteria emit no findings per cycle (silence-as-success, mirroring AuditViolationSensor). `unsatisfied`, `unverifiable_no_evidence_path`, `requires_human_evidence`, and `misclassified` verdicts emit one finding per criterion-cycle.

### R-006. Behavioral criteria require fixtures, governed as constitutional surface

For every criterion declared `verification_class: behavioral`, the URS author shall provide at least one fixture exercising the claim. Fixtures shall live under `.intent/` or `.specs/`, governed by the same discipline as the URSs they verify, not under `tests/` where they would be test-suite cruft. This requirement mirrors URS-mechanism-coherence R-005 — the discipline is consistent across coherence-family instruments.

### R-007. Verifier shall declare its trusted kernel

The Verifier shall declare its **trusted kernel** — the small body of code whose correctness is established by inspection rather than by verification through itself. The kernel boundary shall be explicit, sized for inspection in one sitting, and reviewable as a list. This requirement mirrors URS-mechanism-coherence R-006 and absorbs Reviewer 1's "Verifier self-qualification" critique (recorded in CONCEPT §11 Reception). The kernel exists to prevent the instrument from degenerating into unaccountable meta-recursion.

### R-008. Coverage manifest

Every Verifier run shall produce a coverage manifest enumerating every URS evaluated and, within each URS, every criterion evaluated, with a status of `checked` or `skipped`. A `skipped` URS or criterion requires explicit rationale. Items skipped without rationale constitute a coverage gap and shall be surfaced as findings. Pattern adopted unchanged from CCC paper §5 and URS-mechanism-coherence R-007.

### R-009. Independence from other audit verdicts

The Verifier's verdict and the standard audit verdict are independent. A system may hold a clean standard audit while carrying unsatisfied-URS findings (the rules are obeyed but the URSs are not fulfilled), or vice versa. The two surfaces shall be reported separately and shall not be collapsed into a single overall verdict. Pattern from URS-mechanism-coherence R-008.

### R-010. Normal audit surface

The Verifier shall be invokable as a normal CORE operation — not a development-only tool. Findings shall flow through the standard blackboard subjects (per R-005's namespace) and shall appear on the governor dashboard alongside other findings. Pattern from URS-mechanism-coherence R-009. The CLI surface (e.g., `core-admin specs verify <urs>`) is paper-scope.

### R-011. Authoring obligation: no new URS without criterion manifest

Adding or substantively amending a URS shall require, by constitutional discipline, the simultaneous authoring of its criterion manifest per R-001. A URS landed without a manifest is, by R-001's requirement, malformed by construction and shall fail the Verifier's first invocation. The authoring gate is upstream — no URS reaches `.specs/requirements/` without declared criteria. Pattern from URS-mechanism-coherence R-010.

### R-012. Misclassification feedback is non-blocking

A `misclassified` verdict (R-003) emits a finding but shall not halt evaluation of other criteria in the same URS or other URSs. The Verifier completes its full pass; misclassified criteria appear in the coverage manifest as `checked` with `verdict: misclassified` (distinct from `skipped` per R-008). This requirement exists to prevent one malformed criterion from masking unrelated findings.

## 6. Non-Requirements

This URS deliberately does **not** specify, and explicitly defers:

- **The decomposer** (CONCEPT Stage 3). The recursion dragon (CONCEPT §4 Stage 3) is unsolved at architectural level per the §11 Reception convergence. The decomposer ships in a subsequent URS once the Verifier's evidence shape is stable.
- **The ADR proposer** (CONCEPT Stage 4). Same deferral logic.
- **GitHub or other external work-item dispatch** (CONCEPT Stage 6 outbound). Zero outbound integration today; remains out of scope until the Decomposer surfaces a proposal grain that warrants external dispatch.
- **Conversation primitives or DecisionRequest object** (CONCEPT Stage 6 intervention-as-data). Per the §11 Reception governor decision adopting Reviewer 1's path, intervention is modeled as a finding with `resolution_authority: principal.governor` plus a subsequent URS edit, reusing #428's in-flight work — not as a new structured object.
- **Retrofit of the 5 existing URSs** (`CORE-Ask-URS.md`, `CORE-Governor-Ask-URS.md`, `CORE-Governor-Dashboard-URS.md`, `URS-consequence-chain.md`, `URS-mechanism-coherence.md`) to carry declared criterion manifests per R-001. The retrofit cost is non-trivial and shall be sequenced as a follow-on; v0 of the Verifier may operate on synthetic test URSs to prove the mechanism before the canonical URSs are retrofitted.
- **`.specs/` artifact-class governance.** The CONCEPT artifact class was introduced by fiat in `.specs/concepts/CORE-URS-Intake-Concept.md` §10. Codifying CONCEPT's lifecycle states and bounds is a separate META decision per the §11 Reception convergence, not this URS's scope.
- **The autonomous remediation pathway for URS-class findings.** By default, URS findings route to the governor for resolution, not to an autonomous fixer. Any future autonomous remediation of URS findings requires a separate ADR — same posture as URS-mechanism-coherence §6.
- **The verifier_hint vocabulary.** The hint is best-effort guidance; this URS does not constrain its shape (grep predicate, fixture file reference, free-text). Paper-scope.

## 7. Acceptance Criteria for Downstream Artifacts

A **paper** operationalizing this URS (analogous to `CORE-ConstitutionalCoherenceChecker.md` for ADR-067) shall:

- define the criterion manifest's exact storage format (embedded YAML block? criterion table? separate `.urs.manifest.yaml` file?),
- define the verifier_hint vocabulary or document why it remains free-form,
- specify the trusted-kernel boundary in concrete terms (list of modules),
- specify the fixture file format and location under `.intent/` or `.specs/`,
- specify the finding payload structure (what fields beyond subject, status, claim, verdict, evidence_path),
- specify the misclassification structural form — whether divergence between verification strategy and criterion kind is modeled as a separate axis or as the misclassified verdict alone (Reviewer 3's Stage 2 double-duty),
- specify the URS-shape validation as a precondition to verification (R-011 enforcement),
- amend the CCC paper §8 and the URS-mechanism-coherence URS §3 to register this instrument as a sibling and acknowledge inter-instrument boundary.

An **ADR** operationalizing the paper shall, in turn, specify storage schema, CLI surface (`core-admin specs verify`?), worker declaration (`.intent/workers/urs_satisfaction_sensor.yaml`?), scheduling, dashboard integration, and `artifact_type` declaration covering `.specs/requirements/` (F-41 registry coupling per ADR-091 D6 item 3).

## 8. Closing Note

CORE's working hypothesis is that the constitution shall be verified, not assumed (CCC paper §13). That hypothesis has been operationalized at the document layer (CCC), is in flight at the mechanism layer (URS-mechanism-coherence v0.1), and is shipped at the remediation layer (Coherence Sensor, ADR-027). The intent layer — between accepted URS claims and CORE's runtime state — has been operating on assumption since CORE's inception. The governor's intent surface has been Claude Code CLI sessions, ADR authorship, and planning documents that CORE itself does not consume.

This URS records the governor's requirement that CORE begin consuming its own URSs. The first instrument is a Verifier — a sensor. The first verdict shape is per-criterion, deterministic, declared-classification-driven, with author authority preserved over verification strategy. Decomposer, ADR proposer, and the full intake pipeline framed in the CONCEPT remain ahead; this URS is the foundation under them.

The CONCEPT §11 Reception records the four external reviews that shaped this URS's scope. The convergence — MVP-narrow, sensor reframe, declared classification, author authority, decomposer deferred — is baked into the requirements above. The divergences that survived are recorded as paper-scope decisions (criterion manifest storage form, double-duty resolution) so the downstream paper author can adjudicate with full context.
