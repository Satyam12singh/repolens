# RepoLens

Instant clarity on any codebase. Navigate imports, trace functions, and get AI answers — all in one terminal view.

## Install

### Homebrew — macOS & Linux
```bash
brew tap satyam12singh/tap
brew install repolens-cli
```

### uv / pipx / pip — any platform with Python
```bash
uv tool install repolens-cli
pipx install repolens-cli
pip install repolens-cli
```

### Direct binary — no Python required
macOS and Linux:
```bash
curl -fsSL https://raw.githubusercontent.com/Satyam12singh/repolens/master/scripts/install.sh | sh
```

Windows — download the latest `.exe` from [GitHub Releases](https://github.com/Satyam12singh/repolens/releases/latest).

## Usage

```bash
repolens .          # scan current directory
repolens ~/my-repo  # scan any directory
```

## AI Configuration

RepoLens supports multiple AI providers. Set **one** of the following in your environment (or in a `.env` file in the directory you're scanning):

| Provider | Environment Variable | Default Model |
|---|---|---|
| Gemini (Google) | `GEMINI_API_KEY` | `gemini-2.5-flash` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Groq | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| Ollama (local) | `REPOLENS_AI_PROVIDER=ollama` | `llama3.2` |

Override any default with:

```bash
REPOLENS_AI_MODEL=gemini-2.5-pro repolens .
REPOLENS_AI_BASE_URL=http://localhost:11434/v1 repolens .
```

If no key is set, the file tree and dependency graphs still work — only the AI features (Ask AI, Onboard) are disabled.

## Key Bindings

| Key | Action |
|---|---|
| `1` | Dependencies tab |
| `2` | Call graph tab |
| `3` | Full graph tab |
| `a` | Ask AI a question about the codebase |
| `o` | Generate onboarding guide |
| `f` | Toggle focus between file tree and content |
| `[` / `]` | Resize sidebar |
| `j` / `k` | Scroll |
| `q` | Quit |

## Supported Languages

Python, JavaScript, TypeScript, Go, Rust

## License

MIT
