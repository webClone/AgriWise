# ASMAE IR04 — anchored Worldline replay authority candidate

Status: strict fail-closed implementation candidate; not scientifically or production certified. Base: published IR04 security head `cf521af`.

## Implementation
- `journal_authority_gate.verify_replay_against_trusted_worldline` first validates the receipt's own schema/digest, then independently rehydrates it from a pinned deployment-provisioned Worldline root and durable checkpoint root.
- Binds tenant, plot, trusted namespace, geometry, valid T, knowledge K, selected evidence set and digest, journal generation, and durable-anchor generation.
- Rejects future knowledge cutoffs, missing pinned roots, missing/unanchored checkpoints, forged event sets/generations, and K newer than the matching durable checkpoint creation time.
- Engine uses strict replay check before granting K. A caller-provided journal watermark without an independently verified receipt no longer grants K.
- Added seven real-Worldline or negative-control tests, **not executed independently**.

## Certification boundary
This is an externally mounted durable-journal consistency gate, **not a cryptographically signed external journal-origin proof**; the anchor storage must be independently controlled and protected from mutation. Issuer signing and revocation history, signed checkpoint attestations, genuinely append-only external retention, and authorized historical K policy remain future release gates. If trust roots are missing, historical scientific publication is held rather than upgraded from a self-consistent digest.

## Qualification
Run `pytest services/agribrain/layer05_asmae/tests/test_asmae_ir04_worldline_authority_gate.py -q` plus full Layer05/Worldline/API regressions at exact SHA and multi-process rollback/forged-clock tests. Reconcile only after independent proof. Keep PR #32 draft and all 1m, numerical publishing and irrigation interlocks on HOLD.
