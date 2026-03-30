"""Auto-generate project documentation by analyzing code structure.

When a project has no documentation, this module scans the codebase,
analyzes its structure, and generates markdown docs in a special folder.
"""

import os
import ast
import re
from pathlib import Path

GENERATED_DOCS_DIR = "docs/_generated"

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", ".env", ".tox", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".egg-info", ".chromadb",
}

CODE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def discover_code_files(project_path: Path) -> list[Path]:
    """Find all code files in the project."""
    files = []
    for ext in CODE_EXTENSIONS:
        for f in project_path.rglob(f"*{ext}"):
            if not should_skip(f.relative_to(project_path)):
                files.append(f)
    return sorted(files)


def analyze_python_file(filepath: Path) -> dict:
    """Extract structure from a Python file using AST."""
    content = filepath.read_text(errors="replace")
    info = {
        "path": str(filepath),
        "docstring": None,
        "classes": [],
        "functions": [],
        "imports": [],
    }

    try:
        tree = ast.parse(content)
    except SyntaxError:
        info["error"] = "Could not parse (syntax error)"
        return info

    info["docstring"] = ast.get_docstring(tree)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append({
                        "name": item.name,
                        "docstring": ast.get_docstring(item),
                        "args": [a.arg for a in item.args.args if a.arg != "self"],
                    })
            info["classes"].append({
                "name": node.name,
                "docstring": ast.get_docstring(node),
                "methods": methods,
                "bases": [_name(b) for b in node.bases],
            })

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info["functions"].append({
                "name": node.name,
                "docstring": ast.get_docstring(node),
                "args": [a.arg for a in node.args.args],
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            })

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    info["imports"].append(alias.name)
            else:
                module = node.module or ""
                for alias in node.names:
                    info["imports"].append(f"{module}.{alias.name}")

    return info


def analyze_generic_file(filepath: Path) -> dict:
    """Basic analysis for non-Python files: extract function/class patterns."""
    content = filepath.read_text(errors="replace")
    ext = filepath.suffix
    lang = CODE_EXTENSIONS.get(ext, "unknown")

    info = {
        "path": str(filepath),
        "language": lang,
        "lines": content.count("\n") + 1,
        "functions": [],
        "classes": [],
    }

    # Extract function-like patterns
    func_patterns = {
        "javascript": r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        "typescript": r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        "go": r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)",
        "rust": r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)",
        "java": r"(?:public|private|protected)?\s+\w+\s+(\w+)\s*\(",
        "ruby": r"def\s+(\w+)",
    }

    class_patterns = {
        "javascript": r"class\s+(\w+)",
        "typescript": r"(?:export\s+)?class\s+(\w+)",
        "java": r"class\s+(\w+)",
        "rust": r"(?:pub\s+)?struct\s+(\w+)",
        "go": r"type\s+(\w+)\s+struct",
    }

    if lang in func_patterns:
        info["functions"] = re.findall(func_patterns[lang], content)
    if lang in class_patterns:
        info["classes"] = re.findall(class_patterns[lang], content)

    return info


def analyze_project(project_path: Path) -> dict:
    """Analyze entire project structure and code."""
    code_files = discover_code_files(project_path)

    analysis = {
        "project_path": str(project_path),
        "project_name": project_path.name,
        "files": [],
        "tree": build_tree(project_path),
        "config_files": [],
        "total_files": len(code_files),
    }

    # Detect config/metadata files
    config_names = [
        "pyproject.toml", "setup.py", "setup.cfg", "package.json",
        "Cargo.toml", "go.mod", "Gemfile", "Makefile", "Dockerfile",
        "docker-compose.yml", "docker-compose.yaml",
        ".env.example", "requirements.txt",
    ]
    for name in config_names:
        p = project_path / name
        if p.exists():
            analysis["config_files"].append(name)

    for filepath in code_files:
        if filepath.suffix == ".py":
            analysis["files"].append(analyze_python_file(filepath))
        else:
            analysis["files"].append(analyze_generic_file(filepath))

    return analysis


