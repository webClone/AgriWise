# Scientific Pilot — Phase 1E-A: Quarantined V2 Candidate Ledger and Revocation

**Baseline:** \`main@6edd3721c0defa7eed94b44cf96601ba59a49696\`  
**Starting remote head (verified GitHub):** \`87161ce685b9a7ee2c7e5761648eb6f643b7cde3\`  
**Scope:** Single-node pilot authorization/revocation foundation, **NOT** a positive production issuer or farmer-facing permission path.

The Phase 1D attestation uses a symmetric HMAC, so it is a **message authentication code**, not a publicly verifiable asymmetric digital signature. Successful HMAC verification proves possession of a server secret and content integrity, **not** that the physical data was calibrated or truly assimilated. Its current development default must never qualify an intervention. This E-A ledger has a **separate explicit 32-byte-or-longer key requirement** and refuses implicit development keys.

## Source review before Phase 1E

- Phase 1D stores signed child attestations under the plot snapshot directory; the authenticated loader detects mismatched \`head.json\` roots while retaining the 10 canonical publication flags. The exact remote SHA reported in the user message (\`87161ce20f...\`) did not resolve on GitHub; the actual branch head was \`87161ce685...\`.
- Phase 1D's \`attach_canonical_proof_attestation\` and witness builders accept provided proof values. Hashes/signatures secure the **claim**, but do not certify the underlying acquisition and posterior computation. The existing \`attach_canonical_proof_roots\` unsigned convenience path must never become an authority source.
- A genuine Phase 1E issuer must use \`read_trusted_current_asmae_publication(..., require_proof_attestation=True)\`, not request-supplied head JSON or the optional legacy proof mode. It must independently verify admission, calibration, stage receipts, tribunal ancestry, influence selection, posterior uncertainty and source policy.
- The public \`run_schema._validated_authorization\` V2 quarantine remains mandatory until a separate production exporter rechecks the authentic issuance and revocation chain.

## Implemented: durable signed **candidate audit**, not authorization

\`services/agribrain/orchestrator_v2/pilot_authorization_ledger.py\`:

1. Re-fetches exact latest canonical publication from the internal server snapshot store with \`require_proof_attestation=True\`; rechecks V2 scope, crop/geometry, receipt, window, expiry and attested roots.
2. Writes a **QUARANTINED** candidate record containing exact V2 content hash, attestation hash, admitted-evidence root, uncertainty root, posterior root, snapshot and plot identity. Its record is content-hashed and HMAC-authenticated with a distinct explicit key (no silent default). It cannot be interpreted as a scientist/issuer certification.
3. Uses a durable SQLite ledger (single-node pilot) with \`BEGIN IMMEDIATE\` for record insertion and revocation, WAL mode and synchronous FULL. Unique record IDs are random. Record contents, signed metadata and SQLite index columns are verified at read.
4. Permanent candidate-specific revocation is idempotent and rejects unknown IDs. Plot-scope emergency block prevents **both** future candidate registration and inspection of existing candidates. No unblocking API is provided.
5. Inspection requires an authenticated namespace, valid HMAC, non-expired candidate and **current** attested snapshot, geometry/crop, receipt and roots. It can return only \`QUARANTINED\`, \`valid_export_authorization=False\`, and \`authorized_actions=[]\`.
6. \`authorize_export()\` always raises \`ContractViolation\`. The existing public \`run_schema\` also continues to reject V2 independently.

**Risk boundary:** SQLite is **not a distributed revocation authority**. A multi-replica Cloud Run/GCP deployment must use a strongly consistent shared transaction store with access control, recovery and audit retention; independent local files are unsafe. This pilot ledger protects normal application mutation/concurrency, not an attacker with full arbitrary database-administrator or server-key access. File/DB/key backups and permissions are operational requirements.

## New test gate

\`services/agribrain/tests/test_pilot_authorization_ledger.py\` exercises:

- Signed quarantined candidate storage, process reopen and hard-denied export.
- Durable record revocation, idempotence, missing record and invalid key.
- Content/HMAC tampering, altered SQLite index and signer-key rotation.
- Missing/invalid attestation and drifted publication or uncertainty roots.
- Plot cross-tenant isolation, future expiry and pre-record time.
- Rejection of legacy V1 envelopes.
- Emergency plot-scope block persisting across reopen and denying both read and registration.

Tests use mocked current heads and explicit throwaway test keys; they do **not** operate on Plot A production storage, sign a physically authorized intervention, or execute AgriBrain science.

## Required local qualification commands (Windows)

\`\`\`powershell
git pull origin feat/akaloris-scientific-pilot-qualification
py -3 -m pytest -q services/agribrain/tests/test_pilot_authorization_ledger.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_producer_publication_roots.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_proof_gate.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_publication_gate.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_prescription_authorization_v2.py
py -3 -m pytest -q services/agribrain/tests/test_corrected_maturity_boundary.py
npm run test:frontend
npx tsc --noEmit
\`\`\`

These new tests have not been run in the GitHub-only authoring environment. Earlier user-reported 204 pilot and 97 frontend passes apply to the starting Phase 1D candidate, not necessarily to the new E-A head.

## Remains OPEN for Phase 1E-B / E-C

**E-B: Trusted issuer and proof admission.** Require actual producer-owned, immutable and server-retrievable evidence witness documents and typed receipts. Check their signatures, device calibration authorities, originating stage integrity, source timestamps, ASMAE assimilation membership, tribunal verdict, explicit \`require_evidence_receipts=True\` promotion policy and each L8 action. Recompute/validate a posterior uncertainty receipt from a trusted scientific producer. Candidate hashes and fixture labels are insufficient. Issue a distinct domain-separated authorization MAC/signature **only after** these gates. Version key IDs, rotation, expiry and durable authorization records.

**E-C: Guarded V2 public export.** Use a separate owner-authenticated action route/boundary that loads the actual run artifact, current publication, trusted issuer record, current revocation/plot-scope controls and exact V2 content/action/plan hashes. Recheck all inputs at the moment of export (including supersession and farmer confirmation). Never convert an internal V1 envelope or a quarantined candidate into published V2 authority. Keep the existing serializer quarantine until a complete positive Plot A plus adversarial run proves correct behavior.

**Disposition:** Phase 1E-A coded as a **fail-closed foundation**, awaiting local regression verification. Phase 1E-B/E-C remain unimplemented. No physical action, positive signing service, real Plot A prescription or production export is claimed. \`main\`, PR #8 telemetry and accepted historic gates remain unchanged.
