# bot/llm.py
import os
import openai
from bot.logger import logger

openai.api_key = os.getenv("OPENAI_API_KEY")

class LLMClient:
    def __init__(self, model="gpt-3.5-turbo"):
        self.model = model
        self.max_tokens = 500
        self.temperature = 0.7

    async def moderate(self, text: str) -> bool:
        try:
            response = await openai.Moderation.acreate(input=text)
            results = response["results"][0]
            # conservative: if any category flagged, treat as unsafe
            flagged = results.get("flagged", False)
            if flagged:
                logger.warning("Moderation flagged input.")
            return not flagged
        except Exception as e:
            logger.exception("Moderation API failed: %s", e)
            return True

    async def chat(self, messages, **kwargs):
        try:
            # Basic moderation on last user message
            if messages and messages[-1].get("role") == "user":
                allowed = await self.moderate(messages[-1]["content"])
                if not allowed:
                    raise ValueError("User content blocked by moderation.")

            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.exception("LLM chat error: %s", e)
            raise
