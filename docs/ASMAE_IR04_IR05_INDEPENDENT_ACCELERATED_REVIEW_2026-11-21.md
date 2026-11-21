# ASMAE accelerated independent qualification — 2026-11-21

## Verified remote baseline
- Security branch \`feat/akaloris-asmae-ir04-r03-r04-review-20261119\` at \`cf521af9749265f5ecc0e7b14ae75df887ba96d9\`.
- Historical branch \`feat/akaloris-asmae-ir05-archive-integrity-batch-20261119\` at \`ad3fc5704fbc3f937a4923e0ec36a8e2e2bc395d\`.
- Draft PR #32 remains open/draft at \`64a9f69945d8e3eda2bf33de9ff24e98186c9a17\`.
- No GitHub check runs found at either published head at review time. User reports local IR05 15 historical / 11 Gate B / 196 full Layer05 / 341 frontend and tsc clean; this review has not independently executed them.
- The original 238 finding records, signed irrigation hold, numerical publication hold, 1m certification hold remain unchanged.

## Review pass A: Admission/cryptography

**IR04-Q01 — Journal-issued bitemporal authority not proven (P1 qualification blocker).**
\`resolution/observation_footprint_adapter.py::verify_bitemporal_replay_receipt\` validates receipt schema, tenant/plot/geometry equality, recomputes the digest of the *same receipt's selected_evidence_set*, and checks K against an *optional* journal_watermark. There is no independent journal hydration or signature/externally provisioned journal anchor inside that verifier; a digest made by the same party that supplies the evidence is not authenticity. Distinguish journal-consistent from journal-authenticated. Gate: rehydrate event IDs from trusted immutable Worldline at T and K, match event hash/namespace/watermark, and require signed or out-of-band trusted anchor before granting historical science.

**IR04-Q02 — Legacy classifier proof has weaker scope (P1 qualification blocker).**
\`evidence_classifier.py::_is_valid_proof\` retains an explicitly registered HMAC bytes fallback and signs only \`trust_root:geometry:valid_until\`, not asset bytes, scene identity, tenant, operator, sensor or purpose. Default keys are empty and old embedded secrets are removed (material improvement). Do not label the legacy fallback equivalent to signed positive admission. Gate: disable legacy HMAC for scientific authority; scope external public-key proof to immutable scene, namespace, source/purpose, observation T, commitment K, and operator.

## Review pass B: STAC historical truthfulness

**IR05-Q01 — Manifest-mode asset provenance (P1 integration blocker).**
\`create_copernicus_archive_provider\` defaults to \`manifest_only=True\`. \`ArchiveFetcher.orchestrate_fetch\` can compute the 64-hex \`source_content_hash\` using catalog metadata and \`scene.remote_hash\`, not verified raster bytes. Test IR05-T15 uses a MockFetcher. The bridge is valid *inventory* functionality; it has not demonstrated live Copernicus asset acquisition, state assimilation, weather coverage, 13 state maps or effective-resolution qualification.

**IR05-Q02 — Quota failure could fake archive coverage (P1 integration blocker).**
Previously \`ArchiveFetcher.orchestrate_fetch\` returned \`existing_records\` if \`download_planner.plan_download\` failed; empty results could then be interpreted by bootstrap as a genuinely empty completed window. Patched to fail explicitly on isolated review branch.

**IR05-Q03 — Spatial namespace binding of provider records (P1 integration blocker).**
Previous bridge accepted records without independently comparing returned \`plot_id\` and \`geometry_hash\` with requested values. Patched on review branch to reject cross-plot, cross-geometry, unqualified and source-out-of-scope entries.

## This review branch — candidate only, not independently qualified
\`feat/akaloris-asmae-ir05-provider-truthfulness-20261121\` based exactly on \`ad3fc57\`.

Implemented:
1. In \`archive_fetcher.py\`, quota-denied/incomplete download planning raises \`archive_download_plan_incomplete\` instead of silently returning an empty or partial manifest.
2. In \`archive_bootstrap_service.py\`, STAC manifests must bind plot, SHA-256 of requested WKT geometry, allowed sensor and accepted record status. Inventory events explicitly contain \`asset_content_verified=False\` and \`source_hash_kind\`: \`manifest_metadata_digest\` or \`archive_fetcher_composite_digest\`. No raw byte authority is inferred from the shape of a digest.
3. In \`test_asmae_ir05_archive_bootstrap.py\`, existing STAC bridge fixture is updated and new negative controls reject foreign plot/geometry, unsupported sensor and candidate quality, and incomplete quota/provider windows. Total authored IR05 tests: 17.

Required qualification:
- Execute all 17 historical tests, 11 Gate B tests and complete Layer05, Worldline, frontend, TypeScript regressions on exact branch head; capture SHA+logs.
- Live authenticated STAC query + paging + retrieval receipts for S1/S2, real raster-byte hashes, cloud/SCL masking, AOI/CRS, and missing windows.
- Verify quote/quotas and HTTP failures never produce false \`COMPLETED\` checkpoints.
- Verify first-open full available 2015+ history, durable posterior/EnKF event DAG and next-open incremental continuation. The inventory service alone does not deliver scientific posteriors.
- Preserve separate effective state×cell×time resolution; display resampling never creates authority.
- Independently verify \`cf521af\` IR04 authority gap before combining branches. No PR32 fast-forward or merge.

## Release decision
**HOLD** independent security and historical scientific acceptance, even though source changes and reported local tests represent progress. Preserve 238 master findings (0 independently closed). Certified 1 m, numerical scientific publication and physical actuation remain on HOLD.
