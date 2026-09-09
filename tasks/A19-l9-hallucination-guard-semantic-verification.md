# Task A19: Layer 9 Hallucination Guard Context & Unit-Blind Matching

## 1. Finding Overview
* **Finding ID:** A19
* **Severity:** **P1 — Post-Generation Verification Defect & False Scientific Grounding**
* **Component:** Layer 9 Interface (Hallucination Guard)
* **Primary Target File:** [`services/agribrain/layer9_interface/hallucination_guard.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/hallucination_guard.py) (lines 181–185)

---

## 2. Technical Analysis & Code Audit

### The Code Flaw
In `services/agribrain/layer9_interface/hallucination_guard.py`, lines 58–101:
```python
# Extract all numbers from actions, rates, outcomes, diagnoses into a single set
numbers: Set[float] = set()
for action in l9_input.get("actions", []):
    ...
    for key in ("priority_score", "recommended", "min_safe", "max_safe"):
        val = action.get(key)
        if val is not None and isinstance(val, (int, float)):
            numbers.add(round(float(val), 2))
```
In `services/agribrain/layer9_interface/hallucination_guard.py`, lines 181–185:
```python
# DEFECT: Checks whether the extracted number is close to ANY number in the pool
if val > 0 and val not in self.upstream_numbers:
    # Check if close to any upstream number (10% tolerance)
    close = any(abs(val - u) / max(abs(u), 0.01) < 0.1
                for u in self.upstream_numbers if u != 0)
    if not close:
        flags.append(HallucinationFlag(claim_type="number", claim_value=str(val), ...))
```

### Reproducing Probe:
1. Upstream data contains:
   - Max temperature = $25^\circ\text{C}$ (from weather)
   - Wind speed = $18\text{ km/h}$
   - Soil moisture = $30\%$
   - Allowed nitrogen rate = $80\text{ kg/ha}$
2. The LLM generates a catastrophic hallucination:
   *"Apply 25 kg/ha of Atrazine herbicide across the entire field."*
3. The guard extracts: `val = 25.0` with unit `kg/ha`.
4. It iterates over `self.upstream_numbers` (which contains `25.0` from temperature).
5. `25.0 in self.upstream_numbers` evaluates to `True`!
6. **Result:** The fabricated chemical recommendation passes the guard without flags because a completely unrelated weather temperature happened to be $25^\circ\text{C}$.

---

## 3. Agronomical & Systemic Impact
- **Illusion of Safety:** The presence of a "Hallucination Guard" provides a false sense of security that LLM advice is grounded in upstream physics.
- **Dangerous Chemical & Operational Advice:** A farmer could receive an unauthorized herbicide application rate that slips past the guard simply because the number matches an upstream humidity, slope, or date number.

---

## 4. Implementation Plan

### Step 1: Replace Flat Float Set with Structured Fact Registry
In `services/agribrain/layer9_interface/hallucination_guard.py`:
- Store upstream facts as typed, scoped claims:
```python
@dataclass(frozen=True)
class GroundedFact:
    domain: str         # "RATE", "WEATHER", "DIAGNOSIS", "OUTCOME"
    variable: str       # "nitrogen_rate", "temp_max", "disease_prob", "wind_speed"
    value: float
    unit: str           # "kg/ha", "°C", "%", "km/h"
    action_type: Optional[str] = None
    tolerance: float = 0.05
```

### Step 2: Extract Contextualized Semantic Claims from LLM Output
Instead of extracting raw isolated digits via `r'\b(\d+\.?\d*)\s*(?:kg|mm|L|t|ha|%|°)'`:
- Parse the surrounding sentence to extract both the **unit** and the **semantic subject**:
```python
# Example: match rates with units and target chemical/nutrient
RATE_PATTERN = r'(?:apply|rate of|dose of)\s+(\d+\.?\d*)\s*(kg/ha|L/ha|g/ha)'
WEATHER_PATTERN = r'(?:temperature|temp of|wind of)\s+(\d+\.?\d*)\s*(°C|km/h|m/s)'
```

### Step 3: Enforce Dimensional & Domain Matching
```python
def _validate_numeric_claim(self, val: float, unit: str, domain: str, action_type: str = None) -> bool:
    """Only accept the number if a matching upstream fact exists with identical unit and domain."""
    matching_facts = [
        f for f in self.grounded_facts
        if f.domain == domain and f.unit.lower() == unit.lower()
    ]
    if action_type:
        matching_facts = [f for f in matching_facts if f.action_type == action_type]
        
    for fact in matching_facts:
        if abs(val - fact.value) / max(abs(fact.value), 0.01) <= fact.tolerance:
            return True # Legitimate match
            
    return False # Hallucination: number does not exist within this physical dimension!
```

---

## 5. Verification & Test Plan

### Automated Tests
1. **Cross-Dimensional Hallucination Test:**
   - Upstream: `temp_max = 25°C`, `rate = 80 kg/ha`.
   - Text: `"Apply 25 kg/ha of urea"`.
   - Call `guard.validate(text)`.
   - Assert `val=25` is flagged as an ungrounded hallucination (unit/rate mismatch).
2. **Valid Grounded Rate Test:**
   - Text: `"Apply 80 kg/ha of urea"`.
   - Assert no hallucination flags.

---

## 6. Progress Tracking Checklist
- [ ] Flat float set replaced with `GroundedFact` registry binding variable, unit, and domain.
- [ ] Unit and context parsing implemented in `_check_numbers`.
- [ ] Cross-dimensional matching vulnerability eliminated.
- [ ] Automated hallucination detection tests written and passing.
