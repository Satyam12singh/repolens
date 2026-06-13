import os
from pathlib import Path

from .models import FileNode

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".md": "markdown",
}

SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "env", ".env",
    "dist", "build", "out", "target",
    ".idea", ".vscode",
    "vendor", "third_party",
}

MAX_FILE_SIZE = 500_000  # 500 KB


def scan(root: str, max_files: int = 2000) -> list[FileNode]:
    """Walk *root* and return FileNode list for all source files."""
    root_path = Path(root).resolve()
    nodes: list[FileNode] = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

        for filename in filenames:
            if len(nodes) >= max_files:
                break
            full_path = Path(dirpath) / filename
            suffix = full_path.suffix.lower()
            language = SUPPORTED_EXTENSIONS.get(suffix)
            if not language:
                continue

            rel_path = full_path.relative_to(root_path).as_posix()
            size = full_path.stat().st_size

            content: str | None = None
            if size <= MAX_FILE_SIZE:
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass

            nodes.append(FileNode(path=rel_path, size=size, language=language, content=content))

    return sorted(nodes, key=lambda n: n.path)
