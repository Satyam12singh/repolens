"""RepoLens TUI — Textual-based terminal interface."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import events, on, work
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

from ..models import ApiEndpoint, DtoModel, FileAnalysis, FunctionNode, GraphStats, RepoAnalysis
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
    max-width: 51;
    border-right: solid #1e3a5f;
    background: #0d1b2a;
}

#sidebar.-focused-pane {
    /* state marker only — visual border is on #file-tree */
}

#file-tree.-focused-pane {
    border: solid #a8d8ea;
    margin-bottom: 1;
}

#file-tree .tree--cursor {
    background: #1e3a5f;
    color: #a8d8ea;
}

#file-tree:focus .tree--cursor {
    background: #1e3a5f;
    color: #a8d8ea;
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

#fn-panel {
    display: none;
    height: 1fr;
    border-top: solid #1e3a5f;
}

#fn-panel.-focused-pane {
    border: solid #a8d8ea;
}

#fn-left {
    width: 32;
    border-right: solid #1e3a5f;
    background: #0d1b2a;
}

#fn-search {
    height: 3;
    background: #0d1b2a;
    color: #e2e8f0;
    border: solid #1e3a5f;
    padding: 0 1;
}

#fn-search:focus {
    border: solid #a8d8ea;
}

#fn-list-scroll {
    width: 1fr;
    background: #0d1b2a;
    padding: 0 1;
}

#fn-code-scroll {
    width: 1fr;
    background: #1a1a2e;
    padding: 0 2;
}

#api-panel {
    display: none;
    height: 1fr;
    border-top: solid #1e3a5f;
}

#api-panel.-focused-pane {
    border: solid #a8d8ea;
}

#api-left {
    width: 42;
    border-right: solid #1e3a5f;
    background: #0d1b2a;
}

#api-toggle-bar {
    height: 3;
    background: #0d1b2a;
    padding: 0 1;
}

.api-toggle {
    width: 1fr;
    background: #0d1b2a;
    border: none;
    color: #4a5568;
    height: 3;
    padding: 1 2 0 2;
    content-align: center middle;
}

.api-toggle:hover {
    background: #1e3a5f;
    color: #cbd5e0;
    padding: 1 2 0 2;
    content-align: center middle;
}

.api-toggle.-active-toggle {
    background: #1e3a5f;
    border: solid #a8d8ea;
    color: #a8d8ea;
    text-style: bold;
    padding: 0 2;
    content-align: center middle;
}

#api-search {
    height: 3;
    background: #0d1b2a;
    color: #e2e8f0;
    border: solid #1e3a5f;
    padding: 0 1;
}

#api-search:focus {
    border: solid #a8d8ea;
}

#api-list-scroll {
    width: 1fr;
    background: #0d1b2a;
    padding: 0 1;
}

#api-detail-scroll {
    width: 1fr;
    background: #1a1a2e;
    padding: 0 2;
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

.msg-cache-note {
    color: #68d391;
    text-style: italic;
    background: #0a1f0a;
    padding: 0 2;
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
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("r", "regenerate", "Regenerate", show=False),
    ]

    def __init__(self, analysis: RepoAnalysis, mode: str = "ask") -> None:
        super().__init__()
        self._analysis = analysis
        self._mode = mode
        self._history: list[dict] = []
        self._thinking = False
        self._thinking_widget: Optional[Markdown] = None
        self._from_cache = False

    def _cache_path(self) -> Path:
        return Path(self._analysis.root) / ".repolens" / "onboard.md"

    def _load_from_cache(self) -> Optional[str]:
        p = self._cache_path()
        if p.exists():
            return p.read_text(encoding="utf-8")
        return None

    def _save_to_cache(self, text: str) -> None:
        p = self._cache_path()
        p.parent.mkdir(exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def compose(self) -> ComposeResult:
        with Vertical(id="ai-dialog"):
            if self._mode == "onboard":
                yield Label(" Codebase Guide  (Esc to close  ·  r — regenerate)", id="ai-header")
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
            cached = self._load_from_cache()
            if cached:
                self._from_cache = True
                self._show_cached(cached)
            else:
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

    def _show_cached(self, text: str) -> None:
        container = self.query_one("#chat-history", ScrollableContainer)
        container.mount(Label(
            " Loaded from cache  ·  press r to regenerate",
            classes="msg-cache-note",
        ))
        container.mount(Label("RepoLens AI", classes="msg-ai-label"))
        container.mount(Markdown(text, classes="msg-thinking"))
        container.scroll_home(animate=False)

    def action_regenerate(self) -> None:
        if self._mode != "onboard" or self._thinking:
            return
        p = self._cache_path()
        if p.exists():
            p.unlink()
        self._from_cache = False
        container = self.query_one("#chat-history", ScrollableContainer)
        container.remove_children()
        self._run_onboard()

    @work(thread=True)
    def _run_onboard(self) -> None:
        self.app.call_from_thread(self._start_onboard_ui)
        try:
            result = ai_client.generate_onboarding(self._analysis)
        except Exception as exc:
            result = f"**Error:** {exc}"
        self.app.call_from_thread(self._finish_onboard_ui, result)

    def _start_onboard_ui(self) -> None:
        container = self.query_one("#chat-history", ScrollableContainer)
        container.mount(Label("RepoLens AI", classes="msg-ai-label"))
        self._thinking_widget = Markdown("_Generating codebase guide…_", classes="msg-thinking")
        container.mount(self._thinking_widget)

    def _finish_onboard_ui(self, text: str) -> None:
        self._replace_thinking(text)
        self._save_to_cache(text)

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
        Binding("4", "tab_funcs", "Functions"),
        Binding("5", "tab_api", "API"),
        Binding("a", "ask_ai", "Ask AI"),
        Binding("o", "onboard", "Codebase Guide"),
        Binding("f", "focus_next_pane", "Focus pane"),
        Binding("]", "sidebar_grow", "Sidebar ▶"),
        Binding("[", "sidebar_shrink", "◀ Sidebar"),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("g", "goto_funcs", "Functions", show=False),
        Binding("up",   "navigate_up",   "", show=False, priority=True),
        Binding("down", "navigate_down", "", show=False, priority=True),
    ]

    current_tab: reactive[str] = reactive("deps")
    selected_file: reactive[Optional[str]] = reactive(None)
    sidebar_width: reactive[int] = reactive(28)
    _focus_on_content: bool = False
    _fn_selected: int = 0
    _fn_search: str = ""
    _min_sidebar_width: int = 14
    _api_view: str = "endpoints"   # "endpoints" | "dtos"
    _api_selected: int = 0
    _api_search: str = ""

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
                    yield Button("4 Functions",    classes="tab-btn",         id="tab-funcs-btn")
                    yield Button("5 API",          classes="tab-btn",         id="tab-api-btn")
                yield ScrollableContainer(
                    Static("", id="content"),
                    id="content-area",
                )
                with Horizontal(id="fn-panel"):
                    with Vertical(id="fn-left"):
                        yield Input(placeholder="  search functions…", id="fn-search")
                        with ScrollableContainer(id="fn-list-scroll"):
                            yield Static("", id="fn-list")
                    with ScrollableContainer(id="fn-code-scroll"):
                        yield Static("", id="fn-code")
                with Horizontal(id="api-panel"):
                    with Vertical(id="api-left"):
                        with Horizontal(id="api-toggle-bar"):
                            yield Button("Endpoints", classes="api-toggle -active-toggle", id="btn-endpoints")
                            yield Button("DTOs", classes="api-toggle", id="btn-dtos")
                        yield Input(placeholder="  search…", id="api-search")
                        with ScrollableContainer(id="api-list-scroll"):
                            yield Static("", id="api-list")
                    with ScrollableContainer(id="api-detail-scroll"):
                        yield Static("", id="api-detail")
                yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._populate_file_tree()
        self._update_stats_bar()
        self._render_content()
        self._min_sidebar_width = self._optimal_sidebar_width()
        self.sidebar_width = self._min_sidebar_width
        self.query_one("#sidebar").styles.min_width = self._min_sidebar_width
        self.query_one("#sidebar").add_class("-focused-pane")
        self.query_one("#file-tree", Tree).add_class("-focused-pane")

    def _optimal_sidebar_width(self) -> int:
        max_len = 0
        for file_node in self._analysis.files:
            parts = file_node.path.split("/")
            depth = len(parts)
            name = parts[-1]
            in_deg = self._analysis.stats.in_degree.get(file_node.path, 0)
            label = name + (f" ({in_deg} importers)" if in_deg > 0 else "")
            # Textual Tree: ~4 chars indent per level + connector + label
            line_len = depth * 4 + len(label) + 2
            max_len = max(max_len, line_len)
        return max(24, min(51, max_len + 6))

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
        stats    = self._analysis.stats
        n_files  = len(self._analysis.files)
        n_funcs  = len(stats.functions)
        n_ep     = len(self._analysis.endpoints)
        n_dtos   = len(self._analysis.dtos)
        n_cycles = len(stats.circular_deps)
        cycle_str = (
            f"  [red]! {n_cycles} circular dep{'s' if n_cycles != 1 else ''}[/]"
            if n_cycles else "  [green]no circular deps[/]"
        )
        ep_str = f"   [bold]{n_ep}[/] endpoints  [bold]{n_dtos}[/] DTOs" if (n_ep or n_dtos) else ""
        text = (
            f"  [bold]{n_files}[/] files"
            f"   [bold]{n_funcs}[/] functions"
            f"{ep_str}"
            f"{cycle_str}"
            f"   [dim][ / ] resize   [f] switch pane[/]"
        )
        self.query_one("#stats-bar", Static).update(text)

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _set_active_tab(self, tab: str) -> None:
        self.current_tab = tab
        for btn_id in ("tab-deps-btn", "tab-calls-btn", "tab-graph-btn", "tab-funcs-btn", "tab-api-btn"):
            self.query_one(f"#{btn_id}", Button).remove_class("-active")
        self.query_one(f"#tab-{tab}-btn", Button).add_class("-active")
        self._render_content()
        # Tabs 4 & 5 have their own navigation — auto-focus their content pane
        # so arrow keys go to the list, not the file tree.
        if tab in ("funcs", "api"):
            self._focus_on_content = True
            self.query_one("#sidebar").remove_class("-focused-pane")
            self.query_one("#file-tree", Tree).remove_class("-focused-pane")
            self.query_one("#fn-panel").set_class(tab == "funcs", "-focused-pane")
            self.query_one("#api-panel").set_class(tab == "api", "-focused-pane")
            self.query_one("#content-area").remove_class("-focused-pane")

    @on(Button.Pressed, "#tab-deps-btn")
    def _tab_deps(self) -> None:
        self._set_active_tab("deps")

    @on(Button.Pressed, "#tab-calls-btn")
    def _tab_calls(self) -> None:
        self._set_active_tab("calls")

    @on(Button.Pressed, "#tab-graph-btn")
    def _tab_graph(self) -> None:
        self._set_active_tab("graph")

    @on(Button.Pressed, "#tab-api-btn")
    def _tab_api_btn(self) -> None:
        self._set_active_tab("api")

    @on(Button.Pressed, "#btn-endpoints")
    def _api_show_endpoints(self) -> None:
        self._api_view = "endpoints"
        self._api_selected = 0
        self._api_search = ""
        try:
            self.query_one("#api-search", Input).value = ""
        except Exception:
            pass
        self._update_api_toggle()
        self._render_api_list()
        self._render_api_detail()

    @on(Button.Pressed, "#btn-dtos")
    def _api_show_dtos(self) -> None:
        self._api_view = "dtos"
        self._api_selected = 0
        self._api_search = ""
        try:
            self.query_one("#api-search", Input).value = ""
        except Exception:
            pass
        self._update_api_toggle()
        self._render_api_list()
        self._render_api_detail()

    @on(Button.Pressed, "#tab-funcs-btn")
    def _tab_funcs(self) -> None:
        self._reset_fn_panel()
        self._set_active_tab("funcs")

    def action_tab_deps(self) -> None:
        self._set_active_tab("deps")

    def action_tab_calls(self) -> None:
        self._set_active_tab("calls")

    def action_tab_graph(self) -> None:
        self._set_active_tab("graph")

    def action_tab_funcs(self) -> None:
        self._reset_fn_panel()
        self._set_active_tab("funcs")

    def action_tab_api(self) -> None:
        self._set_active_tab("api")

    def action_goto_funcs(self) -> None:
        self._reset_fn_panel()
        self._set_active_tab("funcs")

    def _reset_fn_panel(self) -> None:
        self._fn_selected = 0
        self._fn_search = ""
        try:
            self.query_one("#fn-search", Input).value = ""
        except Exception:
            pass

    # ── Tree selection ────────────────────────────────────────────────────────

    @on(Tree.NodeHighlighted, "#file-tree")
    def _on_file_highlighted(self, event: Tree.NodeHighlighted) -> None:
        # data is set on file leaves; directory nodes have no data → show overview
        self.selected_file = event.node.data or None
        self._fn_selected = 0
        self._api_selected = 0
        self._render_content()

    @on(Input.Changed, "#fn-search")
    def _on_fn_search_changed(self, event: Input.Changed) -> None:
        self._fn_search = event.value
        self._fn_selected = 0
        self._render_fn_list()
        self._render_fn_code()

    @on(Input.Submitted, "#fn-search")
    def _on_fn_search_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#fn-list-scroll").focus()

    @on(Input.Changed, "#api-search")
    def _on_api_search_changed(self, event: Input.Changed) -> None:
        self._api_search = event.value
        self._api_selected = 0
        self._render_api_list()
        self._render_api_detail()

    @on(Input.Submitted, "#api-search")
    def _on_api_search_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#api-list-scroll").focus()

    # ── Content rendering ─────────────────────────────────────────────────────

    def _render_content(self) -> None:
        is_funcs = self.current_tab == "funcs"
        is_api   = self.current_tab == "api"
        content_area = self.query_one("#content-area")
        fn_panel  = self.query_one("#fn-panel")
        api_panel = self.query_one("#api-panel")

        content_area.display = not is_funcs and not is_api
        fn_panel.display  = is_funcs
        api_panel.display = is_api

        focused = content_area.has_class("-focused-pane")
        fn_panel.set_class(is_funcs and focused, "-focused-pane")
        api_panel.set_class(is_api and focused, "-focused-pane")

        if is_funcs:
            self._render_fn_list()
            self._render_fn_code()
            return
        if is_api:
            self._render_api_list()
            self._render_api_detail()
            return
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

    def _get_fn_list(self, search: str = "") -> list[tuple[str, FunctionNode]]:
        fns = sorted(
            self._analysis.stats.functions.items(),
            key=lambda x: (x[1].file_path, x[1].line_start),
        )
        if self.selected_file:
            fns = [(k, v) for k, v in fns if v.file_path == self.selected_file]
        if search:
            q = search.lower()
            fns = [(k, v) for k, v in fns if q in v.name.lower()]
        return fns

    def _render_fn_list(self) -> None:
        fns = self._get_fn_list(self._fn_search)
        t = Text()

        if self.selected_file:
            short = self.selected_file.split("/")[-1]
            t.append(f" {len(fns)} fn  ·  {short}\n", style="bold #a8d8ea")
        else:
            t.append(f" {len(fns)} functions (all files)\n", style="bold #a8d8ea")
        t.append(" " + "─" * 28 + "\n", style="#1e3a5f")

        for i, (_, fn) in enumerate(fns):
            name = fn.name if len(fn.name) <= 24 else fn.name[:21] + "…"
            if i == self._fn_selected:
                t.append(f"▶ {name}\n", style="bold #a8d8ea on #1e3a5f")
            else:
                t.append(f"  {name}\n", style="#e2e8f0")

        if not fns:
            t.append("  (no matches)\n", style="#4a5568")

        self.query_one("#fn-list", Static).update(t)
        scroll = self.query_one("#fn-list-scroll", ScrollableContainer)
        scroll.scroll_to(y=max(0, self._fn_selected - 3), animate=False)

    def _render_fn_code(self) -> None:
        fns = self._get_fn_list(self._fn_search)
        if not fns:
            self.query_one("#fn-code", Static).update(
                Text("  (no functions match)", style="#4a5568")
            )
            return
        idx = min(self._fn_selected, len(fns) - 1)
        _, fn = fns[idx]
        file_node = next((f for f in self._analysis.files if f.path == fn.file_path), None)
        t = Text()
        t.append(f"\n  {fn.file_path}", style="bold cyan")
        t.append(f"  ·  line {fn.line_start}\n\n", style="#4a5568")
        if fn.docstring:
            t.append(f'  """{fn.docstring}"""\n\n', style="#718096")
        if file_node and file_node.content:
            lines = file_node.content.splitlines()
            start = max(0, fn.line_start - 1)
            end = min(len(lines), fn.line_end or fn.line_start)
            t.append("\n".join(lines[start:end]), style="#e2e8f0")
        else:
            t.append("  (source not available)", style="#4a5568")
        self.query_one("#fn-code", Static).update(t)
        self.query_one("#fn-code-scroll", ScrollableContainer).scroll_home(animate=False)

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
        self.sidebar_width = min(self.sidebar_width + 2, 51)

    def action_sidebar_shrink(self) -> None:
        self.sidebar_width = max(self.sidebar_width - 2, self._min_sidebar_width)

    # ── Pane focus switching ──────────────────────────────────────────────────

    def action_focus_next_pane(self) -> None:
        self._focus_on_content = not self._focus_on_content
        if self._focus_on_content:
            area = self.query_one("#content-area", ScrollableContainer)
            area.focus()
            area.add_class("-focused-pane")
            self.query_one("#sidebar").remove_class("-focused-pane")
            self.query_one("#file-tree", Tree).remove_class("-focused-pane")
            self.query_one("#fn-panel").set_class(self.current_tab == "funcs", "-focused-pane")
            self.query_one("#api-panel").set_class(self.current_tab == "api", "-focused-pane")
        else:
            self.query_one("#file-tree", Tree).focus()
            self.query_one("#sidebar").add_class("-focused-pane")
            self.query_one("#file-tree", Tree).add_class("-focused-pane")
            self.query_one("#content-area", ScrollableContainer).remove_class("-focused-pane")
            self.query_one("#fn-panel").remove_class("-focused-pane")
            self.query_one("#api-panel").remove_class("-focused-pane")

    # ── Key handling ──────────────────────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        # Left/right toggle Endpoints↔DTOs in Tab 5 (not when search input is focused)
        if self.current_tab == "api":
            focused_id = getattr(self.focused, "id", None)
            if focused_id != "api-search":
                if event.key == "right":
                    self._api_view = "dtos"
                    self._api_selected = 0
                    self._update_api_toggle()
                    self._render_api_list()
                    self._render_api_detail()
                    event.stop()
                elif event.key == "left":
                    self._api_view = "endpoints"
                    self._api_selected = 0
                    self._update_api_toggle()
                    self._render_api_list()
                    self._render_api_detail()
                    event.stop()

    def action_navigate_down(self) -> None:
        if not self._focus_on_content:
            self.query_one("#file-tree", Tree).action_cursor_down()
            return
        focused_id = getattr(self.focused, "id", None)
        if self.current_tab == "funcs" and focused_id != "fn-search":
            fns = self._get_fn_list(self._fn_search)
            if self._fn_selected < len(fns) - 1:
                self._fn_selected += 1
                self._render_fn_list()
                self._render_fn_code()
        elif self.current_tab == "api" and focused_id != "api-search":
            items = self._get_api_items(self._api_search)
            if self._api_selected < len(items) - 1:
                self._api_selected += 1
                self._render_api_list()
                self._render_api_detail()
        else:
            self.query_one("#content-area", ScrollableContainer).scroll_down()

    def action_navigate_up(self) -> None:
        if not self._focus_on_content:
            self.query_one("#file-tree", Tree).action_cursor_up()
            return
        focused_id = getattr(self.focused, "id", None)
        if self.current_tab == "funcs" and focused_id != "fn-search":
            if self._fn_selected > 0:
                self._fn_selected -= 1
                self._render_fn_list()
                self._render_fn_code()
        elif self.current_tab == "api" and focused_id != "api-search":
            if self._api_selected > 0:
                self._api_selected -= 1
                self._render_api_list()
                self._render_api_detail()
        else:
            self.query_one("#content-area", ScrollableContainer).scroll_up()

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

    # ── API Tab (Tab 5) ───────────────────────────────────────────────────────

    _METHOD_COLORS: dict[str, str] = {
        "GET":    "#68d391",
        "POST":   "#63b3ed",
        "PUT":    "#f6ad55",
        "DELETE": "#fc8181",
        "PATCH":  "#b794f4",
        "WS":     "#fbd38d",
        "MSG":    "#fbd38d",
        "ANY":    "#718096",
    }

    def _update_api_toggle(self) -> None:
        self.query_one("#btn-endpoints", Button).set_class(self._api_view == "endpoints", "-active-toggle")
        self.query_one("#btn-dtos",      Button).set_class(self._api_view == "dtos",      "-active-toggle")

    def _get_api_items(self, search: str = "") -> list:
        if self._api_view == "endpoints":
            items: list = list(self._analysis.endpoints)
            if self.selected_file:
                items = [e for e in items if e.file_path == self.selected_file]
            items = sorted(items, key=lambda e: (e.path, e.method))
            if search:
                q = search.lower()
                items = [e for e in items if q in e.path.lower() or q in e.handler.lower() or q in e.method.lower()]
        else:
            items = list(self._analysis.dtos)
            if self.selected_file:
                items = [d for d in items if d.file_path == self.selected_file]
            items = sorted(items, key=lambda d: d.name.lower())
            if search:
                q = search.lower()
                items = [d for d in items if q in d.name.lower() or q in d.kind.lower()]
        return items

    def _render_api_list(self) -> None:
        items = self._get_api_items(self._api_search)
        t = Text()
        label = "endpoints" if self._api_view == "endpoints" else "DTOs"

        if self.selected_file:
            short = self.selected_file.split("/")[-1]
            t.append(f" {len(items)} {label}", style="bold #a8d8ea")
            t.append(f" · {short}\n", style="#4a5568")
        else:
            t.append(f" {len(items)} {label}\n", style="bold #a8d8ea")
        t.append(" " + "─" * 38 + "\n", style="#1e3a5f")
        t.append("  ← → switch view\n", style="#2d4a6b")

        for i, item in enumerate(items):
            sel = i == self._api_selected
            if self._api_view == "endpoints":
                color = self._METHOD_COLORS.get(item.method, "#718096")
                method = f"{item.method:<7}"
                path = item.path if len(item.path) <= 26 else item.path[:23] + "…"
                if sel:
                    t.append(f"▶ {method} {path}\n", style=f"bold {color} on #1e3a5f")
                else:
                    t.append("  ", style="#e2e8f0")
                    t.append(method, style=color)
                    t.append(f" {path}\n", style="#e2e8f0")
            else:
                name = item.name if len(item.name) <= 26 else item.name[:23] + "…"
                badge = f"({len(item.fields)})"
                if sel:
                    t.append(f"▶ {name} {badge}\n", style="bold #a8d8ea on #1e3a5f")
                else:
                    t.append(f"  {name} ", style="#e2e8f0")
                    t.append(f"{badge}\n", style="#4a5568")

        if not items:
            if self.selected_file:
                label_none = "endpoints" if self._api_view == "endpoints" else "DTOs"
                t.append(f"\n  No {label_none} in this file.\n", style="#4a5568")
            else:
                t.append(f"\n  Select a file to view its {label}.\n", style="#4a5568")

        self.query_one("#api-list", Static).update(t)
        self.query_one("#api-list-scroll", ScrollableContainer).scroll_to(
            y=max(0, self._api_selected - 3), animate=False
        )

    def _render_api_detail(self) -> None:
        items = self._get_api_items(self._api_search)
        t = Text()

        if not items:
            if self.selected_file:
                label_none = "API endpoints" if self._api_view == "endpoints" else "DTOs"
                short = self.selected_file.split("/")[-1]
                t.append(f"\n  No {label_none} found in {short}.\n", style="#4a5568")
            else:
                if self._api_view == "endpoints":
                    t.append("\n  Select a file to view its API endpoints.\n\n", style="#4a5568")
                    t.append("  RepoLens detects routes from:\n", style="#718096")
                    for line in [
                        "  Python  — FastAPI @app.get(), Flask @app.route()",
                        "  Node.js — Express router.get(), NestJS @Get()",
                        "  Go      — Gin r.GET(), Echo e.GET(), Chi r.Get()",
                        "  Rust    — actix-web #[get()], axum .route()",
                    ]:
                        t.append(f"{line}\n", style="#4a5568")
                else:
                    t.append("\n  Select a file to view its DTOs.\n\n", style="#4a5568")
                    t.append("  RepoLens detects DTOs from:\n", style="#718096")
                    for line in [
                        "  Python  — Pydantic BaseModel, @dataclass, TypedDict",
                        "  Node.js — TypeScript interface, type aliases",
                        "  Go      — structs with json:\"\" tags",
                        "  Rust    — #[derive(Serialize, Deserialize)] structs",
                    ]:
                        t.append(f"{line}\n", style="#4a5568")
            self.query_one("#api-detail", Static).update(t)
            return

        idx = min(self._api_selected, len(items) - 1)
        item = items[idx]

        if self._api_view == "endpoints":
            color = self._METHOD_COLORS.get(item.method, "#718096")
            t.append(f"\n  ", style="#e2e8f0")
            t.append(f"{item.method}", style=f"bold {color}")
            t.append(f"  {item.path}\n", style="bold #e2e8f0")
            t.append(f"  handler:   ", style="#4a5568")
            t.append(f"{item.handler}\n", style="bold #a8d8ea")
            t.append(f"  framework: ", style="#4a5568")
            t.append(f"{item.framework}\n", style="#90cdf4")
            t.append(f"  file:      ", style="#4a5568")
            t.append(f"{item.file_path}", style="#90cdf4")
            t.append(f"  ·  line {item.line}\n", style="#4a5568")

            file_node = next((f for f in self._analysis.files if f.path == item.file_path), None)
            if file_node and file_node.content:
                t.append(f"\n  {'─' * 58}\n", style="#2d3748")
                t.append("  HANDLER SOURCE\n\n", style="bold #a8d8ea")
                lines = file_node.content.splitlines()
                start = max(0, item.line - 1)
                for line in lines[start : start + 25]:
                    t.append(f"  {line}\n", style="#e2e8f0")
        else:
            kind_label = {
                "pydantic":   "Pydantic BaseModel",
                "dataclass":  "Python Dataclass",
                "typeddict":  "TypedDict",
                "interface":  "TypeScript Interface",
                "type":       "TypeScript Type",
                "struct":     "Go / Rust Struct",
            }.get(item.kind, item.kind.title())

            t.append(f"\n  {item.name}\n", style="bold #e2e8f0")
            t.append(f"  {kind_label}", style="#90cdf4")
            t.append(f"  ·  line {item.line}\n", style="#4a5568")
            t.append(f"  {item.file_path}\n", style="#4a5568")
            t.append(f"\n  {'─' * 58}\n", style="#2d3748")
            t.append(f"  FIELDS  ({len(item.fields)})\n\n", style="bold #a8d8ea")

            if item.fields:
                for fi, f in enumerate(item.fields):
                    conn = "└── " if fi == len(item.fields) - 1 else "├── "
                    t.append(f"  {conn}", style="#4a5568")
                    t.append(f"{f.name}", style="#e2e8f0")
                    if f.type_hint:
                        t.append(": ", style="#4a5568")
                        t.append(f"{f.type_hint}\n", style="#90cdf4")
                    else:
                        t.append("\n")
            else:
                t.append("  └── (no typed fields detected)\n", style="#4a5568")

        self.query_one("#api-detail", Static).update(t)
        self.query_one("#api-detail-scroll", ScrollableContainer).scroll_home(animate=False)

    def action_refresh_view(self) -> None:
        self._render_content()
