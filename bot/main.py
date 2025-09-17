import functools
# List of creator Discord user IDs
CREATOR_IDS = {756227441432723656, 760498940126298112}
# Start the bot if run as a script

# bot/main.py
# MIT License
import os
import asyncio
import logging
import discord
from bot.logger import logger
from bot.config import DISCORD_TOKEN, ALLOWED_GUILD_IDS, ALLOWED_CHANNEL_IDS
from bot.llm import LLMClient
from bot.memory import short_term, long_term
from bot.agent import Agent

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
agent = Agent()            # uses LLMClient internally
llm_client = LLMClient()   # optional direct use

def is_allowed_channel(message: discord.Message) -> bool:
    # If ALLOWED_GUILD_IDS / CHANNELS are empty, allow all
    if ALLOWED_GUILD_IDS and message.guild and message.guild.id not in ALLOWED_GUILD_IDS:
        return False
    if ALLOWED_CHANNEL_IDS and message.channel.id not in ALLOWED_CHANNEL_IDS:
        return False
    return True

@client.event
async def on_ready():
    logger.info("Bot logged in as %s (id=%s)", client.user.name, client.user.id)
    # Useful: show persona/model loaded
    try:
        logger.info("Active model: %s", agent.llm.model)
    except Exception:
        pass

@client.event
async def on_message(message: discord.Message):
    # Ignore bot messages
    if message.author.bot:
        return

    # Check permissions / allowed servers/channels
    if not is_allowed_channel(message):
        # Optionally send ephemeral or nothing; keep it simple
        try:
            await message.channel.send("This server/channel is not allowed.")
        except Exception:
            pass
        return

    content = (message.content or "").strip()

    # Respond if the bot is mentioned anywhere in the message
    if client.user in message.mentions:
        # Remove the mention(s) from the content to get the user query
        query = content
        for mention in message.mentions:
            mention_str = f"<@{mention.id}>"
            query = query.replace(mention_str, "").strip()
        if not query:
            await message.channel.send("Yes? Ask me something after the mention.")
            return
        async with message.channel.typing():
            try:
                respectful = message.author.id in CREATOR_IDS
                # Decide: direct chat or agent? use a prefix "agent:" or let planner decide
                if query.lower().startswith("agent:") or query.lower().startswith("use tools"):
                    # strip prefix
                    q = query.split(":", 1)[-1].strip() if ":" in query else query
                    # Add timeout for agent tool calls
                    answer = await asyncio.wait_for(agent.run_agent(q, user_id=message.author.id), timeout=30)
                else:
                    # default: simple chat (keeps short-term memory)
                    # build history from short-term memory
                    short_term.add_message(message.author.id, f"User: {query}")
                    history = []
                    for msg in short_term.get_messages(message.author.id)[-10:]:
                        history.append({"role": "user", "content": msg})
                    # Limit LLM response length and add timeout
                    answer = await asyncio.wait_for(
                        llm_client.chat(history + [{"role":"user","content": query}], max_tokens=1000),
                        timeout=30
                    )
                    short_term.add_message(message.author.id, f"Assistant: {answer}")
                if respectful:
                    answer = f"Respected creator {message.author.display_name}, {answer}"
                # Always mention the user in the reply
                mention = message.author.mention
                answer = f"{mention} {answer}"
            except asyncio.TimeoutError:
                answer = "Error: LLM or tool timed out. Please try again."
            except Exception as e:
                logger.exception("Error handling mention: %s", e)
                answer = "Error: something went wrong while processing your request."
            # Send long replies in multiple messages (Discord limit: 2000 chars)
            while answer:
                chunk = answer[:2000]
                await message.channel.send(chunk)
                answer = answer[2000:]
                if answer:
                    await asyncio.sleep(0.5)
            return

    # Case 2: DM (private message)
    if isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            query = content
            try:
                # Decide chat vs agent via prefix in DM: agent: ...
                if query.lower().startswith("agent:"):
                    q = query.split(":", 1)[-1].strip()
                    answer = await asyncio.wait_for(agent.run_agent(q, user_id=message.author.id), timeout=30)
                else:
                    # standard chat
                    short_term.add_message(message.author.id, f"User: {query}")
                    history = []
                    for msg in short_term.get_messages(message.author.id)[-10:]:
                        history.append({"role": "user", "content": msg})
                    answer = await asyncio.wait_for(
                        llm_client.chat(history + [{"role":"user","content": query}], max_tokens=1000),
                        timeout=30
                    )
                    short_term.add_message(message.author.id, f"Assistant: {answer}")
            except asyncio.TimeoutError:
                answer = "Error: LLM or tool timed out. Please try again."
            except Exception as e:
                logger.exception("Error in DM flow: %s", e)
                answer = "Error: could not process your DM."
            while answer:
                chunk = answer[:2000]
                await message.channel.send(chunk)
                answer = answer[2000:]
                if answer:
                    await asyncio.sleep(0.5)
            return


# Start the bot if run as a script (must be at the end)
if __name__ == "__main__":
    client.run(DISCORD_TOKEN)

    # Otherwise ignore or implement prefix commands (optional)
    # e.g., messages starting with "!ask" can be supported if you want legacy behavior