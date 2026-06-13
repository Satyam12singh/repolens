"""RepoLens TUI — Textual-based terminal interface."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from ..models import FileAnalysis, FunctionNode, GraphStats, RepoAnalysis
from .. import ai_client, graph as graph_mod


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: #1a1a2e;
}

Header {
    background: #0d1b2a;
    color: #a8d8ea;
    text-style: bold;
}

Footer {
    background: #0d1b2a;
    color: #4a5568;
}

/* ── Sidebar ── */
#sidebar {
    width: 28;
    min-width: 14;
    max-width: 60;
    border-right: solid #1e3a5f;
    background: #0d1b2a;
}

#sidebar.-focused-pane {
    border-right: solid #a8d8ea;
}

#sidebar-label {
    height: 2;
    background: #0d1b2a;
    color: #a8d8ea;
    text-style: bold;
    padding: 0 1;
    border-bottom: solid #1e3a5f;
    content-align: left middle;
}

#file-tree {
    height: 1fr;
    background: #0d1b2a;
    padding: 0 0;
    scrollbar-color: #1e3a5f;
    scrollbar-background: #0d1b2a;
}

/* ── Main area ── */
#main-area {
    background: #1a1a2e;
}

#tab-bar {
    height: 3;
    background: #0d1b2a;
    padding: 0 1;
}

.tab-btn {
    background: #0d1b2a;
    border: none;
    color: #4a5568;
    min-width: 16;
    height: 3;
    padding: 1 2 0 2;
}

.tab-btn:hover {
    background: #1e3a5f;
    color: #cbd5e0;
    padding: 1 2 0 2;
}

.tab-btn.-active {
    background: #1e3a5f;
    border: solid #a8d8ea;
    color: #a8d8ea;
    text-style: bold;
    padding: 0 2;
}

#content-area {
    height: 1fr;
    padding: 1 3;
    background: #1a1a2e;
    overflow: scroll scroll;
    border-top: solid #1e3a5f;
}

#content-area.-focused-pane {
    border: solid #a8d8ea;
}

#stats-bar {
    height: 2;
    background: #0d1b2a;
    border-top: solid #1e3a5f;
    padding: 0 3;
    color: #4a5568;
    content-align: left middle;
}

/* AI chat screen */
AIScreen {
    align: center middle;
}

#ai-dialog {
    width: 86%;
    height: 86%;
    border: solid #0f3460;
    background: #16213e;
}

#ai-header {
    height: 3;
    width: 100%;
    background: #0f3460;
    padding: 0 2;
    color: #a8d8ea;
    text-style: bold;
    content-align: left middle;
}

#chat-history {
    height: 1fr;
    width: 100%;
    padding: 1 2;
    overflow-y: auto;
    background: #16213e;
}

.msg-user {
    color: #a8d8ea;
    text-style: bold;
    margin-top: 1;
}

.msg-user-text {
    color: #e2e8f0;
    margin-left: 4;
    margin-bottom: 1;
}

.msg-ai-label {
    color: #68d391;
    text-style: bold;
}

.msg-thinking {
    color: #718096;
    text-style: italic;
    margin-left: 4;
    margin-bottom: 1;
}

.msg-divider {
    color: #2d3748;
    margin-top: 1;
    margin-bottom: 1;
}

#ai-input-bar {
    height: 5;
    width: 100%;
    dock: bottom;
    background: #0f3460;
    padding: 1 1;
    align: left middle;
}

#ai-input {
    width: 1fr;
    border: solid #4a5568;
    background: #1a1a2e;
    color: #e2e8f0;
}

#ai-input:focus {
    border: solid #a8d8ea;
}

#btn-close-chat {
    width: 12;
    height: 3;
    margin-left: 1;
    background: #1a1a2e;
    border: solid #4a5568;
    color: #a0aec0;
}

#btn-close-chat:hover {
    background: #2d3748;
    color: #e2e8f0;
}

/* Dep content */
.section-title {
    color: #a8d8ea;
    text-style: bold;
    margin-top: 1;
}

.circular {
    color: #fc8181;
}

.hub {
    color: #f6ad55;
}

.entry {
    color: #68d391;
}

.file-path {
    color: #90cdf4;
}

.import-arrow {
    color: #718096;
}

.count-badge {
    color: #f6ad55;
}
"""


