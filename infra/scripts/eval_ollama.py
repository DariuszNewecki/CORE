#!/usr/bin/env python3
"""
Ollama Model Evaluation Harness for CORE PromptModel artifacts.

Standalone script — does NOT import from CORE's src/ package, does NOT
touch the database or daemon. Reads var/prompts/ artifacts directly,
runs each prompt against three local Ollama models, scores each response,
and writes results to var/llm_eval/.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import statistics
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = Path("/opt/dev/CORE")
PROMPTS_DIR = REPO_ROOT / "var" / "prompts"
RESULTS_DIR = REPO_ROOT / "var" / "llm_eval"

OLLAMA_URL = "http://192.168.20.40:11434"
REQUEST_TIMEOUT_SEC = 120.0
REPETITIONS = 3

MODELS: dict[str, str] = {
    "14b-coder":  "qwen2.5-coder:14b",
    "3b-coder":   "qwen2.5-coder:3b",
    "7b-general": "qwen2.5:7b",
    "phi4-14b":   "phi4:14b",
}

# role -> [prompt directory names]
ROLE_PROMPTS: dict[str, list[str]] = {
    "LocalCoder": [
        "coder_repair",
        "code_fixer",
        "violation_remediator",
        "simple_test_generator_prompt",
        "llm_correction_syntax",
        "llm_correction_structural",
        "single_test_fixer",
        "context_aware_test_gen",
        "line_length_refactorer",
        "pattern_correction",
        "complexity_reflex_refactor",
        "clarity_v2_refactor",
    ],
    "DocstringWriter": [
        "docstring_writer",
    ],
    "Architect": [
        "modularity_analyze",
        "code_peer_review",
        "architect_threats_analysis_prompt",
        "intent_inspector_alignment",
        "intent_inspector_coherence",
    ],
    "LocalReasoner": [
        "llm_gate",
        "llm_gate_audit_prompt",
        "assumption_extractor",
    ],
    "Planner": [
        "micro_planner_create_micro_plan",
        "plan_goal",
    ],
    "RemoteCoder": [
        "code_generation_task_step_prompt",
    ],
}

console = Console()


# ---------------------------------------------------------------------------
# Fixture registry
# ---------------------------------------------------------------------------

FIXTURES: dict[str, str] = {
    "source_code": (
        "# src/body/workers/example_worker.py\n"
        "from shared.logger import getLogger\n\n"
        "logger = getLogger(__name__)\n\n"
        "def process_entry(entry):\n"
        "    result = entry.get(\"payload\", {})\n"
        "    return result\n"
    ),
    "file_path": "src/body/workers/example_worker.py",
    "goal": (
        "Implement a stateless worker that reads a blackboard entry payload "
        "and returns a summary dict. Follow CORE Body layer conventions."
    ),
    "task_step": "implement_payload_summarizer",
    "pain_signal": (
        "SyntaxError: invalid syntax at line 7. "
        "The function is missing a return statement in the error branch."
    ),
    "previous_code": (
        "def process_entry(entry):\n"
        "    result = entry.get(\"payload\", {}\n"
        "    return result\n"
    ),
    "violations": (
        "purity.docstrings.required: "
        "Missing module docstring in src/body/workers/example_worker.py. "
        "Missing function docstring on process_entry()."
    ),
    "violations_summary": (
        "Rule purity.docstrings.required — 2 violations:\n"
        "  Line 1: missing module docstring\n"
        "  Line 7: missing docstring on function 'process_entry'"
    ),
    "context_package": (
        "File: src/body/workers/example_worker.py\n"
        "Layer: body/workers\n"
        "Purpose: Reads blackboard entries and summarises payload content.\n"
        "Pattern: Worker — stateless, pure function, no DB calls."
    ),
    "architectural_context": (
        "{\n"
        '  "file_role": "worker",\n'
        '  "layer": "body",\n'
        '  "pattern": "StatelessTransformer",\n'
        '  "candidate_strategies": ["add_docstrings", "restructure_to_pattern"]\n'
        "}\n"
    ),
    "rule_id": "purity.docstrings.required",
    "symbol_name": "process_entry",
    "module_path": "src/body/workers/example_worker.py",
    "description": "Reads a blackboard entry payload and returns a summary dict.",
    "function_name": "process_entry",
    "function_signature": "def process_entry(entry: dict) -> dict:",
    "function_body": (
        "    result = entry.get(\"payload\", {})\n"
        "    return result\n"
    ),
    "code_to_review": (
        "def process_entry(entry):\n"
        "    result = entry.get(\"payload\", {})\n"
        "    logger.info(\"Processing entry\")\n"
        "    return result\n"
    ),
    "code": (
        "def process_entry(entry):\n"
        "    result = entry.get(\"payload\", {})\n"
        "    return result\n"
    ),
    "error_message": "AttributeError: 'NoneType' object has no attribute 'get'",
    "intent": "Summarise a blackboard entry payload as a dict.",
    "pattern_id": "StatelessTransformer",
    "requirements": "Must include module docstring. Must include function docstring.",
    "context_str": "Body layer — stateless transformer worker.",
    "test_subject": "process_entry",
    "subject_code": (
        "def process_entry(entry: dict) -> dict:\n"
        "    \"\"\"Reads a blackboard entry payload and returns a summary dict.\"\"\"\n"
        "    result = entry.get(\"payload\", {})\n"
        "    return result\n"
    ),
    "existing_tests": "# No existing tests.",
    "refactor_goal": "Improve readability and add type hints.",
    "analysis_target": (
        "def process_entry(entry):\n"
        "    result = entry.get(\"payload\", {})\n"
        "    if result:\n"
        "        for k, v in result.items():\n"
        "            logger.info(\"%s=%s\", k, v)\n"
        "            logger.info(\"done\")\n"
        "    return result\n"
    ),
    "capability_name": "payload_summarizer",
    "capability_description": "Summarises blackboard entry payloads.",
    "symbols": '[{"name": "process_entry", "kind": "function", "description": ""}]',
    "question": "What does the CORE Body layer responsibility boundary forbid?",
    "user_message": "What does the Body layer do?",
    "conversation_history": "[]",
    # --- Extended fixtures (pass 2) ---
    "violations_json": (
        "[\n"
        "  {\n"
        "    \"rule_id\": \"purity.docstrings.required\",\n"
        "    \"file_path\": \"src/body/workers/example_worker.py\",\n"
        "    \"line\": 1,\n"
        "    \"message\": \"Missing module docstring.\",\n"
        "    \"severity\": \"error\"\n"
        "  },\n"
        "  {\n"
        "    \"rule_id\": \"purity.docstrings.required\",\n"
        "    \"file_path\": \"src/body/workers/example_worker.py\",\n"
        "    \"line\": 7,\n"
        "    \"message\": \"Missing function docstring on 'process_entry'.\",\n"
        "    \"severity\": \"error\"\n"
        "  }\n"
        "]"
    ),
    "module_name": "example_worker",
    "import_path": "body.workers.example_worker",
    "symbol_code": (
        "def process_entry(entry: dict) -> dict:\n"
        "    \"\"\"Reads a blackboard entry payload and returns a summary dict.\"\"\"\n"
        "    payload = entry.get(\"payload\", {})\n"
        "    return {\"keys\": list(payload.keys()), \"size\": len(payload)}\n"
    ),
    "test_name": "test_process_entry_returns_summary",
    "failure_type": "assertion_error",
    "test_code": (
        "def test_process_entry_returns_summary():\n"
        "    entry = {\"payload\": {\"a\": 1, \"b\": 2}}\n"
        "    result = process_entry(entry)\n"
        "    assert result == {\"keys\": [\"a\"], \"size\": 2}  # wrong: missing \"b\"\n"
    ),
    "original_code": (
        "# src/body/workers/example_worker.py\n"
        "from shared.logger import getLogger\n\n"
        "logger = getLogger(__name__)\n\n"
        "def process_entry(entry):\n"
        "    result = entry.get(\"payload\", {})\n"
        "    return result\n"
    ),
    "rel_path": "src/body/workers/example_worker.py",
    "strategy": "extract_helper",
    "improvement_ratio": "0.42",
    "current_code": (
        "# src/body/workers/example_worker.py\n"
        "from shared.logger import getLogger\n\n"
        "logger = getLogger(__name__)\n\n"
        "def process_entry(entry):\n"
        "    result = entry.get(\"payload\", {})\n"
        "    return result\n"
    ),
    "violation_messages": (
        "purity.docstrings.required: Missing module docstring.\n"
        "purity.docstrings.required: Missing function docstring on 'process_entry'."
    ),
    "pattern_requirements": (
        "Pattern: StatelessTransformer\n"
        "Requirements:\n"
        "  - Module MUST have a module-level docstring.\n"
        "  - Every public function MUST have a docstring.\n"
        "  - Functions MUST include type annotations on all parameters and return type."
    ),
    "layer": "body/workers",
    "line_count": "12",
    "content": (
        "# src/body/workers/example_worker.py\n"
        "from shared.logger import getLogger\n\n"
        "logger = getLogger(__name__)\n\n"
        "def process_entry(entry):\n"
        "    result = entry.get(\"payload\", {})\n"
        "    return result\n"
    ),
    "callers": (
        "[\n"
        "  {\"caller\": \"src/body/atomic/build_tests_action.py\", "
        "\"call_site\": \"process_entry(entry)\"},\n"
        "  {\"caller\": \"src/will/workers/test_runner_sensor.py\", "
        "\"call_site\": \"process_entry(entry)\"}\n"
        "]"
    ),
    "instruction": (
        "Validate that the generated code satisfies the StatelessTransformer pattern. "
        "The code must have a module docstring, a function docstring on every public "
        "function, and type annotations on all parameters and return values."
    ),
    "rationale": (
        "The file is classified as a Body-layer worker. StatelessTransformer is the "
        "governing pattern. The audit found 2 violations: missing docstrings."
    ),
    "code_content": (
        "# src/body/workers/example_worker.py\n"
        "from shared.logger import getLogger\n\n"
        "logger = getLogger(__name__)\n\n"
        "def process_entry(entry):\n"
        "    result = entry.get(\"payload\", {})\n"
        "    return result\n"
    ),
    "task_intent": (
        "Generate a stateless transformer worker that summarises a blackboard entry "
        "payload and returns a summary dict. The worker must follow CORE Body layer "
        "conventions."
    ),
    "task_type": "code_generation",
    "aspect": "constitutional_compliance",
    "policy_text": (
        "Rule purity.docstrings.required: Every public function and module in the "
        "Body layer MUST have a docstring. Violation severity: error. Auto-remediable."
    ),
    "intent_manifest": (
        "name: example_worker\n"
        "version: \"1.0\"\n"
        "layer: body/workers\n"
        "pattern: StatelessTransformer\n"
        "responsibilities:\n"
        "  - Read blackboard entry payload\n"
        "  - Return summary dict\n"
        "constraints:\n"
        "  - No direct database access\n"
        "  - No side effects"
    ),
    "worker_list": "[\"ExampleWorker\", \"BlackboardAuditorWorker\", \"TestRunnerSensor\"]",
    "document_count": "3",
    "document_path": ".intent/workers/example_worker.yaml",
    "document_yaml": (
        "name: ExampleWorker\n"
        "layer: body/workers\n"
        "pattern: StatelessTransformer\n"
        "responsibilities:\n"
        "  - Read blackboard entry payload\n"
        "  - Return summary dict"
    ),
    "user_goal": (
        "Add comprehensive docstrings to all public functions in "
        "src/body/workers/example_worker.py and ensure they comply with the "
        "StatelessTransformer pattern requirements."
    ),
    "policy_content": (
        "Rule purity.docstrings.required (severity: error):\n"
        "  Every module and public function in the Body layer must have a docstring.\n"
        "  Auto-remediable via fix.docstrings atomic action.\n"
        "\n"
        "Rule architecture.body.no_direct_db (severity: error):\n"
        "  Body layer workers must not import or call database session primitives\n"
        "  directly. All DB access must flow through the blackboard service."
    ),
    "action_descriptions_str": (
        "fix.docstrings: Injects missing docstrings into Python modules using the\n"
        "  DocstringWriter LLM role. Targets purity.docstrings.required violations.\n"
        "fix.format: Runs ruff format on files with formatting violations.\n"
        "fix.imports: Resolves missing or incorrect imports."
    ),
    "reconnaissance_report": (
        "{\n"
        "  \"target_file\": \"src/body/workers/example_worker.py\",\n"
        "  \"violations\": [\n"
        "    {\"rule_id\": \"purity.docstrings.required\", \"count\": 2},\n"
        "    {\"rule_id\": \"architecture.layer.no_cross_layer_import\", \"count\": 0}\n"
        "  ],\n"
        "  \"pattern\": \"StatelessTransformer\",\n"
        "  \"layer\": \"body/workers\",\n"
        "  \"complexity_score\": 0.12\n"
        "}"
    ),
    "audit_findings_summary": (
        "19 findings across 7 files. Dominant rule: purity.docstrings.required (8 "
        "violations). Secondary: architecture.body.no_direct_db (4 violations). "
        "3 files have zero violations. Remediation coverage: 14/19 auto-remediable."
    ),
    "finding_count": "19",
    "semantic_landscape": (
        "Cluster A (body/workers): 8 findings, mostly docstring violations.\n"
        "Cluster B (will/workers): 6 findings, mixed docstring and import violations.\n"
        "Cluster C (shared/): 5 findings, architecture boundary violations."
    ),
    "knowledge_gaps": (
        "- 2 rules with no remediation mapping (orphan rules).\n"
        "- IntentGuard scope for will/agents not yet defined.\n"
        "- TestGovernance paper not yet linked to test_coverage.yaml."
    ),
    "structural_health": (
        "Convergence rate: 1.4 findings resolved per day (last 7 days).\n"
        "New findings rate: 0.8 per day. System is converging.\n"
        "Governance debt: 19 open findings (down from 31 last week)."
    ),
    "change_context": (
        "Last 5 commits:\n"
        "  - feat: wire TestRunnerSensor to audit pipeline\n"
        "  - fix: deduplicate findings by subject not UUID\n"
        "  - feat: add repo_crawler worker\n"
        "  - fix: retire vector_sync_worker per ADR-018\n"
        "  - feat: close Band A — release v2.3.0"
    ),
    "intent_drift": (
        "No intent drift detected. All worker declarations in .intent/workers/ have "
        "corresponding implementations in src/will/workers/. 1 orphan atomic action "
        "detected: remediate_cognitive_role not registered in src/body/atomic/__init__.py."
    ),
    "constitution_summary": (
        "Active rule domains: purity (12 rules), architecture (8 rules), ai (6 rules), "
        "db (4 rules). Total: 30 active rules. 19 open violations. 11 rules with zero "
        "violations. Constitutional coverage: 54 PromptModel artifacts governed."
    ),
}


# Per-prompt fixture overrides. The global FIXTURES map is shared across
# prompts; values there must satisfy the lowest-common-denominator template.
# Some prompts (notably code-generation tasks) need a far more specific,
# CORE-domain task description to elicit CORE-specific output rather than a
# generic stub. Override keys here take precedence over FIXTURES for the
# named prompt only. Keys listed here are also treated as known placeholders
# by render_user_text — useful when model.yaml under-declares its inputs.
PER_PROMPT_FIXTURES: dict[str, dict[str, str]] = {
    "code_generation_task_step_prompt": {
        # model.yaml declares no input.required; user.txt references
        # {task_step}. The harness's global "task_step" fixture is the
        # terse, generic placeholder ("implement_payload_summarizer") that
        # invites generic-stub output — exactly the ADR-024 anti-pattern
        # (clarity_v2_refactor failure mode). The override below names a
        # real CORE file path, real CORE types, and a real CORE rule, so a
        # competent answer must speak CORE's actual vocabulary.
        "task_step": (
            "Implement the body-layer service method "
            "`HealthLogService.summarize_blackboard_silence(self, entries)` in "
            "`src/body/services/health_log_service.py`.\n\n"
            "Behaviour:\n"
            "- `entries` is a list of dicts; each has keys `worker_uuid` (str), "
            "`subject` (str), `seconds_silent` (int).\n"
            "- Group entries by `worker_uuid` and compute per worker: "
            "{\"max_silent_sec\": int, \"subjects\": list[str]}.\n"
            "- Return a `ComponentResult` (from `shared.models.component_result`) "
            "with `ok=True`, `data={\"by_worker\": <mapping>}`, "
            "`phase=ComponentPhase.EXECUTION` (from "
            "`shared.models.component_phase`), `component_id=self.component_id`, "
            "`confidence=1.0`, and `duration_sec` measured via "
            "`time.perf_counter()`.\n"
            "- If any entry is missing a required key, return "
            "`ComponentResult(ok=False, data={\"error\": <message>}, "
            "phase=ComponentPhase.EXECUTION, component_id=self.component_id)`.\n"
            "- Place a `# ID: <uuid v4>` comment on the line immediately before "
            "the method signature, per CORE's symbol-graph convention.\n"
            "- Body-layer rule `architecture.body.no_settings_access` forbids "
            "importing from `shared.infrastructure.settings`; any thresholds "
            "or config must arrive as method parameters or already-injected "
            "attributes on `self`.\n"
            "- The module already imports `from collections import defaultdict`, "
            "`import time`, `from shared.models.component_result import "
            "ComponentResult`, and `from shared.models.component_phase import "
            "ComponentPhase`. Do NOT add new imports.\n\n"
            "Output ONLY the method definition starting with the `# ID:` "
            "comment and the `def summarize_blackboard_silence(...)` line. "
            "No prose, no markdown fences."
        ),
    },
}


# Prompts whose model.yaml declares fewer inputs than the test would
# meaningfully need. They are not skipped — they run with what they declare —
# but their results should be read with caution. Recorded here so the report
# surfaces the gap to the governor.
UNDERDOCUMENTED_PROMPTS: dict[str, str] = {
    "clarity_v2_refactor": (
        "requires source_code context not declared in model.yaml — "
        "prompt is undertested with current fixtures."
    ),
    "code_generation_task_step_prompt": (
        "model.yaml declares no input.required and no must_contain; harness "
        "supplies {task_step} via PER_PROMPT_FIXTURES and treats the response "
        "as raw code (heuristic match on 'code_generation' in prompt name)."
    ),
}


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------


@dataclass
class PromptArtifact:
    name: str
    path: Path
    manifest: dict[str, Any]
    system_text: str
    user_template: str
    required_inputs: list[str]
    optional_inputs: list[str]
    output_format: str               # "raw_text" | "json"
    json_schema: dict[str, Any] | None
    must_contain: list[str]
    must_not_contain: list[str]
    role: str | None
    cognitive_role: str | None       # CORE cognitive role: LocalCoder, etc.

    @property
    def schema_required(self) -> list[str]:
        if not self.json_schema:
            return []
        return list(self.json_schema.get("required", []))

    @property
    def expects_code_output(self) -> bool:
        # Code expected when:
        #  - raw_text with python fences in must_contain
        #  - raw_text and prompt id matches code-producing pattern
        #  - json with "code" key in schema or '"code"' in must_contain
        if self.output_format == "json":
            if self.json_schema and "code" in self.json_schema.get("properties", {}):
                return True
            if any('"code"' in m for m in self.must_contain):
                return True
            return False
        if any("```python" in m or "```py" in m for m in self.must_contain):
            return True
        # heuristic by prompt id
        code_patterns = (
            "coder_", "_refactor", "_refactorer", "llm_correction_",
            "line_length_", "complexity_", "clarity_", "test_gen",
            "single_test_fixer", "simple_test_generator", "violation_remediator",
            "pattern_correction", "code_generation",
        )
        return any(p in self.name for p in code_patterns)

    @property
    def expects_docstring_only(self) -> bool:
        return self.name == "docstring_writer"


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    return [str(value)]


def load_prompt(name: str, path: Path) -> PromptArtifact | None:
    manifest_path = path / "model.yaml"
    system_path = path / "system.txt"
    user_path = path / "user.txt"

    if not (manifest_path.exists() and system_path.exists() and user_path.exists()):
        return None

    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        console.print(f"[yellow]WARN[/yellow] failed to parse {manifest_path}: {exc}")
        return None

    inputs = manifest.get("input", {}) or {}
    required_inputs = _coerce_str_list(inputs.get("required"))
    optional_inputs = _coerce_str_list(inputs.get("optional"))

    output = manifest.get("output", {}) or {}
    output_format_raw = str(output.get("format", "raw_text")).strip().lower()
    if output_format_raw in ("json", "json_object", "json_schema"):
        output_format = "json"
    else:
        output_format = "raw_text"

    json_schema = output.get("json_schema")
    if isinstance(json_schema, dict):
        # ensure type is set
        if "type" not in json_schema:
            json_schema = {**json_schema, "type": "object"}
    else:
        json_schema = None

    role = manifest.get("role")
    cog_role: str | None = None
    for cog, prompt_names in ROLE_PROMPTS.items():
        if name in prompt_names:
            cog_role = cog
            break

    return PromptArtifact(
        name=name,
        path=path,
        manifest=manifest,
        system_text=system_path.read_text(encoding="utf-8"),
        user_template=user_path.read_text(encoding="utf-8"),
        required_inputs=required_inputs,
        optional_inputs=optional_inputs,
        output_format=output_format,
        json_schema=json_schema,
        must_contain=_coerce_str_list(output.get("must_contain")),
        must_not_contain=_coerce_str_list(output.get("must_not_contain")),
        role=str(role) if role else None,
        cognitive_role=cog_role,
    )


def discover_prompts() -> list[PromptArtifact]:
    out: list[PromptArtifact] = []
    for entry in sorted(PROMPTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        artifact = load_prompt(entry.name, entry)
        if artifact is not None:
            out.append(artifact)
    return out


def render_user_text(artifact: PromptArtifact, fixtures: dict[str, str]) -> str:
    """
    Render user.txt using str.format_map. Missing keys raise KeyError; the
    caller is expected to have already filtered prompts whose required vars
    are absent from the fixture map. Templates may include literal '{' and
    '}' that are not Python format fields; we use a forgiving renderer that
    only substitutes recognised placeholder names.
    """
    # First, escape literal braces by doubling, then format. To stay safe with
    # complex templates (some include JSON skeletons with {{...}}), we do a
    # targeted substitution: replace {name} only when name is a known fixture
    # variable (required + optional).
    template = artifact.user_template
    # Treat every key actually supplied in `fixtures` as a known placeholder.
    # This covers prompts whose model.yaml under-declares inputs (e.g.,
    # code_generation_task_step_prompt) but whose user.txt still references
    # them; per-prompt fixture overlays land in `fixtures` and become
    # substitutable without needing to amend the artifact.
    known: set[str] = (
        set(artifact.required_inputs)
        | set(artifact.optional_inputs)
        | set(fixtures.keys())
    )

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        if var_name in known:
            return fixtures.get(var_name, "")
        return match.group(0)

    pattern = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
    return pattern.sub(_replace, template)


# ---------------------------------------------------------------------------
# Ollama client (mirrors OllamaProvider.chat_completion)
# ---------------------------------------------------------------------------


@dataclass
class OllamaResponse:
    raw: str
    latency_ms: float
    error: str | None = None


async def call_ollama(
    client: httpx.AsyncClient,
    model_name: str,
    system_text: str,
    user_text: str,
    output_format: str,
    json_schema: dict[str, Any] | None,
    max_tokens: int,
) -> OllamaResponse:
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_text or "You are a helpful assistant."},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "options": {"num_predict": max_tokens},
    }

    if output_format == "json":
        if isinstance(json_schema, dict) and json_schema:
            payload["format"] = json_schema
        else:
            payload["format"] = "json"

    endpoint = f"{OLLAMA_URL}/api/chat"
    started = time.perf_counter()
    try:
        response = await client.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT_SEC)
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return OllamaResponse(raw=content, latency_ms=elapsed_ms)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return OllamaResponse(raw="", latency_ms=elapsed_ms, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - top-level isolation
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return OllamaResponse(
            raw="",
            latency_ms=elapsed_ms,
            error=f"{type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


# Approximate stdlib whitelist for imports_clean check
STDLIB_MODULES: set[str] = set(getattr(sys, "stdlib_module_names", set())) | {
    "typing", "pytest", "unittest", "asyncio", "dataclasses", "pathlib",
    "json", "re", "ast", "os", "sys", "io", "datetime", "logging", "math",
    "collections", "functools", "itertools", "abc", "enum",
}
CORE_INTERNAL_PREFIXES = ("shared", "body", "will", "mind", "api", "cli", "src")


def _strip_code_fences(text: str) -> str:
    """Extract the first ```python ... ``` block, else return text."""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    return text


def _try_extract_code(prompt: PromptArtifact, raw: str) -> str | None:
    if not raw:
        return None
    if prompt.output_format == "json":
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
        if isinstance(parsed, dict) and "code" in parsed and isinstance(parsed["code"], str):
            return parsed["code"]
        return None
    # raw_text — try JSON-as-string first (violation_remediator pattern)
    if any('"code"' in m for m in prompt.must_contain):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("code"), str):
                return parsed["code"]
        except (json.JSONDecodeError, ValueError):
            pass
    # extract from code fences
    fenced = _strip_code_fences(raw)
    if fenced != raw:
        return fenced
    # whole text might be code
    return raw


def _check_imports_clean(code: str) -> bool:
    """Return True if every import is stdlib or starts with a CORE prefix."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Can't analyze imports if the code doesn't parse — return False so
        # imports_clean is FAIL when we can't verify. ast_valid catches the
        # parse failure separately.
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in STDLIB_MODULES or top in CORE_INTERNAL_PREFIXES:
                    continue
                return False
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # relative imports are fine (test scaffolding)
                continue
            if not node.module:
                continue
            top = node.module.split(".")[0]
            if top in STDLIB_MODULES or top in CORE_INTERNAL_PREFIXES:
                continue
            return False
    return True


