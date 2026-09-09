# Task A22: Layer 0.5 ASMAE PlotWorldlineService Migration to CanonicalWorldlineService

## 1. Finding Overview
* **Finding ID:** A22
* **Severity:** **P2 — Subsystem Architecture Deprecation & Legacy Duplication**
* **Component:** Layer 0.5 ASMAE & World Model
* **Primary Target Files:**
  - [`services/agribrain/layer05_asmae/history/worldline_service.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/history/worldline_service.py)
  - [`services/agribrain/layer05_asmae/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/runner.py) (line 173)
  - [`services/agribrain/world_model/canonical_worldline.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/canonical_worldline.py)

---

## 2. Technical Analysis & Code Audit

### The Deprecation Issue
In `services/agribrain/layer05_asmae/history/worldline_service.py`:
```python
warnings.warn(
    "layer05_asmae.history.worldline_service.PlotWorldlineService is deprecated. "
    "Use services.agribrain.world_model.canonical_worldline.CanonicalWorldlineService.",
    DeprecationWarning,
    stacklevel=2,
)
```
In `services/agribrain/layer05_asmae/runner.py` line 173:
```python
PlotWorldlineService().hydrate_context(plot_id, context)
```
Calls to `PlotWorldlineService` still persist in production ASMAE runtime code, maintaining duplicate database interaction logic and generating deprecation warnings during regression runs.

---

## 3. Implementation Plan

### Step 1: Replace Usage in ASMAE Runner
In `services/agribrain/layer05_asmae/runner.py`:
- Replace `from .history.worldline_service import PlotWorldlineService` with:
  ```python
  from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService
  ```
- Use `CanonicalWorldlineService().hydrate_context(plot_id, context)`.

### Step 2: Harmonize Test Fixtures
Update `services/agribrain/layer05_asmae/tests/` to consume `CanonicalWorldlineService` directly.

---

## 4. Verification & Acceptance Criteria

1. **Clean Test Run:**
   - Execute `py -3 -m pytest services/agribrain/layer05_asmae/tests/`.
   - Assert zero `DeprecationWarning: PlotWorldlineService is deprecated`.
