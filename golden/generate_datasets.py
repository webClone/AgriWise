"""
Golden Plot Dataset Generator

Creates 3 deterministic golden plot datasets for regression testing.
Each plot covers 45 days with weather, satellite obs, events, and images.
All data is JSON — no external dependencies.

Plots:
  1. plot_cloudy:          Coastal winter, 70% S2 cloud rate, frequent gaps
  2. plot_irrigated:       Irrigated wheat, 2 irrigation events, sensor data
  3. plot_rain_mismatch:   Convective rain zone, SAR/rain conflicts

Expected outputs are pinned alongside each dataset.
"""

import json
import os
import math
import random

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "golden")

random.seed(42)  # Deterministic


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ {os.path.relpath(path, GOLDEN_DIR)}")


# ============================================================================
# Plot 1: Cloudy Coastal — Frequent S2 gaps
# ============================================================================

def generate_cloudy_coastal():
    plot_dir = os.path.join(GOLDEN_DIR, "plot_cloudy")
    print("\n=== Plot 1: Cloudy Coastal (45 days) ===")

    # Plot metadata
    _write(os.path.join(plot_dir, "plot.json"), {
        "plot_id": "golden_cloudy",
        "lat": 36.72, "lng": 3.08,
        "area_ha": 2.5,
        "crop": "wheat",
        "sowing_date": "2024-01-10",
        "zones": ["plot"],
        "utm_zone": "31N",
    })

    # Weather: cool coastal winter, moderate rain every 3-4 days
    weather = []
    for d in range(45):
        day = f"2024-02-{d+1:02d}" if d < 29 else f"2024-03-{d-28:02d}"
        rain = random.choice([0, 0, 0, 5, 12, 20]) if d % 3 == 0 else 0
        weather.append({
            "day": day,
            "temp_max": 14 + random.gauss(0, 2),
            "temp_min": 6 + random.gauss(0, 1.5),
            "precipitation": rain,
            "et0": 1.5 + random.gauss(0, 0.3),
        })
    _write(os.path.join(plot_dir, "weather_daily.json"), weather)

    # Sentinel-2: 70% cloud rate → only ~30% of obs days usable
    s2_obs = []
    for d in range(45):
        day = weather[d]["day"]
        if d % 5 != 0:  # S2 revisit every 5 days
            continue
        cloud_prob = random.random()
        is_cloudy = cloud_prob > 0.30  # 70% cloud rate
        ndvi = 0.20 + d * 0.008 + random.gauss(0, 0.02)
        ndmi = 0.15 + d * 0.003 + random.gauss(0, 0.02)
        if is_cloudy:
            ndvi *= 0.5  # Cloud contamination reduces apparent NDVI
            cloud_prob = min(0.9, cloud_prob)
        s2_obs.append({
            "day": day,
            "ndvi": round(ndvi, 3),
            "ndmi": round(ndmi, 3),
            "cloud_probability": round(cloud_prob, 2),
            "valid_fraction": round(1.0 - cloud_prob, 2),
            "is_cloudy": is_cloudy,
        })
    _write(os.path.join(plot_dir, "sentinel2.json"), s2_obs)

    # Sentinel-1: reliable every 6 days (SAR penetrates clouds)
    s1_obs = []
    for d in range(45):
        day = weather[d]["day"]
        if d % 6 != 0:
            continue
        sm = 0.30 + sum(w["precipitation"] for w in weather[max(0,d-2):d+1]) * 0.005
        sm = min(0.6, sm)
        vv = -18.0 + 10 * sm + random.gauss(0, 1.0)
        vh = -22.0 + 3 * (0.3 + d * 0.01) + random.gauss(0, 1.5)
        s1_obs.append({
            "day": day,
            "vv": round(vv, 2),
            "vh": round(vh, 2),
            "incidence_angle": 38 + random.gauss(0, 2),
        })
    _write(os.path.join(plot_dir, "sentinel1.json"), s1_obs)

    # Events: just sowing
    _write(os.path.join(plot_dir, "events.json"), [
        {"day": "2024-01-10", "type": "sowing", "crop": "wheat"},
    ])

    # Expected outputs (pinned)
    _write(os.path.join(plot_dir, "expected.json"), {
        "description": "Cloudy coastal: frequent S2 gaps, S1 reliable",
        "final_state_ranges": {
            "lai_proxy": [0.5, 6.0],
            "sm_0_10": [0.15, 0.55],
            "phenology_stage": [0.5, 2.5],
            "canopy_stress": [0.0, 0.3],
        },
        "uncertainty_invariants": {
            "grows_during_gaps": True,
            "max_gap_days": 15,
            "shrinks_on_obs_day": True,
        },
        "reliability_invariants": {
            "sentinel1_stays_high": [0.85, 1.0],
        },
        "audit_invariants": {
            "health_grade_range": ["A", "D"],
            "min_data_availability_pct": 20,
        },
    })


