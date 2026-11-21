# ASMAE verified P2-11 to P2-14 — MESIA truthfulness remediation

**Date:** 21 November 2026  
**Base:** `b6338fda6a57958c246e4443454673f370a6de5f` (five-wave unified integration, not PR #32 fast-forward)  
**Branch:** `feat/akaloris-p2-mesia-p08-truthfulness-20261121`  
**State:** Production source candidate; tests authored, **not run by GitHub connector**.

## Corrected finding identities
- **P2-11 — Fail-open MESIA bridge:** `mesia/integration.py` rejects any packet claiming ASMAE state authority rather than P-08 `evidence_proposal`, refuses non-existent/remote/relative/unscoped native URIs and forged 64-hex hashes, confirms SHA-256 against actual plot-scoped file bytes and SigMF metadata, and refuses to classify unfamiliar radio families as SENSING even when an explicit role says SENSING. Valid physical files without a calibrated biological operator are still not admitted to the posterior.
- **P2-12 — dB is not VWC:** `mesia/behaviour/likelihood_engine.py` retains radio-domain SNR residual and covariance in explicit `radio_residual_db` and `radio_residual_variance_db2`, but withholds agricultural `innovation`, `covariance` and support; `target_variable` is `UNSPECIFIED_PENDING_CALIBRATED_OPERATOR`. A contract's `physical_primitive` is never an agricultural target.
- **P2-13 — Tier 2 biological inference:** `mesia/service.py` labels GNSS/Wi-Fi-derived VWC and canopy-water outputs `DERIVED_MODEL_INFERRED`, reserves `MEASURED_NATIVE` wording for underlying radio observation descriptions, uses the P-08 `evidence_proposal` authority scope, and sets `ProcessingLevel.DERIVED` with the real Layer0 evaluation receipt as its parent. `native_capture_present` is now independently checked against actual file bytes.
- **P2-14 — Claim-scanner bypass:** `mesia/governance/claim_scanner.py` no longer accepts whole-file exemptions for farm-intelligence production UI; substring matching is eliminated; exceptions are exact path + rule + entire reviewed line. Four unqualified `Zero synthetic data.` production UI comments removed. Eight UI-file blanket exemptions were replaced by 10 narrow `GROUND_TRUTH` line exceptions.

**Note on branch isolation:** Four incidental UI documentation/comment files are edited under P2-14. None overlaps the P2-15/16 frontend-wave files `PlotMapShell.tsx`, `ResolutionCoverageHUD.tsx`, or its new helper/tests. Both branches remain independently reviewable.

## Test specification and commands
```powershell
git fetch origin
git switch feat/akaloris-p2-mesia-p08-truthfulness-20261121
python -m pytest services/agribrain/mesia/tests/test_asmae_p2_11_14_mesia_truth_boundaries.py -q
python -m pytest services/agribrain/mesia/tests/ -q
python -m pytest services/agribrain/layer05_asmae/tests/ -q
python -m pytest services/agribrain/layer0/tests/ -q
python -m services.agribrain.mesia.governance.claim_scanner
node scripts/run-frontend-tests.mjs
npx tsc --noEmit
```

## Deliberately unqualified / remaining blockers
- No qualified physics/field calibration maps dB SNR features and their dB² uncertainty into a statewise VWC estimate and VWC² covariance. Until that operator exists, measured radio residuals remain diagnostic; ASMAE EnKF state update is blocked.
- Actual 2-tenant/2-plot byte-store and authenticated receiver replay, revocation, hardware calibration and external closure not independently demonstrated by these source tests.
- End-to-end service TruthEnvelopes and broader root-zone views require a separate review of asserted physical receiver provenance; a native-sensor report does not by itself prove archived bytes.
- This branch has no executed CI suite receipt. Do not close any of the 238 register findings or advance PR #32 on source-only evidence.
- **Queued, separate integration:** FastAPI `GET /v2/runs/{run_id}/result` persistent cold-result endpoint for W1-B; not silently bundled into MESIA remediation.
- Signed irrigation, 1m science certification, and unqualified numerical publication remain disabled/held.

## 2026-11-21 gate review: scanner and dependency
- `mesia/service.py` imports `sgp4.api.Satrec` and `jday` at module import time. Main AgriBrain requirements already declare `sgp4>=2.23`; this branch now declares it in `mesia/requirements.txt` as well. **The developer's local venv was not inspected**.
- The tightened claim scanner was source-dry-run against **all 48** eligible production files in `src/components/farm/intelligence/` and `src/app/api/agribrain/mesia/`: 10 matching claim lines, all with exact-line exemptions; **zero unexempted matches**. This is not execution of the Python CLI, and the scanner also traverses the separate 189-file MESIA subtree.
- The local gate must still confirm `python -m services.agribrain.mesia.governance.claim_scanner` exits `0`, and `python -c "from sgp4.api import Satrec, jday; print('sgp4 import OK')"` succeeds.

Do not convert this static inspection into a PASS receipt for the MESIA module import, scanner CLI, or runtime tests.
