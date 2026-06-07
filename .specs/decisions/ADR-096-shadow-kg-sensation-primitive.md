<!-- path: .specs/decisions/ADR-096-shadow-kg-sensation-primitive.md -->

# ADR-096 — Shadow KG sensation primitive; static-vs-runtime engine partition for pre-commit consequence sensing

**Date:** 2026-06-07
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-07 — drafted retroactively after the v1 prototype shipped at commit `6c7d0ea5`. The governor pre-authorized retroactive ADR-as-cooldown at scoping time ("let's make it work then we write an ADR retroactively, more efficient, gist is clear"). The static-vs-runtime engine category distinction in D1 emerged mid-implementation: the smell-test demo surfaced six ghost-resolved findings from `cli_gate`, my initial response was patch-arguing Option A (carve-out) vs Option B (subprocess + sys.path surgery, ~250 LOC), and the governor's "step back and rethink conceptually" pushed me to interrogate whether the framing of *"make every engine shadow-aware"* was even right. The reframe — that pre-commit sensation and post-commit verification are categorically different jobs that happened to share an engine framework — flipped my recommendation from Option B to a principled Option A. That arc shaped this ADR's headline.)
**Grounding papers:**
- `.specs/papers/CORE-The-Octopus-UNIX-Synthesis.md` — V2.3-REBIRTH plan; this ADR ships Phase 1 (Sensation Layer §1).
- `.specs/papers/CORE-V2-Adaptive-Workflow-Pattern.md` — the V2 Component pattern that maps to Octopus "Limb"; this ADR's primitives are inputs to that pattern's pre-commit step.
- `.specs/papers/CORE-Action.md` — Neuron / AtomicAction definition; the Limb's reflex loop will compose Neurons over the substrate this ADR ships.
**Related:** #590 (V2.3-REBIRTH dispatch tracker — adjacent work, this ADR is not a numbered closure but is foundational to the eventual reflex-loop closure). Memory `reference_v2_limbs_workers_relationship` (the V2 Limb / Workers / Neurons distinction grounding D5).

---

## Context

The Octopus paper §3 names **Chemosensory Context** — Limbs taste consequences before commit — as one of three pillars of distributed autonomous Limbs. Without a sensation substrate, an autonomous Limb is blind to its own harm: it can only correct via post-commit failure signals, which arrive slowly, after damage, and through the same Governor-audit pipeline that should have caught the harm preemptively.

The v1 work began as "build the Shadow KG primitive." Recon flipped the framing:

1. **Most of the substrate already existed.** `LimbWorkspace` (read-only overlay with crate-priority reads) at `src/shared/infrastructure/context/limb_workspace.py`. `KnowledgeGraphBuilder` SHADOW mode that accepts a workspace and builds a graph over the merged crate+disk view. `ContextService` SHADOW mode that disables cache and wires the workspace through. `CoderAgent` accepting workspace parameter. `will/test_generation/sandbox.py` materializing crate to a tempdir for pytest. Five of six primitives Octopus Phase 1 named were already realized.

2. **The actual gap was consequence-sensing.** All those consumers could *read* the proposed-change state. None could answer the question that makes Shadow KG load-bearing: *"what will my proposed change break in the rest of the system?"* That's the Chemosensory Context question.

3. **The constitutional audit was the right answer.** The audit is the Governor's standing assessment of constitutional harm. Running it over a shadow projection of the workspace and diffing against the disk audit produces a signal that is, by construction, grounded in the same Law that authorizes work. The signal is not ad-hoc; it is the Limb asking the Governor's own question against a tentative future.

4. **But the audit's engine framework conflated two question-classes the substrate-shadow could not paper over.** Eight engines, two latent categories:

   - **Static engines** — `ast_gate`, `regex_gate`, `glob_gate`, `artifact_gate`. Substrate is source-file text. They answer *"if the code SAYS this, is it constitutional?"* Naturally shadow-friendly: file-content overlays answer the question for the proposed change.
   - **Runtime engines** — `cli_gate`, `knowledge_gate`, `runtime_gate`, `llm_gate`. Substrate is the imported Typer registry, the DB-backed knowledge graph, the live blackboard, or the LLM provider. They answer *"does the running SYSTEM have the right shape?"* These reflect the state of the deployed system, not the file-level proposition the Limb is sensing.