# ── AI Chat Modal ─────────────────────────────────────────────────────────────

class AIScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def __init__(self, analysis: RepoAnalysis, mode: str = "ask") -> None:
        super().__init__()
        self._analysis = analysis
        self._mode = mode
        self._history: list[dict] = []
        self._thinking = False
        self._thinking_widget: Optional[Markdown] = None  # tracked by ref, no ID games

    def compose(self) -> ComposeResult:
        with Vertical(id="ai-dialog"):
            if self._mode == "onboard":
                yield Label(" Onboarding Guide", id="ai-header")
            else:
                yield Label(" Ask AI — multi-turn chat  (Esc to close)", id="ai-header")

            yield ScrollableContainer(id="chat-history")

            if self._mode == "ask":
                with Horizontal(id="ai-input-bar"):
                    yield Input(
                        placeholder="Ask a follow-up… (Enter to send)",
                        id="ai-input",
                    )
                    yield Button("Close", id="btn-close-chat")

    def on_mount(self) -> None:
        if self._mode == "onboard":
            self._run_onboard()
        else:
            self.query_one("#ai-input", Input).focus()

    # ── Chat history rendering ────────────────────────────────────────────────

    def _append_user_bubble(self, question: str) -> None:
        container = self.query_one("#chat-history", ScrollableContainer)
        container.mount(Label("You", classes="msg-user"))
        container.mount(Label(question, classes="msg-user-text"))
        container.scroll_end(animate=False)

    def _append_thinking(self) -> None:
        container = self.query_one("#chat-history", ScrollableContainer)
        container.mount(Label("RepoLens AI", classes="msg-ai-label"))
        self._thinking_widget = Markdown("_thinking…_", classes="msg-thinking")
        container.mount(self._thinking_widget)
        container.scroll_end(animate=False)

    def _replace_thinking(self, answer: str) -> None:
        if self._thinking_widget is not None:
            self._thinking_widget.update(answer)
            self._thinking_widget = None
        container = self.query_one("#chat-history", ScrollableContainer)
        container.mount(Label("─" * 60, classes="msg-divider"))
        container.scroll_end(animate=False)

    # ── Onboarding mode ───────────────────────────────────────────────────────

    @work(thread=True)
    def _run_onboard(self) -> None:
        container = self.app.call_from_thread(self._start_onboard_ui)
        try:
            result = ai_client.generate_onboarding(self._analysis)
        except Exception as exc:
            result = f"**Error:** {exc}"
        self.app.call_from_thread(self._finish_onboard_ui, result)

    def _start_onboard_ui(self) -> None:
        container = self.query_one("#chat-history", ScrollableContainer)
        container.mount(Label("RepoLens AI", classes="msg-ai-label"))
        self._thinking_widget = Markdown("_Generating onboarding guide…_", classes="msg-thinking")
        container.mount(self._thinking_widget)

    def _finish_onboard_ui(self, text: str) -> None:
        self._replace_thinking(text)

    # ── Ask / follow-up ───────────────────────────────────────────────────────

    @on(Input.Submitted, "#ai-input")
    def _on_submitted(self, event: Input.Submitted) -> None:
        question = event.value.strip()
        if not question or self._thinking:
            return
        self._thinking = True
        self.query_one("#ai-input", Input).value = ""
        self._append_user_bubble(question)
        self._append_thinking()
        self._run_ask(question)

    @work(thread=True)
    def _run_ask(self, question: str) -> None:
        try:
            answer = ai_client.ask(self._analysis, question, history=list(self._history))
        except Exception as exc:
            answer = f"**Error:** {exc}"
        # Update history for next turn
        self._history.append({"role": "user", "content": question})
        self._history.append({"role": "assistant", "content": answer})
        self.app.call_from_thread(self._on_answer_ready, answer)

    def _on_answer_ready(self, answer: str) -> None:
        self._replace_thinking(answer)
        self._thinking = False
        self.query_one("#ai-input", Input).focus()

    @on(Button.Pressed, "#btn-close-chat")
    def _close(self) -> None:
        self.dismiss()


