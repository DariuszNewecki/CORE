#!/usr/bin/env bash
#
# concat_bundle.sh
# A constitutionally-aware script to bundle all relevant .intent/ files
# into a single text file for external AI review and analysis.
#
# This script respects the Charter/Mind separation and excludes sensitive or
# irrelevant files to create a clean, focused context bundle.
#

set -euo pipefail

# --- Configuration ---
# The final output file for the bundle.
OUTPUT_FILE="constitutional_bundle.txt"
# The root of the constitution.
INTENT_DIR=".intent"
# --- End Configuration ---

# Ensure we are in the project root where .intent directory exists
if [ ! -d "$INTENT_DIR" ]; then
    echo "❌ Error: This script must be run from the CORE project root directory."
    exit 1
fi

echo "🚀 Generating constitutional bundle for AI review..."
echo "   -> Output will be saved to: $OUTPUT_FILE"

# Start with a clean slate
> "$OUTPUT_FILE"

# Helper function to append a directory's contents to the bundle
# It takes a title and the directory path as arguments.
append_directory() {
    local title="$1"
    local dir_path="$2"
    local file_count=0

    # Check if the directory exists and has files
    if [ -d "$dir_path" ] && [ -n "$(find "$dir_path" -maxdepth 1 -type f)" ]; then
        echo "" | tee -a "$OUTPUT_FILE" > /dev/null
        echo "--- START OF SECTION: $title ---" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"

        # Use find to handle files gracefully, sorted for deterministic output
        for file in $(find "$dir_path" -maxdepth 1 -type f -name "*.yaml" -o -name "*.yml" -o -name "*.md" -o -name "*.json" | sort); do
            if [ -f "$file" ]; then
                echo "--- START OF FILE $file ---" >> "$OUTPUT_FILE"
                cat "$file" >> "$OUTPUT_FILE"
                echo -e "\n--- END OF FILE $file ---\n" >> "$OUTPUT_FILE"
                file_count=$((file_count + 1))
            fi
        done
        echo "--- END OF SECTION: $title ($file_count files) ---" >> "$OUTPUT_FILE"
    fi
}

# 1. Start with the Master Index
echo "--- START OF FILE $INTENT_DIR/meta.yaml ---" >> "$OUTPUT_FILE"
cat "$INTENT_DIR/meta.yaml" >> "$OUTPUT_FILE"
echo -e "\n--- END OF FILE $INTENT_DIR/meta.yaml ---\n" >> "$OUTPUT_FILE"

# 2. Append the entire Charter
echo "==============================================================================" >> "$OUTPUT_FILE"
echo "                            PART 1: THE CHARTER" >> "$OUTPUT_FILE"
echo " (The Immutable Laws, Mission, and Foundational Principles of the System)" >> "$OUTPUT_FILE"
echo "==============================================================================" >> "$OUTPUT_FILE"
append_directory "Constitution" "$INTENT_DIR/charter/constitution"
append_directory "Mission" "$INTENT_DIR/charter/mission"
append_directory "Policies" "$INTENT_DIR/charter/policies"
append_directory "Schemas" "$INTENT_DIR/charter/schemas"

# 3. Append the entire Working Mind
echo "" >> "$OUTPUT_FILE"
echo "==============================================================================" >> "$OUTPUT_FILE"
echo "                            PART 2: THE WORKING MIND" >> "$OUTPUT_FILE"
echo " (The Dynamic Knowledge, Configuration, and Evaluation Logic of the System)" >> "$OUTPUT_FILE"
echo "==============================================================================" >> "$OUTPUT_FILE"
append_directory "Configuration" "$INTENT_DIR/mind/config"
append_directory "Evaluation" "$INTENT_DIR/mind/evaluation"
append_directory "Knowledge" "$INTENT_DIR/mind/knowledge"

# Note: We intentionally exclude prompts/ as they are often very large and context-specific.
# We also exclude generated artifacts like knowledge_graph.json and sensitive files like keys/.

TOTAL_SIZE=$(wc -c < "$OUTPUT_FILE")
echo ""
echo "✅ Constitutional bundle successfully generated!"
echo "   -> Total size: $TOTAL_SIZE bytes."
echo "   -> You can now copy the content of '$OUTPUT_FILE' and provide it to an external AI for review."
