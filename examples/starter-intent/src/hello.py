"""Sample module that deliberately violates the starter constitution.

The CORE audit should flag four things here:
  - greet() swallows an exception silently -> starter.no_bare_except (BLOCKING)
  - greet() has no docstring               -> starter.docstrings     (reporting)
  - greet() uses print()                   -> starter.no_print       (reporting)
  - greet() has a hardcoded credential     -> starter.no_secrets     (reporting)

Remove the violations (name the exception, add a docstring, swap print for a
logger, move the credential to an env var) and the audit goes green.
"""

from __future__ import annotations

api_key = "sk-demo-hardcoded-secret"  # planted violation for starter.no_secrets


def greet(name: str) -> str:
    print("greeting " + name)
    try:
        return f"hello, {name}"
    except Exception:
        pass
    return "hello"
