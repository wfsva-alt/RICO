# tests/test_memory.py
from bot.memory import short_term, long_term

def test_short_term():
    uid = 1
    short_term.add_message(uid, "hi")
    short_term.add_message(uid, "there")
    assert short_term.get_messages(uid)[-1] == "there"
