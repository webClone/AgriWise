# Task A13: Layer 8 Action Confirmation Under Incomplete Weather

## 1. Finding Overview
* **Finding ID:** A13
* **Severity:** **P0 — Agronomic & Legal Liability Risk**
* **Component:** Layer 8 Prescriptive (Constraint Scheduler)
* **Primary Target File:** [`services/agribrain/layer8_prescriptive/scheduler.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/scheduler.py) (lines 141–187)

---

## 2. Technical Analysis & Code Audit

### The Code Flaw
In `services/agribrain/layer8_prescriptive/scheduler.py`, lines 148–153:
```python
for i in range(scan_days):
    day_fc = forecast[i] if i < len(forecast) else {}
    candidate_date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
    
    day_blocked = False
    day_reasons: List[str] = []
    
    # Check weather constraints
    rain = day_fc.get("precip_mm") or day_fc.get("precipitation") or 0
    wind = day_fc.get("wind_speed") or day_fc.get("wind_kmh") or 0
    temp_max = day_fc.get("temp_max") if day_fc.get("temp_max") is not None else 25
    temp_min = day_fc.get("temp_min") if day_fc.get("temp_min") is not None else 10
```

### Reproducing Probe:
1. An allowed spray action (e.g. `ActionType.SPRAY_FUNGICIDE`) is passed to `schedule_actions`.
2. Spray constraints in `WEATHER_CONSTRAINTS` specify: `max_wind_kmh: 15`, `max_rain_mm: 1.0`, `min_temp_c: 5`, `max_temp_c: 30`.
3. An empty forecast dict is provided: `forecast = [{}]` (e.g. forecast API unavailable or returned incomplete payload).
4. The scheduler extracts:
   - `rain = 0` ($0 \le 1.0$)
   - `wind = 0` ($0 \le 15$)
   - `temp_max = 25` ($25 \le 30$)
   - `temp_min = 10` ($10 \ge 5$)
5. `day_blocked` evaluates to `False`.
6. The action is marked **`ScheduleStatus.CONFIRMED`** for immediate application!

### Date Alignment Defect:
Line 143 calculates `candidate_date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")`.
It completely ignores any explicit date field on `day_fc` (e.g. `day_fc.get("date")`). If the forecast array has missing days or non-consecutive intervals, dates become desynchronized from the actual meteorological forecast.

---

## 3. Agronomical & Legal Liability Impact
- **Chemical Drift & Environmental Contamination:** Spraying pesticides or herbicides under unknown wind conditions is illegal in most agricultural jurisdictions. If a 50 km/h wind gale is blowing during a forecast outage, the scheduler declares calm conditions ($0\text{ km/h}$) and confirms the spray, causing spray drift onto neighboring crops or watercourses.
- **Wash-off Loss:** A heavy rainstorm scheduled for tomorrow will wash off expensive systemic fungicides if treated as $0\text{ mm}$ rain.

---

## 4. Implementation Plan

### Step 1: Enforce Strict Weather Data Presence for Weather-Sensitive Actions
In `services/agribrain/layer8_prescriptive/scheduler.py`:
- Differentiate between "calm verified weather" ($0\text{ km/h}$) and "missing/unrecorded weather" (`None`).
- If an action specifies weather constraints, each required variable must be explicitly present and finite:
```python
# Check whether weather data exists for this day
is_weather_missing = False
missing_fields = []

for req_field, fallback_keys in [("rain", ["precip_mm", "precipitation"]), ("wind", ["wind_speed", "wind_kmh"])]:
    val = None
    for k in fallback_keys:
        if k in day_fc and day_fc[k] is not None:
            val = float(day_fc[k])
            break
    if val is None:
        is_weather_missing = True
        missing_fields.append(req_field)

if is_weather_missing:
    day_blocked = True
    day_reasons.append(f"missing_weather_data({','.join(missing_fields)})")
```

### Step 2: Validate Forecast Dates
Verify that `day_fc` date matches `candidate_date`:
```python
fc_date_str = day_fc.get("date")
if fc_date_str:
    candidate_date = fc_date_str
```

### Step 3: Handle Schedule Status Fail-Closed
If no feasible day with complete weather is found in the planning horizon:
- Return `ScheduleStatus.BLOCKED` with `blocking_constraints=["insufficient_forecast_data"]`.
- Or `ScheduleStatus.TENTATIVE` requiring manual agronomist confirmation before spraying.

---

## 5. Verification & Test Plan

### Automated Regression Tests
Create `tests/test_a13_prescriptive_weather.py`:
1. **Empty Forecast Test:**
   - Call `schedule_actions` with a spray card and `forecast = [{}]`.
   - Assert action status is `ScheduleStatus.BLOCKED` or `TENTATIVE`.
   - Assert `weather_ok == False`.
   - Assert blocking constraint contains `missing_weather_data`.
2. **Missing Wind Field Test:**
   - Call with `forecast = [{"precip_mm": 0.0, "temp_max": 20, "temp_min": 10}]` (missing wind).
   - Assert spray action is NOT confirmed.

---

## 6. Progress Tracking Checklist
- [ ] Fallback default values ($0\text{ km/h}$, $0\text{ mm}$) removed for missing weather records.
- [ ] Strict presence check implemented for required action constraint variables.
- [ ] Forecast date binding checked against candidate dates.
- [ ] Fail-closed status (`BLOCKED` / `TENTATIVE`) enforced when weather is incomplete.
- [ ] Automated regression tests written and passing.
