"""FastAPI web interface for Project Informer."""

import os
import subprocess
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Project Informer")

STATIC_DIR = Path(__file__).parent / "static"

# Default project path, set via CLI or env
PROJECT_PATH = os.environ.get("PROJECT_INFORMER_PATH", ".")


class AskRequest(BaseModel):
    question: str
    provider: str = "none"
    project_path: str | None = None


class IndexRequest(BaseModel):
    project_path: str | None = None


class GenerateDocsRequest(BaseModel):
    project_path: str | None = None


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = STATIC_DIR / "index.html"
    return html_path.read_text()


@app.post("/api/ask")
async def ask(req: AskRequest):
    from project_informer.help_engine import answer_question
    from project_informer.llm import detect_provider

    project = req.project_path or PROJECT_PATH
    provider = req.provider
    if provider == "auto":
        provider = detect_provider()
    try:
        answer = answer_question(req.question, project, provider=provider)
        return {"answer": answer, "provider": provider}
    except Exception as e:
        return {"answer": f"Error: {e}", "provider": provider}


@app.get("/api/providers")
async def providers():
    from project_informer.llm import detect_provider, _is_ollama_available, get_ollama_models

    detected = detect_provider()
    ollama_available = _is_ollama_available()
    ollama_models = get_ollama_models() if ollama_available else []
    openai_available = bool(os.environ.get("OPENAI_API_KEY"))

    return {
        "detected": detected,
        "ollama_available": ollama_available,
        "ollama_models": ollama_models,
        "openai_available": openai_available,
    }


@app.get("/api/status")
async def status():
    project = PROJECT_PATH
    root = Path(project).resolve()

    # Git branch
    branch = None
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
    except Exception:
        pass

    # Indexed chunks count
    chunks = 0
    try:
        import chromadb
        db_path = str(root / ".chromadb")
        if Path(db_path).exists():
            client = chromadb.PersistentClient(path=db_path)
            collection = client.get_collection("project_docs")
            chunks = collection.count()
    except Exception:
        pass

    # Provider - auto-detect
    from project_informer.llm import detect_provider
    provider = detect_provider()

    return {
        "project_path": str(root),
        "project_name": root.name,
        "branch": branch,
        "indexed_chunks": chunks,
        "provider": provider,
    }


@app.post("/api/index")
async def index_docs(req: IndexRequest):
    from project_informer.rag.indexer import index_project

    project = req.project_path or PROJECT_PATH
    try:
        count = index_project(project)
        return {"success": True, "chunks": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/generate-docs")
async def generate_docs(req: GenerateDocsRequest):
    from project_informer.doc_generator import generate_docs as gen

    project = req.project_path or PROJECT_PATH
    try:
        files = gen(project)
        return {"success": True, "files": files}
    except Exception as e:
        return {"success": False, "error": str(e)}


def start_server(project: str = ".", port: int = 8080, host: str = "0.0.0.0"):
    """Start the web server."""
    import uvicorn

    global PROJECT_PATH
    PROJECT_PATH = str(Path(project).resolve())
    os.environ["PROJECT_INFORMER_PATH"] = PROJECT_PATH

    uvicorn.run(app, host=host, port=port)
