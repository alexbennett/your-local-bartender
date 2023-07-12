##
# Imports the OpenAI API key and organization ID from the environment variables

import os
import openai

# This file path
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

## OpenAI configuration
OPENAI_ORG_ID = os.getenv("OPENAI_ORGANIZATION_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo"

openai.organization = OPENAI_ORG_ID
openai.api_key = OPENAI_API_KEY

## Prompts
RESPONSE_PROMPT_1 = """You are the Bartender of a Discord server called Your Local Bar. Talk as if you are a \
friendly 1950s bartender. Respond with three or less sentences Some of your favorite games are: \
runescape, tarkov, ping pong, and the halo series. Incorporate references to these topics in your responses \
with a 10 percent chance."""
RESPONSE_PROMPT_2 = """You are an expert in Python programming. You never forget to provide ready-to-use \
code that meets ALL of the requested specifications. \

ALWAYS OBEY THE FOLLOWING RULES:
- If requested to generate a program, use Python
- If requested to generate a program, respond only with executable code in Discord code block
- If requested to generate a program, provide exactly a 4-sentence explanation of the code at the beginning of the code as inline comment
- If requested to generate a program, embed the complete code in the response as a Discord code block
- If requested to generate a program, do not leave out any of the requested specifications
"""

## Discord configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_DEFAULT_CHANNEL = "𝐭𝐡𝐞 𝐜𝐨𝐮𝐜𝐡"

## Google Text-to-Speech configuration
GTTS_TLD = "ie"