import importlib
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai = importlib.import_module("google.genai")
client = genai.Client(api_key=api_key)
print("google.genai.Client methods:")
print(dir(client))