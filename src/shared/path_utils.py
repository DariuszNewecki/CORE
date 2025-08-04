# src/shared/path_utils.py

from pathlib import Path
from typing import Optional

def get_repo_root(start_path: Optional[Path] = None) -> Path:
    """
    Find and return the repository root by locating the .git directory.
    Starts from current directory or provided path.
    
    Returns:
        Path: Absolute path to repo root.
    
    Raises:
        RuntimeError: If no .git directory is found.
    """
    current = Path(start_path or Path.cwd()).resolve()
    
    # Traverse upward until .git is found
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    
    raise RuntimeError("Not a git repository: could not find .git directory")