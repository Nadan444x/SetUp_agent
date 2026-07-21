"""Thin wrapper around the Ollama client.

All Ollama-specific details live here so agent.py only thinks in terms of
"send messages + tools, get back a message that may contain tool calls".
"""

from __future__ import annotations

import os

import httpx
import ollama

DEFAULT_HOST = "http://localhost:11434"


def client() -> ollama.Client:
    return ollama.Client(host=os.environ.get("OLLAMA_HOST", DEFAULT_HOST))


def server_up() -> bool:
    try:
        client().list()
        return True
    except Exception:
        return False


def installed_models() -> list[str]:
    try:
        return [m.model for m in client().list().models if m.model]
    except Exception:
        return []


def has_model(model: str) -> bool:
    names = installed_models()
    if any(name == model for name in names):
        return True
    # A bare name (no tag) resolves to "<name>:latest" server-side — NOT to an
    # arbitrary installed tag. Only report present if that exact tag exists,
    # otherwise preflight would pass but chat() would 404.
    if ":" not in model:
        return any(name == f"{model}:latest" for name in names)
    return False


class ModelMissing(Exception):
    def __init__(self, model: str):
        super().__init__(model)
        self.model = model
        self.hint = f"model '{model}' is not pulled — run:  ollama pull {model}"


class ServerDown(Exception):
    hint = (
        "the Ollama server is not responding — start it with:  brew services start ollama\n"
        "(or run `ollama serve` in another terminal)"
    )


def chat(model: str, messages: list, tools: list) -> "ollama.ChatResponse":
    """One non-streaming chat turn with tool schemas attached."""
    try:
        return client().chat(model=model, messages=messages, tools=tools)
    except ollama.ResponseError as exc:
        if "not found" in str(exc).lower() or getattr(exc, "status_code", -1) == 404:
            raise ModelMissing(model) from exc
        raise
    # builtin ConnectionError covers a fully-down server (ollama pre-converts
    # httpx.ConnectError); httpx.TransportError covers read/connect timeouts and
    # dropped streams mid-generation (common for a 7B model on a loaded Mac).
    except (ConnectionError, httpx.TransportError) as exc:
        raise ServerDown() from exc
