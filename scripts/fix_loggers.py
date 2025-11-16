#!/usr/bin/env python3
# fix_loggers.py
import ast
from pathlib import Path


class LoggerFixer(ast.NodeTransformer):
    def visit_Assign(self, node):
        # Match 'log = getLogger(...)' or 'logger = getLogger(...)'
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("log", "logger")
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "getLogger"
        ):
            # Always use 'logger' and '__name__'
            node.targets[0].id = "logger"
            if node.value.args and isinstance(node.value.args[0], ast.Constant):
                node.value.args[0] = ast.Constant(value="__name__", kind=None)

            print(f"Fixed: {node.targets[0].id} = getLogger(...)")
        return node


def fix_file(filepath):
    code = filepath.read_text()
    tree = ast.parse(code)

    # Skip if no getLogger calls
    if not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getLogger"
        for node in ast.walk(tree)
    ):
        return

    new_tree = LoggerFixer().visit(tree)
    ast.fix_missing_locations(new_tree)

    # Write back
    new_code = compile(new_tree, filepath, "exec")
    source = ast.unparse(new_tree)
    filepath.write_text(source)
    print(f"✓ Processed {filepath}")


if __name__ == "__main__":
    for pattern in ["src/**/*.py", "tests/**/*.py"]:
        for p in Path(".").glob(pattern):
            if p.is_file():
                fix_file(p)
