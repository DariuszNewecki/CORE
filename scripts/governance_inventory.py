#!/usr/bin/env python3
"""scripts/governance_inventory.py — what in .intent/ and .specs/ is used.

Phase 1 of the governance-text reduction: measure only. Classifies every
.intent/ rule, every .intent/ file and every .specs/ file by whether it is
enforced or used, so later phases can delete on evidence.

Classes (each row has exactly one; precedence is top to bottom):

  rules       ADVISORY      declared ``enforcement: advisory``
              UNMAPPED      no entry in .intent/enforcement/mappings/
              MAPPED-INERT  mapped, but absent from the audit run's
                            ``executed_rule_ids``, or its engine is passive
                            (always OK: passive_gate and the aliases in
                            .intent/taxonomies/substrate_enforcement.yaml)
              ENFORCED      in ``executed_rule_ids`` of an offline
                            ``core-admin code audit`` on this tree
  .intent/    LOADED        a src/*.py path reference reaches the file
              NOT-LOADED    otherwise
  .specs/     RUNTIME       a src/*.py path reference reaches the file
              TEST          a tests/*.py path reference reaches the file
              CITED-BY-INTENT      named from an .intent/ file
              CITED-BY-SPECS-ONLY  named only from other .specs/ files
              ORPHAN        named by nothing

A "path reference" is a string literal in Python code (docstrings and
comments excluded; ``a / "b" / "c"`` joined to ``a/b/c``) that equals the
file's path (with or without the ``.intent/`` / ``.specs/`` prefix), ends
with it, names a directory that contains it, or is a glob that matches it.
References to the tree root itself (``.intent``, ``.specs``, ``**/*``) are
not counted: they are whole-tree machinery (copying, hashing, header
validation, search indexing), not use of a particular file.

Citations (.specs/ rows) are the file's path, its file name, or for ADRs the
id (``ADR-050``), anywhere in the citing file's text.

Prose lines (.intent/ files): comment lines, plus lines under keys such as
``description`` or ``rationale`` that no src/ code reads (no ``x["key"]`` or
``x.get("key")`` in src/), plus every line of an .md file nothing loads.

Findings: blackboard findings per rule in the 90 days before ``--as-of``
(default: the tree's HEAD commit time, so the same tree gives the same
window). Read-only transaction. ``--no-db`` leaves the column empty.

Deterministic: rows sorted, no timestamps in the output, same tree (and
same database history) -> same bytes.

Usage (from the repository root, development venv):
  python scripts/governance_inventory.py                 # writes the CSV
  python scripts/governance_inventory.py --self-test     # proves reclassification
"""

from __future__ import annotations

import argparse
import ast
import csv
import fnmatch
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import yaml


DEFAULT_OUT = "scripts/governance_inventory.csv"
PROSE_KEY_CANDIDATES = (
    "comment",
    "comments",
    "description",
    "explanation",
    "note",
    "notes",
    "purpose",
    "rationale",
    "summary",
)
WHOLE_TREE = {"", ".", "*", "**", "**/*", "*.md", "*.yaml", "*.yml", "*.json"}
COLUMNS = [
    "kind",
    "id_or_path",
    "class",
    "detail",
    "file",
    "lines",
    "prose_lines",
    "findings_90d",
    "adr_status",
    "superseded_by_later_adr",
    "evidence",
    "strict_use",
    "keep_reason",
    "intent_requires",
]

