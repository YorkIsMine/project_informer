# Project Informer

AI-powered developer assistant that understands your project through documentation (RAG) and git context (MCP).

## Features

- **RAG Documentation Search** -- indexes README, docs/, and schema files into a local vector store (ChromaDB)
- **MCP Server** -- exposes git tools (branch, files, diff, tree) for AI assistants
- **Auto Doc Generation** -- analyzes project code and generates documentation automatically
- **`/help` Command** -- answers questions about your project using docs + git context

## Quick Start

```bash
pip install -e .

# Auto-generate docs for a project (if no docs exist)
project-informer generate-docs /path/to/project

# Index project documentation
project-informer index /path/to/project

# Ask questions
project-informer help "What is the project structure?" -p /path/to/project

# Start MCP server for AI assistant integration
project-informer serve --project /path/to/project
```

## Architecture

The system has three layers:

1. **RAG Layer** -- discovers, chunks, and embeds documentation into ChromaDB with default embeddings (all-MiniLM-L6-v2). Queries return the most relevant doc chunks.

2. **MCP Layer** -- a Model Context Protocol server exposing git operations as tools. External AI assistants (Claude Desktop, Claude Code) connect to this over stdio.

3. **Help Engine** -- combines RAG results with live git context to answer developer questions. No LLM API key required for basic operation.

## MCP Integration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "project-informer": {
      "command": "project-informer",
      "args": ["serve", "--project", "/path/to/your/project"]
    }
  }
}
```

## Requirements

- Python 3.10+
- Git (for MCP git tools)
