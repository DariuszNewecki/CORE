# ContextPackage Integration Plan

## Current State Analysis

**Where LLM calls happen:**
1. **LLMClient** (`src/services/llm/client.py`) - Low-level provider wrapper
2. **CognitiveService** (`src/will/orchestration/cognitive_service.py`) - Role-based client factory
3. **Action Services** (e.g., `src/features/self_healing/docstring_service.py`) - Direct LLM calls

**Current Flow (Docstring Fix Example):**
```
FixDocstringsHandler
    ↓
_async_fix_docstrings()
    ↓
writer_client.make_request_async(prompt)  ← RAW PROMPT, NO GOVERNANCE
    ↓
LLMClient._request_with_retry()
    ↓
provider.chat_completion()
```

**Problems:**
- ❌ Raw prompts with unstructured context
- ❌ No privacy checks (could leak secrets)
- ❌ No token budgets (could overflow)
- ❌ No audit trail (what context was used?)
- ❌ No constitutional compliance

---

## Integration Strategy

### Phase 1: Non-Breaking (Add Parallel Path)

**Goal:** Add ContextService alongside existing code, don't break anything.

**Changes:**
1. **Add ContextService to CoreContext** (`src/shared/context.py`)
2. **Create context-aware wrapper methods** in action services
3. **Keep existing methods working** (backward compatibility)

### Phase 2: Migrate Actions One-by-One

**Goal:** Gradually migrate actions to use ContextPackage.

**Priority Order:**
1. `docstring.fix` (simple, well-scoped)
2. `header.fix` (similar to docstring)
3. `test.generate` (more complex, higher value)
4. Code generation (highest risk, most benefit)

### Phase 3: Enforce at LLMClient Level

**Goal:** Make context packets mandatory.

**Changes:**
1. Add `context_packet` parameter to `LLMClient.make_request_async()`
2. Reject calls without valid packet
3. Remove old prompt-based methods

---

## Detailed Implementation

### Step 1: Extend CoreContext

**File:** `src/shared/context.py`

```python
# Add to CoreContext class
from src.services.context import ContextService

class CoreContext:
    def __init__(self, ...):
        # ... existing code ...
        self._context_service: ContextService | None = None

    @property
    async def context_service(self) -> ContextService:
        """Get or create ContextService instance."""
        if not self._context_service:
            db_service = await self.database_service  # Your existing DB service
            qdrant = self.cognitive_service.qdrant_service

            self._context_service = ContextService(
                db_service=db_service,
                qdrant_client=qdrant,
                config={},
                project_root=str(settings.REPO_PATH),
            )

        return self._context_service
```

### Step 2: Create Context-Aware Docstring Service

**File:** `src/features/self_healing/docstring_service.py`

```python
async def _async_fix_docstrings_v2(context: CoreContext, dry_run: bool):
    """
    V2: Uses ContextPackage for constitutional governance.

    Differences from V1:
    - Builds governed context packet
    - Enforces privacy policies
    - Logs to audit trail
    - Token-budgeted
    """
    log.info("🔍 [V2] Searching for symbols with ContextPackage...")

    knowledge_service = context.knowledge_service
    graph = await knowledge_service.get_graph()
    symbols = graph.get("symbols", {})

    symbols_to_fix = [
        s for s in symbols.values()
        if not s.get("docstring")
        and s.get("type") in ["FunctionDef", "AsyncFunctionDef"]
    ]

    if not symbols_to_fix:
        log.info("✅ No symbols missing docstrings")
        return

    log.info(f"Found {len(symbols_to_fix)} symbols to fix")

    # === NEW: Build ContextPackage ===
    context_service = await context.context_service

    for symbol in track(symbols_to_fix, description="Fixing docstrings..."):
        try:
            # Build governed context packet for this symbol
            task_spec = {
                "task_id": f"DOC_FIX_{symbol['uuid']}",
                "task_type": "docstring.fix",
                "summary": f"Fix docstring for {symbol['symbol_path']}",
                "roots": [str(Path(symbol['file_path']).parent)],
                "include": [symbol['file_path']],
                "max_tokens": 5000,  # Small task
                "max_items": 5,
            }

            packet = await context_service.build_for_task(task_spec)

            # === Packet is now:
            # - Validated (schema compliant)
            # - Redacted (no secrets)
            # - Token-budgeted
            # - Audited (logged to DB)
            # ===

            # Get LLM client
            cognitive_service = context.cognitive_service
            writer_client = await cognitive_service.aget_client_for_role("DocstringWriter")

            # Load prompt template
            prompt_template = (settings.MIND / "prompts" / "fix_function_docstring.prompt").read_text()

            # Build prompt WITH context packet
            source_code = extract_source_code(settings.REPO_PATH, symbol)
            final_prompt = prompt_template.format(
                source_code=source_code,
                context=packet  # Include governed context
            )

            # Make governed LLM call
            new_docstring = await writer_client.make_request_async(
                final_prompt,
                user_id="docstring_writer_v2"
            )

            # ... rest of the logic (apply docstring) ...

        except Exception as e:
            log.error(f"Failed to fix {symbol['symbol_path']}: {e}")
```

