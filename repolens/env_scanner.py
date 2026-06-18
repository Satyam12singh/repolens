from __future__ import annotations
import re
from pathlib import Path
from .models import EnvVar, FileNode

# ── Python ────────────────────────────────────────────────────────────────────
# os.getenv("KEY") / os.getenv("KEY", "default")
_PY_GETENV_RE = re.compile(
    r'os\.getenv\(\s*["\']([A-Z0-9_]{2,})["\'](?:\s*,\s*["\']([^"\']*)["\'])?\s*\)'
)
# os.environ["KEY"] / os.environ.get("KEY") / os.environ.get("KEY", "default")
_PY_ENVIRON_BRACKET_RE = re.compile(r'os\.environ\s*\[\s*["\']([A-Z0-9_]{2,})["\']\s*\]')
_PY_ENVIRON_GET_RE = re.compile(
    r'os\.environ\.get\(\s*["\']([A-Z0-9_]{2,})["\'](?:\s*,\s*["\']([^"\']*)["\'])?\s*\)'
)

# ── TypeScript / JavaScript ───────────────────────────────────────────────────
_TS_ENV_DOT_RE  = re.compile(r'process\.env\.([A-Z0-9_]{2,})')
_TS_ENV_BRKT_RE = re.compile(r'process\.env\[\s*["\']([A-Z0-9_]{2,})["\']\s*\]')

# ── Go ────────────────────────────────────────────────────────────────────────
_GO_GETENV_RE  = re.compile(r'os\.Getenv\(\s*"([A-Z0-9_]{2,})"\s*\)')
_GO_LOOKUP_RE  = re.compile(r'os\.LookupEnv\(\s*"([A-Z0-9_]{2,})"\s*\)')

# ── Rust ──────────────────────────────────────────────────────────────────────
_RUST_ENV_RE = re.compile(r'(?:std::)?env::var\(\s*"([A-Z0-9_]{2,})"\s*\)')


def _read_dotenv(root: str) -> set[str]:
    """Return set of variable names defined in any .env file under root."""
    defined: set[str] = set()
    for p in Path(root).rglob(".env"):
        try:
            for line in p.read_text(errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key = line.split("=", 1)[0].strip()
                    if key:
                        defined.add(key)
        except OSError:
            pass
    return defined


def _py_envvars(file_node: FileNode) -> list[tuple[str, int, bool, str]]:
    """Returns list of (name, line, has_default, default_value)."""
    if not file_node.content:
        return []
    results = []
    lines = file_node.content.splitlines()
    for i, line in enumerate(lines, 1):
        for m in _PY_GETENV_RE.finditer(line):
            results.append((m.group(1), i, m.group(2) is not None, m.group(2) or ""))
        for m in _PY_ENVIRON_BRACKET_RE.finditer(line):
            results.append((m.group(1), i, False, ""))
        for m in _PY_ENVIRON_GET_RE.finditer(line):
            results.append((m.group(1), i, m.group(2) is not None, m.group(2) or ""))
    return results


def _ts_envvars(file_node: FileNode) -> list[tuple[str, int, bool, str]]:
    if not file_node.content:
        return []
    results = []
    lines = file_node.content.splitlines()
    for i, line in enumerate(lines, 1):
        for m in _TS_ENV_DOT_RE.finditer(line):
            results.append((m.group(1), i, False, ""))
        for m in _TS_ENV_BRKT_RE.finditer(line):
            results.append((m.group(1), i, False, ""))
    return results


def _go_envvars(file_node: FileNode) -> list[tuple[str, int, bool, str]]:
    if not file_node.content:
        return []
    results = []
    lines = file_node.content.splitlines()
    for i, line in enumerate(lines, 1):
        for m in _GO_GETENV_RE.finditer(line):
            results.append((m.group(1), i, False, ""))
        for m in _GO_LOOKUP_RE.finditer(line):
            results.append((m.group(1), i, False, ""))
    return results


def _rust_envvars(file_node: FileNode) -> list[tuple[str, int, bool, str]]:
    if not file_node.content:
        return []
    results = []
    lines = file_node.content.splitlines()
    for i, line in enumerate(lines, 1):
        for m in _RUST_ENV_RE.finditer(line):
            results.append((m.group(1), i, False, ""))
    return results


_SCANNERS = {
    "python":     _py_envvars,
    "typescript": _ts_envvars,
    "javascript": _ts_envvars,
    "go":         _go_envvars,
    "rust":       _rust_envvars,
}


def scan_env_vars(files: list[FileNode], root: str = ".") -> list[EnvVar]:
    dotenv_names = _read_dotenv(root)
    results: list[EnvVar] = []
    for fn in files:
        scanner = _SCANNERS.get(fn.language)
        if not scanner:
            continue
        for name, line, has_default, default_val in scanner(fn):
            results.append(EnvVar(
                name=name,
                file_path=fn.path,
                line=line,
                has_default=has_default,
                default_value=default_val,
                in_dotenv=name in dotenv_names,
            ))
    return results
