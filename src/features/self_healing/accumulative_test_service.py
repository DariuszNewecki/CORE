# src/features/self_healing/accumulative_test_service.py

"""
Accumulates successful tests over time, one symbol at a time.

This REPLACES all the complex remediation services (Single/Full/Enhanced).
Strategy: Try every symbol, keep what works, accumulate gradually.

Constitutional Principles: evolvable_structure, safe_by_default
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

from features.self_healing.simple_test_generator import SimpleTestGenerator

logger = getLogger(__name__)


# ID: 4333b9d3-e1ae-432c-8395-ecf954342559
class AccumulativeTestService:
    """
    Tries to test every public symbol, keeps what works, skips what doesn't.

    No complex strategies, no retries, just accumulation.
    """

    def __init__(self, cognitive_service: CognitiveService):
        """Initialize with LLM service only."""
        self.generator = SimpleTestGenerator(cognitive_service)

    # ID: 89efba4f-4231-4a6a-bde4-f8d026628c89
    async def accumulate_tests_for_file(self, file_path: str) -> dict[str, Any]:
        """
        Generate tests for all public symbols in a file.
        Keep successful ones, skip failures.

        Args:
            file_path: Path like "src/core/foo.py"

        Returns:
            {
                "file": str,
                "total_symbols": int,
                "tests_generated": int,
                "success_rate": float,
                "test_file": Path | None,
                "successful_symbols": list[str],
                "failed_symbols": list[str]
            }
        """
        logger.info("Accumulating tests for %s", file_path)

        symbols = self._find_public_symbols(file_path)
        logger.info("Found %d public symbols", len(symbols))

        if not symbols:
            logger.warning("No public symbols to test in %s", file_path)
            return {
                "file": file_path,
                "total_symbols": 0,
                "tests_generated": 0,
                "success_rate": 0.0,
                "test_file": None,
                "successful_symbols": [],
                "failed_symbols": [],
            }

        successful_tests = []
        failed_symbols = []

        for i, symbol in enumerate(symbols, 1):
            logger.info(
                "Generating test for symbol %s (%d/%d)", symbol, i, len(symbols)
            )
            result = await self.generator.generate_test_for_symbol(
                file_path=file_path, symbol_name=symbol
            )

            if result["status"] == "success" and result["passed"]:
                successful_tests.append({"symbol": symbol, "code": result["test_code"]})
                logger.info("✓ Test generated and passed for %s", symbol)
            else:
                failed_symbols.append(symbol)
                logger.warning(
                    "✗ Failed to generate test for %s: %s", symbol, result["reason"]
                )

        test_file = None
        if successful_tests:
            test_file = self._write_test_file(file_path, successful_tests)
            success_rate = len(successful_tests) / len(symbols) * 100
            logger.info(
                "Generated %d/%d tests (%.0f%%) for %s. Saved to %s",
                len(successful_tests),
                len(symbols),
                success_rate,
                file_path,
                test_file,
            )
        else:
            logger.warning("No tests generated successfully for %s", file_path)

        return {
            "file": file_path,
            "total_symbols": len(symbols),
            "tests_generated": len(successful_tests),
            "success_rate": len(successful_tests) / len(symbols) if symbols else 0.0,
            "test_file": test_file,
            "successful_symbols": [t["symbol"] for t in successful_tests],
            "failed_symbols": failed_symbols,
        }

    def _find_public_symbols(self, file_path: str) -> list[str]:
        """Find all public (non-private) functions and classes."""
        try:
            full_path = settings.REPO_PATH / file_path
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            symbols = []
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if not node.name.startswith("_"):
                        symbols.append(node.name)
            return symbols
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return []

    def _write_test_file(self, source_file: str, successful_tests: list[dict]) -> Path:
        """
        Combine successful tests into a single test file.

        Strategy: Mirror source structure in tests/
        src/core/foo.py -> tests/core/test_foo.py
        """
        source_path = Path(source_file)
        if "src/" in str(source_path):
            rel_path = str(source_path).split("src/", 1)[1]
        else:
            rel_path = source_path.name
        module_parts = Path(rel_path).parts
        if len(module_parts) > 1:
            test_dir = Path("tests") / Path(*module_parts[:-1])
        else:
            test_dir = Path("tests")
        test_file_name = f"test_{source_path.stem}.py"
        test_file_path = test_dir / test_file_name
        test_file_path.parent.mkdir(parents=True, exist_ok=True)
        module_name = rel_path.replace("/", ".").replace(".py", "")
        header = f"# Auto-generated tests for {source_file}\n# Generated by CORE SimpleTestGenerator\n# Coverage: {len(successful_tests)} symbols\n\nimport pytest\nfrom unittest.mock import MagicMock, AsyncMock, patch\n\n# Import from source module\ntry:\n    from {module_name} import *\nexcept ImportError:\n    # Fallback if import fails\n    pass\n\n"
        test_functions = "\n\n".join([test["code"] for test in successful_tests])
        content = header + test_functions + "\n"
        test_file_path.write_text(content, encoding="utf-8")
        return test_file_path
