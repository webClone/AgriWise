# Task A20: Python 3.13 UTC Timestamp Deprecation Remediation

## 1. Finding Overview
* **Finding ID:** A20
* **Severity:** **P2 — Runtime Deprecation Warning & Forward Compatibility Risk**
* **Component:** Layer 0 Microclimate, Layer 9 Interface, Layer 10 SIRE
* **Primary Target Files:**
  - [`services/agribrain/layer0/state_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/state_engine.py) (line 104)
  - [`services/agribrain/layer0/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/runner.py) (line 299)
  - [`services/agribrain/layer9_interface/engines/telemetry_collector.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/telemetry_collector.py) (lines 93, 104)
  - [`services/agribrain/layer10_sire/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/runner.py)

---

## 2. Technical Analysis & Code Audit

### The Deprecation Issue
During test suite execution on Python 3.13, pytest repeatedly emits:
```
DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.
Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC) or datetime.datetime.now(timezone.utc).
```
Specifically:
1. In `services/agribrain/layer0/state_engine.py` line 104:
   ```python
   now = run_timestamp or datetime.utcnow()
   ```
2. In `services/agribrain/layer0/runner.py` line 299:
   ```python
   "run_timestamp": (run_timestamp or datetime.utcnow()).isoformat()
   ```
3. In `services/agribrain/layer9_interface/engines/telemetry_collector.py` lines 93, 104:
   ```python
   "timestamp": datetime.utcnow().isoformat() + "Z"
   today = datetime.utcnow().strftime("%Y-%m-%d")
   ```

### Technical Risks
- Creates naive datetime objects that risk timezone confusion when compared against timezone-aware datetimes (`tzinfo=timezone.utc`).
- Will raise fatal `AttributeError` when Python removes `utcnow()` in Python 3.14/3.15.

---

## 3. Implementation Plan

### Step 1: Update Layer 0 State Engine & Runner
In `services/agribrain/layer0/state_engine.py` and `services/agribrain/layer0/runner.py`:
- Replace all `datetime.utcnow()` occurrences with `datetime.now(timezone.utc)`.

### Step 2: Update Layer 9 Telemetry Collector
In `services/agribrain/layer9_interface/engines/telemetry_collector.py`:
```python
from datetime import datetime, timezone

# Line 93:
"timestamp": datetime.now(timezone.utc).isoformat(),
# Line 104:
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
```

---

## 4. Verification & Acceptance Criteria

1. **Clean Test Run:**
   - Execute pytest on Layer 0 and Layer 9 test suites; assert zero `DeprecationWarning` regarding `datetime.utcnow()`.