5. **The `cli_gate` ghost made the category leak visible.** The smell-test demo against a hand-broken `src/shared/path_utils.py` reported six "resolved" findings from `cli_gate.standard_verbs` — including one flagging the smell-test command's *own verb*, present on both disk and shadow. Investigation showed `cli_gate` walks the live Typer registry built from real-disk imports (`from cli.admin_cli import app as main_app`), gets back commands carrying absolute paths under `/opt/dev/CORE/src/`, then filters via `relative_to(self._path_resolver.repo_root)` (the #547 mechanism for dropping out-of-repo commands when CORE runtime is pip-installed against a consumer repo). In shadow mode `path_resolver.repo_root` is the shadow tempdir; `relative_to` raises `ValueError` for every command (their file_paths are on real disk, not under shadow_root); every command gets dropped; every `cli_gate` finding disappears. The "resolved" findings were noise from a runtime engine being asked a question it cannot honestly answer in a pre-commit workspace.

6. **First-instinct response (subprocess + sys.path surgery) was the wrong shape.** Initial framing: rescue `cli_gate` by running the shadow audit in a subprocess with PYTHONPATH/sys.path rooted in the shadow's `src/`, so Python imports resolve to crate-overlaid modules and the registry walk returns shadow-rooted file paths. Recon confirmed it was technically viable (CORE's `.pth` files only add to sys.path; they don't pre-import CORE modules; the worker script could surgically rewrite sys.path at its first executable line). Estimated cost: ~250 LOC of worker script + subprocess plumbing + JSON marshalling + error handling.

7. **Step-back reframed the foundation question.** The governor pushed: *"step back and rethink at the conceptual level."* The reframe: forcing runtime engines into the shadow doesn't restore fidelity — it pretends a runtime question is a static one. Even if technically possible, what does *"if we imported the shadow's command tree, what would the registry look like?"* mean? Not what the daemon will see at commit. The daemon will restart, reload from disk, register commands against whatever the committed code is. The shadow registry was a fiction.

   The honest framing was already latent in the engine roster: static engines sense pre-commit; runtime engines verify post-commit. They were always doing different jobs. Shadow audit is the right surface for the first; the regular audit against the live daemon is the right surface for the second.

The cumulative shape: **pre-commit sensation and post-commit verification are different jobs that happened to share an engine framework.** Shadow KG ships the pre-commit job. The runtime-engine partition is not a carve-out (the framing v0.5 work-in-progress used); it is the recognition that the framework was conflating two question-classes. Naming the distinction lets every future engine declare its category and lets the shadow substrate be honest about what it can and cannot sense.

---

## Decisions

### D1 — Static engines and runtime engines are categorically different question-classes

Every audit engine answers one of two questions:

- **Static-class** — *"If the code SAYS this, is it constitutional?"* Substrate is source-file content. Current members: `ast_gate`, `regex_gate`, `glob_gate`, `artifact_gate`. Shadow-friendly by construction; the file is the question.
- **Runtime-class** — *"Does the running SYSTEM have the right shape?"* Substrate is process state (imported Python, DB graph, live blackboard, LLM provider). Current members: `cli_gate`, `knowledge_gate`, `runtime_gate`, `llm_gate`. Not shadow-friendly; the substrate is a property of the deployed system, not of the proposed file-level change.

This is the headline decision. Every subsequent decision in this ADR flows from it. Future engine authors classify their engine into one of these two buckets; the classification determines which audit surfaces the engine participates in.

The two question-classes are **not** a quality ranking. Runtime engines are not "worse." `cli_gate`'s registry checks, `knowledge_gate`'s symbol-coupling rules, and `runtime_gate`'s blackboard telemetry checks remain load-bearing constitutional rules in their natural surface (the disk audit running against the deployed system). They are misplaced when asked to evaluate a pre-commit proposition that has not yet been imported, ingested, or executed.

