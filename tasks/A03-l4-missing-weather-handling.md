# Task A03: Missing Weather Represented as Benign Hydrology

## 1. Finding Overview
* **Finding ID:** A03
* **Severity:** **P0 — Unsafe Failure Semantic / Masked Physical Risk**
* **Component:** Layer 4 Nutrients (Soil Water Balance Engine & Runner)
* **Primary Target Files:**
  - [`services/agribrain/layer4_nutrients/soil_water_balance/engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/soil_water_balance/engine.py) (lines 217–224)
  - [`services/agribrain/layer4_nutrients/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/runner.py)

---

## 2. Technical Analysis & Code Audit

### The Code Flaw
In `services/agribrain/layer4_nutrients/soil_water_balance/engine.py`, lines 217–224:
```python
for day_idx, day_weather in enumerate(weather_timeseries):
    et0 = day_weather.get("et0_mm")
    rain = day_weather.get("precip_mm")
    
    if et0 is None or rain is None:
        daily_stress.append(0.0)      # <-- 0.0 = ZERO WATER STRESS!
        daily_leaching.append(0.0)    # <-- 0.0 = ZERO LEACHING RISK!
        continue
```
In `services/agribrain/layer4_nutrients/soil_water_balance/engine.py`, line 240:
```python
is_water_limiting = any(s > 0.5 for s in daily_stress) # returns False!
```

### Reproducing Probe:
When an empty or partial weather record is supplied (e.g. API timeout, missing precipitation sensor):
1. `daily_stress` receives `0.0`.
2. `is_water_limiting` evaluates to `False`.
3. `cumulative_leaching_risk` evaluates to `"LOW"`.
4. Downstream nutrient advisory consumes `is_water_limiting=False` as proof of **abundant, optimal soil moisture**.

---

## 3. Agronomical & Decision Impact
- **Disguised Crop Stress:** A severe drought during an API or station outage is reported as **zero stress**.
- **Dangerous Agronomic Action:** The system recommends heavy basal or top-dressing nitrogen fertilization on the false presumption that soil moisture is adequate for nutrient dissolution and root absorption. In reality, applying dry fertilizer to severely stressed crops under drought conditions causes root plasmolysis and severe crop desiccation.
- **Violation of Scientific Integrity:** Missing evidence must *never* be converted into positive evidence of favorable conditions.

---

## 4. Implementation Plan

### Step 1: Explicitly Track Missing Hydrological Days
Refactor the loop in `services/agribrain/layer4_nutrients/soil_water_balance/engine.py`:
- Introduce `missing_weather_days: int = 0`.
- Instead of appending `0.0`, record an explicit `None` or an uncertainty interval.
- Calculate conservative bounds or flag the physical state as indeterminable:
```python
missing_weather_count = 0
valid_stress = []

for day_idx, day_weather in enumerate(weather_timeseries):
    et0 = day_weather.get("et0_mm")
    rain = day_weather.get("precip_mm")
    
    if et0 is None or rain is None:
        missing_weather_count += 1
        daily_stress.append(None)
        daily_leaching.append(None)
        continue
    
    # ... compute normal daily balance ...
    valid_stress.append(ks_stress)
    daily_stress.append(ks_stress)
```

### Step 2: Fail-Closed Stress Evaluation
In `SoilWaterBalanceResult`:
```python
if missing_weather_count > 0:
    weather_coverage_ratio = (len(weather_timeseries) - missing_weather_count) / max(1, len(weather_timeseries))
    if weather_coverage_ratio < 0.70:
        # Cannot reliably evaluate water limitation
        is_water_limiting = None  # Explicitly Unknown
        hydration_confidence = 0.0
        degradation_mode = "MISSING_WEATHER_DATA"
    else:
        # Impute conservative stress and mark degraded
        is_water_limiting = any(s is not None and s > 0.5 for s in daily_stress)
        hydration_confidence = round(weather_coverage_ratio, 2)
        degradation_mode = "PARTIAL_WEATHER_DATA"
```

### Step 3: Enforce Degradation in Layer 4 Runner
In `services/agribrain/layer4_nutrients/runner.py`:
- If `swb_result.is_water_limiting is None` or `hydration_confidence < 0.5`:
  - Tag Layer 4 output with `LayerStatus.DEGRADED`.
  - Append `"HYDROLOGY_WEATHER_GAP"` to `missing_drivers`.
  - Block autonomous top-dress recommendations until physical soil moisture is confirmed.

---

## 5. Verification & Test Plan

### Automated Tests
1. **Empty Weather Input Test:**
   - Supply `weather_timeseries = [{}, {}, {}]`.
   - Assert `swb_result.is_water_limiting is None` (or raises explicit degradation, NOT `False`).
   - Assert `swb_result.degradation_mode == "MISSING_WEATHER_DATA"`.
2. **Partial Weather Gaps:**
   - Supply 7-day timeseries with days 3 and 4 missing (`et0=None`).
   - Assert `hydration_confidence <= 0.75`.
   - Verify that Layer 4 runner reports `status == LayerStatus.DEGRADED`.

---

## 6. Progress Tracking Checklist
- [ ] Missing weather loop modified to record `None` and track gap count.
- [ ] `is_water_limiting` updated to fail-closed (`None` when data insufficient).
- [ ] Layer 4 runner updated to emit `MISSING_WEATHER_DATA` degradation.
- [ ] Prescriptive fertilizer blocker hooked up to unknown hydration status.
- [ ] Automated regression tests written and passing.
