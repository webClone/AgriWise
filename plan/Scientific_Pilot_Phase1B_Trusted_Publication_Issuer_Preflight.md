# Scientific Pilot — Phase 1B: Trusted Publication Reader and Issuer Preflight

**Base:** \`main@6edd3721c0defa7eed94b44cf96601ba59a49696\`  
**Branch:** \`feat/akaloris-scientific-pilot-qualification\`  
**Status:** Read-only trusted current publication adapter + negative issuer-preflight tests committed. **NOT a production signer or positive authorization.**

## Current evidence

Local report against \`8993a68\`: V2 62/62; V1 14/14; pilot baseline 8/8; P2B temporal 8/8; frontend 97/97; TypeScript 0 errors; production build 63 routes. These executions occurred **before** this Phase-1B code and must not be reported as results for the new head.

## A critical trust distinction: ASMAE publication manifest ≠ full L8 evidence admission

\`services/agribrain/layer05_asmae/job_manifest.py\` generates \`manifest_hash\` for the ASMAE **job manifest**. \`services/agribrain/layer05_asmae/plot_snapshot_store.py\` publishes that job manifest hash in its current head and validates node/publication/receipt integrity. \`PrescriptionAuthorizationEnvelopeV2.evidence_manifest_hash\` presently binds the current head's \`manifest_hash\`, for backward compatibility with the V2 contract.

That equality **does not establish** that the individual tribunal-accepted \`PRESCRIPTION_DRIVER\` contributions were observed, calibrated, assimilated, admitted and represented in the exact published state. A missing membership edge must not be filled with a guessed hash, matching timestamp, diagnostic identifier, or simply the job manifest hash.

The eventual issuer must present a separately verifiable chain:

\`\`\`
authenticated plot + current geometry/cycle
      → canonical ASMAE job manifest and immutable snapshot receipt
      → immutable physical evidence references + admission receipts
      → ASMAE assimilated state/belief and uncertainty receipt
      → tribunal accepted contribution IDs and influence manifest
      → policy-enforced, receipt-backed promotion audit
      → exact L8 action and final plan hashes
      → authenticated issuer signature + revocation and expiry
      → public export authorization (re-validate current head)
\`\`\`

## Phase 1B implementation

\`services/agribrain/orchestrator_v2/pilot_publication_gate.py\`:

- Calls \`load_latest_plot_snapshot(namespace)\` from the **real** internal snapshot store; it does not accept a caller-supplied \`canonical_head\` document.
- Takes a server-derived \`PlotNamespace\` and expected current snapshot ID, geometry hash and crop cycle ID; rejects mismatch, missing values, wrong snapshot kind and unsupported old/superseded head.
- Revalidates all ten snapshot publication flags (including \`temporalBindingValid\`), validates receipt and ASMAE job manifest hash shape, normalizes UTC times and checks chronological window ordering.
- Returns only a narrow trusted publication adapter shape with \`available: true\`, which makes it compatible with the existing \`validate_published_pilot_envelope\` contract. It never creates a V2 envelope, permission receipt or signature.
- \`preflight_pilot_issuer(...)\` cannot elevate authority. It returns a frozen \`PublicationToPrescriptionPreflight(status="BLOCKED", reason=...)\` for every candidate. Reasons distinguish no recorded run, wrong namespace, missing mandatory evidence policy, incomplete tribunal/promotion gate, and missing exact ASMAE-evidence-to-L8/uncertainty proof.

\`services/agribrain/tests/test_pilot_publication_gate.py\` verifies exact current-scoped read, no raw scientific payload leakage, wrong plot/tenant/farm/geometry/cycle/snapshot, each invalid integrity flag, invalid receipt or job-manifest hash, malformed chronology, missing publication and **never-positive** preflight.

## Why there is deliberately no positive issuer yet

A content hash is not a signature. The production code has evidence receipts and a \`DiagnosticPromotionService\`, but policy defaults can omit mandatory receipt checks, and current run artifacts do not yet carry a sufficient *verified* link from the immutable published ASMAE evidence set to each accepted L8 contribution. Nor is an authenticated uncertainty receipt verifier/signer and durable revocation store connected.

Introducing a signer that accepts \`is_verified: true\` or arbitrary caller JSON as proof would bypass the required scientific trust boundary. Therefore positive issuance is blocked until all three obligations are fulfilled:

1. **Membership verifier:** trusted, server-side proof that exact admitted evidence IDs and hashes feed the published ASMAE state, the specific diagnosis/belief, tribunal and L8 influence manifest. It must reject old/superseded snapshots and late, uncertified PR #8 operational telemetry.
2. **Uncertainty verifier:** source-verified uncertainty-bounds receipt matching crop/geometry/cutoff and each action's rate/zone/time domain, not merely a 64-hex field supplied by caller.
3. **Issuer, durable policy and revocation:** server-owned signing key or verifiable durable issuer record, identity/domain/expiry, key rotation and revocation, and a final head re-check at the point of action export. V1 legacy behavior must not be advertised as scientific parcel-specific authorization.

## Immediate local test gate

\`\`\`powershell
git pull origin feat/akaloris-scientific-pilot-qualification

py -3 -m pytest -q services/agribrain/tests/test_pilot_publication_gate.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_prescription_authorization_v2.py
py -3 -m pytest -q services/agribrain/tests/test_corrected_maturity_boundary.py
py -3 -m pytest -q services/agribrain/tests/test_scientific_pilot_baseline_probe.py
\`\`\`

Any unexpected failure is a regression to resolve before proceeding. This phase has not been executed against the live Plot A runtime here; all positive Pilot-AUTH-04 and full publication-to-prescription gates remain **OPEN**. PR #8 telemetry and \`main\` remain unchanged.


## P899-TIME-01 correction — versioned contract validity gate

**Review basis:** Independent report pinned to scientific-pilot head \`8993a68\` reproduced a P2 ISO variable-precision string comparison error in \`validate_published_pilot_envelope()\`. The fix was applied to the **current** scientific-pilot branch, preserving subsequent Phase-1B work.

- Comparison now parses \`issued_at\`, \`now\`, and \`expires_at\` into UTC-aware \`datetime\` values before enforcing \`issued <= now < expires\`.
- V2's serialized canonical UTC strings, content hash, publication identity and snapshot cutoff checks remain unchanged.
- The focused pytest matrix covers whole/fractional seconds; just before/at/after issuance and expiry; fractional endpoints; and equivalent offset-aware instant representations. Each case exercises an in-memory V2 object and a JSON-round-tripped mapping (36 decisions).
- Existing V1 compatibility and V2 legacy public-run export quarantine remain unchanged. No production authorizer or signer was activated.

**Execution evidence:** This correction was committed to GitHub and structurally reviewed. Its newly added pytest matrix and the full Python/TypeScript/build gates still require local execution at the current head. Historical passes at \`8993a68\` do not validate this new candidate. There is no claim of live issuance or a deployed physical-action bypass.
