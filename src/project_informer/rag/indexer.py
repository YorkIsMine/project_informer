"""RAG indexer: discovers docs, chunks them, and stores in ChromaDB."""

import hashlib
import re
from pathlib import Path

import chromadb

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", ".tox", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".chromadb",
}

DOC_PATTERNS = ["*.md", "*.rst", "*.txt"]
SCHEMA_PATTERNS = ["*.schema.json", "*.graphql", "*.proto", "openapi.yaml", "openapi.json"]

COLLECTION_NAME = "project_docs"


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part in SKIP_DIRS for part in rel.parts)


def discover_files(project_path: Path) -> list[Path]:
    """Find all indexable documentation files."""
    files = []
    all_patterns = DOC_PATTERNS + SCHEMA_PATTERNS
    for pattern in all_patterns:
        for f in project_path.rglob(pattern):
            if f.is_file() and not should_skip(f, project_path):
                files.append(f)
    return sorted(set(files))


def chunk_markdown(content: str, source: str) -> list[dict]:
    """Split markdown into heading-based chunks."""
    chunks = []
    # Split on ## headings (keep the heading with its content)
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)

    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue

        # Extract heading if present
        heading_match = re.match(r"^##\s+(.+)$", section, re.MULTILINE)
        heading = heading_match.group(1) if heading_match else f"Section {i}"

        # If section is too long, sub-split on paragraphs
        if len(section) > 1500:
            paragraphs = section.split("\n\n")
            para_chunk = ""
            chunk_idx = 0
            for para in paragraphs:
                if len(para_chunk) + len(para) > 1000 and para_chunk:
                    chunks.append(_make_chunk(para_chunk, source, heading, chunk_idx))
                    chunk_idx += 1
                    para_chunk = para
                else:
                    para_chunk = para_chunk + "\n\n" + para if para_chunk else para
            if para_chunk.strip():
                chunks.append(_make_chunk(para_chunk, source, heading, chunk_idx))
        else:
            chunks.append(_make_chunk(section, source, heading, 0))

    if not chunks and content.strip():
        chunks.append(_make_chunk(content.strip(), source, "Document", 0))

    return chunks


def chunk_text(content: str, source: str, window: int = 800, overlap: int = 100) -> list[dict]:
    """Split plain text into overlapping windows."""
    chunks = []
    start = 0
    idx = 0
    while start < len(content):
        end = start + window
        text = content[start:end]
        if text.strip():
            chunks.append(_make_chunk(text.strip(), source, f"Chunk {idx}", idx))
        start = end - overlap
        idx += 1
    return chunks


def _make_chunk(text: str, source: str, heading: str, idx: int) -> dict:
    chunk_id = hashlib.md5(f"{source}:{heading}:{idx}".encode()).hexdigest()
    return {
        "id": chunk_id,
        "document": text,
        "metadata": {
            "source": source,
            "heading": heading,
            "chunk_index": idx,
        },
    }


def index_project(project_path: str, db_path: str | None = None) -> int:
    """Index all documentation in the project into ChromaDB.

    Returns the number of chunks indexed.
    """
    root = Path(project_path).resolve()
    if db_path is None:
        db_path = str(root / ".chromadb")

    files = discover_files(root)
    if not files:
        return 0

    all_chunks = []
    for filepath in files:
        content = filepath.read_text(errors="replace")
        rel_path = str(filepath.relative_to(root))

        if filepath.suffix in (".md", ".rst"):
            all_chunks.extend(chunk_markdown(content, rel_path))
        else:
            all_chunks.extend(chunk_text(content, rel_path))

    if not all_chunks:
        return 0

    client = chromadb.PersistentClient(path=db_path)

    # Recreate collection for fresh index
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(COLLECTION_NAME)

    # ChromaDB batch limit is 5461, insert in batches
    batch_size = 5000
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        collection.add(
            ids=[c["id"] for c in batch],
            documents=[c["document"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
        )

    return len(all_chunks)
