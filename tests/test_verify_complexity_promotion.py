# tests/test_verify_complexity_promotion.py
import asyncio

from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from will.self_healing.complexity_service import ComplexityRemediationService


async def verify_promotion():
    # 1. Setup the Environment
    core_context = create_core_context(service_registry)

    print("🧠 Ignition: Waking up the Cognitive Services...")

    # 2. CONSTITUTIONAL INITIALIZATION (Simulating @core_command)
    # We must provide a session so the CognitiveService can read its
    # LLM configuration from the database.
    async with service_registry.session() as session:
        # Request the service from the registry
        cog = await service_registry.get_cognitive_service()
        # Initialize it (this loads LLM_ENABLED, API keys, etc. from DB)
        await cog.initialize(session)

        # Manually attach to context for this standalone run
        core_context.cognitive_service = cog
        core_context.auditor_context = await service_registry.get_auditor_context()
        core_context.qdrant_service = await service_registry.get_qdrant_service()

    # 3. Instantiate and Run the Promoted Service
    service = ComplexityRemediationService(core_context)

    target_file = (
        core_context.git_service.repo_path / "src/shared/utils/text_cleaner.py"
    )

    print(f"🧐 Verifying Promoted Orchestrator on: {target_file.name}")

    try:
        # Dry-Run Execution
        success = await service.remediate(target_file, write=False)

        if success:
            print("\n✅ VERIFICATION PASSED: Service generated a validated blueprint.")
        else:
            print(
                "\n❌ VERIFICATION FAILED: Complexity reduction not achieved or Gate violated."
            )
    except Exception as e:
        print(f"\n💥 CRASH DETECTED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(verify_promotion())
