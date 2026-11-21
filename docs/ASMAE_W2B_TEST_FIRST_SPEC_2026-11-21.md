# ASMAE W2-B — Yield, Standalone Layer 4, L3/L8 Provenance (test-first specification)

**Date:** 2026-11-21 · **Parent:** W2-A `5c56e1203632b7311b48290dc82a734199aa1345` · **Status:** Specification and deliberately RED yield regression tests only. Do not promote before W2-A qualification.

## Scientific authority is consumer-specific
An estimate can be finite and visualizable without being permitted to adjust yield, fertilization or prescription confidence. The gate must examine the actual `ASMAEFeature` state support, channel, retro/BMA status, uncertainty and crop-relevant calibration; a high confidence number alone is insufficient.

### W2B-01 — Layer 6 yield
Source: `services/agribrain/layer6_yield/yield_forecast.py::YieldForecastEngine.predict_yield`, baseline vigor/LAI code near lines 68–94.
- Remove duck-typed confidence-only acceptance and the dictionary fallback `uncertainty=0.1`. No missing sigma may be manufactured.
- Admit only explicitly state-update-allowed, non-diagnostic, non-revoked, qualified supported vigor/LAI, with valid retro/BMA, local resolution and finite sigma. Consume through central ASMAE usability accessor with consistent dict/object semantics.
- For diagnostic-only, missing sigma, 1m advisory, high confidence but no provenance, or untrusted state: return the **same** baseline yield and uncertainty interval as if ASMAE had been absent. Do not crash on `None` sigma.
- Additional scientific calibration gate before claiming an ASMAE-driven yield delta; confidence does not establish crop yield causation. Until qualified, keep baseline forecast and separately report exploratory diagnostics.

### W2B-02 — Layer 4 standalone
Source: `services/agribrain/layer4_nutrients/runner.py::run_layer4_standalone`, near lines 160 and 350.
- Replace raw `asmae_features["ASMAE_LAI"].value` injection into `l2_biophysical.lai_current` with authority-checked candidate plus crop/phenology applicability.
- Preserve W2-A explicit `ug/cm2` chlorophyll tag and `fraction_content` water tag. Missing trusted calibration verifier withholds chlorophyll influence.
- No action/prescription authority for unqualified LAI, missing semantic lineage, wrong crop, stale calibration, unsupported BMA/retro or diagnostic-only inputs.
- Retain independent, verified soil lab and non-ASMAE evidence for legitimate use; do not globally disable Layer4.

### W2B-03 — Case-insensitive 13-state provenance in Layer 3 and Layer 8
Sources: `services/agribrain/layer3_decision/runner.py` around lines 305–325; `services/agribrain/layer8_prescriptive/action_ranker.py` around lines 365–414; `services/agribrain/scientific_contracts/state_schema_ref.py`.
- Normalize ASMAE variable identities using `canonical_state_key` / `SURFACE_TO_CANONICAL_STATE`, not substring scans for uppercase `ASMAE` and a hardcoded five-state whitelist.
- Enumerate **all `STATE_ORDER` 13 states** and canonical aliases in parameterized tests; include lower/mixed-case evidence IDs, descriptions and drivers.
- If a card refers to multiple ASMAE states, a usable state cannot launder an unqualified second state. Match the full participating set and individual proof authority.
- Missing numerical sigma or `uncertainty=None` must not be converted to 0.1; missing provenance/corroboration must not certify irreversible action.
- The next wave may improve *detection and blocking*; it does **not** authorize irrigation actuation or 1m certification.

## RED tests already authored
`services/agribrain/layer6_yield/tests/test_asmae_w2b_yield_authority_contract.py`
- Parameterized dict/object vigor and LAI combinations lacking state authority.
- No fabricated 0.1 uncertainty for missing `uncertainty`; no crash on `None`.
- 1m advisory cannot modify yield.
- Each unqualified forecast must equal independent no-ASMAE baseline for mean, P10 and P90.

## Additional tests to implement with code
- Standalone Layer4 identical inferred output for diagnostic-only ASMAE LAI versus absent ASMAE LAI; a qualified crop/phenology state may contribute only through the authorized adapter.
- For each of 13 states, `ASMAE_<STATE>`, `asmae_<state>`, mixed-case alias and evidence identifier must produce same recognized provenance.
- Any one revoked/unusable participating ASMAE state blocks action; non-ASMAE independent corroboration cannot erase a failed ASMAE proof.
- Exactly one correctly authorized non-ASMAE action survives unchanged, proving fail-closed ASMAE handling is not a global disablement.

## Gate
Run the authored yield tests; add Layer4 standalone integration, L3 decision and L8 action card tests. Run affected complete Layer2/3/4/6/8 and Layer05 regression suites plus frontend, exact HEAD. Maintain all holds and master register.
