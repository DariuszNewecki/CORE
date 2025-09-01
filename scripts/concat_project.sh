#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="project_context.txt"
echo "Initializing context builder (find mode)..."

# Directories to prune at any depth (add 'demo' here)
PRUNE_DIRS=( .git .venv __pycache__ .pytest_cache .ruff_cache logs sandbox pending_writes demo )

# Filenames/patterns to exclude
EXCLUDED_NAMES=( ".env" "poetry.lock" "*.png" "*.jpg" "*.jpeg" "*.gif" "*.webp" "*.ico" "*.pyc" "*.so" "$(basename "$0")" "$OUTPUT_FILE" )

# Build prune expression for find
prune_expr=()
for d in "${PRUNE_DIRS[@]}"; do
  [[ ${#prune_expr[@]} -gt 0 ]] && prune_expr+=(-o)
  prune_expr+=( -type d -name "$d" )
done

# Build name exclusions
name_expr=()
for n in "${EXCLUDED_NAMES[@]}"; do
  name_expr+=( -not -name "$n" )
done

: > "$OUTPUT_FILE"

# find → sort deterministically → loop
find . \( "${prune_expr[@]}" \) -prune -o -type f \( "${name_expr[@]}" \) -print0 \
| sort -z \
| while IFS= read -r -d '' file; do
    printf -- "--- START OF FILE %s ---\n" "$file" >> "$OUTPUT_FILE"
    if [[ -s "$file" ]]; then
      cat "$file" >> "$OUTPUT_FILE"
    else
      printf "[EMPTY FILE]\n" >> "$OUTPUT_FILE"
    fi
    printf "\n--- END OF FILE %s ---\n\n" "$file" >> "$OUTPUT_FILE"
  done

count=$(grep -c "^--- START OF FILE " "$OUTPUT_FILE" || true)
echo "Done. Concatenated $count files into ${OUTPUT_FILE}."
