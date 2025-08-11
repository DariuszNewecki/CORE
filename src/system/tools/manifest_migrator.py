# src/system/tools/manifest_migrator.py
"""
A CLI tool to migrate the monolithic project_manifest.yaml into domain-specific
manifests, as per the modular manifest architecture.
"""
import json
from pathlib import Path

import typer
import yaml

from shared.logger import getLogger

# --- Constants & Setup ---
log = getLogger("manifest_migrator")
REPO_ROOT = Path(__file__).resolve().parents[3]
INTENT_DIR = REPO_ROOT / ".intent"
MONOLITHIC_MANIFEST_PATH = INTENT_DIR / "project_manifest.yaml"
SOURCE_STRUCTURE_PATH = INTENT_DIR / "knowledge" / "source_structure.yaml"
KNOWLEDGE_GRAPH_PATH = INTENT_DIR / "knowledge" / "knowledge_graph.json"


def migrate_manifest(
    dry_run: bool = typer.Option(
        True,  # Default to True for safety
        "--dry-run/--write",
        help="Show what changes would be made without writing any files. Use --write to apply changes.",
    )
):
    """
    Reads the monolithic manifest and splits it into per-domain manifests.
    """
    log.info("🚀 Starting manifest migration...")

    # Step 1: Load all necessary constitutional and knowledge files.
    log.info("   -> Loading source files...")
    if not all(
        p.exists()
        for p in [
            MONOLITHIC_MANIFEST_PATH,
            SOURCE_STRUCTURE_PATH,
            KNOWLEDGE_GRAPH_PATH,
        ]
    ):
        log.error("❌ Critical file missing. Ensure manifest, source structure, and knowledge graph exist.")
        raise typer.Exit(code=1)

    monolith = yaml.safe_load(MONOLITHIC_MANIFEST_PATH.read_text())
    source_structure = yaml.safe_load(SOURCE_STRUCTURE_PATH.read_text())
    knowledge_graph = json.loads(KNOWLEDGE_GRAPH_PATH.read_text())

    # Step 2: Build a map to determine which domain "owns" each capability.
    # The Knowledge Graph is the source of truth for this.
    log.info("   -> Building capability-to-domain map from Knowledge Graph...")
    cap_to_domain = {
        symbol["capability"]: symbol["domain"]
        for symbol in knowledge_graph.get("symbols", {}).values()
        if symbol.get("capability") != "unassigned"
    }

    # Step 3: Prepare the new domain-specific manifests in memory.
    log.info("   -> Preparing new domain-specific manifests...")
    domain_manifests = {}
    for entry in source_structure.get("structure", []):
        domain_name = entry.get("domain")
        if domain_name:
            domain_manifests[domain_name] = {
                "domain": domain_name,
                "description": entry.get("description", "No description provided."),
                "capabilities": [],
            }

    # Step 4: Distribute capabilities from the old manifest to the new ones.
    log.info("   -> Distributing capabilities to their respective domains...")
    all_capabilities = monolith.get("required_capabilities", [])
    for cap in all_capabilities:
        domain = cap_to_domain.get(cap)
        if domain and domain in domain_manifests:
            domain_manifests[domain]["capabilities"].append(cap)
        else:
            log.warning(f"   -> Capability '{cap}' has no known domain. Skipping.")

    # Step 5: Perform the write or dry run.
    if dry_run:
        log.info("\n💧 **Dry Run Mode:** No files will be written.")
        for domain, content in domain_manifests.items():
            if not content["capabilities"]:  # Don't create empty manifests
                continue
            domain_path = source_structure["structure"][
                [i for i, d in enumerate(source_structure["structure"]) if d["domain"] == domain][0]
            ]["path"]
            target_path = REPO_ROOT / domain_path / "manifest.yaml"
            typer.secho(f"\n📄 Would write to: {target_path}", fg=typer.colors.YELLOW)
            typer.echo(yaml.dump(content, indent=2))
    else:
        log.info("\n💾 **Write Mode:** Applying changes to disk.")
        for domain, content in domain_manifests.items():
            if not content["capabilities"]:
                continue
            domain_path_str = next(
                (d["path"] for d in source_structure["structure"] if d["domain"] == domain), None
            )
            if domain_path_str:
                target_path = REPO_ROOT / domain_path_str / "manifest.yaml"
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(yaml.dump(content, indent=2))
                typer.secho(f"   -> ✅ Wrote manifest for domain '{domain}' to {target_path}", fg=typer.colors.GREEN)

    log.info("\n🎉 Migration process complete.")


if __name__ == "__main__":
    typer.run(migrate_manifest)