# AgriBrain Layer 0 — L0-004B2B Native Provider Receipt Issuance
## Pinned implementation blueprint and acceptance contract — 2026-11-03

**Status:** DESIGN AND IMPLEMENTATION PLAN ONLY. No provider issuer or signing service implemented by this document.
**Parent:** PR #16 at 952d41118322ee19d0ffe1c28c37db355e91dfb5
**Parallel track:** Scientific Pilot PR #9 at 71ee1f788ec981bd0824089e46dc68164260444d remains independent.
**Governing architecture:** R3 master monograph; DO NOT modify. Historical 469-finding Layer 0 audit is frozen evidence; write new dispositions separately.
**Baseline evidence:** User-provided Windows Python 3.13.13 test receipt: 197/197 Layer 0, 21/21 Layer 1, 84/84 ASMAE at PR #16 pin, total 302/302. This is a reported local qualification, not independently executed by this authoring session.
**Unchanged/open:** L0-002 actual plot/zone physical support, L0-004 complete source authority, L0-02C3/C4 verified net infiltration, physical Q and durable replay.

---

## 1. Scientific purpose and non-negotiable trust boundary

L0-004B2B is the **trusted producer** counterpart of the existing signed-input verifier (L0-004A/B1/B2A). It must turn a provider-verified, spatially grounded and QA-qualified native acquisition into an independently issued statement that the **specific current ObservationPacket** may be admitted to **one specific state-input purpose**, for a designated plot/geometry/version/zone and bounded time.

A positive issuer decision is NOT:
- A signature over arbitrary uploaded JSON, a client-selected scene ID, a cached boolean such as real_provider_product, or user-declared quality.
- Proof that physics is calibrated, a scene truly represents a field, a prior state is measured, or an irrigation event was physically delivered.
- Permission to publish advice, execute irrigation, override MESIA spatial containment, or merge into Scientific Pilot PR #9.
- Permission to use model forecasts as observed temperature, rain, or ET0.
- A substitute for Layer 1/ASMAE source independence, state-estimate classification, and downstream pilot publication authorization.

Issuer **signing keys and source credentials remain server-only**. A remote request may identify a desired plot/time/source search; it cannot supply issuer status, evidence truth, signing secret, authoritative geometry, or final QA approval. Missing or unqualified evidence results in explicit DENIED/DEFERRED with provenance, not a fabricated certificate.

## 2. Source-verified current repository surfaces

Verified against parent SHA 952d411:

