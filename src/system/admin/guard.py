"""
Intent: Governance/validation guard commands exposed to the operator.
- `drift`: compare .intent manifest vs discovered code capabilities.
- `kg-export`: emit a knowledge-graph artifact so `--strict-intent` has a stable source.

This command honors UX defaults declared in .intent/project_manifest.yaml under:
  operator_experience.guard.drift
If absent, it falls back to sensible defaults (JSON output, non-strict).
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import typer
import yaml
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table
from shared.logger import getLogger
from system.guard.drift_detector import collect_code_capabilities, detect_capability_drift, load_manifest, write_report
log = getLogger('core_admin')

def _find_manifest_path(root: Path, explicit: Optional[Path]) -> Path:
    """Locate the manifest file path, checking explicit path first, then default locations under root/.intent/."""
    if explicit:
        return explicit
    for p in (root / '.intent' / 'project_manifest.yaml', root / '.intent' / 'manifest.yaml'):
        if p.exists():
            return p
    raise FileNotFoundError('No manifest found (.intent/project_manifest.yaml or .intent/manifest.yaml)')

def _load_raw_manifest(root: Path, explicit: Optional[Path]) -> Dict[str, Any]:
    """Loads and parses a YAML manifest file from the given root or explicit path, returning its contents as a dictionary."""
    path = _find_manifest_path(root, explicit)
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    return data

def _ux_defaults(root: Path, explicit: Optional[Path]) -> Dict[str, Any]:
    """Extracts and returns UX defaults for drift guard from a raw manifest, with fallback values."""
    raw = _load_raw_manifest(root, explicit)
    ux = ((raw.get('operator_experience') or {}).get('guard') or {}).get('drift') or {}
    return {'default_format': ux.get('default_format', 'json'), 'default_fail_on': ux.get('default_fail_on', 'any'), 'strict_default': bool(ux.get('strict_default', False)), 'evidence_json': bool(ux.get('evidence_json', True)), 'evidence_path': ux.get('evidence_path', 'reports/drift_report.json'), 'labels': {'none': (ux.get('labels') or {}).get('none', 'NONE'), 'success': (ux.get('labels') or {}).get('success', '✅ No capability drift'), 'failure': (ux.get('labels') or {}).get('failure', '🚨 Drift detected')}}

def _is_clean(report: dict) -> bool:
    """Determines if a report is clean by checking for missing, undeclared, or mismatched entries."""
    return not (report.get('missing_in_code') or report.get('undeclared_in_manifest') or report.get('mismatched_mappings'))

def _print_table(report_dict: dict, labels: Dict[str, str]) -> None:
    """Prints a formatted table showing capability drift report details, including missing in code, undeclared in manifest, and mismatched mappings sections."""
    table = Table(show_header=True, header_style='bold', title='Capability Drift')
    table.add_column('Section', style='bold')
    table.add_column('Values')

    def row(title: str, items: List[str]):
        if not items:
            table.add_row(title, f'[bold green]{labels['none']}[/bold green]')
        else:
            joined = '\n'.join((f'- {it}' for it in items))
            table.add_row(title, f'[yellow]{joined}[/yellow]')
    row('Missing in code', report_dict.get('missing_in_code', []))
    row('Undeclared in manifest', report_dict.get('undeclared_in_manifest', []))
    mism = report_dict.get('mismatched_mappings', [])
    if not mism:
        table.add_row('Mismatched mappings', f'[bold green]{labels['none']}[/bold green]')
    else:
        lines = []
        for m in mism:
            man, cod = (m.get('manifest', {}), m.get('code', {}))
            lines.append(f'- {m.get('capability')}: manifest(domain={man.get('domain')}, owner={man.get('owner')}) != code(domain={cod.get('domain')}, owner={cod.get('owner')})')
        table.add_row('Mismatched mappings', '[yellow]' + '\n'.join(lines) + '[/yellow]')
    status = '[bold green]' + labels['success'] + '[/bold green]' if _is_clean(report_dict) else '[bold red]' + labels['failure'] + '[/bold red]'
    rprint(Panel.fit(table, title=status))

def _print_pretty(report_dict: dict, labels: Dict[str, str]) -> None:
    """Prints a formatted capability drift report based on the provided report dictionary and labels, including a summary panel and detailed table."""
    clean = _is_clean(report_dict)
    if clean:
        summary = f'[bold green]{labels['success']}[/bold green]\n[green]missing_in_code: {labels['none']}[/green]\n[green]undeclared_in_manifest: {labels['none']}[/green]\n[green]mismatched_mappings: {labels['none']}[/green]'
    else:
        summary = f'[bold red]{labels['failure']}[/bold red]\n[yellow]missing_in_code: {len(report_dict.get('missing_in_code', []))}[/yellow]\n[yellow]undeclared_in_manifest: {len(report_dict.get('undeclared_in_manifest', []))}[/yellow]\n[yellow]mismatched_mappings: {len(report_dict.get('mismatched_mappings', []))}[/yellow]'
    rprint(Panel(summary, title='Capability Drift', border_style='green' if clean else 'red'))
    _print_table(report_dict, labels)

def _should_fail(report: dict, fail_on: str) -> bool:
    """Determines whether to fail based on the report and fail_on criteria, checking for missing, undeclared, or mismatched mappings."""
    if fail_on == 'missing':
        return bool(report['missing_in_code'])
    if fail_on == 'undeclared':
        return bool(report['undeclared_in_manifest'])
    return bool(report['missing_in_code'] or report['undeclared_in_manifest'] or report['mismatched_mappings'])

def register(app: typer.Typer) -> None:
    """Register governance/validation guard commands (drift detection and knowledge-graph export) under a Typer app."""
    guard = typer.Typer(help='Governance/validation guards')
    app.add_typer(guard, name='guard')

    @guard.command('drift')
    def drift(root: Path=typer.Option(Path('.'), help='Repository root (default: .)'), manifest_path: Optional[Path]=typer.Option(None, help='Explicit manifest path'), output: Optional[Path]=typer.Option(None, help='Path for JSON evidence report'), format: Optional[str]=typer.Option(None, help='json|table|pretty (defaults come from manifest)'), fail_on: Optional[str]=typer.Option(None, help='any|missing|undeclared (default from manifest)'), include: Optional[List[str]]=typer.Option(None, help='Include globs'), exclude: Optional[List[str]]=typer.Option(None, help='Exclude globs'), strict_intent: Optional[bool]=typer.Option(None, help='Default from manifest (strict_default)')) -> None:
        """Intent: Compare manifest vs code to detect capability drift; write JSON evidence for CI."""
        ux = _ux_defaults(root, manifest_path)
        fmt = (format or ux['default_format']).lower()
        fail_policy = (fail_on or ux['default_fail_on']).lower()
        strict = bool(ux['strict_default'] if strict_intent is None else strict_intent)
        manifest_caps = load_manifest(root, explicit_path=manifest_path)
        code_caps = collect_code_capabilities(root, include_globs=include or [], exclude_globs=exclude or [], require_kgb=strict)
        report = detect_capability_drift(manifest_caps, code_caps)
        report_dict = report.to_dict()
        if ux['evidence_json']:
            evidence_path = output or root / ux['evidence_path']
            write_report(evidence_path, report)
        labels = ux['labels']
        if fmt == 'json':
            typer.echo(json.dumps(report_dict, indent=2))
        elif fmt == 'table':
            _print_table(report_dict, labels)
        elif fmt == 'pretty':
            _print_pretty(report_dict, labels)
        else:
            typer.echo(json.dumps(report_dict, indent=2))
        if _should_fail(report_dict, fail_policy):
            raise typer.Exit(code=2)

    @guard.command('kg-export')
    def kg_export(root: Path=typer.Option(Path('.'), help='Repository root (default: .)'), output: Optional[Path]=typer.Option(None, help='Artifact file (default: <root>/reports/knowledge_graph.json)'), include: Optional[List[str]]=typer.Option(None, help='Include globs'), exclude: Optional[List[str]]=typer.Option(None, help='Exclude globs'), prefer: str=typer.Option('auto', case_sensitive=False, help='auto|kgb|grep')) -> None:
        """
        Intent: Emit a minimal knowledge-graph artifact with capability nodes.
        Format: { "nodes": [ {"capability": "...", "domain": "x", "owner": "y"}, ... ] }
        """
        require_kgb = prefer.lower() == 'kgb'
        caps = collect_code_capabilities(root, include_globs=include or [], exclude_globs=exclude or [], require_kgb=require_kgb)
        nodes = [{'capability': k, 'domain': v.domain, 'owner': v.owner} for k, v in sorted(caps.items())]
        out_path = output or root / 'reports' / 'knowledge_graph.json'
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({'nodes': nodes}, indent=2), encoding='utf-8')
        rprint(f'[bold green]✅[/bold green] Wrote knowledge-graph artifact with [bold]{len(nodes)}[/bold] capability nodes -> {out_path}')