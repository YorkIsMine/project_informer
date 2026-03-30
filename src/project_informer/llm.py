"""LLM providers: Ollama (local) and OpenAI (remote)."""

import json
import os

SYSTEM_PROMPT = (
    "You are a helpful developer assistant that answers questions about a software project. "
    "Use the provided documentation and project context to give accurate, concise answers. "
    "If the context doesn't contain enough information, say so. "
    "Answer in the same language as the question."
)


def ask_llm(question: str, context: str, provider: str = "none") -> str:
    """Send question + context to the selected LLM provider.

    Args:
        question: The user's question.
        context: Assembled RAG + git context.
        provider: "ollama", "openai", or "none".

    Returns:
        LLM-synthesized answer, or raw context if provider is "none".
    """
    if provider == "none":
        return context

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Project context:\n\n{context}\n\nQuestion: {question}"},
    ]

    if provider == "ollama":
        return _ask_ollama(messages)
    elif provider == "openai":
        return _ask_openai(messages)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'ollama', 'openai', or 'none'.")


def _ask_ollama(messages: list[dict]) -> str:
    """Query Ollama local LLM."""
    import httpx

    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")

    try:
        response = httpx.post(
            f"{base_url}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=120.0,
        )
        response.raise_for_status()
    except httpx.ConnectError:
        return (
            f"Error: Cannot connect to Ollama at {base_url}\n"
            "Make sure Ollama is running: ollama serve\n"
            f"And the model is pulled: ollama pull {model}"
        )
    except httpx.HTTPStatusError as e:
        return f"Error from Ollama: {e.response.status_code} {e.response.text}"

    data = response.json()
    return data.get("message", {}).get("content", "No response from Ollama.")


def _ask_openai(messages: list[dict]) -> str:
    """Query OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return (
            "Error: OPENAI_API_KEY not set.\n"
            "Set it with: export OPENAI_API_KEY=sk-...\n"
            "Or run: project-informer config"
        )

    from openai import OpenAI, APIError, AuthenticationError

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
    except AuthenticationError:
        return "Error: Invalid OPENAI_API_KEY. Check your API key."
    except APIError as e:
        return f"Error from OpenAI: {e}"

    return response.choices[0].message.content


def detect_provider() -> str:
    """Auto-detect the best available LLM provider.

    Priority: env LLM_PROVIDER > Ollama running > OpenAI key > none.
    """
    configured = os.environ.get("LLM_PROVIDER")
    if configured and configured != "auto":
        return configured

    # Check Ollama
    if _is_ollama_available():
        return "ollama"

    # Check OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"

    return "none"


def _is_ollama_available() -> bool:
    """Check if Ollama is running and has at least one model."""
    try:
        import httpx
        base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        resp = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return len(models) > 0
    except Exception:
        pass
    return False


def get_ollama_models() -> list[str]:
    """Get list of available Ollama models."""
    try:
        import httpx
        base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        resp = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def get_provider() -> str:
    """Get the configured LLM provider, with auto-detection."""
    return detect_provider()


def list_providers() -> dict[str, str]:
    """Return available providers with descriptions."""
    return {
        "auto": "Auto-detect best available (Ollama > OpenAI > none)",
        "none": "No LLM - show raw documentation chunks + git context",
        "ollama": "Ollama (local) - free, private, requires ollama installed",
        "openai": "OpenAI (remote) - requires OPENAI_API_KEY",
    }