# .specs/ files that have no strict use but whose deletion broke runtime
# behaviour (phase 2). Path -> what breaks without it.
KEEP: dict[str, str] = {
    ".specs/META/charter.header.schema.json": (
        "header schema loaded by specs_doc_validator via an artifact type's schema_ref; law check-tree refuses without it"
    ),
    ".specs/META/northstar.header.schema.json": (
        "header schema loaded by specs_doc_validator via an artifact type's schema_ref; law check-tree refuses without it"
    ),
    ".specs/META/planning.header.schema.json": (
        "header schema loaded by specs_doc_validator via an artifact type's schema_ref; law check-tree refuses without it"
    ),
    ".specs/META/requirement.header.schema.json": (
        "header schema loaded by specs_doc_validator via an artifact type's schema_ref; law check-tree refuses without it"
    ),
    ".specs/northstar/CORE - What It Does.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Action.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Adaptive-Workflow-Pattern.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Authority-Without-Registries.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Blackboard.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Canary.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-ConservationGate.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-ConstitutionalEnvelope.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-ConsumerWorker.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Context-Packet-Doctrine.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Crate.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Evidence-as-Input.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Finding.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Gate.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-IntentGuard.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-IntentRepository.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Proposal.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Remediation.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-RemediationMap.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-RemediatorWorker.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Rule-Evaluation-Semantics.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-ShopManager.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-The-Octopus-UNIX-Synthesis.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-ViolationExecutor.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-ViolationSensor.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Workers-and-Governance-Model.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
    ".specs/papers/CORE-Workflow-Stages.md": (
        "named as authoritative_paper in .intent/META/vocabulary.json; blocking rule governance.vocabulary.authoritative_source_must_be_paper fails without it"
    ),
}


# --------------------------------------------------------------------------
# tree walking


def _files(root: Path, top: str) -> list[str]:
    out = []
    for dirpath, _dirs, names in os.walk(root / top):
        for name in names:
            out.append((Path(dirpath) / name).relative_to(root).as_posix())
    return sorted(out)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _line_count(text: str) -> int:
    return len(text.splitlines())


# --------------------------------------------------------------------------
# path references in Python code


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def _name_env(tree: ast.AST) -> dict[str, list[str]]:
    """Names bound to path strings in this file: module- and function-level
    ``NAME = "x"`` / ``NAME = a / "x"`` and ``for NAME in ("x", Y)``. Unknown
    parts are NUL (see _div_chain); a name bound twice keeps every value."""
    env: dict[str, list[str]] = defaultdict(list)
    for _ in range(2):  # a second pass resolves names defined from names
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                values = _values(node.value, env)
                if values and any(v != "\0" for v in values):
                    env[node.targets[0].id] = sorted(set(values))
            elif (
                isinstance(node, ast.For)
                and isinstance(node.target, ast.Name)
                and isinstance(node.iter, (ast.Tuple, ast.List, ast.Set))
            ):
                values = [v for el in node.iter.elts for v in _values(el, env)]
                if values and all(v != "\0" for v in values):
                    env[node.target.id] = sorted(set(values))
    return env