| Producer or consumer | Current source path | Existing capability / relevant gap |
|---|---|---|
| Sentinel-2 acquisition | services/agribrain/layer0/asmae_scene_products/s2_real_scene_product_fetcher.py | Sentinel Hub Catalog search plus Process API retrieval; exact-product binding, request/response hashes, SCL/dataMask, valid fraction, locally cached metadata, ASMAE_TEST_OVERRIDE. No independently controlled receipt issuer. |
| Sentinel-1 acquisition | services/agribrain/layer0/asmae_scene_products/s1_real_scene_product_fetcher.py | Catalog plus Process API, orbit/product metadata, VV/VH and dataMask, content/request/response hashes and cache. No signed issuance authority. |
| Catalog-to-process binding | services/agribrain/layer0/asmae_scene_products/product_binding.py | verify_exact_product_binding checks expected product identity against returned tile userdata; this is necessary but not independently authenticated authorization. |
| Scene source packages | services/agribrain/layer0/asmae_scene_products/scene_product_schema.py and scene_product_store.py | Recorded provider product IDs, response hash, processing metadata and local band-file references. A local JSON file and a content digest can be replaced; neither is a provider signature. |
| Sentinel-2 packet producer | services/agribrain/layer0/sentinel2/packetizer.py | Scene QA and provenance packets, usable indices and raster references; geometry identity can be supplied at packetization. These packet flags are evidence, never a grant. |
| Sentinel-1 packet producer | services/agribrain/layer0/sentinel1/packetizer.py | SAR QA and provenance, plot and zone summaries, runtime-supplied scope fields. Need issuer-side zone support confirmation. |
| Environmental processing | services/agribrain/layer0/environment/engine.py | Operates on **prefetched dictionaries**, not direct provider calls; weather normalization and consensus are separate transformations. No native credential-bound response trace established here. |
| Weather models and consensus | services/agribrain/layer0/environment/weather/ (open_meteo.py, openweather.py, era5_land.py, consensus.py) | Historical, forecast and reanalysis semantics must not be mixed into one authority class. Consensus confidence is not provider authenticity. |
| Environmental envelopes | services/agribrain/layer0/environment/packetizer.py | Emits dict envelopes such as WEATHER_PROVIDER_OBSERVATION, WEATHER_CONSENSUS_DAILY, WEATHER_FORCING_DAILY; these are NOT automatically typed signed ObservationPacket instances. |
| Admission consumer | services/agribrain/layer0/positive_observation_admission.py | Verifies full packet digest and HMAC source/scope/purpose/time, using v1 plot and v2 zone domains. Does not issue signatures. |
| Mandatory runtime | services/agribrain/layer0/production_admission.py and state_engine.py | Uses backend-only key configuration and detached receipts; runtime trust must not be weakened to accommodate an issuer. |
| Revocation | services/agribrain/layer0/issuer_revocation.py | Checks file-backed trusted snapshots with freshness and in-worker monotonic revision. **Snapshot content is not externally signed**. Digest is a content identifier, not a third-party signature; cross-worker durability remains open. |
| Receipt transport and lineage | services/agribrain/layer0/runner.py, state_engine.py, source_package.py | Detached receipts to the state engine; successfully admitted observations/effective weather are rooted in input manifest/output hash; still NOT pilot publication authority. |

**Special risk in current acquisition:** S2 Process uses mosaickingOrder=leastCC; S1 uses mosaickingOrder=mostRecent. A real response hash does not establish a unique scene unless the exact Catalog-selected product is bound to returned Process userdata and the pixel support. Cached "real" artifacts must not automatically inherit a live authorization on the basis of filename or metadata.json.

## 3. Required trust and data flow

1. **Trusted acquisition worker:** authenticate to an allowlisted provider using backend-managed credentials, collect its request, response and authenticated-transport context, and persist the raw evidence bytes/metadata. No user response body is authoritative.
2. **Immutable acquisition record:** compute SHA-256 over the raw response payload and relevant normalized metadata; persist immutable references and provider request/product identity. No hash-only "proof of origin" claim.
3. **Independent provider-specific qualifier:** check product/catalog/process binding, acquisition time, required bands/masks/orbits, QA, declared units/processing chain and a trusted plot/zone geometry snapshot.
4. **MESIA-support validator:** prove actual raster coverage and support with explicit CRS, pixel grid, field polygon version, mask fraction and excluded external contamination. If not implemented, issuer must defer localized zone grants.
5. **Source authority decision:** determine what the validated evidence may influence (plot-observation, zone-observation, weather forcing, diagnostics only, or forecast scenario), using server-held policy and scientific eligibility—not packet flags.
6. **Privileged receipt issuer:** sign an exact packet digest and server-held scope/role/expiry, following a uniquely versioned receipt schema; persist an append-only issuance decision/denial and policy revision.
7. **Existing verifier:** verify signature or HMAC, current packet digest, scope, purpose, live revocation, and run time. Preserve the current state input manifest and do not elevate state estimates to raw observations.
8. **Separate publication gate:** on a future **pinned integration branch**, recheck parent grant validity and revocation and bind the exact accepted Layer 0 input root into Layer 1/ASMAE and the pilot publication root. L0 never grants this itself.

No single module should accept both a caller-supplied provider response and a caller-supplied issuer signing key. Avoid dual-use endpoints that allow arbitrary packet-signing requests.

## 4. Typed producer evidence contract (new, immutable)

Proposed objects: NativeAcquisitionReceipt, QualifiedNativeEvidence, IssuanceDecision, DetachedStateInputGrant.

