# F-10.3 — `core-audit-gate` image used by the GitHub Action (action.yml).
#
# Minimal container per ADR-086 D1: Python runtime + core-runtime from
# PyPI (F-48.2) + entrypoint script. No daemon, no DB, no Qdrant — the
# Audit tier runs the stateless audit path (F-10.1a) only.
#
# This Dockerfile is built by the GH Actions runner each time the action
# is used (`runs.image: Dockerfile` in action.yml). Build time is ~30s,
# dominated by `pip install core-runtime`.

FROM python:3.12-slim

# Pin the core-runtime version. Bump on every action release that needs
# a newer audit engine; otherwise the action remains stable against this
# version.
ARG CORE_RUNTIME_VERSION=2.7.0

# Minimal OS-level dependencies. `core-runtime` brings everything else
# (pydantic, jsonschema, sqlalchemy, etc.) via its declared Requires-Dist;
# the stateless audit path does not touch DB/Qdrant so those deps are
# pulled but never connected.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "core-runtime==${CORE_RUNTIME_VERSION}"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
