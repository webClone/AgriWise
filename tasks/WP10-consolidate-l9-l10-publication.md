# Work Package 10: Consolidate L9/L10 Publication

## 1. Executive Summary & Objective
Layers 9 (Interface / Natural Language Explanation) and 10 (SIRE / Spatial Surface Rasterization) form the external publication surface of AgriBrain. In an agricultural intelligence system, user-facing text, interactive map surfaces, and machine-executable tasks must maintain complete mathematical and semantic alignment.
Currently, several publication vulnerabilities exist:
1. **L9 Text Hallucination & Resolution**: L9 LLM generation can resolve unidentifiable agronomic conflicts in conversational text (e.g. asserting that nitrogen deficiency is definitely present when L2 marked it unresolved), fabricating certainty that does not exist in the scientific ledger.
2. **Spatial Resolution Conflation in L10**: High-resolution display surfaces ($1\text{m}$ rendering grids) are produced by interpolating coarse satellite data ($10-20\text{m}$ Sentinel pixels) or scalar field-level averages. The system does not strictly distinguish native observation resolution, effective physical resolution, and display interpolation grids.
3. **Proxy Visualization Treated as Evidence**: Scalar-to-spatial smoothing masks are occasionally consumed downstream as if they represented direct spatial observations.

Work Package 10 consolidates L9 and L10 into strictly grounded publication layers governed by immutable receipts and clear spatial resolution metadata.

---

## 2. Affected Subsystems & Source References
- **Layer 9 Interface**: [`services/agribrain/layer9_interface/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/).
  - `hallucination_guard.py`: Semantic verification of generated LLM claims.
  - `prompts/`: System prompts for agronomic explanations.
- **Layer 10 SIRE Runner**: [`services/agribrain/layer10_sire/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/runner.py).
- **Layer 10 Surfaces**: [`services/agribrain/layer10_sire/surfaces/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/surfaces/).
- **Surface Contracts**: [`services/agribrain/layer10_sire/contracts/surface_contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/contracts/surface_contracts.py).

---

## 3. Root Cause & Defect Analysis

### 3.1 Conversational Resolution of Unresolved Diagnoses in L9
When Layer 2 and the Diagnostic Tribunal mark a stress condition as `UNRESOLVED` (e.g. water deficit vs root pathogen having equal likelihood), L9's natural language generation can hallucinate a definitive diagnosis to provide a helpful answer to the user. Natural language text must never resolve an ambiguity that the mathematical tribunal left open.

### 3.2 Display Resolution vs Physical Grounding in L10
When generating a $1\text{m} \times 1\text{m}$ GeoTIFF surface of soil moisture:
- The underlying physical observation comes from Sentinel-1 ($20\text{m}$ resolution) or a single point probe.
- Bilinear or spline interpolation over a digital elevation model produces a visually smooth $1\text{m}$ raster.
- Without explicit provenance masks, downstream users or automated sprayers interpret the $1\text{m}$ variation as measured meter-scale heterogeneity.

---

## 4. Implementation Specification

### 4.1 Step 1: Enforce Structured Claim Grounding in L9
1. In `services/agribrain/layer9_interface/hallucination_guard.py`:
   - Parse all numerical assertions (rates, dates, areas, probabilities) and diagnoses from the generated natural language response.
   - Cross-reference every assertion against the `ActionAuthorization` and `TribunalReceipt`.
   - If the LLM generates a rate that differs from the authorized prescription by $> 0.1\%$, or asserts a stress state marked `UNRESOLVED`, the guard rejects the text and replaces it with a structured fallback template derived directly from the receipts.
2. Forbid natural language advice from recommending actions that were rejected or deferred by L8 policy.

### 4.2 Step 2: Formalize Resolution Metadata in L10 Surfaces
1. In `services/agribrain/layer10_sire/contracts/surface_contracts.py`, update `SurfaceArtifact`:
   ```python
   @dataclass(frozen=True)
   class SurfaceArtifact:
       surface_id: str
       semantic_type: SurfaceType
       grid_shape: Tuple[int, int]         # (H, W)
       display_resolution_m: float         # E.g. 1.0 m
       native_resolution_m: float          # E.g. 10.0 m or 20.0 m
       effective_resolution_m: float       # Physical resolving limit
       observed_mask: List[List[bool]]     # True where direct observations exist
       inferred_mask: List[List[bool]]     # True where values are interpolated/modeled
       grounding_class: GroundingClass     # MEASURED_NATIVE, INTERPOLATED_PROXY, SYNTHETIC
       values: List[List[float]]
       palette_id: str
       provenance_hash: str
   ```
2. For every generated surface, output both the data raster and the binary `observed_mask`.

### 4.3 Step 3: Reclassify Spatial Modulations as Visualization Proxies
1. Strictly tag all rasters created by modulating field-level scalars with elevation or soil type as `GroundingClass.INTERPOLATED_PROXY`.
2. Prohibit `INTERPOLATED_PROXY` rasters from being used as evidence in data assimilation or variable-rate machine execution.

---

## 5. Verification & Completion Criteria
- **L9 Hallucination Test**: Simulated runs with unresolved stress conditions verify that L9 output explicitly communicates uncertainty and suggests scouting, rather than asserting a single cause.
- **Resolution Transparency**: All Layer 10 surfaces report accurate `native_resolution_m` vs `display_resolution_m`, accompanied by valid observation masks.
- **Cross-Layer Agreement**: Natural language explanations, visual heatmaps, and machine-executable action files exported by a run contain identical numerical quantities and uncertainty qualifiers.

---

## 6. Monograph & Defect Task Traceability
- **Monograph Findings**: Finding #7 (L10 surface path failure), Finding #10 (Surface publication), Finding #12 (Proxy visualization boundaries).
- **Defect Tasks**: [A14-l10-water-surfaces-call-signature.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A14-l10-water-surfaces-call-signature.md), [A19-l9-hallucination-guard-semantic-verification.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A19-l9-hallucination-guard-semantic-verification.md), [A24-l10-sire-display-trace-metrics-initialization.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A24-l10-sire-display-trace-metrics-initialization.md).
- **Phase Tasks**: [P04.2-ground-scientific-explanations-structurally.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P04.2-ground-scientific-explanations-structurally.md).
