#!/usr/bin/env bash
#
# scripts/demo.sh — compatibility wrapper (ADR-155 D1).
#
# This script contains NO scenario logic. It exists only so an operator (or an
# old bookmark/link) invoking `scripts/demo.sh` is delegated to the real,
# isolated command. All of the demonstration — the disposable clone, the
# disposable infrastructure, the genuine governance chain, the evidence, and the
# scoped cleanup — lives in:
#
#     core-admin demo consequence-chain
#
# It deliberately performs no git mutation, no database query, and no error
# suppression: it execs the real command and passes its exit code straight
# through, so a failed demonstration fails this wrapper too.
set -euo pipefail

cd "$(dirname "$0")/.."
exec poetry run core-admin demo consequence-chain "$@"
