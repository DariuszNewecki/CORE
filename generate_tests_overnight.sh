#!/bin/bash
# Target files with <25% coverage
poetry run core-admin coverage accumulate-batch --pattern "src/features/introspection/*.py" --limit 10
poetry run core-admin coverage accumulate-batch --pattern "src/features/self_healing/*.py" --limit 15
poetry run core-admin coverage accumulate-batch --pattern "src/mind/governance/checks/*.py" --limit 10
poetry run core-admin coverage accumulate-batch --pattern "src/services/context/*.py" --limit 5
poetry run core-admin coverage accumulate-batch --pattern "src/body/cli/logic/*.py" --limit 10
