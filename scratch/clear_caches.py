import os
import shutil
import subprocess

# 1. Clear surfaces_cache and ASMAE caches
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
surfaces_cache_dir = os.path.join(base_dir, "services", "agribrain", "artifacts", "surfaces_cache")
historical_cache_dir = os.path.join(base_dir, "services", "agribrain", "artifacts", "historical_surfaces_cache")
asmae_cache_dir = os.path.join(base_dir, "services", "agribrain", "artifacts", "asmae_cache")
asmae_operators_dir = os.path.join(base_dir, "services", "agribrain", "artifacts", "asmae_operators")
asmae_rasters_dir = os.path.join(base_dir, "services", "agribrain", "artifacts", "asmae_rasters")
pseudo_scenes_dir = os.path.join(base_dir, "services", "agribrain", "artifacts", "pseudo_scenes")

for cache_dir in [
    surfaces_cache_dir,
    historical_cache_dir,
    asmae_cache_dir,
    asmae_operators_dir,
    asmae_rasters_dir,
    pseudo_scenes_dir
]:
    if os.path.exists(cache_dir):
        print(f"Clearing: {cache_dir}")
        for filename in os.listdir(cache_dir):
            file_path = os.path.join(cache_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

# 2. Run prisma clear_snapshots.js via subprocess
js_script = os.path.join(base_dir, "scratch", "clear_snapshots.js")
if os.path.exists(js_script):
    print("Running database clear script...")
    result = subprocess.run(["node", js_script], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Error clearing database snapshots:")
        print(result.stderr)
