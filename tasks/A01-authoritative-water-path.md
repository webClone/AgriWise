# Task A01: Authoritative Integrated Water Path

## 1. Finding Overview
* **Finding ID:** A01
* **Severity:** **P0 — Architectural Integration Gap**
* **Component:** Orchestrator V2, Layer 3 Decision, Layer 3 Water, Layer 4 Nutrients
* **Primary Target Files:**
  - [`services/agribrain/orchestrator_v2/registry.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/registry.py)
  - [`services/agribrain/layer3_water/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/runner.py)
  - [`services/agribrain/layer4_nutrients/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/runner.py)
  - [`services/agribrain/layer4_nutrients/soil_water_balance/engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/soil_water_balance/engine.py)

---

## 2. Technical Analysis & Code Audit

### The Architectural Problem
AgriBrain currently contains **two completely separate, uncoupled implementations of soil hydrology**:
1. **The Modern Water Engine (`layer3_water/`)**:
   Contains FAO-56 dual $K_c$ partitioning, multi-layer soil hydrology, Kalman data assimilation of moisture probes, and MPC irrigation optimization.
   *However*, `orchestrator_v2/registry.py` lines 30–35 routes `LayerId.L3` exclusively to the legacy diagnostic decision engine:
   ```python
   # services/agribrain/orchestrator_v2/registry.py:32
   LayerSpec(
       layer_id=LayerId.L3,
       runner=run_layer3_decision, # <-- Calls layer3_decision, NOT layer3_water
       ...
   )
   ```
   `layer3_water/runner.py::WaterIntelligenceEngine` has **zero callers** across the production orchestrator.
2. **Layer 4 Nutrients Private Hydrology (`layer4_nutrients/soil_water_balance/`)**:
   Because L3 does not supply an authoritative water balance receipt, `layer4_nutrients/runner.py` instantiates and executes its own private, simplified `SoilWaterBalanceEngine`:
   ```python
   # services/agribrain/layer4_nutrients/runner.py:42
   from layer4_nutrients.soil_water_balance.engine import SoilWaterBalanceEngine
   ...
   swb_result = SoilWaterBalanceEngine.run_daily_balance(...)
   ```
   This means any diagnosis or recommendation generated in L4 and downstream layers is completely divorced from the advanced water physics modeled in `layer3_water`.

---

## 3. Agronomical & Decision Impact
- **Inconsistent Irrigation & Fertilization Recommendations:** A crop may be diagnosed as water-stressed by L3 water physics, while Layer 4's private soil water balance calculates adequate moisture, recommending full granular nitrogen fertilizer that cannot be taken up by dry roots and causes salt scorch.
- **Leaching Disconnect:** L4 estimates deep drainage and nitrogen leaching using its private bucket model, ignoring the multi-layer hydraulic conductivity calculations in `layer3_water`.
- **False Production Claims:** External documentation claims AgriBrain runs an end-to-end multi-layer soil-water balance driving dynamic nutrient uptake, whereas in reality L3 water is an orphaned prototype.

---

## 4. Implementation Plan

> [!IMPORTANT]
> **Precondition:** Do NOT switch `orchestrator_v2/registry.py` to `layer3_water` until **Task A04** (mass balance conservation violation) and **Task A05** (flux update mismatch) are resolved.

### Step 1: Formalize Layer 3 Hydrology Boundary Contract
In `services/agribrain/scientific_contracts/hydrology.py` (or existing `layer3_water/schema.py`), ensure a versioned, immutable `HydrologyStateReceipt` is exported:
```python
@dataclass(frozen=True)
class HydrologyStateReceipt:
    plot_id: str
    timestamp: datetime
    root_zone_depletion_fraction: float  # [0, 1]
    transpiration_constraint_ks: float   # [0, 1]
    daily_deep_percolation_mm: float
    daily_actual_transpiration_mm: float
    daily_actual_evaporation_mm: float
    volumetric_water_content_root_zone: float
    authority_level: str  # "OBSERVED", "ASSIMILATED", "MODELLED"
    quality_status: str   # "HEALTHY", "DEGRADED", "DATA_GAP"
```

### Step 2: Separate Diagnostic Decision from Water Physics in Registry
Separate L3 into two distinct lifecycle stages in Orchestrator V2:
1. `LayerId.L3_WATER` (`layer3_water.runner.run_layer3_water`): Computes physical water state and fluxes.
2. `LayerId.L3_DECISION` (`layer3_decision.runner.run_layer3_decision`): Diagnoses crop stress, weed, pest, and agronomic operational urgency.

Update `orchestrator_v2/schema.py` and `orchestrator_v2/registry.py`:
```python
# orchestrator_v2/registry.py
LayerSpec(
    layer_id=LayerId.L3_WATER,
    runner=run_layer3_water,
    required=True,
    ...
),
LayerSpec(
    layer_id=LayerId.L3_DECISION,
    runner=run_layer3_decision,
    required=True,
    ...
)
```

### Step 3: Refactor Layer 4 to Consume Authoritative Water Receipt
In `services/agribrain/layer4_nutrients/runner.py`:
- Modify `run_layer4_nutrients` signature to accept `l3_water_res: Optional[LayerResult]`.
- If `l3_water_res` is present and healthy, consume its `HydrologyStateReceipt` directly for percolation, evapotranspiration, and root-zone water content.
- Deprecate internal `SoilWaterBalanceEngine` to a strict fallback mode that explicitly marks L4 output as `DEGRADED (FALLBACK_HYDROLOGY)`.

---

## 5. Verification & Test Plan

### Automated Tests
1. **Pipeline Execution Test:** Run `run_orchestrator` end-to-end and verify that:
   - `LayerId.L3_WATER` executes before `LayerId.L4`.
   - `l4_res.output.provenance["hydrology_source"] == "L3_WATER_AUTHORITATIVE"`.
   - Deep percolation value in L4 nutrient leaching matches `l3_water_res.output.fluxes.deep_drainage_mm`.
2. **Fallback Isolation Test:**
   - Execute L4 with `l3_water_res=None`.
   - Assert `l4_res.status == LayerStatus.DEGRADED`.
   - Assert warning log emitted: `"Using degraded fallback soil water balance"`.

---

## 6. Progress Tracking Checklist
- [ ] Task A04 & A05 verified and fixed in `layer3_water`.
- [ ] Contract `HydrologyStateReceipt` published and imported.
- [ ] Orchestrator registry updated to include authoritative `L3_WATER` runner.
- [ ] Layer 4 runner refactored to consume `HydrologyStateReceipt`.
- [ ] Fallback path in Layer 4 tagged with explicit degradation metrics.
- [ ] Unit & regression tests passing.
