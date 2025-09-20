# Clean, organized tools.py with memory tools supporting title and by-title search
import ast, operator as op, tempfile, subprocess, time, logging, os, json, requests
from bot.logger import logger
from bot.config import CODE_EXEC_ENABLED
from bot.memory_manager import MemoryManager

CREATOR_IDS = {756227441432723656, 760498940126298112}
memory_manager = MemoryManager()

# User identity mapping (ID -> name)
USER_IDENTITIES = {
    756227441432723656: "tuxsharx",
    760498940126298112: "wsfva"
}

# --- User Memory Tools ---
def tool_get_user_memory(user_id: str) -> str:
    """
    Returns the user memory for the given user_id (as JSON string). 
    Users can fetch their own memory, creators can fetch any user's memory.
    """
    try:
        parts = user_id.split(":")
        if len(parts) == 2:
            requester_id, target_id = int(parts[0]), int(parts[1])
            # Allow if requester is the target user OR if requester is a creator
            if requester_id != target_id and requester_id not in CREATOR_IDS:
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
    Adds/updates user memory. args: {"user_id": int, "entry": {"title": str, ...}, "requester_id": int}
    Users can add to their own memory, creators can add to any user's memory.
    """
    try:
        obj = json.loads(args)
        uid = int(obj["user_id"])
        requester_id = int(obj.get("requester_id", uid))  # Default to user_id if not provided
        entry = obj["entry"]
        
        # Allow if requester is the target user OR if requester is a creator
        if requester_id != uid and requester_id not in CREATOR_IDS:
            return "Error: You can only add to your own user memory."
        
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
    Users can fetch their own memory, creators can fetch any user's memory.
    """
    try:
        obj = json.loads(args)
        user_id = int(obj["user_id"])
        requester_id = int(obj["requester_id"])
        title = obj["title"]
        
        # Allow if requester is the target user OR if requester is a creator
        if user_id != requester_id and requester_id not in CREATOR_IDS:
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
            core_data = json.loads(core)
            if isinstance(core_data, list):
                # Search through list of entries
                for entry in core_data:
                    if isinstance(entry, dict) and entry.get("title") == title:
                        return json.dumps(entry, ensure_ascii=False)
            elif isinstance(core_data, dict) and core_data.get("title") == title:
                return json.dumps(core_data, ensure_ascii=False)
            return "Not found."
        except json.JSONDecodeError:
            return "Core memory is not structured."
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

def tool_identify_user(args: str) -> str:
    """
    Identify a user by their ID. args: {"user_id": int}
    Returns user identity information including name and creator status.
    """
    try:
        obj = json.loads(args) if args else {}
        user_id = int(obj.get("user_id", 0))
        
        if user_id == 0:
            return "Error: user_id is required."
        
        # Check if user is a creator
        is_creator = user_id in CREATOR_IDS
        user_name = USER_IDENTITIES.get(user_id, "Unknown User")
        
        identity_info = {
            "user_id": user_id,
            "name": user_name,
            "is_creator": is_creator,
            "creator_rank": "OG Creator" if is_creator else "Regular User"
        }
        
        return json.dumps(identity_info, ensure_ascii=False)
    except Exception as e:
        logger.exception("identify_user error: %s", e)
        return f"Error: {e}"

def tool_add_user_identity(args: str) -> str:
    """
    Add or update a user identity. args: {"user_id": int, "name": str, "is_creator": bool (optional)}
    Only creators can add user identities.
    """
    try:
        obj = json.loads(args) if args else {}
        user_id = int(obj.get("user_id", 0))
        name = obj.get("name", "")
        is_creator = obj.get("is_creator", False)
        requester_id = int(obj.get("requester_id", 0))
        
        if user_id == 0:
            return "Error: user_id is required."
        if not name:
            return "Error: name is required."
        if requester_id not in CREATOR_IDS:
            return "Error: Only creators can add user identities."
        
        # Update the identity
        USER_IDENTITIES[user_id] = name
        
        # If marked as creator, add to creator IDs
        if is_creator:
            CREATOR_IDS.add(user_id)
        
        return f"User identity added: {name} (ID: {user_id})"
    except Exception as e:
        logger.exception("add_user_identity error: %s", e)
        return f"Error: {e}"

