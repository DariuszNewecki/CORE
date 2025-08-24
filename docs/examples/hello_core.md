import os

file_path = "docs/examples/hello_core.md"
os.makedirs(os.path.dirname(file_path), exist_ok=True)
with open(file_path, 'w') as f:
    f.write('# Hello CORE')