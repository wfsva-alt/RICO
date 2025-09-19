import os
import json
import threading
import time
from typing import List, Dict, Any

try:
    import redis
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

USE_REDIS = os.getenv("USE_REDIS", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Fallback SQLite imports if needed
import sqlite3

class CoreMemory:
    def __init__(self, r=None):
        self.r = r
        self.key = "core:memory"
        self._lock = threading.Lock()

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
        self.r = r
        self._lock = threading.Lock()

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
        self.r = r
        self.index_name = "idx:general_memory"
        self.vector_dim = 1536  # OpenAI Ada default
        self._lock = threading.Lock()
        if self.r and REDIS_SEARCH_AVAILABLE:
            try:
                self.r.ft(self.index_name).info()
            except Exception:
                self.r.ft(self.index_name).create_index([
                    TextField("content"),
                    TextField("metadata"),
                    VectorField("vector", "FLAT", {"TYPE": "FLOAT32", "DIM": self.vector_dim, "DISTANCE_METRIC": "COSINE"})
                ], definition=IndexDefinition(prefix=["general:memory:"])
                )

    def add_entry(self, content: str, metadata: dict) -> None:
        if self.r:
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

    def search(self, query: str, top_k=5) -> List[dict]:
        if self.r and REDIS_SEARCH_AVAILABLE:
            try:
                import numpy as np
                vec = embed_text(query)
                q = Query(f"*=>[KNN {top_k} @vector $vec as score]").sort_by("score").paging(0, top_k).return_fields("content", "metadata", "score").dialect(2)
                params_dict = {"vec": np.array(vec, dtype=np.float32).tobytes()}
                results = self.r.ft(self.index_name).search(q, query_params=params_dict)
                return [{"content": doc.content, "metadata": json.loads(doc.metadata), "score": doc.score} for doc in results.docs]
            except Exception as e:
                print(f"Redis search error: {e}")
                return []
        return []

class ChannelContext:
    def __init__(self, r=None):
        self.r = r
        self.buffer_size = 100  # Store last 100 messages
        self.max_message_length = 500  # Truncate very long messages

    def add_message(self, channel_id: int, message: str, author: str = "Unknown") -> None:
        """Add a message to channel history with author info."""
        key = f"history:{channel_id}"
        if self.r:
            # Truncate very long messages to prevent memory bloat
            if len(message) > self.max_message_length:
                message = message[:self.max_message_length] + "..."
            
            # Store with timestamp and author
            import time
            timestamp = int(time.time())
            message_data = {
                "timestamp": timestamp,
                "author": author,
                "content": message
            }
            
            # Store as JSON string
            self.r.lpush(key, json.dumps(message_data, ensure_ascii=False))
            self.r.ltrim(key, 0, self.buffer_size - 1)

    def get_recent(self, channel_id: int, limit=100) -> List[dict]:
        """Get recent messages with full context including author and timestamp."""
        key = f"history:{channel_id}"
        if self.r:
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
        return []

    def get_formatted_context(self, channel_id: int, limit=50) -> str:
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

class MemoryManager:
    def __init__(self):
        self.r = None
        if USE_REDIS and redis:
            self.r = redis.Redis.from_url(REDIS_URL, decode_responses=False)
        self.core = CoreMemory(self.r)
        self.user = UserMemory(self.r)
        self.general = GeneralMemory(self.r)
        self.channel = ChannelContext(self.r)

    def build_prompt(self, user_id: int, channel_id: int, user_message: str) -> str:
        core = self.core.get_core()
        user = self.user.get_user(user_id)
        general = self.general.search(user_message, top_k=5)
        channel_context = self.channel.get_formatted_context(channel_id, limit=50)
        
        # Compose prompt with enhanced context
        prompt = f"[CORE MEMORY]\n{core}\n\n"
        prompt += f"[USER DOSSIER]\n{json.dumps(user, ensure_ascii=False)}\n\n"
        prompt += f"[RELEVANT MEMORY]\n{json.dumps(general, ensure_ascii=False)}\n\n"
        prompt += f"[CHANNEL CONTEXT - Last 50 messages]\n{channel_context}\n\n"
        prompt += f"[CURRENT MESSAGE]\n{user_message}\n"
        return prompt
