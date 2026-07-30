"""
Crop Intelligence v6.1A — Seeded End-to-End Evaluation Run Seeding Script.

Generates 40 synthetic labeled samples across 15 plots, splitting plots
strictly between training and evaluation splits to avoid leakage.
Each label contains a synthetic marker and realistic feature signatures.
"""

import os
import sys
import random
from datetime import datetime, timezone
from pymongo import MongoClient
from bson import ObjectId

# Ensure we can import from services/agribrain
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layer2_veg_int.labels.label_schema import CropLabel
from layer2_veg_int.labels.label_store import MongoLabelStore
from layer2_veg_int.features.crop_feature_vector import CropFeatureVector

def main():
    # ── 1. Dev-only safety guards ──
    for env_var in ["NODE_ENV", "APP_ENV"]:
        if os.environ.get(env_var) == "production":
            print(f"ERROR: Cannot run seeding script in production environment ({env_var}=production). Aborting.")
            sys.exit(1)

    db_uri = os.environ.get("MONGODB_URI") or "mongodb://localhost:27017/agriwise?directConnection=true"
    client = MongoClient(db_uri, serverSelectionTimeoutMS=3000)
    db_name = db_uri.split("/")[-1].split("?")[0] if "/" in db_uri else "agriwise"
    if not db_name or "mongodb" in db_name:
        db_name = "agriwise"
    db = client[db_name]

    print(f"Connected to database '{db_name}'.")

    # ── 2. Targeted clean of synthetic labels only ──
    del_res = db["ConfirmedCropLabel"].delete_many({"notes": {"$regex": "synthetic_seeded_v6_1A"}})
    print(f"Deleted {del_res.deleted_count} existing synthetic labels with marker 'synthetic_seeded_v6_1A'.")

    # ── 3. Split plots to prevent leakage ──
    plots = list(db["Plot"].find())
    if len(plots) < 15:
        print(f"WARNING: Expected 15 plots, found {len(plots)}. Seeding will proceed using available plots.")
    
    # Split plots strictly: first 73% (approx 11 plots) for train, rest (approx 4 plots) for eval
    train_split_idx = min(len(plots) - 1, 11) if len(plots) > 4 else len(plots) // 2
    train_plots = plots[:train_split_idx]
    eval_plots = plots[train_split_idx:]

    print(f"Split plots: {len(train_plots)} training plots, {len(eval_plots)} evaluation holdout plots.")
    print(f"Train plots: {[str(p['_id'])[:8] for p in train_plots]}")
    print(f"Eval plots: {[str(p['_id'])[:8] for p in eval_plots]}")

    # Initialize random seed for controlled noise
    random.seed(610)

    # ── 4. Generate 40 samples (30 train, 10 eval) ──
    # Target counts:
    # Tomato: 11 train, 4 eval
    # Orange: 11 train, 4 eval
    # Fallow: 8 train, 2 eval
    splits = {
        "train": {
            "plots": train_plots,
            "counts": {"tomato": 11, "orange": 11, "fallow": 8},
            "is_active": True,
            "note_suffix": "train"
        },
        "eval": {
            "plots": eval_plots,
            "counts": {"tomato": 4, "orange": 4, "fallow": 2},
            "is_active": False, # inactive initially so train endpoint doesn't see them
            "note_suffix": "eval"
        }
    }

    store = MongoLabelStore(db_uri)
    seeded_count = 0

    # Retrieve all flat feature keys to seed full vectors
    flat_keys = sorted(list(CropFeatureVector().to_flat_dict().keys()))

    for split_name, config in splits.items():
        plots_list = config["plots"]
        note_suffix = config["note_suffix"]
        is_active = config["is_active"]

        # If there are no plots in this split, skip
        if not plots_list:
            continue

        label_index = 0
        for crop_type, target_count in config["counts"].items():
            for i in range(target_count):
                # Distribute labels round-robin across plots in the split
                plot = plots_list[label_index % len(plots_list)]
                plot_id = str(plot["_id"])
                label_index += 1

                # Define non-overlapping crop cycles per crop type to avoid DB conflicts on same plot
                if crop_type == "tomato":
                    planting_date = "2023-03-01"
                    harvest_date = "2023-07-01"
                    crop_group = "solanaceae_veg"
                elif crop_type == "orange":
                    planting_date = "2024-03-01"
                    harvest_date = "2024-11-01"
                    crop_group = "evergreen_orchard"
                else: # fallow
                    planting_date = "2025-06-01"
                    harvest_date = "2025-07-01"
                    crop_group = "non_crop"

                # Generate features with class-specific characteristics and controlled noise
                features = {k: 0.0 for k in flat_keys}
                
                # Context features
                features["latitude"] = float(plot.get("latitude", 36.5))
                features["longitude"] = float(plot.get("longitude", 3.0))
                features["plot_area_ha"] = float(plot.get("area", 1.0))
                features["aridity_index"] = random.uniform(0.3, 0.8)

                # Crop-specific profiles with overlap for realistic ambiguity
                if crop_type == "tomato":
                    peak_ndvi = random.uniform(0.58, 0.78)
                    base_ndvi = random.uniform(0.12, 0.18)
                    amp = peak_ndvi - base_ndvi
                    
                    features["peak_ndvi"] = peak_ndvi
                    features["base_ndvi"] = base_ndvi
                    features["amplitude"] = amp
                    features["cv_ndvi"] = random.uniform(0.35, 0.45)
                    features["is_evergreen"] = 0.0
                    features["n_seasons"] = 1.0
                    features["los_days"] = 120.0
                    features["sos_doy"] = random.uniform(60, 90)
                    features["pos_doy"] = features["sos_doy"] + random.uniform(50, 70)
                    features["eos_doy"] = features["pos_doy"] + random.uniform(50, 70)
                    features["growth_rate"] = amp / (features["pos_doy"] - features["sos_doy"])
                    features["senescence_rate"] = amp / (features["eos_doy"] - features["pos_doy"])
                    features["ndre_peak"] = random.uniform(0.40, 0.50)
                    features["ndre_mean"] = random.uniform(0.25, 0.35)
                    features["vv_mean_db"] = random.uniform(-14.0, -10.0)
                    features["vh_mean_db"] = random.uniform(-22.0, -18.0)
                    features["vv_vh_ratio_mean"] = features["vv_mean_db"] - features["vh_mean_db"]
                    features["rvi_mean"] = random.uniform(2.0, 4.0)
                    features["sar_crop_cycle_amplitude"] = random.uniform(3.0, 6.0)

                    # Rules engine lists
                    ndvi_series = [0.2, 0.3, 0.5, 0.7, 0.6, 0.4, 0.2]
                    ndvi_dates = ["2023-03-01", "2023-03-15", "2023-04-01", "2023-04-15", "2023-05-01", "2023-05-15", "2023-06-01"]
                    ndvi_velocity = [0.01, 0.02, 0.02, -0.01, -0.02, -0.02]
                    seasonal_profile = [0.2, 0.3, 0.5, 0.7, 0.6, 0.4, 0.2]

                elif crop_type == "orange":
                    peak_ndvi = random.uniform(0.50, 0.70)
                    base_ndvi = random.uniform(0.40, 0.50)
                    amp = peak_ndvi - base_ndvi
                    
                    features["peak_ndvi"] = peak_ndvi
                    features["base_ndvi"] = base_ndvi
                    features["amplitude"] = amp
                    features["cv_ndvi"] = random.uniform(0.05, 0.15)
                    features["is_evergreen"] = 1.0
                    features["n_seasons"] = 1.0
                    features["los_days"] = 365.0
                    features["sos_doy"] = random.uniform(1, 365)
                    features["pos_doy"] = random.uniform(1, 365)
                    features["eos_doy"] = random.uniform(1, 365)
                    features["growth_rate"] = 0.001
                    features["senescence_rate"] = 0.001
                    features["ndre_peak"] = random.uniform(0.35, 0.45)
                    features["ndre_mean"] = random.uniform(0.30, 0.40)
                    features["vv_mean_db"] = random.uniform(-11.0, -8.0)
                    features["vh_mean_db"] = random.uniform(-16.0, -13.0)
                    features["vv_vh_ratio_mean"] = features["vv_mean_db"] - features["vh_mean_db"]
                    features["rvi_mean"] = random.uniform(3.5, 5.5)
                    features["sar_crop_cycle_amplitude"] = random.uniform(1.0, 3.0)

                    # Rules engine lists
                    ndvi_series = [0.45, 0.48, 0.52, 0.62, 0.58, 0.48, 0.46]
                    ndvi_dates = ["2024-03-01", "2024-03-15", "2024-04-01", "2024-04-15", "2024-05-01", "2024-05-15", "2024-06-01"]
                    ndvi_velocity = [0.002, 0.003, 0.005, -0.002, -0.004, -0.001]
                    seasonal_profile = [0.45, 0.48, 0.52, 0.62, 0.58, 0.48, 0.46]

                else: # fallow
                    peak_ndvi = random.uniform(0.08, 0.25)
                    base_ndvi = random.uniform(0.08, 0.18)
                    amp = peak_ndvi - base_ndvi

                    features["peak_ndvi"] = peak_ndvi
                    features["base_ndvi"] = base_ndvi
                    features["amplitude"] = amp
                    features["cv_ndvi"] = random.uniform(0.05, 0.20)
                    features["is_evergreen"] = 0.0
                    features["n_seasons"] = 0.0
                    features["los_days"] = 30.0
                    features["sos_doy"] = random.uniform(1, 365)
                    features["pos_doy"] = random.uniform(1, 365)
                    features["eos_doy"] = random.uniform(1, 365)
                    features["growth_rate"] = 0.0
                    features["senescence_rate"] = 0.0
                    features["ndre_peak"] = random.uniform(0.10, 0.20)
                    features["ndre_mean"] = random.uniform(0.08, 0.15)
                    features["vv_mean_db"] = random.uniform(-18.0, -14.0)
                    features["vh_mean_db"] = random.uniform(-26.0, -22.0)
                    features["vv_vh_ratio_mean"] = features["vv_mean_db"] - features["vh_mean_db"]
                    features["rvi_mean"] = random.uniform(1.0, 2.0)
                    features["sar_crop_cycle_amplitude"] = random.uniform(0.5, 2.0)

                    # Rules engine lists
                    ndvi_series = [0.15, 0.18, 0.22, 0.20, 0.17, 0.16, 0.15]
                    ndvi_dates = ["2025-06-01", "2025-06-08", "2025-06-15", "2025-06-22", "2025-06-29", "2025-07-06", "2025-07-13"]
                    ndvi_velocity = [0.003, 0.005, -0.002, -0.003, -0.001, -0.001]
                    seasonal_profile = [0.15, 0.18, 0.22, 0.20, 0.17, 0.16, 0.15]

                # Setup feature snapshot structure
                fv_snapshot = {
                    "feature_vector_version": "6.0.0",
                    "flat_features": features,
                    "full_json": {
                        "ndvi_series": ndvi_series,
                        "ndvi_dates": ndvi_dates,
                        "ndvi_velocity": ndvi_velocity,
                        "seasonal_profile": seasonal_profile
                    },
                    "data_completeness": 0.8,
                    "feature_availability_by_level": {"L0": 1.0, "L1": 1.0, "L2": 1.0, "L3": 1.0}
                }

                # Construct CropLabel
                label = CropLabel(
                    label_id="",
                    plot_id=plot_id,
                    geometry_hash="geom_hash_v6_1a",
                    crop_code=crop_type,
                    crop_group=crop_group,
                    label_source="imported_dataset",
                    label_confidence="MEDIUM",
                    planting_date=planting_date,
                    harvest_date=harvest_date,
                    notes=f"synthetic_seeded_v6_1A_{note_suffix}",
                    feature_vector_snapshot=fv_snapshot,
                    is_active=is_active
                )

                # Save via store (handles normalization and validation)
                label_id, conflict = store.save_label(label)
                
                # Directly write extra MongoDB flags to bypass dataclass schema limitations
                db["ConfirmedCropLabel"].update_one(
                    {"labelId": label_id},
                    {
                        "$set": {
                            "synthetic": True,
                            "seed_run_id": f"v6.1A-{note_suffix}-{seeded_count}"
                        }
                    }
                )

                seeded_count += 1

    print(f"Seeded {seeded_count} total synthetic labels successfully.")

if __name__ == "__main__":
    main()
