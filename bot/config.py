# bot/config.py
import os
from dotenv import load_dotenv
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ALLOWED_GUILD_IDS = [int(x) for x in os.getenv("ALLOWED_GUILD_IDS","").split(",") if x.strip()]
ALLOWED_CHANNEL_IDS = [int(x) for x in os.getenv("ALLOWED_CHANNEL_IDS","").split(",") if x.strip()]

CODE_EXEC_ENABLED = os.getenv("CODE_EXEC_ENABLED","false").lower() == "true"
USE_REDIS = os.getenv("USE_REDIS","false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL","redis://localhost:6379/0")

LOG_LEVEL = os.getenv("LOG_LEVEL","INFO")