### D2 — Shadow audits skip the runtime-class engine cohort as a principled partition

`mind/governance/shadow_audit.py` runs the static-class cohort and partitions the runtime-class cohort into `skipped_rules` with per-engine reasons. The skip set lives as a module-level constant:

```python
_SHADOW_INCOMPATIBLE_ENGINES: frozenset[str] = frozenset({
    "cli_gate", "knowledge_gate", "llm_gate", "runtime_gate",
})
```

`run_shadow_audit(intent_repo, repo_path, *, files=None)` is a sibling of `run_stateless_audit`. It builds an `AuditorContext(stateless=True)`, extracts rules, partitions any rule whose engine is in `_STATELESS_SKIP_ENGINES` (knowledge_gate, llm_gate — already partitioned out of stateless paths for DB/LLM reasons) **or** in `_SHADOW_INCOMPATIBLE_ENGINES` (the wider runtime-class set), then dispatches the remainder via `run_filtered_audit`. The return shape mirrors `run_stateless_audit` so existing diff primitives consume the output unchanged.

**Both sides of a shadow-diff comparison MUST use `run_shadow_audit`** — not `run_stateless_audit` on disk and `run_shadow_audit` on shadow. Using different cohorts on the two sides is the bug that produced the original `cli_gate` ghost: disk reported 6 findings, shadow reported 0, the diff inferred "resolved." Using the same partition on both sides makes the diff honest by symmetry.

### D3 — Shadow materialization is per-file-symlinked src/ + directory-symlinked siblings, with a write-through guard

`shared/infrastructure/context/shadow_materializer.py::materialize_workspace_for_audit` builds a tempdir under `var/tmp/core-shadow-<uuid>/` containing:

- **`shadow/src/`** — real directory. For each non-crate file: per-file symlink to the real source file. For each crate file: a real file with the proposed content. Per-file (not directory) symlinks for `src/` are mandatory so individual crate-file overlays cannot bleed through a directory symlink and mutate the real repo.
- **`shadow/.intent/`**, **`shadow/tests/`**, **`shadow/pyproject.toml`**, etc. — directory or file symlinks to the real entries. The audit walker needs them; the Limb doesn't propose changes to them in v1.
- **`shadow/var/`** — real directory; children symlinked individually **except** `var/tmp/`. `var/tmp/` is skipped because the shadow tempdir itself lives there; symlinking `shadow/var/tmp/` would re-enter the shadow when the walker rglobs `var/`, creating a cycle.
- **Structural excludes** (`.git`, `.venv`, `__pycache__`, `node_modules`, `dist`, `build`) — not materialized. Mirrors the auditor's own `_STRUCTURAL_DIR_PARTS` set; the shadow harmlessly omits paths the audit would prune anyway.

A `_guard_no_symlink_ancestor` check refuses to overlay any crate path whose ancestor chain inside `shadow_root` contains a directory symlink. Writing through a directory symlink would mutate the real repo (data loss). The guard makes the failure loud and named.

The materializer is a context manager. Tempdir + symlinks die on context exit; no cleanup discipline at call sites.

### D4 — v1 supports crate paths under `src/` only; other prefixes raise

A crate path under `src/foo.py` is safe because `_materialize_src_tree` per-file symlinks `src/`. A crate path under `.intent/foo.yaml` or `tests/foo.py` would write through the directory symlinks D3 places at those prefixes, mutating the real repo. The guard catches this and raises `ValueError` with a clear remediation hint pointing at `_materialize_src_tree` as the extension point.

This is a hard v1 boundary, not a future-promise: extending to `tests/` requires explicit per-file materialization of `tests/`; extending to `.intent/` requires the same for `.intent/`; in either case the corresponding governance argument (e.g., "does it make sense for a Limb to propose `.intent/` changes?") needs to be made before the materializer changes.

