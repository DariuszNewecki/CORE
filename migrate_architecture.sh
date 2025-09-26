#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# CORE FINAL MIGRATION SCRIPT (CR-DB-ARCH-V4 - Final Polish)
#
# PURPOSE:
#   This script completes the final 2% of the refactoring by moving the last
#   remaining logic files out of the CLI layer and flattening its structure.
#
# USAGE: ./finalize_architecture.sh
# ==============================================================================

echo "🚀 Applying the final polish to the new architecture..."

# --- Step 1: Move the last pieces of logic out of the CLI layer ---
echo "-> Moving final logic files to 'features/introspection'..."
mv src/cli/commands/knowledge_vectorizer.py src/features/introspection/
mv src/cli/commands/knowledge_helpers.py src/features/introspection/

# --- Step 2: Flatten the CLI command structure for clarity ---
echo "-> Flattening the CLI command structure..."
# Move files from subdirectories up to the main commands directory
# Use `find` to handle this robustly.
find src/cli/commands/ -mindepth 2 -type f -print -exec mv {} src/cli/commands/ \;

# --- Step 3: Clean up the now-empty subdirectories ---
echo "-> Cleaning up empty CLI subdirectories..."
# Use `find` to delete empty directories
find src/cli/commands/ -mindepth 1 -type d -delete

echo -e "\n✅ Final architecture polish complete!"
echo "--- NEXT STEPS ---"
echo "1.  **CRITICAL:** Manually fix any remaining Python 'import' statements."
echo "2.  **CRITICAL:** Update '.intent/mind/knowledge/source_structure.yaml' to match this final structure."
echo "3.  Run 'make check' to get a final report of any remaining issues."
echo "4.  Commit your work. The migration is complete."