def _detect_hard_constraint(system_text: str) -> bool:
    """Approximate detector for 'output ONLY ...' style constraints."""
    lower = system_text.lower()
    triggers = (
        "respond only", "output only", "return only",
        "only the docstring", "only the json", "only the code",
        "no code fences", "no preamble", "no explanation",
        "strict json",
    )
    return any(t in lower for t in triggers)


def _check_instruction_follow(prompt: PromptArtifact, raw: str) -> bool:
    if not raw:
        return False
    # must_contain / must_not_contain
    for s in prompt.must_contain:
        if s and s not in raw:
            return False
    for s in prompt.must_not_contain:
        if s and s in raw:
            return False
    if prompt.output_format == "json":
        stripped = raw.strip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            return False
    if prompt.expects_docstring_only:
        stripped = raw.strip()
        if not stripped.startswith('"""'):
            return False
    return True


def _no_prose_leak(raw: str) -> bool:
    stripped = raw.strip()
    if not stripped:
        return False
    return stripped[0] in ("{", "[")


# Sentinel for non-applicable dimensions
NA = "N/A"


def score_response(prompt: PromptArtifact, raw: str, error: str | None, latency_ms: float) -> dict[str, Any]:
    """Return a dict of dimension -> result. Binary dimensions use True/False/'N/A'."""
    dims: dict[str, Any] = {
        "latency_ms": round(latency_ms, 1),
        "output_chars": len(raw),
        "non_empty": bool(raw and raw.strip()),
    }

    if error:
        # error case — fail every applicable binary dimension
        dims.update(
            error=error,
            json_valid=False if prompt.output_format == "json" else NA,
            schema_fields=False if prompt.json_schema else NA,
            ast_valid=False if prompt.expects_code_output else NA,
            no_prose_leak=False if prompt.output_format == "json" else NA,
            has_code_field=False if (prompt.output_format == "json" or prompt.expects_code_output) else NA,
            imports_clean=False if prompt.expects_code_output else NA,
            instruction_follow=False,
        )
        return dims

    # json_valid
    json_parsed: Any = None
    if prompt.output_format == "json":
        try:
            json_parsed = json.loads(raw)
            dims["json_valid"] = True
        except (json.JSONDecodeError, ValueError):
            dims["json_valid"] = False
    else:
        dims["json_valid"] = NA

    # schema_fields
    if prompt.json_schema:
        if isinstance(json_parsed, dict):
            required = prompt.schema_required
            dims["schema_fields"] = all(k in json_parsed for k in required)
        else:
            dims["schema_fields"] = False
    else:
        dims["schema_fields"] = NA

    # no_prose_leak
    if prompt.output_format == "json":
        dims["no_prose_leak"] = _no_prose_leak(raw)
    else:
        dims["no_prose_leak"] = NA

    # has_code_field — only applicable when the prompt's JSON schema
    # declares a "code" property. For analysis/reasoning JSON outputs
    # (llm_gate, assumption_extractor, plan_goal, modularity_analyze, etc.)
    # that have no "code" key this dimension must be N/A, not False.
    _schema_has_code = bool(
        prompt.json_schema
        and "code" in (prompt.json_schema.get("properties") or {})
    )
    _must_contain_code = any('"code"' in m for m in prompt.must_contain)
    if prompt.output_format == "json" and (_schema_has_code or _must_contain_code):
        if isinstance(json_parsed, dict):
            dims["has_code_field"] = (
                "code" in json_parsed
                and isinstance(json_parsed["code"], str)
                and bool(json_parsed["code"].strip())
            )
        else:
            dims["has_code_field"] = False
    elif prompt.output_format != "json" and _must_contain_code:
        # raw_text prompt that requires a JSON-encoded code field
        # (violation_remediator pattern)
        try:
            jp = json.loads(raw)
            dims["has_code_field"] = (
                isinstance(jp, dict)
                and isinstance(jp.get("code"), str)
                and bool(jp["code"].strip())
            )
        except (json.JSONDecodeError, ValueError):
            dims["has_code_field"] = False
    else:
        dims["has_code_field"] = NA

    # ast_valid + imports_clean
    if prompt.expects_code_output:
        code_str = _try_extract_code(prompt, raw)
        if code_str is None or not code_str.strip():
            dims["ast_valid"] = False
            dims["imports_clean"] = False
        else:
            try:
                ast.parse(code_str)
                dims["ast_valid"] = True
                dims["imports_clean"] = _check_imports_clean(code_str)
            except SyntaxError:
                dims["ast_valid"] = False
                dims["imports_clean"] = False
    else:
        dims["ast_valid"] = NA
        dims["imports_clean"] = NA

    # instruction_follow
    dims["instruction_follow"] = _check_instruction_follow(prompt, raw)

    return dims