### D5 — Sensation is calibrated before autonomy; reflex loop deferred to v2

v1 ships the smell-test CLI as a one-shot demonstration — *no* reflex loop, *no* autonomy, *no* commit. The split exists because a reflex loop reading `resolved_findings ≥ 1 ⇒ success` against an uncalibrated signal would terminate falsely. The `cli_gate` ghost demonstrated this concretely: before D2 landed, the smell-test reported 6 phantom "resolved" findings; a reflex loop reading that signal would have declared victory on a destructive change.

v2 (the reflex loop) consumes the calibrated v1 signal. Calibration is a v1 deliverable, not a v2 prerequisite the loop builds against fresh.

The v2 scope (proposal → shadow audit → diff → re-propose iteration) is a sibling ADR, not part of this one.

### D6 — In-process sensation is the v1 substrate; Limb-as-process is a future architectural question

v1 sensation runs in-process. `run_shadow_audit` is a normal Python function called from the same interpreter that owns the smell-test CLI, the IntentRepository singleton, and the audit machinery. No subprocess, no PYTHONPATH manipulation, no per-engine Python-import-rerouting.

The Octopus paper's bigger architectural picture suggests Limbs may eventually want their own process — sys.path rooted in shadow, working directory shadow-rooted, substrate adapters all shadow-aware — so the entire Limb lifecycle runs in an envelope where the shadow is the ambient truth. That posture would dissolve the static-vs-runtime distinction at the Limb level: every engine the Limb runs would see shadow content because every Python import would resolve from shadow first.

v1 does not ship that posture. The reasons:

- **Calibration first.** The static-engine cohort already produces a load-bearing signal (the smell-test demo proved it). Wrapping that in process isolation before knowing what the reflex loop wants would be premature shape-locking — the Phase-Goal-Absorbs-Design trap.
- **Cost vs. marginal benefit.** Process isolation adds JSON IPC, ~3–5s subprocess startup, error surface for crashes/timeouts. The marginal benefit (one engine — `cli_gate` — works in shadow) is small for v1's smell-test demo.
- **v1's primitives are envelope-agnostic.** `ShadowDiff`, `ShadowAuditDiff`, `materialize_workspace_for_audit` are all pure or near-pure functions. They work in-process today; they would work inside a Limb-process tomorrow. The decision is deferred, not foreclosed.

When v2 (or v3) needs Limb-as-process, a sibling ADR scopes it. This ADR commits v1 to the in-process substrate and explicitly opens the door to the bigger move.

---

## Phasing

This ADR is retroactive. The v1 implementation shipped at commit **`6c7d0ea5`** on 2026-06-07. The phasing below describes the v1 ship as it landed, not a forward plan.

1. **New file `src/shared/infrastructure/context/shadow_diff.py`** — `ShadowDiff` pure function over two KG dicts; surfaces `added_symbols`, `removed_symbols`, `changed_signatures`, `orphaned_callers`.
2. **New file `src/shared/infrastructure/context/shadow_audit_diff.py`** — `ShadowAuditDiff` pure function over two audit-result dicts; surfaces `new_findings`, `resolved_findings`, `unchanged_findings`.
3. **New file `src/shared/infrastructure/context/shadow_materializer.py`** — `materialize_workspace_for_audit` context manager; per-file-symlink src/ + directory-symlink siblings + write-through guard.
4. **New file `src/mind/governance/shadow_audit.py`** — `run_shadow_audit` static-cohort runner; `_SHADOW_INCOMPATIBLE_ENGINES` constant and per-engine reasons; mirrors `run_stateless_audit`'s shape.
5. **New file `src/cli/resources/dev/smell_test.py`** — `core-admin dev smell-test` CLI; runs disk + shadow audits and KG builds; prints engine partition, audit diff, structural diff, verdict.
6. **Modified `src/cli/resources/dev/__init__.py`** — added `smell_test` to the dev sub-app's import list so `@app.command("smell-test")` decoration runs.
7. **New tests** — 22 unit tests across `tests/shared/infrastructure/context/test_shadow_diff.py` and `tests/shared/infrastructure/context/test_shadow_audit_diff.py`. All passing under pytest.

