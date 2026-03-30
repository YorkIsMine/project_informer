"""CLI interface for Project Informer."""

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
def help_cmd(question, project):
    """Ask a question about the project.

    Uses RAG documentation search + git context to answer.
    """
    from project_informer.help_engine import answer_question

    answer = answer_question(question, project)
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


if __name__ == "__main__":
    main()
