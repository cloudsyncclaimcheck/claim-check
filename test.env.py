import os
from dotenv import load_dotenv
from pathlib import Path

# Explicit path to .env
env_path = Path(__file__).resolve().parent.parent / ".env"
print(f"Looking for .env at: {env_path}")

loaded = load_dotenv(dotenv_path=env_path)
print("Loaded:", loaded)

print("GOOGLE_API_KEY =", os.getenv("GOOGLE_API_KEY"))
print("OPENAI_API_KEY =", os.getenv("OPENAI_API_KEY"))
print("GOOGLE_CX_ID =", os.getenv("GOOGLE_CX_ID"))
