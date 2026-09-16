---
kind: adr
id: ADR-161
title: 'ADR-161 — The repository tree is declared law: one register, one blocking check, a legacy ratchet'
status: proposed
---

<!-- path: .specs/decisions/ADR-161-repository-layout.md -->

# ADR-161 — The repository tree is declared law: one register, one blocking check, a legacy ratchet

**Date:** 2026-09-16
**Status:** Proposed — not binding until the Governor accepts it.
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-09-16 — first draft from read-only reconnaissance at `3750aaa2`; this revision re-verified every claim at `a14e5822`; records: `var/reports/2026-09-16_adr161_draft_review.md`, `…_structure_deep_dive.md`, `…_resources_kind_draft.md`)
**Grounds:** ADR-130 D1 (CORE never writes `.intent/`) together with the `governance.constitution.read_only` rule and the CLAUDE.md confirmation gate (only the Governor edits `.intent/`); ADR-031/032 (runtime paths resolve through PathResolver); ADR-075 D7 (completeness-by-set-difference precedent); ADR-076 D3 (`artifact_gate` is mixed-mode; context-level dispatch); ADR-023 §"The CI gate is upstream prevention" and Alternative E (CI is the authority; pre-commit hooks can be skipped and cannot bear constitutional weight)
**Relates:** `.intent/META/intent_tree.yaml` (the same pattern, one level down); ADR-115 (corrigendum, D6); ADR-123 and ADR-147 / #772 (`work/`); ADR-086 / #521 (`schema.sql` at root); ADR-116 D2/D8/D9 and ADR-149 (catalog roots — consolidated under `resources/catalogs/` by D1a/D5); ADR-108 D3 / ADR-112 (the shipped machinery floor mirrors the starter law — the precedent for D3a property 3 and for D2b's verified-mirror choice); `.specs/papers/CORE-Repo-Split-Plan.md` Phase 0 (protected-path gate — D2/D3 give it a tripwire, see D2); #908 (`FileHandler.ensure_dir` re-roots absolute paths — the `opt/dev/` cause)

---

## Context

New top-level entries keep appearing, and nothing stops them. Every placement was reasonable on its day. Together they no longer tell a newcomer — human or agent — where a file goes.

Recon at `a14e5822` (2026-09-16; counts are `git ls-files`, and are re-derived, not carried, at the implementing commit) shows:

- **39 tracked top-level entries, no declared set.** Nothing in `.intent/` states which entries may exist. Inside `.intent/`, by contrast, `META/intent_tree.yaml` already declares required and optional directories. The repository root has no equivalent.
- **The same kind of thing in several places.**
  - Scripts live in `scripts/` (7), `infra/scripts/` (55), `infra/tools/` (4) and `hooks/` (1).
  - Docker files live at root (`Dockerfile`, both compose files), in `.docker/core-engine/` and in `infra/demo/`.
  - SQL is split between `schema.sql`, `infra/sql/` (3), and 39 SQL migrations (42 tracked files) in `infra/scripts/migrations/` whose ledger is `infra/migrations/manifest.yaml`.
