# Architecture

## Overview

Project Informer is a developer assistant with three layers:

1. **RAG Layer** — documentation indexing and search
2. **MCP Layer** — git tools for AI assistants
3. **Help Engine** — combines both to answer questions

## RAG Pipeline

The RAG pipeline works in two phases:

**Indexing** (`rag/indexer.py`):
- Discovers `.md`, `.rst`, `.txt`, and schema files
- Chunks markdown by `##` headings (max ~1000 chars per chunk)
- Chunks other files with 800-char overlapping windows
- Stores embeddings in ChromaDB using all-MiniLM-L6-v2

**Querying** (`rag/query.py`):
- Takes a natural language question
- Returns top-N most relevant documentation chunks with source metadata

## MCP Server

The MCP server (`mcp_server/server.py`) exposes tools over stdio:

| Tool | Description |
|------|-------------|
| `get_current_branch` | Returns the active git branch |
| `list_files` | Lists git-tracked files |
| `get_diff` | Shows uncommitted changes |
| `get_project_structure` | Directory tree |
| `query_project_docs` | RAG search via MCP |

## Auto Doc Generation

When a project has no documentation, the doc generator (`doc_generator.py`):
- Scans all code files (Python, JS, TS, Go, Rust, etc.)
- For Python: uses AST to extract classes, functions, docstrings, imports
- For other languages: uses regex patterns
- Generates `overview.md`, `architecture.md`, `api_reference.md` in `docs/_generated/`

## Help Engine

The help engine (`help_engine.py`) orchestrates:
1. Queries RAG for relevant doc chunks
2. Gathers git context (branch, structure, diff, history) based on the question
3. Formats a structured response combining both