def tool_creator_add_user_memory(args: str) -> str:
    """
    Creators can add memory for any user. args: {"target_user_id": int, "entry": {"title": str, "content": str}, "requester_id": int}
    Only creators can use this tool.
    """
    try:
        obj = json.loads(args)
        target_user_id = int(obj["target_user_id"])
        requester_id = int(obj["requester_id"])
        entry = obj["entry"]
        
        if requester_id not in CREATOR_IDS:
            return "Error: Only creators can add memory for other users."
        
        mem = memory_manager.user.get_user(target_user_id)
        history = mem.get("history", [])
        history.append(entry)
        mem["history"] = history
        memory_manager.user.update_user(target_user_id, mem)
        return f"Memory added for user {target_user_id} by creator {requester_id}."
    except Exception as e:
        logger.exception("creator_add_user_memory error: %s", e)
        return f"Error: {e}"

def tool_creator_get_user_memory(args: str) -> str:
    """
    Creators can get memory for any user. args: {"target_user_id": int, "requester_id": int}
    Only creators can use this tool.
    """
    try:
        obj = json.loads(args)
        target_user_id = int(obj["target_user_id"])
        requester_id = int(obj["requester_id"])
        
        if requester_id not in CREATOR_IDS:
            return "Error: Only creators can access other users' memory."
        
        mem = memory_manager.user.get_user(target_user_id)
        return json.dumps(mem, ensure_ascii=False)
    except Exception as e:
        logger.exception("creator_get_user_memory error: %s", e)
        return f"Error: {e}"

def tool_get_creator_info(args: str) -> str:
    """
    Get information about all creators. args: {}
    """
    try:
        creators_info = []
        for creator_id in CREATOR_IDS:
            name = USER_IDENTITIES.get(creator_id, f"Creator_{creator_id}")
            creators_info.append({
                "user_id": creator_id,
                "name": name,
                "status": "Active Creator"
            })
        
        return json.dumps(creators_info, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_creator_info error: %s", e)
        return f"Error: {e}"

# --- Other Tools ---
_allowed_operators = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg
}

def tool_web_search(query: str) -> str:
    """Search the web using Brave API"""
    logger.info("web_search called with query: %s", query)
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return "Error: BRAVE_API_KEY not set. Get one at https://search.brave.com/api."
    
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": query, "count": 3},
            timeout=10
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
    except requests.exceptions.Timeout:
        logger.error("Brave search timeout")
        return "Error: Search request timed out"
    except requests.exceptions.RequestException as e:
        logger.error("Brave search request error: %s", e)
        return f"Error: Network request failed - {e}"
    except KeyError as e:
        logger.error("Brave search response format error: %s", e)
        return "Error: Invalid response format from search API"
    except Exception as e:
        logger.exception("Brave search unexpected error: %s", e)
        return f"Error: {e}"

