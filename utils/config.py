import os

from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_FILE = os.getenv("DB_FILE", "data.sqlite")

oai_client = OpenAI(api_key=OPENAI_API_KEY)