- **`var/` is not purely runtime.** It holds 168 tracked files:
  - 153 are `var/prompts/`, tracked deliberately through `.gitignore` lines 81–82 (#296).
  - 15 (`var/core/` 8, `var/knowledge/` 1, `var/mind/` 6) are tracked despite the `var/*` ignore rule.
- **Inputs the system loads sit in five places.** `var/prompts/` (153 files, inside the runtime-state directory), `examples/starter-intent/` (read at runtime by `onboard_routes.py` and `scout.py`; the shipped floor's `intent_tree.yaml` names it "source of truth" — it is not an example), `packs/` (ADR-149), `grc-catalogs/` (ADR-116), and `var/knowledge/` + `var/mind/knowledge/` (PathResolver `knowledge_dir`). The wheel `core_runtime-2.9.1` (built and inspected 2026-09-16) ships **no prompt files**; its only non-Python data is `shared/_machinery_floor/`. A pip-installed CORE therefore has no prompts unless the target repository happens to carry `var/prompts/`.
- **Two runtime roots, both live.**
  - `var/` is owned by PathResolver.
  - `work/` is ephemeral scratch. ADR-123 staging, ADR-147 canary sandboxes, the context cache and other writers use it, and it is declared `ephemeral-scratch` in `.intent/taxonomies/target_class_boundaries.yaml` (#772). It has no tracked file.
- **Runtime drift outside the declared paths.**
  - Root `reports/` holds 1,029 ignored files — all of them `reports/htmlcov/`. The writer is not `src/`: it is pytest-cov configuration in `pyproject.toml` (`--cov-report=html:reports/htmlcov`, `[tool.coverage.html] directory`, `[tool.coverage.xml]`/`[json] output`). The `src/` mentions of `reports` are exclusion lists; the former `src/` writers already route through `PathResolver.reports_dir` (`var/reports/`).
  - The Makefile writes `var/log/` (lines 26 and 74); PathResolver declares `var/logs/`.
  - An untracked, empty `opt/dev/CORE/var/{reports/decisions,run}` tree exists at root. Cause established: `FileHandler.ensure_dir` strips a leading slash, so an absolute path is re-rooted under the repository; `DecisionTracer.__init__` passes one. Filed as #908; it is a FileHandler defect, not a layout question.
- **Stale schema references.** `infra/sql/db_schema_live.sql` no longer exists. CI and `docker-compose.test.yml` already seed from `schema.sql`. ADR-115 (lines 63, 74, 158, 196) and the docstrings in `src/cli/logic/db.py` and `src/cli/resources/database/migrate.py` still name the old file.

A convention without a check decays. This ADR therefore makes the tree **declared data** and **enforces** it before any file moves. The clean-up then proceeds as bounded drains that can only shrink.

## Decisions

### D1 — Seven kinds, and every tracked top-level entry is exactly one

| Kind | Who writes | Tracked | Top-level entries |
|---|---|---|---|
| Constitution | the Governor, deliberately | yes | `.intent/`, `.specs/` |
| Code | humans and CORE, via review | yes | `src/`, `tests/` |
| Resources — inputs the system loads (D1a) | humans, via review | yes | `resources/` (`prompts/`, `catalogs/grc/`, `catalogs/packs/`, `starter-intent/`, `knowledge/`) |
| Human documentation | humans | yes | `docs/`, `examples/` (demos only — nothing the system reads), `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `SECURITY.md`, `ROADMAP.md`, `LICENSE`, `CLAUDE.md` |
| Deployment artifacts | humans | yes | `infra/` (second level declared in D1b), `.github/`, `docker-compose.yml`, `docker-compose.test.yml`, `entrypoint.sh`, `.env.example`, `.env.test` — and the root-pinned integration surfaces `Dockerfile` (the Action builds from it), `action.yml`, `.pre-commit-hooks.yaml`, `.gitlab-ci/` (consumers `include` it by path), `install-core.sh`, `schema.sql` (#521): external consumers reference these by path, so moving one is a release-noted breaking change |
| Developer tooling | humans | yes | `scripts/`, `Makefile`, `pyproject.toml`, `poetry.lock`, `.pre-commit-config.yaml`, `mkdocs.yml`, `.gitignore` |
| Runtime state / build output | the running system, or a tool run by a human | no | `var/` (PathResolver-owned, retained state), `work/` (ephemeral scratch, ADR-123/147), `reports/` (coverage output; see D6) |

Root keeps a deployment or tooling file only when its consumer requires the root:
- Docker and compose resolve from the root;
- GitHub resolves `action.yml` there;
- pre-commit resolves `.pre-commit-hooks.yaml` there;
- GitLab consumers include `.gitlab-ci/CORE.gitlab-ci.yml` by that path (the file's own usage header);
- `install-core.sh` and `schema.sql` are fixed by #521.

`CLAUDE.md` is classed as human documentation. Its readers include agents, but it is authored and changed only by humans. It is also the one root file this ADR obliges to change (D4); that edit is within Claude Code's write scope and lands with the implementing change-set.


### D1a — Resources: the kind in human language

CORE reads three kinds of file at runtime, and they are told apart by *what deleting one does*:

- Delete a **law** file and the system loses a constraint it was supposed to have — usually
  **silently** (a rule document gone is a rule that is simply no longer evaluated; nothing errors, the
  next violation passes CI), sometimes **loudly** (a fail-closed loader such as the safe-auto-approval
  envelope denies everything when its file is missing), sometimes as a **declined capability** (a
  worker without its declaration does not start), and in one case as a **mechanism that outlives its
  law** (a `passive_gate` rule `enforced_by` FileHandler keeps refusing but now names a rule that does
  not exist). Never by doing something it was not allowed to do. Law lives in `.intent/`, is written by
  the Governor, and is read-only at runtime (ADR-130 D1, `governance.constitution.read_only`).
- Delete a **state** file and the system merely **forgets** — a log, a cache, a report, a run
  directory. State lives under `var/` (retained) or `work/` (ephemeral), is written by the running
  system, and is never tracked (ADR-031/032, ADR-123/147).
- Delete a **resource** and the system **cannot do its job** — a prompt cannot be built
  (`FileNotFoundError` in `prompt_model.py`), a pack cannot be adopted, a catalog cannot be resolved,
  a target cannot be scaffolded — without any rule having changed and nothing having been forgotten.
  A resource is an **input the running system loads to do its work**: authored by humans, tracked in
  git, reviewed like code, shipped with the product, and **never written at runtime**.

Today's resources, by that test: prompt templates (`var/prompts/`), governance packs (`packs/`,
ADR-149), GRC catalogs (`grc-catalogs/`, ADR-116), the starter law CORE scaffolds into adopters
(`examples/starter-intent/`), and knowledge seeds (`var/knowledge/`, `var/mind/knowledge/`). Five
roots, three of them inside directories whose names say something else (`var/` says "state",
`examples/` says "not loaded"). The `.gitignore` exception that tracks `var/prompts/` (#296) is the
symptom of that mislabelling.

**Decision.** Resources are one kind and live under one root:

```
resources/
  prompts/          ← var/prompts            (prompts drain ADR; ~20 .intent refs + PathResolver.prompts_dir)
  catalogs/grc/     ← grc-catalogs           (catalog drain ADR amending ADR-116 D2/D8/D9; protection-first commit)
  catalogs/packs/   ← packs                  (same ADR; reverses ADR-149's *placement* "top-level packs/", not its substance — outside `.intent/`)
  starter-intent/   ← examples/starter-intent
  knowledge/        ← var/knowledge, var/mind/knowledge
```

Three properties define the root, and each is enforced (D3a):

1. **The system reads resources only from `resources/`.** No `src/` code names any other directory as
   the home of an input; the only place a resource path is spelled out is `PathResolver`.
2. **The system never writes under `resources/`.** A governed change to a prompt or a catalog is a
   proposal against a tracked file — the same path as a change to `src/` — never a runtime write.
3. **Every resource ships with the product.** What the wheel carries as package data is
   byte-identical to `resources/` at the tagged commit, the way `src/shared/_machinery_floor/`
   already mirrors the starter law (ADR-108 D3, ADR-112; `machinery_floor_integrity.verify_floor`).
   The 2.9.1 wheel ships zero prompt files; this kind makes that defect visible and property 3
   closes it.

What is **not** a resource: `examples/pharma-demo/` (nothing reads it — demos stay in `examples/`);
`src/shared/_machinery_floor/` (package *data*, the wheel-side mirror of a resource, not a source of
truth — the `src/` register entry says so); `.intent/enforcement/config/*` (constrains behaviour —
law; `var/mind/config/local_mode.yaml` and `runtime_requirements.yaml` are dispositioned there or
to `resources/` by that test in their drain); `schema.sql` (consumed by `install-core.sh`/CI, not
loaded by the running system — a published surface).

**The one-line test for a newcomer:** *Does CORE open this file while doing its job, and would a
human have written it?* Yes and yes → `resources/`. Written by CORE → `var/`. Written by the
Governor to constrain CORE → `.intent/`.

### D1b — `infra/` second level is declared in this ADR

`infra/` is where the placement confusion actually lives (68 files, eight sub-directories, four
different kinds), and the register's prefix mechanism (D2 `protected`/`legacy`) already reaches
below the root, so governing this one second level now costs nothing extra. `infra/` contains
exactly:

```
infra/
  docker/      ← .docker (image builds we control; the Action's Dockerfile stays at root, pinned)
  systemd/     (units)
  logrotate/
  demo/        (compose for demos)
  db/
    migrations/    ← infra/scripts/migrations   (39 SQL files)
    manifest.yaml  ← infra/migrations/manifest.yaml (the ledger, read by src/shared/infrastructure/repositories/db/common.py)
    one-off/       ← infra/sql
    init-test-db.sh, reset_test_db.sh, reset_and_rebuild_db.sh  ← infra/scripts (deployment: mounted/used by compose and install-core.sh)
```

Nothing else: the ten remaining Python files of `infra/scripts/` are developer tooling and move to
`scripts/`; `infra/tools/` and `infra/work/` are deleted after a per-file reference check
(`context_packets` included). `schema.sql` stays at root (#521). Consumers of the moved paths
(`migrate.py`, `db.py`, `db/common.py`, `docker-compose.test.yml`, a test docstring) move in the same
change-set.

### D2 — The register is law: `.intent/META/repo_tree.yaml`

The D1 table becomes data in a new file, `.intent/META/repo_tree.yaml`, validated by a new `.intent/META/repo_tree.schema.json` and modelled on `intent_tree.yaml`. It has two lists:

- **`entries`** — each allowed top-level path, with `type` (`file` | `dir`), `kind` (one of the D1 seven), `tracked` (bool), and for the `resources` kind `system_writes: false` and `ships: true` — the single place the D1a boundary is declared, read by FileHandler (D3a-2) and the wheel test (D3a-3). Second-level rows are permitted for `resources/` and `infra/` (D1a, D1b); `examples/` stays `kind: documentation`, which is the register's one-line reason `starter-intent` cannot remain there. A tracked directory entry, or a legacy entry, may also list **protected sub-paths** (`protected: [<prefix>, …]`): paths that must never contain a tracked file. This is how the register carries the IP boundary of ADR-116 D8/D9: the licensed and internal GRC tiers are declared protected, so the D3 check fails if licensed or internal-corpus bytes are ever staged.
- **`legacy`** — each non-conforming path that exists today, with `path` (top-level, or a deeper prefix under a `tracked: false` entry), `target` (destination, or `delete`) and `issue` (its drain issue).

Rules for the register:
- A new top-level entry requires a new `entries` row. Only the Governor adds one: CORE never writes `.intent/` (ADR-130 D1, `governance.constitution.read_only`), and Claude Code writes it only under the CLAUDE.md confirmation gate.
- An `entries` row MAY name a path that does not yet exist (`catalogs/`, `prompts/` before their drains; `work/` has no tracked file). The check is one-directional — every tracked path must be declared, not every declared path must exist — otherwise no drain could stage its target before the move. A declared-but-empty `tracked: true` entry is not a finding under this ADR; it is noted as a possible later tightening.
- **Validation.** `MetaValidator` skips `intent_tree.yaml` *by name* and reads it separately as the directory declaration. `repo_tree.yaml` is deliberately **not** added to that by-name exclusion: `META` is a `validated_directories` entry, so the new file is walked like every other governed document and must satisfy `GLOBAL-DOCUMENT-META-SCHEMA.json` and its own `$schema`, under the `constitution validate` CI gate (#617 ratchet, currently 0 errors). "Modelled on `intent_tree.yaml`" means the shape, not the exemption.
- Both files are Governor-applied and classified in `namespace_manifest.yaml` like every other `.intent/` file (ADR-075 D7).
- The legacy list is seeded from `git ls-files` at the implementation commit, not from this document.

**What the protected sub-paths do and do not do.** The D3 check runs in CI, after a push. A commit that carries licensed bytes fails the build when those bytes are already on the public remote. For a public-repository IP leak a red build is detection, not containment. Therefore:
- `.gitignore` (`grc-catalogs/licensed/`, `grc-catalogs/internal/`, and their successors under D5) remains the **preventive** layer, and the D5 "protection first, one commit" constraint is the real control during the rename.
- The check is a **tripwire**: it catches a force-add, a rename that dropped an ignore line, or a mount at the wrong path — the failure modes `.gitignore` alone cannot report.
- Its universe is `git ls-files`, which never contains ignored paths. The check proves "nothing licensed is *staged*", not "nothing licensed is *present*". A correctly ignored licensed tree mounted on a developer machine is invisible to it, by design.

### D2b — PathResolver is the register's code twin, and the register governs `var/` one level down

**The fact.** The runtime tree is declared three times today: `PathResolver` (`src/shared/path_resolver.py`,
fifteen `_DEFAULT_*_SUBDIR` class constants plus `grc_catalogs_dir`, surfaced by `runtime_dirs()`),
the `no_hardcoded_runtime_dirs` regex alternation in
`.intent/enforcement/mappings/architecture/path_access.yaml`, and — after D2 — `repo_tree.yaml`.
Nothing checks one against another; the Makefile's `var/log` against PathResolver's `var/logs`
(Context) is what that looks like in practice.

**Decision.** `repo_tree.yaml` is the single source. It declares `var/` one level down (as D1a/D1b
do for `resources/` and `infra/`): one row per runtime directory with `kind: state`, `retained: true|false`
(retained → `var/`, ephemeral → `var/tmp/` or `work/`), and **`resolver: PathResolver.<property>`** —
the register names the code that resolves it. PathResolver and the regex mapping are **mirrors**, and
two standing tests keep them honest:

1. `tests/shared/test_path_resolver_matches_repo_tree.py` — the set of `(relative path, property)`
   pairs from `PathResolver.runtime_dirs()` equals the set of `var/` rows' `(path, resolver)` in the
   register; a directory declared without a resolver, or a resolver property without a row, fails.
   Same shape as `tests/infra/test_claude_md_rule_digest_matches_source.py` (#775).
2. The two path-rule mappings (`no_hardcoded_runtime_dirs`, and D3a-1 `resources.single_root`) are
   checked for coverage against the register: every `state` and `resources` directory name appears in
   the pattern alternation, and no name in the alternation is undeclared. (Generating the patterns from
   the register is the cleaner end state; the check is enough for this ADR and keeps the mapping a
   plain file the Governor can read.)

**Why a mirror and not a read.** PathResolver is bootstrap infrastructure in `src/shared/`: it is
constructed before `IntentRepository` is initialised, it resolves paths for external targets whose
`.intent/` is *not* CORE's (#894 bindings), and the daemon's path layer must stay deterministic
without YAML parsing on every construction. Making it read the register at runtime would invert that
dependency. Verified mirroring is the same choice ADR-112 made for the framework floor ("mirrors
registry"); it keeps the register authoritative and the runtime path layer boring.

**Consequences for PathResolver in the drains.**
- `grc_catalogs_dir` → `resources_dir / "catalogs" / "grc"`; new `resources_dir`, `catalogs_dir`,
  `starter_intent_dir`; `prompts_dir` and `knowledge_dir` re-rooted under `resources/` (D3a-1).
  Each is a `resources` row in the register with the same `resolver:` field, so test 1 covers both kinds.
- `_DEFAULT_MIND_SUBDIR` (`var/mind`) and `rollbacks` stay `state`; `var/mind/knowledge` leaves for
  `resources/knowledge` (D5).
- The Makefile, `install-core.sh` and `docker-compose*.yml` name runtime directories by string
  (`var/run`, `var/logs`, `var/log`). They are outside the audit's `src/` scope by design; test 1
  cannot reach them. D6's Makefile fix stands, and the register's `var/` rows are the reference the
  next such literal is checked against by a human.

**Registration.** Test 1 and test 2 are new test files (no rule, no engine); the `resolver:` and
`retained:` fields go in `repo_tree.schema.json`; `runtime_dirs()` gains the property name it already
implies (it returns `(Path, "var/…")` pairs today — the test needs the attribute name, a one-line
change to the tuple).

### D3 — One blocking check: `governance.repo_tree.declared`

**The rule.** A new rule, `governance.repo_tree.declared` (authority: constitution; phase: audit; enforcement: blocking), states:

> Every tracked path's top-level component MUST be declared in `repo_tree.yaml` `entries` or `legacy`. No tracked path may fall under an entry declared `tracked: false` unless it matches a `legacy` prefix. No tracked path may fall under a `protected` sub-path, and no legacy entry can excuse one. Declared entries MAY be absent from the tree.

**How it runs.**
- It is implemented as a new check type in `artifact_gate`, `repo_tree_completeness`, which joins `_GOVERNANCE_CHECK_TYPES` and dispatches at context level (ADR-076 D3). It has the shape of `_check_namespace_manifest_completeness`: a set-difference, failing closed if the register is missing or unparseable.
- Its universe is the tracked-file list, obtained through the existing shared primitive `shared.infrastructure.git_service.GitService` (its tracked-files method wraps `git ls-files`), not a filesystem walk and not a new `subprocess` call in the engine. The verdict is therefore identical on a developer machine and a fresh CI checkout, and ignored runtime content never counts.
- It needs no database and no LLM, so it runs under `--offline`.
- It is placed in the `governance.*` namespace, next to its precedents, not in `layout.*`. The layout sensor is a per-file Python cohort.

**Registration obligations** (all in the implementing change-set; each one is a CI gate that has gone red on an omission before):
- the rule document and its enforcement mapping;
- `auto_remediation.yaml`, as a DELEGATE entry, because placement is a Governor decision;
- `namespace_manifest.yaml` entries for every new `.intent/` file (ADR-075 D7);
- `META/vocabulary.json` for the new `check_type` value;
- CLAUDE.md's rule digest — the blocking/reporting/advisory counts and the Blocking list (`tests/infra/test_claude_md_rule_digest_matches_source.py`, #775);
- README's rule/document/mapping counts (`scripts/check_readme_counts.sh`, #631);
- violating and compliant fixtures in `.specs/verification/g2_blocking_rule_registry.yaml`. The violating fixture is a throwaway git repository with one undeclared top-level file (precedent: `tests/fixtures/external_target/materialize.py` builds real disposable repositories) — this, not a provocation on `main`, is how the check is proven to fire;
- an ADR-076 firing-coverage test.


### D3a — Enforcing the three resource properties

Each property is one check on an engine CORE already runs; nothing new is built.

**(1) Read only from `resources/` — `architecture.resources.single_root` (blocking, `src/**/*.py`).**
Same shape as `architecture.path_access.no_hardcoded_runtime_dirs` (ADR-031/032): a `regex_gate`
`pattern_match` mapping whose patterns forbid, in path-construction expressions, the literals
`resources/`, `examples/starter-intent`, `grc-catalogs`, `packs/`, `var/prompts`, `var/knowledge`
and `var/mind/knowledge`, with the same excludes (`src/shared/path_resolver.py`, the two storage
canonical surfaces, `tests/**`). `PathResolver` gains `resources_dir` and typed children
(`prompts_dir`, `catalogs_dir`, `starter_intent_dir`, `knowledge_dir` — the last two replace their
current `examples/` and `var/mind/knowledge` roots). Consumers move to the property in the same
change-set as the file move, so the rule fires on nothing at the moment it lands and on everything
that regresses afterwards. Registration obligations as in D3.

**(2) Never written at runtime — `architecture.resources.read_only` (blocking; `enforced_by`
FileHandler).** Same shape as `architecture.execution_write.repository_containment` (#895 U3 D2, a
`passive_gate` class-A rule): `FileHandler._resolve_repo_path` refuses any execution-time write whose
resolved target lies under `resources/`, raising a typed refusal that names this rule. The register's
`system_writes: false` flag is what the handler reads, through `IntentRepository`. Governed edits to
a resource go through the proposal path like any edit to `src/` (ADR-101 D2 commit-set derivation
applies unchanged). G2 registry row with a real fixture: a `write=True` execution write to
`resources/prompts/x` is refused before mutation; the same change as a proposal action lands.

**(3) Ships with the product — a standing test, not a rule.** `tests/infra/test_resources_ship_in_wheel.py`
builds the package-data manifest the way `machinery_floor_integrity.floor_manifest()` does and asserts
it equals a SHA-256 manifest of `resources/` at HEAD; the package-data include in `pyproject.toml` is
the only thing the test needs to be true. Precedent: the floor integrity check and
`tests/body/atomic/test_machinery_floor_action_risk_coverage.py`. A test rather than an audit rule
because the audit engines see the tree, not the wheel; CI's hermetic job already builds the wheel for
its e2e step, so the check runs where the artefact exists.

**Sequencing.** (1) and (2) land with the register and the D3 layout check, *before* any file moves:
they are the ratchet the drains run under. (3) lands with the prompts drain — the first resource whose
absence from the wheel is a user-visible defect.

### D4 — Where it is enforced

- **CI is the authority** (ADR-023 §"The CI gate is upstream prevention"). The `static-checks` job in `core-ci.yml` already runs `core-admin code audit --offline --severity=block`, so an undeclared entry fails the build with no workflow change. Proof that it fires is the G2 violating fixture and the firing-coverage test (D3). CORE does not use pull requests and CI runs on pushes to `main`/`develop`, so a live provocation would leave a deliberately red commit in public history; if one is ever wanted, it runs by `workflow_dispatch` on a throwaway branch, never on `main`.
- **Pre-commit MAY run the same audit locally** as a convenience. It carries no constitutional weight, because it can be skipped (ADR-023 Alternative E).
- **`CLAUDE.md` § Source layout points to `repo_tree.yaml`**, so agents read the rule before creating a directory.
- **The daemon does not surface this finding. This ADR records that; it does not fix it.**
  - The finding carries `file_path="repo"` (the one context-level emission site in `artifact_gate`), and `filter_actionable_violations` (`src/will/audit_violation/filter.py`) drops every non-`.py` path.
  - The same drop applies to every existing repo-level check in `artifact_gate`.
  - It is filed as its own issue; it is not solved here.

### D5 — The legacy ratchet

- Entries leave `legacy` one drain issue at a time and never return. Adding a legacy entry is a deliberate Governor edit, which is visible and reviewable.
- Each drain is one small change-set that moves or deletes the files, fixes every reference the recon found, and removes the entry.
- Drains with a large constitutional blast radius get their own ADR. The prime example is `var/prompts/` → `prompts/`: about 20 `.intent/` references across worker mandates, `artifact_types/prompt.yaml`, the `prompt_artifact_structure` and `prompt_governance` mappings, and `path_access.yaml`, plus `PathResolver.prompts_dir`. That move must be atomic, and the prompt rules must be shown to still fire afterwards (the ADR-076 inert-rule hazard).

Initial drain list (legacy paths → target):

| Legacy path | Target | Note |
|---|---|---|
| `hooks/` | `scripts/hooks/` | `.pre-commit-config.yaml` line 40; no `src/` imports |
| `.docker/` | `infra/docker/` | `publish-docker-core-engine.yml` lines 81–82 |
| `infra/scripts/migrations/`, `infra/migrations/`, `infra/sql/` | `infra/db/` (D1b) | one drain; update `migrate.py`, `db.py`, `db/common.py`, a test docstring |
| `infra/scripts/` (rest) | `infra/db/` for the three DB shell scripts; `scripts/` for the ten Python tools | per D1b |
| `infra/tools/` (4 scripts), `infra/work/` (`context_packets/`, 1 file) | `delete` after confirmation | zero references found at the first recon; re-verify per file (including `context_packets`) in the drain |
| `var/prompts/` | `resources/prompts/` | own ADR (above); carries D3a-3 (ship in the wheel) |
| `examples/starter-intent/` | `resources/starter-intent/` | `onboard_routes.py`, `scout.py` (`_FALLBACK_RULES_REL`), the floor's `intent_tree.yaml` note |
| `grc-catalogs/` | `resources/catalogs/grc/` | own ADR amending ADR-116 D2/D8/D9 (see below) |
| `packs/` | `resources/catalogs/packs/` | same ADR; it reverses the Governor resolution of 2026-07-14 in ADR-149 ("location is top-level `packs/`") and must say so; `PackLoader` root (`intent_repository.py`, two sites) and `adopt_pack.py` follow |
| `var/knowledge/`, `var/mind/knowledge/` | `resources/knowledge/` | `PathResolver.knowledge_dir` follows |
| `var/mind/config/` | `.intent/enforcement/config/` if it constrains, else `resources/` | by the D1a delete-test, per file |
| `var/core/mind_export/`, `var/mind/history/`, `var/core/ir/` | untrack (state) — or `.specs/` if the IR logs are reasoning | per file |
| `var/mind/northstar.yaml` | `delete` | duplicate of `.specs/northstar/` |

**The catalog consolidation is IP-critical.** The licensed and internal tiers are protected only by the `.gitignore` lines `grc-catalogs/licensed/` and `grc-catalogs/internal/`. If the directory is renamed without those lines, licensed bytes mounted on a developer machine become stageable into the public repo — and, per D2, the D3 check would report that only after the push. The drain therefore has three constraints:

- **One commit, protection first.** The rename, the new `.gitignore` lines for `resources/catalogs/grc/licensed/` and `resources/catalogs/grc/internal/`, and the `protected` sub-paths in `repo_tree.yaml` land together, with the protection added before the move.
- **Consumers updated in the same commit.** `PathResolver.grc_catalogs_dir` and the catalog resolver move with the rename.
- **Mount points updated.** Every documented clone or mount target for the private `core-grc-catalogs` repository moves to the new path.

Until that ADR lands, `grc-catalogs/licensed/` and `grc-catalogs/internal/` are declared `protected` under the current `grc-catalogs` legacy entry.

### D6 — Runtime hygiene and corrigenda

These items fall outside the check, because the check governs what is committed. Runtime creation is governed by FileHandler and PathResolver (ADR-031), so these are tracked as issues:

- **Root `reports/`** is coverage output written by pytest-cov per `pyproject.toml`, not by `src/`. Decide once: either keep it as declared build output (D1 kind 7, `tracked: false`, `.gitignore` line 95 already covers it) or point the four `pyproject.toml` coverage paths at `var/reports/`. There is nothing to route through PathResolver.
- Change the Makefile from `var/log` to `var/logs`.
- **`opt/dev/`** is #908 (`FileHandler.ensure_dir` re-roots absolute paths; `DecisionTracer.__init__` is the caller). Fix there; delete the phantom tree after. `import_sorting_handler.py:55` hard-codes `/opt/dev/CORE` — a separate hardcoded-root defect, not the creator.
- **Append-only corrigendum to ADR-115:** CI seeds from `schema.sql` (#521). References to `infra/sql/db_schema_live.sql` are historical. The docstrings in `src/cli/logic/db.py` and `migrate.py` are corrected in the same issue.

## Consequences

**Positive.**
- A new top-level entry cannot land on `main` with a green build without a deliberate Governor edit.
- The clean-up becomes a finite, visible, shrinking list rather than a one-off reorganisation that must succeed all at once.
- The check reuses an existing engine, dispatch path, git primitive and CI step; no new engine, no new workflow.
- The licensed/internal IP boundary gains a tripwire that reports what `.gitignore` alone cannot: a force-add, a rename that dropped the ignore line, a mount at the wrong path. `.gitignore` remains the preventive layer (D2).

**Costs and obligations.**
- Two new Governor-applied `.intent/META/` files (constitutional core: file-by-file confirmation), three rules (D3, D3a-1, D3a-2), their mappings, one check type, one standing test (D3a-3), plus the eight registration obligations in D3 for each rule.
- `PathResolver` grows `resources_dir` and typed children; 13 modules that reference `prompts_dir` and the `examples/`/`packs/`/`grc-catalogs` consumers move to them across the drains.
- `PathResolver` becomes a verified mirror of the register (D2b): two standing tests, two new schema fields, a one-line change to `runtime_dirs()`.
- The daemon stays blind to repo-level findings until the D4 filter issue is resolved.
- Second-level structure below `resources/` and `infra/` is governed (D1a, D1b); below `scripts/`, `var/`, `tests/` and inside `.intent/` (the prose files `ARCHITECT.md`, `daily_loop.md`, `CHANGELOG.md` living in the law directory) it is not yet. The register's shape allows it later without a new mechanism.

## Open items

- **`.specs/planning/` runbooks:** the `.specs/META/` twin (#617) already validates them with `planning.header.schema.json`, so they are constitution-side artifacts today; nothing to move unless the Governor wants them in `docs/`.
- **`work/` versus `var/`:** two runtime roots remain. Folding `work/` into PathResolver would touch ADR-123, ADR-147 and #772, so it is not proposed here.
- **Retention of `var/tmp/`:** convention, not enforced.
- **`tests/` non-mirror cohorts** (`tests/engines`, `tests/infra`, `tests/proof_index`, `tests/fixtures`, `tests/helpers`, `tests/var`) are deliberate; declaring them is a later ratchet.
