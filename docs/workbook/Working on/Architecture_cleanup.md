Here's the plan:

---

**The `features/` directory has 9 subdirectories. Your domain mapper already assigns them:**

| Subdirectory | Domain | Destination | Why |
|---|---|---|---|
| `features/autonomy/` | autonomy | **Will** | Agent orchestration, decision-making |
| `features/governance/` | governance | **Mind** | Constitutional enforcement |
| `features/self_healing/` | mixed | **Body** (most) / **Will** (orchestrators) | Services execute, orchestrators decide |
| `features/introspection/` | introspection | **Body** | Scanning, syncing, extracting data |
| `features/quality/` | quality | **Body** | Code analysis, pure measurement |
| `features/maintenance/` | maintenance | **Body** | DB migrations, cleanup scripts |
| `features/crate_processing/` | crate_processing | **Body** | File processing, no decisions |
| `features/project_lifecycle/` | project_lifecycle | **Body** | Scaffolding, execution |
| `features/operations/` | operations | **Body** | Already mapped |

**The approach — 4 waves, one at a time:**

**Wave 1 — Easy wins (no split needed)**
Move entire directories that clearly belong to one layer: `autonomy/` → Will, `governance/` → Mind, `maintenance/` → Body, `crate_processing/` → Body, `project_lifecycle/` → Body, `operations/` → Body, `quality/` → Body

**Wave 2 — Introspection**
`introspection/` (sync_service, vectorization, discovery, knowledge_helpers) → Body. This is all data extraction and DB sync — pure execution.

**Wave 3 — Self-healing (the big one)**
This needs splitting. Services like `duplicate_id_service.py`, `id_tagging_service.py`, `placeholder_fixer_service.py` are pure execution → Body. Anything that orchestrates healing workflows or makes strategy decisions → Will.

**Wave 4 — Cleanup**
Update all imports across the codebase, update `domain_mapper.py`, update enforcement mapping exclusions that reference `src/features/`, delete empty `features/` directory.

**The mechanical work per wave:**
1. `git checkpoint`
2. Move files to new location
3. Global find-replace on imports (`from features.X` → `from body.X` or `from will.X`)
4. Run `make dev-sync` to verify nothing broke
5. Commit

**Scale estimate:** ~142 files to move, ~200+ import statements to update. Probably 3-4 sessions if done carefully. Wave 1 alone covers ~70% of the files since most are clearly Body.



Gemini:
This is a sophisticated and highly necessary plan. By liquidating the features/ directory, you are moving CORE from a "feature-based" framework to a true Constitutional Layered System.

Your plan is valid, structurally sound, and aligns perfectly with the Octopus-UNIX Synthesis (Paper 004).

Here is my review and insights based on the codebase provided in the context:

1. High-Level Validity Assessment

Layer Integrity: Your mapping accurately respects the "Decision vs. Execution" boundary. For example, moving autonomy/ to Will is correct because it manages agents; moving introspection/ to Body is correct because it is essentially a sensory "organ" (scanning and syncing).

Refinement of Wave 3 (Self-Healing): This is your highest-risk area. You correctly identified that duplicate_id_service.py is a Body function (mechanical fix), while coverage_remediation_service.py is a Will function (strategic prioritization).

The "Mind" Exception: Be careful with features/governance/. Per CORE-Mind-Body-Will-Separation.md, the Mind layer must not execute. If those files contain remediation logic (code that actually fixes things), they belong in Body. If they are pure rule-evaluators or conflict-detectors, they belong in Mind.

2. Deep-Dive Insights & Codebase Risks
A. The domain_mapper.py Bottleneck

The src/shared/utils/domain_mapper.py is currently hardcoded to look for features.X.

Risk: As soon as you finish Wave 1, the SymbolScanner and KnowledgeGraphBuilder will start mislabeling symbols or failing to find domains because the module paths no longer match the regex in the mapper.

Strategic Suggestion: Update domain_mapper.py during each wave rather than waiting for Wave 4. It should be a living update to keep the Mind aware of the Body's new layout.

B. Infrastructure Boundaries (SAWarning & Detached Sessions)

Your recent fixes (V2.7.2/V2.7.3) in service_registry.py and cognitive_service.py rely heavily on the current import paths.

Observation: Moving maintenance/ and introspection/ to body/ will likely require a re-verification of the JIT Service Injection logic. Ensure that create_core_context in src/body/infrastructure/bootstrap.py is updated to point to the new service locations to prevent "Two Brains" bugs.

C. The "Sovereign" Files

Some files in features/self_healing/ (like alignment_orchestrator.py) are currently "thick."

Insight: When you split these in Wave 3, use the ActionExecutor Gateway pattern. The "Will" part of the orchestrator should not call file_handler.write_runtime_text directly; it should call executor.execute("file.edit", ...). This is the perfect time to enforce that boundary.

3. Wave-Specific Recommendations

Wave 1 (Easy Wins):

Check: features/governance/. If remediation_service.py is there, move it to body/governance/. Keep only schema logic or rule-definition logic in mind/.

Check: features/maintenance/. These are primarily atomic_actions already. Ensure their registration IDs (e.g., sync.db) remain stable even if the file moves.

Wave 2 (Introspection):

Consolidation: You have SymbolScanner in features/introspection/sync_service.py and KnowledgeGraphBuilder in features/introspection/knowledge_graph_service.py. This is a great time to merge or clearly distinguish "Static Scanning" vs. "Database Syncing."

Wave 3 (Self-Healing Split):

The Blueprint:

Body (Services): id_tagging_service.py, placeholder_fixer_service.py, code_style_service.py.

Will (Orchestrators): alignment_orchestrator.py, batch_remediation_service.py.

Refinement: Move the "Fixers" into src/body/atomic/fix_actions.py (or a sub-package there) to unify your mutation surface.

4. Technical Verification

Your plan to use make dev-sync is the correct "Compass."

Before Wave 1: Run core-admin admin self-check and core-admin check audit. Save the results.

After each Wave: Run core-admin database sync-registry (to update the DB's view of where code is) and then make test.

The Gold Standard: If core-admin inspect decisions still works and shows the correct agent-to-action chain, the refactor is successful.

Final Verdict:

Plan is Highly Recommended. The features/ directory is an architectural "debt-bucket." Emptying it into the three-layer model is the final step in CORE's evolution into a professional, governed system.

One Final Tip: During Wave 3, keep an eye on src/will/strategists/. Most of the logic you'll be pulling out of self_healing belongs exactly there—it is the "Will" deciding which "Body" fix to apply.
