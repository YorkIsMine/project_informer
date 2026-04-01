"""PR Reviewer: AI-powered code review using RAG + LLM."""

import re
import sys
from pathlib import Path

from project_informer.llm import ask_llm, detect_provider
from project_informer.rag.indexer import index_project
from project_informer.rag.query import query_docs

REVIEW_SYSTEM_PROMPT = (
    "You are an expert code reviewer. Analyze the pull request diff using "
    "the project documentation and codebase context provided.\n\n"
    "Structure your review EXACTLY as follows:\n\n"
    "## Potential Bugs\n"
    "List any bugs, logic errors, off-by-one mistakes, missing error handling, "
    "race conditions, or security issues. If none found, say 'No issues found.'\n\n"
    "## Architecture Issues\n"
    "List any violations of project conventions, poor abstractions, coupling problems, "
    "or design concerns. Reference project docs when relevant. If none found, say 'No issues found.'\n\n"
    "## Recommendations\n"
    "Suggest concrete improvements: better naming, simpler approaches, missing tests, "
    "performance improvements, etc.\n\n"
    "Be specific — reference file names, line numbers from the diff, and function names. "
    "Be concise. Skip praise — focus on actionable feedback. "
    "Answer in the same language as the code comments or commit messages."
)

MAX_DIFF_CHARS = 6000
MAX_RAG_CHARS = 3000
MAX_FILES_CHARS = 3000


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n... (truncated)"


def _extract_query_terms(diff: str, changed_files: list[str]) -> list[str]:
    """Extract meaningful search terms from the diff for RAG queries."""
    terms = []

    # Use file paths as query context
    for f in changed_files:
        stem = Path(f).stem
        if stem not in ("__init__", "test", "conftest"):
            terms.append(stem.replace("_", " "))

    # Extract function/class names from diff additions
    for match in re.finditer(r"^\+.*(?:def|class|function|func)\s+(\w+)", diff, re.MULTILINE):
        terms.append(match.group(1))

    return terms[:5]  # Limit to 5 queries


def _get_rag_context(diff: str, changed_files: list[str], project_path: str) -> str:
    """Query RAG for documentation relevant to the changed code."""
    try:
        index_project(project_path)
    except Exception:
        pass  # Index may already exist or docs may be missing

    terms = _extract_query_terms(diff, changed_files)
    if not terms:
        terms = ["project architecture overview"]

    seen_docs = set()
    chunks = []

    for term in terms:
        try:
            results = query_docs(term, project_path, n_results=3)
        except (RuntimeError, Exception):
            continue
        for r in results:
            doc_key = (r["source"], r["heading"])
            if doc_key not in seen_docs:
                seen_docs.add(doc_key)
                chunks.append(f"[{r['source']} — {r['heading']}]\n{r['document']}")

    if not chunks:
        return ""

    return _truncate("\n\n".join(chunks), MAX_RAG_CHARS)


def _read_changed_files(changed_files: list[str], project_path: str) -> str:
    """Read the full content of changed files for additional context."""
    root = Path(project_path).resolve()
    parts = []
    total = 0

    for filepath in changed_files:
        full_path = root / filepath
        if not full_path.is_file():
            continue
        # Skip binary / large files
        if full_path.suffix in (".png", ".jpg", ".gif", ".ico", ".woff", ".woff2", ".lock"):
            continue
        try:
            content = full_path.read_text(errors="replace")
        except Exception:
            continue
        if len(content) > 5000:
            content = content[:5000] + "\n... (file truncated)"
        entry = f"=== {filepath} ===\n{content}"
        if total + len(entry) > MAX_FILES_CHARS:
            break
        parts.append(entry)
        total += len(entry)

    return "\n\n".join(parts)


def review_pr(
    diff: str,
    changed_files: list[str],
    project_path: str,
    provider: str = "auto",
) -> str:
    """Perform AI code review on a PR diff.

    Args:
        diff: The unified diff text of the PR.
        changed_files: List of changed file paths (relative to project root).
        project_path: Path to the project root.
        provider: LLM provider ("auto", "openai", "ollama", "none").

    Returns:
        Formatted review text with bugs, architecture issues, and recommendations.
    """
    if provider == "auto":
        provider = detect_provider()

    if provider == "none":
        return (
            "## AI Review\n\n"
            "No LLM provider available. Set OPENAI_API_KEY or start Ollama to enable AI reviews."
        )

    # 1. RAG context from project docs
    rag_context = _get_rag_context(diff, changed_files, project_path)

    # 2. Full content of changed files
    file_context = _read_changed_files(changed_files, project_path)

    # 3. Build the user message
    sections = []
    sections.append(f"## PR Diff\n\n```diff\n{_truncate(diff, MAX_DIFF_CHARS)}\n```")

    if rag_context:
        sections.append(f"## Project Documentation Context\n\n{rag_context}")

    if file_context:
        sections.append(f"## Changed Files (full content)\n\n{file_context}")

    user_message = "\n\n---\n\n".join(sections)

    # 4. Call LLM with review-specific system prompt
    from project_informer.llm import SYSTEM_PROMPT as _orig

    import project_informer.llm as llm_module
    original_prompt = llm_module.SYSTEM_PROMPT
    llm_module.SYSTEM_PROMPT = REVIEW_SYSTEM_PROMPT
    try:
        result = ask_llm("Review this pull request.", user_message, provider)
    finally:
        llm_module.SYSTEM_PROMPT = original_prompt

    return result


def main():
    """CLI entrypoint for pr_reviewer (used by GitHub Actions)."""
    import argparse

    parser = argparse.ArgumentParser(description="AI PR Reviewer")
    parser.add_argument("--diff-file", help="Path to file containing the PR diff")
    parser.add_argument("--files", help="Comma-separated list of changed file paths")
    parser.add_argument("--project-path", default=".", help="Path to project root")
    parser.add_argument("--provider", default="auto", help="LLM provider")
    args = parser.parse_args()

    # Read diff from file or stdin
    if args.diff_file:
        diff = Path(args.diff_file).read_text()
    else:
        diff = sys.stdin.read()

    if not diff.strip():
        print("No diff provided.")
        sys.exit(1)

    # Parse changed files
    changed_files = []
    if args.files:
        changed_files = [f.strip() for f in args.files.split(",") if f.strip()]

    review = review_pr(diff, changed_files, args.project_path, args.provider)
    print(review)


if __name__ == "__main__":
    main()
