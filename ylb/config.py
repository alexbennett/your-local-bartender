import os
import yaml
import logging

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

# This file path
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

# Get version number
VERSION_FILE = open(os.path.join(__location__, "../VERSION"))
VERSION = VERSION_FILE.read().strip()

###################
## Setup Logging ##
###################

# Configure logging
logging.basicConfig(
    # filename="gps-toolkit-log.log",
    # filemode="a",
    level=logging.WARN,
    format=f"[%(asctime)s][%(filename)s:%(lineno)s->%(funcName)s()][%(levelname)s] %(message)s",
)

#############
## OpenAPI ##
#############

ENABLE_SWAGGER = os.environ.get("ENABLE_SWAGGER", True)
openapi_yaml = os.path.join(__location__, "../openapi.yaml")

########################
## Grab Configuration ##
########################

# Path to config yaml
yaml_config_path = os.path.join(__location__, "../ylb-config.yaml")

# Default content for config
default_config_content = """discord_default_voice_channel: 'MyVoiceChannel'"""

# Check if yaml exists, if not, create it with default content
if not os.path.exists(yaml_config_path):
    with open(yaml_config_path, "w") as file:
        file.write(default_config_content)

# Load gps-toolkit-config.yaml
config_yaml = yaml.load(open(yaml_config_path), Loader=Loader)

###
## General configuration options
###

CONVO_MAX_CYCLES = 100  # Maximum number of consecutive tool calls within a conversation
MAX_MESSAGE_BUFFER_SIZE = 150  # Maximum number of messages to store in memory

# Promptss
SYSTEM_PROMPT = (
    open(os.path.join(__location__, "resources/prompts/system-prompt.md"))
    .read()
    .strip()
)
PERSONALITY_PROMPT = (
    open(os.path.join(__location__, "resources/prompts/personality-prompt.md"))
    .read()
    .strip()
)
INSTRUCTION_PROMPT = (
    open(os.path.join(__location__, "resources/prompts/instruction-prompt.md"))
    .read()
    .strip()
)
SYNOPSIS_PROMPT = "Return a summary of the content in 1-2 sentences."

# Memory
OUTPUT_DIRECTORY = "/output"
DEEP_MEMORY_FILENAME = ".memory/deep_memory.json"
SHORT_MEMORY_FILENAME = ".memory/short_memory.json"

###
## Discord configuration options
###

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_DEFAULT_CHANNEL = config_yaml.get("discord.default_voice_channel")
CONTINUOUS_LISTEN_RECORDING_DURATION = config_yaml.get("discord.continuous_listen.recording_duration", 30)
CONTINUOUS_LISTEN_PAUSE_DURATION = config_yaml.get("discord.continuous_listen.pause_duration", 0.1)
CONTINUOUS_LISTEN_ACTIVATION_PHRASE = config_yaml.get("discord.continuous_listen.activation_phrase", "binkins")
CONTINUOUS_LISTEN_SAMPLE_RATE = config_yaml.get("discord.continous_listen.sample_rate", 16000)

###
## End Discord configuration options
###

###
## Begin OpenAI API setup
###

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG_ID = os.getenv("OPENAI_ORGANIZATION_ID")
OPENAI_MODEL = config_yaml.get("openai.chat.model", "gpt-4o-mini")
OPENAI_MODEL_TEMPERATURE = config_yaml.get("openai.chat.temperature", 1.0)
OPENAI_VOICE_MODEL = config_yaml.get("openai.voice.model", "whisper-1")
OPENAI_TTS_VOICE = config_yaml.get("openai.voice.tts_voice", "echo")
OPENAI_TTS_MODEL = config_yaml.get("openai.voice.tts_model", "tts-1-hd")

# Assistant
OPENAI_ASSISTANT_ID = config_yaml.get("openai.assistant.id", "asst_ZUgOFB1c8RyXse4q888oTo5D")
OPENAI_ASSISTANT_NAME = config_yaml.get("openai.assistant.name", None)

# Vector store
OPENAI_VECTOR_STORE_ID = config_yaml.get("openai.vector_store.id", "vs_dfpknpKmECiqIvaxAlo0bxuh")

OPENAI_DEFAULT_PROMPT = "Let's have a voice conversation. You start by asking me what to discuss. Allow me 10 seconds to respond."

###
## End OpenAPI setup
###

SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)
