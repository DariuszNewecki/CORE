# add_filepath_comments.py
from pathlib import Path

SRC_DIR = Path("src")

def heal_file(file_path: Path):
    """
    Ensures the file starts with the correct '# src/...' comment.
    """
    relative_path_str = str(file_path).replace(os.path.sep, '/')
    correct_header = f"# {relative_path_str}"
    
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        
        # Check if the file is empty or already has the correct header
        if not lines or lines[0] == correct_header:
            return

        # If the first line is a different comment, remove it if it looks like an old path
        if lines[0].strip().startswith("# src/"):
             lines.pop(0)

        # Prepend the correct header
        new_lines = [correct_header] + lines
        
        new_content = "\n".join(new_lines) + "\n"
        file_path.write_text(new_content, encoding="utf-8")
        print(f"HEALED: {file_path}")

    except Exception as e:
        print(f"SKIPPED: {file_path} due to error: {e}")


if __name__ == "__main__":
    import os
    print("--- Starting One-Time Codebase Healing Script ---")
    py_files = list(SRC_DIR.rglob("*.py"))
    for py_file in py_files:
        heal_file(py_file)
    print(f"--- Healing Complete. Processed {len(py_files)} files. ---")