import os
import asyncio
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def enrich_engines_with_explainability(engines: List[Dict]) -> List[Dict]:
    """
    Enriches the engine payload with conversational explainability.
    Moves the data-enrichment logic out of the HTTP layer (app/main.py) and into the L10 ecosystem.
    Supports hybrid architecture: base templates + optional OpenRouter LLM rewrite.
    """
    from layer10_sire.explainability_conversational import generate_layer_explainability
    
    use_llm = os.environ.get("ENABLE_LLM_EXPLAINABILITY", "false").lower() == "true"
    
    # 1. Generate base templates for all engines synchronously
    base_templates = []
    for eng in engines:
        data = eng.get("data", {}) or {}
        layer_id = eng.get("id", "")
        status = eng.get("status", "OK")
        base_templates.append(generate_layer_explainability(layer_id, data, status))
        
    final_conv_data = list(base_templates)
    
    # 2. Optionally rewrite with LLM concurrently
    if use_llm:
        from layer10_sire.llm_client import enhance_explainability
        
        async def fetch_all():
            tasks = []
            for i, eng in enumerate(engines):
                layer_id = eng.get("id", "")
                data = eng.get("data", {}) or {}
                tasks.append(enhance_explainability(layer_id, base_templates[i], data))
            return await asyncio.gather(*tasks, return_exceptions=True)
            
        try:
            # Check if an event loop is running
            asyncio.get_running_loop()
            logger.debug("Cannot run LLM enhancement synchronously due to running event loop.")
        except RuntimeError:
            # No event loop, we can safely block and run all enhancements CONCURRENTLY
            try:
                results = asyncio.run(fetch_all())
                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        logger.warning(f"Failed concurrent LLM explainability for {engines[i].get('id')}: {res}")
                    elif res:
                        final_conv_data[i] = res
            except Exception as e:
                logger.warning(f"Batch LLM explainability failed: {e}")
                
    # 3. Inject the final strings into the engine's data object
    enriched_engines = []
    for i, eng in enumerate(engines):
        eng_copy = eng.copy()
        data = eng_copy.get("data", {}) or {}
        conv_data = final_conv_data[i]
        
        for k, v in conv_data.items():
            if k not in data or not data[k]:
                data[k] = v
                
        eng_copy["data"] = data
        enriched_engines.append(eng_copy)
        
    return enriched_engines
