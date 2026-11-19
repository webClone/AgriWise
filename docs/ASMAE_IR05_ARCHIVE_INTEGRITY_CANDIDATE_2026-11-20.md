# ASMAE IR-05 — Archive Integrity, Crash Resume and Scientific Truthfulness

Date: 2026-11-20
Branch: `feat/akaloris-asmae-ir05-archive-integrity-batch-20261119`
Base: Draft PR #32 head `64a9f69945d8e3eda2bf33de9ff24e98186c9a17`
Status: **Implementation candidate only — tests authored, NOT EXECUTED, merge HOLD**
Security candidates `95dda02` and `bfe56c9` remain local-only/unavailable to this review; no changes to their branch.

## Vision alignment

- Maintain full *available* 2015+ historical archives (not a three-year rolling approximation).
- Distinguish discovered scene inventory from admitted observations, assimilated posteriors, retrovalidated knowledge and actionable authority.
- Preserve real observations at T, actual journal commitment at K, and original evidence digests.
- On future invocations, resume from durable progress, append new observations only and use selective replay for late revisions.
- Never manufacture 13 scientific raster maps, fine effective resolution, operational permission, or weather.
- Preserve dynamic state×cell×time spatial support and future MESIA tomography as separate, evidence-qualified workstreams.

## Delivered on isolated branch

1. Archive provider missing means explicit failure, never an empty but completed historical archive.
2. Strict UTC/date/window/geometry inputs; checkpoint path and tenant isolation; malformed checkpoints fail closed.
3. Atomic checkpoint file replacement with fsync, unique temporaries and path containment.
4. New v2 checkpoint identity checks; mismatched geometry/start/window/tenant cannot silently resume old history.
5. Journal-led recovery of already-committed scene identities, including commit-then-crash-before-checkpoint scenarios.
6. Historical scene times must fall inside the exact queried window; duplicate scene IDs with changed content hashes require selective replay.
7. Archive discoveries publish `ARCHIVE_SCENE_INGESTED` inventory-only events rather than mislabeling them `ARCHIVE_POSTERIOR_VALIDATED`. The scientific posterior event remains owned by assimilation/independent qualification.
8. Completed checkpoints undergo a cold journal consistency check before early reuse.
9. 14 historical unit/integration test cases now cover ordinary, resumed and negative-control behavior.

## Crucial limitations (not silently closed)

- **No live STAC/provider integration:** Provider injection must be wired to authenticated real Copernicus/Layer0 retrieval. `archive_provider_not_configured` remains a deliberate safe failure.
- **No science is calculated by this batch:** No 13-state EnKF historical posterior, map reconstruction, event inference, BMA, prospective holdout or MESIA tomography is asserted.
- **No distributed exactly-once guarantee:** Recovery from single-worker post-commit crashes is addressed; concurrent-worker locking, durable source acknowledgements, versioned late-data replay and transactional journal/checkpoint reconciliation remain to be qualified.
- **Existing v1 checkpoint migration required:** v2 deliberately rejects legacy checkpoint identities until a reviewed migration is provided.
- **Timestamp provenance:** Inventory preserves acquisition T; the Worldline owns real committed_at K. Never assign K from the queried cutoff.
- **Test status:** No local Python repository, CI checks, or provider credentials available to this review. All authored tests and code require actual execution before acceptance.

## Required independent qualification before promotion

1. Run `pytest services/agribrain/layer05_asmae/tests/test_asmae_ir05_archive_bootstrap.py -q` at the exact branch SHA; collect complete logs.
2. Run the full Layer05 backend suite and dependent Worldline tests; test the newly introduced inventory event contract.
3. Integrate and verify a genuine production STAC archive provider: empty valid window vs unavailable provider must be distinguishable.
4. Execute cross-process crash, concurrency, journal rollback, geometry revision, late-arriving scenes, and new-target incremental append cases.
5. Prove complete first-open bootstrap (all available history) and next-open incremental continuation; verify no fake validated posterior.
6. Ensure historical inventory cannot be promoted to state update, 1m certification, numerical publication or actuator authority.
7. Rebase/reconcile only after separate `bfe56c9` security patch is remotely verified. Keep PR #32 draft and unmodified.

Original 238 findings and 40/48/150 cohorts are unchanged. **Zero original findings independently closed.**
`AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`; numerical publication and certified 1 m resolution on HOLD.
