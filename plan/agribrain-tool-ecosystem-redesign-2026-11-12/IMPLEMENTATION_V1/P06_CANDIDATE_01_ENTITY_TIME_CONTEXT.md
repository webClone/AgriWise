# P06 Candidate 01 — Scoped Entity Time Context

**Base:** c1f147f (P05 fast-forward; reconciliation preserved)  
**Feature branch:** feat/plot-workspace-p06-entity-time-context  
**Canonical PR #30:** untouched on feat/plot-workspace-p04-tool-registry

## Implemented
- Selected SENSOR, CAMERA, DRONE_MISSION and FIELD_OBSERVATION/FIELD_EVENT actions include **Compare time**.
- The in-place P04 host uses only the latest tenant/farm/plot-scoped P05 envelope, matched to selected ID, kind and source version.
- The comparison shows observed, first-available and publication timestamps, epistemic class, current scientific cutoff/authority, and chronological relationships.
- SIMULATED/demo and PLANNED records never imply real measurement or executed mission.
- A checksum is not treated as a signed sensor attestation.
- No second scientific snapshot, temporal raster estimate, or point-to-raster value is invented.
- Original zone investigation, instrument dock, hardware fail-closed boundary, legacy fallback and P03 publication authority are unchanged.

## Automated checks to run on this candidate
```powershell
npm run test:frontend
npx tsc --noEmit
npm run build
```

The new pure helper contains 9 regression tests and the frontend wiring contains 3 source-level checks. Direct V8 regression checks of the 9 helper cases passed during development. The complete npm test command, TypeScript compiler, and production build were **not run** by the GitHub-only editing session.

## Real browser qualification — PENDING
Run in an authenticated plot session with V2 enabled, on the candidate commit:
1. **Map:** load the native spatial canvas and confirm entities render in the correct plot scope.
2. **Select:** click a real DeckGL entity pin (not a testing CustomEvent), record kind, ID, source version and visible selection halo.
3. **Inspect:** verify context inspector shows this same entity and accurate epistemic badge; check demo fixtures do not claim fresh readings.
4. **Open:** click the entity's real instrument action, verify in-place mounting and matching ID; return to the map without a route change.
5. **Compare:** click **Compare time**, confirm current entity's observed/availability times are aligned against the *current* scientific cutoff; switch to another entity and verify the host retargets; change plot and verify stale entity content disappears. Check absent availability and simulated/PLANNED data show explicit non-admission text.

**Evidence required:** screenshots, CDP request/DOM logs, rendered timestamps, one valid real sensor (if available), a demo fixture, a plot-scope transition, and the exact commit SHA.

**Do not mark full P06 temporal comparison accepted** until the browser gate passes. This slice provides chronological context only, not a field-calibrated scientific time-series comparison.