# ── Main App ──────────────────────────────────────────────────────────────────

class RepoLensApp(App):
    TITLE = "RepoLens"
    CSS = CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("1", "tab_deps", "Deps"),
        Binding("2", "tab_calls", "Calls"),
        Binding("3", "tab_graph", "Full Graph"),
        Binding("a", "ask_ai", "Ask AI"),
        Binding("o", "onboard", "Onboard"),
        Binding("f", "focus_next_pane", "Focus pane"),
        Binding("]", "sidebar_grow", "Sidebar ▶"),
        Binding("[", "sidebar_shrink", "◀ Sidebar"),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]

    current_tab: reactive[str] = reactive("deps")
    selected_file: reactive[Optional[str]] = reactive(None)
    sidebar_width: reactive[int] = reactive(28)
    _focus_on_content: bool = False

    def __init__(self, analysis: RepoAnalysis) -> None:
        super().__init__()
        self._analysis = analysis

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("  FILES", id="sidebar-label")
                yield Tree(".", id="file-tree")
            with Vertical(id="main-area"):
                with Horizontal(id="tab-bar"):
                    yield Button("1 Dependencies", classes="tab-btn -active", id="tab-deps-btn")
                    yield Button("2 Call Graph",   classes="tab-btn",         id="tab-calls-btn")
                    yield Button("3 Full Graph",   classes="tab-btn",         id="tab-graph-btn")
                yield ScrollableContainer(
                    Static("", id="content"),
                    id="content-area",
                )
                yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._populate_file_tree()
        self._update_stats_bar()
        self._render_content()

    # ── File Tree ─────────────────────────────────────────────────────────────

    def _populate_file_tree(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        tree.root.expand()
        stats = self._analysis.stats
        root_path = Path(self._analysis.root).name

        # Build directory hierarchy
        dir_nodes: dict[str, TreeNode] = {}

        def get_dir_node(parts: list[str]) -> TreeNode:
            key = "/".join(parts)
            if key in dir_nodes:
                return dir_nodes[key]
            if len(parts) == 1:
                node = tree.root.add(f" {parts[0]}/", expand=True)
            else:
                parent = get_dir_node(parts[:-1])
                node = parent.add(f" {parts[-1]}/", expand=True)
            dir_nodes[key] = node
            return node

        for file_node in self._analysis.files:
            parts = file_node.path.split("/")
            in_deg = stats.in_degree.get(file_node.path, 0)

            lang_icon = {
                "python": "🐍",
                "javascript": "󰌞",
                "typescript": "󰛦",
                "go": "󰟓",
                "rust": "",
            }.get(file_node.language, "")

            label = parts[-1]
            if in_deg > 0:
                label += f" ({in_deg} importers)"

            is_circular = any(file_node.path in c for c in stats.circular_deps)
            is_hub = in_deg >= 5

            rich_label = Text(label)
            if is_circular:
                rich_label.stylize("bold red")
            elif is_hub:
                rich_label.stylize("bold yellow")

            if len(parts) == 1:
                leaf = tree.root.add_leaf(label)
            else:
                parent = get_dir_node(parts[:-1])
                leaf = parent.add_leaf(label)

            leaf.data = file_node.path  # store path for selection

        tree.root.label = Text(f" {root_path} ({len(self._analysis.files)} files)")

    # ── Stats Bar ─────────────────────────────────────────────────────────────

    def _update_stats_bar(self) -> None:
        stats = self._analysis.stats
        n_files  = len(self._analysis.files)
        n_funcs  = len(stats.functions)
        n_cycles = len(stats.circular_deps)
        cycle_str = (
            f"  [red]! {n_cycles} circular dep{'s' if n_cycles != 1 else ''}[/]"
            if n_cycles else
            "  [green]no circular deps[/]"
        )
        text = (
            f"  [bold]{n_files}[/] files"
            f"   [bold]{n_funcs}[/] functions"
            f"{cycle_str}"
            f"   [bold]{len(stats.entry_points)}[/] entry points"
            f"   [dim][ / ] resize   [f] switch pane[/]"
        )
        self.query_one("#stats-bar", Static).update(text)

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _set_active_tab(self, tab: str) -> None:
        self.current_tab = tab
        for btn_id in ("tab-deps-btn", "tab-calls-btn", "tab-graph-btn"):
            btn = self.query_one(f"#{btn_id}", Button)
            btn.remove_class("-active")
        self.query_one(f"#tab-{tab}-btn", Button).add_class("-active")
        self._render_content()

    @on(Button.Pressed, "#tab-deps-btn")
    def _tab_deps(self) -> None:
        self._set_active_tab("deps")

    @on(Button.Pressed, "#tab-calls-btn")
    def _tab_calls(self) -> None:
        self._set_active_tab("calls")

    @on(Button.Pressed, "#tab-graph-btn")
    def _tab_graph(self) -> None:
        self._set_active_tab("graph")

    def action_tab_deps(self) -> None:
        self._set_active_tab("deps")

    def action_tab_calls(self) -> None:
        self._set_active_tab("calls")

    def action_tab_graph(self) -> None:
        self._set_active_tab("graph")

    # ── Tree selection ────────────────────────────────────────────────────────

    @on(Tree.NodeHighlighted, "#file-tree")
    def _on_file_highlighted(self, event: Tree.NodeHighlighted) -> None:
        # data is set on file leaves; directory nodes have no data → show overview
        self.selected_file = event.node.data or None
        self._render_content()

    # ── Content rendering ─────────────────────────────────────────────────────

    def _render_content(self) -> None:
        content = self.query_one("#content", Static)
        if self.selected_file and self.selected_file.endswith(".md"):
            content.update(self._render_doc_file())
            return
        if self.current_tab == "deps":
            content.update(self._render_deps())
        elif self.current_tab == "calls":
            content.update(self._render_calls())
        elif self.current_tab == "graph":
            content.update(self._render_full_graph())

    def _render_doc_file(self) -> Text:
        t = Text()
        file_node = next((f for f in self._analysis.files if f.path == self.selected_file), None)
        if not file_node or not file_node.content:
            t.append("  (empty)", style="#4a5568")
            return t
        t.append(f"\n  {self.selected_file}\n\n", style="bold cyan")
        t.append(file_node.content, style="#e2e8f0")
        return t

    # ── Tree-drawing helpers ──────────────────────────────────────────────────

    @staticmethod
    def _branch(t: Text, indent: str, items: list[tuple[str, str, str, str]]) -> None:
        """Append tree-branch lines to *t*.

        items: list of (prefix_label, prefix_style, body_label, body_style)
        Uses ├──→ for all but the last item, └──→ for the last.
        """
        for i, (pre_label, pre_style, body_label, body_style) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            t.append(indent + connector, style="#4a5568")
            t.append(pre_label, style=pre_style)
            if body_label:
                t.append(body_label, style=body_style)
            t.append("\n")

    @staticmethod
    def _branch_arrow(
        t: Text,
        indent: str,
        items: list[tuple[str, str]],   # (label, style)
        arrow: str = "──→",
    ) -> None:
        """Append arrow-branch lines (├──→ / └──→) for dependency lists."""
        for i, (label, style) in enumerate(items):
            is_last = i == len(items) - 1
            connector = f"└{arrow} " if is_last else f"├{arrow} "
            t.append(indent + connector, style="#4a5568")
            t.append(label + "\n", style=style)

    # ── Deps view ─────────────────────────────────────────────────────────────

    def _render_deps(self) -> Text:
        stats = self._analysis.stats
        t = Text()

        if self.selected_file:
            fa = self._analysis.file_analyses.get(self.selected_file)
            t.append(f"\n  {self.selected_file}\n", style="bold cyan")

            if fa:
                deps        = stats.import_edges.get(self.selected_file, [])
                importers   = graph_mod.importers_of(self.selected_file, stats)
                has_funcs   = bool(fa.functions)
                has_classes = bool(fa.classes)

                # ── IMPORTS ──────────────────────────────────────────────────
                section_connector = "├── " if (importers or has_funcs or has_classes) else "└── "
                t.append(f"  {section_connector}", style="#4a5568")
                t.append("IMPORTS\n", style="bold #a8d8ea")

                if deps:
                    cont = "│   " if (importers or has_funcs or has_classes) else "    "
                    dep_items = []
                    for dep in deps:
                        in_deg = stats.in_degree.get(dep, 0)
                        is_circ = any(self.selected_file in c and dep in c for c in stats.circular_deps)
                        label = dep
                        if in_deg > 0:
                            label += f"  (used by {in_deg} files)"
                        if is_circ:
                            label += "  ⚠ CIRCULAR"
                        dep_items.append((label, "bold red" if is_circ else "#90cdf4"))
                    self._branch_arrow(t, f"  {cont}", dep_items, arrow="──→")
                else:
                    cont = "│   " if (importers or has_funcs or has_classes) else "    "
                    t.append(f"  {cont}    (no local imports)\n", style="#4a5568")

                # ── IMPORTED BY ───────────────────────────────────────────────
                if importers or has_funcs or has_classes:
                    section_connector = "├── " if (has_funcs or has_classes) else "└── "
                    t.append(f"  {section_connector}", style="#4a5568")
                    t.append("IMPORTED BY\n", style="bold #a8d8ea")
                    cont = "│   " if (has_funcs or has_classes) else "    "
                    if importers:
                        imp_items = [(imp, "#90cdf4") for imp in importers]
                        self._branch_arrow(t, f"  {cont}", imp_items, arrow="──←")
                    else:
                        t.append(f"  {cont}    (entry point — nothing imports this)\n", style="#68d391")

                # ── FUNCTIONS ────────────────────────────────────────────────
                if has_funcs:
                    section_connector = "├── " if has_classes else "└── "
                    t.append(f"  {section_connector}", style="#4a5568")
                    t.append("FUNCTIONS\n", style="bold #a8d8ea")
                    cont = "│   " if has_classes else "    "
                    fns = fa.functions[:20]
                    for i, fn in enumerate(fns):
                        is_last_fn = i == len(fns) - 1
                        fn_conn = "└── " if is_last_fn else "├── "
                        fn_cont = "    " if is_last_fn else "│   "
                        # function name + line number
                        t.append(f"  {cont}{fn_conn}", style="#4a5568")
                        t.append(fn.name, style="bold #e2e8f0")
                        t.append(f"  line {fn.line_start}\n", style="#718096")
                        # docstring directly under its function, labelled
                        if fn.docstring:
                            t.append(f"  {cont}{fn_cont}  ", style="#4a5568")
                            t.append('"""', style="#4a5568")
                            t.append(f" {fn.docstring}\n", style="italic #a0aec0")

                # ── CLASSES ──────────────────────────────────────────────────
                if has_classes:
                    t.append("  └── ", style="#4a5568")
                    t.append("CLASSES\n", style="bold #a8d8ea")
                    cls_items = [("", "", cls, "#e2e8f0") for cls in fa.classes]
                    self._branch(t, "      ", cls_items)

        else:
            # ── Overview ─────────────────────────────────────────────────────
            t.append("\n  DEPENDENCY OVERVIEW\n", style="bold #a8d8ea")

            if stats.circular_deps:
                t.append("\n  ⚠  CIRCULAR DEPENDENCIES\n", style="bold red")
                for cycle in stats.circular_deps:
                    t.append("  │\n", style="#4a5568")
                    chain = " ──→ ".join(cycle) + " ──→ " + cycle[0]
                    t.append(f"  └── {chain}\n", style="red")

            t.append("\n  MOST IMPORTED FILES\n", style="bold #a8d8ea")
            hub = [(p, c) for p, c in stats.hub_files[:10] if c > 0]
            for i, (path, count) in enumerate(hub):
                is_last = i == len(hub) - 1
                conn = "└── " if is_last else "├── "
                bar = "▪" * min(count, 15)
                t.append(f"  {conn}", style="#4a5568")
                t.append(f"{bar} {count:>2}  ", style="#f6ad55")
                t.append(path + "\n", style="#90cdf4")

            t.append("\n  ENTRY POINTS\n", style="bold #a8d8ea")
            eps = stats.entry_points[:15]
            for i, ep in enumerate(eps):
                is_last = i == len(eps) - 1
                conn = "└──> " if is_last else "├──> "
                t.append(f"  {conn}", style="#4a5568")
                t.append(ep + "\n", style="#68d391")

        return t

    # ── Call graph view ───────────────────────────────────────────────────────

    def _render_calls(self) -> Text:
        stats = self._analysis.stats
        t = Text()

        if self.selected_file:
            fa = self._analysis.file_analyses.get(self.selected_file)
            t.append(f"\n  {self.selected_file}\n", style="bold cyan")

            if fa and fa.functions:
                for fn_idx, fn in enumerate(fa.functions[:30]):
                    fid     = f"{self.selected_file}::{fn.name}"
                    fn_obj  = stats.functions.get(fid)
                    callees = graph_mod.callees_of(fid, stats) if fn_obj else []
                    callers = graph_mod.callers_of(fid, stats) if fn_obj else []

                    is_last_fn = fn_idx == len(fa.functions[:30]) - 1
                    fn_conn = "└── " if is_last_fn else "├── "
                    fn_cont = "    " if is_last_fn else "│   "

                    # Function header
                    t.append(f"  {fn_conn}", style="#4a5568")
                    t.append(f"fn {fn.name}", style="bold #e2e8f0")
                    t.append(f"  line {fn.line_start}\n", style="#718096")

                    # Docstring — labelled inline under the function name
                    if fn.docstring:
                        t.append(f"  {fn_cont}  ", style="#4a5568")
                        t.append('"""', style="#4a5568")
                        t.append(f" {fn.docstring}\n", style="italic #a0aec0")

                    has_calls   = bool(callees)
                    has_callers = bool(callers)

                    # what this function calls
                    if has_calls:
                        sub_conn = "├── " if has_callers else "└── "
                        sub_cont = "│   " if has_callers else "    "
                        t.append(f"  {fn_cont}{sub_conn}", style="#4a5568")
                        t.append(f"calls {len(callees)} function(s)\n", style="#a0aec0")
                        call_items = [(c, "#90cdf4") for c in callees[:8]]
                        self._branch_arrow(t, f"  {fn_cont}{sub_cont}", call_items, arrow="──→")

                    # what calls this function
                    if has_callers:
                        t.append(f"  {fn_cont}└── ", style="#4a5568")
                        t.append(f"called by {len(callers)} function(s)\n", style="#a0aec0")
                        caller_items = [(c, "#68d391") for c in callers[:8]]
                        self._branch_arrow(t, f"  {fn_cont}    ", caller_items, arrow="──←")

                    if not is_last_fn:
                        t.append(f"  │\n", style="#4a5568")
            else:
                t.append("  └── (no functions found)\n", style="#718096")

        else:
            self._render_call_overview(t, stats)

        return t

    def _render_call_overview(self, t: Text, stats: "GraphStats") -> None:
        all_fns = list(stats.functions.values())
        total   = len(all_fns)
        t.append(f"\n  CALL GRAPH  ·  {total} functions\n", style="bold #a8d8ea")

        if not all_fns:
            t.append("  No functions found.\n", style="#718096")
            return

        # ── Ranked table ─────────────────────────────────────────────────────
        by_total = sorted(all_fns, key=lambda f: len(f.callers) + len(f.calls), reverse=True)[:20]
        max_callers = max((len(f.callers) for f in by_total), default=1) or 1
        max_calls   = max((len(f.calls)   for f in by_total), default=1) or 1

        t.append("\n  MOST CONNECTED FUNCTIONS\n", style="bold #a8d8ea")
        # column header
        t.append("  " + "─" * 72 + "\n", style="#2d3748")
        t.append(
            f"  {'#':<4}{'function':<26}{'callers':<22}{'calls':<22}{'file'}\n",
            style="#4a5568",
        )
        t.append("  " + "─" * 72 + "\n", style="#2d3748")

        for rank, fn in enumerate(by_total, 1):
            n_callers = len(fn.callers)
            n_calls   = len(fn.calls)

            # colour-code by role
            if n_callers == 0:
                fn_style = "#68d391"   # green  — entry / standalone
            elif n_calls == 0:
                fn_style = "#fc8181"   # red    — sink / leaf
            elif n_callers >= 4:
                fn_style = "#f6ad55"   # orange — hot hub
            else:
                fn_style = "#e2e8f0"   # white  — normal

            # proportional bars (max 10 chars each)
            caller_bar = "▪" * round(n_callers / max_callers * 10)
            calls_bar  = "▪" * round(n_calls   / max_calls   * 10)

            caller_col = f"{caller_bar:<10} {n_callers}"
            calls_col  = f"{calls_bar:<10} {n_calls}"

            fname = fn.name[:24]
            fpath = fn.file_path

            t.append(f"  {rank:<4}", style="#4a5568")
            t.append(f"{fname:<26}", style=fn_style)
            t.append(f"{caller_col:<22}", style="#a8d8ea")
            t.append(f"{calls_col:<22}", style="#90cdf4")
            t.append(f"{fpath}\n", style="#4a5568")

        t.append("  " + "─" * 72 + "\n", style="#2d3748")

        # ── Legend ────────────────────────────────────────────────────────────
        t.append("\n  LEGEND  ", style="#4a5568")
        t.append("* ", style="#68d391");  t.append("entry (nothing calls it)  ", style="#718096")
        t.append("* ", style="#f6ad55");  t.append("hub (called 4+ times)  ", style="#718096")
        t.append("* ", style="#fc8181");  t.append("leaf (calls nothing)\n", style="#718096")

        # ── Entry functions ───────────────────────────────────────────────────
        entries = [f for f in all_fns if not f.callers][:10]
        if entries:
            t.append("\n  ENTRY FUNCTIONS  (nothing calls these — start reading here)\n",
                     style="bold #a8d8ea")
            entry_items = [(fn.name, "#68d391", f"  {fn.file_path}", "#4a5568") for fn in entries]
            self._branch(t, "  ", entry_items)

        # ── Hottest hubs ──────────────────────────────────────────────────────
        hubs = [f for f in all_fns if len(f.callers) >= 4]
        if hubs:
            hubs.sort(key=lambda f: len(f.callers), reverse=True)
            t.append("\n  HOT HUBS  (called most frequently — high-impact functions)\n",
                     style="bold #a8d8ea")
            hub_items = [
                (fn.name, "#f6ad55", f"  called {len(fn.callers)}×  ·  {fn.file_path}", "#4a5568")
                for fn in hubs[:8]
            ]
            self._branch(t, "  ", hub_items)

    # ── Full graph view ───────────────────────────────────────────────────────

    def _render_full_graph(self) -> Text:
        stats = self._analysis.stats
        t = Text()
        t.append("\n  FULL IMPORT GRAPH\n", style="bold #a8d8ea")

        entries = [(src, deps) for src, deps in sorted(stats.import_edges.items()) if deps]

        if not entries:
            t.append("  └── No inter-file imports found.\n", style="#718096")
            return t

        for src_idx, (src, deps) in enumerate(entries):
            is_last_src = src_idx == len(entries) - 1
            src_conn = "└── " if is_last_src else "├── "
            src_cont = "    " if is_last_src else "│   "

            is_circ = any(src in c for c in stats.circular_deps)
            t.append(f"\n  {src_conn}", style="#4a5568")
            t.append(src, style="bold red" if is_circ else "bold #90cdf4")
            if is_circ:
                t.append("  ⚠ CIRCULAR", style="bold red")
            t.append("\n")

            dep_items = []
            for dep in deps:
                dep_circ = any(dep in c for c in stats.circular_deps)
                in_deg   = stats.in_degree.get(dep, 0)
                label    = dep + (f"  (used by {in_deg} files)" if in_deg > 1 else "")
                dep_items.append((label, "red" if dep_circ else "#a0aec0"))
            self._branch_arrow(t, f"  {src_cont}", dep_items, arrow="──→")

        return t

    # ── Sidebar resize ────────────────────────────────────────────────────────

    def watch_sidebar_width(self, width: int) -> None:
        self.query_one("#sidebar").styles.width = width

    def action_sidebar_grow(self) -> None:
        self.sidebar_width = min(self.sidebar_width + 2, 60)

    def action_sidebar_shrink(self) -> None:
        self.sidebar_width = max(self.sidebar_width - 2, 14)

    # ── Pane focus switching ──────────────────────────────────────────────────

    def action_focus_next_pane(self) -> None:
        self._focus_on_content = not self._focus_on_content
        if self._focus_on_content:
            area = self.query_one("#content-area", ScrollableContainer)
            area.focus()
            area.add_class("-focused-pane")
            self.query_one("#sidebar").remove_class("-focused-pane")
        else:
            self.query_one("#file-tree", Tree).focus()
            self.query_one("#sidebar").add_class("-focused-pane")
            self.query_one("#content-area", ScrollableContainer).remove_class("-focused-pane")

    # ── Override j/k to go to correct widget ─────────────────────────────────

    def action_cursor_down(self) -> None:
        if self._focus_on_content:
            self.query_one("#content-area", ScrollableContainer).scroll_down()
        else:
            self.query_one("#file-tree", Tree).action_cursor_down()

    def action_cursor_up(self) -> None:
        if self._focus_on_content:
            self.query_one("#content-area", ScrollableContainer).scroll_up()
        else:
            self.query_one("#file-tree", Tree).action_cursor_up()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_ask_ai(self) -> None:
        if not ai_client.is_configured():
            self.notify(
                "No AI provider configured. Set GEMINI_API_KEY, OPENAI_API_KEY, GROQ_API_KEY, or ANTHROPIC_API_KEY.",
                title="AI not configured",
                severity="warning",
                timeout=6,
            )
            return
        self.push_screen(AIScreen(self._analysis, mode="ask"))

    def action_onboard(self) -> None:
        if not ai_client.is_configured():
            self.notify(
                "No AI provider configured. Set GEMINI_API_KEY, OPENAI_API_KEY, GROQ_API_KEY, or ANTHROPIC_API_KEY.",
                title="AI not configured",
                severity="warning",
                timeout=6,
            )
            return
        self.push_screen(AIScreen(self._analysis, mode="onboard"))

    def action_refresh_view(self) -> None:
        self._render_content()
