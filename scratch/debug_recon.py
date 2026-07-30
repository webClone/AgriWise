import os
from datetime import datetime

cache_dir = "services/agribrain/artifacts/surfaces_cache"
if os.path.exists(cache_dir):
    for f in os.listdir(cache_dir):
        p = os.path.join(cache_dir, f)
        mtime = os.path.getmtime(p)
        print(f"{f}: {datetime.fromtimestamp(mtime).isoformat()}")
else:
    print("No cache dir")
