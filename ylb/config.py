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
yaml_config_path = os.path.join(__location__, "ylb-config.yaml")

# Default content for config
default_config_content = """"""

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
DISCORD_DEFAULT_CHANNEL = "𝐭𝐡𝐞 𝐛𝐚𝐫"
DISCORD_TOILET_CHANNEL = "𝐭𝐡𝐞 𝐭𝐨𝐢𝐥𝐞𝐭"
DISCORD_COUCH_CHANNEL = "𝐭𝐡𝐞 𝐜𝐨𝐮𝐜𝐡"

CONTINUOUS_LISTEN_RECORDING_INTERVAL = 10
CONTINUOUS_LISTEN_PAUSE_TIME = 0.1
CONTINUOUS_LISTEN_ACTIVATOR = "bartender"

###
## End Discord configuration options
###

###
## Begin audio configuration options
###

AUDIO_DEFAULT_SAMPLE_RATE = 16000
AUDIO_DEFAULT_DURATION = 5

###
## End audio configuration options
###

###
## Begin OpenAI API setup
###

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG_ID = os.getenv("OPENAI_ORGANIZATION_ID")
OPENAI_MODEL = "gpt-4o"
OPENAI_MODEL_TEMPERATURE = 1.0
OPENAI_VOICE_MODEL = "whisper-1"
OPENAI_TTS_VOICE = "nova"
OPENAI_TTS_MODEL = "tts-1-hd"

# Assistant
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID", None)
OPENAI_ASSISTANT_NAME = "Binkins"

# Vector store
OPENAI_VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID", None)

OPENAI_DEFAULT_PROMPT = "Let's have a voice conversation. You start by asking me what to discuss. Allow me 10 seconds to respond."

###
## End OpenAPI setup
###

SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)
