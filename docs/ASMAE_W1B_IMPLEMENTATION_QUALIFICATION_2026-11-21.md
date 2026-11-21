# ASMAE W1-B implementation — qualification hold

Base: W1-A `94272b1`. Current implementation candidate is on `feat/akaloris-asmae-w1b-implementation` only. No merging or release promotion.

## Implemented
- `rollout/validation_ledger.py`: manual approval is not science eligibility at initial record, exception fallback or candidate update. Candidate-builder failure yields eligibility false and no synthetic trust/agreement 1.0.
- `src/lib/agribrain/plot-map-evidence-state.ts`: only explicit non-diagnostic scientific driver flags can show a prescription cap; raster renderability alone cannot.
- `prisma/schema.prisma`: new tenant-scoped durable `AgriBrainRun` runId-to-plot/farm binding, created before authenticated `/api/agribrain/run` execution. Deployment must generate Prisma client and provision appropriate unique indexes.
- `src/app/api/agribrain/runs/[runId]/result/route.ts`: checks signed-in user, stored run binding, plot ownership, and exact envelope run/plot identity; uses signed internal request headers; no upstream fetch on unauthorized/foreign runs.
- `tests/frontend/asmae-w1b-route-and-map-authority.test.mjs`: extended negative cases with authorized success and malicious backend run/plot substitutions.

## Outstanding integration blocker
No matching `/v2/runs/{run_id}/result` handler was found in current Python `services/agribrain/app/main.py`. The Next.js proxy is safe-by-default, but owner successful cold result retrieval remains **unqualified** until the backend endpoint is implemented against persistent run artifacts and tested. A stubbed Node success test does not prove that backend endpoint exists.

## Qualification commands (not executed in this connector review)
```powershell
npx prisma generate
node --test tests/frontend/asmae-w1b-route-and-map-authority.test.mjs
python -m pytest services/agribrain/rollout/tests/test_asmae_w1b_learning_eligibility_contract.py -q
python -m pytest services/agribrain/layer05_asmae/tests/ -q
node scripts/run-frontend-tests.mjs
npx tsc --noEmit
```
Also run a real two-tenant run registration and cold exact result lookup, test index migration, rollback/revocation, and server-side prescription authorization. Do not claim W1-B green until executed, and do not count route owner access as qualified before the backend endpoint is available.
