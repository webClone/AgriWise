# Akaloris Scientific Pilot — P347-PUB-01 Canonical Head Transaction Repair

**Scope:** One shared P2 race between canonical ASMAE/Layer10 publication and both proof attachment helpers.  
**Review baseline:** \`feat/akaloris-scientific-pilot-qualification@347029581b7cb6836c3fde1ab3bcbae10fdd4525\`  
**Main:** \`6edd3721c0defa7eed94b44cf96601ba59a49696\` (unchanged)  
**Status:** Source-level correction committed. **Focused native race regressions and full suites require local execution on the new candidate before acceptance.** No positive issuance or V2 export enabled.

## Reproduced defect (review input)

Both \`attach_canonical_proof_attestation\` and \`attach_canonical_proof_roots\` used an old full \`head.json\` image after a newer publication committed. Native controlled interleavings reproduced C→D→C and E→F→E. The original ASMAE node, publication and receipt remained internally hash-valid, so cold loader and ten canonical flags did not detect semantic latest-pointer rollback. \`_atomic\` alone cannot protect read/validate/replace.

## Implemented correction

**Single shared per-plot head transaction** in \`services/agribrain/layer05_asmae/plot_snapshot_store.py\`:

- \`_plot_head_transaction(ns)\`: per-plot process-local \`threading.RLock\` **plus** a persistent, never-renamed \`head.transaction.lock\` file. POSIX \`fcntl.flock\` or Windows \`msvcrt.locking\` provides cross-process mutual exclusion for workers sharing the same local snapshot root. Lock acquisition times out fail-closed instead of silently performing an unlocked write. The same thread may safely reenter the transaction for the Layer10 → canonical publisher delegation.
- \`@_serialized_plot_head_writer\`: wraps the complete function read/validate/immutable-file-write/head-replace interval of **all four** known current-head writers: \`publish_canonical_plot_snapshot\`, \`publish_canonical_layer10_snapshot\`, \`attach_canonical_proof_attestation\`, \`attach_canonical_proof_roots\`.
- Signed attachment C cannot read C, pause, and overwrite a published D. If attachment acquires the lock first, D waits and publishes after C attaches. If D acquires the lock first, the signed C attestation fails the existing exact snapshot/receipt/scope checks; it cannot restore C.
- Unsigned helper is also serialized with publication, eliminating stale full-head replacement. The helper is not a signing authority and must remain ineligible for positive prescription authorization.
- \`_atomic\` remains responsible for durable per-file replacement; it no longer substitutes for the transaction.
- No changes to immutable node/publication/receipt hash algorithms, signed proof attestation payload or HMAC verification, accepted telemetry, V2 time arithmetic, ledger/revocation or public serializer/export quarantine.

**Operational limitation:** This lock synchronizes only cooperating processes using the **same filesystem with working OS file-lock semantics**. It is not a cloud-wide distributed lock. Before using multi-replica storage on Cloud Run/GCP, replace the local head pointer with a strongly consistent shared transactional/CAS mechanism. Do not split workers across independent replica-local artifact stores.

## Deterministic new regression controls

\`services/agribrain/tests/test_p347_publication_head_transaction.py\` adds:

1. **Signed C→D race:** real attachment is paused after its child attestation file is written; another thread attempts full native D publication; lock forces attachment to commit before D. After both complete, cold-loaded latest is D; D receipt matches; C's immutable node/frontend publication/receipt bytes are unchanged.
2. **Unsigned E→F race:** E is genuinely attested; root helper pauses before writing E head; another thread attempts full F publication; lock forces E completion before F. Cold latest remains F; original E parent bytes preserved.
3. **Ordinary/stale controls:** valid signed attachment passes all ordinary attestation checks; signed C attachment beginning after D publication is rejected, D remains current.
4. **Nested publication:** nested same-thread plot transaction completes without deadlock (protecting Layer10 delegation).
5. **Separate-process lock:** subprocess attempts to acquire the same plot lock while parent holds it; child proceeds only after release. This validates the OS lock beyond the Python \`RLock\`.

Test imports real canonical store and existing test publication payload fixture, writes temporary plot files, and uses event barriers rather than flaky randomized sleeps to enforce the two native interleavings. A short subprocess scheduling window checks lock fencing. No real plot, device, operational database or browser is involved.

## Exact local verification gate

\`\`\`powershell
git pull origin feat/akaloris-scientific-pilot-qualification
py -3 -m pytest -q services/agribrain/tests/test_p347_publication_head_transaction.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_producer_publication_roots.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_publication_gate.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_proof_gate.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_authorization_ledger.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_prescription_authorization_v2.py
py -3 -m pytest -q services/agribrain/tests/test_corrected_maturity_boundary.py
npm run test:frontend
npx tsc --noEmit
npm run build
\`\`\`

The previous review's 36 timestamp and 49 structural-proof checks need not be independently rediscovered unless the corresponding source changes. The above are concrete regression gates, not claims that they passed at the new head.

## Exit criteria

- Native signed C→D and unsigned E→F interleavings never restore a stale head after a newer publication commits.
- Cross-process workers sharing one artifact store honor the same lock.
- Current cold-loaded snapshot is the winning D/F, with correctly scoped publication receipt.
- Positive signed attachment and stale-before-start rejection remain correct.
- Immutable parent bytes and ten canonical flags remain untouched.
- Public V2 action exporter still quarantined; candidate ledger still denies authorization.
- Verify complete affected Python suite and frontend/TypeScript/build gates at one pinned head.

**Next work after acceptance:** E-B authenticated producer-owned admission and posterior proofs, durable trusted positive issuer, then E-C independently guarded V2 export with revocation and owner-scope revalidation. A signed candidate or synthetic structural fixture is not a real authorized agronomic intervention.
