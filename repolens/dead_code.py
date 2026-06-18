from __future__ import annotations

import re

from .models import DeadItem, RepoAnalysis

_SKIP_NAMES = frozenset({
    "main", "__init__", "__str__", "__repr__", "__eq__", "__hash__",
    "__len__", "__iter__", "__next__", "__enter__", "__exit__",
    "__call__", "__get__", "__set__", "__delete__", "__new__",
    "__class_getitem__", "setUp", "tearDown", "setUpClass", "tearDownClass",
    # Textual / framework lifecycle
    "compose", "on_mount", "on_unmount", "on_show", "on_hide",
    # Django / DRF
    "get", "post", "put", "patch", "delete", "get_queryset",
    "get_serializer", "perform_create", "perform_update",
})

_SKIP_PREFIXES = (
    "test_", "Test",
    "action_",   # Textual binding actions  — called by the framework
    "watch_",    # Textual reactive watchers — called by the framework
    "on_",       # Textual / framework event handlers
)

_ENTRY_FILENAMES = frozenset({
    "main.py", "app.py", "__main__.py", "manage.py", "wsgi.py", "asgi.py",
    "index.py", "server.py", "run.py",
    "main.ts", "index.ts", "main.js", "index.js",
    "main.go", "main.rs",
})

# Matches @on(...) / @app.route(...) / @router.get(...) etc. followed by a def
_DECORATOR_CALL_RE = re.compile(
    r'@\w[\w.]*\s*\([^)]*\)\s*(?:\n\s*@\w[\w.]*[^\n]*)?\s*\n\s*(?:async\s+)?def\s+(\w+)',
    re.MULTILINE,
)


def _build_referenced_names(analysis: RepoAnalysis) -> frozenset[str]:
    referenced: set[str] = set()
    for file_node in analysis.files:
        if not file_node.content:
            continue
        # Bare-name references that aren't direct calls (dict values, callbacks, etc.)
        for m in re.finditer(r'\b([A-Za-z_]\w*)\b(?!\s*\()', file_node.content):
            referenced.add(m.group(1))
    return frozenset(referenced)


def _build_decorator_registered(analysis: RepoAnalysis) -> frozenset[str]:
    """Functions whose only 'caller' is a decorator — the framework calls them."""
    names: set[str] = set()
    for file_node in analysis.files:
        if not file_node.content:
            continue
        for m in _DECORATOR_CALL_RE.finditer(file_node.content):
            names.add(m.group(1))
    return frozenset(names)


def find_dead_code(analysis: RepoAnalysis) -> list[DeadItem]:
    results: list[DeadItem] = []
    stats = analysis.stats

    handler_names = {e.handler for e in analysis.endpoints}
    referenced_as_value = _build_referenced_names(analysis)
    decorator_registered = _build_decorator_registered(analysis)

    for _, fn in stats.functions.items():
        if fn.callers:
            continue
        if fn.name in _SKIP_NAMES:
            continue
        if fn.name.startswith("__") and fn.name.endswith("__"):
            continue
        if any(fn.name.startswith(p) for p in _SKIP_PREFIXES):
            continue
        if fn.name in handler_names:
            continue
        if fn.name in referenced_as_value:
            continue
        if fn.name in decorator_registered:
            continue
        results.append(DeadItem(
            name=fn.name,
            kind="function",
            file_path=fn.file_path,
            line=fn.line_start,
            reason="no callers found",
        ))

    for f in analysis.files:
        filename = f.path.split("/")[-1]
        if filename in _ENTRY_FILENAMES:
            continue
        if stats.in_degree.get(f.path, 0) == 0:
            results.append(DeadItem(
                name=filename,
                kind="file",
                file_path=f.path,
                line=1,
                reason="never imported",
            ))

    return sorted(results, key=lambda d: (d.file_path, d.line))
