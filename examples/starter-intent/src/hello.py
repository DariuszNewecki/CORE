"""Sample module that deliberately violates the starter constitution.

The CORE audit should flag four things here:
  - greet() has no `# ID:` anchor          -> starter.symbol_ids   (BLOCKING)
  - greet() has no docstring               -> starter.docstrings   (reporting)
  - greet() uses print()                   -> starter.no_print     (reporting)
  - greet() swallows an exception silently -> starter.no_bare_except(reporting)

Remove the violations (add a `# ID:` anchor + docstring, swap print for a
logger, name the exception) and the audit goes green.
"""

from __future__ import annotations


def greet(name: str) -> str:
    print("greeting " + name)
    try:
        return f"hello, {name}"
    except Exception:
        pass
    return "hello"
