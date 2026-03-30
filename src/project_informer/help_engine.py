"""Help engine: combines RAG documentation search with live git context."""

import subprocess
from pathlib import Path


def answer_question(question: str, project_path: str) -> str:
    """Answer a project question using RAG docs + git context.

    Assembles relevant documentation chunks and git state into a
    structured response. No LLM API key required.
    """
    root = Path(project_path).resolve()
    parts = []

    # 1. Query RAG for relevant documentation
    doc_section = _get_doc_context(question, str(root))
    if doc_section:
        parts.append(doc_section)

    # 2. Gather git context
    git_section = _get_git_context(str(root), question)
    if git_section:
        parts.append(git_section)

    if not parts:
        return (
            "No documentation or git context found.\n"
            "Try running:\n"
            "  project-informer generate-docs  -- to auto-generate docs\n"
            "  project-informer index          -- to index documentation\n"
        )

    return "\n\n".join(parts)


def _get_doc_context(question: str, project_path: str) -> str | None:
    """Query RAG and format documentation results."""
    try:
        from project_informer.rag.query import query_docs
        results = query_docs(question, project_path, n_results=5)
    except (RuntimeError, Exception):
        return None

    if not results:
        return None

    lines = ["== Relevant Documentation ==", ""]
    for r in results:
        lines.append(f"[Source: {r['source']}, Section: {r['heading']}]")
        lines.append(r["document"])
        lines.append("")

    return "\n".join(lines)


def _get_git_context(project_path: str, question: str) -> str | None:
    """Gather git context relevant to the question."""
    lines = ["== Project Context ==", ""]

    # Always show branch
    branch = _run_git(project_path, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        lines.append(f"Branch: {branch}")

    # Show structure for structure-related questions
    q_lower = question.lower()
    structure_keywords = {"structure", "files", "folder", "directory", "tree", "layout", "организаци", "структур"}
    if any(kw in q_lower for kw in structure_keywords):
        from project_informer.mcp_server.server import get_project_structure
        tree = get_project_structure(project_path, max_depth=3)
        lines.append("")
        lines.append("Project structure:")
        lines.append(tree)

    # Show diff for change-related questions
    change_keywords = {"change", "diff", "modif", "commit", "изменен"}
    if any(kw in q_lower for kw in change_keywords):
        diff = _run_git(project_path, "diff", "--stat")
        if diff:
            lines.append("")
            lines.append("Uncommitted changes:")
            lines.append(diff)
        else:
            lines.append("")
            lines.append("No uncommitted changes.")

    # Show recent commits for history questions
    history_keywords = {"history", "log", "recent", "last", "commit", "истори"}
    if any(kw in q_lower for kw in history_keywords):
        log = _run_git(project_path, "log", "--oneline", "-10")
        if log:
            lines.append("")
            lines.append("Recent commits:")
            lines.append(log)

    if len(lines) <= 2:
        return None

    return "\n".join(lines)


def _run_git(project_path: str, *args: str) -> str | None:
    """Run a git command and return stdout, or None on failure."""
    result = subprocess.run(
        ["git", "-C", project_path, *args],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()
