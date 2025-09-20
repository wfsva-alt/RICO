import os
import json
import threading
import time
from typing import List, Dict, Any
from functools import lru_cache

try:
    import redis
    from redis.connection import ConnectionPool
    # Try to import Redis search features (may not be available in all versions)
    try:
        from redis.commands.search.field import VectorField, TextField
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        from redis.commands.search.query import Query
        REDIS_SEARCH_AVAILABLE = True
    except ImportError:
        REDIS_SEARCH_AVAILABLE = False
        # Create dummy classes for compatibility
        class VectorField: pass
        class TextField: pass
        class IndexDefinition: pass
        class IndexType: pass
        class Query: pass
except ImportError:
    redis = None
    REDIS_SEARCH_AVAILABLE = False

from utils.embeddings import embed_text
from bot.logger import logger

USE_REDIS = os.getenv("USE_REDIS", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Fallback SQLite imports if needed
import sqlite3

# Global Redis connection pool
_redis_pool = None
_redis_client = None

def get_redis_client():
    """Get or create Redis client with connection pooling"""
    global _redis_client, _redis_pool
    
    if _redis_client is not None:
        return _redis_client
    
    if not USE_REDIS or not redis:
        return None
    
    try:
        # Create connection pool
        _redis_pool = ConnectionPool.from_url(REDIS_URL, decode_responses=False, max_connections=20)
        _redis_client = redis.Redis(connection_pool=_redis_pool)
        # Test connection
        _redis_client.ping()
        logger.info("Redis connection pool created successfully")
        return _redis_client
    except Exception as e:
        logger.error(f"Failed to create Redis connection pool: {e}")
        return None

class CoreMemory:
    def __init__(self, r=None):
        self.r = r or get_redis_client()
        self.key = "core:memory"
        self._lock = threading.RLock()  # Use RLock for nested locking

    def load_core(self) -> str:
        if self.r:
            val = self.r.get(self.key)
            return val.decode() if val else ""
        return ""

    def update_core(self, new_content: str) -> None:
        if self.r:
            with self._lock:
                self.r.set(self.key, new_content)

    def add_core_entry(self, title: str, content: str) -> None:
        """Add a new core memory entry, preserving existing entries."""
        if self.r:
            with self._lock:
                # Get existing core memory
                existing = self.load_core()
                try:
                    if existing:
                        core_data = json.loads(existing)
                        if not isinstance(core_data, list):
                            # Convert old format to new format
                            core_data = [core_data] if core_data else []
                    else:
                        core_data = []
                except (json.JSONDecodeError, TypeError):
                    core_data = []
                
                # Add new entry
                new_entry = {"title": title, "content": content, "timestamp": time.time()}
                core_data.append(new_entry)
                
                # Save back to Redis
                self.r.set(self.key, json.dumps(core_data, ensure_ascii=False))

    def get_core(self) -> str:
        return self.load_core()

class UserMemory:
    def __init__(self, r=None):
        self.r = r or get_redis_client()
        self._lock = threading.RLock()  # Use RLock for nested locking

    def get_user(self, user_id: int) -> dict:
        key = f"user:{user_id}:memory"
        if self.r:
            data = self.r.hgetall(key)
            if not data:
                return {"traits": [], "preferences": {}, "history": []}
            return {k.decode(): json.loads(v) for k, v in data.items()}
        return {"traits": [], "preferences": {}, "history": []}

    def update_user(self, user_id: int, new_info: dict) -> None:
        key = f"user:{user_id}:memory"
        if self.r:
            with self._lock:
                for k, v in new_info.items():
                    self.r.hset(key, k, json.dumps(v))

    def clear_user(self, user_id: int) -> None:
        key = f"user:{user_id}:memory"
        if self.r:
            self.r.delete(key)

class GeneralMemory:
    def __init__(self, r=None):
        self.r = r or get_redis_client()
        self.index_name = "idx:general_memory"
        self.vector_dim = 1536  # OpenAI Ada default
        self._lock = threading.RLock()  # Use RLock for nested locking
        if self.r and REDIS_SEARCH_AVAILABLE:
            try:
                self.r.ft(self.index_name).info()
            except Exception as e:
                logger.warning(f"Redis search index not found, creating: {e}")
                try:
                    self.r.ft(self.index_name).create_index([
                        TextField("content"),
                        TextField("metadata"),
                        VectorField("vector", "FLAT", {"TYPE": "FLOAT32", "DIM": self.vector_dim, "DISTANCE_METRIC": "COSINE"})
                    ], definition=IndexDefinition(prefix=["general:memory:"])
                    )
                except Exception as create_error:
                    logger.error(f"Failed to create Redis search index: {create_error}")

    def add_entry(self, content: str, metadata: dict) -> None:
        if self.r:
            with self._lock:
                try:
                    import numpy as np
                    vec = embed_text(content)
                    doc_id = f"general:memory:{os.urandom(8).hex()}"
                    pipe = self.r.pipeline()
                    pipe.hset(doc_id, mapping={
                        "content": content,
                        "metadata": json.dumps(metadata),
                        "vector": np.array(vec, dtype=np.float32).tobytes()
                    })
                    pipe.execute()
                except Exception as e:
                    logger.error(f"Failed to add general memory entry: {e}")
                    raise

    def search(self, query: str, top_k=5) -> List[dict]:
        if self.r and REDIS_SEARCH_AVAILABLE:
            with self._lock:
                try:
                    import numpy as np
                    vec = embed_text(query)
                    q = Query(f"*=>[KNN {top_k} @vector $vec as score]").sort_by("score").paging(0, top_k).return_fields("content", "metadata", "score").dialect(2)
                    params_dict = {"vec": np.array(vec, dtype=np.float32).tobytes()}
                    results = self.r.ft(self.index_name).search(q, query_params=params_dict)
                    return [{"content": doc.content, "metadata": json.loads(doc.metadata), "score": doc.score} for doc in results.docs]
                except Exception as e:
                    logger.error(f"Redis search error: {e}")
                    return []
        elif self.r:
            # Fallback to simple keyword search if Redis search is not available
            with self._lock:
                try:
                    # Get all general memory keys
                    pattern = "general:memory:*"
                    keys = self.r.keys(pattern)
                    if not keys:
                        return []
                    
                    results = []
                    query_lower = query.lower()
                    
                    for key in keys[:50]:  # Limit to first 50 entries for performance
                        try:
                            data = self.r.hgetall(key)
                            if data:
                                content = data.get(b'content', b'').decode('utf-8', errors='ignore')
                                metadata = data.get(b'metadata', b'{}').decode('utf-8', errors='ignore')
                                
                                # Simple keyword matching
                                if query_lower in content.lower():
                                    try:
                                        metadata_dict = json.loads(metadata)
                                    except json.JSONDecodeError:
                                        metadata_dict = {}
                                    
                                    results.append({
                                        "content": content,
                                        "metadata": metadata_dict,
                                        "score": 1.0  # Simple score for keyword matches
                                    })
                        except Exception as e:
                            logger.warning(f"Error processing memory entry {key}: {e}")
                            continue
                    
                    # Sort by score and return top_k
                    results.sort(key=lambda x: x.get('score', 0), reverse=True)
                    return results[:top_k]
                    
                except Exception as e:
                    logger.error(f"Fallback search error: {e}")
                    return []
        return []

class ChannelContext:
    def __init__(self, r=None):
        self.r = r or get_redis_client()
        self.buffer_size = 100  # Store last 100 messages
        self.max_message_length = 500  # Truncate very long messages
        self._lock = threading.RLock()  # Use RLock for nested locking

    def add_message(self, channel_id: int, message: str, author: str = "Unknown") -> None:
        """Add a message to channel history with author info."""
        key = f"history:{channel_id}"
        if self.r:
            with self._lock:
                try:
                    # Truncate very long messages to prevent memory bloat
                    if len(message) > self.max_message_length:
                        message = message[:self.max_message_length] + "..."
                    
                    # Store with timestamp and author
                    timestamp = int(time.time())
                    message_data = {
                        "timestamp": timestamp,
                        "author": author,
                        "content": message
                    }
                    
                    # Store as JSON string
                    self.r.lpush(key, json.dumps(message_data, ensure_ascii=False))
                    self.r.ltrim(key, 0, self.buffer_size - 1)
                except Exception as e:
                    logger.error(f"Failed to add channel message: {e}")
                    raise

    def get_recent(self, channel_id: int, limit=100) -> List[dict]:
        """Get recent messages with full context including author and timestamp."""
        key = f"history:{channel_id}"
        if self.r:
            with self._lock:
                try:
                    messages = []
                    raw_messages = self.r.lrange(key, 0, limit-1)
                    for msg in raw_messages:
                        try:
                            message_data = json.loads(msg.decode())
                            messages.append(message_data)
                        except (json.JSONDecodeError, AttributeError):
                            # Handle old format messages (just strings)
                            messages.append({
                                "timestamp": 0,
                                "author": "Unknown",
                                "content": msg.decode() if isinstance(msg, bytes) else str(msg)
                            })
                    return messages
                except Exception as e:
                    logger.error(f"Failed to get recent messages: {e}")
                    return []
        return []

    def get_formatted_context(self, channel_id: int, limit=15) -> str:
        """Get formatted context string for use in prompts."""
        messages = self.get_recent(channel_id, limit)
        if not messages:
            return "No recent conversation history."
        
        context_lines = []
        for msg in messages:
            author = msg.get("author", "Unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", 0)
            
            # Format timestamp if available
            if timestamp > 0:
                import datetime
                dt = datetime.datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("%H:%M")
            else:
                time_str = "??:??"
            
            context_lines.append(f"[{time_str}] {author}: {content}")
        
        return "\n".join(context_lines)

    def search(self, channel_id: int, query: str, limit=5) -> List[dict]:
        """Search through channel history for relevant messages."""
        with self._lock:
            try:
                messages = self.get_recent(channel_id, 100)
                if not messages:
                    return []
                
                # Simple keyword search (could be enhanced with vector search)
                query_lower = query.lower()
                matches = []
                for msg in messages:
                    content = msg.get("content", "").lower()
                    if query_lower in content:
                        matches.append(msg)
                
                return matches[:limit]
            except Exception as e:
                logger.error(f"Failed to search channel history: {e}")
                return []

class MemoryManager:
    def __init__(self):
        self.r = get_redis_client()
        self.core = CoreMemory(self.r)
        self.user = UserMemory(self.r)
        self.general = GeneralMemory(self.r)
        self.channel = ChannelContext(self.r)

    def build_prompt(self, user_id: int, channel_id: int, user_message: str) -> str:
        """Build optimized prompt with efficient memory retrieval"""
        try:
            # Fetch memory components sequentially to avoid race conditions
            results = {}
            
            # Core memory
            try:
                core_memory = self.core.get_core()
                if core_memory:
                    # Parse core memory to make it more readable
                    try:
                        core_data = json.loads(core_memory)
                        if isinstance(core_data, list):
                            core_formatted = []
                            for entry in core_data:
                                if isinstance(entry, dict):
                                    core_formatted.append(f"- {entry.get('title', 'Untitled')}: {entry.get('content', '')}")
                                else:
                                    core_formatted.append(str(entry))
                            results['core'] = "\n".join(core_formatted)
                        else:
                            results['core'] = str(core_data)
                    except json.JSONDecodeError:
                        results['core'] = core_memory
                else:
                    results['core'] = "No core memory available."
            except Exception as e:
                logger.warning(f"Failed to fetch core memory: {e}")
                results['core'] = "Core memory unavailable."
            
            # User memory
            try:
                user_data = self.user.get_user(user_id)
                if user_data and any(user_data.values()):
                    user_formatted = []
                    if user_data.get('traits'):
                        user_formatted.append(f"Traits: {', '.join(user_data['traits'])}")
                    if user_data.get('preferences'):
                        user_formatted.append(f"Preferences: {json.dumps(user_data['preferences'])}")
                    if user_data.get('history'):
                        user_formatted.append(f"History: {len(user_data['history'])} entries")
                    results['user'] = "\n".join(user_formatted) if user_formatted else "No user data available."
                else:
                    results['user'] = "No user data available."
            except Exception as e:
                logger.warning(f"Failed to fetch user memory: {e}")
                results['user'] = "User memory unavailable."
            
            # General memory (semantic search)
            try:
                general_results = self.general.search(user_message, top_k=3)
                if general_results:
                    general_formatted = []
                    for result in general_results:
                        content = result.get('content', '')[:200]  # Truncate long content
                        metadata = result.get('metadata', {})
                        title = metadata.get('title', 'Untitled')
                        general_formatted.append(f"- {title}: {content}")
                    results['general'] = "\n".join(general_formatted)
                else:
                    results['general'] = "No relevant general memory found."
            except Exception as e:
                logger.warning(f"Failed to fetch general memory: {e}")
                results['general'] = "General memory unavailable."
            
            # Channel context
            try:
                channel_context = self.channel.get_formatted_context(channel_id, limit=10)
                results['channel'] = channel_context if channel_context else "No recent conversation history."
            except Exception as e:
                logger.warning(f"Failed to fetch channel context: {e}")
                results['channel'] = "Channel context unavailable."
            
            # Compose prompt with enhanced context
            prompt = f"""You are RICO, an autonomous agent with a streetwise, darkly comedic personality.

[CORE MEMORY - Your fundamental knowledge]
{results.get('core', 'No core memory available.')}

[USER DOSSIER - Information about the current user]
{results.get('user', 'No user data available.')}

[RELEVANT MEMORY - Contextually relevant information]
{results.get('general', 'No relevant memory found.')}

[CHANNEL CONTEXT - Recent conversation history]
{results.get('channel', 'No conversation history.')}

[CURRENT MESSAGE]
{user_message}

Respond with your streetwise personality, using the context above to provide relevant and personalized responses."""
            
            return prompt
            
        except Exception as e:
            logger.error(f"Failed to build prompt: {e}")
            # Fallback to simple prompt
            return f"""You are RICO, an autonomous agent with a streetwise, darkly comedic personality.

[CURRENT MESSAGE]
{user_message}

Respond with your streetwise personality."""
