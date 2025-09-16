# bot/agent.py
import json
from bot.llm import LLMClient
from bot.tools import TOOLS
from bot.logger import logger

class Agent:
    def __init__(self):
        self.llm = LLMClient()
        self.system_prompt = (
            "You are an autonomous agent. Produce a JSON plan with 'steps' where each step includes 'tool' and 'input'. "
            "Also include an optional 'final_prompt' to craft the final answer."
        )

    async def plan(self, user_query: str) -> dict:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"User query: {user_query}\nPlease provide a JSON plan."}
        ]
        response = await self.llm.chat(messages)
        logger.debug("Planner raw response: %s", response)
        try:
            plan = json.loads(response)
            return plan
        except Exception:
            logger.exception("Planner returned invalid JSON.")
            return {"steps": [], "final_prompt": user_query}

    async def execute_plan(self, plan: dict, user_query: str) -> str:
        outputs = []
        max_tool_calls = 5
        calls = 0
        for step in plan.get("steps", []):
            if calls >= max_tool_calls:
                outputs.append("[Tool call limit reached]")
                break
            tool_name = step.get("tool")
            tool_input = step.get("input", "")
            fn = TOOLS.get(tool_name)
            if not fn:
                outputs.append(f"[Unknown tool: {tool_name}]")
                continue
            try:
                out = fn(tool_input)
                outputs.append(f"{tool_name}({tool_input}) -> {out}")
            except Exception as e:
                outputs.append(f"{tool_name} error: {e}")
            calls += 1

        final_prompt = plan.get("final_prompt", user_query)
        final_messages = [
            {"role": "system", "content": "You are an assistant that uses tool outputs to answer clearly."},
            {"role": "user", "content": final_prompt + "\n\nTool outputs:\n" + "\n".join(outputs)}
        ]
        return await self.llm.chat(final_messages)
