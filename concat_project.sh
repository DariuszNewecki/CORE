#!/bin/bash
#
# CONTEXT BUILDER SCRIPT (v3 - The Correct One)
#
# Concatenates all relevant project source files into a single context file.
# Correctly prunes excluded directories and filters files without generating empty entries.

# The name of the final output file.
OUTPUT_FILE="project_context.txt"

echo "Initializing context builder..."

# Directories to completely exclude.
EXCLUDED_DIRS=(
    "./.git"
    "./.venv"
    "./__pycache__"
    "./logs"
    "./sandbox"
    "./pending_writes"
    "./.pytest_cache"
    "./.ruff_cache"
)

# Files/patterns to exclude.
EXCLUDED_FILES=(
    ".env"
    "poetry.lock"
    "*.png"
    "*.jpg"
    "*.pyc"
    "*.so"
    # This script and its output must always be excluded.
    "$(basename "$0")"
    "$OUTPUT_FILE"
)

# --- CORRECTED FIND LOGIC ---

# 1. Build the directory exclusion list for -prune.
#    This creates a list like: -path './.git' -o -path './.venv'
prune_paths=()
for dir in "${EXCLUDED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        # Add '-o' (OR) between each path, but not at the beginning.
        if [ ${#prune_paths[@]} -gt 0 ]; then
            prune_paths+=(-o)
        fi
        prune_paths+=(-path "$dir")
    fi
done

# 2. Build the file exclusion list.
#    This creates a list like: -not -name '*.pyc' -not -name 'poetry.lock'
exclude_files_args=()
for pattern in "${EXCLUDED_FILES[@]}"; do
    exclude_files_args+=(-not -name "$pattern")
done

# Clear the output file to start fresh.
> "$OUTPUT_FILE"

echo "Concatenating relevant project files into ${OUTPUT_FILE}..."

# 3. Execute the corrected find command.
#    - Group the prune paths: \( ... \) -prune
#    - Use -o to combine with the action for non-pruned paths.
#    - Find only files (-type f) and apply the name exclusions.
find . \( "${prune_paths[@]}" \) -prune -o -type f \( "${exclude_files_args[@]}" \) -print0 | while IFS= read -r -d $'\0' file; do
    
    # Just in case, skip if the file variable is somehow empty.
    if [ -z "$file" ]; then
        continue
    fi
    
    echo "--- START OF FILE ${file} ---" >> "$OUTPUT_FILE"
    
    if [[ -s "$file" ]]; then
        cat "$file" >> "$OUTPUT_FILE"
    else
        echo "[EMPTY FILE]" >> "$OUTPUT_FILE"
    fi
    
    echo "" >> "$OUTPUT_FILE"
    echo "--- END OF FILE ${file} ---" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
done

# Final sanity check.
file_count=$(grep -c "START OF FILE" "$OUTPUT_FILE")
if [ "$file_count" -gt 0 ]; then
    echo "Done. Concatenated $file_count files into ${OUTPUT_FILE}."
else
    echo "Warning: No files were found to concatenate. Please check your exclusion rules."
fi