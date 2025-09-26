# CORE Governance Map

This document provides a visual and conceptual map of the CORE system's governance structure, as defined in the `.intent/` directory. It serves the `clarity_first` principle by making the separation of concerns explicit.

```mermaid
flowchart TB
  A["<div style='font-weight: bold; font-size: 1.2em'>.intent/</div><div style='font-style: italic'>The Mind</div>"]:::root

  subgraph Charter [Immutable Charter (Human-Governed)]
    direction TB
    C1[constitution/]:::ro
    C2[mission/]:::ro
    P[policies/]:::ro
    S[schemas/]:::ro
  end

  subgraph Mind [Dynamic Mind (System-Maintained)]
    direction TB
    K[knowledge/]:::dyn
    E[evaluation/]:::dyn
    M[config/]:::dyn
  end
  
  subgraph Meta [Meta & Governance]
    direction TB
    meta_yaml["meta.yaml"]:::meta
    project_manifest["project_manifest.yaml"]:::meta
  end

  A --> Charter
  A --> Mind
  A --> Meta

  classDef root fill:#111827,stroke:#6b7280,color:#f9fafb,font-weight:bold;
  classDef ro fill:#0369a1,stroke:#0ea5e9,color:#f0f9ff;
  classDef dyn fill:#166534,stroke:#22c55e,color:#f0fdf4;
  classDef meta fill:#78350f,stroke:#f59e0b,color:#fffbeb;

Key
Immutable Charter (Blue): These are the foundational laws and principles. They can only be changed by a formal, human-in-the-loop proposal process. The system itself cannot modify these files.
Dynamic Mind (Green): This is the system's working memory and self-knowledge. These files can be updated by governed system processes, such as knowledge sync, but always under the rules defined in the Charter.
Meta & Governance (Amber): These files orchestrate the constitution itself, defining the structure and high-level intent.