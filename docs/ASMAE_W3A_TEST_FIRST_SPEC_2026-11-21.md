# ASMAE W3-A — Layer 1 Confidence RasterRef and Layer 10 Surface Truthfulness

**Date:** 2026-11-21 · **Parent:** Draft PR #32 `64a9f69945d8e3eda2bf33de9ff24e98186c9a17` · **Status:** Specification and deliberately RED tests only. No changes to PR #32.

## W3A-01 — L1 canonical posterior concentration
Source: `services/agribrain/layer1_fusion/raster_ingest.py::ingest_asmae_raster_refs`, near lines 682–701.
- `build_ref()` returns a `RasterRef` object; the current canonical alias branch checks `if ref and isinstance(ref, dict)` and therefore drops this confidence raster.
- Always append the valid class instance when the grid is physically qualified; retain diagnostic channel, `state_update_allowed=False`, `diagnostic_only=True`, and canonical `asmae_posterior_concentration` identity.
- Accept `ASMAE_CONFIDENCE`, `CONFIDENCE_ASMAE`, `ASMAE_POSTERIOR_CONCENTRATION` as aliases but deduplicate to **one** canonical raster when all are present, with deterministic canonical priority.
- If supported, preserve alias identity in explicit metadata/provenance without casting `RasterRef` to dict or creating zero sigma. Geometry, masks, native grid, uncertainty and provenance remain independently qualified.
- Never let confidence/support rasters become 13-state posteriors or fine effective-resolution certification.

## W3A-02 — L10 composite invariant reachability
Source: `services/agribrain/layer10_sire/invariants.py::enforce_layer10_invariants`, near lines 293–325.
- Existing `if not is_asmae: continue` makes the subsequent `COMPOSITE_` invariant checks unreachable. Evaluate composite advisory types **before** any unrelated ASMAE-only branch skip.
- For each `COMPOSITE_` advisory: verify `source_reality="raster_composite_proxy"`, `real_asmae_evidence=False`, `asmae_advisory_evidence=True`, `current_1m_approval_allowed=False`, `authority="experimental_asmae_advisory"`, `state_update_allowed=False`, `prescription_driver_allowed=False`, plus exact grid dimensions.
- A missing/forged field must generate an `INV-COMPOSITE` violation. A legitimate advisory composite should remain displayable without becoming state evidence.
- Preserve existing treatment for ordinary, non-ASMAE surfaces and high-resolution display masks.

## W3A-03 — L10 posterior-concentration support mapping
Source: `services/agribrain/layer10_sire/runner.py`, `asmae_state_gate` around lines 5270–5386.
- Explicit `ASMAE_POSTERIOR_CONCENTRATION` diagnostic support requires current anchored spatial posterior and valid grid/mask; never fall through to `surface_state_requirement_unmapped`.
- Do not use the numeric concentration grid as a proxy for missing statewise posterior sigma, calibration or local authority.
- A supported diagnostic confidence layer may render even where certification is withheld; a stale, missing, unanchored, all-masked or wrong-grid confidence layer must not.
- Render-grid resampling must not change the scientific grid or effective resolution. Require state×cell×time support metadata where claimed.

## RED tests already authored
`services/agribrain/layer1_fusion/tests/test_asmae_w3a_confidence_composite_contract.py`
1. Valid one-cell canonical confidence map creates a real diagnostic `RasterRef`.
2. Three confidence aliases deduplicate to one canonical reference.
3. Structural guard prevents composite invariant code from sitting behind the non-ASMAE skip.
4. Sanity checks for the composite/posterior concentration enum identities.

## Behavioral tests required before qualification
- Construct real `Layer10Output` + `SurfaceArtifact` objects: mutate one forbidden provenance flag at a time; assert each causes `INV-COMPOSITE` (not just source-order test).
- Valid advisory composite has no `INV-COMPOSITE` and remains diagnostic, never certified.
- Pass a native confidence raster through L1→L10→Plot Workspace in cold read; compare pixel masks and provenance, not only names.
- Verify no 1m or signed prescription authority after display-only resampling; duplicate/empty/malformed grids are rejected without fabricated pixels.

## Gate
Run the new Layer1 regression file, existing Layer1 tests, Layer10 invariant and runner tests, exact API/Plot Workspace contract checks, Layer05 regression, frontend unit tests and TypeScript. Keep PR #32 draft, all science/actuator holds in place.
