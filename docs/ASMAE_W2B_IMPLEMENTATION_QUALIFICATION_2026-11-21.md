# ASMAE W2-B implementation — qualification hold

Base: qualified W2-A `c53a78c`. Isolated branch `feat/akaloris-asmae-w2b-implementation`.

## Implemented
- `layer6_yield/yield_forecast.py`: remove unvalidated ASMAE confidence-only vigor and LAI adjustments and the fabricated 0.1 uncertainty. Preserve independent biomass/stress forecast and correct uncertainty intervals. Crop-specific qualified yield response remains a future scientific contract.
- `layer4_nutrients/runner.py`: standalone injection of ASMAE LAI into independent L2 data requires actual authority, finite physical value + uncertainty, crop/stage and independent calibration lineage; diagnostic/untagged inputs cannot overwrite L2 data.
- `layer3_decision/runner.py`: recognize lower/mixed-case ASMAE evidence and `asmae_artifact:` references across all 13 states in the guard.
- `layer8_prescriptive/action_ranker.py`: canonical 13-state provenance across evidence IDs, descriptions and explanations, no missing-sigma fallback, multiple participating-state checks; explicitly include IRRIGATE with other irreversible actions. All ASMAE-driven irreversible actions stay blocked until independently signed server-side action authority exists, irrespective of untrusted self-asserted high confidence.
- `test_asmae_w2b_13state_provenance_contract.py`: added four parameterized ASMAE physical intervention holds and non-ASMAE scouting preservation.

## Acceptance commands (not run here)
```powershell
python -m pytest services/agribrain/layer6_yield/tests/test_asmae_w2b_yield_authority_contract.py -q
python -m pytest services/agribrain/layer4_nutrients/tests/test_asmae_w2b_standalone_authority_contract.py -q
python -m pytest services/agribrain/layer3_decision/tests/test_asmae_w2b_13state_provenance_contract.py -q
python -m pytest services/agribrain/layer8_prescriptive/tests/test_asmae_w2b_13state_provenance_contract.py -q
python -m pytest services/agribrain/layer05_asmae/tests/ -q
node scripts/run-frontend-tests.mjs
npx tsc --noEmit
```
Then run all relevant full L3/L4/L6/L8 suites and an end-to-end test proving no unauthorized or physical action from any ASMAE diagnostic state. This batch does not certify crop yields or issue irreversible actions.
