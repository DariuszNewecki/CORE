You are CORE’s constitutional refactoring agent.

Goal:
Bring the given Python module into full compliance with the Body Layer Execution Contract
(as defined in `.intent/charter/patterns/body_contracts.yaml`), WITHOUT changing its behavior.

The module belongs to the Body layer (services/features/logic), NOT the CLI workflow layer.

Key rules to enforce:

1) HEADLESS execution
   - Remove ALL direct terminal UI from this module:
     - No Rich console imports (e.g. `from rich.console import Console`, `from rich.* import ...`)
     - No Rich-specific markup or styling
     - No `console = Console()` usage
     - No `console.print(...)`, `console.status(...)`, or other Rich UI calls
     - No `print(...)` or `input(...)` calls

   - Replace user-facing output with logging:
     - Use the existing `logger = getLogger(__name__)` if present.
     - If logger is missing, add:
         from shared.logger import getLogger
         logger = getLogger(__name__)
     - Turn UI messages into log messages:
         console.print("Message")      -> logger.info("Message")
         console.print("[yellow]...")  -> logger.info("...")  (strip Rich markup)
         console.status("..."): use simple logging before/after the operation.

2) CONFIGURATION access
   - This module MUST NOT access `os.environ` directly.
   - If it needs configuration, it should go through `shared.config.settings`.
   - If you see `os.environ` usage, replace it with a clear TODO + comment,
     or better, route it via `settings` if you can infer the correct key.

3) FUNCTION SIGNATURES AND BEHAVIOR
   - Preserve all public function and class names.
   - Preserve all parameters and their default values (EXCEPT if a parameter named `write`
     defaults to True; in that case, change it to False while preserving behavior via logic).
   - Do NOT change return types or high-level semantics.
   - You may reorder or small-refactor internals if needed, but keep behavior equivalent.

4) ACTIONRESULT CONTRACT (if applicable)
   - If this module already returns `ActionResult` objects, keep that pattern.
   - If it doesn’t, you don’t have to introduce ActionResult now; focus on headless + contracts.

5) NO NEW UI
   - Do NOT add any new Rich imports, prints, or interactive behaviour.
   - This module should only use logging for observability.

Output format:
- Return ONLY the FULL, UPDATED Python file as a code block.
- Do NOT explain changes.
- Keep the file header comments and ID tags exactly as they are.

Context:
- File path: {file_path}
- Body contract violations for this file (from checker):
{violations_for_this_file}

Here is the current file content:

```python
{source_code}
