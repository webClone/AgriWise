import asyncio
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

from services.agribrain.layer10_sire.llm_client import _call_gemini_api, SYSTEM_PROMPT

async def test():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
        res = await _call_gemini_api(s, 'gemma-4-26b-a4b-it', SYSTEM_PROMPT, 'Rewrite {"test": 123}')
        print("Result:", res)

asyncio.run(test())