NativeAcquisitionReceipt (created only by acquisition worker):
- acquisition_id and source_adapter_version; trusted backend service identity and execution ID.
- provider_name, endpoint/collection and request class, provider_response_id or request ID (if supplied), bounded catalog_item_id and provider_product_id.
- acquisition_start/end, retrieval_utc, observed coverage window and provider model/run time when applicable.
- SHA-256 of exact raw response bytes, canonical request, output bands/masks and any metadata or userdata; immutable object-version references and artifact checksums.
- backend credential reference ID (NOT the secret/token), transport outcome and stable source status; provider license/retention policy.
- explicit origin_class = LIVE_PROVIDER_AUTHENTICATED | PROVENANCE_VERIFIED_CACHE | REANALYSIS | FORECAST | TEST_FIXTURE | USER_DECLARED.
- cached/fixture/replayed objects cannot be re-labelled LIVE_PROVIDER_AUTHENTICATED without independently proving original acquisition lineage.

QualifiedNativeEvidence:
- reference to immutable acquisition_id and exact artifact version(s); qualified source modality.
- provider-specific binding details, spatial grid/transform/CRS and actual support fraction; acquisition UTC interval and declared time-role.
- quality model/version and **measured** valid-mask/support values; per-variable measurement units, sigma, permitted observation variables and provenance.
- operator/algorithm version, input object hashes, source quality flags and explicit exclusion reasons.
- authoritative plot ID, plot geometry hash/version, tenant authorization result and zone ID/zone geometry hash when applicable.
- status QUALIFIED | DIAGNOSTIC_ONLY | DEFERRED | REJECTED; never silently promote UNKNOWN.
- immutable qualification decision ID and policy/config revision.

IssuanceDecision:
- decision_id, source evidence ID, exact observation_packet_digest(), purpose, issuer identity/key ID, trusted policy revision, authoritative scope and issued/expiry time.
- accepted/rejected with machine-readable reason; a negative decision must not contain a usable grant.
- deterministic deduplication key for same evidence/packet/scope/purpose/policy; issuance ledger retains history across restarts.

### Versioning requirement

Current verifier understands GRANT_DOMAIN (v1 plot HMAC) and ZONE_GRANT_DOMAIN (v2 zonal HMAC), with exact field sets. **Do not append issuer evidence fields to v1/v2** and quietly assume the verifier will accept them.

B2B compatibility choices:
- **Transition-only:** a narrowly isolated internal issuer may create existing v1/v2 HMAC grants after trusted validation. The same symmetric secret is necessary to verify, so strict role isolation and key distribution remain a risk.
- **Target:** versioned v3 **asymmetric** receipt envelope (KMS/HSM-backed private signing key, separate public verification key), with signed evidence_id, science-qualification/policy hash, source product ID, geometry support proof root, time role, permitted variable set, source lineage root, tenant/plot authority and explicit revocation revision. Add a new verifier branch and acceptance suite before enabling v3; never reuse v1/v2 domain bytes with new semantics.

Choose the receipt wire version in an explicit architecture decision record (ADR) before implementing the issuer. Preferred production end-state is v3 separated signing and verification, not an HMAC endpoint reachable from general Layer 0 ingestion workers.

## 5. Module-by-module implementation phases

### L0-004B2B-01 — Origin capture and immutable evidence

**Primary module:** new services/agribrain/layer0/native_issuer/acquisition_evidence.py
**Integration:** S1/S2 real-scene fetchers; new weather-provider fetch adapter; protected object store.

Tasks:
- Record authenticated backend acquisition and raw response/object hashes **at fetch time**, with bounded request IDs and exact provider endpoints.
- Persist content and metadata atomically; read back immutable version ID and digest. Do not trust metadata.json alone.
- Separate live provider responses from cached files, test overrides, experimental composites and simulations.
- Define cache requalification from previously recorded trusted acquisition receipts, not from relabelled local disk files.
- Apply SSRF protections, TLS verification, allowlisted provider endpoints, bounded retries, response size and TAR/GeoTIFF parsing limits.

**Gate:** changing response bytes, product metadata or stored object version invalidates eligibility; mock/fixture/cache without original evidence cannot issue a live-observation grant.

### L0-004B2B-02 — Sentinel-2 native qualifier

