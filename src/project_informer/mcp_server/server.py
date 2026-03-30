"""MCP server exposing git and project tools for AI assistants."""

import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("project-informer")

# Default project path, can be overridden via env var
PROJECT_PATH = os.environ.get("PROJECT_INFORMER_PATH", ".")


@mcp.tool()
def get_current_branch(project_path: str = "") -> str:
    """Get the current git branch name for the project."""
    path = project_path or PROJECT_PATH
    result = subprocess.run(
        ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return f"Error: {result.stderr.strip()}"
    return result.stdout.strip()


@mcp.tool()
def list_files(project_path: str = "", pattern: str = "") -> str:
    """List tracked files in the git repository, optionally filtered by glob pattern."""
    path = project_path or PROJECT_PATH
    cmd = ["git", "-C", path, "ls-files"]
    if pattern:
        cmd.append(pattern)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return f"Error: {result.stderr.strip()}"
    return result.stdout.strip()


@mcp.tool()
def get_diff(project_path: str = "", staged: bool = False) -> str:
    """Get the git diff for the project. Set staged=True for staged changes only."""
    path = project_path or PROJECT_PATH
    cmd = ["git", "-C", path, "diff"]
    if staged:
        cmd.append("--staged")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return f"Error: {result.stderr.strip()}"
    return result.stdout.strip() or "No changes."


@mcp.tool()
def get_project_structure(project_path: str = "", max_depth: int = 3) -> str:
    """Get the directory tree structure of the project."""
    path = project_path or PROJECT_PATH
    root = Path(path).resolve()

    skip = {".git", "__pycache__", "node_modules", ".venv", "venv",
            ".chromadb", "dist", "build", ".egg-info", ".tox"}

    lines = [root.name + "/"]

    def _walk(current: Path, prefix: str, depth: int):
        if depth >= max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return
        entries = [e for e in entries if e.name not in skip and not e.name.startswith(".")]
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            ext = "    " if is_last else "│   "
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                _walk(entry, prefix + ext, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

    _walk(root, "", 0)
    return "\n".join(lines)


@mcp.tool()
def query_project_docs(question: str, project_path: str = "") -> str:
    """Search project documentation using RAG. Returns relevant documentation chunks."""
    path = project_path or PROJECT_PATH
    try:
        from project_informer.rag.query import query_docs
        results = query_docs(question, path)
        if not results:
            return "No relevant documentation found."
        parts = []
        for r in results:
            parts.append(f"[Source: {r['source']}, Section: {r['heading']}]\n{r['document']}")
        return "\n\n---\n\n".join(parts)
    except RuntimeError as e:
        return str(e)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
