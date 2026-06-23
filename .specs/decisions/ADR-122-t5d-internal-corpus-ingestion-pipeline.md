---
kind: adr
id: ADR-122
title: 'ADR-122 — T5d: Internal corpus ingestion pipeline — Qdrant wiring, chunking, CLI surface, and judge augmentation'
status: accepted
---

<!-- path: .specs/decisions/ADR-122-t5d-internal-corpus-ingestion-pipeline.md -->

# ADR-122 — T5d: Internal corpus ingestion pipeline

**Status:** Accepted — governor-ratified 2026-06-21
**Date:** 2026-06-21
**Grounds:** ADR-116 D9 (the internal corpus decision boundary this ADR implements).
**Relates:** ADR-113 (evidence class — JUDGED stays JUDGED with or without augmentation);
  ADR-118 (RequirementVerdict — the consumer of the augmented judge);
  `CORE-RepositoryIndexing.md` (the code-corpus crawler/embedder pattern this mirrors).

---

## Context

ADR-116 D9 ratified the three-boundary model and defined the internal corpus layout
(`grc-catalogs/internal/<framework>/source/`, `text/`, `licence.yaml`) and the
licence gate (`internal_use_licence: required` in `inventory.yaml`). It explicitly
deferred "the internal-corpus ingestion pipeline, licence-gate enforcement, and Qdrant
wiring" to implementation.

Four things are unspecified by D9 and required before any code is written:

1. **Qdrant collection naming** — how are per-framework collections identified?
2. **Chunking strategy** — how is the source text split and what metadata does each
   chunk carry?
3. **Ingestion surface** — what triggers ingestion and what does the operator invoke?
4. **`grc_judge` augmentation** — how does the judge query the internal corpus at
   verdict time, and what happens when the collection is absent?

The code-corpus analogue (`RepoCrawlerWorker → RepoEmbedderWorker`) provides a
precedent for the crawler/embedder split and the `chunk_count` synchronization signal,
but the GRC internal corpus is operator-managed and CORE-internal, so the trigger and
lifecycle differ.

---

## Decision

### D1 — Per-framework Qdrant collection, named `grc-internal-{framework_id}`

Each framework gets its own collection: `grc-internal-nist_800_171`,
`grc-internal-gdpr`, `grc-internal-cfr_part_11`, etc. This mirrors D9's explicit
"per-framework Qdrant collection, not as files" and gives each framework an
independent lifecycle — different ingestion cadences, independent replacement, and
clean deletion when a licence is not renewed.

The `grc-internal-` prefix is distinct from the `core-*` family (which covers CORE's
own self-model: `core-code`, `core-specs`, `core-patterns`, etc.) and signals that
these collections are GRC-domain data, not CORE self-governance artifacts.

The collection is created on first ingest and replaced (not merged) on re-ingest.
Re-ingestion is idempotent: the previous collection is dropped and rebuilt from the
current `text/` content.

### D2 — Structure-aware chunking with `ChunkingConfig` fallback

Regulatory text has natural boundaries (articles, sections, controls, recitals).
Where the text is pre-structured into sections (one file per section in
`internal/<framework>/text/`, named by section identifier), each section file
becomes one chunk if it fits within `max_chunk_chars`; oversized sections fall back
to the shared `_chunk_text` utility (from `shared.utils.embedding_utils`) using the
project's `ChunkingConfig` defaults (512-token target, 50-token overlap). Unstructured
text (single blob) is chunked entirely by `_chunk_text`.

Each chunk upserted to Qdrant carries a payload:

```json
{
  "framework_id": "nist_800_171",
  "section_id": "3.1.1",        // null if not derivable from filename
  "source_ref": "NIST SP 800-171 Rev. 2 §3.1.1",
  "text": "..."
}
```

`section_id` is derived from the filename (e.g., `3.1.1.txt` → `"3.1.1"`); if the
filename does not parse as a section identifier, `section_id` is null. This keeps
chunking honest — no invented structure where none exists.

The embedding model is the project's configured local embedder (`nomic-embed-text`
via `settings.LOCAL_EMBEDDING_MODEL_NAME`), identical to the code-corpus embedder.

