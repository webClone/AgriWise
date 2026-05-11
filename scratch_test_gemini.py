import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

async def test_gemini():
    payload = {
        "contents": [
            {
                "parts": [{"text": "You are an AI. Return JSON: {\"hello\": \"world\"}"}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            print(resp.status)
            print(await resp.text())

asyncio.run(test_gemini())