def _values(node: ast.AST, env: dict[str, list[str]]) -> list[str]:
    """Possible string values of a path expression; NUL for unknown parts."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return [
            f"{a}/{b}"
            for a in _values(node.left, env)
            for b in _values(node.right, env)
        ]
    return ["\0"]


def _div_chain(
    node: ast.AST, env: dict[str, list[str]] | None = None
) -> list[str] | None:
    """Path strings of ``a / "x" / NAME``, names resolved through ``env``;
    None if no part is known."""
    out = []
    for joined in _values(node, env or {}):
        pieces = joined.split("\0")
        for i, piece in enumerate(pieces):
            seg = re.sub(r"/{2,}", "/", piece).strip("/")
            if not seg:
                continue
            # ``base / "dir" / name``: the code reads one child of dir, not the
            # whole subtree. PARAM marks "one level below, name unknown".
            out.append(seg + "/" + PARAM if i < len(pieces) - 1 else seg)
    return out or None


PATH_CALLS = {
    "Path",
    "PurePath",
    "joinpath",
    "glob",
    "rglob",
    "iterdir",
    "open",
    "read_text",
    "resolve_rel",
    "law_path",
    "law_glob",
    "load_text",
    "load_document",
    "iter_documents",
    "load_policy",
    "load_workflow",
    "load_worker",
    "load_phase",
    "exists",
    "is_file",
    "is_dir",
}
DATA_SUFFIXES = (".yaml", ".yml", ".json", ".jsonl", ".md")
PARAM = "\x01"
MANIFEST = ".intent/governance/namespace_manifest.yaml"


def _call_name(node: ast.Call) -> str:
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def python_references(
    root: Path, top: str
) -> tuple[dict[str, set[str]], set[str], dict[str, set[str]]]:
    """Path-like literals {literal: {files}}, dict keys read via [..]/.get(..),
    and the literals that reach a path operation {literal: {files}}.

    A literal is path-like when it contains "/", ends with a data suffix, is a
    segment of an ``a / "b"`` chain, or is an argument of a path call
    (``iter_documents(under="workers")``, ``resolve_rel("x.yaml")``).
    """
    refs: dict[str, set[str]] = defaultdict(set)
    path_refs: dict[str, set[str]] = defaultdict(set)
    read_keys: set[str] = set()
    for rel in _files(root, top):
        if not rel.endswith(".py"):
            continue
        try:
            tree = ast.parse(_read(root / rel))
        except SyntaxError:
            continue
        docs = _docstring_ids(tree)
        env = _name_env(tree)
        path_context: set[int] = set()
        inner_div = {
            id(child)
            for node in ast.walk(tree)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
            for child in (node.left, node.right)
            if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Div)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.Div)
                and id(node) not in inner_div
            ):
                for seg in _div_chain(node, env) or []:
                    refs[seg].add(rel)
                    path_refs[seg].add(rel)
            elif isinstance(node, ast.Call) and _call_name(node) in PATH_CALLS:
                for arg in [*node.args, *(k.value for k in node.keywords)]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        path_context.add(id(arg))
                    if isinstance(arg, (ast.Constant, ast.Name, ast.BinOp)):
                        for seg in _div_chain(arg, env) or []:
                            path_refs[seg].add(rel)
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                if isinstance(node.slice.value, str):
                    read_keys.add(node.slice.value)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("get", "pop", "setdefault")
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                read_keys.add(node.args[0].value)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
                and len(node.value) <= 300
                and "\n" not in node.value
                and " " not in node.value.strip()
            ):
                v = node.value
                if "/" in v or v.endswith(DATA_SUFFIXES) or id(node) in path_context:
                    refs[v].add(rel)
    return refs, read_keys, path_refs


def _norm(literal: str, tree: str) -> str:
    """A literal as a path relative to ``tree`` (".intent" / ".specs").

    ``<anything>/.specs/x`` is cut after the tree name; a literal without it
    is taken as relative to the tree root (``resolve_rel("workers/x.yaml")``).
    """
    s = literal.strip()
    while s.startswith("./"):
        s = s[2:]
    if s == tree:
        return ""
    marker = tree + "/"
    if marker in s:
        s = s[s.rindex(marker) + len(marker) :]
    return s.rstrip("/")


def references_to(rel_in_tree: str, tree: str, refs: dict[str, set[str]]) -> set[str]:
    """Files whose path-like literals reach ``tree/rel_in_tree``: the path,
    a path ending in it, a directory containing it, or a glob matching it."""
    hits: set[str] = set()
    name = Path(rel_in_tree).name
    for literal, users in refs.items():
        explicit = literal.strip().lstrip("./").startswith(
            tree.lstrip(".") + "/"
        ) or literal.startswith(tree + "/")
        cand = _norm(literal, tree)
        if cand.endswith("/" + PARAM):
            parent = cand[: -len(PARAM) - 1]
            if parent not in WHOLE_TREE and str(Path(rel_in_tree).parent) == parent:
                hits |= users
            continue
        if cand in WHOLE_TREE or cand.startswith(("/", "..")):
            continue
        if "*" in cand:
            # A glob says nothing about this tree unless it is anchored in it:
            # the tree prefix, a literal first segment, or an ADR-/CORE- name.
            anchored = explicit or "*" not in cand.split("/")[0]
            if anchored and fnmatch.fnmatchcase(rel_in_tree, cand):
                hits |= users
            elif (
                "/" not in cand
                and fnmatch.fnmatchcase(name, cand)
                and (explicit or cand.startswith(("ADR-", "CORE-")))
            ):
                hits |= users
        elif cand == rel_in_tree or rel_in_tree.startswith(cand + "/"):
            hits |= users
        elif cand == name and len(name) > 12:
            hits |= users
    return hits


def named_references(
    rel_in_tree: str, tree: str, refs: dict[str, set[str]]
) -> set[str]:
    """Files that name ``tree/rel_in_tree`` itself: its full path. Directory sweeps, globs and parametrised joins
    (``decisions / f"{adr}.md"``) are not a reference to this file."""
    hits: set[str] = set()
    for literal, users in refs.items():
        if "*" in literal or literal.endswith(PARAM):
            continue
        cand = _norm(literal, tree)
        # The full tree-relative path, not a bare file name: ``seed_dir /
        # "assignments.yaml"`` reads that name in whatever directory it is given.
        if cand == rel_in_tree and ("/" in cand or "/" not in rel_in_tree):
            hits |= users
    return hits


# --------------------------------------------------------------------------
# .intent/ rules


def _compose(text: str) -> yaml.Node | None:
    try:
        return yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return None


def _span(node: yaml.Node) -> set[int]:
    end = node.end_mark.line
    if node.end_mark.column == 0 and end > node.start_mark.line:
        end -= 1
    return set(range(node.start_mark.line, end + 1))


def _find_mappings(node: yaml.Node, path: str, out: dict[str, tuple[str, str]]) -> None:
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            if k.value == "mappings" and isinstance(v, yaml.MappingNode):
                for rk, rv in v.value:
                    engine = ""
                    if isinstance(rv, yaml.MappingNode):
                        for ek, ev in rv.value:
                            if ek.value == "engine" and isinstance(ev, yaml.ScalarNode):
                                engine = ev.value
                    out[rk.value] = (path, engine)
            else:
                _find_mappings(v, path, out)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _find_mappings(item, path, out)


def collect_rules(root: Path) -> list[dict]:
    rules = []
    for rel in _files(root, ".intent/rules"):
        if not rel.endswith(".json"):
            continue
        node = _compose(_read(root / rel))
        if not isinstance(node, yaml.MappingNode):
            continue
        for k, v in node.value:
            if k.value != "rules" or not isinstance(v, yaml.SequenceNode):
                continue
            for item in v.value:
                if not isinstance(item, yaml.MappingNode):
                    continue
                fields = {
                    fk.value: fv.value
                    for fk, fv in item.value
                    if isinstance(fv, yaml.ScalarNode)
                }
                if "id" in fields:
                    rules.append(
                        {
                            "id": fields["id"],
                            "file": rel,
                            "enforcement": fields.get("enforcement", ""),
                            "lines": len(_span(item)),
                        }
                    )
    return rules


def collect_mappings(root: Path) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for rel in _files(root, ".intent/enforcement/mappings"):
        if rel.endswith((".yaml", ".yml")):
            node = _compose(_read(root / rel))
            if node is not None:
                _find_mappings(node, rel, out)
    return out


def passive_engines(root: Path) -> set[str]:
    doc = yaml.safe_load(_read(root / ".intent/taxonomies/substrate_enforcement.yaml"))
    return {"passive_gate", *((doc or {}).get("entries") or {}).keys()}


def run_audit(root: Path) -> dict:
    exe = Path(sys.executable).with_name("core-admin")
    env = {**os.environ, "REPO_PATH": str(root), "PYTHONPATH": str(root / "src")}
    proc = subprocess.run(
        [str(exe), "code", "audit", "--offline", "--format=json"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(proc.stdout)
    except ValueError:
        sys.exit(
            f"audit produced no JSON (rc={proc.returncode}):\n{proc.stderr[-2000:]}"
        )


# --------------------------------------------------------------------------
# findings (read-only)


def findings_90d(root: Path, as_of: datetime) -> dict[str, int]:
    import asyncio

    from sqlalchemy import text

    from shared.infrastructure.database.session_manager import get_session

    query = text(
        """
        SELECT split_part(subject, '::', 1) AS a, split_part(subject, '::', 2) AS b,
               count(*)
        FROM core.blackboard_entries
        WHERE entry_type = 'finding'
          AND created_at >= :start AND created_at < :end
        GROUP BY 1, 2
        """
    )

    async def fetch() -> list[tuple[str, str, int]]:
        async with get_session() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            rows = await session.execute(
                query, {"start": as_of - timedelta(days=90), "end": as_of}
            )
            result = [(r[0], r[1], r[2]) for r in rows]
            await session.rollback()
            return result

    counts: dict[str, int] = defaultdict(int)
    for a, b, n in asyncio.run(fetch()):
        counts[a] += n
        if b and b != a:
            counts[b] += n
    return counts


# --------------------------------------------------------------------------
# .specs/ citations and ADR metadata

ADR_ID = re.compile(r"\bADR-(\d{1,4})\b")


def _adr_key(num: str) -> str:
    return f"ADR-{int(num):03d}"


def adr_metadata(root: Path, specs: list[str]) -> dict[str, dict]:
    meta: dict[str, dict] = {}
    supersedes: dict[str, set[str]] = defaultdict(set)
    for rel in specs:
        name = Path(rel).name
        m = re.match(r"ADR-(\d+)", name)
        if not rel.startswith(".specs/decisions/") or not m:
            continue
        key = _adr_key(m.group(1))
        text = _read(root / rel)
        status = ""
        fm = re.match(r"---\n(.*?)\n---", text, re.S)
        if fm:
            s = re.search(r"^status:\s*(\S+)", fm.group(1), re.M)
            status = s.group(1).lower() if s else ""
        if not status:
            s = re.search(r"^\*\*Status:\*\*\s*([A-Za-z]+)", text, re.M)
            status = s.group(1).lower() if s else ""
        if status not in ("accepted", "superseded"):
            status = f"other:{status or 'none'}"
        meta[rel] = {"key": key, "status": status, "superseded_by": set()}
        for line in re.findall(r"^\*\*Supersedes:\*\*(.*)$", text, re.M):
            for num in ADR_ID.findall(line):
                if _adr_key(num) != key:
                    supersedes[_adr_key(num)].add(key)
        for line in re.findall(
            r"^\*\*Superseded by:\*\*(.*)$|^Superseded by (.*)$", text, re.M
        ):
            for num in ADR_ID.findall(" ".join(line)):
                meta[rel]["superseded_by"].add(_adr_key(num))
    for rel, m in meta.items():
        later = {
            k
            for k in supersedes.get(m["key"], set()) | m["superseded_by"]
            if k > m["key"]
        }
        m["superseded_by"] = later
    return meta


def citations(target: str, texts: dict[str, str], adr_key: str | None) -> set[str]:
    name = Path(target).name
    inner = target[len(".specs/") :]
    stem = Path(name).stem
    hits = set()
    for rel, text in texts.items():
        if rel == target:
            continue
        if inner in text or (len(name) > 8 and name in text):
            hits.add(rel)
        elif stem.startswith("CORE-") and re.search(rf"\b{re.escape(stem)}\b", text):
            hits.add(rel)
        elif adr_key and re.search(rf"\bADR-0*{int(adr_key[4:])}\b", text):
            hits.add(rel)
    return hits


# --------------------------------------------------------------------------
# prose lines in .intent/ files


def prose_lines(text: str, rel: str, prose_keys: set[str], loaded: bool) -> int:
    if rel.endswith(".md"):
        return 0 if loaded else sum(1 for line in text.splitlines() if line.strip())
    lines: set[int] = set()
    if rel.endswith((".yaml", ".yml")):
        for i, line in enumerate(text.splitlines()):
            if line.lstrip().startswith("#"):
                lines.add(i)
    if rel.endswith((".yaml", ".yml", ".json")):
        node = _compose(text)

        def walk(n: yaml.Node) -> None:
            if isinstance(n, yaml.MappingNode):
                for k, v in n.value:
                    if isinstance(k, yaml.ScalarNode) and k.value in prose_keys:
                        lines.update(_span(k) | _span(v))
                    else:
                        walk(v)
            elif isinstance(n, yaml.SequenceNode):
                for item in n.value:
                    walk(item)

        if node is not None:
            walk(node)
    return len(lines)


# --------------------------------------------------------------------------
# inventory


def build(root: Path, audit: dict, findings: dict[str, int] | None) -> list[list[str]]:
    rows: list[list[str]] = []
    src_refs, read_keys, src_paths = python_references(root, "src")
    test_refs, _, test_paths = python_references(root, "tests")
    prose_keys = {k for k in PROSE_KEY_CANDIDATES if k not in read_keys}

    # rules
    executed = set(audit.get("executed_rule_ids") or [])
    skipped = {
        r["rule_id"]: r.get("reason", "") for r in audit.get("skipped_rules") or []
    }
    mappings = collect_mappings(root)
    passive = passive_engines(root)
    seen: set[str] = set()
    for rule in sorted(collect_rules(root), key=lambda r: r["id"]):
        rid = rule["id"]
        if rid in seen:
            sys.exit(f"duplicate rule id {rid}")
        seen.add(rid)
        mapping = mappings.get(rid)
        engine = mapping[1] if mapping else ""
        if rule["enforcement"] == "advisory":
            cls, detail = "ADVISORY", f"mapped:{engine}" if mapping else "no mapping"
        elif not mapping:
            cls, detail = "UNMAPPED", rule["enforcement"]
        elif engine in passive:
            cls, detail = (
                "MAPPED-INERT",
                f"{rule['enforcement']}; passive engine {engine} always returns OK",
            )
        elif rid not in executed:
            why = skipped.get(rid, "not in executed_rule_ids")
            cls, detail = (
                "MAPPED-INERT",
                f"{rule['enforcement']}; {engine}; did not execute: {why}",
            )
        else:
            cls, detail = "ENFORCED", f"{rule['enforcement']}; {engine}"
        rows.append(
            [
                "rule",
                rid,
                cls,
                detail,
                rule["file"],
                str(rule["lines"]),
                "",
                "" if findings is None else str(findings.get(rid, 0)),
                "",
                "",
                mapping[0] if mapping else "",
                "",
                "",
                "",
            ]
        )

    # .intent/ files
    for rel in _files(root, ".intent"):
        inner = rel[len(".intent/") :]
        users = references_to(inner, ".intent", src_refs)
        text = _read(root / rel)
        cls = "LOADED" if users else "NOT-LOADED"
        rows.append(
            [
                "intent-file",
                rel,
                cls,
                "",
                rel,
                str(_line_count(text)),
                str(prose_lines(text, rel, prose_keys, bool(users))),
                "",
                "",
                "",
                ";".join(sorted(users)),
                "",
                "",
                "",
            ]
        )

    # .specs/ files
    specs = _files(root, ".specs")
    intent_texts = {rel: _read(root / rel) for rel in _files(root, ".intent")}
    spec_texts = {rel: _read(root / rel) for rel in specs}
    adrs = adr_metadata(root, specs)
    for rel in specs:
        inner = rel[len(".specs/") :]
        text = spec_texts[rel]
        adr = adrs.get(rel)
        runtime = references_to(inner, ".specs", src_refs)
        tests = references_to(inner, ".specs", test_refs)
        key = adr["key"] if adr else None
        by_intent = citations(rel, intent_texts, key)
        by_specs = citations(rel, spec_texts, key)
        # STRICT_USE: a specific src/ or tests/ file opens this file by its
        # full path (the literal reaches a path operation, not just a string).
        # Not use: the namespace manifest (it lists every file), folder
        # sweeps, and citations from .intent/ or other .specs/ files.
        strict = sorted(
            named_references(inner, ".specs", src_paths)
            | named_references(inner, ".specs", test_paths)
        )
        # .intent/ files that need this file: its full path in law data (not
        # the register MANIFEST, the append-only ledger or prose .md), or its
        # file name in a rule (a rule citing it as the doctrine it retains).
        requires = sorted(
            f
            for f, body in intent_texts.items()
            if f != MANIFEST
            and f.endswith((".yaml", ".yml", ".json"))
            and (
                rel in body
                or (f.startswith(".intent/rules/") and Path(rel).name in body)
            )
        )
        detail = ""
        if by_intent == {MANIFEST}:
            # The namespace manifest registers every .specs/ file by path; it
            # is a listing, not a use. Say what the file is without it.
            detail = (
                "listed only in "
                + MANIFEST
                + "; without it: "
                + ("CITED-BY-SPECS-ONLY" if by_specs else "ORPHAN")
            )
        if runtime:
            cls, ev = "RUNTIME", runtime
        elif tests:
            cls, ev = "TEST", tests
        elif by_intent:
            cls, ev = "CITED-BY-INTENT", by_intent
        elif by_specs:
            cls, ev = "CITED-BY-SPECS-ONLY", by_specs
        else:
            cls, ev = "ORPHAN", set()
        rows.append(
            [
                "spec",
                rel,
                cls,
                detail if cls == "CITED-BY-INTENT" else "",
                rel,
                str(_line_count(text)),
                "",
                "",
                adr["status"] if adr else "",
                ";".join(sorted(adr["superseded_by"])) if adr else "",
                ";".join(sorted(ev)),
                "true" if strict else "false",
                KEEP.get(rel, ""),
                ";".join(requires),
            ]
        )

    n_intent = sum(1 for r in rows if r[0] == "intent-file")
    n_specs = sum(1 for r in rows if r[0] == "spec")
    if n_intent != len(_files(root, ".intent")) or n_specs != len(specs):
        sys.exit("row count does not match the file count")
    if len({(r[0], r[1]) for r in rows}) != len(rows):
        sys.exit("a row appears twice")
    return rows


def render(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS)
    order = {"rule": 0, "intent-file": 1, "spec": 2}
    for row in sorted(rows, key=lambda r: (order[r[0]], r[1])):
        w.writerow(row)
    return buf.getvalue()


def summary(rows: list[list[str]]) -> str:
    out = []
    for kind in ("rule", "intent-file", "spec"):
        tally: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        for r in rows:
            if r[0] == kind:
                t = tally[r[2]]
                t[0] += 1
                t[1] += int(r[5] or 0)
                t[2] += int(r[6] or 0)
        parts = [f"{c} {n} ({ln} lines)" for c, (n, ln, _p) in sorted(tally.items())]
        out.append(f"{kind}: " + ", ".join(parts))
    return "\n".join(out)


def _as_of(root: Path, given: str | None) -> datetime:
    if given:
        return datetime.fromisoformat(given)
    stamp = subprocess.run(
        ["git", "log", "-1", "--format=%cI"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    if not stamp:
        sys.exit("no git HEAD: pass --as-of")
    return datetime.fromisoformat(stamp)


# --------------------------------------------------------------------------
# self-test


def _cut_mapping(root: Path, mapping_file: str, rule_id: str) -> None:
    path = root / mapping_file
    text = _read(path)
    node = _compose(text)
    lines = text.splitlines(keepends=True)

    def find(n: yaml.Node) -> tuple[int, int] | None:
        if isinstance(n, yaml.MappingNode):
            for k, v in n.value:
                if k.value == rule_id:
                    return k.start_mark.line, max(_span(v))
                hit = find(v)
                if hit:
                    return hit
        return None

    start, end = find(node)
    del lines[start : end + 1]
    path.write_text("".join(lines), encoding="utf-8")


def _strict(root: Path, rel: str) -> bool:
    inner = rel[len(".specs/") :]
    return bool(
        named_references(inner, ".specs", python_references(root, "src")[2])
        | named_references(inner, ".specs", python_references(root, "tests")[2])
    )


def self_test_strict(root: Path) -> None:
    """The three exclusions do not make STRICT_USE true; a named read does."""
    manifest = _read(root / MANIFEST)
    target = next(
        f".specs/papers/{p.name}"
        for p in sorted((root / ".specs" / "papers").glob("CORE-*.md"))
        if f".specs/papers/{p.name}" in manifest
        and not _strict(root, f".specs/papers/{p.name}")
    )
    other = next(r for r in _files(root, ".specs") if r.endswith(".md") and r != target)
    with tempfile.TemporaryDirectory(dir=root / "var" / "tmp") as tmp:
        copy = Path(tmp) / "tree"
        for top in ("src", "tests", ".specs", ".intent"):
            shutil.copytree(root / top, copy / top)
        checks = []
        # 1. the register lists it (already true in the real tree)
        checks.append(("listed in the namespace manifest", target in manifest))
        checks.append(("register: strict stays false", not _strict(copy, target)))
        # 2. a folder sweep reads every paper, this one included
        (copy / "src" / "zz_selftest_sweep.py").write_text(
            "from pathlib import Path\n\n\n"
            "def sweep(root: Path) -> list[str]:\n"
            '    return [p.read_text() for p in (root / ".specs" / "papers").glob("*.md")]\n'
        )
        checks.append(("sweep: strict stays false", not _strict(copy, target)))
        # 3. another .specs file cites it
        cited = copy / other
        cited.write_text(_read(cited) + f"\nSee {target}.\n")
        checks.append(("citation: strict stays false", not _strict(copy, target)))
        # control: a named read makes it true
        (copy / "src" / "zz_selftest_named.py").write_text(
            "from pathlib import Path\n\n\n"
            "def read() -> str:\n"
            f'    return Path("{target}").read_text()\n'
        )
        checks.append(("named read: strict becomes true", _strict(copy, target)))
        # a read through named constants joined later (the Trial 0 pattern)
        (copy / "src" / "zz_selftest_named.py").unlink()
        inner = target[len(".specs/") :]
        head, _, tail = inner.rpartition("/")
        (copy / "tests" / "test_zz_selftest_joined.py").write_text(
            "from pathlib import Path\n\n"
            f'BASE = Path("root") / ".specs" / "{head}"\n'
            f'NAME = "{tail}"\n\n\n'
            "def test_read() -> None:\n"
            "    for rel in (NAME,):\n"
            "        assert (BASE / rel).read_text()\n"
        )
        checks.append(("joined constants: strict becomes true", _strict(copy, target)))
    for label, ok in checks:
        print(f"strict {target}: {label}: {'ok' if ok else 'FAILED'}")
    if not all(ok for _label, ok in checks):
        sys.exit("SELF-TEST FAILED: STRICT_USE exclusions")


def self_test(root: Path) -> None:
    self_test_strict(root)
    audit = run_audit(root)
    before = {(r[0], r[1]): r for r in build(root, audit, None)}
    rule = next(
        r for k, r in sorted(before.items()) if k[0] == "rule" and r[2] == "ENFORCED"
    )
    spec = next(
        r
        for k, r in sorted(before.items())
        if k[0] == "spec" and r[2] == "RUNTIME" and len(r[10].split(";")) == 1
    )
    with tempfile.TemporaryDirectory(dir=root / "var" / "tmp") as tmp:
        copy = Path(tmp) / "tree"
        shutil.copytree(
            root,
            copy,
            ignore=shutil.ignore_patterns(
                ".git", "var", "reports", ".venv", "__pycache__", "node_modules"
            ),
        )
        (copy / "var" / "tmp").mkdir(parents=True)
        _cut_mapping(copy, rule[10], rule[1])
        user = copy / spec[10]
        inner = spec[1][len(".specs/") :]
        src = _read(user)
        needles = [spec[1], inner, Path(spec[1]).name]
        for needle in needles:
            src = src.replace(f'"{needle}"', '"removed-by-self-test"')
        parts = Path(inner).parts
        for i in range(len(parts) - 1, 0, -1):
            src = src.replace(f'"{"/".join(parts[:i])}"', '"removed-by-self-test"')
        user.write_text(src, encoding="utf-8")
        after = {(r[0], r[1]): r for r in build(copy, run_audit(copy), None)}
    r2 = after[("rule", rule[1])]
    s2 = after[("spec", spec[1])]
    print(f"rule {rule[1]}: {rule[2]} -> {r2[2]} (mapping removed from {rule[10]})")
    print(f"spec {spec[1]}: {spec[2]} -> {s2[2]} (reference removed from {spec[10]})")
    if r2[2] == "ENFORCED" or s2[2] == "RUNTIME":
        sys.exit("SELF-TEST FAILED: a removal did not reclassify")
    print("self-test passed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument(
        "--audit-json", help="reuse a saved `code audit --offline --format=json`"
    )
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--as-of", help="end of the 90-day findings window (ISO 8601)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.self_test:
        self_test(root)
        return
    audit = (
        json.loads(Path(args.audit_json).read_text())
        if args.audit_json
        else run_audit(root)
    )
    findings = None if args.no_db else findings_90d(root, _as_of(root, args.as_of))
    rows = build(root, audit, findings)
    (root / args.out).write_text(render(rows), encoding="utf-8")
    print(summary(rows))


if __name__ == "__main__":
    main()
