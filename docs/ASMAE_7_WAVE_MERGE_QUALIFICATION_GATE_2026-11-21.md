# ASMAE seven-wave integration candidate — merge and full-stack qualification gate

**Date:** 2026-11-21
**Repository:** webClone/AgriWise
**Integration branch:** feat/akaloris-asmae-unified-seven-wave-candidate-20261121
**Initial integration commit:** a12b499d934326e55c7cee037229457254f104e4
**State:** Source merged into an isolated candidate. Combined regression NOT executed. Not a release or production qualification.

## Immutable merger lineage

GitHub's three-parent merge commit preserves:

1. First parent: five-wave unified development baseline b6338fda6a57958c246e4443454673f370a6de5f (W1-A, W1-B, W2-A, W2-B, W3-A).
2. Second parent: MESIA P2-11–14 5b86359c739ce3636586e627dfb8197869a0a2ad; reported local gates MESIA 140/140, P-08 scanner exit 0, sgp4 import pass.
3. Third parent: frontend P2-15–16 e8f47850524a913d77df0bcc1bf0beb6937107cf; reported local gates frontend 355/355, TypeScript 0 errors.

GitHub compares confirm 16 MESIA changed paths and five frontend changed paths, zero overlap and exact combined tree. The two local green receipts are supported by user-provided Windows execution logs. They are not proof that the merged candidate itself passed tests. The counts must not be presented as distinct aggregated test counts without deduplication.

Protected original unified branch remains unchanged at b6338fd. PR #32 remains draft at 64a9f699 and ON HOLD; PR #30 and main remain untouched.

## Full-stack regression runner

Use scripts/verify-asmae-seven-wave.ps1. It checks exact branch and expected SHA, runs 12 separately logged gates, stops on first failure, and produces seven_wave_receipt.json under a timestamped temporary folder (or a caller-provided folder). It does not upload results to GitHub, submit scientific claims or enable physical controls.

From PowerShell on the Windows checkout:

    git fetch origin
    git switch feat/akaloris-asmae-unified-seven-wave-candidate-20261121
    git pull --ff-only
    $expected = (git rev-parse origin/feat/akaloris-asmae-unified-seven-wave-candidate-20261121).Trim()
    .\scripts\verify-asmae-seven-wave.ps1 -ExpectedHead $expected

The runner covers: sgp4 import, full MESIA scanner, entire MESIA suite, all Layer0 tests, all Layer05 tests, full intermediate layer-scoped suites (including Layer3 Water), W1-B/W2-A service contract files, all 65 AgriBrain cross-layer test files plus rollout tests, targeted frontend W1-B/P2-15/16 authority tests, Prisma client generation, all frontend TAP files, and strict TypeScript compilation.

**Acceptance:** Every command exits zero at the same exact candidate SHA, with all full output logs retained and independently reviewed. Check registration and two-tenant cold run-result behavior separately; the missing Python GET /v2/runs/{run_id}/result endpoint is NOT fixed by this merge.

## Scientific holds (not closed by seven-wave merge)

- P2-13 physical-receiver provenance including CALIB-UNVERIFIED-DEMONSTRATOR, synthetic three-node fleet claims, and actual signed native radio capture origin remains open.
- P2-12 keeps dB SNR evidence diagnostic; a calibrated dB-to-VWC operator with justified propagated uncertainties does not yet exist. Zero physical assimilation from uncalibrated radio.
- No assertion of unique 1 m spatial certification from HUD percentage or materialized raster display.
- No unsigned or unqualified numerical science publication, learning export, irreversible crop treatment or physical irrigation delivery. Keep AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false.
- All 238 ASMAE register findings stay open unless individually evidence-qualified.
- Do not fast-forward the original unified branch or PR #32 until the merged candidate has a complete pass and independent scientific review.

## Go/no-go

**READY TO EXECUTE MERGED TESTS. NOT YET QUALIFIED GREEN.**
