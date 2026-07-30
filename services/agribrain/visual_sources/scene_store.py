import os
import json
import sys
from typing import Optional, Dict, Any

class BaseSceneStore:
    def save(self, scene_id: str, data: Dict[str, Any]) -> None:
        raise NotImplementedError
    def get(self, scene_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

class MongoSceneStore(BaseSceneStore):
    def __init__(self, mongo_url: str):
        from pymongo import MongoClient
        self.client = MongoClient(mongo_url, serverSelectionTimeoutMS=1000)
        
        # Extract db name
        db_name = "agriwise"
        try:
            path = mongo_url.split("?")[0].split("/")
            if len(path) >= 4:
                db_name = path[3] or "agriwise"
        except Exception:
            pass
        self.db = self.client[db_name]
        self.collection = self.db["VisualScene"]
        # Trigger quick ping to force server selection timeout if offline
        self.client.admin.command('ping')

    def save(self, scene_id: str, data: Dict[str, Any]) -> None:
        self.collection.update_one(
            {"scene_id": scene_id},
            {"$set": data},
            upsert=True
        )

    def get(self, scene_id: str) -> Optional[Dict[str, Any]]:
        return self.collection.find_one({"scene_id": scene_id})

class JsonSceneStore(BaseSceneStore):
    def __init__(self, filepath: str):
        self.filepath = filepath
        # Ensure parent dir exists
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                json.dump({}, f)

    def _read(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _write(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def save(self, scene_id: str, data: Dict[str, Any]) -> None:
        current = self._read()
        current[scene_id] = data
        self._write(current)

    def get(self, scene_id: str) -> Optional[Dict[str, Any]]:
        current = self._read()
        return current.get(scene_id)

class InMemorySceneStore(BaseSceneStore):
    def __init__(self):
        self.store = {}

    def save(self, scene_id: str, data: Dict[str, Any]) -> None:
        self.store[scene_id] = data

    def get(self, scene_id: str) -> Optional[Dict[str, Any]]:
        return self.store.get(scene_id)


# Global Store Selector
_scene_store_instance: BaseSceneStore = None

def get_scene_store() -> BaseSceneStore:
    global _scene_store_instance
    if _scene_store_instance is not None:
        return _scene_store_instance

    # Tier 1: MongoDB Connection
    try:
        mongo_url = os.getenv("DATABASE_URL", "mongodb://localhost:27017/agriwise")
        _scene_store_instance = MongoSceneStore(mongo_url)
        print("[SceneStore] Successfully initialized MongoDB backend.", file=sys.stderr)
        return _scene_store_instance
    except Exception as me:
        print(f"[SceneStore] MongoDB unavailable (falling back to JSON file): {me}", file=sys.stderr)

    # Tier 2: Local JSON file fallback
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_dir, "artifacts", "visual_scene_store.json")
        _scene_store_instance = JsonSceneStore(json_path)
        print(f"[SceneStore] Successfully initialized Local JSON file backend at {json_path}.", file=sys.stderr)
        return _scene_store_instance
    except Exception as je:
        print(f"[SceneStore] JSON file write unavailable (falling back to in-memory): {je}", file=sys.stderr)

    # Tier 3: In-Memory dictionary cache
    _scene_store_instance = InMemorySceneStore()
    print("[SceneStore] Initialized In-Memory fallback cache.", file=sys.stderr)
    return _scene_store_instance


def save_scene(
    scene_id: str,
    provider: str,
    cog_asset: str,
    datetime: str,
    native_resolution_m: float
) -> None:
    """Save a satellite visual scene's metadata to the active registry."""
    data = {
        "scene_id": scene_id,
        "provider": provider,
        "cog_asset": cog_asset,
        "datetime": datetime,
        "native_resolution_m": native_resolution_m
    }
    try:
        store = get_scene_store()
        store.save(scene_id, data)
    except Exception as e:
        print(f"[SceneStore] Save error for scene {scene_id}: {e}", file=sys.stderr)


def get_scene(scene_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve visual scene details by ID from the active registry."""
    try:
        store = get_scene_store()
        return store.get(scene_id)
    except Exception as e:
        print(f"[SceneStore] Fetch error for scene {scene_id}: {e}", file=sys.stderr)
        return None