BINARY_DIMS_FOR_OVERALL = (
    "non_empty",
    "json_valid",
    "schema_fields",
    "ast_valid",
    "no_prose_leak",
    "has_code_field",
    "imports_clean",
    "instruction_follow",
)


def _is_pass(value: Any) -> bool | None:
    if value is True:
        return True
    if value is False:
        return False
    return None  # N/A


def aggregate_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate scores across N reps for a single (model, prompt) pair."""
    if not runs:
        return {"runs": 0}

    pass_rates: dict[str, float | str] = {}
    for dim in BINARY_DIMS_FOR_OVERALL:
        results = [_is_pass(r.get(dim)) for r in runs]
        non_na = [r for r in results if r is not None]
        if not non_na:
            pass_rates[dim] = "N/A"
        else:
            pass_rates[dim] = sum(1 for r in non_na if r) / len(non_na)

    latencies = [r.get("latency_ms", 0.0) for r in runs]
    chars = [r.get("output_chars", 0) for r in runs]

    # Consistency: identical pass/fail tuple across runs (binary dims only)
    verdict_tuples = [
        tuple(_is_pass(r.get(d)) for d in BINARY_DIMS_FOR_OVERALL)
        for r in runs
    ]
    consistency = len(set(verdict_tuples)) == 1

    # overall_score: mean of numeric (non-N/A) pass_rates
    numeric_rates = [v for v in pass_rates.values() if isinstance(v, (int, float))]
    overall = (sum(numeric_rates) / len(numeric_rates)) if numeric_rates else 0.0

    return {
        "runs": len(runs),
        "pass_rates": pass_rates,
        "avg_latency_ms": round(statistics.mean(latencies), 1),
        "p95_latency_ms": round(_percentile(latencies, 0.95), 1),
        "max_latency_ms": round(max(latencies), 1),
        "avg_output_chars": round(statistics.mean(chars), 1),
        "consistency": consistency,
        "overall_score": round(overall, 4),
        "errors": [r.get("error") for r in runs if r.get("error")],
    }


def _percentile(data: list[float], q: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * q
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------


@dataclass
class TestCase:
    prompt: PromptArtifact
    model_handle: str
    model_name: str
    fixture_context: dict[str, str]


@dataclass
class CaseResult:
    prompt_name: str
    cognitive_role: str | None
    model_handle: str
    runs: list[dict[str, Any]] = field(default_factory=list)
    aggregate: dict[str, Any] = field(default_factory=dict)


def build_test_cases(
    prompts: list[PromptArtifact],
    skip_log: list[dict[str, Any]],
) -> list[tuple[PromptArtifact, dict[str, str]]]:
    eligible: list[tuple[PromptArtifact, dict[str, str]]] = []
    for prompt in prompts:
        missing = [v for v in prompt.required_inputs if v not in FIXTURES]
        if missing:
            skip_log.append(
                {
                    "prompt": prompt.name,
                    "reason": "missing_fixture",
                    "missing_vars": missing,
                }
            )
            console.print(
                f"[yellow]WARN[/yellow] skip [bold]{prompt.name}[/bold] "
                f"— missing fixture vars: {', '.join(missing)}"
            )
            continue
        ctx = {v: FIXTURES[v] for v in prompt.required_inputs}
        for v in prompt.optional_inputs:
            if v in FIXTURES:
                ctx[v] = FIXTURES[v]
        # Per-prompt overlay (overrides any global fixture, and supplies
        # keys for prompts whose model.yaml under-declares its inputs).
        ctx.update(PER_PROMPT_FIXTURES.get(prompt.name, {}))
        eligible.append((prompt, ctx))
    return eligible


async def run_one_test(
    client: httpx.AsyncClient,
    prompt: PromptArtifact,
    fixture_ctx: dict[str, str],
    model_handle: str,
    model_name: str,
    rep_idx: int,
) -> dict[str, Any]:
    user_text = render_user_text(prompt, fixture_ctx)
    max_tokens = int((prompt.manifest.get("model") or {}).get("max_tokens", 4096))
    response = await call_ollama(
        client=client,
        model_name=model_name,
        system_text=prompt.system_text,
        user_text=user_text,
        output_format=prompt.output_format,
        json_schema=prompt.json_schema,
        max_tokens=max_tokens,
    )
    scores = score_response(prompt, response.raw, response.error, response.latency_ms)
    pass_marker = "PASS" if scores.get("non_empty") and not response.error else "FAIL"
    if response.error:
        pass_marker = f"ERR ({response.error[:60]}...)"
    console.print(
        f"[cyan][{model_handle}][/cyan] {prompt.name} "
        f"run {rep_idx}/{REPETITIONS} → {response.latency_ms:7.0f}ms {pass_marker}"
    )
    run_record = {
        "rep": rep_idx,
        "model_handle": model_handle,
        "raw_response": response.raw,
        "error": response.error,
        **scores,
    }
    return run_record


async def run_evaluation(
    eligible: list[tuple[PromptArtifact, dict[str, str]]],
) -> list[CaseResult]:
    results: list[CaseResult] = []
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SEC) as client:
        for handle, model_name in MODELS.items():
            for prompt, fixture_ctx in eligible:
                case = CaseResult(
                    prompt_name=prompt.name,
                    cognitive_role=prompt.cognitive_role,
                    model_handle=handle,
                )
                for rep in range(1, REPETITIONS + 1):
                    rec = await run_one_test(
                        client=client,
                        prompt=prompt,
                        fixture_ctx=fixture_ctx,
                        model_handle=handle,
                        model_name=model_name,
                        rep_idx=rep,
                    )
                    case.runs.append(rec)
                case.aggregate = aggregate_runs(case.runs)
                results.append(case)
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _qualification_label(score: float) -> str:
    if score >= 0.80:
        return "QUALIFIED"
    if score >= 0.60:
        return "BORDERLINE"
    return "DISQUALIFIED"


def _qualification_color(label: str) -> str:
    return {
        "QUALIFIED": "green",
        "BORDERLINE": "yellow",
        "DISQUALIFIED": "red",
    }.get(label, "white")


def render_per_prompt_table(results: list[CaseResult]) -> Table:
    table = Table(title="Per-Model × Per-Prompt Scores", show_lines=False)
    table.add_column("Prompt", style="cyan", no_wrap=True)
    table.add_column("Role")
    for handle in MODELS:
        table.add_column(f"{handle}\nscore", justify="right")
        table.add_column(f"{handle}\nlatency_ms", justify="right")

    by_prompt: dict[str, dict[str, CaseResult]] = {}
    for r in results:
        by_prompt.setdefault(r.prompt_name, {})[r.model_handle] = r

    for prompt_name in sorted(by_prompt):
        rows: list[str] = [prompt_name]
        any_role = next(iter(by_prompt[prompt_name].values())).cognitive_role or "-"
        rows.append(any_role)
        for handle in MODELS:
            case = by_prompt[prompt_name].get(handle)
            if not case:
                rows.extend(["-", "-"])
                continue
            score = case.aggregate.get("overall_score", 0.0)
            avg_lat = case.aggregate.get("avg_latency_ms", 0.0)
            color = _qualification_color(_qualification_label(score))
            rows.append(f"[{color}]{score:.2f}[/{color}]")
            rows.append(f"{avg_lat:.0f}")
        table.add_row(*rows)
    return table


def render_role_matrix(
    results: list[CaseResult],
    skipped_role_prompts: dict[str, list[str]],
) -> tuple[Table, dict[str, dict[str, dict[str, Any]]]]:
    matrix: dict[str, dict[str, dict[str, Any]]] = {}
    for cog_role, prompt_names in ROLE_PROMPTS.items():
        matrix[cog_role] = {}
        for handle in MODELS:
            relevant = [
                r for r in results
                if r.cognitive_role == cog_role and r.model_handle == handle
            ]
            if not relevant:
                matrix[cog_role][handle] = {
                    "label": "DISQUALIFIED",
                    "reason": "no testable prompts",
                    "score": 0.0,
                    "tested_prompts": 0,
                    "skipped": skipped_role_prompts.get(cog_role, []),
                }
                continue
            scores = [r.aggregate.get("overall_score", 0.0) for r in relevant]
            min_score = min(scores)
            mean_score = sum(scores) / len(scores)
            # qualifies if all prompts >= 0.80
            label = _qualification_label(min_score)
            matrix[cog_role][handle] = {
                "label": label,
                "min_score": round(min_score, 4),
                "mean_score": round(mean_score, 4),
                "tested_prompts": len(relevant),
                "expected_prompts": len(prompt_names),
                "skipped": skipped_role_prompts.get(cog_role, []),
            }

    table = Table(title="Role Qualification Matrix", show_lines=True)
    table.add_column("Cognitive Role", style="cyan", no_wrap=True)
    table.add_column("Coverage", justify="right")
    for handle in MODELS:
        table.add_column(handle, justify="center")

    for cog_role in ROLE_PROMPTS:
        coverage = (
            f"{matrix[cog_role][next(iter(MODELS))]['tested_prompts']}"
            f"/{matrix[cog_role][next(iter(MODELS))].get('expected_prompts', '?')}"
        )
        row = [cog_role, coverage]
        for handle in MODELS:
            cell = matrix[cog_role][handle]
            label = cell["label"]
            color = _qualification_color(label)
            min_s = cell.get("min_score", 0.0)
            row.append(f"[{color}]{label}\n(min={min_s:.2f})[/{color}]")
        table.add_row(*row)
    return table, matrix


def render_failure_summary(results: list[CaseResult]) -> str:
    lines: list[str] = []
    # detect persistent failure patterns per model
    per_model: dict[str, dict[str, list[str]]] = {handle: {} for handle in MODELS}
    for r in results:
        for dim in BINARY_DIMS_FOR_OVERALL:
            rate = r.aggregate.get("pass_rates", {}).get(dim)
            if isinstance(rate, (int, float)) and rate <= 0.34:
                per_model[r.model_handle].setdefault(dim, []).append(r.prompt_name)

    for handle, dim_map in per_model.items():
        if not dim_map:
            continue
        lines.append(f"\n[bold]{handle}[/bold] persistent failure patterns:")
        for dim, prompts in sorted(dim_map.items()):
            lines.append(f"  - {dim} fails on: {', '.join(prompts)}")
    return "\n".join(lines) if lines else "(no persistent failure patterns)"


def assign_models_to_roles(
    matrix: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, str]:
    """Pick the best model per cognitive role: prefer QUALIFIED, then highest mean."""
    assignments: dict[str, str] = {}
    for cog_role, by_handle in matrix.items():
        ranked = sorted(
            by_handle.items(),
            key=lambda kv: (
                0 if kv[1]["label"] == "QUALIFIED"
                else (1 if kv[1]["label"] == "BORDERLINE" else 2),
                -float(kv[1].get("mean_score", 0.0) or 0.0),
            ),
        )
        if not ranked:
            assignments[cog_role] = "(no candidate)"
            continue
        best_handle, best_cell = ranked[0]
        assignments[cog_role] = (
            f"{best_handle} ({best_cell['label']}, "
            f"mean={best_cell.get('mean_score', 0.0):.2f}, "
            f"tested={best_cell.get('tested_prompts', 0)}"
            f"/{best_cell.get('expected_prompts', 0)})"
        )
    return assignments


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def serialize_artifact(p: PromptArtifact) -> dict[str, Any]:
    return {
        "name": p.name,
        "role": p.role,
        "cognitive_role": p.cognitive_role,
        "output_format": p.output_format,
        "required_inputs": p.required_inputs,
        "optional_inputs": p.optional_inputs,
        "json_schema": p.json_schema,
        "must_contain": p.must_contain,
        "must_not_contain": p.must_not_contain,
    }


def serialize_case(c: CaseResult) -> dict[str, Any]:
    return {
        "prompt_name": c.prompt_name,
        "cognitive_role": c.cognitive_role,
        "model_handle": c.model_handle,
        "runs": c.runs,
        "aggregate": c.aggregate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CORE Ollama eval harness")
    parser.add_argument(
        "--only-role-mapped",
        action="store_true",
        default=True,
        help="Only test prompts in ROLE_PROMPTS (default: True).",
    )
    parser.add_argument(
        "--all-prompts",
        action="store_true",
        help="Override --only-role-mapped and test every prompt with all required fixtures.",
    )
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=None,
        metavar="NAME",
        help="Restrict the run to the named prompt artifact(s) (directory name "
             "under var/prompts/). Repeatable.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        metavar="HANDLE",
        help="Restrict the run to the named model handle(s) (keys of MODELS). "
             "Repeatable.",
    )
    args = parser.parse_args()

    # Apply --models filter in-place so the rest of the harness (which
    # iterates over the global MODELS dict in several places) honours it.
    if args.models:
        unknown = [h for h in args.models if h not in MODELS]
        if unknown:
            console.print(
                f"[red]ERROR[/red] unknown model handle(s): {', '.join(unknown)}. "
                f"Known: {', '.join(MODELS.keys())}"
            )
            return 2
        filtered = {h: MODELS[h] for h in args.models}
        MODELS.clear()
        MODELS.update(filtered)

    started_wall = time.perf_counter()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    console.rule("[bold cyan]CORE Ollama Eval Harness[/bold cyan]")
    console.print(f"Ollama: {OLLAMA_URL}")
    console.print(f"Models: {', '.join(MODELS.keys())}")
    console.print(f"Repetitions per (model, prompt): {REPETITIONS}")
    console.print(f"Results dir: {RESULTS_DIR}")

    all_prompts = discover_prompts()
    console.print(f"Discovered {len(all_prompts)} prompt artifacts in {PROMPTS_DIR}.")

    # Build the candidate set
    if args.all_prompts:
        candidates = all_prompts
    else:
        role_set: set[str] = set()
        for names in ROLE_PROMPTS.values():
            role_set.update(names)
        candidates = [p for p in all_prompts if p.name in role_set]

        # Track role-mapped prompts that don't exist on disk at all
        present = {p.name for p in all_prompts}
        missing_dirs = sorted(role_set - present)
        if missing_dirs:
            console.print(
                "[yellow]WARN[/yellow] role-mapped prompts not present as PromptModel "
                f"directories on disk: {', '.join(missing_dirs)}"
            )

    # --prompts narrows the candidate set further.
    if args.prompts:
        requested = set(args.prompts)
        present_names = {p.name for p in all_prompts}
        unknown = sorted(requested - present_names)
        if unknown:
            console.print(
                "[red]ERROR[/red] unknown prompt name(s) (no matching "
                f"directory under var/prompts/): {', '.join(unknown)}"
            )
            return 2
        candidates = [p for p in all_prompts if p.name in requested]
        console.print(
            f"[cyan]--prompts[/cyan] filter active: {len(candidates)} prompt(s) selected."
        )

    skip_log: list[dict[str, Any]] = []
    eligible = build_test_cases(candidates, skip_log)
    console.print(
        f"Eligible test cases: {len(eligible)} prompts × {len(MODELS)} models "
        f"× {REPETITIONS} reps = {len(eligible) * len(MODELS) * REPETITIONS} requests"
    )

    if not eligible:
        console.print("[red]No eligible test cases. Aborting.[/red]")
        return 1

    # Track skipped role prompts per cognitive role for the matrix
    skipped_role_prompts: dict[str, list[str]] = {}
    skipped_names = {s["prompt"] for s in skip_log}
    present = {p.name for p in all_prompts}
    for cog_role, names in ROLE_PROMPTS.items():
        skipped_for_role = [
            n for n in names if n in skipped_names or n not in present
        ]
        if skipped_for_role:
            skipped_role_prompts[cog_role] = skipped_for_role

    # Run
    console.rule("[bold]Executing tests[/bold]")
    results = asyncio.run(run_evaluation(eligible))

    elapsed_total = time.perf_counter() - started_wall

    # Tables
    console.rule("[bold]Results[/bold]")
    table1 = render_per_prompt_table(results)
    console.print(table1)

    table2, matrix = render_role_matrix(results, skipped_role_prompts)
    console.print(table2)

    # Summary narrative
    console.rule("[bold]Summary[/bold]")
    assignments = assign_models_to_roles(matrix)
    assign_lines = ["[bold]Recommended model per cognitive role:[/bold]"]
    for cog_role, choice in assignments.items():
        assign_lines.append(f"  {cog_role:18} → {choice}")
    console.print(Panel("\n".join(assign_lines), title="Role Assignments"))

    if skip_log:
        skip_lines = ["[yellow]Skipped prompts (missing fixtures):[/yellow]"]
        for s in skip_log:
            skip_lines.append(
                f"  - {s['prompt']}: missing {', '.join(s['missing_vars'])}"
            )
        console.print(Panel("\n".join(skip_lines), title="Coverage Gaps"))

    if UNDERDOCUMENTED_PROMPTS:
        under_lines = ["[yellow]Undertested prompts (model.yaml under-declares inputs):[/yellow]"]
        for name, note in UNDERDOCUMENTED_PROMPTS.items():
            under_lines.append(f"  - {name}: {note}")
        console.print(Panel("\n".join(under_lines), title="Coverage Caveats"))

    failure_summary = render_failure_summary(results)
    console.print(Panel(failure_summary, title="Failure Patterns"))

    console.print(f"\n[bold]Total wall time:[/bold] {elapsed_total:.1f} s")

    # Write JSON results
    out_path = RESULTS_DIR / f"results_{timestamp}.json"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ollama_url": OLLAMA_URL,
        "models": MODELS,
        "repetitions": REPETITIONS,
        "request_timeout_sec": REQUEST_TIMEOUT_SEC,
        "wall_time_sec": round(elapsed_total, 2),
        "prompts_tested": [serialize_artifact(p) for p, _ in eligible],
        "skipped_prompts": skip_log,
        "underdocumented_prompts": UNDERDOCUMENTED_PROMPTS,
        "skipped_role_prompts": skipped_role_prompts,
        "missing_role_prompt_dirs": sorted(
            {n for names in ROLE_PROMPTS.values() for n in names}
            - {p.name for p in all_prompts}
        ),
        "results": [serialize_case(c) for c in results],
        "role_qualification_matrix": matrix,
        "role_assignments": assignments,
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    console.print(f"\n[green]JSON results written to:[/green] {out_path}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n[red]Interrupted by user.[/red]")
        sys.exit(130)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
