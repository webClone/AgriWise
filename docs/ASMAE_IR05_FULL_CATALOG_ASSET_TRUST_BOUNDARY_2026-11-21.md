# ASMAE IR-05 — Full Catalog Inventory and Asset Transport Trust Boundary
Date: 2026-11-21
Status: **Source implementation candidate, unexecuted. No production scientific qualification.**
Base: `0674fe027e66286ea63060577d0936f4a55c28ec` (the separately reported 14/14 STAC, 28/28 archive, 827/827 Layer0 and 198/198 Layer05 regression head).

## Why this batch exists
ASMAE requires the full *available* 2015+ Sentinel archive for first-open historical work. Previously, `ArchiveFetcher.orchestrate_fetch(..., manifest_only=True)` ran `ArchiveDownloadPlanner.plan_download` despite downloading zero assets. Planner has a configurable 500-scene cap, plus storage and job byte limits; it can silently omit historical catalog scenes. Even after exhaustive STAC pagination, manifest-only search could be artificially truncated.

Separately, raw asset URLs obtained from catalog items were given the CDSE bearer header without an explicit host trust check. This is a credential-leak / untrusted asset transport boundary, not an ASMAE numerical validation claim.

## Implemented on isolated branch
1. Pure `manifest_only=True` returns every newly discovered item from the fully paginated STAC search without invoking raster download storage/scene quotas. When `manifest_only=False`, all existing planner limits and partial-success failure checks remain active.
2. Asset URLs must be HTTPS, avoid credentials in the URL, and use approved hosts. Defaults permit `dataspace.copernicus.eu` or its subdomains; deployments can add explicit exact hostnames through `AGRIWISE_ARCHIVE_ALLOWED_ASSET_HOSTS`. IP-literal addresses are rejected.
3. CDSE Authorization may be transmitted only to the exact HTTPS STAC auth origin. Approved external CDN asset URLs receive no CDSE bearer token.
4. HTTP redirects are not followed; oversized, empty, missing and partial asset responses fail closed.
5. Asset downloads use temporary files, bounded streaming, `fsync`, and atomic replacement. Resources close and partial files are deleted on failure.
6. Plot/scene path components are checked before disk writes.
7. Seven new adversarial tests authored for 505-scene manifest without download quotas; disallowed URL, missing required band, approved CDN with no credentials, CDSE same-origin credentials, redirect/partial download, and plot traversal.

## Remaining gaps — not claimed solved
- No authenticated live Copernicus STAC retrieval or asset bytes executed in this review. No externally attested asset digest, crop/PSF assimilation or posterior `sigma` from this batch.
- `save_scene_manifest` currently writes each invocation's records, not a durable cumulative plot-wide history. Across independent archive windows, prior manifest data can be replaced. Worldline inventory event retention is separate. A future batch must implement durable per-window manifest epochs or reconciled append-only history with concurrent-write safety and selective revised-scene replay.
- Asset downloads currently fetch entire files rather than an independently qualified AOI crop and require provider-specific resolution, CRS, SCL, orbital/incidence and content-hash revalidation.
- A manifest inventory is **not** an `ARCHIVE_POSTERIOR_VALIDATED` event. Statewise rasters, adaptive local effective resolution, BMA/EnKF and first-open posterior reconstruction remain to be demonstrated.
- Actual HTTP access and provider credentials require environment-level validation on a nonproduction test plot.

## Test/merge gates
- `python -m pytest services/agribrain/layer0/tests/test_ir05_manifest_and_asset_security.py -q`
- `python -m pytest services/agribrain/layer0/tests/test_ir05_stac_window_completeness.py -q`
- `python -m pytest services/agribrain/layer05_asmae/tests/test_asmae_ir05_archive_bootstrap.py services/agribrain/layer05_asmae/tests/test_asmae_ir05_genuine_provider_qualification.py -q`
- Full Layer0/Layer05 regressions, native provider transport and frontend checks.
- Absent actual runs, tests count as authored only.
- Do not advance PR #32 or merge security, archive and publication heads. Maintain 238-finding register, certified 1m/numerical publication and irrigation holds.
