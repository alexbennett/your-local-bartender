from openai import OpenAI
from ylb import config

openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
