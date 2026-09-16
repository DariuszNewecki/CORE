# ADR-159 Trial 0 apparatus — canonical staged inputs

Governor ruling 2026-09-15: the canonical overlay and seed for Trial 0 are tracked here. Before
execution they are staged byte-for-byte into the evidence root
(`/opt/core-trials/adr-159/trial-0`) and their hashes recorded there; the coldroom receives only
the pinned runner (`a2adc03c`), the frozen subject (`c4d9fdf9`), these staged inputs and the
evidence destination — never the working CORE checkout. The seal stays outside everything the
runner can see.

Why the overlay is exactly this small: the overlay is additive-only and the subject (frozen CORE)
already carries its own phases, workflow definitions and policies; the test fixture's overlay
collides on 11 of 13 paths and cannot be used. Only paths absent from the subject may be
overlaid: the worker declaration below, the safe-auto-approval envelope, and the three
evaluation-workflow declarations added for #895 U2.

The U2 additions are additive on the same test: `git ls-tree -r c4d9fdf9 -- .intent/workflows/`
lists sixteen files and none of the three below, so they displace nothing in the subject. Each is
a byte-identical copy of the governed declaration under `.intent/` -- verified by sha256, not by
inspection -- because the subject must evaluate under exactly the law CORE declares, not a
restatement of it.

#895 U3 (D2, governor ruling 2026-09-16) adds two more additive paths on the same test (`git
ls-tree -r c4d9fdf9` lists neither): the `architecture.execution_write.repository_containment`
rule document and its `passive_gate` class-A mapping, so the I-5 probe's refusal names a rule
that exists in the law the subject evaluates under. Byte-identical copies, hashed below.

The envelope is an explicit `authorization_mode: deny_all` (Governor ruling F, 2026-09-15): nothing is
authorized for safe auto-approval, by declaration. Materialization of this overlay onto the frozen
subject was proven 2026-09-15: 2 overlay files installed, 12 floor collisions displaced and
manifested, floor clean, envelope loads as deny_all.

Provenance: seed resource digest `f72c60cabf6237b07f6e` verified 2026-09-15 on `.40` and `.200`.

| file | sha256 | bytes |
|---|---|---|
| `intent_overlay/enforcement/config/safe_auto_approval_envelope.yaml` | `bac3d4bb62fb37553c4d14278e6b581776e8387578b5ad4cea1c31800a46bf5f` | 767 |
| `intent_overlay/workflows/definitions/evaluation.yaml` | `5abad3bc1610a14bb084205a6b55a938caec56944d75ba0b6833f7423f12bbc6` | 1299 |
| `intent_overlay/workflows/stages/parse.plan_investigation.yaml` | `0b18505d8ce367bb647d1d745db1e79aa487796dc0e8e1fb50810cd00f27d18a` | 1664 |
| `intent_overlay/workflows/stages/runtime.investigate.yaml` | `6807a0a4d42fb3587b9a8ac32df8f0c120ef067e2ea18e595a704b6dd77b4fd8` | 1479 |
| `intent_overlay/workers/goal_execution_worker.yaml` | `ab8d279420eab934f246462f566ba9ed0344b383c8cff734fa09551e7db4db47` | 1687 |
| `intent_overlay/rules/architecture/execution_write_containment.json` | `6af0c30cd02e7932b3088882c3df32e4d4a50c8992289d1364003186923c8036` | 1863 |
| `intent_overlay/enforcement/mappings/architecture/execution_write_containment.yaml` | `c26f112cab6dcc10171aaa9c24a19c03067571d80f00da3d40417ba30c680685` | 1565 |
| `seed/assignments.yaml` | `247ba8c05be49dd9e6357f40480ae00dd92d598f9f5c2572e60efbb3c985367d` | 553 |
| `seed/llm_resources/ollama_qwen_coder_3b_trial.yaml` | `7d1d94725bbff59c6b3e5a2a1d5115a5fae0f63613252328f3641d7fa959d3e7` | 809 |
| `seed/system_config.yaml` | `31ed092d8b356ab600a80cb7842c984dc99fb7846bf094e75a3a8fafbf357436` | 181 |