**Primary module:** new native_issuer/sentinel2_qualifier.py
**Existing sources:** s2_real_scene_product_fetcher.py, product_binding.py, sentinel2/qa.py, sentinel2/packetizer.py

Tasks:
- Validate Catalog item ID, collection (Sentinel-2 L2A), selected datetime, Process userdata and exact product binding; no product-mosaic uncertainty disguised as a unique product.
- Independently verify required B04/B08 + SCL/dataMask and any other bands used for NDRE/NDMI, proper units/ranges, no undocumented gap fill, physically usable masks and finite scalar summaries.
- Bind actual raw band hashes and grid support, cloud/shadow/snow/coverage eligibility and QA version. Avoid signing QA/provenance-only packets as Kalman observations.
- Match the verified scene and plot polygon to exact caller-owned geometry version and immutable scene selection.
- Produce immutable QA record and permitted scientific variables; sign the exact resulting packet only after these checks.

**Gate:** wrong Catalog/Process product, missing mask, cloud-only zero-quality, invalid support, mismatched pixel grid or modified NDVI/sigma => no state-update grant.

### L0-004B2B-03 — Sentinel-1 native qualifier

**Primary module:** new native_issuer/sentinel1_qualifier.py
**Existing sources:** s1_real_scene_product_fetcher.py, sentinel1/orbit.py, sentinel1/qa.py and packetizer.py

Tasks:
- Require identity match for Catalog-selected Sentinel-1 GRD product and Process response; verify orbit direction, relative/absolute orbit and acquisition timestamp provenance where available.
- Validate polarization, incidence angle, VV/VH units and validMask, no inappropriate mixing of orbit tracks, clear pixel coverage, calibration flags, speckle/border noise and stable grid support.
- Reject missing/ambiguous orbit metadata when the consumer claims independently observed multi-temporal SAR.
- Apply plot/zone geometry support and per-variable sigma qualification before issuing a SAR observation grant.

**Gate:** wrong orbit, cross-track conflict, missing polarization or mask, unusable scene and unsupported spatial support => diagnostic/deferred, not positive Kalman grant.

### L0-004B2B-04 — Weather provenance and forecast isolation

**Primary modules:** new native_issuer/weather_acquisition.py and weather_qualifier.py
**Existing sources:** environment/engine.py, weather/open_meteo.py, openweather.py, era5_land.py, consensus.py, environment/packetizer.py

Tasks:
- Establish **trusted native fetch boundaries** upstream of EnvironmentalEngine.process(), because it currently receives prefetched dictionaries rather than making authenticated provider calls.
- Distinguish MEASURED_STATION, HISTORICAL_PROVIDER, REANALYSIS_MODEL, FORECAST_MODEL and DERIVED_CONSENSUS in typed evidence.
- Bind provider request and raw daily/hourly response, location/grid-cell support, UTC times, units, provider vintage/model run + lead time and original variable availability.
- Explicitly protect legitimate zero rainfall, time-zone/DST boundaries and missing values. Preserve raw source values alongside derived ET0/consensus fields and their science version.
- A derived consensus may only have a state-input grant if every materially contributing parent source evidence is authenticated and its weights/selection rule are bound. Never sign "consensus_average" as a standalone native provider.
- Weather forecasts require a distinct forecast/scenario purpose and may **not** use weather_state_forcing for an observed historical state unless an independently authorized science contract permits a strictly labelled modeled-forcing path.
- Do not create VPD or other observed-weather claims from missing drivers; missing forcing remains visible.

**Gate:** absent authenticated provider evidence, future-only forecast, provider value substitution, missing rain/ET0/temperature, wrong location/day or mixed historical/forecast lineage cannot obtain an observed-weather grant.

### L0-004B2B-05 — Trusted spatial/tenant admission

**Primary modules:** new native_issuer/spatial_authority.py and trusted plot/zone registry interface
**Dependencies:** MESIA SI-BCA geometric support checks and actual provider raster lattice.