# ============================================================================
# Plot 2: Irrigated — User events + moisture response
# ============================================================================

def generate_irrigated():
    plot_dir = os.path.join(GOLDEN_DIR, "plot_irrigated")
    print("\n=== Plot 2: Irrigated Wheat (45 days) ===")

    _write(os.path.join(plot_dir, "plot.json"), {
        "plot_id": "golden_irrigated",
        "lat": 34.05, "lng": -6.80,
        "area_ha": 5.0,
        "crop": "wheat",
        "sowing_date": "2024-01-05",
        "zones": ["plot"],
        "utm_zone": "29N",
    })

    # Weather: hot, dry Mediterranean — rain only a few days
    weather = []
    base_sm = 0.35
    for d in range(45):
        day = f"2024-03-{d+1:02d}" if d < 31 else f"2024-04-{d-30:02d}"
        rain = 0
        if d in [8, 22]:  # Only 2 rain days
            rain = 10 + random.gauss(0, 3)
        temp_max = 22 + d * 0.15 + random.gauss(0, 2)
        weather.append({
            "day": day,
            "temp_max": round(temp_max, 1),
            "temp_min": round(temp_max - 10 + random.gauss(0, 1), 1),
            "precipitation": max(0, round(rain, 1)),
            "et0": round(3.5 + d * 0.03 + random.gauss(0, 0.3), 1),
        })
    _write(os.path.join(plot_dir, "weather_daily.json"), weather)

    # Sentinel-2: clear sky except 2 cloud days
    s2_obs = []
    for d in range(45):
        day = weather[d]["day"]
        if d % 5 != 0:
            continue
        is_cloudy = d in [15, 30]
        ndvi = 0.35 + d * 0.01 + random.gauss(0, 0.015)
        # After irrigation (day 12, 28), vegetation boost
        if d > 14:
            ndvi += 0.05
        if d > 30:
            ndvi += 0.03
        ndmi = 0.20 + (ndvi - 0.35) * 0.3 + random.gauss(0, 0.01)
        if is_cloudy:
            ndvi *= 0.6
        s2_obs.append({
            "day": day,
            "ndvi": round(min(0.9, ndvi), 3),
            "ndmi": round(ndmi, 3),
            "cloud_probability": 0.8 if is_cloudy else 0.05,
            "valid_fraction": 0.2 if is_cloudy else 0.95,
            "is_cloudy": is_cloudy,
        })
    _write(os.path.join(plot_dir, "sentinel2.json"), s2_obs)

    # Sentinel-1: every 6 days
    s1_obs = []
    for d in range(45):
        day = weather[d]["day"]
        if d % 6 != 0:
            continue
        # SM responds to irrigation on days 12 and 28
        irrigation_boost = 0
        if 12 <= d <= 15:
            irrigation_boost = 0.15
        elif 28 <= d <= 31:
            irrigation_boost = 0.12
        sm = 0.30 - d * 0.003 + irrigation_boost + random.gauss(0, 0.02)
        sm = max(0.10, min(0.60, sm))
        vv = -18.0 + 10 * sm + random.gauss(0, 0.8)
        vh = -22.0 + 3 * (0.4 + d * 0.012) + random.gauss(0, 1.2)
        s1_obs.append({
            "day": day,
            "vv": round(vv, 2),
            "vh": round(vh, 2),
            "incidence_angle": 36 + random.gauss(0, 1.5),
        })
    _write(os.path.join(plot_dir, "sentinel1.json"), s1_obs)

    # Events: sowing + 2 irrigations
    _write(os.path.join(plot_dir, "events.json"), [
        {"day": "2024-01-05", "type": "sowing", "crop": "wheat"},
        {"day": "2024-03-13", "type": "irrigation", "amount_mm": 30},
        {"day": "2024-03-29", "type": "irrigation", "amount_mm": 25},
    ])

    # Soil sensor data (drifts on day 35+)
    sensor_data = []
    for d in range(45):
        day = weather[d]["day"]
        if d % 2 != 0:
            continue
        sm_true = 0.30 - d * 0.003
        if 12 <= d <= 15:
            sm_true += 0.15
        if 28 <= d <= 31:
            sm_true += 0.12
        # Sensor drifts after day 35
        drift = 0.05 * (d - 35) / 10 if d > 35 else 0
        reading = sm_true + drift + random.gauss(0, 0.01)
        sensor_data.append({
            "day": day,
            "soil_moisture": round(max(0, min(1, reading)), 3),
            "depth_cm": 10,
        })
    _write(os.path.join(plot_dir, "sensor_data.json"), sensor_data)

    # Expected
    _write(os.path.join(plot_dir, "expected.json"), {
        "description": "Irrigated: SM response to events, sensor drift late",
        "final_state_ranges": {
            "lai_proxy": [1.5, 6.0],
            "sm_0_10": [0.10, 0.45],
            "phenology_stage": [1.0, 3.0],
        },
        "event_response_invariants": {
            "irrigation_day_12": {
                "sm_increase_within_2_days": True,
                "sm_increase_range": [0.05, 0.25],
            },
            "irrigation_day_28": {
                "sm_increase_within_2_days": True,
                "sm_increase_range": [0.04, 0.20],
            },
        },
        "sensor_drift_invariants": {
            "drift_detected_after_day_35": True,
            "reliability_decreases_late": True,
        },
        "audit_invariants": {
            "health_grade_range": ["A", "C"],
        },
    })


