# Work Package 01: Repair Deterministic Failures and Explicit Degradation

## 1. Executive Summary & Objective
Work Package 01 targets immediate, deterministic runtime crashes, silent exception swallowing, and ungrounded execution states identified in the architectural review. Currently, several critical execution paths fail deterministically:
1. The Layer 10 (SIRE) water-surface path crashes with a `TypeError` due to mismatched positional and keyword arguments, and fails to find undefined helper functions (`_compute_water_stress_prob` and `_compute_drainage_deficit`), which are then caught silently and counted as skipped surfaces.
2. Layer 5 (Bio Threat Intelligence) evaluates agronomical invariants, catches critical invariant errors, logs them, but returns the output anyway without marking the result as degraded or blocking downstream publication.
3. Backend route authentication and environment identification contain contradictory logic between `internal_service_auth.py` and `app/main.py`, where `ENVIRONMENT=production` fails to be recognized in training routes, leaving active fallback credentials (`dev_admin_token`).
4. Stage execution status and scientific usability are conflated in orchestrator wrappers, allowing degraded or broken scientific outputs to be wrapped as healthy `LayerStatus.OK`.

The objective of WP01 is to eliminate all deterministic failures, eliminate silent exception swallowing on scientific publication paths, normalize environment classification, and introduce a common `StageReceipt` abstraction that cleanly separates operational execution status from scientific usability.

---

