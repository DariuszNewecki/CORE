#!/usr/bin/env python3
"""
AI-Powered Test Scavenger - Uses local LLM to repair failed tests

Leverages CORE's CognitiveService with local Qwen to intelligently fix
test failures through pattern recognition and code understanding.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Tuple

# Add CORE to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)

FAILURES_DIR = Path("work/testing/failures")
REPAIRED_DIR = Path("work/testing/repaired")
PROMOTED_DIR = Path("tests/scavenged")


REPAIR_PROMPT_TEMPLATE = """You are a test repair specialist. Fix this failing Python test.

# TEST FILE
```python
{test_code}
```

# ERROR OUTPUT
```
{error_text}
```

# COMMON FIXES
1. **Import errors for properties**: Change `from module import property_name` to `from module import ClassName`, then instantiate class
2. **Nested functions**: If importing nested function like 'wrapper' or 'decorator', mark test with `@pytest.mark.skip`
3. **Path double-extension**: Fix `.prompt.prompt` → `.prompt`
4. **Mock assertions**: Remove `assert_called` if mocks aren't actually used
5. **Missing imports**: Add `import pytest` if using `@pytest.mark`

# RULES
- Return ONLY the corrected Python code
- NO markdown backticks, NO explanations
- Start with imports, end with test function
- Keep test logic intact, only fix technical issues
- If unfixable, return the original code with `@pytest.mark.skip(reason='...')`

