"""
Local embedding implementation using sentence-transformers
No API key required - runs locally
"""
import os
import numpy as np
from typing import List
from functools import lru_cache

# Try to import sentence-transformers, fall back to simple hash-based embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Global model instance
_model = None

def get_model():
    """Get or initialize the embedding model"""
    global _model
    if _model is None and SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            _model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            print(f"Warning: Could not load sentence-transformers model: {e}")
            _model = None
    return _model

@lru_cache(maxsize=1000)
def embed_text(text: str) -> List[float]:
    """
    Returns embedding vector for the given text.
    Uses sentence-transformers if available, otherwise falls back to hash-based embeddings.
    """
    if not text or not text.strip():
        return [0.0] * 384  # Default dimension for all-MiniLM-L6-v2
    
    # Try sentence-transformers first
    model = get_model()
    if model is not None:
        try:
            embedding = model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            print(f"Warning: sentence-transformers failed: {e}")
    
    # Fallback: simple hash-based embedding
    return hash_based_embedding(text)

def hash_based_embedding(text: str, dim: int = 384) -> List[float]:
    """
    Fallback embedding using hash functions.
    Not as good as real embeddings but works without dependencies.
    """
    import hashlib
    import math
    
    # Normalize text
    text = text.lower().strip()
    if not text:
        return [0.0] * dim
    
    # Create multiple hash values
    embeddings = []
    for i in range(dim):
        # Use different hash inputs for each dimension
        hash_input = f"{text}_{i}_{len(text)}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        
        # Normalize to [-1, 1] range
        normalized = (hash_value % 1000000) / 1000000.0 * 2 - 1
        embeddings.append(normalized)
    
    return embeddings

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two embedding vectors"""
    if len(a) != len(b):
        return 0.0
    
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)
