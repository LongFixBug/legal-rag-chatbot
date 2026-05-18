from __future__ import annotations

import os

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": ADMIN_TOKEN} if ADMIN_TOKEN else {}


def get_documents() -> list[dict]:
    response = httpx.get(f"{API_BASE_URL}/documents", timeout=30.0)
    response.raise_for_status()
    return response.json()


def ask_question(question: str, top_k: int = 4, conversation_id: str | None = None) -> dict:
    response = httpx.post(
        f"{API_BASE_URL}/chat/query",
        json={"question": question, "top_k": top_k, "conversation_id": conversation_id},
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()


def create_conversation(title: str | None = None) -> dict:
    response = httpx.post(
        f"{API_BASE_URL}/chat/conversations",
        json={"title": title},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def list_conversations() -> list[dict]:
    response = httpx.get(f"{API_BASE_URL}/chat/conversations", timeout=30.0)
    response.raise_for_status()
    return response.json()


def get_conversation_history(conversation_id: str) -> list[dict]:
    response = httpx.get(f"{API_BASE_URL}/chat/conversations/{conversation_id}", timeout=30.0)
    response.raise_for_status()
    return response.json()


def delete_conversation(conversation_id: str) -> dict:
    response = httpx.delete(f"{API_BASE_URL}/chat/conversations/{conversation_id}", timeout=30.0)
    response.raise_for_status()
    return response.json()


def search_legal(query: str, article: str | None = None, top_k: int = 6) -> dict:
    params = {"q": query, "top_k": top_k}
    if article:
        params["article"] = article
    response = httpx.get(f"{API_BASE_URL}/legal/search", params=params, timeout=30.0)
    response.raise_for_status()
    return response.json()


def ingest_document(title: str, content: str) -> dict:
    response = httpx.post(
        f"{API_BASE_URL}/documents/ingest",
        json={"title": title, "content": content, "source": "streamlit"},
        headers=admin_headers(),
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


def upload_document(title: str, filename: str, content: bytes, mime_type: str) -> dict:
    response = httpx.post(
        f"{API_BASE_URL}/documents/upload",
        data={"title": title},
        files={"file": (filename, content, mime_type)},
        headers=admin_headers(),
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


def preload_samples() -> dict:
    response = httpx.post(f"{API_BASE_URL}/documents/preload", headers=admin_headers(), timeout=60.0)
    response.raise_for_status()
    return response.json()


def reindex_samples() -> dict:
    response = httpx.post(f"{API_BASE_URL}/documents/reindex", headers=admin_headers(), timeout=120.0)
    response.raise_for_status()
    return response.json()
