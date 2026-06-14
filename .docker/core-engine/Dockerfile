# .docker/core-engine/Dockerfile
# core-engine — the Solo+ CORE runtime image (ADR-086 D1).
#
# The full CORE daemon + complete CLI. Postgres + Qdrant are EXTERNAL
# (operator-supplied via DATABASE_URL / QDRANT_URL); this image is the
# application tier ONLY and never bundles a database (ADR-086 D1 forbidden
# combinations).
#
# Version-matched per ADR-086 D7: installs the *published* core-runtime
# from PyPI, so a `core-engine:X.Y.Z` image exists if and only if
# `core-runtime X.Y.Z` exists on PyPI. CORE_RUNTIME_VERSION is REQUIRED
# (no default) so the image can never silently drift from its release tag.

FROM python:3.12-slim

ARG CORE_RUNTIME_VERSION
ENV PYTHONUNBUFFERED=1

# git is required by the daemon's GitService (repo operations on /workspace).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Fail the build loudly if the version arg was not supplied — forces every
# build to be version-matched (no stale default to drift, cf. #648).
RUN test -n "${CORE_RUNTIME_VERSION}" \
    || ( echo "ERROR: CORE_RUNTIME_VERSION build-arg is required" >&2; exit 1 )

# Install the version-matched, PUBLISHED runtime from PyPI. ADR-086 D1: the
# image is the published wheel, never a pin to an unpublished SHA.
RUN pip install --no-cache-dir "core-runtime==${CORE_RUNTIME_VERSION}"

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Operators mount their governed project (a git repo containing .intent/) here.
WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
