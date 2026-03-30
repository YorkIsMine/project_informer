# Usage Guide

## Installation

```bash
cd project_informer
pip install -e .
```

## Commands

### Auto-generate documentation

If the target project has no docs, generate them:

```bash
project-informer generate-docs /path/to/project
```

This creates `docs/_generated/` with:
- `overview.md` — project structure, stats, config files
- `architecture.md` — modules, classes, functions
- `api_reference.md` — detailed Python API docs (if applicable)

### Index documentation

```bash
project-informer index /path/to/project
```

Indexes all `.md`, `.rst`, `.txt`, and schema files into ChromaDB.

### Ask questions

```bash
project-informer help "What is the project structure?" -p /path/to/project
```

Combines RAG search results with live git context.

### Start MCP server

```bash
project-informer serve --project /path/to/project
```

Starts the MCP server over stdio for AI assistant integration.

## MCP Integration with Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "project-informer": {
      "command": "project-informer",
      "args": ["serve", "--project", "/path/to/project"]
    }
  }
}
```

## Environment Variables

- `PROJECT_INFORMER_PATH` — default project path for MCP server
