# src/features/self_healing/test_context_analyzer.py

"""
Analyzes target modules to build rich context for test generation.
Refactored for High Fidelity (V2.3).
"""

from __future__ import annotations

import ast

from shared.config import settings
from shared.logger import getLogger

from .test_context import detectors, examples, metrics, parsers
from .test_context.models import ModuleContext


logger = getLogger(__name__)


# ID: d3ee69df-00b1-4ac4-bfb9-9f559007e7db
class TestContextAnalyzer:
    """Analyzes modules to gather rich context for test generation."""

    __test__ = False

    def __init__(self):
        self.repo_root = settings.REPO_PATH

    # ID: 195772da-8fff-4360-a6f8-362d5e1156e5
    async def analyze_module(self, module_path: str) -> ModuleContext:
        logger.info("Analyzing module: %s", module_path)
        full_path = self.repo_root / module_path
        if not full_path.exists():
            raise FileNotFoundError(f"Module not found: {full_path}")

        source_code = full_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            logger.error("Failed to parse %s: %s", module_path, e)
            raise

        cls_list = parsers.extract_classes(tree)
        fn_list = parsers.extract_functions(tree)
        imp_list = parsers.extract_imports(tree)

        cov_info = metrics.get_coverage_data(self.repo_root, module_path)
        sim_tests = examples.find_similar_tests(
            self.repo_root, full_path.stem, cls_list, fn_list
        )

        return ModuleContext(
            module_path=module_path,
            module_name=full_path.stem,
            import_path=module_path.replace("src/", "")
            .replace(".py", "")
            .replace("/", "."),
            source_code=source_code,
            module_docstring=ast.get_docstring(tree),
            classes=cls_list,
            functions=fn_list,
            imports=imp_list,
            dependencies=detectors.analyze_dependencies(imp_list),
            current_coverage=cov_info["coverage"],
            uncovered_lines=cov_info["uncovered_lines"],
            uncovered_functions=cov_info["uncovered_functions"],
            similar_test_files=sim_tests,
            external_deps=detectors.identify_external_deps(imp_list),
            filesystem_usage=detectors.detect_fs_usage(source_code),
            database_usage=detectors.detect_db_usage(source_code),
            network_usage=detectors.detect_network_usage(source_code),
        )


# Ensure the type is exported for external modules
__all__ = ["ModuleContext", "TestContextAnalyzer"]
