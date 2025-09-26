# Governed Embeddings System

## Preamble: The Canonical Reference
This document is the **single source of truth** for CORE's semantic embedding architecture.  
It incorporates and supersedes all previous proposals, defining the **constitutional guarantees**, **schema**, and **configuration** for this foundational component.

---

## Purpose
Embeddings provide **CORE** with a semantic map of its own code, intent, and documentation.  
They are a foundational component for advanced reasoning, allowing CORE to:

- **Detect duplicate or near-duplicate functions** (`dry_by_design`).
- **Link capabilities** defined in `.intent/` to their implementation in `src/`.
- **Reason about code and policies by meaning**, not just keywords (`reason_with_purpose`).

This document describes the current, **constitutionally governed embedding architecture**, which is designed for **determinism**, **provenance**, and **safety**.

---

## System Guarantees
The embedding system provides the following **constitutional guarantees**:

### Determinism
All text is passed through a strict normalization process (`src/shared/services/embedding_utils.py`) before being processed.  
This involves converting line endings, collapsing blank lines, and trimming whitespace.  
It ensures that identical content always produces an identical hash, preventing redundant work.

### Provenance
Every vector stored in **Qdrant** is accompanied by a rich payload, enforced by a Pydantic schema (`EmbeddingPayload` in `src/shared/models.py`).  
This guarantees that every piece of knowledge is **traceable to its origin, model, and version**.

### Schema Enforcement
The `QdrantService` strictly validates every upsert operation against the `EmbeddingPayload` schema.  
No vector can be stored without its **complete, valid provenance data**.

### Incremental Updates
The vectorization orchestrator (`src/system/admin/knowledge_orchestrator.py`) uses the `content_sha256` and `model_rev` from the payload to check if a capability's source code has changed.  
This acts as an effective cache, ensuring that **unchanged code is not re-embedded**, saving time and resources.

---

## Architecture & Schema
The system uses a **single Qdrant collection** with a formally defined schema for all vector payloads.

- **Collection Name:** `core_capabilities` (defined by `QDRANT_COLLECTION_NAME`)
- **Distance Metric:** Cosine
- **Point ID:** A deterministic UUIDv5 derived from a stable identifier (e.g., the symbol key), ensuring upserts are idempotent.

### Payload Schema (`EmbeddingPayload`)
All vectors stored in Qdrant must conform to this schema:

| Key | Type | Required | Purpose |
|-----|------|---------|--------|
| `source_path` | string | ✅ | Repo-relative path of the source file. |
| `source_type` | enum | ✅ | Type of content (code, intent, docs). |
| `chunk_id` | string | ✅ | Stable locator for the text chunk (e.g., symbol key). |
| `content_sha256` | string | ✅ | Fingerprint of the normalized chunk text. |
| `model` | string | ✅ | Embedding model name (e.g., `text-embedding-3-small`). |
| `model_rev` | string | ✅ | Pinned revision of the model (e.g., `2025-09-15`). |
| `dim` | integer | ✅ | Dimensionality of the vector. |
| `created_at` | string (ISO8601) | ✅ | Timestamp of when the vector was created. |
| `language` | string | ❑ | Programming/documentation language (e.g., python, markdown, yaml). |
| `symbol` | string | ❑ | For code: fully qualified function/class name. |
| `capability_tags` | array[string] | ❑ | Associated capability tags, if any. |

---

## Configuration
All embedding-related configuration is centralized in `src/shared/config.py` and managed via environment variables, as defined in `.intent/config/runtime_requirements.yaml`.

| Setting | Purpose |
|---------|---------|
| **LOCAL_EMBEDDING_API_URL** | Endpoint URL for the embedding model service. |
| **LOCAL_EMBEDDING_API_KEY** | API key for the embedding service, if required. |
| **LOCAL_EMBEDDING_MODEL_NAME** | Defines the specific local embedding model to use. |
| **LOCAL_EMBEDDING_DIM** | Sets the output vector dimension (e.g., 768). |
| **EMBED_MODEL_REVISION** | Pins the embedding model version, enabling safe upgrades. |
| **QDRANT_URL** | Connection endpoint for the Qdrant vector store. |
| **QDRANT_COLLECTION_NAME** | Name of the Qdrant collection used to store embeddings. |

---

## Data Flow
The process of creating and storing a semantic vector is **fully governed**:

1. **Discovery** – A tool (e.g., `KnowledgeGraphBuilder`) identifies a piece of source code or a constitutional document to be embedded.  
2. **Normalization & Hashing** – The text is passed to `normalize_text`, and a `content_sha256` hash is computed.  
3. **Cache Check** – The system queries Qdrant to see if a vector already exists for this exact `content_sha256` and `EMBED_MODEL_REVISION`. If found, the process stops.  
4. **Embedding** – If new or updated, the content is sent to the `EmbeddingService` to be converted into a vector.  
5. **Validation & Upsert** – The `QdrantService` constructs a complete `EmbeddingPayload`, validates it against the schema, and upserts the vector with its full provenance payload into the collection.

---

## Summary
CORE's embedding system has evolved from a **basic prototype** into a **stable, governed, and reliable foundation for AI reasoning**.  
By enforcing **determinism**, **provenance**, and a **strict schema**, it fully aligns with the constitutional principles of:

- **safe_by_default**
- **evolvable_structure**

This foundation enables the **next phase of autonomous development**.

