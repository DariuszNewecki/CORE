# .intent/charter/patterns/conversational_context_extractor.yaml
id: conversational_context_extractor
version: "1.0.0"
title: "Conversational Context Extractor"
description: |
  Pattern for turning an irritation or high-level topic into a governed,
  minimal ContextPackage bundle suitable for conversational reasoning.
  The Extractor is deterministic (Body), governed by Mind policies, and
  consumed by Will agents or humans.

applies_to:
  - "core-admin context.* commands"
  - "Will-layer agents that request conversational context"
  - "test harnesses that escalate failing tests into investigations"
  - "governance checks that attach conversational bundles to violations"

principles:
  - "Mind defines allowed sources, redaction rules, and bundle schema."
  - "Body gathers only relevant, non-sensitive context deterministically."
  - "Will never bypasses constitutional workflows when using a bundle."
  - "Context must be reproducible from inputs (topic, hints, run id, repo state)."
  - "Prefer minimal, focused bundles over full-repo dumps (context_minimization)."

contracts:
  inputs:
    required:
      - name: topic
        type: string
        description: "Short human description of the irritation or question."
    optional:
      - name: files
        type: list[path]
        description: "Explicit files the human suspects are relevant."
      - name: symbols
        type: list[string]
        description: "Symbol names or IDs (e.g. CoreContext, configure_root_logger)."
      - name: tests
        type: list[string]
        description: "Failing tests to anchor the investigation."
      - name: irritation_id
        type: string
        description: "Reference to a recorded irritation event."

  outputs:
    kind: conversational_context_bundle
    schema: ".intent/charter/schemas/context_bundle.yaml"
    guarantees:
      - "Bundle includes topic, scope, relevant symbols, policies, and runtime artefacts."
      - "Bundle never includes secrets or sensitive payloads."
      - "Bundle is small enough to be passed to a single LLM call."
      - "Bundle can be regenerated from its recorded inputs and repo state."

governance:
  policies:
    - "headless_body"          # Body cannot emit UI; only structured bundles.
    - "ui_single_owner"        # CCE does not own rendering, only data.
    - "context_minimization"   # Only necessary context is collected.
    - "logging_standards"      # CCE logs its own activity in a structured way.
  audits:
    - "DomainPlacementCheck"   # CCE implementation must live in the correct domain.
    - "CapabilityOwnerCheck"   # Ownership must be explicit.
    - "BodyContractsCheck"     # Must not violate headless Body / UI ownership.
