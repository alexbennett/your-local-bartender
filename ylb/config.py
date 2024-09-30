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

# Setup logging configuration
LOG_FILE = os.path.join(__location__, "../ylb.log")

# Define custom logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
    ]
)

# Custom filter to only show logs from the bartender-v2 module
class ModuleFilter(logging.Filter):
    def filter(self, record):
        return record.module == 'bartender-v2'

# Custom console handler without logging tags
class ConsoleHandler(logging.StreamHandler):
    def emit(self, record):
        msg = self.format(record)
        print(msg)  # Direct print to console

# Add custom console handler
console_handler = ConsoleHandler()
console_handler.setFormatter(logging.Formatter('%(message)s'))  # Strip logging tags
console_handler.addFilter(ModuleFilter())  # Apply the filter to ignore logs from other modules
logging.getLogger().addHandler(console_handler)


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

ENABLE_THOUGHT_MESSAGES = config_yaml.get("enable_thought_messages", False)
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
DISCORD_DEFAULT_CHANNEL = config_yaml.get("discord", {}).get("default_voice_channel")
CONTINUOUS_LISTEN_RECORDING_DURATION = config_yaml.get("discord", {}).get("continuous_listen", {}).get("recording_duration", 15)
CONTINUOUS_LISTEN_PAUSE_DURATION = config_yaml.get("discord", {}).get("continuous_listen", {}).get("pause_duration", 0.1)
CONTINUOUS_LISTEN_ACTIVATION_PHRASE = config_yaml.get("discord", {}).get("continuous_listen", {}).get("activation_phrase", "bartender")
CONTINUOUS_LISTEN_SAMPLE_RATE = config_yaml.get("discord", {}).get("continuous_listen", {}).get("sample_rate", 16000)

###
## End Discord configuration options
###

###
## Begin OpenAI API setup
###

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG_ID = os.getenv("OPENAI_ORGANIZATION_ID")
OPENAI_MODEL = config_yaml.get("openai", {}).get("chat", {}).get("model", "gpt-4o-mini")
OPENAI_MODEL_TEMPERATURE = config_yaml.get("openai", {}).get("chat", {}).get("temperature", 1.0)
OPENAI_VOICE_MODEL = config_yaml.get("openai", {}).get("voice", {}).get("model", "whisper-1")
OPENAI_TTS_VOICE = config_yaml.get("openai", {}).get("voice", {}).get("tts_voice", "echo")
OPENAI_TTS_MODEL = config_yaml.get("openai", {}).get("voice", {}).get("tts_model", "tts-1-hd")

# Assistant
OPENAI_ASSISTANT_ID = config_yaml.get("openai", {}).get("assistant", {}).get("id", "asst_ZUgOFB1c8RyXse4q888oTo5D")
OPENAI_ASSISTANT_NAME = config_yaml.get("openai", {}).get("assistant", {}).get("name", "Bartender")

# Vector store
OPENAI_VECTOR_STORE_ID = config_yaml.get("openai", {}).get("vector_store", {}).get("id", "vs_dfpknpKmECiqIvaxAlo0bxuh")

OPENAI_DEFAULT_PROMPT = "Let's have a voice conversation. You start by asking me what to discuss. Allow me 10 seconds to respond."

###
## End OpenAPI setup
###

SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)
