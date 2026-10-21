import os

from dotenv import load_dotenv
from google import genai

load_dotenv()  # reads the .env file into environment variables

api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

if not api_key or api_key == "paste_your_key_here":
    raise SystemExit("GEMINI_API_KEY is missing. Check your .env file.")

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model=model,
    contents="Say hello to a hackathon judge in one short sentence.",
)

print("Model used:", model)
print("Reply:", response.text)