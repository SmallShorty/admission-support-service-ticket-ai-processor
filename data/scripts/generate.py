import os
import json
import random
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY не найден в файле .env")

model = genai.GenerativeModel("gemini-1.5-flash")

genai.configure(api_key=api_key)

generation_config = {
    "temperature": 0.9,  # Высокий для разнообразия текстов
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 1024,
    "response_mime_type": "application/json",
}
