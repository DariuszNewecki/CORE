# 10. API Reference

This document provides the formal, machine-readable specification for CORE's internal API. It is intended for use by both human operators and external AI systems that need to interact with CORE in a governed, predictable manner.

All endpoints are hosted under the main FastAPI application defined in `src/core/main.py`.

---

## 1. Governance Endpoints

These endpoints provide mechanisms for constitutional alignment and safety checks.

### `POST /guard/align`

Evaluates a high-level goal against the project's constitutional `northstar.yaml` and an optional `blocked_topics.txt` to ensure alignment before committing resources to a development cycle.

-   **Request Body:**
    ```json
    {
      "goal": "A string describing the high-level objective.",
      "min_coverage": 0.25
    }
    ```
-   **Success Response (200 OK):**
    ```json
    {
      "status": "ok",
      "details": {
        "coverage": 0.85,
        "violations": []
      }
    }
    ```
-   **Failure Response (200 OK):**
    ```json
    {
      "status": "rejected",
      "details": {
        "coverage": 0.05,
        "violations": [
          "low_mission_overlap"
        ]
      }
    }
    ```

---

## 2. Knowledge Endpoints

These endpoints provide read-only access to the system's `KnowledgeGraph`.

### `GET /knowledge/capabilities`

Returns a complete, sorted list of all unique capability keys that are declared in the constitution and implemented in the codebase.

-   **Request Body:** None
-   **Success Response (200 OK):**
    ```json
    {
      "capabilities": [
        "agent.capability_tagger.apply_tags",
        "agent.capability_tagger.initialize",
        "audit.check.architecture_integrity",
        "...etc"
      ]
    }
    ```

---

## 3. Execution Endpoints

These endpoints trigger CORE's autonomous development and reasoning cycles.

### `POST /execute_goal`

The primary entry point for CORE's autonomous operation. This endpoint takes a high-level goal, orchestrates the entire "reconnaissance -> plan -> execute" cycle, and applies the resulting changes to the codebase.

-   **Request Body:**
    ```json
    {
      "goal": "Refactor the GitService to improve its error handling for commit failures."
    }
    ```
-   **Success Response (200 OK):**
    ```json
    {
      "status": "success",
      "message": "✅ Plan executed successfully."
    }
    ```
-   **Failure Response (500 Internal Server Error):**
    ```json
    {
      "error": "internal_server_error",
      "detail": "Plan execution failed: [Reason for failure]"
    }
    ```

---

## 4. System Endpoints

### `GET /`

The root endpoint. Returns a simple status message indicating that the CORE system is online and operational.

-   **Request Body:** None
-   **Success Response (200 OK):**
    ```json
    {
      "message": "CORE system is online and self-governing."
    }
    ```
