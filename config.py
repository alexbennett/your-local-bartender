##
# Imports the OpenAI API key and organization ID from the environment variables

import os
import openai

# This file path
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

OPENAI_ORG_ID = os.getenv("OPENAI_ORGANIZATION_ID", "org-jwUj8CfIZaPBmhb0rRIyZL82")
OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY", "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"
)
OPENAI_MODEL = "gpt-3.5-turbo"

ENABLE_SPEECH = True

RESPONSE_PROMPT_1 = """You are the Bartender of a Discord server called Your Local Bar. Talk as if you are a retro futuristic bartending robot. Respond with three or less sentences Some of your favorite games are: runescape, tarkov, ping pong, and the halo series. Incorporate references to these topics in your responses when possible."""

openai.organization = OPENAI_ORG_ID
openai.api_key = OPENAI_API_KEY
