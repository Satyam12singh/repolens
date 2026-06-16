#!/usr/bin/env python3
"""RepoLens CLI — `repolens [path]`"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="repolens",
        description="RepoLens — AI-native codebase intelligence",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to analyse (default: current directory)",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip AI features (no ANTHROPIC_API_KEY needed)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=2000,
        help="Max source files to scan (default: 2000)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output analysis as JSON instead of launching TUI",
    )
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"RepoLens  scanning {root} …")

    # Load .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    from repolens.scanner import scan
    from repolens.analyzer import analyze_all
    from repolens.graph import build_graph
    from repolens.models import RepoAnalysis

    print("  Walking directory tree…")
    files = scan(str(root), max_files=args.max_files)
    print(f"  Found {len(files)} source files.")

    print("  Analysing imports and functions…")
    file_analyses = analyze_all(files)
    print(f"  Analysed {len(file_analyses)} files.")

    print("  Building dependency and call graphs…")
    stats = build_graph(file_analyses)

    print("  Scanning API endpoints and DTOs…")
    from repolens.api_scanner import scan_all as api_scan_all
    endpoints, dtos = api_scan_all(files)

    analysis = RepoAnalysis(
        root=str(root),
        files=files,
        file_analyses=file_analyses,
        stats=stats,
        endpoints=endpoints,
        dtos=dtos,
    )

    n_cycles = len(stats.circular_deps)
    print(f"  Done. {len(stats.functions)} functions  ·  {len(endpoints)} endpoints  ·  {len(dtos)} DTOs  ·  {n_cycles} circular dep(s)")

    if args.json:
        _print_json(analysis)
        return

    if args.no_ai:
        import os
        os.environ.setdefault("ANTHROPIC_API_KEY", "")

    print("  Launching TUI…\n")
    from repolens.tui.app import RepoLensApp
    app = RepoLensApp(analysis)
    app.run()


def _print_json(analysis: "RepoAnalysis") -> None:
    import json

    stats = analysis.stats
    output = {
        "root": analysis.root,
        "total_files": len(analysis.files),
        "files": [
            {"path": f.path, "language": f.language, "size": f.size}
            for f in analysis.files
        ],
        "import_graph": {k: v for k, v in stats.import_edges.items() if v},
        "circular_deps": stats.circular_deps,
        "hub_files": [{"path": p, "in_degree": d} for p, d in stats.hub_files],
        "entry_points": stats.entry_points,
        "functions": [
            {
                "id": fid,
                "name": fn.name,
                "file": fn.file_path,
                "line": fn.line_start,
                "calls": fn.calls,
                "callers": fn.callers,
            }
            for fid, fn in stats.functions.items()
        ],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
