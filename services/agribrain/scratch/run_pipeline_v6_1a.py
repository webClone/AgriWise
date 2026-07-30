"""
Crop Intelligence v6.1A — Seeded End-to-End Evaluation Run Execution Script.

Coordinates:
  1. Seeding of synthetic labels (30 active train, 10 inactive eval).
  2. POST /v2/crop-model/train (trains on train split).
  3. Swapping isActive flags (deactivates train, activates eval).
  4. POST /v2/crop-model/evaluate (evaluates on evaluation holdout split).
  5. Restoring all labels to active.
"""

import os
import sys
import json
from pymongo import MongoClient

# Ensure we can import from services/agribrain
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

def run_pipeline():
    # Set dev override for synthetic model loading inside this script/process
    os.environ["AGRIBRAIN_DEV_ALLOW_SYNTHETIC_MODEL"] = "true"

    # ── 1. Safety Guards ──
    for env_var in ["NODE_ENV", "APP_ENV"]:
        if os.environ.get(env_var) == "production":
            print(f"ERROR: Cannot run pipeline in production environment ({env_var}=production). Aborting.")
            sys.exit(1)

    db_uri = os.environ.get("MONGODB_URI") or "mongodb://localhost:27017/agriwise?directConnection=true"
    client = MongoClient(db_uri, serverSelectionTimeoutMS=3000)
    db_name = db_uri.split("/")[-1].split("?")[0] if "/" in db_uri else "agriwise"
    if not db_name or "mongodb" in db_name:
        db_name = "agriwise"
    db = client[db_name]

    # Initialize TestClient
    api_client = TestClient(app)
    headers = {"X-Admin-Token": "dev_admin_token"}

    # ── 2. Run Seeding Script ──
    print("\n--- STEP 1: Seeding Synthetic Labels ---")
    from scratch.seed_evaluation_data import main as seed_main
    seed_main()

    # Verify counts in DB
    total_labels = db["ConfirmedCropLabel"].count_documents({"notes": {"$regex": "synthetic_seeded_v6_1A"}})
    active_labels = db["ConfirmedCropLabel"].count_documents({"notes": {"$regex": "synthetic_seeded_v6_1A"}, "isActive": True})
    print(f"DB Status: {total_labels} seeded labels total ({active_labels} active).")

    # ── 3. Train Classifier ──
    print("\n--- STEP 2: Training Hierarchical Classifier on Train Split ---")
    train_req = {
        "dry_run": False,
        "min_quality_tier": "C",
        "include_historical": True,
        "include_synthetic": True
    }
    resp = api_client.post("/v2/crop-model/train", json=train_req, headers=headers)
    if resp.status_code != 200:
        print(f"ERROR: Training failed with status {resp.status_code}: {resp.text}")
        sys.exit(1)
    
    train_result = resp.json()
    print("Training Response:")
    print(json.dumps(train_result, indent=2))

    # ── 4. Programmatic Swap of Labels for Evaluation ──
    print("\n--- STEP 3: Swapping Labels (Deactivate Train, Activate Eval Holdout) ---")
    # Set train labels to inactive
    db["ConfirmedCropLabel"].update_many(
        {"notes": "synthetic_seeded_v6_1A_train"},
        {"$set": {"isActive": False}}
    )
    # Set eval labels to active
    db["ConfirmedCropLabel"].update_many(
        {"notes": "synthetic_seeded_v6_1A_eval"},
        {"$set": {"isActive": True}}
    )

    eval_active = db["ConfirmedCropLabel"].count_documents({"notes": {"$regex": "synthetic_seeded_v6_1A"}, "isActive": True})
    print(f"Labels active for evaluation: {eval_active} (expected 10).")

    # ── 5. Run Evaluation Endpoint ──
    print("\n--- STEP 4: Running Model Evaluation on Holdout Split ---")
    eval_req = {
        "min_quality_tier": "C",
        "include_historical": True,
        "dry_run": False,
        "save_report": True,
        "include_synthetic": True
    }
    resp = api_client.post("/v2/crop-model/evaluate", json=eval_req, headers=headers)
    if resp.status_code != 200:
        print(f"ERROR: Evaluation failed with status {resp.status_code}: {resp.text}")
        # Restore labels before exiting
        db["ConfirmedCropLabel"].update_many(
            {"notes": {"$regex": "synthetic_seeded_v6_1A"}},
            {"$set": {"isActive": True}}
        )
        sys.exit(1)

    eval_result = resp.json()
    print("Evaluation completed. Summary statistics:")
    print(json.dumps(eval_result.get("summary", {}), indent=2))
    
    # ── 6. Restore all seeded labels to active ──
    print("\n--- STEP 5: Restoring all seeded labels to active ---")
    db["ConfirmedCropLabel"].update_many(
        {"notes": {"$regex": "synthetic_seeded_v6_1A"}},
        {"$set": {"isActive": True}}
    )
    print("Pipeline run completed successfully.")

if __name__ == "__main__":
    run_pipeline()
