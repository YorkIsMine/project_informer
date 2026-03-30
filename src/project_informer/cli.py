"""CLI interface for Project Informer."""

from pathlib import Path

import click


@click.group()
def main():
    """Project Informer - AI-powered developer assistant."""
    pass


@main.command("generate-docs")
@click.argument("project_path", default=".")
def generate_docs(project_path):
    """Auto-generate documentation from code analysis.

    Scans the project code, analyzes structure, classes, functions,
    and generates markdown docs in docs/_generated/.
    """
    from project_informer.doc_generator import generate_docs as gen

    click.echo(f"Analyzing project at: {project_path}")
    generated = gen(project_path)

    if not generated:
        click.echo("No code files found to analyze.")
        return

    click.echo(f"Generated {len(generated)} documentation files:")
    for path in generated:
        click.echo(f"  {path}")
    click.echo("\nRun 'project-informer index' to add these to the search index.")


@main.command()
@click.argument("project_path", default=".")
def index(project_path):
    """Index project documentation for RAG queries.

    Indexes README, docs/, schema files, and auto-generated docs
    into a local ChromaDB vector store.
    """
    from project_informer.rag.indexer import index_project

    click.echo(f"Indexing documentation in: {project_path}")
    count = index_project(project_path)
    if count == 0:
        click.echo("No documentation files found. Run 'project-informer generate-docs' first.")
    else:
        click.echo(f"Indexed {count} chunks from project documentation.")


@main.command("help")
@click.argument("question")
@click.option("--project", "-p", default=".", help="Path to the project root.")
@click.option(
    "--llm", "provider",
    type=click.Choice(["auto", "none", "ollama", "openai"], case_sensitive=False),
    default="auto",
    help="LLM provider: auto (detect best), none (raw context), ollama (local), openai (remote).",
)
def help_cmd(question, project, provider):
    """Ask a question about the project.

    Uses RAG documentation search + git context to answer.
    Auto-detects the best LLM (Ollama > OpenAI > none).
    """
    from project_informer.help_engine import answer_question
    from project_informer.llm import detect_provider

    resolved = detect_provider() if provider == "auto" else provider
    if resolved != "none":
        click.echo(f"Using LLM: {resolved}")

    answer = answer_question(question, project, provider=provider)
    click.echo(answer)


@main.command()
@click.option("--project", "-p", default=".", help="Path to the project root.")
def serve(project):
    """Start the MCP server for AI assistant integration.

    The server exposes git tools (branch, files, diff, structure)
    and documentation search over the MCP protocol (stdio transport).
    """
    import os
    os.environ["PROJECT_INFORMER_PATH"] = project

    from project_informer.mcp_server.server import main as serve_main
    serve_main()


@main.command()
def config():
    """Interactively configure LLM provider and API keys.

    Saves settings to a .env file in the current directory.
    """
    from project_informer.llm import list_providers

    providers = list_providers()

    click.echo("Available LLM providers:\n")
    for key, desc in providers.items():
        click.echo(f"  {key:8s} - {desc}")

    click.echo()
    provider = click.prompt(
        "Choose LLM provider",
        type=click.Choice(list(providers.keys()), case_sensitive=False),
        default="none",
    )

    env_lines = [f"LLM_PROVIDER={provider}"]

    if provider == "ollama":
        model = click.prompt("Ollama model", default="llama3.2")
        url = click.prompt("Ollama URL", default="http://localhost:11434")
        env_lines.append(f"OLLAMA_MODEL={model}")
        env_lines.append(f"OLLAMA_URL={url}")
        click.echo(f"\nMake sure Ollama is running and model is pulled: ollama pull {model}")

    elif provider == "openai":
        api_key = click.prompt("OpenAI API key", hide_input=True)
        model = click.prompt("OpenAI model", default="gpt-4o-mini")
        env_lines.append(f"OPENAI_API_KEY={api_key}")
        env_lines.append(f"OPENAI_MODEL={model}")

    env_path = Path(".env")
    env_path.write_text("\n".join(env_lines) + "\n")
    click.echo(f"\nSaved configuration to {env_path.resolve()}")
    click.echo("Load it with: source .env  or  export $(cat .env | xargs)")


@main.command()
@click.option("--project", "-p", default=".", help="Path to the project root.")
@click.option("--port", default=8080, help="Port to run the web server on.")
@click.option("--host", default="0.0.0.0", help="Host to bind the web server to.")
def web(project, port, host):
    """Start the web interface.

    Opens a browser-based chat UI for asking questions about your project.
    """
    from project_informer.web import start_server

    click.echo(f"Starting Project Informer web UI...")
    click.echo(f"  Project: {Path(project).resolve()}")
    click.echo(f"  URL:     http://localhost:{port}")
    start_server(project=project, port=port, host=host)


if __name__ == "__main__":
    main()
