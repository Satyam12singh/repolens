"""GitHub API client — fetches file trees and content without cloning."""
import base64
import re
import time
from typing import Optional

import requests

from .models import FileNode

GITHUB_API = "https://api.github.com"

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
}


def parse_github_url(url: str) -> tuple[str, str, Optional[str]]:
    """Parse GitHub URL into (owner, repo, branch_or_None).

    Handles:
    - https://github.com/owner/repo
    - https://github.com/owner/repo/tree/branch
    - github.com/owner/repo
    - owner/repo
    """
    url = url.strip().rstrip("/")
    # strip protocol
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^github\.com/", "", url)

    parts = url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse GitHub URL: {url!r}. Expected owner/repo format.")

    owner, repo = parts[0], parts[1]
    repo = repo.removesuffix(".git")

    branch = None
    if len(parts) >= 4 and parts[2] == "tree":
        branch = "/".join(parts[3:])

    return owner, repo, branch


def _headers(token: Optional[str]) -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(url: str, token: Optional[str], params: dict | None = None) -> dict:
    resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
        wait = max(0, reset - int(time.time())) + 1
        raise RuntimeError(
            f"GitHub rate limit hit. Resets in {wait}s. Set GITHUB_TOKEN to increase limits."
        )
    if resp.status_code == 404:
        raise ValueError(f"Not found: {url}")
    resp.raise_for_status()
    return resp.json()


def get_repo_info(owner: str, repo: str, token: Optional[str] = None) -> dict:
    return _get(f"{GITHUB_API}/repos/{owner}/{repo}", token)


def get_default_branch(owner: str, repo: str, token: Optional[str] = None) -> str:
    info = get_repo_info(owner, repo, token)
    return info["default_branch"]


def fetch_file_tree(
    owner: str,
    repo: str,
    branch: str,
    token: Optional[str] = None,
    max_files: int = 500,
) -> list[FileNode]:
    """Fetch the full file tree via GitHub Trees API (no cloning)."""
    # Get commit SHA for the branch
    branch_data = _get(f"{GITHUB_API}/repos/{owner}/{repo}/branches/{branch}", token)
    commit_sha = branch_data["commit"]["sha"]

    # Get tree SHA from commit
    commit_data = _get(f"{GITHUB_API}/repos/{owner}/{repo}/git/commits/{commit_sha}", token)
    tree_sha = commit_data["tree"]["sha"]

    # Fetch full recursive tree
    tree_data = _get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{tree_sha}",
        token,
        params={"recursive": "1"},
    )

    if tree_data.get("truncated"):
        print(f"  Warning: repo tree was truncated (>{max_files} items). Showing first {max_files}.")

    nodes = []
    for item in tree_data.get("tree", []):
        if item["type"] != "blob":
            continue
        path = item["path"]
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        language = SUPPORTED_EXTENSIONS.get(ext.lower(), "")
        nodes.append(
            FileNode(
                path=path,
                sha=item["sha"],
                size=item.get("size", 0),
                language=language,
            )
        )
        if len(nodes) >= max_files:
            break

    return nodes


def fetch_file_content(
    owner: str,
    repo: str,
    path: str,
    branch: str,
    token: Optional[str] = None,
) -> Optional[str]:
    """Fetch decoded content of a single file. Returns None if too large or binary."""
    try:
        data = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            token,
            params={"ref": branch},
        )
    except (ValueError, requests.HTTPError):
        return None

    if isinstance(data, list):
        return None  # It's a directory

    if data.get("encoding") != "base64":
        return None

    size = data.get("size", 0)
    if size > 500_000:  # skip files > 500KB
        return None

    raw = data.get("content", "")
    try:
        return base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return None


def fetch_source_files(
    owner: str,
    repo: str,
    branch: str,
    files: list[FileNode],
    token: Optional[str] = None,
    languages: Optional[set[str]] = None,
    max_fetch: int = 200,
) -> None:
    """Fetch content for source files in-place, filtered by language."""
    source_files = [
        f for f in files
        if f.language and f.language not in ("markdown", "json", "yaml", "toml")
        and (languages is None or f.language in languages)
    ][:max_fetch]

    print(f"  Fetching content for {len(source_files)} source files...")
    for i, file_node in enumerate(source_files, 1):
        if i % 20 == 0:
            print(f"    {i}/{len(source_files)}...")
        file_node.content = fetch_file_content(owner, repo, file_node.path, branch, token)
