import os
import requests
from typing import List
from functools import lru_cache
import hashlib

EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL")

# Cache for embeddings to avoid recomputing
_embedding_cache = {}

def _get_cache_key(text: str) -> str:
    """Generate a cache key for the text"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

@lru_cache(maxsize=1000)
def embed_text(text: str) -> List[float]:
    """
    Returns embedding vector for the given text.
    Uses external API if configured, otherwise falls back to local embeddings.
    """
    # Try external API first
    if EMBEDDING_API_KEY and EMBEDDING_API_URL:
        try:
            return _api_embedding(text)
        except Exception as e:
            print(f"Warning: API embedding failed: {e}, falling back to local")
    
    # Fallback to local embeddings
    try:
        from .embeddings_local import embed_text as local_embed_text
        return local_embed_text(text)
    except ImportError:
        # Final fallback: simple hash-based embedding
        return _hash_based_embedding(text)

def _api_embedding(text: str) -> List[float]:
    """Use external API for embeddings"""
    headers = {
        "Content-Type": "application/json"
    }
    
    # Check if it's Gemini API (different format)
    if "generativelanguage.googleapis.com" in EMBEDDING_API_URL:
        # Gemini API format
        data = {
            "content": {
                "parts": [{"text": text}]
            }
        }
        # Add API key as query parameter for Gemini
        url = f"{EMBEDDING_API_URL}?key={EMBEDDING_API_KEY}"
    else:
        # OpenAI or other API format
        headers["Authorization"] = f"Bearer {EMBEDDING_API_KEY}"
        data = {
            "input": text,
            "model": "text-embedding-ada-002"
        }
        url = EMBEDDING_API_URL
    
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    
    if "generativelanguage.googleapis.com" in EMBEDDING_API_URL:
        # Gemini API response format
        return resp.json()["embedding"]["values"]
    else:
        # OpenAI API response format
        return resp.json()["data"][0]["embedding"]

def _hash_based_embedding(text: str, dim: int = 384) -> List[float]:
    """Simple hash-based embedding fallback"""
    import hashlib
    import math
    
    text = text.lower().strip()
    if not text:
        return [0.0] * dim
    
    embeddings = []
    for i in range(dim):
        hash_input = f"{text}_{i}_{len(text)}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        normalized = (hash_value % 1000000) / 1000000.0 * 2 - 1
        embeddings.append(normalized)
    
    return embeddings
