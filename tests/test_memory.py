# tests/test_memory.py
<<<<<<< HEAD

from bot.memory_manager import MemoryManager

def test_channel_context_add_and_get():
    mm = MemoryManager()
    channel_id = 123
    mm.channel.add_message(channel_id, "hi")
    mm.channel.add_message(channel_id, "there")
    recent = mm.channel.get_recent(channel_id, limit=2)
    assert recent[0] == "there"
    assert recent[1] == "hi"
=======
from bot.memory import short_term, long_term
>>>>>>> origin/main

def test_short_term():
    uid = 1
    short_term.add_message(uid, "hi")
    short_term.add_message(uid, "there")
    assert short_term.get_messages(uid)[-1] == "there"
