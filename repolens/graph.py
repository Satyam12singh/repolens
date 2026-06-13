"""Build and analyse dependency and call graphs from FileAnalysis data."""
from __future__ import annotations

from .models import FileAnalysis, FunctionNode, GraphStats


def build_graph(analyses: dict[str, FileAnalysis]) -> GraphStats:
    stats = GraphStats()

    # ── Import graph ──────────────────────────────────────────────────────────
    in_degree: dict[str, int] = {p: 0 for p in analyses}

    for path, fa in analyses.items():
        unique_imports = list(dict.fromkeys(fa.resolved_imports))  # deduplicate, preserve order
        stats.import_edges[path] = unique_imports
        for dep in unique_imports:
            if dep in in_degree:
                in_degree[dep] = in_degree.get(dep, 0) + 1
            else:
                in_degree[dep] = 1

    stats.in_degree = in_degree

    # ── Circular dependency detection (iterative DFS) ─────────────────────────
    stats.circular_deps = _find_cycles(stats.import_edges)

    # ── Entry points (source files nobody imports) ────────────────────────────
    stats.entry_points = [
        p for p in analyses if in_degree.get(p, 0) == 0
    ]

    # ── Hub files (most imported) ─────────────────────────────────────────────
    stats.hub_files = sorted(
        [(p, in_degree.get(p, 0)) for p in analyses],
        key=lambda x: x[1],
        reverse=True,
    )[:10]

    # ── Function index & caller resolution ────────────────────────────────────
    # Build name -> list[function_id] index for resolving calls
    name_index: dict[str, list[str]] = {}
    for path, fa in analyses.items():
        for fn in fa.functions:
            fid = f"{path}::{fn.name}"
            fn_copy = FunctionNode(
                name=fn.name,
                file_path=fn.file_path,
                line_start=fn.line_start,
                line_end=fn.line_end,
                calls=list(fn.calls),
            )
            stats.functions[fid] = fn_copy
            name_index.setdefault(fn.name, []).append(fid)

    # Resolve calls to function IDs and back-populate callers
    for fid, fn in stats.functions.items():
        resolved_calls: list[str] = []
        for call in fn.calls:
            base_name = call.split(".")[-1]  # handle obj.method style
            for candidate in name_index.get(base_name, []):
                resolved_calls.append(candidate)
                stats.functions[candidate].callers.append(fid)
        fn.calls = list(dict.fromkeys(resolved_calls))

    return stats


def _find_cycles(edges: dict[str, list[str]]) -> list[list[str]]:
    """Detect all simple cycles using iterative DFS (Johnson-lite)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in edges}
    # include all targets too
    for deps in edges.values():
        for d in deps:
            color.setdefault(d, WHITE)

    cycles: list[list[str]] = []
    parent: dict[str, str | None] = {}

    for start in list(color):
        if color[start] != WHITE:
            continue
        stack = [(start, iter(edges.get(start, [])))]
        color[start] = GRAY
        path = [start]
        parent[start] = None

        while stack:
            node, children = stack[-1]
            try:
                child = next(children)
                if color.get(child, WHITE) == GRAY:
                    # Found a back-edge → extract cycle
                    idx = path.index(child)
                    cycle = path[idx:]
                    # Deduplicate: only add if we haven't seen this cycle (by sorted set)
                    cycle_key = frozenset(cycle)
                    if not any(frozenset(c) == cycle_key for c in cycles):
                        cycles.append(cycle)
                elif color.get(child, WHITE) == WHITE:
                    color[child] = GRAY
                    parent[child] = node
                    path.append(child)
                    stack.append((child, iter(edges.get(child, []))))
            except StopIteration:
                color[node] = BLACK
                stack.pop()
                if path and path[-1] == node:
                    path.pop()

    return cycles


def importers_of(path: str, stats: GraphStats) -> list[str]:
    """Return list of files that import *path*."""
    return [src for src, deps in stats.import_edges.items() if path in deps]


def callers_of(function_id: str, stats: GraphStats) -> list[str]:
    fn = stats.functions.get(function_id)
    return fn.callers if fn else []


def callees_of(function_id: str, stats: GraphStats) -> list[str]:
    fn = stats.functions.get(function_id)
    return fn.calls if fn else []
