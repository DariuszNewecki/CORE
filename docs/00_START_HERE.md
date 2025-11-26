# START HERE — The Plain-Language Introduction

This page gives you a **crystal-clear, beginner-friendly explanation** of what CORE is, why it exists, and what it *actually does* to AI‑generated code.

No jargon. No theory. Just reality.

---

## 🚀 What CORE Is (10-second version)

**CORE is not another agent.**

CORE is the **safety layer** that makes sure Claude, Gemini, or any AI coder **doesn’t damage your codebase**.

It acts as a governance shield around your repository:

* stops architectural drift
* prevents touching unrelated files
* enforces naming & structure rules
* adds docstrings, IDs, headers
* auto-corrects mistakes
* runs tests and blocks regressions
* only allows *safe, clean, validated* code through

If you use AI to write code, you need something like CORE.

---

## 🧠 Why CORE Exists

Autonomous coding is now good enough to:

* write features
* refactor modules
* generate tests
* fix bugs

…but also careless enough to:

* delete tests to “make CI green”
* drop files into random directories
* ignore your architecture
* introduce regressions silently
* create global state or custom patterns that break everything later

Without guardrails, AI coding is **fast chaos**.

CORE turns it into **fast order**.

---

## 🧩 The Real "Ah‑ha" Moment (Before/After)

A real example.
A real transformation.
No theory.

---

# ❌ BEFORE CORE

> Request to AI: *"Add a health endpoint with simple rate limiting."*

The model generates something that *works*, but is full of landmines:

```python
# randomly dropped into main.py

import time
last = 0

def health():
    now = time.time()
    global last
    if now - last < 0.1:
        return {"status": "error", "reason": "too many calls"}
    last = now
    return {"status": "ok"}
```

Problems:

* ❌ wrong file location
* ❌ global state
* ❌ no typing
* ❌ no docstring, no purpose
* ❌ no architecture boundaries
* ❌ error handling by magic dicts
* ❌ no test generated
* ❌ no header, no ID, no structure

This is *extremely common* with raw AI coding.

---

# ✅ AFTER CORE

> Same request — but everything goes through CORE’s governance pipeline.

```python
# src/api/routes/health.py
"""
Health check endpoint with simple in-memory rate limiting.
Exposed as GET /health.
"""

from __future__ import annotations

import time
from fastapi import APIRouter, Depends

# ID: 4f9d3e9b-2e7a-4c7b-9e1c-a3e2f5c123ab

router = APIRouter()


class RateLimiter:
    """Naive in-memory rate limiter for demo purposes."""

    def __init__(self) -> None:
        self._last_call_ts: float = 0.0

    def allow(self, min_interval: float = 0.1) -> None:
        now = time.time()
        if now - self._last_call_ts < min_interval:
            raise RuntimeError("Rate limit exceeded")
        self._last_call_ts = now


def get_rate_limiter() -> RateLimiter:
    return RateLimiter()


@router.get("/health", summary="Health check with basic rate limiting")
def health_check(limiter: RateLimiter = Depends(get_rate_limiter)) -> dict[str, str]:
    """Return service health status.

    Raises:
        RuntimeError: If the endpoint is called too frequently.
    """
    limiter.allow()
    return {"status": "ok"}
```

CORE enforced:

* ✅ correct file location (`src/api/routes/...`)
* ✅ mandatory file header
* ✅ docstring
* ✅ unique governance ID
* ✅ dependency injection instead of globals
* ✅ typed function signatures
* ✅ consistent API structure
* ✅ described error behaviour
* ✅ proper imports + architecture boundaries

And CORE also generated the **tests**:

```python
# tests/api/test_health.py
from fastapi.testclient import TestClient
from api.app import app

def test_health_ok():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
```

---

## 🧱 The Mental Model (Simple But Accurate)

```
MIND  — rules, constitution, governance, knowledge
BODY  — auditors, validators, crate sandbox, test engine
WILL  — AI agents creating proposals
```

The AI tries to make changes → the BODY tests & audits them → the MIND decides.

Unsafe changes simply never reach your repository.

---

## 🔍 What CORE Guarantees

* Architecture is protected
* Naming rules always apply
* No ghost files or global state
* Tests can’t be removed
* Changes are traceable
* You get docstrings, headers, IDs for free
* Everything is reviewed before touching your main repo

This is why CORE is so valuable in the post‑Claude‑Opus world.

---

## 📍 Where to Go Next

* **What is CORE?** — deeper conceptual overview
* **Worked Example** — full end‑to‑end feature build
* **CLI Cheat Sheet** — all commands in one place
* **Constitution** — the rules that govern the AI

---

## 🎯 Final Message

Autonomous coding is here.
But without guardrails, it’s unpredictable and unsafe.

CORE gives you:

* safety
* predictability
* structure
* traceability
* trust in AI‑generated code

**This is how we build safe autonomous software.**