Tasks:
- Derive plot and zone identity from trusted backend authorization context, not packet payload or user-supplied geometry hash.
- Require immutable polygon/version, zone polygons, CRS transformation, grid alignment and coverage/support metrics; prove containment without assuming a matching hash proves physical footprint.
- Quantify partial coverage, cross-boundary contamination, masked area and spatial interpolation support with a stored proof.
- Grant plot-scoped state only where valid. Zone v2 grants need actual qualified zone-local support, not cloned plot-wide evidence.
- Resolve tenant/owner and historical boundary-version rights at issuance time; reject wrong-tenant, changed geometry or stale data windows.

**Gate:** foreign plot, invalid polygon, zero overlap, out-of-zone pixels, unsupported imagery or stale geometry => cannot issue scoped positive grant.

### L0-004B2B-06 — Privileged issuer and key isolation

**Primary modules:** new native_issuer/issuer_service.py, receipt_schema.py, issuance_ledger.py, policy_registry.py

Tasks:
- Implement an independently authenticated, server-internal issuance worker. It retrieves immutable QualifiedNativeEvidence **by server-controlled ID**, rechecks provider and plot authority, and never signs arbitrary packet JSON supplied by the caller.
- Verify exact packet digest *after* canonical packet generation, including QA/sigma/status, against qualified evidence. Recompute digest at signature time.
- Enforce source/purpose/variable allowlist, bounded expiration, key ID and policy revision. Deny unsupported sources and user events.
- Separate issuer signing service IAM from ingestion and verifier. Prefer asymmetric KMS/HSM v3 design; if temporary v1/v2 HMAC used, record migration limits and prohibit external signing endpoints.
- Durable append-only issuance decisions with unique idempotency key; failed/rejected issuance is retained, no duplicate re-sign on retry.
- Record key-version, activation/revocation, rejected causes and issuer audit metadata without secret exposure in logs.

**Gate:** forged acquisition ID, switched source/plot, altered QA, revoked signing key, failed KMS, retry race or unsupported purpose => no usable receipt; identical requests cannot issue inconsistent decisions.

### L0-004B2B-07 — Revocation and distributed consistency

**Primary:** revisioned durable issuer/key authority service (new adapter, no silent replacement of existing snapshot gate)

Tasks:
- Put issuer ACLs, key status and revocation revisions in a durable shared store with atomic writes, tested per-worker cache invalidation, protected operator access and authoritative freshness.
- Bind issuance decisions and key status to policy revision. On revocation, reject newly issued grants immediately; invalidate downstream publication eligibility as required.
- If snapshots distributed, sign/authenticate them independently and validate authenticity before accepting their content hash. Existing SHA digest alone is insufficient.
- Test multi-worker monotonicity, conflicting revisions, restart, lost connection, delayed propagation, key rotation and replay-cutoff semantics.
- Maintain production fail-closed behavior when revocation authority is unreachable or stale.

**Gate:** old worker or cached snapshot must not resurrect a revoked key, regardless of correct HMAC on an old grant.

### L0-004B2B-08 — End-to-end handoff and scientific pilot integration gate

**Primary:** Layer0Runner input, StateEngine, Layer 1/ASMAE consumers, pilot publication contract on a **separate pinned integration branch**.

Tasks:
- Transport only independently issued detached receipts and immutable provider evidence references. Current unverified producer paths retain DIAGNOSTIC_ONLY or explicit unavailability.
- Verify before Kalman assimilation and again at publication with trusted authority/revocation; bind source product, QA, crop/geometry/grid, weather-forcing contributor hashes, state parameter version and exact output state root.
- Ensure the Signed Input Manifest includes actual state-affecting observations and effective forcing, not superseded packets or diagnostics. Keep state_output_role=STATE_ESTIMATE and scientific_publication_authorized=False at Layer 0.
- Preserve MESIA/ASMAE scope, time, lineage, authorizations and the pilot's existing publication receipts; do not loosen the pilot gate to accept a Layer 0 signature.
- Coordinate only at explicitly pinned commits after independent tests pass; PR #9 remains untouched until a separate reviewed integration is authorized.

**Gate:** unsigned, revoked, stale, cross-zone, altered or unqualified source cannot reach an authorized pilot publication; neither Layer 0 readiness nor pilot publication permission can be inferred from green unit tests alone.

