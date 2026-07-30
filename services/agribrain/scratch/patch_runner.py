import pathlib

def main():
    p = pathlib.Path("services/agribrain/layer10_sire/runner.py")
    content = p.read_text(encoding="utf-8")
    
    target = """def load_layer10_from_cache(cache_key: str) -> Optional[Layer10Output]:
    # Ignore .tmp files during cache load
    if cache_key.endswith(".tmp"):
        return None
        
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cache_path = os.path.join(base_dir, "artifacts", "surfaces_cache", f"{cache_key}.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                d = json.load(f)"""

    replacement = """def load_layer10_from_cache(cache_key: str) -> Optional[Layer10Output]:
    # Ignore .tmp files during cache load
    if cache_key.endswith(".tmp"):
        return None
        
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cache_path = os.path.join(base_dir, "artifacts", "surfaces_cache", f"{cache_key}.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            
            # Check rollout registry if ASMAE surfaces are cached
            has_asmae_cached = any(
                s_dict.get("semantic_type", {}).get("value", "").startswith("ASMAE_")
                for s_dict in d.get("surface_pack", [])
            )
            if has_asmae_cached:
                plot_id = d.get("plot_id", "default")
                from rollout.rollout_policy import should_render_l10_asmae
                if not should_render_l10_asmae(plot_id):
                    # Cache contains ASMAE surfaces, but visuals are disabled for this plot: return miss
                    return None"""

    if target in content:
        p.write_text(content.replace(target, replacement), encoding="utf-8")
        print("Success LF")
    elif target.replace("\n", "\r\n") in content:
        p.write_text(content.replace(target.replace("\n", "\r\n"), replacement.replace("\n", "\r\n")), encoding="utf-8")
        print("Success CRLF")
    else:
        print("Target not found!")

if __name__ == "__main__":
    main()
