def tool_get_general_memory(query: str) -> str:
    """
    Searches general memory (RAG) for relevant entries. Input is a query string.
    Returns top 5 results as JSON.
    """
    try:
        results = memory_manager.general.search(query, top_k=5)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_general_memory error: %s", e)
        return f"Error: {e}"
def tool_add_general_memory(args: str) -> str:
    """
    Adds an entry to general memory (RAG). args should be a JSON string: {"user_id": int, "content": str, "metadata": dict (optional)}
    All users are allowed.
    """
    try:
        obj = json.loads(args)
        content = obj["content"]
        metadata = obj.get("metadata", {})
        # Optionally add user_id to metadata for traceability
        metadata["added_by"] = obj.get("user_id")
        memory_manager.general.add_entry(content, metadata)
        return "General memory entry added."
    except Exception as e:
        logger.exception("add_general_memory error: %s", e)
        return f"Error: {e}"

# Clean, organized tools.py with memory tools supporting title and by-title search
import ast, operator as op, tempfile, subprocess, time, logging, os, json, requests
from bot.logger import logger
from bot.config import CODE_EXEC_ENABLED
from bot.memory_manager import MemoryManager

CREATOR_IDS = {756227441432723656, 760498940126298112}
memory_manager = MemoryManager()

# --- User Memory Tools ---
def tool_get_user_memory(user_id: str) -> str:
    """
    Returns the user memory for the given user_id (as JSON string). Only the user can fetch their own memory.
    """
    try:
        parts = user_id.split(":")
        if len(parts) == 2:
            requester_id, target_id = int(parts[0]), int(parts[1])
            if requester_id != target_id:
                return "Error: You can only fetch your own user memory."
            uid = target_id
        else:
            uid = int(user_id)
        mem = memory_manager.user.get_user(uid)
        return json.dumps(mem, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_user_memory error: %s", e)
        return f"Error: {e}"

def tool_add_user_memory(args: str) -> str:
    """
    Adds/updates user memory. args: {"user_id": int, "entry": {"title": str, ...}}
    Appends to 'history' list in user memory.
    """
    try:
        obj = json.loads(args)
        uid = int(obj["user_id"])
        entry = obj["entry"]
        mem = memory_manager.user.get_user(uid)
        history = mem.get("history", [])
        history.append(entry)
        mem["history"] = history
        memory_manager.user.update_user(uid, mem)
        return "User memory entry added."
    except Exception as e:
        logger.exception("add_user_memory error: %s", e)
        return f"Error: {e}"

def tool_get_user_memory_by_title(args: str) -> str:
    """
    Fetch a specific user memory entry by title. args: {"user_id": int, "title": str, "requester_id": int}
    Only the user can fetch their own memory.
    """
    try:
        obj = json.loads(args)
        user_id = int(obj["user_id"])
        requester_id = int(obj["requester_id"])
        title = obj["title"]
        if user_id != requester_id:
            return "Error: You can only fetch your own user memory."
        mem = memory_manager.user.get_user(user_id)
        for entry in mem.get("history", []):
            if entry.get("title") == title:
                return json.dumps(entry, ensure_ascii=False)
        return "Not found."
    except Exception as e:
        logger.exception("get_user_memory_by_title error: %s", e)
        return f"Error: {e}"

# --- Core Memory Tools ---
def tool_add_core_memory(args: str) -> str:
    """
    Adds a new core memory entry. args: {"user_id": int, "content": str, "title": str}
    Only allowed for creator IDs. Appends to existing core memory entries.
    """
    try:
        obj = json.loads(args)
        uid = int(obj["user_id"])
        content = obj["content"]
        title = obj["title"]
        if uid not in CREATOR_IDS:
            return "Error: Only creators can add core memory."
        memory_manager.core.add_core_entry(title, content)
        return "Core memory entry added."
    except Exception as e:
        logger.exception("add_core_memory error: %s", e)
        return f"Error: {e}"

def tool_get_core_memory(args: str) -> str:
    """
    Fetch all core memory. args: {"user_id": int}
    Only allowed for creator IDs.
    """
    try:
        obj = json.loads(args) if args else {}
        uid = int(obj.get("user_id", 0))
        if uid not in CREATOR_IDS:
            return "Error: Only creators can fetch core memory."
        core = memory_manager.core.get_core()
        return core if core else "No core memory found."
    except Exception as e:
        logger.exception("get_core_memory error: %s", e)
        return f"Error: {e}"

def tool_get_core_memory_by_title(args: str) -> str:
    """
    Fetch core memory by title. args: {"user_id": int, "title": str}
    Only allowed for creator IDs.
    """
    try:
        obj = json.loads(args)
        uid = int(obj["user_id"])
        title = obj["title"]
        if uid not in CREATOR_IDS:
            return "Error: Only creators can fetch core memory."
        core = memory_manager.core.get_core()
        try:
            core_obj = json.loads(core)
        except Exception:
            return "Core memory is not structured."
        if core_obj.get("title") == title:
            return json.dumps(core_obj, ensure_ascii=False)
        return "Not found."
    except Exception as e:
        logger.exception("get_core_memory_by_title error: %s", e)
        return f"Error: {e}"

# --- General Memory Tools ---
def tool_add_general_memory(args: str) -> str:
    """
    Adds an entry to general memory (RAG). args: {"user_id": int, "content": str, "title": str, "metadata": dict (optional)}
    All users are allowed. Title is required.
    """
    try:
        obj = json.loads(args)
        content = obj["content"]
        title = obj["title"]
        metadata = obj.get("metadata", {})
        metadata["added_by"] = obj.get("user_id")
        metadata["title"] = title
        memory_manager.general.add_entry(content, metadata)
        return "General memory entry added."
    except Exception as e:
        logger.exception("add_general_memory error: %s", e)
        return f"Error: {e}"

def tool_get_general_memory(query: str) -> str:
    """
    Searches general memory (RAG) for relevant entries. Input is a query string.
    Returns top 5 results as JSON.
    """
    try:
        results = memory_manager.general.search(query, top_k=5)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_general_memory error: %s", e)
        return f"Error: {e}"

def tool_get_general_memory_by_title(title: str) -> str:
    """
    Fetch general memory entries by title. Returns all matches as JSON.
    """
    try:
        results = memory_manager.general.search(title, top_k=10)
        matches = [r for r in results if r.get("metadata", {}).get("title") == title]
        return json.dumps(matches, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_general_memory_by_title error: %s", e)
        return f"Error: {e}"

def tool_get_channel_context(args: str) -> str:
    """
    Get recent channel conversation history. args: {"channel_id": int, "limit": int (optional)}
    """
    try:
        obj = json.loads(args) if args else {}
        channel_id = int(obj.get("channel_id", 0))
        limit = int(obj.get("limit", 20))
        
        if channel_id == 0:
            return "Error: channel_id is required."
        
        context = memory_manager.channel.get_formatted_context(channel_id, limit)
        return context if context else "No conversation history found for this channel."
    except Exception as e:
        logger.exception("get_channel_context error: %s", e)
        return f"Error: {e}"

def tool_search_channel_history(args: str) -> str:
    """
    Search through channel conversation history. args: {"channel_id": int, "query": str, "limit": int (optional)}
    """
    try:
        obj = json.loads(args) if args else {}
        channel_id = int(obj.get("channel_id", 0))
        query = obj.get("query", "")
        limit = int(obj.get("limit", 10))
        
        if channel_id == 0:
            return "Error: channel_id is required."
        if not query:
            return "Error: query is required."
        
        results = memory_manager.channel.search(channel_id, query, limit)
        if not results:
            return f"No messages found matching '{query}' in channel history."
        
        formatted_results = []
        for msg in results:
            author = msg.get("author", "Unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", 0)
            
            if timestamp > 0:
                import datetime
                dt = datetime.datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("%H:%M")
            else:
                time_str = "??:??"
            
            formatted_results.append(f"[{time_str}] {author}: {content}")
        
        return "\n".join(formatted_results)
    except Exception as e:
        logger.exception("search_channel_history error: %s", e)
        return f"Error: {e}"

# --- Other Tools ---
_allowed_operators = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg
}

def tool_web_search(query: str) -> str:
    logger.info("web_search called with query: %s", query)
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return "Error: BRAVE_API_KEY not set. Get one at https://search.brave.com/api."
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": query, "count": 3}
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("web", {}).get("results", [])
        if not results:
            return "No results found."
        out = []
        for r in results:
            out.append(f"{r.get('title')}: {r.get('url')}")
        return "\n".join(out)
    except Exception as e:
        logger.exception("Brave search error: %s", e)
        return f"Error: {e}"

def tool_calculator(expr: str) -> str:
    logger.info("calculator called with expr: %s", expr)
    try:
        node = ast.parse(expr, mode='eval').body
        def _eval(n):
            if isinstance(n, ast.Constant):
                return n.value
            if isinstance(n, ast.BinOp):
                left = _eval(n.left); right = _eval(n.right)
                fn = _allowed_operators.get(type(n.op))
                if fn: return fn(left, right)
            if isinstance(n, ast.UnaryOp):
                val = _eval(n.operand); fn = _allowed_operators.get(type(n.op))
                if fn: return fn(val)
            raise ValueError("Unsupported expression")
        return str(_eval(node))
    except Exception as e:
        logger.exception("Calculator error: %s", e)
        return "Error: invalid arithmetic expression."

def tool_file_store(content: str) -> str:
    logger.info("file_store called (len=%d)", len(content))
    try:
        with open("data_store.txt", "a", encoding="utf-8") as f:
            f.write(content + "\n")
        return "Stored content."
    except Exception as e:
        logger.exception("File store error: %s", e)
        return "Error storing content."

def tool_code_execute(code: str) -> str:
    if not CODE_EXEC_ENABLED:
        return "Error: code execution is disabled by default."
    logger.info("code_execute invoked")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tf:
            tf.write(code)
            tmp_path = tf.name
        start = time.time()
        proc = subprocess.run(["python", tmp_path], capture_output=True, text=True, timeout=5)
        duration = time.time() - start
        logger.info("Code executed in %.2fs", duration)
        return proc.stdout + proc.stderr or "No output."
    except subprocess.TimeoutExpired:
        return "Error: execution timed out."
    except Exception as e:
        logger.exception("Code exec error: %s", e)
        return f"Error: {e}"

TOOLS = {
    "web_search": tool_web_search,
    "brave_search": tool_web_search,  # alias for clarity
    "calculate": tool_calculator,
    "file_store": tool_file_store,
    "code_execute": tool_code_execute,
    "get_user_memory": tool_get_user_memory,
    "add_user_memory": tool_add_user_memory,
    "get_user_memory_by_title": tool_get_user_memory_by_title,
    "add_core_memory": tool_add_core_memory,
    "get_core_memory": tool_get_core_memory,
    "get_core_memory_by_title": tool_get_core_memory_by_title,
    "add_general_memory": tool_add_general_memory,
    "get_general_memory": tool_get_general_memory,
    "get_general_memory_by_title": tool_get_general_memory_by_title,
    "get_channel_context": tool_get_channel_context,
    "search_channel_history": tool_search_channel_history
}