## 6. Principal API and data contracts

Interface proposals (design-only; names and wire schemas are not yet implemented):

- acquire_native(source, trusted_plot_context, window) -> NativeAcquisitionReceipt | AcquisitionFailure
- qualify_native(acquisition_id, protected_plot_geometry, science_policy_revision) -> QualifiedNativeEvidence
- issue_state_input_grant(qualification_id, generated_packet_digest, purpose, trusted_worker_identity) -> IssuanceDecision
- verify_detached_grant(receipt, current_packet, trusted_scope, security_clock) -> AdmissionResult
- assert_publication_source_lineage(state_input_manifest_root, revocation_anchor, publication_context) -> PublicationGateDecision

The issuer must not take a user-provided credential, source_verified boolean, arbitrary provider_response_hash or geometry_hash as proof. The qualifier must independently resolve those fields from trusted acquisition and backend plot authority.

For initial source coverage, prioritize:
- Sentinel-2 true product-bound live acquisition and QA.
- Sentinel-1 true product/orbit-bound live acquisition and QA.
- Open-Meteo/OpenWeather historical weather via an authenticated native fetch adapter; ERA5-Land after confirming actual upstream retrieval and model-vintage lineage.
- Forecasts only under a separate declared scenario/forecast contract (not an observed-weather grant).
- Other source modalities follow only after their own equivalent QA/provenance contracts; no generic "all providers" signature.

## 7. Required adversarial and scientific acceptance matrix

| Counterexample | Required result |
|---|---|
| Client submits valid-looking ObservationPacket plus real_provider_product=True without captured origin | DENY issuer; preserve diagnostic evidence |
| Attacker copies cached metadata.json from different scene and reuses product ID | Reject origin/content/version mismatch |
| Live Catalog item A and Process response product B | Fail exact product binding; no receipt |
| Process response contains mosaicked/ambiguous Sentinel tiles | Defer unique-scene authority; no hidden product selection |
| S2 cloud-only / valid fraction 0 / absent SCL and dataMask | No state observation grant |
| S1 mixed orbit or missing permitted polarization | No independent SAR state grant |
| Forecast 12 mm rainfall is submitted as yesterday's observed rain | Reject weather_state_forcing observed purpose |
| True observed zero rainfall | Preserve zero and permit if provider/time/scope/sigma qualification passes |
| Consensus contains a synthetic or unverified parent | No observed state forcing grant for that derived variable |
| Different packet sigma, QA, source, timestamp or payload after issuance | HMAC/signature verification fails on current digest |
| Caller-provided fake plot geometry hash matches own packet | Deny absent trusted backend plot authorization |
| Signed zone ID with no verified pixel/zone intersection | Defer/deny zone-local state authority |
| Provider changes content while keeping URL/product ID | Old immutable evidence digest/version invalid |
| Replay with valid old key after revocation | Deny in issuer AND state/pilot verifier |
| Two workers issue same idempotency key concurrently | One consistent authorized decision; no duplicate conflicting receipt |
| Signing service/KMS, provider, registry or revocation outage | Fail closed without unverified legacy assimilation |
| User-reported irrigation claims VERIFIED_DELIVERY | No net-infiltration receipt; remains event evidence only |
| Layer 0 prior-only or verified observation with no pilot publication grant | Still STATE_ESTIMATE, cannot publish or actuate |

## 8. Qualification and release gates

**G0 — source inventory:** Every production path from raw acquisition to typed packet mapped; test override, local fixture, experimental composite, cached, modeled and provider live are distinct. Pin exact file SHAs and report coverage.

**G1 — deterministic acquisition:** Live S1/S2/approved weather source response hashes, acquisition provenance and immutable store versions consistently replay. No fixture/cached-file promotion.

**G2 — qualification:** Negative/provider-identity, mask/QA, unit, time, geometry and MESIA-support cases pass, including real provider data where available.

**G3 — issuer security:** External callers cannot mint grants. KMS/IAM/secret isolation, idempotency, key lifecycle and failure-mode tests qualified. v3 wire-schema/version migration independently approved.

