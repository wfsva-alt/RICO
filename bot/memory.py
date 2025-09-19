# bot/memory.py
import sqlite3
import threading
from bot.logger import logger
from bot.config import USE_REDIS, REDIS_URL

try:
    import redis
except Exception:
    redis = None

class ShortTermMemory:
    def __init__(self):
        self._mem = {}
        self._lock = threading.Lock()

    def add_message(self, user_id: int, message: str):
        with self._lock:
            self._mem.setdefault(user_id, []).append(message)
            # limit length
            if len(self._mem[user_id]) > 20:
                self._mem[user_id].pop(0)

    def get_messages(self, user_id: int):
        return list(self._mem.get(user_id, []))

short_term = ShortTermMemory()

class LongTermMemory:
    def __init__(self):
        if USE_REDIS and redis:
            self.store = redis.from_url(REDIS_URL)
            logger.info("Using Redis for long-term memory")
        else:
            self.conn = sqlite3.connect("longterm_memory.db", check_same_thread=False)
            self._init_db()
            logger.info("Using SQLite for long-term memory")

    def _init_db(self):
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS memory (user_id INTEGER, note TEXT)")
        self.conn.commit()

    def add_note(self, user_id: int, note: str):
        if USE_REDIS and redis:
            key = f"mem:{user_id}"
            self.store.lpush(key, note)
        else:
            c = self.conn.cursor()
            c.execute("INSERT INTO memory (user_id, note) VALUES (?, ?)", (user_id, note))
            self.conn.commit()

    def get_notes(self, user_id: int):
        if USE_REDIS and redis:
            key = f"mem:{user_id}"
            return [x.decode() if isinstance(x, bytes) else x for x in self.store.lrange(key, 0, -1)]
        else:
            c = self.conn.cursor()
            c.execute("SELECT note FROM memory WHERE user_id = ?", (user_id,))
            return [r[0] for r in c.fetchall()]

long_term = LongTermMemory()