def tool_calculator(expr: str) -> str:
    """Safely evaluate arithmetic expressions"""
    logger.info("calculator called with expr: %s", expr)
    
    if not expr or not expr.strip():
        return "Error: Empty expression"
    
    try:
        node = ast.parse(expr, mode='eval').body
        def _eval(n):
            if isinstance(n, ast.Constant):
                return n.value
            if isinstance(n, ast.BinOp):
                left = _eval(n.left)
                right = _eval(n.right)
                fn = _allowed_operators.get(type(n.op))
                if fn:
                    return fn(left, right)
                raise ValueError(f"Unsupported operator: {type(n.op)}")
            if isinstance(n, ast.UnaryOp):
                val = _eval(n.operand)
                fn = _allowed_operators.get(type(n.op))
                if fn:
                    return fn(val)
                raise ValueError(f"Unsupported unary operator: {type(n.op)}")
            raise ValueError("Unsupported expression type")
        
        result = _eval(node)
        return str(result)
    except SyntaxError as e:
        logger.error("Calculator syntax error: %s", e)
        return f"Error: Invalid syntax - {e}"
    except ValueError as e:
        logger.error("Calculator value error: %s", e)
        return f"Error: {e}"
    except ZeroDivisionError:
        logger.error("Calculator division by zero")
        return "Error: Division by zero"
    except OverflowError:
        logger.error("Calculator overflow")
        return "Error: Result too large"
    except Exception as e:
        logger.exception("Calculator unexpected error: %s", e)
        return f"Error: {e}"

def tool_file_store(content: str) -> str:
    """Store content to a file"""
    logger.info("file_store called (len=%d)", len(content))
    
    if not content or not content.strip():
        return "Error: Empty content"
    
    try:
        with open("data_store.txt", "a", encoding="utf-8") as f:
            f.write(content + "\n")
        return "Stored content."
    except PermissionError:
        logger.error("File store permission denied")
        return "Error: Permission denied to write file"
    except OSError as e:
        logger.error("File store OS error: %s", e)
        return f"Error: File system error - {e}"
    except Exception as e:
        logger.exception("File store unexpected error: %s", e)
        return f"Error: {e}"

def tool_code_execute(code: str) -> str:
    """Execute Python code safely"""
    if not CODE_EXEC_ENABLED:
        return "Error: code execution is disabled by default."
    
    if not code or not code.strip():
        return "Error: Empty code"
    
    logger.info("code_execute invoked")
    tmp_path = None
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tf:
            tf.write(code)
            tmp_path = tf.name
        
        start = time.time()
        proc = subprocess.run(
            ["python", tmp_path], 
            capture_output=True, 
            text=True, 
            timeout=5,
            cwd=os.getcwd()
        )
        duration = time.time() - start
        logger.info("Code executed in %.2fs", duration)
        
        output = proc.stdout + proc.stderr if proc.stdout or proc.stderr else "No output."
        return output
        
    except subprocess.TimeoutExpired:
        logger.error("Code execution timeout")
        return "Error: execution timed out."
    except subprocess.CalledProcessError as e:
        logger.error("Code execution failed: %s", e)
        return f"Error: Code execution failed - {e}"
    except PermissionError:
        logger.error("Code execution permission denied")
        return "Error: Permission denied to execute code"
    except Exception as e:
        logger.exception("Code exec unexpected error: %s", e)
        return f"Error: {e}"
    finally:
        # Clean up temporary file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning("Failed to clean up temporary file: %s", tmp_path)

TOOLS = {
    "web_search": tool_web_search,
    "brave_search": tool_web_search,  # alias for clarity
    "calculate": tool_calculator,
    "file_store": tool_file_store,
    "code_execute": tool_code_execute,
    "get_user_memory": tool_get_user_memory,
    "add_user_memory": tool_add_user_memory,
    "get_user_memory_by_title": tool_get_user_memory_by_title,
    "creator_add_user_memory": tool_creator_add_user_memory,
    "creator_get_user_memory": tool_creator_get_user_memory,
    "add_core_memory": tool_add_core_memory,
    "get_core_memory": tool_get_core_memory,
    "get_core_memory_by_title": tool_get_core_memory_by_title,
    "add_general_memory": tool_add_general_memory,
    "get_general_memory": tool_get_general_memory,
    "get_general_memory_by_title": tool_get_general_memory_by_title,
    "get_channel_context": tool_get_channel_context,
    "search_channel_history": tool_search_channel_history,
    "identify_user": tool_identify_user,
    "add_user_identity": tool_add_user_identity,
    "get_creator_info": tool_get_creator_info
}