## 2. Affected Subsystems & Source References
- **Layer 10 SIRE Runner**: [`services/agribrain/layer10_sire/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/runner.py#L2253-L2262) (Line 2256 call site).
- **Layer 10 Water Surfaces**: [`services/agribrain/layer10_sire/surfaces/water.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/surfaces/water.py#L59-L85) (Line 59 definition and lines 69-71 missing helpers).
- **Layer 5 Bio Runner**: [`services/agribrain/layer5_bio/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer5_bio/runner.py#L540-L552) (Invariant enforcement gate).
- **Orchestrator v2 Runner**: [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py#L3688-L3694) (`_structured_output_status` and status parsing).
- **Internal Service Auth**: [`services/agribrain/app/internal_service_auth.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/app/internal_service_auth.py#L50-L58).
- **App Main Routes**: [`services/agribrain/app/main.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/app/main.py#L4980-L5002) (Training route authentication).

---

## 3. Root Cause & Defect Analysis

### 3.1 Layer 10 Water Surface Signature and Undefined Helpers (Finding #7)
In `services/agribrain/layer10_sire/surfaces/water.py`, the function is defined as:
```python
def generate_water_surfaces(
    inp: Layer10Input,
    l1_data: L1SpatialData,
    l3_data: L3DiagnosticData,
    H: int,
    W: int,
) -> List[SurfaceArtifact]:
```
However, in `services/agribrain/layer10_sire/runner.py` line 2256, the caller invokes:
```python
water_surfaces = generate_water_surfaces(
    l10_input, H, W, l1_data=l1_data, l3_data=l3_data
)
```
The caller passes `l10_input` (position 1), `H` (position 2 -> assigned to `l1_data`), `W` (position 3 -> assigned to `l3_data`), and then provides keyword arguments `l1_data=l1_data` and `l3_data=l3_data`. Python raises:
`TypeError: generate_water_surfaces() got multiple values for argument 'l1_data'`

Even when the signature is corrected, line 69 calls:
```python
prob_grid, grounding_class, basis, prov = _compute_water_stress_prob(inp, l1_data, l3_data, H, W)
```
and line 112 calls `_compute_drainage_deficit`. Neither function exists or is imported in `water.py`. The runner catches the exception with a bare `except Exception:` and increments `skipped += 2`, hiding the defect completely while returning an incomplete set of surfaces without provenance or explanation.

### 3.2 Layer 5 Invariant Enforcement Pass-Through (Finding #30)
In `services/agribrain/layer5_bio/runner.py`:
```python
violations = enforce_layer5_invariants(output)
errors = [v for v in violations if v.severity == "error"]
if errors:
    for v in errors:
        logger.error(f"[Layer 5] INVARIANT ERROR: {v.check_name} — {v.description}")
return output
```
When an agronomical invariant is violated (e.g. probability out of bounds, missing evidence traces, contradictory risk categories), the runner merely writes an error to the logger and returns the invalid output unchanged. Upstream orchestrators receive this as a healthy run, which is subsequently published or used in decisions.

### 3.3 Authentication & Environment Inconsistency (Finding #32)
In `app/internal_service_auth.py`, production mode is evaluated via:
```python
env = os.getenv("NODE_ENV", os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development"))).lower()
if env in ("production", "prod", "staging"): ...
```
In `app/main.py` line 4988, the training endpoint checks:
```python
is_prod = os.environ.get("NODE_ENV") == "production" or os.environ.get("ENV") == "production" or os.environ.get("APP_ENV") == "production"
effective_token = admin_token or "dev_admin_token"
```
If a deployment sets `ENVIRONMENT=production`, `internal_service_auth` correctly identifies production, but `main.py` evaluates `is_prod = False`, falling back to `effective_token = "dev_admin_token"`. This allows unauthenticated external callers to trigger model training pipelines using default development tokens.

### 3.4 Conflated Health & Identity Normalization (Finding #5)
The orchestrator's `_structured_output_status()` relies on guessing top-level dictionary keys. If an engine returns health indicators nested in `run_meta` or `data_health`, the orchestrator ignores them and marks the execution `LayerStatus.OK`. Conversely, if an engine uses an alternative run identifier (such as `run_id_l3`), its lineage is lost in the audit trail.

---

## 4. Implementation Specification

### 4.1 Step 1: Repair Layer 10 Water Surface Pipeline
1. Update `services/agribrain/layer10_sire/runner.py` to call `generate_water_surfaces` with explicit keyword arguments or correct positional ordering:
   ```python
   water_surfaces = generate_water_surfaces(
       inp=l10_input,
       l1_data=l1_data,
       l3_data=l3_data,
       H=H,
       W=W,
   )
   ```
2. In `services/agribrain/layer10_sire/surfaces/water.py`, implement the missing functions:
   - `_compute_water_stress_prob(inp, l1_data, l3_data, H, W)`: Extracts spatial root-zone moisture or NDMI from `l1_data` and water stress diagnosis from `l3_data`, computing calibrated grid probabilities and returning `(prob_grid, grounding_class, basis, prov)`.
   - `_compute_drainage_deficit(inp, l1_data, l3_data, H, W)`: Evaluates soil drainage coefficient from static soil properties and rainfall fluxes.
3. Replace silent `try/except: skipped += 2` blocks in `layer10_sire/runner.py` with structured `SurfaceFailure` records containing the surface type, error message, stack trace hash, and degradation reason.

### 4.2 Step 2: Enforce Hard Invariant Gates in Layer 5
1. In `services/agribrain/layer5_bio/runner.py`, when `errors` is non-empty:
   - Mark the output status as degraded or failed:
     ```python
     output.quality_metrics.status = "degraded"
     output.quality_metrics.invariant_violations = [v.to_dict() for v in violations]
     ```
   - If severe invariant violations occur (e.g. invalid probability bounds or falsified evidence links), raise an `InvariantFailureException` or return a `LayerResult` with `LayerStatus.FAILED` and explicit error receipts.
2. In the orchestrator runner, ensure `results[LayerId.L5].status` accurately reflects invariant status and blocks L5 contributions from entering the diagnostic tribunal as valid evidence.

### 4.3 Step 3: Centralize Environment Classification and Eliminate Fallbacks
1. Create a single canonical environment classifier in `services/agribrain/common/environment.py`:
   ```python
   def is_production_environment() -> bool:
       env = (
           os.getenv("NODE_ENV")
           or os.getenv("ENVIRONMENT")
           or os.getenv("APP_ENV")
           or os.getenv("ENV")
           or "development"
       ).lower()
       return env in ("production", "prod", "staging")
   ```
2. Refactor `app/internal_service_auth.py` and `app/main.py` to use `is_production_environment()`.
3. In `app/main.py`:
   ```python
   if is_production_environment():
       if not admin_token:
           raise HTTPException(status_code=500, detail="Server misconfigured: AGRIBRAIN_ADMIN_TOKEN missing")
       effective_token = admin_token
   else:
       effective_token = admin_token or "dev_admin_token"
   ```

### 4.4 Step 4: Standardize StageReceipt Protocol
1. Introduce `StageReceipt` in `services/agribrain/scientific_contracts/stage_receipt.py`:
   - `stage_id: str`
   - `execution_status: str` ("success", "failed", "timeout")
   - `scientific_usability: str` ("usable", "degraded", "unusable")
   - `input_evidence_hashes: Tuple[str, ...]`
   - `output_payload_hash: str`
   - `missing_inputs: List[str]`
   - `degradation_reasons: List[str]`
   - `authority_receipt: AuthorityVector`
   - `invariant_violations: List[Dict[str, Any]]`
2. Update layer wrappers (`_safe_run`) to inspect the engine's `StageReceipt` rather than guessing keys from dictionaries.

---

## 5. Verification & Completion Criteria
1. **Zero Silent Surface Failures**: All Layer 10 surfaces either produce valid GeoTIFF/JSON artifacts with complete provenance or publish an explicit `SurfaceUnavailableReceipt` detailing the scientific reason.
2. **Invariant Gate Test**: Layer 5 invariant errors cause execution to halt or return `LayerStatus.DEGRADED`; invalid outputs are never presented as `LayerStatus.OK`.
3. **Authentication Audit**: Setting `ENVIRONMENT=production` and querying `/v2/crop-model/train` with `X-Admin-Token: dev_admin_token` deterministically returns `403 Forbidden`.
4. **Regression Safety**: All 532 multi-layer tests remain 100% passing.

---

## 6. Monograph & Defect Task Traceability
- **Monograph Findings**: Finding #5 (Stage health and identity normalization), Finding #7 (L10 water surface caller and missing helpers), Finding #30 (L5 invariant enforcement), Finding #32 (Authentication inconsistency).
- **Defect Tasks**: [A14-l10-water-surfaces-call-signature.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A14-l10-water-surfaces-call-signature.md), [A15-orchestrator-and-l10-undefined-variables.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A15-orchestrator-and-l10-undefined-variables.md), [A12-orchestrator-health-and-quality-metrics.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A12-orchestrator-health-and-quality-metrics.md).
- **Phase Tasks**: [P01.1-normalize-layer-returns-and-health.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P01.1-normalize-layer-returns-and-health.md), [P01.2-repair-asmae-scene-and-sire-failures.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P01.2-repair-asmae-scene-and-sire-failures.md).
