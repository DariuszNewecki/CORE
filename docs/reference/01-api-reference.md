# API Reference

This document provides the **public API reference** for CORE.
It describes only what is actually implemented in the current 2025 codebase under `src/api/`.

CORE intentionally exposes a **minimal HTTP surface**.
Most functionality is accessed through the CLI (`core-admin`) rather than HTTP.

---

# 1. Overview

CORE exposes two primary API groups:

* **Development Routes** — internal diagnostic/introspection endpoints
* **Knowledge Routes** — access to Knowledge Graph data (symbols, capabilities)

These routes live under:

```
src/api/v1/development_routes.py
src/api/v1/knowledge_routes.py
```

The root application is defined in:

```
src/api/main.py
```

---

# 2. Base URL

All endpoints are mounted under:

```
/api/v1
```

Example:

```
GET /api/v1/status
```

---

# 3. Development Routes

Located in: `src/api/v1/development_routes.py`

These endpoints support:

* debug information
* development-mode diagnostics
* environment checks
* version + health metadata

## 3.1. `GET /api/v1/status`

Returns a basic health status for the API.

**Response:**

```json
{
  "status": "ok",
  "version": "v0.2.0"
}
```

---

## 3.2. `GET /api/v1/environment`

Returns environment/debug metadata.

Used internally for troubleshooting.

**Note:** Does not expose secrets.

---

## 3.3. `GET /api/v1/config`

Returns selected configuration metadata loaded from `settings`.

Useful to confirm whether the environment has been initialized correctly.

---

# 4. Knowledge Routes

Located in: `src/api/v1/knowledge_routes.py`

These endpoints provide a read-only interface to the Knowledge Graph.

### Important:

These APIs **do not modify knowledge**.
Modification is handled by CLI and internal services.

---

## 4.1. `GET /api/v1/knowledge/symbols`

Returns indexed symbols.

**Example response:**

```json
[
  {
    "symbol": "ContextBuilder.build",
    "path": "src/services/context/builder.py",
    "domain": "context"
  }
]
```

---

## 4.2. `GET /api/v1/knowledge/capabilities`

Returns known capabilities extracted from the codebase.

**Example response:**

```json
[
  {
    "id": "cap.context.build",
    "symbol": "ContextBuilder.build",
    "file": "src/services/context/builder.py"
  }
]
```

---

# 5. Error Handling

Errors follow FastAPI's standard model.

Typical error responses:

## 5.1. 400 — Bad Request

Example:

```json
{
  "detail": "Invalid parameter"
}
```

## 5.2. 404 — Not Found

Example:

```json
{
  "detail": "Not Found"
}
```

## 5.3. 500 — Internal Error

Returned when backend services fail.

---

# 6. Authentication

Currently **no authentication layer** is implemented.
APIs are designed for:

* local development,
* debugging,
* internal tooling.

Production deployments should place the API behind:

* a reverse proxy,
* authentication middleware,
* or local-only access.

---

# 7. Versioning

All endpoints live under `/api/v1`.

Future versions will extend:

* `/api/v2/introspection`
* `/api/v2/knowledge`
* `/api/v2/governance`

without breaking existing clients.

---

# 8. Summary

This API surface is intentionally small and stable.
CORE's power lives in its **CLI**, **audits**, **Knowledge Graph**, and **governed autonomy pipeline**, not in HTTP endpoints.

Use these APIs for:

* environment health
* read-only knowledge access
* tooling integrations

For everything else, use:

```
poetry run core-admin <command>
```