### D3 — Ingestion surface: `core-admin grc ingest <framework_id>`

Ingestion is a **CLI command**, not a worker. The internal corpus is CORE-operator
work: it requires deliberate action (obtaining source material, confirming licence
satisfaction) and is never triggered autonomously. A worker would be wrong here for
the same reason the autonomous daemon must not scoop licensed bytes into a commit
(ADR-116 D8).

Command: `core-admin grc ingest <framework_id> [--text-dir <path>]`

Execution sequence:

1. **Licence gate** — read `grc-catalogs/inventory.yaml`; find the entry for
   `framework_id`. If `internal_use_licence: required` is set AND
   `grc-catalogs/internal/<framework_id>/licence.yaml` does not exist → refuse with
   a clear message naming what licence is required and where to place the file. If
   `internal_use_licence` is absent from the entry (public-domain /
   official-*-reusable) → allow unconditionally.

2. **Locate text** — default source is `grc-catalogs/internal/<framework_id>/text/`;
   `--text-dir` overrides. If the directory is absent or empty → abort with a clear
   message (populate `text/` first; text extraction is out of scope for this command).

3. **Chunk and embed** — walk `text/` files, apply D2 chunking, embed each chunk
   via `nomic-embed-text`.

4. **Upsert to Qdrant** — drop the existing `grc-internal-{framework_id}` collection
   (if present) and upsert all embedded chunks. Report chunk count on completion.

5. **Write `licence.yaml`** — record the provenance of this ingest:

   ```yaml
   framework_id: nist_800_171
   internal_use_licence: public-domain    # from inventory.yaml; absent means ungated
   ingested_at: "2026-06-21T11:30:00Z"
   text_dir: grc-catalogs/internal/nist_800_171/text
   chunk_count: 142
   collection: grc-internal-nist_800_171
   embedding_model: nomic-embed-text
   ```

   Written to `grc-catalogs/internal/<framework_id>/licence.yaml`. Gitignored (same
   directory as `source/` and `text/`), so this file never enters any committed repo.

Text extraction (PDF → `text/`) is a separate operator step, out of scope for this
ADR. A future `core-admin grc fetch` command may automate it for ungated frameworks;
for now the operator populates `text/` manually or via their own tooling.

### D4 — `grc_judge` augmentation: top-3 passages injected as source context

At verdict time, before constructing the LLM prompt, `GRCJudgeEngine` queries the
internal corpus:

1. Embed the requirement's `instruction` text (the same string already sent to the
   LLM as the instruction).
2. Query `grc-internal-{framework_id}` for the top-3 passages by cosine similarity.
3. Inject the retrieved passages into the prompt as a new section — **"AUTHORITATIVE
   SOURCE CONTEXT"** — placed immediately before the document content, so the model
   reads the authoritative source before the customer's text.

The `framework_id` is derived from the catalog's `provenance.yaml` field
`framework_id` (already present; catalog's `provenance.yaml` records which framework
it was derived from). If the catalog does not supply `framework_id`, augmentation is
skipped silently.

**Graceful degradation.** If the Qdrant collection is absent, empty, or the Qdrant
service is unreachable: log once at DEBUG level and proceed without augmentation. The
verdict is still valid — the model judges from the catalog's requirement text and the
document content, which is the current (unaugmented) baseline. No error is raised, no
finding is marked ATTESTED solely because augmentation was unavailable. The
`EvidenceClass` stays JUDGED in all cases — the LLM makes the judgement regardless
of how much context it has.

Top-K is fixed at 3. This is conservative: too few to distort the prompt, enough
to ground the model in the authoritative text for the specific requirement. It is a
code constant (`_INTERNAL_CORPUS_TOP_K = 3`), not a config value — it is a
product-quality choice, not an operator tunable.

### D5 — Licence gate is ingestion-time only; query-time is degradation-not-gate

The licence gate (D3 step 1) fires **at ingestion**, not at query time. Once a
collection exists it was gated on creation; the query path trusts the collection's
existence as proof. This avoids re-reading `inventory.yaml` on every verdict and
keeps the hot path clean.

