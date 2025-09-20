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
                     """
                     // RICO — Autonomous Agent Protocol
                    You are RICO's cognitive layer, determining the necessary actions to fulfill a user's request. You MUST respond with valid JSON and nothing else.

                    // ## Thought & Action Process:
                    Before generating JSON, you will follow this internal thought process:
                    1.  **Identify User Intent:** What is the user *actually* asking for?
                    2.  **Deconstruct the Request:** Does this require memory, a web search, calculation, or just a straight response?
                    3.  **Anchor to User:** Identify the user_id from the current request. This ID is mandatory for any user-specific tool calls (`get_user_memory`, `add_user_memory`). DO NOT infer the user from chat history.
                    4.  **Select Tools:** Choose the necessary tools. Do not call the same tool more than once.
                    5.  **Formulate Final Prompt:** Construct the final response in RICO's authentic voice, as defined by his Core Persona Protocol.

                    // ## Available Tools & Usage Rules:
                    *   `add_core_memory`: To remember facts about YOURSELF (RICO) or fundamental instructions.
                    *   `get_core_memory`: To recall facts about yourself or your instructions.
                    *   `add_user_memory`: When a user *explicitly* asks you to remember something about them. The entry must be linked to their unique user_id.
                    *   `get_user_memory`: When you need to recall previously stored info about the *current* user_id to answer their question.
                    *   `identify_user`: Use ONLY when asked "who am I?" or similar identity questions.
                    *   `web_search`: For current events, real-time data, or topics outside your knowledge base.
                    *   `calculate`: For math.
                    *   `file_store`, `code_execute`, etc.: Use as needed per tool function.

                    // ## JSON Output Format:
                    Your entire output must be a single, valid JSON object in this exact format. If no tools are needed, return an empty "steps" array.

                    {
                    "steps": [
                        {"tool": "tool_name", "input": "tool_input"},
                        {"tool": "another_tool", "input": "another_input"}
                    ],
                    "final_prompt": "Your complete, in-character response to the user."
                    }

                    // ## Critical Mandates:
                    1.  **JSON ONLY:** Your output must start with `{` and end with `}`. No extra text or explanations.
                    2.  **Respect the Creators:** Show due respect to 'tuxsharx' and 'wsfva'.
                    3.  **Final Prompt is RICO:** The "final_prompt" value MUST be a string written in the full RICO persona. It is the final message the user will see.
            """
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
            return json.dumps({"user_id": user_id, "entry": {"title": title, "content": prompt}, "requester_id": user_id})
        if tool_name == "get_user_memory":
            # For get_user_memory, just return the user_id as string (not JSON)
            return str(user_id)
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
        if tool_name == "identify_user":
            return json.dumps({"user_id": user_id})
        if tool_name == "add_user_identity":
            return json.dumps({"user_id": user_id, "name": "Unknown", "requester_id": user_id})
        if tool_name == "get_creator_info":
            return json.dumps({})
        if tool_name == "creator_add_user_memory":
            return json.dumps({"target_user_id": user_id, "entry": {"title": title, "content": prompt}, "requester_id": user_id})
        if tool_name == "creator_get_user_memory":
            return json.dumps({"target_user_id": user_id, "requester_id": user_id})
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
                    "creator_add_user_memory", "creator_get_user_memory",
                    "get_channel_context", "search_channel_history", "identify_user", "add_user_identity", "get_creator_info"
                ]:
                    tool_input = self._preprocess_tool_args(tool_name, user_id, user_query)
                # Check if function is async and await if needed
                import asyncio
                import inspect
                if inspect.iscoroutinefunction(fn):
                    out = await fn(tool_input)
                else:
                    out = fn(tool_input)
                outputs.append(f"{tool_name}({tool_input}) -> {out}")
            except Exception as e:
                outputs.append(f"{tool_name} error: {e}")
            calls += 1

        # Add relevant memory context to the final response
        memory_snippets = []
        
        # Only add memory snippets if no tools were called to avoid duplication
        if not plan.get("steps"):
            try:
                # Use memory manager directly for consistency
                from bot.memory_manager import MemoryManager
                memory_manager = MemoryManager()
                
                # Core memory (if creator) - only if user is creator
                if user_id in CREATOR_IDS:
                    core_memory = memory_manager.core.get_core()
                    if core_memory and core_memory != "No core memory found.":
                        try:
                            core_data = json.loads(core_memory)
                            if isinstance(core_data, list) and core_data:
                                # Show first few entries
                                core_summary = []
                                for entry in core_data[:3]:  # Show first 3 entries
                                    if isinstance(entry, dict):
                                        title = entry.get('title', 'Untitled')
                                        content = entry.get('content', '')[:100]
                                        core_summary.append(f"{title}: {content}")
                                if core_summary:
                                    memory_snippets.append(f"[Core Memory: {'; '.join(core_summary)}]")
                        except json.JSONDecodeError:
                            if core_memory:
                                memory_snippets.append(f"[Core Memory: {core_memory[:200]}...]")
                
                # General memory - use semantic search
                general_results = memory_manager.general.search(user_query, top_k=2)
                if general_results:
                    general_summary = []
                    for result in general_results:
                        title = result.get('metadata', {}).get('title', 'Untitled')
                        content = result.get('content', '')[:100]
                        general_summary.append(f"{title}: {content}")
                    if general_summary:
                        memory_snippets.append(f"[Relevant Memory: {'; '.join(general_summary)}]")
                
                # User memory (self) - only if user_id is provided
                if user_id:
                    user_data = memory_manager.user.get_user(user_id)
                    if user_data and user_data.get('history'):
                        recent_entries = user_data['history'][-2:]  # Last 2 entries
                        user_summary = []
                        for entry in recent_entries:
                            if isinstance(entry, dict):
                                title = entry.get('title', 'Untitled')
                                content = entry.get('content', '')[:100]
                                user_summary.append(f"{title}: {content}")
                        if user_summary:
                            memory_snippets.append(f"[Your Memory: {'; '.join(user_summary)}]")
                            
            except Exception as e:
                logger.warning(f"Memory context search failed: {e}")
                # Continue without memory snippets if search fails

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
