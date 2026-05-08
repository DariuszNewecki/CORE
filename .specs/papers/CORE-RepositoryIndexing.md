<!-- path: .specs/papers/CORE-RepositoryIndexing.md -->

# CORE — Repository Indexing

**Status:** Canonical
**Authority:** Policy
**Scope:** Autonomous structural self-model construction and semantic embedding

---

## 1. Purpose

This paper defines the Repository Indexing pipeline — the two-worker tandem
that maintains CORE's structural self-model and its semantic embedding layer.
Together, `RepoCrawlerWorker` and `RepoEmbedderWorker` give the system a
queryable representation of its own codebase.

---

## 2. Problem Statement

CORE's cognitive roles — ContextBuilder, CoderAgent, and their peers — rely on
vector evidence to reason about the codebase. That evidence must be current and
structured. A monolithic sync operation cannot scale to a repository that
changes continuously under autonomous governance: it couples structure extraction
with embedding, making it impossible to skip re-embedding unchanged artifacts or
to assign the two operations to different compute budgets.

The decomposed pipeline separates concerns. Crawling is deterministic and fast.
Embedding is expensive and model-dependent. Separating them allows each to run
at the cadence its cost justifies, and allows embedding to be triggered
precisely — by a content change, not by a schedule.

---

## 3. The Pipeline

Repository Indexing operates as a two-stage producer/consumer pipeline.

### Stage 1 — Repository Crawling

**Worker:** `RepoCrawlerWorker`
**Declaration:** `.intent/workers/repo_crawler.yaml`

Walks the CORE repository across all governed paths. For each file:

- Computes a SHA256 content hash.
- If the hash has not changed since the last crawl, skips the file.
- If the hash is new or changed: upserts the artifact record in
  `core.repo_artifacts` and sets `chunk_count = 0`. A value of zero is the
  explicit work-queue signal consumed by `RepoEmbedderWorker` (ADR-018 D4).
- For Python files: extracts AST call-graph edges into `core.symbol_calls`.
- For non-Python files: registers cross-references in
  `core.artifact_symbol_links`.

`RepoCrawlerWorker` does not embed. It does not call an LLM. It never follows
symlinks.

### Stage 2 — Semantic Embedding

**Worker:** `RepoEmbedderWorker`
**Declaration:** `.intent/workers/repo_embedder.yaml`

Consumes `core.repo_artifacts` records where `chunk_count = 0`. For each:

- Chunks the artifact according to its type.
- Embeds each chunk using the configured embedding model.
- Upserts the embedded chunks into the appropriate Qdrant collection.
- Updates `core.repo_artifacts.chunk_count` to the number of chunks
  produced, clearing the work-queue signal.

`RepoEmbedderWorker` depends on `RepoCrawlerWorker` having populated
`core.repo_artifacts` first. It does not crawl.

---

## 4. Qdrant Collection Routing

| Artifact type | Qdrant collection |
|---|---|
| Python source (`src/**`) | `core-code` |
| Documentation | `core-docs` |
| Tests | `core-tests` |
| Prompts (`var/prompts/**`) | `core-prompts` |
| Reports | `core-reports` |
| Intent governance (`.intent/**`) | `core-patterns` |

---

## 5. Work-Queue Protocol

The `chunk_count` column on `core.repo_artifacts` is the synchronization
surface between the two workers.

| Value | Meaning |
|---|---|
| `0` | Content changed; embedding required. Produced by RepoCrawlerWorker. |
| `> 0` | Embedded; `chunk_count` reflects actual chunks stored. |
| `-1` | Permanently empty artifact; skip embedding. |

This contract is declared in ADR-018 D4 and must not be bypassed by direct
column writes from any other component.

---

## 6. Constitutional Identity

| Field | RepoCrawlerWorker | RepoEmbedderWorker |
|---|---|---|
| Declaration | `.intent/workers/repo_crawler.yaml` | `.intent/workers/repo_embedder.yaml` |
| Class | `sensing` | `sensing` |
| Phase | `audit` | `audit` |
| Permitted tools | `file.read` | `file.read`, `llm.embedder` |
| Approval required | false | false |
| Schedule | max_interval 600 s | max_interval 600 s, batch_size 50 |
| ADR | ADR-018 | ADR-018 |

Both workers are classified `sensing` because each reads state and records
derived state; neither invokes LLM-driven mutation against `src/` files. The
`llm.embedder` tool used by `RepoEmbedderWorker` is a read-only embedding
operation, not a generative mutation.

---

## 7. Architectural Lineage

This pipeline supersedes `vector_sync_worker`, which wrapped both operations in
a single acting worker. The decomposition is governed by ADR-018. The monolithic
wrapper is retired; its YAML declaration has been removed from `.intent/workers/`.
The `sync.vectors.code` action is preserved for CLI-triggered full syncs.

---

## 8. Non-Goals

This paper does not define:
- the chunking strategy per artifact type
- embedding model selection (governed in `core.runtime_settings` and ADR-024)
- Qdrant collection schema or indexing parameters
- the vector query interface used by cognitive roles (see ADR-022)

---

## 9. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
