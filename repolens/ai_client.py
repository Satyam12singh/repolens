from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from .models import RepoAnalysis


_PROVIDER_DEFAULTS: dict[str, dict] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "key_env": "OPENAI_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash",
        "key_env": "GEMINI_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_env": "GROQ_API_KEY",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2",
        "key_env": None,  # no key needed
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-4-6",
        "key_env": "ANTHROPIC_API_KEY",
    },
}

_client: Optional[OpenAI] = None
_model: str = ""


def is_configured() -> bool:
    for p, cfg in _PROVIDER_DEFAULTS.items():
        key_env = cfg.get("key_env")
        if key_env and os.environ.get(key_env):
            return True
    if os.environ.get("REPOLENS_AI_PROVIDER") == "ollama":
        return True
    if os.environ.get("REPOLENS_AI_BASE_URL"):
        return True
    if os.environ.get("REPOLENS_AI_API_KEY"):
        return True
    return False


def _get_client() -> tuple[OpenAI, str]:
    global _client, _model
    if _client is not None:
        return _client, _model

    provider = os.environ.get("REPOLENS_AI_PROVIDER", "").lower()
    if not provider:
        # auto-detect from available keys
        for p, cfg in _PROVIDER_DEFAULTS.items():
            key_env = cfg.get("key_env")
            if key_env and os.environ.get(key_env):
                provider = p
                break
        if not provider:
            if os.environ.get("REPOLENS_AI_API_KEY") and os.environ.get("REPOLENS_AI_BASE_URL"):
                provider = "custom"
            elif os.environ.get("REPOLENS_AI_BASE_URL"):
                provider = "ollama"  # no-auth local provider
            else:
                raise RuntimeError(
                    "No AI provider configured.\n"
                    "Set REPOLENS_AI_PROVIDER and a matching API key, e.g.:\n"
                    "  REPOLENS_AI_PROVIDER=gemini  GEMINI_API_KEY=...\n"
                    "  REPOLENS_AI_PROVIDER=groq    GROQ_API_KEY=...\n"
                    "  REPOLENS_AI_PROVIDER=ollama  (no key needed)\n"
                    "  REPOLENS_AI_PROVIDER=openai  OPENAI_API_KEY=...\n"
                    "See .env.example for full reference."
                )

    cfg = _PROVIDER_DEFAULTS.get(provider, {})
    base_url = os.environ.get("REPOLENS_AI_BASE_URL") or cfg.get("base_url", "")
    model = os.environ.get("REPOLENS_AI_MODEL") or cfg.get("model", "gpt-4o")

    # Resolve API key
    api_key = os.environ.get("REPOLENS_AI_API_KEY")
    if not api_key:
        key_env = cfg.get("key_env")
        if key_env:
            api_key = os.environ.get(key_env)
    if not api_key:
        api_key = "ollama"  # openai SDK requires a non-empty string; local providers ignore it

    _client = OpenAI(api_key=api_key, base_url=base_url or None)
    _model = model
    return _client, _model


def _build_repo_context(analysis: RepoAnalysis) -> str:
    lines: list[str] = []
    lines.append(f"# Repository: {analysis.root}")
    lines.append(f"Files analysed: {len(analysis.file_analyses)}")
    lines.append("")

    lines.append("## File Tree")
    for f in analysis.files[:100]:
        in_deg = analysis.stats.in_degree.get(f.path, 0)
        badge = f" [{in_deg}←]" if in_deg > 0 else ""
        lines.append(f"  {f.path} ({f.language}){badge}")
    if len(analysis.files) > 100:
        lines.append(f"  … and {len(analysis.files) - 100} more")
    lines.append("")

    lines.append("## Import Graph (file → local deps)")
    for path, deps in list(analysis.stats.import_edges.items())[:50]:
        if deps:
            lines.append(f"  {path} → {', '.join(deps)}")
    lines.append("")

    if analysis.stats.circular_deps:
        lines.append("## ⚠ Circular Dependencies")
        for cycle in analysis.stats.circular_deps:
            lines.append("  " + " → ".join(cycle) + " → " + cycle[0])
        lines.append("")

    lines.append("## Entry Points")
    for ep in analysis.stats.entry_points[:20]:
        lines.append(f"  {ep}")
    lines.append("")

    lines.append("## Most-Imported Files")
    for path, count in analysis.stats.hub_files[:10]:
        if count > 0:
            lines.append(f"  {path} ({count} importers)")
    lines.append("")

    lines.append("## Functions per File (sample)")
    items = sorted(
        analysis.file_analyses.items(),
        key=lambda x: len(x[1].functions),
        reverse=True,
    )[:20]
    for path, fa in items:
        if fa.functions:
            names = ", ".join(f.name for f in fa.functions[:10])
            lines.append(f"  {path}: {names}")

    return "\n".join(lines)


_SYSTEM_PROMPT = (
    "You are RepoLens, an AI assistant that helps developers understand codebases. "
    "You have a structured summary of a code repository: file tree, import dependency "
    "graph, circular dependency alerts, entry points, and function listings. "
    "Answer concisely, reference actual file names, and trace call chains step by step "
    "when asked. If unsure, say so."
)


def ask(
    analysis: RepoAnalysis,
    question: str,
    history: list[dict] | None = None,
) -> str:
    """Send *question* to the model, including prior *history* for multi-turn chat.

    history: list of {"role": "user"|"assistant", "content": str} pairs
             from previous turns (oldest first, excluding repo context).
    """
    client, model = _get_client()
    context = _build_repo_context(analysis)

    # First user turn carries the repo context; subsequent turns are plain text.
    if history:
        first_user = history[0]["content"]
        if not first_user.startswith("<repo_context>"):
            history[0] = {
                "role": "user",
                "content": f"<repo_context>\n{context}\n</repo_context>\n\n{first_user}",
            }
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}] + history + [
            {"role": "user", "content": question}
        ]
    else:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"<repo_context>\n{context}\n</repo_context>\n\nQuestion: {question}",
            },
        ]

    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=messages,
    )
    return response.choices[0].message.content or ""


def generate_onboarding(analysis: RepoAnalysis) -> str:
    client, model = _get_client()
    context = _build_repo_context(analysis)
    response = client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"<repo_context>\n{context}\n</repo_context>\n\n"
                    "Generate a new developer onboarding guide. Include:\n"
                    "1. What this codebase does (1-2 sentences)\n"
                    "2. Key abstractions to understand first\n"
                    "3. Entry points — where to start reading\n"
                    "4. Most important files and what each does\n"
                    "5. Architectural patterns worth knowing\n"
                    "6. Circular dependencies or tech debt to be aware of\n\n"
                    "Be specific; reference actual file names."
                ),
            },
        ],
    )
    return response.choices[0].message.content or ""