Zero modifications to: `AuditorContext`, any engine, any `.intent/` artifact, `stateless_audit.py`, the existing audit driver pipeline.

---

## Consequences

### Pre-commit sensation has a substrate

A Limb (or any consumer — IDE plugin, autonomous remediator, governor smoke test) can now ask "what does my proposed change break?" and get a constitutional answer grounded in the same Law the Governor uses to authorize work. The substrate is the Shadow KG (structural) + Shadow Audit (constitutional) + their diffs.

### The static-vs-runtime engine partition is a first-class constitutional argument

Before this ADR, the partition lived as a docstring on `shadow_audit.py` and an implicit set in `_SHADOW_INCOMPATIBLE_ENGINES`. After this ADR, D1 commits the partition as a category distinction in the audit framework's design. New engine authors will be asked which category their engine belongs to; the answer determines which audit surfaces the engine participates in.

### Runtime engines retain their natural surface

`cli_gate`, `knowledge_gate`, `runtime_gate`, `llm_gate` are unchanged. They still run in disk audit, CI audit, the daemon's audit cycle. They are only partitioned out of *shadow* audits, where their substrate question doesn't apply. No regressions in existing audit fidelity.

### The 250 LOC subprocess-and-sys.path-surgery proposal is rejected

Option B (rescue `cli_gate` via subprocess with PYTHONPATH/sys.path manipulation) was the natural next implementation move when the `cli_gate` ghost surfaced. D1 + D6 explicitly reject it: forcing a runtime engine into a static surface answers a fictional question. The recon work behind Option B is preserved in this ADR's Context section so future readers don't redo it; the implementation itself is not shipped.

### The smell-test CLI is the v1 demonstration surface

`core-admin dev smell-test --file <src-path> --content-from <local-file>` is the canonical way to exercise v1. It is not a production sensor (no autonomous loop, no triggering, no scheduled execution). It is a demonstration that the substrate produces honest signal. The autonomous loop is v2 territory.

### v2 (reflex loop) has calibrated signal as its starting point, not a calibration prerequisite

The cli_gate-ghost calibration is finished. v2 scoping begins with: "what shape does the reflex loop take on top of (new_findings, resolved_findings, structural diff) we now trust?" The architectural question for v2 is the in-process-vs-Limb-as-process decision per D6, not "is the signal honest?"

### The autonomous test-generation loop and existing workers are unaffected

This ADR does not touch the autonomous test-generation loop, the worker substrate, the blackboard, or any production sensor. The Shadow KG primitive is additive infrastructure for a future Limb consumer; existing autonomous remediation paths continue unchanged.

### Future engines inherit the category decision

When a new engine joins the audit framework, the author declares its category (static or runtime) per D1. Static engines are admitted to shadow audits automatically; runtime engines are added to `_SHADOW_INCOMPATIBLE_ENGINES`. The decision-point is named; the engine cannot accidentally be silently broken in shadow audits.

### Limb-as-process remains an open architectural question

D6's deferral is explicit, not silent. When v2's reflex loop or v3's full autonomous Limb pushes the in-process substrate to its limits, a sibling ADR re-opens the architectural envelope question. This ADR documents the reasons v1 ships in-process so the eventual sibling has the rejected alternative in writing.

---

## Verification

