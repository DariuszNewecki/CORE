# Write a CORE Plug-in

A plug-in is an installable Python package that brings CORE engines, content
(catalogs, governance packs) or both. Install it next to `core-runtime` and CORE
finds it by itself; there are no folder settings and no list to edit (ADR-177).

**You need:** Python 3.12 and `core-runtime` 3.3 or later.

A complete example lives in `examples/plugin-example/`: one engine that flags TODO
markers and one catalog that uses it.

## 1. Declare the plug-in

The package's name and version are its own metadata (`pyproject.toml`). It declares
one entry point in the group `core.plugins`, naming its manifest:

```toml
[project.entry-points."core.plugins"]
my-plugin = "my_plugin:MANIFEST"
```

The manifest is plain data, checked against `plugin_manifest.schema.json`:

```python
MANIFEST = {
    "format_version": 1,
    "core_engine_api": "1",          # the engine interface it was built for
    "engines": ["my_plugin.engines:MyGate"],   # optional
    "catalogs": "catalogs",          # optional: a catalog root in the package
    "packs": "packs",                # optional: governance packs in the package
}
```

`catalogs` and `packs` are directories relative to the plug-in's top-level package.
Ship them as package data.

## 2. Write an engine

Import only from `mind.engine_api`; that is the one import path CORE promises to keep
(ADR-177 D6). Everything else in `mind` is internal.

```python
from mind.engine_api import BaseEngine, EngineResult, EvidenceClass

class MyGate(BaseEngine):
    engine_id = "my_gate"              # lowercase letters, digits, underscores
    evidence_class = EvidenceClass.PROVEN

    async def verify(self, file_path, params):
        return EngineResult(ok=True, message="ok", violations=[], engine_id=self.engine_id)
```

The rules an engine follows are ADR-176's:

- It declares `engine_id` on its own class.
- `api_version` defaults to `"1"`.
- `verify` is async.
- The constructor may ask only for `path_resolver`, `llm_client` and `embedding_client`.

A record engine sets `supports_records = True` and implements `evaluate_record`.

## 3. Add content

A catalog root uses the usual layout: `inventory.yaml`, then
`public/<id>/catalog.yaml` with a `provenance.yaml` beside it. It goes through the
same catalog checks as CORE's own (ADR-174).

A pack is a `governance_pack` YAML file in the `packs` directory (ADR-149).

## 4. Check it

```bash
pip install -e path/to/my-plugin
core-admin plugin list
core-admin plugin check my-plugin
core-admin plugin check my-plugin --format json > plugin-check.json
```

`plugin check` reports everything CORE would say about the plug-in:

- the manifest;
- each engine: its declarations, and one run on a minimal input;
- clashes with CORE's ids or another plug-in's;
- the plug-in's catalogs and packs.

The JSON report (`plugin-check/1`) carries the plug-in's fingerprint. Keep it as
validation evidence for that exact build.

| Exit code | Meaning |
|---|---|
| 0 | The plug-in conforms |
| 1 | Problems were found (listed with the rule they break) |
| 3 | The check could not run (no such plug-in, bad option) |

## What CORE does at load

- **Every installed plug-in is loaded,** CORE's own engines first, then plug-ins in name
  order. Installing a package means trusting it: its code runs when CORE loads it.
- **A broken plug-in is never a silent pass.** If its manifest is invalid, or it was
  built for another `core_engine_api`, the whole plug-in is skipped with a warning. Rules
  that name its engines then give the engine-missing finding.
- **No overriding.** An engine id, catalog id or pack id that a plug-in shares with CORE
  or with another plug-in stops CORE and names both sides.
- **CORE says what it loaded.** The log gets one line per plug-in: name, version, engines,
  catalog and pack counts, and a fingerprint (sha256 over the plug-in's installed files).
  `core-admin code audit --format json` lists the plug-ins and fingerprints each run used.
