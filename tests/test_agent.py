# tests/test_agent.py
import pytest
from bot.agent import Agent

class Dummy:
    def __init__(self, resp):
        self.resp = resp
    async def chat(self, messages, **kwargs):
        return self.resp

@pytest.mark.asyncio
async def test_agent_plan_and_execute(monkeypatch):
    a = Agent()
    monkeypatch.setattr(a, "llm", Dummy('{"steps":[{"tool":"calculate","input":"3+4"}],"final_prompt":"Compute."}'))
    plan = await a.plan("3+4")
    assert isinstance(plan, dict)
    monkeypatch.setattr(a, "llm", Dummy("The answer is 7."))
    res = await a.execute_plan(plan, "3+4")
    assert "7" in res