# CORRECTED TEST CODE
"""


class AITestScavenger:
    """Uses AI to repair failed tests."""

    def __init__(self, cognitive_service: CognitiveService):
        self.cognitive = cognitive_service
        self.stats = {
            "total": 0,
            "repaired": 0,
            "partial": 0,
            "unfixable": 0,
            "skipped": 0
        }

    async def repair_test(self, test_file: Path) -> Tuple[bool, str, str]:
        """
        Attempt to repair a single test using AI.

        Returns:
            (success, status_message, repaired_code)
        """
        error_file = test_file.with_suffix('.error.txt')

        if not error_file.exists():
            return False, "No error file", ""

        try:
            # Read test and error
            test_code = test_file.read_text()
            error_text = error_file.read_text()

            # Build prompt
            prompt = REPAIR_PROMPT_TEMPLATE.format(
                test_code=test_code,
                error_text=error_text
            )

            # Call local LLM (Qwen)
            logger.info(f"Repairing {test_file.name} with AI...")
            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(
                prompt,
                user_id="test_scavenger"
            )

            # Extract code from response
            repaired_code = self._extract_code(response)

            if not repaired_code or len(repaired_code) < 50:
                return False, "AI returned invalid code", ""

            # Check if AI marked it as skipped
            if "@pytest.mark.skip" in repaired_code and "@pytest.mark.skip" not in test_code:
                self.stats["skipped"] += 1
                return False, "AI marked as unfixable (skipped)", repaired_code

            return True, "Repaired by AI", repaired_code

        except Exception as e:
            logger.error(f"Failed to repair {test_file.name}: {e}")
            return False, f"AI repair failed: {e}", ""

    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response."""
        # Remove markdown code fences if present
        code = response.strip()

        # Remove ```python or ``` markers
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]

        if code.endswith("```"):
            code = code[:-3]

        return code.strip()

    async def validate_repair(self, test_file: Path, repaired_code: str) -> Tuple[bool, str]:
        """
        Validate repaired test by running it.

        Returns:
            (passed, error_message)
        """
        # Write to repaired directory
        REPAIRED_DIR.mkdir(parents=True, exist_ok=True)
        repaired_path = REPAIRED_DIR / test_file.name
        repaired_path.write_text(repaired_code)

        # Run pytest on it
        try:
            import subprocess
            result = subprocess.run(
                ["pytest", str(repaired_path), "-v", "--tb=short", "-x"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=REPO_ROOT
            )

            if result.returncode == 0:
                return True, "PASSED"
            else:
                # Extract error for potential re-repair
                output = result.stdout + result.stderr
                if "FAILED" in output:
                    return False, "Still failing after repair"
                elif "ERROR" in output:
                    return False, "Import/syntax error in repair"
                else:
                    return False, "Unknown test failure"

        except subprocess.TimeoutExpired:
            return False, "Test timed out"
        except Exception as e:
            return False, f"Validation error: {e}"

    async def scavenge_all(self, max_repairs: int = None, validate: bool = True) -> Dict:
        """
        Repair all failed tests in the failures directory.

        Args:
            max_repairs: Maximum number of tests to repair (None = all)
            validate: Whether to run tests to validate repairs
        """
        if not FAILURES_DIR.exists():
            logger.error(f"Failures directory not found: {FAILURES_DIR}")
            return self.stats

        test_files = list(FAILURES_DIR.glob("test_*.py"))
        if max_repairs:
            test_files = test_files[:max_repairs]

        self.stats["total"] = len(test_files)

        print(f"🔍 Found {len(test_files)} failed tests")
        print(f"🤖 Using AI-powered repair (local Qwen)\n")

        results = []

        for i, test_file in enumerate(test_files, 1):
            print(f"[{i}/{len(test_files)}] {test_file.name}...", end=" ", flush=True)

            # Repair with AI
            success, message, repaired_code = await self.repair_test(test_file)

            if not success or not repaired_code:
                print(f"❌ {message}")
                self.stats["unfixable"] += 1
                results.append(("❌", test_file.name, message))
                continue

            # Validate if requested
            if validate:
                passed, validation_msg = await self.validate_repair(test_file, repaired_code)

                if passed:
                    print(f"✅ {validation_msg}")
                    self.stats["repaired"] += 1
                    results.append(("✅", test_file.name, validation_msg))

                    # Save to promoted directory
                    PROMOTED_DIR.mkdir(parents=True, exist_ok=True)
                    promoted_path = PROMOTED_DIR / test_file.name
                    promoted_path.write_text(repaired_code)
                else:
                    print(f"⚠️  {validation_msg}")
                    self.stats["partial"] += 1
                    results.append(("⚠️", test_file.name, validation_msg))
            else:
                # Just save without validation
                print(f"✅ Repaired (not validated)")
                self.stats["repaired"] += 1
                results.append(("✅", test_file.name, "Repaired (not validated)"))

        # Print summary
        self._print_summary(results)

        return self.stats

    def _print_summary(self, results: list):
        """Print detailed summary of scavenging results."""
        print("\n" + "="*80)
        print("AI SCAVENGER RESULTS")
        print("="*80)
        print(f"Total tests:       {self.stats['total']}")
        print(f"✅ Fully repaired:  {self.stats['repaired']} ({self.stats['repaired']/max(1,self.stats['total'])*100:.1f}%)")
        print(f"⚠️  Partially fixed: {self.stats['partial']} ({self.stats['partial']/max(1,self.stats['total'])*100:.1f}%)")
        print(f"❌ Unfixable:       {self.stats['unfixable']} ({self.stats['unfixable']/max(1,self.stats['total'])*100:.1f}%)")
        print(f"⏭️  Skipped:         {self.stats['skipped']} (AI marked as unfixable)")

        # Show successes
        successes = [r for r in results if r[0] == "✅"]
        if successes:
            print(f"\n✅ SUCCESSFULLY REPAIRED ({len(successes)}):")
            for _, name, _ in successes[:20]:
                print(f"   {name}")

        # Show partials
        partials = [r for r in results if r[0] == "⚠️"]
        if partials:
            print(f"\n⚠️  PARTIALLY FIXED ({len(partials)} - showing first 10):")
            for _, name, msg in partials[:10]:
                print(f"   {name}: {msg}")

        # Next steps
        if self.stats["repaired"] > 0:
            print(f"\n" + "="*80)
            print("NEXT STEPS")
            print("="*80)
            print(f"✨ {self.stats['repaired']} tests ready to promote!")
            print(f"\nPromoted tests saved to: {PROMOTED_DIR}")
            print(f"\nTo add to test suite:")
            print(f"   cp {PROMOTED_DIR}/*.py tests/")
            print(f"\nOr run all promoted tests:")
            print(f"   pytest {PROMOTED_DIR}/ -v")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="AI-powered test scavenger")
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of tests to repair (default: all)"
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip test validation (faster, but less accurate)"
    )
    args = parser.parse_args()

    # Initialize cognitive service
    print("🧠 Initializing AI services...")
    cognitive = CognitiveService(repo_path=REPO_ROOT)
    await cognitive.initialize()

    # Run scavenger
    scavenger = AITestScavenger(cognitive)
    await scavenger.scavenge_all(
        max_repairs=args.limit,
        validate=not args.no_validate
    )


if __name__ == "__main__":
    asyncio.run(main())