**G4 — runtime:** strict Layer 0 admission works with genuinely issued receipts; rejections are visible; existing 197 L0, 21 L1, and all 84 ASMAE cases re-run at the NEW exact head, not inherited from PR #16.

**G5 — distribution:** multi-worker revocation with restart, rollback, stale snapshot, cross-worker desynchronization and publication-time revocation tested against a real durable store.

**G6 — scientific pilot:** separate pinned cross-track L0 → Layer 1/ASMAE → Pilot PR #9 publication/authorization proof; no implicit merge or weakening of the pilot ledger.

**G7 — deployment:** source credential and signing-key management, least privilege, protected object store, observability/alerts, incident response, rotation and rollback exercised in staging before production.

CI/testing:
- Unit/property tests: canonicalization, digest mutation, trusted origin schema, product binding, cross-purpose, time and zone scope, idempotency and key status.
- Integration tests: Sentinel Hub authenticated Catalog→Process acquisition, immutable store, native packetizer, issuer and verifier. Provider calls must be explicitly opted in and use appropriate credentials/quota.
- Weather tests: provider response/normalization/consensus and forecast-vs-observed behavior; no invented zero or missing driver.
- Security tests: attacker-supplied fake evidence, file tampering, wrong tenant, KMS outage, mixed-role signer and distributed revocation.
- Cross-layer tests: actual Layer 0/Kalman, Layer 1 Fusion and full ASMAE suites plus pilot publication and browser/DB validations when integration is authorized.
- Report exact branch SHA, environment, collection counts, observed scientific effects, test artifacts and any excluded live-provider runs. No green claim for unexecuted tests.

## 9. Recommended sequence and decision checkpoints

1. **Design/ADR first**: freeze NativeAcquisitionReceipt and QualifiedNativeEvidence typed schemas, select v1/v2 transitional versus v3 asymmetric issuance, approve immutable object store and trust/IAM model. Do not write a generic signing endpoint.
2. **B2B-01**: implement immutable origin capture, live-vs-cached distinctions, signed-acquisition context and evidence storage; no signing yet.
3. **B2B-05 and B2B-06 (minimum trusted core)**: implement authoritative plot/zone registry adapter and policy-enforced, internal issuer interface with idempotent decisions, after the versioned schema/ADR is approved. Initially require DENY until a provider-specific qualifier is registered.
4. **B2B-02**: integrate Sentinel-2 live acquisition → QA/support proof → eligible packet digest → issuer, and validate against authentic and adversarial products.
5. **B2B-03**: Sentinel-1 product/orbit and polarization-specific qualification; do not copy S2 masks or priors blindly.
6. **B2B-04**: weather native provider fetch/qualification, parent-source lineage and explicit forecast isolation.
7. **B2B-07**: durable distributed revocation, issuer key lifecycle, and independent snapshot authenticity before production rollout.
8. **B2B-08**: new pinned integration branch, requalify the state/pilot chain; retain pilot autonomy until reviewed.

**Stop condition:** If native source evidence, authoritative plot geometry, key revocation or issuer provenance cannot be independently established, record diagnostics and keep state/publication unqualified; do not add a heuristic exception.

## 10. Disposition register at planning completion

- PR #16 / L0-004B2A: reported 302/302 software tests qualified at parent SHA, not provider-issuer production qualified.
- L0-004B2B: **SCOPED / NOT IMPLEMENTED** by this document.
- L0-002: signed plot/zone identity partial; actual geospatial support, tenant rights and MESIA containment OPEN.
- L0-004: verification/mandatory signed admission partial; real issuance, production revocation and trust-chain deployment OPEN.
- L0-001/003: earlier bounded software defects qualified by reported tests; full publication proof still separate.
- L0-02C3/C4: trusted L3 net infiltration, physically calibrated Q(Δt), durable management-event replay OPEN.
- Scientific Pilot PR #9, main, architecture monograph and frozen 469-finding audit: **not touched**.

This is a reviewable implementation plan. No provider credentials are requested, stored, signed or exposed in this document, and no new state/publication authority is granted.
