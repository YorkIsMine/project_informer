"""RAG query: search the indexed documentation."""

from pathlib import Path

import chromadb

from project_informer.rag.indexer import COLLECTION_NAME


def query_docs(
    question: str,
    project_path: str,
    n_results: int = 5,
    db_path: str | None = None,
) -> list[dict]:
    """Query the vector store for relevant documentation chunks.

    Returns list of {"document": str, "source": str, "heading": str, "distance": float}.
    """
    root = Path(project_path).resolve()
    if db_path is None:
        db_path = str(root / ".chromadb")

    client = chromadb.PersistentClient(path=db_path)

    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        raise RuntimeError(
            "No indexed documentation found. Run 'project-informer index' first."
        )

    count = collection.count()
    if count == 0:
        return []

    actual_n = min(n_results, count)
    results = collection.query(query_texts=[question], n_results=actual_n)

    output = []
    for i in range(len(results["documents"][0])):
        output.append({
            "document": results["documents"][0][i],
            "source": results["metadatas"][0][i].get("source", "unknown"),
            "heading": results["metadatas"][0][i].get("heading", ""),
            "distance": results["distances"][0][i] if results.get("distances") else 0,
        })

    return output