### Step 3: Add Feature Flag

**File:** `.intent/charter/policies/operations.yaml`

```yaml
# Add to feature flags
feature_flags:
  use_context_packages:
    enabled: false  # Start disabled
    description: "Use ContextPackage for LLM calls (Phase 1 rollout)"
    applies_to:
      - "docstring.fix"
      - "header.fix"
```

### Step 4: Update Action Handler

**File:** `src/body/actions/healing_actions.py`

```python
class FixDocstringsHandler(ActionHandler):
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Execute with optional ContextPackage."""

        # Check feature flag
        use_context_packages = await context.config_service.get(
            "feature_flags.use_context_packages.enabled"
        )

        if use_context_packages:
            log.info("Using ContextPackage (V2)")
            await _async_fix_docstrings_v2(context, dry_run=False)
        else:
            log.info("Using legacy prompt (V1)")
            await _async_fix_docstrings(context, dry_run=False)
```

---

## Benefits Per Action

### Docstring Fix
- **Before**: Raw file contents in prompt → could leak secrets
- **After**: Governed context with redaction → secrets blocked

### Test Generation
- **Before**: Entire codebase in context → token overflow
- **After**: Smart scope selection → only relevant symbols

### Code Generation
- **Before**: No audit trail of what context was used
- **After**: Every packet logged with provenance

---

## Rollout Plan

**Week 1:**
- ✅ Add ContextService to CoreContext
- ✅ Create `_async_fix_docstrings_v2()`
- ✅ Add feature flag
- ✅ Test with single file: `python -m core_admin docstring fix --use-context-packages`

**Week 2:**
- Enable flag for docstring.fix in production
- Monitor audit logs for redactions
- Verify token budgets working

**Week 3:**
- Migrate header.fix
- Migrate test.generate

**Week 4:**
- Enforce at LLMClient level
- Remove legacy methods
- Full constitutional compliance

---

## Testing Strategy

```python
# Test file: tests/services/test_context_integration.py

@pytest.mark.asyncio
async def test_docstring_fix_uses_context_package():
    """Verify docstring fix creates and uses context packet."""

    context = await create_test_context()

    # Mock symbol
    symbol = {
        "uuid": "test-123",
        "symbol_path": "test.func",
        "file_path": "src/test.py",
        "type": "FunctionDef",
    }

    # Run V2
    await _async_fix_docstrings_v2(context, dry_run=True)

    # Verify packet was created
    packets = await context.context_service.database.get_packets_for_task("DOC_FIX_test-123")
    assert len(packets) == 1

    packet = packets[0]
    assert packet["task_type"] == "docstring.fix"
    assert packet["privacy"] == "local_only"
    assert packet["policy"]["remote_allowed"] is False
```

---

## Constitutional Compliance

**Before Integration:**
```
Action → Raw Prompt → LLM
(No governance, no audit, no safety)
```

**After Integration:**
```
Action → ContextPackage → Validation → Redaction → LLM
         (Schema)          (Token budget)  (Privacy)
                                ↓
                           Audit Log (DB)
```

Every LLM call now:
- ✅ Enforces Mind-layer policies
- ✅ Blocks forbidden content
- ✅ Respects token budgets
- ✅ Logs complete provenance
- ✅ Privacy-by-default

---

## Next Steps

1. **Review this plan** - Does it fit CORE's architecture?
2. **Create feature branch** - `feature/context-package-integration`
3. **Implement Step 1** - Extend CoreContext
4. **Test with docstring.fix** - Single action as proof-of-concept
5. **Expand gradually** - One action at a time

Would you like me to:
1. Create the actual code files for Step 1?
2. Write the integration tests?
3. Update the autonomy loop documentation?
