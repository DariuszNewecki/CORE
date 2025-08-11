from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import List
from src.system.guard.drift_detector import load_manifest, collect_code_capabilities, detect_capability_drift, write_report
DEFAULT_REPORT = Path('reports/drift_report.json')

def _print_table(report_dict: dict) -> None:
    """Prints a formatted report of capability discrepancies (missing in code, undeclared in manifest, and mismatched mappings) from a dictionary."""

    def section(title: str, items: List[str]) -> None:
        print(f'\n== {title} ==')
        print('  (none)' if not items else '\n'.join((f'  - {it}' for it in items)))
    section('Missing in code', report_dict.get('missing_in_code', []))
    section('Undeclared in manifest', report_dict.get('undeclared_in_manifest', []))
    print('\n== Mismatched mappings ==')
    mism = report_dict.get('mismatched_mappings', [])
    if not mism:
        print('  (none)')
    else:
        for m in mism:
            man, cod = (m.get('manifest', {}), m.get('code', {}))
            print(f'  - {m.get('capability')}: manifest(domain={man.get('domain')}, owner={man.get('owner')}) != code(domain={cod.get('domain')}, owner={cod.get('owner')})')

def _should_fail(report: dict, fail_on: str) -> bool:
    """Determines whether to fail based on the report and specified condition (missing, undeclared, or any discrepancy)."""
    if fail_on == 'missing':
        return bool(report['missing_in_code'])
    if fail_on == 'undeclared':
        return bool(report['undeclared_in_manifest'])
    return bool(report['missing_in_code'] or report['undeclared_in_manifest'] or report['mismatched_mappings'])

def _handle_drift(args: argparse.Namespace) -> int:
    """Processes capability drift detection, generates a report, and returns an exit code based on drift severity and fail conditions."""
    root = Path(args.root).resolve()
    manifest_path = Path(args.manifest_path).resolve() if args.manifest_path else None
    manifest = load_manifest(root, explicit_path=manifest_path)
    code_caps = collect_code_capabilities(root, include_globs=args.include or [], exclude_globs=args.exclude or [], require_kgb=args.strict_intent)
    report = detect_capability_drift(manifest, code_caps)
    report_dict = report.to_dict()
    out = Path(args.output or DEFAULT_REPORT)
    write_report(out, report)
    print(json.dumps(report_dict, indent=2) if args.format == 'json' else '')
    if args.format == 'table':
        _print_table(report_dict)
    return 2 if _should_fail(report_dict, args.fail_on) else 0

def register_guard_command(subparsers: argparse._SubParsersAction) -> None:
    """Register the 'guard' command and its subcommands (including 'drift') with argparse subparsers."""
    guard = subparsers.add_parser('guard', help='Governance/validation guards')
    guard_sub = guard.add_subparsers(dest='guard_command')
    drift = guard_sub.add_parser('drift', help='Detect capability drift vs .intent manifest')
    drift.add_argument('--root', default='.', help='Repository root (default: .)')
    drift.add_argument('--manifest-path', default=None, help='Explicit manifest path (defaults to .intent/project_manifest.yaml)')
    drift.add_argument('--format', choices=['json', 'table'], default='json')
    drift.add_argument('--output', default=None, help='Path for JSON report (default: reports/drift_report.json)')
    drift.add_argument('--fail-on', choices=['any', 'missing', 'undeclared'], default='any')
    drift.add_argument('--include', nargs='*', help='Include globs for source files')
    drift.add_argument('--exclude', nargs='*', help='Exclude globs for source files')
    drift.add_argument('--strict-intent', action='store_true', help='Require KnowledgeGraphBuilder; disallow regex fallback')
    drift.set_defaults(func=_handle_drift)

def ensure_cli_entrypoint():
    """Initializes and executes the CLI entrypoint for core-admin, handling command registration and parsing."""
    parser = argparse.ArgumentParser(prog='core-admin')
    subparsers = parser.add_subparsers(dest='command')
    register_guard_command(subparsers)
    args = parser.parse_args()
    if hasattr(args, 'func'):
        sys.exit(args.func(args))
    parser.print_help()
    sys.exit(0)
if __name__ == '__main__':
    ensure_cli_entrypoint()