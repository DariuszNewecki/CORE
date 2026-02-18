# src/features/maintenance/apply_provider_refactoring.py

"""
Automated Provider Refactoring - Apply Changes

Applies automated refactorings for high-confidence cases identified by analysis.
This script handles the 29 files that can be safely automated:
- IntentRepository pattern: 12 files
- Repo path parameter: 17 files

SAFETY: Only applies changes to files marked as high-confidence by analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 701fbb96-5241-4c2d-981b-974c3f941e43
class RefactoringAction:
    """A specific refactoring action to apply."""

    file_path: Path
    action_type: str  # 'intent_repository', 'repo_path_param'
    original_content: str
    refactored_content: str
    changes_made: list[str]


# ID: a1b2c3d4-e5f6-7890-1234-567890abcdef
class ProviderRefactoringApplicator:
    """Applies provider refactoring to files."""

    def __init__(self, repo_path: Path, file_handler: FileHandler):
        self.repo_path = repo_path
        self.file_handler = file_handler

    # ID: e8d3a04b-c235-460d-a04c-40648f5e441f
    def refactor_to_intent_repository(self, file_path: Path) -> RefactoringAction:
        """
                Refactor file to use IntentRepository instead of settings.

                Changes:
        # REFACTORED: Removed direct settings import
                2. Add: from shared.infrastructure.intent.intent_repository import IntentRepository, get_intent_repository
                3. Add parameter: intent_repository: IntentRepository | None = None
                4. Add assignment: self.intent_repo = intent_repository or get_intent_repository()
                5. Replace: context.path_resolver.intent_root → self.intent_repo.root
                6. Replace: context.context.settings.load(...) → self.intent_repo.load_policy(...)
                7. Replace: context.context.context.context.settings.get_path(...) → self.intent_repo methods
        """
        original = file_path.read_text()
        lines = original.splitlines()
        changes = []

        # Step 1: Remove settings import
        new_lines = []
        for i, line in enumerate(lines):
            if "from shared.config import settings" in line and "settings" in line:
                new_lines.append(f"# REFACTORED: {line}")
                changes.append(f"Line {i+1}: Removed settings import")
            else:
                new_lines.append(line)
        lines = new_lines

        # Step 2: Add IntentRepository import (after last import)
        last_import_idx = 0
        has_intent_import = False
        for i, line in enumerate(lines):
            if "IntentRepository" in line and ("from " in line or "import " in line):
                has_intent_import = True
            if line.startswith("from ") or line.startswith("import "):
                last_import_idx = i

        if not has_intent_import:
            import_line = "from shared.infrastructure.intent.intent_repository import IntentRepository, get_intent_repository"
            lines.insert(last_import_idx + 1, import_line)
            changes.append(f"Line {last_import_idx+2}: Added IntentRepository import")

        # Step 3: Find __init__ and add parameter
        init_line_idx = None
        for i, line in enumerate(lines):
            if re.match(r"\s*def __init__\(", line):
                init_line_idx = i
                break

        if init_line_idx is not None:
            old_line = lines[init_line_idx]

            # Check if intent_repository already in params
            if "intent_repository" not in old_line:
                # Add parameter
                if old_line.rstrip().endswith("):"):
                    # Single line __init__
                    new_line = old_line.replace(
                        "):", ", intent_repository: IntentRepository | None = None):"
                    )
                else:
                    # Multi-line __init__ - add after last parameter
                    new_line = old_line.replace(
                        ",", ", intent_repository: IntentRepository | None = None,", 1
                    )

                if new_line != old_line:
                    lines[init_line_idx] = new_line
                    changes.append(
                        f"Line {init_line_idx+1}: Added intent_repository parameter"
                    )

                # Step 4: Add self.intent_repo assignment
                indent = len(old_line) - len(old_line.lstrip())
                assignment = (
                    " " * (indent + 4)
                    + "self.intent_repo = intent_repository or get_intent_repository()"
                )

                # Find where to insert (after __init__ line, before first real statement)
                insert_idx = init_line_idx + 1
                lines.insert(insert_idx, assignment)
                changes.append(
                    f"Line {insert_idx+1}: Added self.intent_repo initialization"
                )

        # Step 5-7: Replace settings usage
        for i, line in enumerate(lines):
            old_line = line

            # Replace context.path_resolver.intent_root
            if "context.path_resolver.intent_root" in line:
                line = line.replace(
                    "context.path_resolver.intent_root", "self.intent_repo.root"
                )

            # Replace context.context.settings.load("path") with intent_repo.load_policy("path")
            load_match = re.search(r'settings\.load\(["\']([^"\']+)["\']\)', line)
            if load_match:
                old_call = load_match.group(0)
                policy_path = load_match.group(1)
                new_call = f'self.intent_repo.load_policy("{policy_path}")'
                line = line.replace(old_call, new_call)

            # Replace context.context.context.context.settings.get_path()
            if "context.context.context.context.settings.get_path(" in line:
                line = line.replace(
                    "context.context.context.context.settings.get_path(",
                    "self.intent_repo.resolve_rel(",
                )

            # Replace context.context.context.settings.paths
            if "context.context.context.settings.paths" in line:
                line = line.replace(
                    "context.context.context.settings.paths", "self.intent_repo"
                )

            if line != old_line:
                lines[i] = line
                changes.append(f"Line {i+1}: Replaced settings usage")

        refactored = "\n".join(lines) + "\n"

        return RefactoringAction(
            file_path=file_path,
            action_type="intent_repository",
            original_content=original,
            refactored_content=refactored,
            changes_made=changes,
        )

    # ID: 625bd829-15a8-49ba-9bf2-11d479098acf
    def refactor_to_repo_path_param(self, file_path: Path) -> RefactoringAction:
        """
        Refactor file to receive repo_path as parameter instead of settings.

        Changes:
        1. Remove: from shared.config import settings
        2. Add: from pathlib import Path (if not present)
        3. Add parameter: repo_path: Path
        4. Add assignment: self.repo_path = repo_path
        5. Replace: context.git_service.repo_path → self.repo_path
        """
        original = file_path.read_text()
        lines = original.splitlines()
        changes = []

        # Step 1: Remove settings import
        new_lines = []
        for i, line in enumerate(lines):
            if "from shared.config import settings" in line:
                new_lines.append(f"# REFACTORED: {line}")
                changes.append(f"Line {i+1}: Removed settings import")
            else:
                new_lines.append(line)
        lines = new_lines

        # Step 2: Add Path import if needed
        has_path_import = False
        last_import_idx = 0
        for i, line in enumerate(lines):
            if "from pathlib import" in line and "Path" in line:
                has_path_import = True
            if line.startswith("from ") or line.startswith("import "):
                last_import_idx = i

        if not has_path_import:
            lines.insert(last_import_idx + 1, "from pathlib import Path")
            changes.append(f"Line {last_import_idx+2}: Added Path import")

        # Step 3: Find __init__ and add repo_path parameter
        init_line_idx = None
        for i, line in enumerate(lines):
            if re.match(r"\s*def __init__\(", line):
                init_line_idx = i
                break

        if init_line_idx is not None:
            old_line = lines[init_line_idx]

            # Check if repo_path already in params
            if "repo_path" not in old_line:
                # Add parameter after self
                if "def __init__(self)" in old_line:
                    new_line = old_line.replace(
                        "def __init__(self)", "def __init__(self, repo_path: Path)"
                    )
                elif "def __init__(self," in old_line:
                    new_line = old_line.replace(
                        "def __init__(self,", "def __init__(self, repo_path: Path,"
                    )
                else:
                    new_line = old_line

                if new_line != old_line:
                    lines[init_line_idx] = new_line
                    changes.append(f"Line {init_line_idx+1}: Added repo_path parameter")

                # Step 4: Add self.repo_path assignment
                indent = len(old_line) - len(old_line.lstrip())
                assignment = " " * (indent + 4) + "self.repo_path = repo_path"

                insert_idx = init_line_idx + 1
                lines.insert(insert_idx, assignment)
                changes.append(
                    f"Line {insert_idx+1}: Added self.repo_path initialization"
                )

        # Step 5: Replace context.git_service.repo_path
        for i, line in enumerate(lines):
            if "context.git_service.repo_path" in line:
                old_line = line
                line = line.replace("context.git_service.repo_path", "self.repo_path")
                lines[i] = line
                changes.append(
                    f"Line {i+1}: Replaced context.git_service.repo_path with self.repo_path"
                )

        refactored = "\n".join(lines) + "\n"

        return RefactoringAction(
            file_path=file_path,
            action_type="repo_path_param",
            original_content=original,
            refactored_content=refactored,
            changes_made=changes,
        )

    # ID: fcc9ef7e-e502-4830-9183-0a4e4be4f0cc
    def apply_refactoring(
        self, file_path: Path, action_type: str, dry_run: bool = True
    ) -> RefactoringAction | None:
        """Apply refactoring to a file."""
        try:
            if action_type == "intent_repository":
                action = self.refactor_to_intent_repository(file_path)
            elif action_type == "repo_path_param":
                action = self.refactor_to_repo_path_param(file_path)
            else:
                logger.error("Unknown action type: %s", action_type)
                return None

            if dry_run:
                logger.info(
                    "DRY RUN: Would refactor %s", file_path.relative_to(self.repo_path)
                )
                return action

            # Apply using FileHandler
            rel_path = str(file_path.relative_to(self.repo_path))
            self.file_handler.write_runtime_text(rel_path, action.refactored_content)
            logger.info("✅ Refactored %s", rel_path)
            return action

        except Exception as e:
            logger.error("Failed to refactor %s: %s", file_path, e, exc_info=True)
            return None


# ID: d149dd73-5aa9-4a7b-8bdf-b00e304d3678
# List of files to refactor (from analysis report)
INTENT_REPOSITORY_FILES = [
    # Mind layer
    "src/mind/governance/policy_loader.py",
    "src/mind/governance/audit_context.py",
    "src/mind/governance/micro_proposal_validator.py",
    "src/mind/governance/intent_guard.py",
    "src/mind/logic/engines/workflow_gate/checks/coverage.py",
    # Will layer
    "src/will/cli_logic/reviewer.py",
    "src/will/agents/tagger_agent.py",
    "src/will/agents/micro_planner.py",
    "src/will/agents/deduction_agent.py",
    "src/will/agents/planner_agent.py",
    "src/will/agents/intent_translator.py",
    "src/will/agents/code_generation/code_generator.py",
]

REPO_PATH_PARAM_FILES = [
    # Mind layer
    "src/mind/governance/policy_coverage_service.py",
    "src/mind/logic/engines/ast_gate/checks/capability_checks.py",
    "src/mind/logic/engines/workflow_gate/checks/alignment.py",
    "src/mind/logic/engines/workflow_gate/checks/dead_code.py",
    "src/mind/logic/engines/workflow_gate/checks/quality.py",
    # Will layer
    "src/will/orchestration/decision_tracer.py",
    "src/will/orchestration/workflow_orchestrator.py",
    "src/will/orchestration/phase_registry.py",
    "src/will/orchestration/self_correction_engine.py",
    "src/will/cli_logic/chat.py",
    "src/will/agents/base_planner.py",
    "src/will/agents/specification_agent.py",
    "src/will/agents/coder_agent.py",
    "src/will/agents/self_correction_engine.py",
    "src/will/tools/architectural_context_builder.py",
    "src/will/phases/canary/pytest_runner.py",
    "src/will/phases/canary/test_discovery.py",
]


# ID: 4ffc7a5a-7452-45f5-a239-b44f68d9471f
async def apply_provider_refactoring(
    repo_path: Path,
    dry_run: bool = True,
    file_list: list[str] | None = None,
) -> dict[str, Any]:
    """
    Apply automated provider refactoring to high-confidence files.

    Args:
        repo_path: Repository root path
        dry_run: If True, analyze but don't modify files
        file_list: Optional list of specific files to refactor (relative paths)

    Returns:
        Results dictionary with statistics and file details
    """
    file_handler = FileHandler(str(repo_path))
    applicator = ProviderRefactoringApplicator(repo_path, file_handler)

    results = {
        "dry_run": dry_run,
        "intent_repository": {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "files": [],
        },
        "repo_path_param": {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "files": [],
        },
    }

    # Determine which files to process
    if file_list:
        # Filter by user-provided list
        intent_files = [f for f in INTENT_REPOSITORY_FILES if f in file_list]
        repo_path_files = [f for f in REPO_PATH_PARAM_FILES if f in file_list]
    else:
        intent_files = INTENT_REPOSITORY_FILES
        repo_path_files = REPO_PATH_PARAM_FILES

    # Process IntentRepository refactorings
    logger.info("=" * 80)
    logger.info("Applying IntentRepository pattern refactorings")
    logger.info("=" * 80)

    for rel_path in intent_files:
        file_path = repo_path / rel_path
        if not file_path.exists():
            logger.warning("File not found: %s", rel_path)
            continue

        results["intent_repository"]["attempted"] += 1
        action = applicator.apply_refactoring(file_path, "intent_repository", dry_run)

        if action:
            results["intent_repository"]["succeeded"] += 1
            results["intent_repository"]["files"].append(
                {
                    "path": rel_path,
                    "changes": len(action.changes_made),
                    "success": True,
                }
            )
        else:
            results["intent_repository"]["failed"] += 1
            results["intent_repository"]["files"].append(
                {"path": rel_path, "success": False}
            )

    # Process repo_path parameter refactorings
    logger.info("=" * 80)
    logger.info("Applying repo_path parameter refactorings")
    logger.info("=" * 80)

    for rel_path in repo_path_files:
        file_path = repo_path / rel_path
        if not file_path.exists():
            logger.warning("File not found: %s", rel_path)
            continue

        results["repo_path_param"]["attempted"] += 1
        action = applicator.apply_refactoring(file_path, "repo_path_param", dry_run)

        if action:
            results["repo_path_param"]["succeeded"] += 1
            results["repo_path_param"]["files"].append(
                {
                    "path": rel_path,
                    "changes": len(action.changes_made),
                    "success": True,
                }
            )
        else:
            results["repo_path_param"]["failed"] += 1
            results["repo_path_param"]["files"].append(
                {"path": rel_path, "success": False}
            )

    return results
