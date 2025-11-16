╔══════════════════════════════════════════════════════════════════════╗
║           CONTEXTPACKAGE INTEGRATION - EXECUTIVE SUMMARY             ║
╚══════════════════════════════════════════════════════════════════════╝

📋 WHAT IT DOES
═══════════════
Replaces raw, ungoverned LLM prompts with constitutional ContextPackages.

🎯 WHY YOU NEED IT
═══════════════════
Current State (RISKY):
  Action → "Fix this: {raw_file_content}" → LLM
           ❌ No privacy checks
           ❌ No token limits
           ❌ No audit trail
           ❌ Could leak .env files

With ContextPackages (SAFE):
  Action → ContextPackage → Validate → Redact → Audit → LLM
           ✅ Schema enforced
           ✅ Secrets blocked
           ✅ Token budgeted
           ✅ Logged to DB

🔧 WHERE TO INTEGRATE
══════════════════════
3 integration points:

1. CoreContext (src/shared/context.py)
   ├─ Add context_service property
   └─ Initialize ContextService

2. Action Services (src/features/self_healing/*.py)
   ├─ Create _v2 methods using ContextPackage
   └─ Keep old methods (backward compat)

3. Action Handlers (src/body/actions/healing_actions.py)
   ├─ Add feature flag check
   └─ Route to V1 or V2

📊 EXAMPLE: DOCSTRING FIX
══════════════════════════
BEFORE (Unsafe):
  final_prompt = template.format(source_code=file_content)
  result = await llm.make_request_async(final_prompt)

AFTER (Constitutional):
  packet = await context_service.build_for_task({
      "task_id": "DOC_FIX_001",
      "task_type": "docstring.fix",
      "roots": ["src/auth/"],
      "max_tokens": 5000,
  })
  # Packet is now validated, redacted, token-budgeted, audited
  final_prompt = template.format(source_code=file_content, context=packet)
  result = await llm.make_request_async(final_prompt)

🚀 ROLLOUT STRATEGY
════════════════════
Phase 1: Non-Breaking (Week 1)
  - Add ContextService to CoreContext
  - Create parallel V2 methods
  - Add feature flag (disabled)
  - Test with single file

Phase 2: Gradual Migration (Weeks 2-3)
  - Enable flag for docstring.fix
  - Monitor audit logs
  - Migrate header.fix
  - Migrate test.generate

Phase 3: Enforce (Week 4)
  - Make packets mandatory
  - Remove legacy methods
  - Full constitutional compliance

✅ BENEFITS
════════════
Per Action:
  docstring.fix → Blocks secret leaks
  test.generate → Prevents token overflow
  code.generate → Complete audit trail

System-Wide:
  🔒 Privacy by default (local_only)
  📊 Every LLM call logged to DB
  ⚖️ Constitutional policies enforced
  🎯 Token budgets prevent waste
  🔍 Provenance for every context

⚠️  RISK: NONE
═══════════════
- Parallel implementation (V1 + V2 coexist)
- Feature flag controls rollout
- Backward compatible
- Easy rollback

📁 FILES CREATED
═════════════════
✅ src/services/context/           (Full service)
✅ .intent/context/schema.yaml     (Structure)
✅ .intent/context/policy.yaml     (Governance)
✅ sql/2025-11-11_create_context_packets.sql
✅ tests/services/test_context_service.py (5/5 passing)
✅ docs/ContextPackage Service/

🎬 NEXT STEPS
══════════════
1. Review /tmp/CONTEXT_INTEGRATION_PLAN.md
2. Implement Step 1 (CoreContext extension)
3. Test with docstring.fix
4. Enable feature flag
5. Expand to other actions

Want me to generate the actual code for Step 1?
