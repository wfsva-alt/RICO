# bot/tools.py
import ast, operator as op, tempfile, subprocess, time, logging
from bot.logger import logger
from bot.config import CODE_EXEC_ENABLED

# Allowed operators for calculator
_allowed_operators = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg
}

def tool_web_search(query: str) -> str:
    logger.info("web_search called with query: %s", query)
    # Placeholder: integrate a real web search (SerpAPI/Bing/Google) by replacing below
    return f"Search results (stub) for '{query}'."

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
    "calculate": tool_calculator,
    "file_store": tool_file_store,
    "code_execute": tool_code_execute
}