If a licence lapses, the operator drops the collection (`core-admin grc drop
<framework_id>`) and the judge degrades gracefully (D4) until re-ingested under a
valid licence. No automated lapse detection — this is an operator obligation, not an
engine obligation, consistent with the manual ingestion model.

---

## Consequences

- **Ungated frameworks can be ingested immediately.** nist_800_171, gdpr,
  cfr_part_11, and eu_annex_11 carry no `internal_use_licence: required` gate;
  operators can populate `text/` and run `core-admin grc ingest` now.
- **Copyrighted frameworks are blocked at ingestion, not at design.** iso_27001,
  gamp5, and cyfun remain unavailable for internal corpus use until a
  commercial/internal-use licence is held and `licence.yaml` is placed. The
  engineering exists; the blocker is procurement.
- **`grc_judge` improves without a contract change.** The augmentation is additive;
  the judge's input/output contract (`instruction` + document → verdict) is
  unchanged. Callers and tests that don't populate the internal corpus see the same
  behaviour as today.
- **`licence.yaml` is the operator's attestation.** Placing it is a deliberate act
  confirming the gate is satisfied. It is gitignored and CORE-only, consistent with
  D9's "never enters any committed repo" invariant.
- **No new DB schema.** The internal corpus is Qdrant-only; `core.repo_artifacts`
  is not extended. The `chunk_count` synchronization pattern from
  `CORE-RepositoryIndexing.md` is not needed because ingestion is operator-triggered
  and fully synchronous — the CLI completes only after all chunks are upserted.

## Alternatives considered

- **Single `grc-internal` collection with `framework_id` as a filter field.**
  Rejected: per-framework collections allow independent lifecycle (drop/replace one
  framework without touching others) and avoid cross-framework payload pollution in
  vector search results. One collection also introduces accidental cross-framework
  retrieval if the similarity threshold is loose.
- **Worker-triggered ingestion (watching `text/` for changes).**
  Rejected: the internal corpus requires deliberate operator action (licence
  confirmation, source placement). Autonomous re-ingestion on file change violates
  the operator-ownership model and risks ingesting an incomplete or unlicensed
  corpus mid-write.
- **Top-K as a config value.**
  Rejected: operator-tunable K introduces a surface where a misconfigured value (e.g.
  K=50) bloats every verdict prompt with irrelevant passages and degrades judgment
  quality. 3 is a product decision, not an infrastructure knob; it belongs in code.
- **Augmentation raises an error when internal corpus is absent.**
  Rejected: the judge already works without augmentation (the unaugmented baseline is
  the current shipped behaviour). Making absence an error would break every customer
  deployment that hasn't run `grc ingest`, which is the majority. Degradation is the
  correct posture (consistent with ADR-116 D3's "fewer catalogs, never an error").

## Implementation scope

New files / changes required:

- `src/cli/commands/admin/grc_ingest.py` — `core-admin grc ingest` command
- `src/body/services/grc/internal_corpus.py` — chunking, embedding, Qdrant upsert;
  licence gate reader; `licence.yaml` writer
- `src/mind/logic/engines/grc_judge.py` — augmentation hook (query internal corpus,
  inject passages); `_INTERNAL_CORPUS_TOP_K = 3` constant
- `var/prompts/grc_judge/system.txt` — add AUTHORITATIVE SOURCE CONTEXT section
  (conditional: only injected when passages retrieved)
- `tests/body/services/grc/test_internal_corpus.py` — licence gate (ungated / gated
  / satisfied), chunk/embed round-trip, absent-collection degradation

## References

- ADR-116 D9 — the decision boundary this ADR implements
- ADR-113 — evidence class (JUDGED; unchanged by augmentation)
- ADR-118 — RequirementVerdict (consumer of augmented verdicts)
- `CORE-RepositoryIndexing.md` — code-corpus crawler/embedder precedent
- `grc-catalogs/inventory.yaml` — the licence gate source of truth
- `shared/utils/embedding_utils.py` — `_chunk_text` utility
- `shared/infrastructure/intent/operational_config.py` — `ChunkingConfig` defaults
