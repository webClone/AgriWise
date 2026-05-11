import asyncio
import os
import traceback
import logging

logging.basicConfig(level=logging.WARNING)

# Override logger to print exception traceback
class TracingHandler(logging.StreamHandler):
    def emit(self, record):
        if record.exc_info:
            super().emit(record)
        else:
            print("LOG:", record.getMessage())
            # Let's force an exception print if we see 'Gemini API error:'
            if "Gemini API error:" in record.getMessage():
                import sys
                print(sys.exc_info())

logging.getLogger().handlers = [TracingHandler()]

from dotenv import load_dotenv
load_dotenv()

from services.agribrain.layer10_sire.llm_client import enhance_explainability, _trip_circuit, OPENROUTER_API_KEY

async def test_fallback():
    _trip_circuit(429)
    res = await enhance_explainability("TEST-LAYER", {"farmer_summary": "Template"}, {"test": 123})
    print("Result:", res)

asyncio.run(test_fallback())