# ============================================================================
# Plot 3: Rainfall Mismatch — Convective storm conflicts
# ============================================================================

def generate_rain_mismatch():
    plot_dir = os.path.join(GOLDEN_DIR, "plot_rain_mismatch")
    print("\n=== Plot 3: Rainfall Mismatch (45 days) ===")

    _write(os.path.join(plot_dir, "plot.json"), {
        "plot_id": "golden_rain_mismatch",
        "lat": 35.50, "lng": -1.30,
        "area_ha": 3.0,
        "crop": "barley",
        "sowing_date": "2024-02-01",
        "zones": ["plot"],
        "utm_zone": "30N",
    })

    # Weather: 3 convective storm events that SAR doesn't confirm
    weather = []
    storm_days = [12, 24, 36]  # Must align with SAR days (d % 6 == 0)
    for d in range(45):
        day = f"2024-03-{d+1:02d}" if d < 31 else f"2024-04-{d-30:02d}"
        rain = 0
        if d in storm_days:
            rain = 25 + random.gauss(0, 5)  # Heavy convective
        elif d % 7 == 0:
            rain = 5 + random.gauss(0, 2)  # Light frontal
        weather.append({
            "day": day,
            "temp_max": round(18 + d * 0.1 + random.gauss(0, 2), 1),
            "temp_min": round(8 + d * 0.05 + random.gauss(0, 1.5), 1),
            "precipitation": max(0, round(rain, 1)),
            "et0": round(2.5 + d * 0.02 + random.gauss(0, 0.3), 1),
        })
    _write(os.path.join(plot_dir, "weather_daily.json"), weather)

    # Sentinel-2: mostly clear
    s2_obs = []
    for d in range(45):
        day = weather[d]["day"]
        if d % 5 != 0:
            continue
        ndvi = 0.25 + d * 0.012 + random.gauss(0, 0.02)
        ndmi = 0.15 + d * 0.005 + random.gauss(0, 0.015)
        s2_obs.append({
            "day": day,
            "ndvi": round(min(0.85, ndvi), 3),
            "ndmi": round(ndmi, 3),
            "cloud_probability": 0.05,
            "valid_fraction": 0.95,
            "is_cloudy": False,
        })
    _write(os.path.join(plot_dir, "sentinel2.json"), s2_obs)

    # Sentinel-1: SAR shows dry on storm days (storm missed the plot)
    s1_obs = []
    for d in range(45):
        day = weather[d]["day"]
        if d % 6 != 0:
            continue
        # SAR says dry even on storm days — the mismatch
        sm_sar = 0.25 + random.gauss(0, 0.03)
        if d in storm_days or (d - 1) in storm_days:
            sm_sar = 0.05  # Very dry — storm clearly missed the plot
        vv = -18.0 + 10 * sm_sar + random.gauss(0, 0.5)  # Tighter noise
        vh = -22.0 + 3 * (0.3 + d * 0.01) + random.gauss(0, 1.2)
        s1_obs.append({
            "day": day,
            "vv": round(vv, 2),
            "vh": round(vh, 2),
            "incidence_angle": 37 + random.gauss(0, 2),
        })
    _write(os.path.join(plot_dir, "sentinel1.json"), s1_obs)

    # No irrigation events
    _write(os.path.join(plot_dir, "events.json"), [
        {"day": "2024-02-01", "type": "sowing", "crop": "barley"},
    ])

    # Expected
    _write(os.path.join(plot_dir, "expected.json"), {
        "description": "Rain mismatch: convective storms not confirmed by SAR",
        "final_state_ranges": {
            "lai_proxy": [0.5, 6.0],
            "sm_0_10": [0.12, 0.45],
        },
        "conflict_invariants": {
            "rainfall_spatial_mismatch_expected": True,
            "conflict_days_near": storm_days,
            "weather_reliability_decreases": True,
            "weather_reliability_range_after_conflicts": [0.4, 0.95],
        },
        "reliability_invariants": {
            "sentinel1_stays_stable": [0.80, 1.0],
        },
        "audit_invariants": {
            "health_grade_range": ["B", "D"],
            "min_conflict_count": 1,
        },
    })


if __name__ == "__main__":
    print("=" * 60)
    print("Golden Plot Dataset Generator")
    print("=" * 60)
    generate_cloudy_coastal()
    generate_irrigated()
    generate_rain_mismatch()
    print("\n" + "=" * 60)
    print("All 3 golden plots generated ✓")
    print("=" * 60)
