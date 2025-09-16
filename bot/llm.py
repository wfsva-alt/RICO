# bot/llm.py
# MIT License
import os
import google.generativeai as genai
from bot.logger import logger

# Configure Gemini client
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


class LLMClient:
    def __init__(self, model="gemini-2.5-flash"):
        self.model = model
        self.max_tokens = 500
        self.temperature = 0.7
        self._model = genai.GenerativeModel(model)

    async def moderate(self, text: str) -> bool:
        """
        Gemini does not have a standalone moderation API like OpenAI.
        Here we add a very simple check.
        TODO: For production, integrate a proper content filter or moderation service.
        """
        banned_keywords = ["hack", "malware", "terrorism"]
        for bad in banned_keywords:
            if bad in text.lower():
                logger.warning("Moderation flagged input: contains '%s'", bad)
                return False
        return True

    async def chat(self, messages, **kwargs) -> str:
        """
        Generate a chat response using Gemini.
        `messages` should be a list of {"role": "user"|"assistant"|"system", "content": str}.
        """
        try:
            # Basic moderation on the last user message
            if messages and messages[-1].get("role") == "user":
                allowed = await self.moderate(messages[-1]["content"])
                if not allowed:
                    raise ValueError("User content blocked by moderation.")

            # Build a conversation prompt
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

            response = self._model.generate_content(
                prompt,
                generation_config={
                    "temperature": kwargs.get("temperature", self.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.max_tokens),
                },
            )

            if response and response.text:
                return response.text.strip()
            else:
                logger.error("Empty response from Gemini.")
                return "⚠️ Sorry, I couldn't generate a response."

        except Exception as e:
            logger.exception("LLM chat error: %s", e)
            raise
