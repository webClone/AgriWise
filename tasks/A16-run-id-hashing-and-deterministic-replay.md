# Task A16: Run Identity Pre-Acquisition Hashing & String Hash Instability

## 1. Finding Overview
* **Finding ID:** A16
* **Severity:** **P1 — Scientific Reproducibility & Deterministic Replay Defect**
* **Component:** Orchestrator Hashing Engine & Layer 7 Climate Resilience Engine
* **Primary Target Files:**
  - [`services/agribrain/orchestrator_v2/hashing.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/hashing.py) (lines 33–53)
  - [`services/agribrain/layer7_planning/engines/ccr_resilience.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/ccr_resilience.py) (line 112)

---

## 2. Technical Analysis & Code Audit

### Defect 1: Random String Hashing in Climate Monte Carlo Simulation
In `services/agribrain/layer7_planning/engines/ccr_resilience.py`, line 112:
```python
# Seed random state deterministically based on profile display name to keep run reproducible
rng = random.Random(hash(profile.display_name))
```
- In Python 3, `hash(str)` uses SipHash-2-4 with a per-process randomized seed (`PYTHONHASHSEED`), which changes on every Python process launch.
- If process A evaluates `"Maize"`, `hash("Maize")` might return `283918274`.
- If worker B or a restarted API container evaluates `"Maize"`, `hash("Maize")` might return `-928371948`.
- **Result:** Two runs with identical inputs produce **different Monte Carlo heat/frost vulnerability probabilities** simply because they ran in different worker processes.

---

### Defect 2: Pre-Acquisition Fallback Hashes Parameter Dicts, Not Data
In `services/agribrain/orchestrator_v2/hashing.py`, lines 46–48:
```python
"scene_manifest": _get_hash("scene_manifest_hash", inputs.date_range),
"weather": _get_hash("weather_set_hash", {"plot": inputs.plot_id, "dates": inputs.date_range}),
```
- `generate_orchestrator_run_id` executes *before* satellite imagery or weather data are acquired from upstream APIs.
- When `weather_set_hash` is not supplied up-front, the fallback hashes `{"plot": inputs.plot_id, "dates": inputs.date_range}`.
- If weather values change on the provider's server (e.g. ECMWF updates rainfall from $0\text{ mm}$ to $50\text{ mm}$), the input parameters remain identical, producing the **exact same run ID**! The new run overwrites the previous run record in storage despite operating on different physical weather data.
- Tenant ID, farm ID, and caller intent are omitted from the hash input dictionary.

---

## 3. Agronomical & Scientific Impact
- **Non-Reproducible Audit Trails:** Regulators or agronomists re-running a season plan cannot reproduce the exact same resilience score or DAG recommendations.
- **Cache Poisoning:** If runs are deduplicated by Run ID, a run with outdated weather blocks an update with fresh storm forecasts.

---

## 4. Implementation Plan

### Step 1: Replace Python `hash()` with Deterministic SHA-256 Integer
In `services/agribrain/layer7_planning/engines/ccr_resilience.py`, line 112:
```python
import hashlib

# Deterministic cross-process seed via SHA-256
seed_int = int(hashlib.sha256(profile.display_name.encode("utf-8")).hexdigest()[:8], 16)
rng = random.Random(seed_int)
```

### Step 2: Separate Request ID from Scientific Run Identity
In `services/agribrain/orchestrator_v2/`:
1. **Request ID:** Generated at entry point (`AGB-REQ-{uuid4()[:8]}`).
2. **Scientific Run Manifest Hash:** Computed *after* data acquisition in `run_orchestrator`, binding:
   - SHA-256 of fetched weather records.
   - SHA-256 of ingested scene raster arrays.
   - Tenant ID, Farm ID, Plot ID, Intent, Model versions, and Policy snapshot.
```python
# In orchestrator_v2/hashing.py
input_data = {
    "tenant_id": getattr(inputs, "tenant_id", "default"),
    "plot_id": inputs.plot_id,
    "intent": getattr(inputs, "intent", "FULL"),
    "weather_data_sha256": _compute_buffer_sha256(weather_payload),
    "scene_manifest_sha256": _compute_buffer_sha256(scene_payload),
    "model_versions": layer_versions,
}
```

---

## 5. Verification & Test Plan

### Automated Tests
1. **Cross-Process Determinism Test:**
   - Execute Monte Carlo in `ccr_resilience.py` in two separate subprocesses (`py -c "..."`).
   - Assert `p_heat`, `p_frost`, and `p_disease` are identical to 6 decimal places.
2. **Data-Sensitive Run ID Test:**
   - Generate Run ID with weather dataset A.
   - Generate Run ID with weather dataset B (same plot, same dates, but different rainfall values).
   - Assert `run_id_A != run_id_B`.

---

## 6. Progress Tracking Checklist
- [ ] Python's `hash()` replaced with `hashlib.sha256` integer in `ccr_resilience.py`.
- [ ] Cross-process Monte Carlo determinism verified.
- [ ] Request ID separated from Scientific Manifest Hash in Orchestrator.
- [ ] Tenant ID and Intent bound to run identity.
- [ ] Automated regression tests passing.