- This ADR exists at `.specs/decisions/ADR-096-shadow-kg-sensation-primitive.md`.
- Files exist at the paths listed in Phasing items 1–5. Each carries the canonical `# src/...` path comment at line 1 (CLAUDE.md §source-layout).
- `src/mind/governance/shadow_audit.py::_SHADOW_INCOMPATIBLE_ENGINES` equals `frozenset({"cli_gate", "knowledge_gate", "llm_gate", "runtime_gate"})`.
- `src/mind/governance/shadow_audit.py::_SHADOW_SKIP_REASONS` has one reason per engine in `_SHADOW_INCOMPATIBLE_ENGINES`; the two sets agree (asserted by import-smoke verification at v1 ship time).
- `run_shadow_audit` accepts the same `(intent_repo, repo_path, *, files=None)` signature as `run_stateless_audit` and returns a dict carrying `mode="shadow"`, `findings`, `skipped_rules`, `executed_rule_ids`, `verdict`, `passed`, `duration_sec`.
- `materialize_workspace_for_audit` is a context manager yielding a `Path` under `var/tmp/core-shadow-<uuid>/`. The tempdir cleans up on context exit (verified end-to-end at v1 ship time).
- `core-admin dev smell-test --file <src-path> --content-from <local-file>` runs end-to-end against the real repo. The end-to-end demo against `src/shared/path_utils.py` with `var/tmp/broken_path_utils.py` produces: 3 new findings (deliberate `print()` violation + downstream pytest failure), 0 resolved findings (the cli_gate ghost is gone), 1 removed symbol (`get_repo_root`), 6 orphaned callers across `body/`, `cli/`. Verdict exit code 1 (new constitutional findings).
- 22 unit tests across `tests/shared/infrastructure/context/test_shadow_diff.py` and `tests/shared/infrastructure/context/test_shadow_audit_diff.py` pass under pytest.
- `src/mind/governance/audit_context.py` is unchanged by the v1 ship. `git log src/mind/governance/audit_context.py` does not show commit `6c7d0ea5`.
- `src/mind/governance/stateless_audit.py` is unchanged by the v1 ship. `git log src/mind/governance/stateless_audit.py` does not show commit `6c7d0ea5`.
- No engine source file under `src/mind/logic/engines/` was modified by the v1 ship.
- A crate path attempt outside `src/` (e.g. `{".intent/foo.yaml": "..."}`) raises `ValueError` from `_guard_no_symlink_ancestor` with the message naming the ancestor directory symlink. Verified at v1 ship time via smoke.

---

## References

- `.specs/papers/CORE-The-Octopus-UNIX-Synthesis.md` §3 (Pillar I: Octopus, Distributed Autonomy), §6 (Limb Operational Model V2.3+) — this ADR ships Phase 1 of the V2.3-REBIRTH plan.
- `.specs/papers/CORE-V2-Adaptive-Workflow-Pattern.md` — the V2 Component pattern that maps to Octopus "Limb"; Shadow KG primitives are inputs to that pattern's pre-commit sensation step.
- `.specs/papers/CORE-Action.md` — Neuron / AtomicAction definition; the Limb's eventual reflex loop composes Neurons over this ADR's substrate.
- ADR-085 (open operational completeness) — the stateless audit infrastructure `run_shadow_audit` inherits from.
- #547 — `cli_gate`'s `relative_to(repo_root)` mechanism for dropping out-of-repo commands; this ADR's Context point 5 traces the `cli_gate` ghost back to #547's interaction with the shadow tempdir.
- #590 — V2.3-REBIRTH dispatch tracker; this ADR is foundational to the eventual reflex-loop closure on #590.
- Commit `6c7d0ea5` — v1 implementation (8 files, 1341 insertions).
- Memory `feedback_phase_goal_absorbs_design` — informed the step-back when the `cli_gate` ghost surfaced and Option B was the first instinct.
- Memory `feedback_coder_architect_interleaving` — saved mid-session (2026-06-07) as the lesson from this ADR's scoping arc; the governor's interrogation was the engineering work that produced D1.
- Memory `feedback_grep_before_declaring_design_needed` — informed the recon-first posture that revealed 5 of 6 Shadow KG primitives already existed.
- Memory `feedback_universal_sink_beats_per_site` — informed materializer's single-guard approach (one `_guard_no_symlink_ancestor` at the overlay site instead of per-engine workarounds).
- Memory `reference_v2_limbs_workers_relationship` — V2 Limb / Workers / Neurons distinction grounding D5's reflex-loop-deferred posture and D6's Limb-as-process open question.
