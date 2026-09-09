# Task A06: ASMAE Silent Drop of External Scenes (Undefined `resolution_m`)

## 1. Finding Overview
* **Finding ID:** A06
* **Severity:** **P0 — Data Ingestion Failure & Silent Exception Swallowing**
* **Component:** ASMAE / Layer 0.5 (Geometry & External Scene Loader)
* **Primary Target File:** [`services/agribrain/layer05_asmae/geometry/external_scene_loader.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/geometry/external_scene_loader.py) (around line 115)

---

## 2. Technical Analysis & Code Audit

### The Code Defect
In `services/agribrain/layer05_asmae/geometry/external_scene_loader.py`, lines 110–125:
```python
try:
    # Scene construction from external raster / metadata
    scene = ExternalSceneRecord(
        scene_id=scene_id,
        bounds=bounds,
        crs=crs,
        resolution_m=resolution_m,  # <-- NameError: name 'resolution_m' is not defined!
        timestamp=timestamp,
        ...
    )
    scenes.append(scene)
except Exception as e:
    logger.debug(f"Failed to load external scene {scene_id}: {e}")
    # Swallows exception and continues!
```

### Reproducing Probe:
When providing a valid projected GeoTIFF or external drone/satellite raster:
1. Python executes the constructor and encounters `resolution_m`.
2. A `NameError: name 'resolution_m' is not defined` is raised immediately.
3. The broad `except Exception:` catches the error, logs a debug line, and returns an empty list `[]`.
4. The system continues execution with **zero external scenes**, completely oblivious to the fact that user-supplied imagery was uploaded.

---

## 3. Agronomical & Systemic Impact
- **Loss of High-Resolution Imagery:** High-resolution drone orthomosaics, commercial Planet/Sentinel imagery, and spatial soil maps uploaded by agronomists fail to enter ASMAE.
- **Unnoticed Fallback to Coarse Synthetic Data:** ASMAE silently falls back to coarse default resolutions ($10\text{m}$ Sentinel or synthetic priors), losing field-level microzone precision and weed/disease hotspot detection.

---

## 4. Implementation Plan

### Step 1: Extract and Validate `resolution_m` from Scene Metadata
In `services/agribrain/layer05_asmae/geometry/external_scene_loader.py`:
- Extract resolution from metadata, affine transform, or header dict.
- Compute ground sampling distance (GSD) in meters using CRS or default:
```python
# Derive resolution from transform or explicit metadata
res = None
if "resolution_m" in metadata:
    res = float(metadata["resolution_m"])
elif "transform" in metadata and hasattr(metadata["transform"], "a"):
    # Affine transform: pixel width in projected CRS units
    res = abs(float(metadata["transform"].a))
elif "pixel_size" in metadata:
    res = float(metadata["pixel_size"][0])
else:
    # Fallback to standard platform default if unspecified
    res = float(metadata.get("gsd", 10.0))

if res <= 0.0 or math.isnan(res):
    raise ValueError(f"Invalid spatial resolution_m: {res} for scene {scene_id}")

resolution_m = round(res, 3)
```

### Step 2: Separate Geometry Validation Errors from System Crashes
- Replace the broad `except Exception:` with typed error handling:
  - If a scene has unparseable metadata, log a structured warning and record an explicit `SceneAdmissionRejection` receipt containing the rejection reason.
  - Never let a programming `NameError` or `TypeError` masquerade as a normal "no data" condition.

---

## 5. Verification & Test Plan

### Automated Regression Test
Create `tests/test_a06_external_scene_loader.py`:
1. **Valid Raster Loading:**
   - Provide mock external raster metadata with affine transform `a=0.5` (50 cm drone imagery).
   - Call `load_external_scenes()`.
   - Assert `len(scenes) == 1`.
   - Assert `scenes[0].resolution_m == 0.5`.
2. **Missing Metadata Validation:**
   - Provide malformed scene dict.
   - Assert structured `SceneAdmissionRejection` is logged with explicit error.

---

## 6. Progress Tracking Checklist
- [ ] Undefined `resolution_m` variable reference fixed.
- [ ] Robust resolution extraction from affine transform / metadata implemented.
- [ ] Broad exception handler replaced with typed exception handling.
- [ ] Rejection receipts emitted for unparseable scenes.
- [ ] Automated regression tests passing.
