# Example CORE plug-in

One engine (`example_no_todo_gate`) and one catalog (`example_no_todo`) that uses
it, packaged as a CORE plug-in (ADR-177). See `docs/write-a-plugin.md`.

```
pip install -e examples/plugin-example
core-admin plugin list
core-admin plugin check core-plugin-example
```
