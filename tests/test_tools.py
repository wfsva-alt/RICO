# tests/test_tools.py
from bot.tools import tool_calculator, tool_web_search, tool_file_store

def test_calculator():
    assert tool_calculator("2+2") == "4"
    assert "Error" in tool_calculator("__import__('os')")

def test_web_search():
    res = tool_web_search("hello")
    assert "Search results" in res

def test_file_store(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.open", lambda f, mode='a', encoding=None: open(tmp_path/"o.txt", mode))
    assert "Stored" in tool_file_store("hi")
