from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional

from .models import FileAnalysis, FileNode, FunctionNode


# ── Python ────────────────────────────────────────────────────────────────────

def _py_resolve(module: str, level: int, current_file: str, all_paths: set[str]) -> Optional[str]:
    """Resolve a Python import to a repo-relative file path."""
    parts = module.split(".") if module else []

    if level > 0:
        base = Path(current_file).parent
        for _ in range(level - 1):
            base = base.parent
        candidate_parts = list(base.parts) + parts
    else:
        candidate_parts = parts

    as_path = "/".join(candidate_parts)
    for candidate in (f"{as_path}.py", f"{as_path}/__init__.py"):
        if candidate in all_paths:
            return candidate
    return None


def _call_name(node: ast.expr) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        obj = _call_name(node.value)
        return f"{obj}.{node.attr}" if obj else node.attr
    return None


def _analyze_python(file_node: FileNode, all_paths: set[str]) -> FileAnalysis:
    fa = FileAnalysis(path=file_node.path, language="python")
    if not file_node.content:
        return fa
    try:
        tree = ast.parse(file_node.content, filename=file_node.path)
    except SyntaxError:
        return fa

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                fa.raw_imports.append(alias.name)
                r = _py_resolve(alias.name, 0, file_node.path, all_paths)
                if r:
                    fa.resolved_imports.append(r)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = node.level
            fa.raw_imports.append(("." * level) + module)
            r = _py_resolve(module, level, file_node.path, all_paths)
            if r:
                fa.resolved_imports.append(r)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            calls: list[str] = []
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, ast.Call):
                    name = _call_name(child.func)
                    if name:
                        calls.append(name)
            raw_doc = ast.get_docstring(node, clean=True)
            # Trim to first paragraph so long docstrings don't flood the TUI
            docstring = raw_doc.split("\n\n")[0].strip() if raw_doc else None
            fa.functions.append(
                FunctionNode(
                    name=node.name,
                    file_path=file_node.path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    calls=calls,
                    docstring=docstring,
                )
            )

        elif isinstance(node, ast.ClassDef):
            fa.classes.append(node.name)

    return fa


# ── JavaScript / TypeScript ───────────────────────────────────────────────────

_JS_IMPORT_RE = re.compile(
    r"""(?:
        import\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]
      | (?:require|import)\s*\(\s*['"]([^'"]+)['"]\s*\)
      | export\s+[^'"]*?\s+from\s+['"]([^'"]+)['"]
    )""",
    re.VERBOSE | re.MULTILINE,
)

_JS_FUNC_RE = re.compile(
    r"""(?:
        (?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)\s*\(
      | (?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(
      | (?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?function
    )""",
    re.VERBOSE | re.MULTILINE,
)

# Matches /** ... */ JSDoc block immediately before a function
_JSDOC_RE = re.compile(r'/\*\*(.*?)\*/', re.DOTALL)


def _js_resolve(import_path: str, current_file: str, all_paths: set[str]) -> Optional[str]:
    if not import_path.startswith("."):
        return None
    base = Path(current_file).parent
    candidate = (base / import_path).as_posix()
    for ext in ("", ".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.ts", "/index.tsx"):
        p = candidate + ext
        if p in all_paths:
            return p
    return None


def _analyze_js(file_node: FileNode, all_paths: set[str]) -> FileAnalysis:
    fa = FileAnalysis(path=file_node.path, language=file_node.language)
    if not file_node.content:
        return fa
    content = file_node.content

    for m in _JS_IMPORT_RE.finditer(content):
        raw = m.group(1) or m.group(2) or m.group(3)
        if not raw:
            continue
        fa.raw_imports.append(raw)
        r = _js_resolve(raw, file_node.path, all_paths)
        if r:
            fa.resolved_imports.append(r)

    for m in _JS_FUNC_RE.finditer(content):
        name = m.group(1) or m.group(2) or m.group(3)
        if not name:
            continue
        line = content[: m.start()].count("\n") + 1
        # Look for a JSDoc comment ending just before this function
        preceding = content[: m.start()].rstrip()
        jsdoc_match = _JSDOC_RE.search(preceding)
        docstring: Optional[str] = None
        if jsdoc_match and preceding.endswith("*/"):
            raw = jsdoc_match.group(1)
            # Strip leading " * " from each line and @param/@returns tags
            lines = [re.sub(r'^\s*\*\s?', '', l) for l in raw.splitlines()]
            desc_lines = [l for l in lines if l.strip() and not l.strip().startswith("@")]
            if desc_lines:
                docstring = " ".join(desc_lines).strip()
        fa.functions.append(
            FunctionNode(
                name=name,
                file_path=file_node.path,
                line_start=line,
                line_end=line,
                docstring=docstring,
            )
        )
    return fa


# ── Go ────────────────────────────────────────────────────────────────────────

_GO_IMPORT_BLOCK_RE = re.compile(r'import\s*\(([^)]+)\)', re.DOTALL)
_GO_IMPORT_SINGLE_RE = re.compile(r'^import\s+"([^"]+)"', re.MULTILINE)
_GO_FUNC_RE = re.compile(r'^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(', re.MULTILINE)


def _analyze_go(file_node: FileNode, _all_paths: set[str]) -> FileAnalysis:
    fa = FileAnalysis(path=file_node.path, language="go")
    if not file_node.content:
        return fa
    content = file_node.content
    for block in _GO_IMPORT_BLOCK_RE.findall(content):
        for imp in re.findall(r'"([^"]+)"', block):
            fa.raw_imports.append(imp)
    for m in _GO_IMPORT_SINGLE_RE.finditer(content):
        fa.raw_imports.append(m.group(1))
    for m in _GO_FUNC_RE.finditer(content):
        line = content[: m.start()].count("\n") + 1
        fa.functions.append(
            FunctionNode(name=m.group(1), file_path=file_node.path, line_start=line, line_end=line)
        )
    return fa


# ── Rust ──────────────────────────────────────────────────────────────────────

_RUST_USE_RE = re.compile(r'^use\s+([\w::{},\s*]+);', re.MULTILINE)
_RUST_FN_RE = re.compile(r'^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[\(<]', re.MULTILINE)


def _analyze_rust(file_node: FileNode, _all_paths: set[str]) -> FileAnalysis:
    fa = FileAnalysis(path=file_node.path, language="rust")
    if not file_node.content:
        return fa
    content = file_node.content
    for m in _RUST_USE_RE.finditer(content):
        fa.raw_imports.append(m.group(1).strip())
    for m in _RUST_FN_RE.finditer(content):
        line = content[: m.start()].count("\n") + 1
        fa.functions.append(
            FunctionNode(name=m.group(1), file_path=file_node.path, line_start=line, line_end=line)
        )
    return fa


# ── Dispatcher ────────────────────────────────────────────────────────────────

def analyze_file(file_node: FileNode, all_paths: set[str]) -> FileAnalysis:
    dispatch = {
        "python": _analyze_python,
        "javascript": _analyze_js,
        "typescript": _analyze_js,
        "go": _analyze_go,
        "rust": _analyze_rust,
    }
    fn = dispatch.get(file_node.language)
    if fn:
        return fn(file_node, all_paths)
    return FileAnalysis(path=file_node.path, language=file_node.language)


def analyze_all(files: list[FileNode]) -> dict[str, FileAnalysis]:
    all_paths = {f.path for f in files}
    return {
        f.path: analyze_file(f, all_paths)
        for f in files
        if f.content is not None
    }