def build_tree(project_path: Path, max_depth: int = 4) -> str:
    """Build a directory tree string."""
    lines = [project_path.name + "/"]

    def _walk(path: Path, prefix: str, depth: int):
        if depth >= max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return

        entries = [e for e in entries if not should_skip(e.relative_to(project_path))
                   and not e.name.startswith(".")]
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                extension = "    " if is_last else "│   "
                _walk(entry, prefix + extension, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

    _walk(project_path, "", 0)
    return "\n".join(lines)


def _name(node) -> str:
    """Get name from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name(node.value)}.{node.attr}"
    return "?"


def generate_docs(project_path: str) -> list[str]:
    """Analyze project and generate documentation files.

    Returns list of generated file paths.
    """
    root = Path(project_path).resolve()
    analysis = analyze_project(root)
    out_dir = root / GENERATED_DOCS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    # 1. Project overview
    overview = _generate_overview(analysis)
    p = out_dir / "overview.md"
    p.write_text(overview)
    generated.append(str(p))

    # 2. Architecture / structure
    arch = _generate_architecture(analysis)
    p = out_dir / "architecture.md"
    p.write_text(arch)
    generated.append(str(p))

    # 3. Per-module API docs (for Python projects)
    python_files = [f for f in analysis["files"] if f["path"].endswith(".py")]
    if python_files:
        api = _generate_api_reference(python_files, root)
        p = out_dir / "api_reference.md"
        p.write_text(api)
        generated.append(str(p))

    return generated


def _generate_overview(analysis: dict) -> str:
    """Generate project overview document."""
    lines = [
        f"# {analysis['project_name']} — Project Overview",
        "",
        "*Auto-generated documentation based on code analysis.*",
        "",
        "## Project Structure",
        "",
        "```",
        analysis["tree"],
        "```",
        "",
    ]

    if analysis["config_files"]:
        lines.append("## Configuration Files")
        lines.append("")
        for cf in analysis["config_files"]:
            lines.append(f"- `{cf}`")
        lines.append("")

    lines.append(f"## Statistics")
    lines.append("")
    lines.append(f"- **Total code files**: {analysis['total_files']}")

    # Count by language
    lang_count: dict[str, int] = {}
    for f in analysis["files"]:
        lang = f.get("language") or "python"
        lang_count[lang] = lang_count.get(lang, 0) + 1
    for lang, count in sorted(lang_count.items()):
        lines.append(f"- **{lang}**: {count} files")

    lines.append("")
    return "\n".join(lines)


def _generate_architecture(analysis: dict) -> str:
    """Generate architecture document based on directory and module analysis."""
    lines = [
        f"# {analysis['project_name']} — Architecture",
        "",
        "*Auto-generated from code structure analysis.*",
        "",
    ]

    # Group files by top-level directory
    groups: dict[str, list[dict]] = {}
    root = Path(analysis["project_path"])
    for f in analysis["files"]:
        rel = Path(f["path"]).relative_to(root)
        parts = rel.parts
        group = parts[0] if len(parts) > 1 else "(root)"
        groups.setdefault(group, []).append(f)

    for group_name, files in sorted(groups.items()):
        lines.append(f"## `{group_name}/`")
        lines.append("")

        for f in files:
            rel = Path(f["path"]).relative_to(root)
            lines.append(f"### `{rel}`")
            lines.append("")

            if f.get("docstring"):
                lines.append(f"> {f['docstring']}")
                lines.append("")

            if f.get("classes"):
                if isinstance(f["classes"][0], dict):
                    # Python detailed analysis
                    for cls in f["classes"]:
                        bases = f" ({', '.join(cls['bases'])})" if cls.get("bases") else ""
                        lines.append(f"**class `{cls['name']}`**{bases}")
                        if cls.get("docstring"):
                            lines.append(f": {cls['docstring']}")
                        lines.append("")
                        if cls.get("methods"):
                            for m in cls["methods"]:
                                args = ", ".join(m["args"])
                                doc = f" — {m['docstring']}" if m.get("docstring") else ""
                                lines.append(f"  - `{m['name']}({args})`{doc}")
                            lines.append("")
                else:
                    # Generic: list of names
                    lines.append("**Classes**: " + ", ".join(f"`{c}`" for c in f["classes"]))
                    lines.append("")

            if f.get("functions"):
                if isinstance(f["functions"][0], dict):
                    for fn in f["functions"]:
                        args = ", ".join(fn["args"])
                        prefix = "async " if fn.get("is_async") else ""
                        doc = f" — {fn['docstring']}" if fn.get("docstring") else ""
                        lines.append(f"- `{prefix}{fn['name']}({args})`{doc}")
                else:
                    lines.append("**Functions**: " + ", ".join(f"`{f_name}`" for f_name in f["functions"]))
                lines.append("")

            if f.get("imports"):
                ext_imports = [i for i in f["imports"] if not i.startswith(".")]
                if ext_imports:
                    lines.append("**Key imports**: " + ", ".join(f"`{i}`" for i in ext_imports[:10]))
                    lines.append("")

    return "\n".join(lines)


def _generate_api_reference(python_files: list[dict], root: Path) -> str:
    """Generate API reference for Python modules."""
    lines = [
        "# API Reference",
        "",
        "*Auto-generated from Python source code.*",
        "",
    ]

    for f in python_files:
        rel = Path(f["path"]).relative_to(root)
        module_path = str(rel).replace("/", ".").replace(".py", "")

        if not f.get("classes") and not f.get("functions"):
            continue

        lines.append(f"## `{module_path}`")
        lines.append("")

        if f.get("docstring"):
            lines.append(f"{f['docstring']}")
            lines.append("")

        for cls in f.get("classes", []):
            bases = f"({', '.join(cls['bases'])})" if cls.get("bases") else ""
            lines.append(f"### class `{cls['name']}{bases}`")
            lines.append("")
            if cls.get("docstring"):
                lines.append(cls["docstring"])
                lines.append("")
            for m in cls.get("methods", []):
                args = ", ".join(m["args"])
                lines.append(f"#### `{cls['name']}.{m['name']}({args})`")
                lines.append("")
                if m.get("docstring"):
                    lines.append(m["docstring"])
                    lines.append("")

        for fn in f.get("functions", []):
            args = ", ".join(fn["args"])
            prefix = "async " if fn.get("is_async") else ""
            lines.append(f"### `{prefix}{fn['name']}({args})`")
            lines.append("")
            if fn.get("docstring"):
                lines.append(fn["docstring"])
                lines.append("")

    return "\n".join(lines)
