# Task A23: Layer 2 Crop Phenology & Dynamic Kcb Stage Alignment

## 1. Finding Overview
* **Finding ID:** A23
* **Severity:** **P1 — Agronomical Accuracy & Multi-Crop Generalization Defect**
* **Component:** Layer 2 Vegetation & Layer 3 Water / Layer 4 Nutrients
* **Primary Target Files:**
  - [`services/agribrain/layer2_veg_int/growth_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_veg_int/growth_engine.py)
  - [`services/agribrain/scientific_contracts/crop_phenology.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/scientific_contracts/crop_phenology.py)
  - [`services/agribrain/layer3_water/crop/crop_coefficient.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/crop/crop_coefficient.py)

---

## 2. Technical Analysis & Code Audit

### The Agronomical Problem
Across AgriBrain:
- Layer 2 tracks vegetative vigor (NDVI, SAVI, NDRE, LAI) and estimates phenological growth stages (e.g. `initial`, `vegetative`, `flowering`, `yield_formation`, `ripening`).
- In `layer4_nutrients/soil_water_balance/engine.py` line 227:
  ```python
  stage = "vegetative"
  if stages and day_idx < len(stages):
      stage = stages[day_idx]
  kcb = get_kcb(crop_type, stage)
  ```
- *The Gap:* If `crop_type` is unmapped or string formatting differs (`"WHEAT"` vs `"durum_wheat"`), `get_kcb()` silently falls back to default reference values without logging or raising an uncertainty flag.
- Phenological degree-day accumulation ($\text{GDD} = \sum \max(0, T_{\text{mean}} - T_{\text{base}})$) is not synchronized between Layer 2 and Layer 3, leading to staggered stage transitions.

---

## 3. Implementation Plan

### Step 1: Centralize Canonical Crop Variety Taxonomy
In `services/agribrain/scientific_contracts/crop_phenology.py`:
- Map all 14 commercial crop varieties (Durum Wheat, Soft Wheat, Barley, Olive, Citrus, Tomato, Potato, Date Palm, Table Grape, Wine Grape, Apple, Onion, Chickpea, Alfalfa).
- Export standard GDD base temperatures ($T_{\text{base}}$) and maximum cutoffs ($T_{\text{upper}}$).

### Step 2: Unify `get_kcb()` Lookup Function
In `services/agribrain/layer3_water/crop/crop_coefficient.py`:
- Support normalized lookup with aliases.
- Return explicit `is_exact_match: bool` and fallback uncertainty inflation.

---

## 4. Verification & Acceptance Criteria

1. **Crop Variety Coverage Test:**
   - Query all 14 supported crop varieties across all 4 FAO growth stages; assert zero unmapped fallbacks.
2. **GDD Synchronization Test:**
   - Compare Layer 2 phenology stage transition with Layer 3 $K_{cb}$ step; assert 0 days phase misalignment.
