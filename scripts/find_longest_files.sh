#!/bin/bash
# find_longest_files.sh
# Finds the 5 longest files in the CORE project by line count, respecting .gitignore patterns
# and explicitly excluding docs/ and scripts/ directories.

# Read .gitignore, ignoring comments and empty lines
patterns=()
while IFS= read -r line; do
  line=$(echo "$line" | sed 's/#.*//; s/^[ \t]*//; s/[ \t]*$//')
  [[ -n "$line" ]] && patterns+=("$line")
done < .gitignore

# Add .git/, docs/, and scripts/ to exclusions
patterns+=(".git/" "docs/" "scripts/" "sql/")

# Convert patterns to find exclusions
exclusions=""
for pattern in "${patterns[@]}"; do
  # Handle directory patterns (ending with /) and escape special characters
  if [[ "$pattern" == */ ]]; then
    pattern="${pattern%/}/*"
  fi
  # Escape special characters for find
  escaped_pattern=$(echo "$pattern" | sed 's/[][<>\\"|&;() ]/\\&/g')
  exclusions="$exclusions -not -path './$escaped_pattern'"
done

# Run find with exclusions, count lines individually, and get top 5
eval "find . -type f $exclusions -exec wc -l {} \; | awk '{print \$1 \" \" \$2}' | sort -nr | head -n 5"
