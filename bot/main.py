# bot/main.py
import os, asyncio
import discord
from discord import app_commands
from bot.config import DISCORD_TOKEN, ALLOWED_GUILD_IDS, ALLOWED_CHANNEL_IDS
from bot.llm import LLMClient
from bot.memory import short_term, long_term
from bot.agent import Agent
from bot.logger import logger

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
llm = LLMClient()
agent = Agent()

def is_allowed(interaction: discord.Interaction) -> bool:
    if ALLOWED_GUILD_IDS and interaction.guild_id not in ALLOWED_GUILD_IDS:
        return False
    if ALLOWED_CHANNEL_IDS and interaction.channel_id not in ALLOWED_CHANNEL_IDS:
        return False
    return True

@client.event
async def on_ready():
    await tree.sync()
    logger.info("Logged in as %s (ID: %s)", client.user.name, client.user.id)

@tree.command(name="ask", description="Ask the AI bot a question (normal chat).")
async def ask(interaction: discord.Interaction, question: str):
    if not is_allowed(interaction):
        await interaction.response.send_message("This server/channel is not allowed.", ephemeral=True); return
    await interaction.response.defer()
    user_id = interaction.user.id
    short_term.add_message(user_id, question)

    messages = [{"role":"system","content":"You are a helpful assistant."}]
    for m in short_term.get_messages(user_id):
        messages.append({"role":"user","content": m})
    messages.append({"role":"user","content": question})

    try:
        reply = await llm.chat(messages)
    except Exception:
        reply = "Error: LLM currently unavailable."
    short_term.add_message(user_id, reply)
    await interaction.followup.send(reply)

@tree.command(name="ask_agent", description="Ask the agent to plan and use tools.")
async def ask_agent(interaction: discord.Interaction, query: str):
    if not is_allowed(interaction):
        await interaction.response.send_message("This server/channel is not allowed.", ephemeral=True); return
    await interaction.response.defer()
    user_id = interaction.user.id
    try:
        plan = await agent.plan(query)
        answer = await agent.execute_plan(plan, query)
    except Exception as e:
        logger.exception("Agent failed: %s", e)
        answer = "Error: Agent failed to complete the request."
    short_term.add_message(user_id, query)
    short_term.add_message(user_id, answer)
    await interaction.followup.send(answer)

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if isinstance(message.channel, discord.DMChannel):
        user_id = message.author.id
        short_term.add_message(user_id, message.content)
        messages = [{"role":"system","content":"You are a helpful assistant."}]
        for m in short_term.get_messages(user_id):
            messages.append({"role":"user","content": m})
        try:
            reply = await llm.chat(messages)
        except Exception:
            reply = "Error: LLM currently unavailable."
        short_term.add_message(user_id, reply)
        await message.channel.send(reply)

if __name__ == "__main__":
    if not DISCORD_TOKEN or not os.getenv("GEMINI_API_KEY"):
        logger.error("Missing DISCORD_TOKEN or GEMINI_API_KEY in environment.")
    else:
        client.run(DISCORD_TOKEN)
