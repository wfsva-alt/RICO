# bot/agent.py
import json
from bot.llm import LLMClient
from bot.tools import TOOLS, CREATOR_IDS
from bot.logger import logger

import re

class Agent:
    def __init__(self):
        self.llm = LLMClient()
        self.system_prompt = (
            "You are an autonomous agent. You MUST respond with valid JSON in this exact format:\n"
            "{\n"
            '  "steps": [\n'
            '    {"tool": "tool_name", "input": "tool_input"},\n'
            '    {"tool": "another_tool", "input": "another_input"}\n'
            '  ],\n'
            '  "final_prompt": "Your response to the user"\n'
            "}\n\n"
            "Available tools: add_core_memory, get_core_memory, add_general_memory, get_general_memory, add_user_memory, get_user_memory, get_channel_context, search_channel_history, web_search, calculate, file_store, code_execute\n"
            "For memory tools, use JSON format for input: {\"user_id\": 123, \"title\": \"title\", \"content\": \"content\"}\n"
            "IMPORTANT: Do NOT call the same tool multiple times. Each tool should be called only once per request.\n"
            "If no tools are needed, return: {\"steps\": [], \"final_prompt\": \"Your response\"}\n"
            "ALWAYS respond with valid JSON only, no other text."
        )

    def _extract_title(self, text: str) -> str:
        # Use first 5 words or a keyword as a fallback title
        text = text.strip()
        if not text:
            return "untitled"
        # Try to extract a quoted title
        m = re.search(r'"([^"]{3,40})"', text)
        if m:
            return m.group(1)
        # Otherwise, use first 5 words
        return " ".join(text.split()[:5])

    def _preprocess_tool_args(self, tool_name, user_id, prompt):
        # For memory tools, auto-generate required JSON
        title = self._extract_title(prompt)
        if tool_name == "add_core_memory":
            return json.dumps({"user_id": user_id, "title": title, "content": prompt})
        if tool_name == "add_general_memory":
            return json.dumps({"user_id": user_id, "title": title, "content": prompt})
        if tool_name == "add_user_memory":
            return json.dumps({"user_id": user_id, "entry": {"title": title, "content": prompt}})
        if tool_name == "get_user_memory_by_title":
            return json.dumps({"user_id": user_id, "requester_id": user_id, "title": title})
        if tool_name == "get_core_memory_by_title":
            return json.dumps({"user_id": user_id, "title": title})
        if tool_name == "get_core_memory":
            return json.dumps({"user_id": user_id})
        if tool_name == "get_channel_context":
            # Use the channel_id passed from Discord context
            channel_id = getattr(self, '_current_channel_id', 0)
            return json.dumps({"channel_id": channel_id, "limit": 20})
        if tool_name == "search_channel_history":
            channel_id = getattr(self, '_current_channel_id', 0)
            return json.dumps({"channel_id": channel_id, "query": prompt, "limit": 10})
        if tool_name == "get_general_memory_by_title":
            return title
        return prompt

    async def plan(self, user_query: str, user_id: int = None) -> dict:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"User query: {user_query}\nPlease provide a JSON plan."}
        ]
        response = await self.llm.chat(messages)
        logger.debug("Planner raw response: %s", response)
        try:
            # Try to extract JSON from the response (in case LLM adds extra text)
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            # Try to find JSON object in the response
            start_idx = response_clean.find('{')
            end_idx = response_clean.rfind('}')
            if start_idx != -1 and end_idx != -1:
                response_clean = response_clean[start_idx:end_idx+1]
            
            plan = json.loads(response_clean)
            # Note: Tool preprocessing will happen in execute_plan where channel_id is available
            return plan
        except Exception as e:
            logger.exception("Planner returned invalid JSON: %s", e)
            logger.debug("Raw response was: %s", response)
            return {"steps": [], "final_prompt": user_query}

    async def execute_plan(self, plan: dict, user_query: str, user_id: int = None, channel_id: int = None) -> str:
        # Store channel_id for use in tool preprocessing
        self._current_channel_id = channel_id
        logger.debug(f"Agent execute_plan - channel_id: {channel_id}")
        
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
                # If tool_input is not JSON and tool expects JSON, preprocess
                if user_id is not None and tool_name in [
                    "add_core_memory", "add_general_memory", "add_user_memory",
                    "get_user_memory_by_title", "get_core_memory_by_title", "get_general_memory_by_title", "get_core_memory",
                    "get_channel_context", "search_channel_history"
                ]:
                    tool_input = self._preprocess_tool_args(tool_name, user_id, user_query)
                out = fn(tool_input)
                outputs.append(f"{tool_name}({tool_input}) -> {out}")
            except Exception as e:
                outputs.append(f"{tool_name} error: {e}")
            calls += 1

        # Always search memory for relevant info and include in answer
        memory_snippets = []
        # Core memory (if creator)
        if user_id in CREATOR_IDS:
            from bot.tools import tool_get_core_memory
            core = tool_get_core_memory(json.dumps({"user_id": user_id}))
            if core and core != "No core memory found.":
                memory_snippets.append(f"[Core Memory: {core}]")
        # General memory
        from bot.tools import tool_get_general_memory_by_title
        title = self._extract_title(user_query)
        general = tool_get_general_memory_by_title(title)
        if general and general != "[]":
            memory_snippets.append(f"[General Memory: {general}]")
        # User memory (self)
        from bot.tools import tool_get_user_memory_by_title
        user_mem = tool_get_user_memory_by_title(json.dumps({"user_id": user_id, "requester_id": user_id, "title": title}))
        if user_mem and user_mem != "Not found.":
            memory_snippets.append(f"[User Memory: {user_mem}]")

        final_prompt = plan.get("final_prompt", user_query)
        final_messages = [
            {"role": "system", "content": "You are an assistant that uses tool outputs and memory to answer clearly."},
            {"role": "user", "content": final_prompt + "\n\nTool outputs:\n" + "\n".join(outputs) + ("\n\n" + "\n".join(memory_snippets) if memory_snippets else "")}
        ]
        return await self.llm.chat(final_messages)

    async def run_agent(self, user_query: str, user_id: int = None, channel_id: int = None) -> str:
        """Main agent entry point that plans and executes tools."""
        try:
            # Create a plan
            plan = await self.plan(user_query, user_id)
            logger.info(f"Agent plan: {plan}")
            
            # Execute the plan
            result = await self.execute_plan(plan, user_query, user_id, channel_id)
            return result
        except Exception as e:
            logger.exception("Agent execution error: %s", e)
            return f"Error: {e}"
