import os
import requests

EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL")


def embed_text(text: str) -> list:
    """
    Returns embedding vector for the given text using the configured API.
    Replace with your preferred embedding provider if needed.
    """
    if not EMBEDDING_API_KEY:
        raise RuntimeError("EMBEDDING_API_KEY not set in environment.")
    headers = {
        "Authorization": f"Bearer {EMBEDDING_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "input": text,
        "model": "text-embedding-ada-002"
    }
    resp = requests.post(EMBEDDING_API_URL, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]
